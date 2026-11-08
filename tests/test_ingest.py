import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from robodataops.demo import generate_demo
from robodataops.errors import DataSourceError
from robodataops.ingest import file_sha256, load_batch, safe_path
from robodataops.quality import audit_batch


def test_shared_shard_has_distinct_complete_episodes(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False, count=6))
    assert len({e.source_files for e in batch.episodes}) == 1
    assert len(batch.episodes) == 6
    for episode in batch.episodes:
        assert len(episode.rows) == episode.declared_length
        assert {r["episode_index"] for r in episode.rows} == {episode.episode_index}


def test_paths_cannot_escape_dataset_root(tmp_path):
    with pytest.raises(DataSourceError):
        safe_path(tmp_path, "../../secret.json")


def test_modified_file_fails_integrity_check(tmp_path):
    generate_demo(tmp_path, count=2)
    (tmp_path / "meta/info.json").write_text("{}")
    with pytest.raises(DataSourceError):
        load_batch(tmp_path)


def test_missing_dtype_is_not_silently_accepted(tmp_path):
    generate_demo(tmp_path, injected=False, count=2)
    path = tmp_path / "meta/info.json"
    info = json.loads(path.read_text())
    del info["features"]["action"]["dtype"]
    path.write_text(json.dumps(info))
    with pytest.raises(DataSourceError):
        load_batch(tmp_path, verify_hashes=False)


def test_task_mapping_is_part_of_snapshot_and_run_identity(tmp_path):
    generate_demo(tmp_path, injected=False, count=2)
    before = load_batch(tmp_path)
    path = tmp_path / "meta/tasks.parquet"
    rows = pq.read_table(path).to_pylist()
    rows[0]["task"] = "changed task definition"
    pq.write_table(pa.Table.from_pylist(rows), path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["meta/tasks.parquet"] = file_sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    after = load_batch(tmp_path)
    assert before.snapshot_id != after.snapshot_id
    assert audit_batch(before).run_id != audit_batch(after).run_id
