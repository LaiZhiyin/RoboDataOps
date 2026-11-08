"""Reduce findings to one acceptance state per episode, then aggregate in SQL."""

from __future__ import annotations

from collections import defaultdict
from importlib.resources import files

import duckdb
import pandas as pd

from robodataops.contracts import action_contract
from robodataops.errors import ValidationError
from robodataops.models import Audit, Batch, PlanningTask, Target, digest
from robodataops.planning import validate_task_fields

STATUS_LABELS = {
    "accepted": "按当前口径计入",
    "blocked": "阻断",
    "pending": "待复核",
    "unchecked": "未检查 / 证据不足",
}


def episode_states(
    batch: Batch, audit: Audit, reviews: dict[str, dict] | None = None
) -> list[dict]:
    reviews = reviews or {}
    grouped = defaultdict(list)
    for finding in audit.findings:
        grouped[finding.episode_index].append(finding)
    states = []
    for episode in batch.episodes:
        related = grouped[episode.episode_index]
        active = [(f, reviews.get(f.finding_id, {}).get("decision")) for f in related]
        hard_block = any(
            (f.automatic_block and decision != "dismissed") or decision == "confirmed"
            for f, decision in active
        )
        required_complete = audit.completed.get(episode.episode_index, False)
        if hard_block:
            status = "blocked"
        elif not required_complete:
            status = "unchecked"
        elif any(decision not in {"dismissed", "confirmed"} for _, decision in active):
            status = "pending"
        else:
            status = "accepted"
        technical_clear = required_complete and not any(
            f.automatic_block and decision != "dismissed" for f, decision in active
        )
        states.append(
            {
                "episode_index": episode.episode_index,
                "task_id": episode.task_id,
                "status": status,
                "technical_clear": technical_clear,
                "checked": required_complete,
                "length": len(episode.rows),
                "declared_length": episode.declared_length,
                "finding_count": len(related),
            }
        )
    return states


def coverage(batch: Batch, audit: Audit, reviews: dict, targets: list[Target]) -> pd.DataFrame:
    for target in targets:
        if not isinstance(target.parameter_source, str) or target.parameter_source not in {
            "simulated",
            "user_input",
            "historical_estimate",
        }:
            raise ValidationError("业务参数来源不在支持范围")
        if not isinstance(target.rationale, str):
            raise ValidationError("参数依据必须是文本")
        if target.parameter_source != "simulated" and not target.rationale.strip():
            raise ValidationError("用户输入或历史估计需要填写依据")
    states = pd.DataFrame(
        episode_states(batch, audit, reviews),
        columns=[
            "episode_index",
            "task_id",
            "status",
            "technical_clear",
            "checked",
            "length",
            "declared_length",
            "finding_count",
        ],
    )
    target_rows = [
        {
            "task_id": t.task_id,
            "target": t.target,
            "cost_cents": t.cost_cents,
            "capacity": t.capacity,
            "weight": t.weight,
            "parameter_source": t.parameter_source,
            "task": batch.tasks.get(t.task_id, f"未命名任务 {t.task_id}"),
        }
        for t in targets
    ]
    provisional = [
        PlanningTask(t.task_id, t.task_id, t.target, t.cost_cents, t.capacity, t.weight)
        for t in targets
    ]
    validate_task_fields(provisional, 0)
    if not targets:
        return pd.DataFrame(
            columns=[
                "task_id",
                "target",
                "cost_cents",
                "capacity",
                "weight",
                "parameter_source",
                "task",
                "received",
                "checked",
                "technical_clear",
                "accepted",
                "blocked",
                "pending",
                "unchecked",
                "deficit",
                "optimistic_deficit",
                "attainment",
                "deficit_share",
            ]
        )
    columns = ["task_id", "target", "cost_cents", "capacity", "weight", "parameter_source", "task"]
    with duckdb.connect() as connection:
        connection.register("episode_states", states)
        connection.register("targets", pd.DataFrame(target_rows, columns=columns))
        sql = files("robodataops").joinpath("sql/coverage.sql").read_text(encoding="utf-8")
        return connection.execute(sql).fetchdf()


def planning_tasks(frame: pd.DataFrame) -> list[PlanningTask]:
    return [
        PlanningTask(
            str(row.task_id),
            str(row.task),
            int(row.deficit),
            int(row.cost_cents),
            int(row.capacity),
            float(row.weight),
            int(row.accepted),
            int(row.target),
            str(row.parameter_source),
        )
        for row in frame.itertuples(index=False)
    ]


def context_for(batch: Batch, audit: Audit, reviews: dict, targets: list[Target]) -> dict:
    return {
        "snapshot_id": batch.snapshot_id,
        "run_id": audit.run_id,
        "acceptance_id": digest(
            {"snapshot": batch.snapshot_id, "profile": audit.profile, "reviews": reviews}
        ),
        "targets_id": digest(sorted(targets, key=lambda t: t.task_id)),
        "repo_id": batch.repo_id,
        "revision": batch.revision,
        "source_kind": batch.source_kind,
        "profile": audit.profile,
        "acceptance_policy": "tabular_contract_and_review_v1",
        "profile_id": audit.profile.profile_id,
        "robot_type": batch.info.get("robot_type", "unknown"),
        "data_contract": {
            "fps": batch.info["fps"],
            "features": batch.info["features"],
            "action_semantics": action_contract(batch.manifest),
        },
        "existing_source_ids": [ep.episode_index for ep in batch.episodes],
        "parameter_notice": "成本、产能与目标均为情景输入；不是实际采集成本或策略效果",
    }
