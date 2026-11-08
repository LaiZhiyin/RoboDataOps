import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from robodataops.cli import main
from robodataops.demo import generate_demo
from robodataops.errors import ValidationError
from robodataops.fetch import fetch_libero
from robodataops.ingest import load_batch


def test_cli_audit_plan_and_clear_input_errors(tmp_path, capsys):
    source = str(tmp_path / "source")
    assert main(["demo", "--output", source]) == 0
    report = str(tmp_path / "audit.json")
    database = str(tmp_path / "audit.duckdb")
    assert main(["audit", "--source", source, "--output", report, "--db", database]) == 0
    assert len(json.loads(Path(report).read_text())["states"]) == 100
    output, csv = str(tmp_path / "plan.json"), str(tmp_path / "plan.csv")
    assert (
        main(
            [
                "plan",
                "--source",
                source,
                "--db",
                database,
                "--budget",
                "100",
                "--output",
                output,
                "--csv",
                csv,
            ]
        )
        == 0
    )
    assert json.loads(Path(output).read_text())["plan"]["spent_cents"] <= 10000
    assert main(["plan", "--source", source, "--db", database, "--budget", "-1"]) == 2
    bad_config = tmp_path / "bad.json"
    bad_config.write_text("[]")
    assert main(["audit", "--config", str(bad_config)]) == 2
    assert "错误" in capsys.readouterr().err


@pytest.mark.parametrize("metadata_has_tasks", [True, False])
def test_public_fetch_recovers_tasks_from_actual_rows_when_needed(
    tmp_path, monkeypatch, metadata_has_tasks
):
    source = generate_demo(tmp_path / "fixture", injected=False)
    if not metadata_has_tasks:
        path = source / "meta/episodes/chunk-000/file-000.parquet"
        rows = pq.read_table(path).to_pylist()
        for row in rows:
            del row["tasks"]
        pq.write_table(pa.Table.from_pylist(rows), path)
    calls = []

    def fake_snapshot(*args, **kwargs):
        calls.extend(kwargs["allow_patterns"])
        for pattern in kwargs["allow_patterns"]:
            directory = pattern.split("/")[0]
            shutil.copytree(
                source / directory, Path(kwargs["local_dir"]) / directory, dirs_exist_ok=True
            )

    def fake_file(repo, relative, **kwargs):
        target = Path(kwargs["local_dir"]) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        return str(target)

    monkeypatch.setattr("robodataops.fetch.snapshot_download", fake_snapshot)
    monkeypatch.setattr("robodataops.fetch.hf_hub_download", fake_file)
    batch = load_batch(fetch_libero(tmp_path / "download", task_count=2, per_task=2))
    assert len(batch.episodes) == 4
    assert len({ep.task_id for ep in batch.episodes}) == 2
    assert "videos/**" not in calls
    assert ("data/**" in calls) != metadata_has_tasks


def test_fetch_rejects_invalid_sample_size(tmp_path):
    with pytest.raises(ValidationError):
        fetch_libero(tmp_path, task_count=0)
