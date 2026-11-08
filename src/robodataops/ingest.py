"""Read the pinned LeRobot v3 Parquet layout without loading training libraries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from robodataops.contracts import action_contract, validate_info
from robodataops.errors import DataSourceError
from robodataops.models import Batch, Episode, digest


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise DataSourceError("数据路径超出所选数据集目录")
    return path


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("必须是 JSON 对象")
        return value
    except (OSError, ValueError) as exc:
        raise DataSourceError(f"无法读取 {path.name}：{exc}") from exc


def read_metadata(root: Path) -> tuple[dict, dict[str, str], list[dict]]:
    info = _json(safe_path(root, "meta/info.json"))
    validate_info(info)
    tasks: dict[str, str] = {}
    task_parquet = safe_path(root, "meta/tasks.parquet")
    try:
        if task_parquet.exists():
            for row in pq.read_table(task_parquet).to_pylist():
                name = row.get("task", row.get("__index_level_0__"))
                index = row.get("task_index")
                if index is not None and name is not None:
                    tasks[str(index)] = str(name)
        else:
            jsonl = safe_path(root, "meta/tasks.jsonl")
            if jsonl.exists():
                for line in jsonl.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        tasks[str(row["task_index"])] = str(row["task"])
        meta_dir = safe_path(root, "meta/episodes")
        paths = sorted(meta_dir.rglob("*.parquet"))
        episodes = [
            row
            for path in paths
            for row in pq.read_table(safe_path(root, str(path.relative_to(root)))).to_pylist()
        ]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DataSourceError(f"无法读取任务或 episode 元数据：{exc}") from exc
    ids = [row.get("episode_index") for row in episodes]
    if not episodes or any(not isinstance(i, int) for i in ids) or len(set(ids)) != len(ids):
        raise DataSourceError("episode 元数据为空，或 episode_index 非法／重复")
    for row in episodes:
        for key in (
            "episode_index",
            "length",
            "data/chunk_index",
            "data/file_index",
            "dataset_from_index",
            "dataset_to_index",
        ):
            if type(row.get(key)) is not int or row[key] < 0:
                raise DataSourceError(f"episode 元数据 {key} 必须是非负整数")
        if row["episode_index"] >= info["total_episodes"]:
            raise DataSourceError("episode_index 超出来源声明范围")
    return info, tasks, episodes


def data_relative_path(info: dict, metadata: dict) -> str:
    try:
        for key in ("data/chunk_index", "data/file_index"):
            if type(metadata[key]) is not int or metadata[key] < 0:
                raise ValueError("文件映射必须是非负整数")
        return info["data_path"].format(
            chunk_index=metadata["data/chunk_index"],
            file_index=metadata["data/file_index"],
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise DataSourceError("不支持的 episode 数据文件映射") from exc


def load_batch(
    root: str | Path, episode_ids: list[int] | None = None, *, verify_hashes: bool = True
) -> Batch:
    root = Path(root).resolve()
    info, tasks, metadata = read_metadata(root)
    manifest_path = safe_path(root, "manifest.json")
    manifest = _json(manifest_path) if manifest_path.exists() else {}
    action_contract(manifest)
    if not isinstance(manifest.get("files", {}), dict):
        raise DataSourceError("manifest.files 必须是路径到 SHA256 的对象")
    for key in ("repo_id", "revision", "source_kind"):
        if key in manifest and not isinstance(manifest[key], str):
            raise DataSourceError(f"manifest.{key} 必须是字符串")
    selected_ids = episode_ids if episode_ids is not None else manifest.get("selected_episode_ids")
    if selected_ids is not None:
        if not isinstance(selected_ids, list) or any(
            type(i) is not int or i < 0 for i in selected_ids
        ):
            raise DataSourceError("抽样 episode ID 必须是非负整数列表")
        if len(set(selected_ids)) != len(selected_ids):
            raise DataSourceError("抽样 episode ID 重复")
        wanted = set(selected_ids)
        metadata = [row for row in metadata if row["episode_index"] in wanted]
        if {row["episode_index"] for row in metadata} != wanted:
            raise DataSourceError("部分抽样 episode 不存在于元数据")
    if not metadata:
        raise DataSourceError("未选择任何 episode")
    if verify_hashes:
        for relative, expected in manifest.get("files", {}).items():
            path = safe_path(root, relative)
            if path.exists() and file_sha256(path) != expected:
                raise DataSourceError(f"文件校验失败：{relative}。请重新获取或生成派生样本")
    tables: dict[str, dict[int, list[dict[str, Any]]]] = {}
    errors: dict[str, str] = {}
    schemas: dict[str, dict[str, str]] = {}
    episodes = []
    for meta in sorted(metadata, key=lambda item: item["episode_index"]):
        relative = data_relative_path(info, meta)
        if relative not in tables and relative not in errors:
            path = safe_path(root, relative)
            if not path.exists():
                errors[relative] = "文件尚未获取或本地缺失，不能判断源数据是否损坏"
            else:
                try:
                    table = pq.read_table(path)
                    schemas[relative] = {field.name: str(field.type) for field in table.schema}
                    groups: dict[int, list[dict]] = {}
                    for row in table.to_pylist():
                        groups.setdefault(row.get("episode_index"), []).append(row)
                    tables[relative] = groups
                except (OSError, ValueError) as exc:
                    errors[relative] = f"无法解析数据文件：{exc}"
        rows = tables.get(relative, {}).get(meta["episode_index"], [])
        source_tasks = {str(row["task_index"]) for row in rows if row.get("task_index") is not None}
        task_id = next(iter(source_tasks)) if len(source_tasks) == 1 else None
        if task_id is None:
            names = meta.get("tasks", [])
            matches = [key for key, name in tasks.items() if name in names]
            task_id = matches[0] if len(matches) == 1 else None
        detail = dict(meta)
        detail["arrow_schema"] = schemas.get(relative, {})
        episodes.append(
            Episode(
                meta["episode_index"],
                task_id,
                meta["length"],
                rows,
                detail,
                (relative,),
                errors.get(relative),
            )
        )
    repo_id = manifest.get("repo_id", "local/unverified")
    revision = manifest.get("revision", "unversioned-local")
    source_kind = manifest.get("source_kind", "local")
    from robodataops.media import references

    media_hashes = {}
    for episode in episodes:
        for ref in references(info, episode.metadata, manifest, root):
            relative = str(ref.path.relative_to(root))
            if relative not in media_hashes:
                media_hashes[relative] = file_sha256(ref.path) if ref.path.exists() else None
    fingerprint = {
        "repo": repo_id,
        "revision": revision,
        "kind": source_kind,
        "info": info,
        "tasks": tasks,
        "action_contract": action_contract(manifest),
        "media_files": media_hashes,
        "episodes": [(e.episode_index, e.metadata, e.rows, e.read_error) for e in episodes],
    }
    snapshot_id = digest(fingerprint)
    return Batch(repo_id, revision, source_kind, snapshot_id, info, tasks, episodes, manifest, root)
