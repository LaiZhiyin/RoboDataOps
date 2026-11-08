"""Immutable manifest-scoped cumulative analysis snapshots, without rewriting source rows."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from robodataops.contracts import compatibility_signature
from robodataops.errors import ValidationError
from robodataops.ingest import file_sha256, load_batch, safe_path
from robodataops.models import Batch, canonical_json, digest


def episode_content(episode, batch: Batch | None = None) -> str:
    from robodataops.media import references

    media = []
    if batch is not None:
        media = [
            {
                "camera": ref.camera,
                "source_path": ref.source_path,
                "from": ref.source_start,
                "to": ref.source_end,
                "sha256": file_sha256(ref.path) if ref.path.is_file() else None,
            }
            for ref in references(batch.info, episode.metadata, batch.manifest, batch.root)
        ]
    return digest(
        {
            "task": episode.task_id,
            "length": episode.declared_length,
            "rows": episode.rows,
            "read_error": episode.read_error,
            "metadata": {
                k: v
                for k, v in episode.metadata.items()
                if k not in {"data/chunk_index", "data/file_index", "arrow_schema"}
            },
            "media": media,
        }
    )


def accumulate(batches: list[Batch], destination: str | Path) -> Batch:
    if not batches:
        raise ValidationError("至少需要一个来源快照")
    base = batches[0]
    signature = compatibility_signature(base.info, base.manifest)
    episodes = {}
    for batch in batches:
        if (
            batch.repo_id != base.repo_id
            or batch.source_kind != base.source_kind
            or compatibility_signature(batch.info, batch.manifest) != signature
            or batch.tasks != base.tasks
        ):
            raise ValidationError("累计快照只接受同源、同任务定义和同平台契约")
        for episode in batch.episodes:
            if episode.episode_index in episodes:
                old, old_batch = episodes[episode.episode_index]
                if episode_content(old, old_batch) != episode_content(episode, batch):
                    raise ValidationError(
                        f"同源 EP {episode.episode_index} 内容冲突，需先明确修复/替换决定"
                    )
            else:
                episodes[episode.episode_index] = (episode, batch)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValidationError("派生快照目录已存在；请使用新目录保留历史")
    if any(destination == b.root or destination.is_relative_to(b.root) for b in batches):
        raise ValidationError("累计目录必须独立于原始快照")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".building")
    if temporary.exists():
        raise ValidationError("存在未完成的累计任务，请先检查该临时目录")
    temporary.mkdir()
    try:
        (temporary / "meta/episodes/chunk-000").mkdir(parents=True)
        (temporary / "data/chunk-000").mkdir(parents=True)
        info = copy.deepcopy(base.info)
        info["total_frames"] = max(b.info["total_frames"] for b in batches)
        info["total_episodes"] = max(b.info["total_episodes"] for b in batches)
        info["data_path"] = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
        metadata, lineage, video_evidence = [], [], {}
        for index, (episode, parent) in enumerate(episodes.values()):
            if episode.read_error or not episode.rows:
                raise ValidationError("累计前需先修复无法读取的轨迹，不能静默丢弃")
            meta = {k: v for k, v in episode.metadata.items() if k != "arrow_schema"}
            meta.update({"data/chunk_index": 0, "data/file_index": index})
            metadata.append(meta)
            schema = pq.read_schema(parent.root / episode.source_files[0])
            pq.write_table(
                pa.Table.from_pylist(episode.rows, schema=schema),
                temporary / f"data/chunk-000/file-{index:03d}.parquet",
            )
            lineage.append(
                {
                    "episode_index": episode.episode_index,
                    "parent_snapshot": parent.snapshot_id,
                    "revision": parent.revision,
                    "content_hash": episode_content(episode, parent),
                }
            )
            from robodataops.media import references

            for ref in references(parent.info, episode.metadata, parent.manifest, parent.root):
                key = f"{episode.episode_index}/{ref.camera}"
                if key in parent.manifest.get("video_evidence", {}) or not ref.path.is_file():
                    continue
                target = safe_path(temporary, ref.source_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and file_sha256(target) != file_sha256(ref.path):
                    raise ValidationError(
                        "原始视频同路径内容冲突，请先生成有来源记录的独立证据片段"
                    )
                if not target.exists():
                    shutil.copyfile(ref.path, target)
            for key, evidence in parent.manifest.get("video_evidence", {}).items():
                if key.split("/", 1)[0] == str(episode.episode_index):
                    relative = f"evidence/{digest(key)}.mp4"
                    target = safe_path(temporary, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    origin = safe_path(parent.root, evidence["path"])
                    if file_sha256(origin) != evidence["sha256"]:
                        raise ValidationError("父快照的视频证据校验不一致")
                    shutil.copyfile(origin, target)
                    video_evidence[key] = {**evidence, "path": relative}
        (temporary / "meta/info.json").write_text(canonical_json(info), encoding="utf-8")
        pq.write_table(
            pa.Table.from_pylist(metadata), temporary / "meta/episodes/chunk-000/file-000.parquet"
        )
        pq.write_table(
            pa.Table.from_pylist(
                [{"task_index": int(k), "task": v} for k, v in base.tasks.items()]
            ),
            temporary / "meta/tasks.parquet",
        )
        manifest = {
            "repo_id": base.repo_id,
            "revision": "derived-" + digest(lineage),
            "source_kind": base.source_kind,
            "action_contract": signature["action_contract"],
            "selected_episode_ids": sorted(episodes),
            "parents": sorted({b.snapshot_id for b in batches}),
            "lineage": lineage,
            "video_evidence": video_evidence,
            "cache_notice": "Cumulative analysis snapshot preserving original source IDs/global indices; not a reindexed training split.",
            "files": {
                str(p.relative_to(temporary)): file_sha256(p)
                for p in temporary.rglob("*")
                if p.is_file()
            },
        }
        (temporary / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary)
        raise
    return load_batch(destination)
