"""Explicit network preparation of five attributed video clips and a second data source."""

import json
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

from robodataops.fetch import LIBERO_REPO, LIBERO_REVISION, bundle_analysis_cache
from robodataops.ingest import data_relative_path, file_sha256, load_batch, read_metadata
from robodataops.media import extract_clip, references
from robodataops.models import canonical_json

root = Path(__file__).resolve().parents[1]
raw = root / "data/raw/libero"
cached = root / "data/public_sample"
manifest = json.loads((cached / "manifest.json").read_text())
info, tasks, metadata = read_metadata(raw)
ids = manifest["selected_episode_ids"][:5]
entries = manifest.get("video_evidence", {})
for meta in metadata:
    if meta["episode_index"] not in ids:
        continue
    ref = references(info, meta, {}, raw)[0]
    hf_hub_download(
        LIBERO_REPO, ref.source_path, repo_type="dataset", revision=LIBERO_REVISION, local_dir=raw
    )
    relative = f"evidence/episode-{meta['episode_index']:04d}.mp4"
    entry = extract_clip(ref, cached / relative)
    entries[f"{meta['episode_index']}/{ref.camera}"] = {**entry, "path": relative}
    print("Prepared public clip", meta["episode_index"], flush=True)
manifest["video_evidence"] = entries
manifest["video_status"] = (
    "five_attributed_episode_clips; other episodes and second camera not fetched"
)
(cached / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")

aloha_repo = "lerobot/aloha_sim_insertion_human"
aloha_revision = "cc571a3c661df81b566dbfde3d5c1e85fcdf7884"
aloha_root = root / "data/raw/aloha"
snapshot_download(
    aloha_repo,
    repo_type="dataset",
    revision=aloha_revision,
    allow_patterns=["meta/**"],
    local_dir=aloha_root,
)
info, _, metadata = read_metadata(aloha_root)
selected = sorted(metadata, key=lambda m: m["episode_index"])[:5]
paths = sorted({data_relative_path(info, m) for m in selected})
for relative in paths:
    hf_hub_download(
        aloha_repo, relative, repo_type="dataset", revision=aloha_revision, local_dir=aloha_root
    )
tracked = [p for p in (aloha_root / "meta").rglob("*") if p.is_file()] + [
    aloha_root / p for p in paths
]
manifest = {
    "repo_id": aloha_repo,
    "revision": aloha_revision,
    "source_kind": "public",
    "selected_episode_ids": [m["episode_index"] for m in selected],
    "files": {str(p.relative_to(aloha_root)): file_sha256(p) for p in tracked},
    "license": "apache-2.0 as declared by dataset card",
    "video_status": "not_fetched",
    "sampling": "first five complete episodes; compatibility check, not representative study",
}
(aloha_root / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
destination = root / "data/aloha_sample"
bundle_analysis_cache(aloha_root, destination)
print("Prepared ALOHA episodes", len(load_batch(destination).episodes))
