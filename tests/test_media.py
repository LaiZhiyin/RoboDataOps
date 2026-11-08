import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from robodataops.errors import DataSourceError
from robodataops.ingest import load_batch
from robodataops.media import VideoRef, inspect, references
from robodataops.models import RuleProfile
from robodataops.quality import audit_batch
from robodataops.viewer import viewer_html

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def black_clip(tmp_path):
    executable = shutil.which("ffmpeg")
    if not executable:
        pytest.skip("FFmpeg system package required")
    path = tmp_path / "black.mp4"
    subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=10:d=4",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return VideoRef("camera", path, 0, 4, "original.mp4", 12, 16, 10)


def test_black_and_frozen_are_signals_not_success_claims(black_clip):
    result = inspect(black_clip, full_decode=True)
    assert result["status"] == "decoded"
    assert result["black_signal"] and result["freeze_signal"]
    assert result["physical_sync"] == "not_verified"
    assert inspect(replace(black_clip, end=6))["status"] == "interval_out_of_bounds"


def test_missing_corrupt_and_unavailable_decoder_distinct(tmp_path, monkeypatch):
    ref = VideoRef("camera", tmp_path / "missing.mp4", 0, 4, "source.mp4", 0, 4)
    assert inspect(ref)["status"] == "not_fetched"
    ref.path.write_bytes(b"corrupt")
    if shutil.which("ffmpeg"):
        assert inspect(ref)["status"] == "decode_error"
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert inspect(ref)["status"] == "decoder_unavailable"


def test_public_clip_mapping_and_rendered_frame_payload():
    batch = load_batch(ROOT / "data/public_sample")
    episode = next(ep for ep in batch.episodes if ep.episode_index == 47)
    ref = next(
        r
        for r in references(batch.info, episode.metadata, batch.manifest, batch.root)
        if r.path.exists()
    )
    assert ref.start == 0 and ref.source_start == pytest.approx(295.8)
    html = viewer_html(episode, ref)
    assert "__DATA__" not in html and "__VIDEO__" not in html
    assert '"actions"' in html and "data:video/mp4;base64," in html
    bad = {**batch.manifest, "video_evidence": {**batch.manifest["video_evidence"]}}
    key = f"47/{ref.camera}"
    bad["video_evidence"][key] = {**bad["video_evidence"][key], "source_from_s": 0}
    with pytest.raises(DataSourceError):
        references(batch.info, episode.metadata, bad, batch.root)


def test_required_unfetched_video_never_passes_and_static_video_is_review(tmp_path, black_clip):
    from robodataops.demo import generate_demo

    batch = load_batch(generate_demo(tmp_path / "source", count=1, injected=False))
    batch.info["features"]["camera"] = {"dtype": "video", "shape": [64, 64, 3]}
    batch.info["video_path"] = (
        "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
    )
    episode = batch.episodes[0]
    episode.metadata.update(
        {
            "videos/camera/chunk_index": 0,
            "videos/camera/file_index": 0,
            "videos/camera/from_timestamp": 0,
            "videos/camera/to_timestamp": 3,
        }
    )
    result = audit_batch(batch, RuleProfile(require_video=True))
    assert result.completed[0] is False
    destination = batch.root / "videos/camera/chunk-000/file-000.mp4"
    destination.parent.mkdir(parents=True)
    shutil.copyfile(black_clip.path, destination)
    result = audit_batch(batch, RuleProfile(video_checks=True))
    assert any(f.rule_id == "V003" and not f.automatic_block for f in result.findings)
    assert any(f.rule_id == "V004" for f in result.findings)
