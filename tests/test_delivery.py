from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from robodataops.demo import default_targets, generate_demo
from robodataops.errors import ValidationError
from robodataops.ingest import load_batch
from robodataops.metrics import context_for, coverage, planning_tasks
from robodataops.planning import solve
from robodataops.quality import audit_batch
from robodataops.store import Store


def test_returned_batches_do_not_credit_baseline_or_prior_receipts(tmp_path):
    root = generate_demo(tmp_path, injected=False)
    original = load_batch(root, list(range(50)))
    audit = audit_batch(original)
    targets = default_targets(["0", "1"])
    store = Store()
    store.record_audit(original, audit)
    tasks = planning_tasks(coverage(original, audit, {}, targets))
    plan_id = store.save_plan(
        solve(tasks, 100000), tasks, context_for(original, audit, {}, targets)
    )
    incoming = load_batch(root, list(range(40, 80)))
    receipt = store.receive(plan_id, incoming, audit_batch(incoming))
    assert receipt["baseline_or_duplicate"] == 10
    assert sum(row["credited"] for row in receipt["items"]) == 5
    assert store.receive(plan_id, incoming, audit_batch(incoming)) == receipt
    later = load_batch(root, list(range(50, 100)))
    second = store.receive(plan_id, later, audit_batch(later))
    assert sum(row["credited"] for row in second["items"]) == 0


@pytest.mark.parametrize("change", ["robot_type", "fps", "action"])
def test_delivery_requires_original_platform_and_data_contract(tmp_path, change):
    root = generate_demo(tmp_path, injected=False)
    original = load_batch(root, [0, 1])
    audit = audit_batch(original)
    targets = default_targets(["0"])
    store = Store()
    store.record_audit(original, audit)
    tasks = planning_tasks(coverage(original, audit, {}, targets))
    plan_id = store.save_plan(
        solve(tasks, 100000), tasks, context_for(original, audit, {}, targets)
    )
    incoming = load_batch(root, [2, 3])
    if change == "action":
        incoming.info["features"]["action"]["shape"] = [8]
        for ep in incoming.episodes:
            for row in ep.rows:
                row["action"].append(0.1)
    else:
        incoming.info[change] = "other-platform" if change == "robot_type" else 20.0
    with pytest.raises(ValidationError, match="契约"):
        store.receive(plan_id, incoming, audit_batch(incoming))


def test_two_connections_cannot_credit_overlapping_receipts_twice(tmp_path):
    from robodataops.models import Target

    root = generate_demo(tmp_path / "data", injected=False)
    original = load_batch(root, [0, 1])
    audit = audit_batch(original)
    targets = [Target("0", 4, 100, 10)]
    path = tmp_path / "shared.duckdb"
    first, second = Store(path), Store(path)
    first.record_audit(original, audit)
    tasks = planning_tasks(coverage(original, audit, {}, targets))
    plan_id = first.save_plan(solve(tasks, 1000), tasks, context_for(original, audit, {}, targets))
    batches = [load_batch(root, [2]), load_batch(root, [2, 3])]
    audits = [audit_batch(batch) for batch in batches]
    start = Barrier(2)

    def receive(index):
        start.wait(timeout=5)
        return [first, second][index].receive(plan_id, batches[index], audits[index])

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(receive, range(2)))
    assert sum(row["credited"] for receipt in receipts for row in receipt["items"]) == 2
    keys = [key for receipt in receipts for key in receipt["new_source_keys"]]
    assert len(keys) == len(set(keys)) == 2
    first.close()
    second.close()
