"""Append-only audit/review history and immutable planning snapshots."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from threading import RLock

import duckdb

from robodataops.errors import ValidationError
from robodataops.models import Audit, Batch, Plan, PlanningTask, canonical_json, digest
from robodataops.planning import validate_allocation

# Separate Streamlit connections can otherwise both observe an empty receipt
# ledger. The supported local server has one process and serial receipt writes.
_RECEIPT_LOCK = RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (1) ON CONFLICT DO NOTHING;
CREATE SEQUENCE IF NOT EXISTS review_sequence START 1;
CREATE TABLE IF NOT EXISTS audit_runs(
    run_id VARCHAR PRIMARY KEY, snapshot_id VARCHAR NOT NULL,
    source_json VARCHAR NOT NULL, profile_json VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS findings(
    finding_id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL REFERENCES audit_runs(run_id),
    episode_index INTEGER NOT NULL, payload VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS review_events(
    event_id VARCHAR PRIMARY KEY, finding_id VARCHAR NOT NULL REFERENCES findings(finding_id),
    decision VARCHAR NOT NULL CHECK(decision IN ('confirmed','dismissed','deferred')),
    reason VARCHAR NOT NULL, actor VARCHAR NOT NULL,
    event_sequence BIGINT DEFAULT nextval('review_sequence'),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS plans(
    plan_id VARCHAR PRIMARY KEY, payload VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS receipts(
    receipt_id VARCHAR PRIMARY KEY, plan_id VARCHAR NOT NULL REFERENCES plans(plan_id),
    payload VARCHAR NOT NULL, created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(path))
        self.connection.execute(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def record_audit(self, batch: Batch, audit: Audit) -> None:
        source = {
            "repo_id": batch.repo_id,
            "revision": batch.revision,
            "source_kind": batch.source_kind,
        }
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self.connection.execute(
                "INSERT INTO audit_runs(run_id,snapshot_id,source_json,profile_json) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                [
                    audit.run_id,
                    batch.snapshot_id,
                    canonical_json(source),
                    canonical_json(audit.profile),
                ],
            )
            if audit.findings:
                self.connection.executemany(
                    "INSERT INTO findings(finding_id,run_id,episode_index,payload) VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                    [
                        (f.finding_id, audit.run_id, f.episode_index, canonical_json(f))
                        for f in audit.findings
                    ],
                )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def review(
        self,
        finding_id: str,
        decision: str,
        reason: str,
        *,
        actor: str = "local-reviewer",
        event_id: str | None = None,
    ) -> str:
        if decision not in {"confirmed", "dismissed", "deferred"}:
            raise ValidationError("复核决定必须是确认、驳回或暂缓")
        if not isinstance(reason, str) or not reason.strip():
            raise ValidationError("请填写复核理由")
        if not self.connection.execute(
            "SELECT 1 FROM findings WHERE finding_id=?", [finding_id]
        ).fetchone():
            raise ValidationError("找不到原始发现，请重新运行检查")
        event_id = event_id or uuid.uuid4().hex
        values = (finding_id, decision, reason.strip(), actor)
        existing = self.connection.execute(
            "SELECT finding_id,decision,reason,actor FROM review_events WHERE event_id=?",
            [event_id],
        ).fetchone()
        if existing:
            if existing != values:
                raise ValidationError("复核事件 ID 已用于不同内容")
            return event_id
        self.connection.execute(
            "INSERT INTO review_events(event_id,finding_id,decision,reason,actor) VALUES (?,?,?,?,?)",
            [event_id, *values],
        )
        return event_id

    def reviews(self, run_id: str) -> dict[str, dict]:
        rows = self.connection.execute(
            """
            SELECT finding_id,decision,reason,actor,event_id,event_sequence FROM (
                SELECT e.*, ROW_NUMBER() OVER (PARTITION BY e.finding_id ORDER BY event_sequence DESC) AS rank
                FROM review_events e JOIN findings f USING(finding_id) WHERE f.run_id=?
            ) WHERE rank=1
        """,
            [run_id],
        ).fetchall()
        return {
            row[0]: dict(
                zip(
                    ("decision", "reason", "actor", "event_id", "event_sequence"),
                    row[1:],
                    strict=True,
                )
            )
            for row in rows
        }

    def history(self, run_id: str) -> list[dict]:
        cursor = self.connection.execute(
            """
            SELECT e.finding_id, f.episode_index, e.decision, e.reason, e.actor,
                   e.event_id, e.event_sequence, CAST(e.created_at AS VARCHAR) AS created_at
            FROM review_events e JOIN findings f USING(finding_id)
            WHERE f.run_id=? ORDER BY event_sequence DESC
        """,
            [run_id],
        )
        names = [item[0] for item in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def save_plan(self, plan: Plan, tasks: list[PlanningTask], context: dict) -> str:
        if plan.status not in {"optimal", "feasible", "heuristic", "no_gap"}:
            raise ValidationError("没有通过独立可行性验证的方案不能保存")
        validate_allocation(tasks, plan.budget_cents, plan.allocation)
        required = {
            "snapshot_id",
            "run_id",
            "acceptance_id",
            "targets_id",
            "repo_id",
            "revision",
            "source_kind",
            "profile",
            "profile_id",
            "robot_type",
            "data_contract",
            "existing_source_ids",
        }
        if not required <= context.keys():
            raise ValidationError("方案缺少来源、验收或目标版本")
        payload = {"plan": plan, "tasks": tasks, "context": context, "format_version": 1}
        plan_id = digest(
            {
                "allocation": plan.allocation,
                "strategy": plan.strategy,
                "budget": plan.budget_cents,
                "tasks": tasks,
                "context": context,
            }
        )
        self.connection.execute(
            "INSERT INTO plans(plan_id,payload) VALUES (?,?) ON CONFLICT DO NOTHING",
            [plan_id, canonical_json(payload)],
        )
        return plan_id

    def plan(self, plan_id: str) -> dict:
        row = self.connection.execute(
            "SELECT payload FROM plans WHERE plan_id=?", [plan_id]
        ).fetchone()
        if row is None:
            raise ValidationError("找不到已保存方案")
        return {"plan_id": plan_id, **json.loads(row[0])}

    def list_plans(self) -> list[dict]:
        return [
            {"plan_id": row[0], "created_at": row[1]}
            for row in self.connection.execute(
                "SELECT plan_id,CAST(created_at AS VARCHAR) FROM plans ORDER BY created_at DESC"
            ).fetchall()
        ]

    def receive(self, plan_id: str, batch: Batch, audit: Audit) -> dict:
        with _RECEIPT_LOCK:
            return self._receive_locked(plan_id, batch, audit)

    def _receive_locked(self, plan_id: str, batch: Batch, audit: Audit) -> dict:
        from robodataops.delivery import reconcile

        self.record_audit(batch, audit)
        reviews = self.reviews(audit.run_id)
        receipt_id = digest(
            {"plan": plan_id, "batch": batch.snapshot_id, "run": audit.run_id, "reviews": reviews}
        )
        existing = self.connection.execute(
            "SELECT payload FROM receipts WHERE receipt_id=?", [receipt_id]
        ).fetchone()
        if existing:
            return json.loads(existing[0])
        # Read, deduplicate and save as one transaction in the local single writer.
        self.connection.execute("BEGIN TRANSACTION")
        try:
            previous = [
                json.loads(row[0])
                for row in self.connection.execute("SELECT payload FROM receipts").fetchall()
            ]
            receipt = reconcile(self.plan(plan_id), batch, audit, reviews, previous)
            receipt["receipt_id"] = receipt_id
            self.connection.execute(
                "INSERT INTO receipts(receipt_id,plan_id,payload) VALUES (?,?,?)",
                [receipt_id, plan_id, canonical_json(receipt)],
            )
            self.connection.execute("COMMIT")
            return receipt
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def receipts(self, plan_id: str) -> list[dict]:
        return [
            json.loads(row[0])
            for row in self.connection.execute(
                "SELECT payload FROM receipts WHERE plan_id=? ORDER BY created_at", [plan_id]
            ).fetchall()
        ]
