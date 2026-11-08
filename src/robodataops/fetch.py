"""Obtain a reproducible tabular subset of the explicitly supported public source."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from random import Random

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, snapshot_download

from robodataops.errors import ValidationError
from robodataops.ingest import data_relative_path, file_sha256, read_metadata, safe_path
from robodataops.models import canonical_json

LIBERO_REPO = "lerobot/libero"
LIBERO_REVISION = "a1aaacb7f6cd6ee5fb43120f673cebb0cfea7dd4"


def fetch_libero(
    root: str | Path, *, task_count: int = 5, per_task: int = 20, seed: int = 42
) -> Path:
    if not 1 <= task_count <= 40 or not 1 <= per_task <= 50:
        raise ValidationError("任务数需为 1–40，每任务样本数需为 1–50")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        LIBERO_REPO,
        repo_type="dataset",
        revision=LIBERO_REVISION,
        allow_patterns=["meta/**"],
        local_dir=root,
        max_workers=4,
    )
    info, tasks, metadata = read_metadata(root)
    groups = defaultdict(list)
    if all(len(row.get("tasks", [])) == 1 for row in metadata):
        for row in metadata:
            groups[row["tasks"][0]].append(row)
    else:
        # This pinned conversion has no task column in episode metadata.
        # Read actual tabular task_index values; never infer task from file order.
        snapshot_download(
            LIBERO_REPO,
            repo_type="dataset",
            revision=LIBERO_REVISION,
            allow_patterns=["data/**"],
            local_dir=root,
            max_workers=8,
        )
        mapping = {}
        for relative in sorted({data_relative_path(info, row) for row in metadata}):
            table = pq.read_table(
                safe_path(root, relative), columns=["episode_index", "task_index"]
            )
            for item in table.to_pylist():
                mapping.setdefault(item["episode_index"], set()).add(str(item["task_index"]))
        for row in metadata:
            ids = mapping.get(row["episode_index"], set())
            if len(ids) == 1 and next(iter(ids)) in tasks:
                groups[tasks[next(iter(ids))]].append(row)
    candidates = [name for name in sorted(groups) if len(groups[name]) >= per_task]
    if len(candidates) < task_count:
        raise ValidationError("没有足够任务满足指定抽样数量，请减少样本量")
    rng = Random(seed)
    names = sorted(rng.sample(candidates, task_count))
    selected = [
        row
        for name in names
        for row in rng.sample(sorted(groups[name], key=lambda r: r["episode_index"]), per_task)
    ]
    paths = sorted({data_relative_path(info, row) for row in selected})
    for relative in paths:
        safe_path(root, relative)
        hf_hub_download(
            LIBERO_REPO, relative, repo_type="dataset", revision=LIBERO_REVISION, local_dir=root
        )
    tracked = (
        sorted(root.glob("meta/**/*.parquet"))
        + sorted(root.glob("meta/*.json"))
        + sorted(root.glob("meta/*.jsonl"))
        + [safe_path(root, rel) for rel in paths]
    )
    manifest = {
        "repo_id": LIBERO_REPO,
        "revision": LIBERO_REVISION,
        "source_kind": "public",
        "license": "apache-2.0 (as declared by dataset card)",
        "license_url": f"https://huggingface.co/datasets/{LIBERO_REPO}",
        "selected_episode_ids": sorted(row["episode_index"] for row in selected),
        "sampling": {
            "seed": seed,
            "task_count": task_count,
            "per_task": per_task,
            "task_names": names,
        },
        "files": {str(path.relative_to(root)): file_sha256(path) for path in tracked},
        "video_status": "not_downloaded_not_checked",
        "schema_version": info["codebase_version"],
        "notice": "公开仿真示教子集。未获取视频；成本、产能和数量目标需另行提供。",
    }
    (root / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    return root


def bundle_analysis_cache(source: str | Path, destination: str | Path) -> Path:
    """Copy manifest-selected shards unchanged; this is not a training split."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.is_relative_to(source):
        raise ValidationError("演示缓存需使用独立目录")
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    for relative in manifest["files"]:
        origin, target = safe_path(source, relative), safe_path(destination, relative)
        if file_sha256(origin) != manifest["files"][relative]:
            raise ValidationError("来源文件校验不一致，不能打包")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    manifest["cache_notice"] = (
        "Manifest-scoped analysis cache with original metadata/shards; not a standalone LeRobot training split."
    )
    (destination / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    return destination
