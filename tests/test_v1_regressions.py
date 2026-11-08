"""Counterexamples found by the independent V1 review."""

import copy
import json
import shutil
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest

from robodataops.cumulative import accumulate
from robodataops.demo import generate_demo
from robodataops.errors import ValidationError
from robodataops.ingest import load_batch
from robodataops.media import VideoRef, inspect, references
from robodataops.models import PlanningTask, RuleProfile
from robodataops.quality import audit_batch
from robodataops.scenarios import (
    counterfactuals,
    export_scenario,
    import_scenario,
    yield_sensitivity,
)
from robodataops.store import Store


def test_no_mixing_original_and_injected_sources(tmp_path):
    batch = load_batch(generate_demo(tmp_path / "source", count=1, injected=False))
    other = copy.deepcopy(batch)
    other.source_kind = "injected"
    with pytest.raises(ValidationError):
        accumulate([batch, other], tmp_path / "merged")


@pytest.mark.parametrize("rationale", [None, [], 3])
def test_scenario_nontext_rationale_is_a_validation_error(rationale):
    from robodataops.models import Target

    value = json.loads(export_scenario("test", [Target("1", 1, 100, 1)], 100))
    value["targets"][0].update(parameter_source="user_input", rationale=rationale)
    with pytest.raises(ValidationError):
        import_scenario(json.dumps(value), {"1"})


def test_unknown_solver_result_is_not_a_business_conclusion(monkeypatch):
    from robodataops import scenarios
    from robodataops.planning import solve

    tasks = [PlanningTask("A", "A", 2, 100, 1)]
    good = solve(tasks, 100)
    unknown = replace(good, status="no_solution", allocation=None)
    calls = iter([good, unknown, unknown])
    monkeypatch.setattr(scenarios, "solve", lambda *args: next(calls))
    rows = counterfactuals(tasks, 100)
    assert rows and all(r["improvement"] is None for r in rows)
    assert all("不能判断" in r["interpretation"] for r in rows)
    monkeypatch.setattr(scenarios, "solve", lambda *args: unknown)
    result = yield_sensitivity(tasks, 100, costs_are_attempts=True)
    assert all(r["planned_accepted"] is None and r["status"] == "no_solution" for r in result)


def test_ffmpeg_zero_exit_with_decode_errors_never_passes(tmp_path, monkeypatch):
    from robodataops import media

    path = tmp_path / "damaged.mp4"
    path.touch()
    monkeypatch.setattr(media.shutil, "which", lambda name: name)

    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            return SimpleNamespace(returncode=0, stdout=b'{"format":{"duration":"4"}}', stderr=b"")
        assert "-xerror" in command
        return SimpleNamespace(
            returncode=0, stdout=bytes(64 * 64 * 3 * 3), stderr=b"error while decoding MB"
        )

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    ref = VideoRef("cam", path, 0, 4, "source.mp4", 0, 4)
    assert inspect(ref, full_decode=True)["status"] == "decode_error"
    assert inspect(ref, full_decode=False)["status"] == "decode_error"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg system package required")
def test_raw_video_is_preserved_and_changed_evidence_never_inherits_review(tmp_path):
    def source(name, color):
        batch = load_batch(generate_demo(tmp_path / name, count=1, injected=False))
        batch.info["features"]["cam"] = {"dtype": "video", "shape": [64, 64, 3]}
        batch.info["video_path"] = (
            "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
        )
        ep = batch.episodes[0]
        ep.metadata.update(
            {
                "videos/cam/chunk_index": 0,
                "videos/cam/file_index": 0,
                "videos/cam/from_timestamp": 0,
                "videos/cam/to_timestamp": 4,
            }
        )
        path = batch.root / "videos/cam/chunk-000/file-000.mp4"
        path.parent.mkdir(parents=True)
        subprocess.run(
            [
                shutil.which("ffmpeg"),
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=64x64:r=10:d=4",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
        )
        return batch

    old, new = source("old", "gray"), source("new", "silver")
    profile = RuleProfile(video_checks=True)
    store = Store()
    old_audit = audit_batch(old, profile)
    store.record_audit(old, old_audit)
    frozen = next(f for f in old_audit.findings if f.rule_id == "V003")
    store.review(frozen.finding_id, "dismissed", "已查看旧灰色视频")
    with pytest.raises(ValidationError, match="冲突"):
        accumulate([new, old], tmp_path / "conflict")
    merged = accumulate([new], tmp_path / "merged")
    ref = references(merged.info, merged.episodes[0].metadata, merged.manifest, merged.root)[0]
    assert inspect(ref, full_decode=True)["status"] == "decoded"
    assert store.carry_reviews([(old, old_audit)], merged, audit_batch(merged, profile)) == 0
