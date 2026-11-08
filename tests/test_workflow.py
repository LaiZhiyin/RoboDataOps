import json

import pytest

from robodataops.demo import default_targets, generate_demo
from robodataops.errors import ValidationError
from robodataops.export import plan_csv, plan_json
from robodataops.ingest import load_batch
from robodataops.metrics import context_for, coverage, episode_states, planning_tasks
from robodataops.models import digest
from robodataops.planning import solve
from robodataops.quality import audit_batch
from robodataops.store import Store


def test_review_changes_counts_once_and_keeps_history(tmp_path):
    batch = load_batch(generate_demo(tmp_path / "data"))
    audit = audit_batch(batch)
    store = Store(tmp_path / "history.duckdb")
    store.record_audit(batch, audit)
    store.record_audit(batch, audit)
    target = default_targets()
    before = coverage(batch, audit, {}, target)
    finding = next(f for f in audit.findings if f.episode_index == 64)
    store.review(finding.finding_id, "dismissed", "正常保持动作", event_id="first")
    store.review(finding.finding_id, "dismissed", "正常保持动作", event_id="first")
    after = coverage(batch, audit, store.reviews(audit.run_id), target)
    assert int(after.accepted.sum()) == int(before.accepted.sum()) + 1
    assert len(store.history(audit.run_id)) == 1
    store.review(finding.finding_id, "deferred", "需要更多上下文", event_id="second")
    assert len(store.history(audit.run_id)) == 2
    assert digest(before.to_dict("records")) == digest(
        coverage(batch, audit, store.reviews(audit.run_id), target).to_dict("records")
    )
    assert len(episode_states(batch, audit)) == 100
    assert int(before.received.sum()) == 99  # Unknown task 999 is shown separately.
    store.close()


def test_blocked_dominates_unchecked_and_other_pending_findings(tmp_path):
    batch = load_batch(generate_demo(tmp_path, count=2))
    audit = audit_batch(batch)
    audit.completed[1] = False
    assert episode_states(batch, audit)[1]["status"] == "blocked"
    reviews = {
        f.finding_id: {"decision": "dismissed"} for f in audit.findings if f.episode_index == 1
    }
    assert episode_states(batch, audit, reviews)[1]["status"] == "unchecked"


def test_plan_snapshot_and_export_survive_later_review_changes(tmp_path):
    batch = load_batch(generate_demo(tmp_path))
    audit = audit_batch(batch)
    targets = default_targets()
    store = Store()
    store.record_audit(batch, audit)
    tasks = planning_tasks(coverage(batch, audit, {}, targets))
    plan_id = store.save_plan(solve(tasks, 30000), tasks, context_for(batch, audit, {}, targets))
    original = store.plan(plan_id)
    row = next(f for f in audit.findings if f.episode_index == 64)
    store.review(row.finding_id, "dismissed", "人工确认可用于当前用途")
    assert store.plan(plan_id) == original
    assert json.loads(plan_json(original))["plan_id"] == plan_id
    assert "new_accepted_episodes" in plan_csv(original).decode("utf-8-sig")
    assert (
        context_for(batch, audit, {}, targets)["acceptance_id"]
        != context_for(batch, audit, store.reviews(audit.run_id), targets)["acceptance_id"]
    )


def test_review_requires_original_finding_and_reason():
    store = Store()
    with pytest.raises(ValidationError):
        store.review("unknown", "dismissed", "reason")


def test_reimport_same_source_is_idempotent(tmp_path):
    root = generate_demo(tmp_path)
    assert load_batch(root).snapshot_id == load_batch(root).snapshot_id
