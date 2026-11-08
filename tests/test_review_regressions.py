import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from robodataops.demo import generate_demo
from robodataops.errors import DataSourceError
from robodataops.export import plan_csv
from robodataops.ingest import load_batch
from robodataops.metrics import context_for, coverage, planning_tasks
from robodataops.models import Target
from robodataops.planning import solve
from robodataops.quality import audit_batch
from robodataops.store import Store


@pytest.mark.parametrize("field", ["length", "data/file_index", "data/chunk_index"])
def test_metadata_is_never_truncated(tmp_path, field):
    generate_demo(tmp_path, injected=False, count=2)
    path = tmp_path / "meta/episodes/chunk-000/file-000.parquet"
    rows = pq.read_table(path).to_pylist()
    rows[0][field] = 0.9
    pq.write_table(pa.Table.from_pylist(rows), path)
    with pytest.raises(DataSourceError):
        load_batch(tmp_path, verify_hashes=False)


@pytest.mark.parametrize("name", ["meta/info.json", "manifest.json"])
def test_json_arrays_produce_domain_errors(tmp_path, name):
    generate_demo(tmp_path, count=2)
    (tmp_path / name).write_text("[]")
    with pytest.raises(DataSourceError):
        load_batch(tmp_path, verify_hashes=False)


def test_aligned_but_out_of_range_indices_are_flagged(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False, count=2))
    ep = batch.episodes[0]
    offset = batch.info["total_frames"]
    ep.metadata["dataset_from_index"] += offset
    ep.metadata["dataset_to_index"] += offset
    for row in ep.rows:
        row["index"] += offset
    assert any(f.rule_id == "I003" for f in audit_batch(batch).findings)


def test_met_targets_allow_zero_priorities_and_csv_contains_contract(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False, count=2))
    audit = audit_batch(batch)
    targets = [Target("0", 1, 100, 10, 0)]
    frame = coverage(batch, audit, {}, targets)
    tasks = planning_tasks(frame)
    assert solve(tasks, 1000).status == "no_gap"
    store = Store()
    plan_id = store.save_plan(solve(tasks, 1000), tasks, context_for(batch, audit, {}, targets))
    text = plan_csv(store.plan(plan_id)).decode("utf-8-sig")
    assert all(
        key in text
        for key in (
            "revision",
            "robot_type",
            "profile_id",
            "rule_config_json",
            "data_contract_json",
        )
    )
