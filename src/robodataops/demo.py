"""Deterministic synthetic fixtures, always labelled separately from public data."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from robodataops.ingest import file_sha256
from robodataops.models import Target, canonical_json

TASKS = {
    "0": "抓取方块并放入托盘",
    "1": "打开抽屉并放入物体",
    "2": "将杯子移至指定区域",
    "3": "按空间关系排列物体",
    "4": "完成多步骤收纳任务",
}


def default_targets(task_ids: list[str] | None = None) -> list[Target]:
    ids = task_ids if task_ids is not None else list(TASKS)
    costs = [1200, 1500, 1800, 2100, 1600]
    return [
        Target(key, 40 if i == 0 else 30, costs[i % 5], 20, [1, 1.5, 2, 2.5, 1.5][i % 5])
        for i, key in enumerate(ids)
    ]


def generate_demo(root: str | Path, *, injected: bool = True, count: int = 100) -> Path:
    root = Path(root)
    (root / "meta/episodes/chunk-000").mkdir(parents=True, exist_ok=True)
    (root / "data/chunk-000").mkdir(parents=True, exist_ok=True)
    info = {
        "codebase_version": "v3.0",
        "robot_type": "synthetic-panda-like",
        "total_episodes": count,
        "total_tasks": 5,
        "fps": 10.0,
        "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
        "features": {
            "observation.state": {"dtype": "float32", "shape": [8]},
            "action": {"dtype": "float32", "shape": [7]},
            **{
                key: {"dtype": dtype, "shape": [1]}
                for key, dtype in [
                    ("timestamp", "float32"),
                    ("frame_index", "int64"),
                    ("episode_index", "int64"),
                    ("index", "int64"),
                    ("task_index", "int64"),
                ]
            },
        },
    }
    all_rows, metadata, mutations = [], [], []
    cursor = 0
    for episode_index in range(count):
        task_index = min(
            4,
            next(
                (j for j, edge in enumerate([30, 55, 75, 90, 100]) if episode_index % 100 < edge), 4
            ),
        )
        length = 40 + episode_index % 21
        if injected and episode_index == 96:
            length = 3
        rows = []
        for frame in range(length):
            phase = frame / 7 + episode_index / 11
            rows.append(
                {
                    "episode_index": episode_index,
                    "frame_index": frame,
                    "index": cursor + frame,
                    "task_index": task_index,
                    "timestamp": frame / 10,
                    "observation.state": [math.sin(phase + j / 5) for j in range(8)],
                    "action": [0.1 * math.sin(phase + j / 4) for j in range(7)],
                }
            )
        meta = {
            "episode_index": episode_index,
            "length": length,
            "tasks": [TASKS[str(task_index)]],
            "data/chunk_index": 0,
            "data/file_index": episode_index // 50,
            "dataset_from_index": cursor,
            "dataset_to_index": cursor + length,
        }
        mutation = None
        if injected:
            if episode_index == 1:
                rows[10]["timestamp"] = rows[9]["timestamp"] - 0.1
                mutation = "timestamp_backwards"
            elif episode_index == 7:
                rows[8]["action"][2] = float("nan")
                mutation = "nonfinite_action"
            elif episode_index == 13:
                rows[9]["action"] = [0.1] * 6
                mutation = "action_shape"
            elif episode_index == 25:
                rows[9]["frame_index"] = 8
                mutation = "duplicate_frame"
            elif episode_index == 34:
                meta["length"] += 2
                mutation = "declared_length"
            elif episode_index == 49:
                rows[10]["index"] = rows[9]["index"]
                mutation = "global_index"
            elif episode_index == 58:
                for row in rows[10:]:
                    row["timestamp"] += 0.4
                mutation = "time_gap_review"
            elif episode_index == 64:
                for row in rows:
                    row["action"] = [0.0] * 7
                mutation = "low_motion_review"
            elif episode_index == 72:
                for row in rows:
                    row["task_index"] = 999
                mutation = "unknown_task"
            elif episode_index == 83:
                rows[5]["action"] = None
                mutation = "missing_value"
            elif episode_index == 90:
                meta["dataset_from_index"] += 5
                mutation = "boundary_mismatch"
            elif episode_index == 96:
                mutation = "short_episode_review"
            elif episode_index == 97:
                meta["data/file_index"] = 999
                mutation = "unavailable_local_shard"
        if mutation:
            mutations.append(
                {"episode_index": episode_index, "type": mutation, "source": "synthetic_injection"}
            )
        metadata.append(meta)
        all_rows.extend(rows)
        cursor += length
    info["total_frames"] = cursor
    (root / "meta/info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    pq.write_table(
        pa.Table.from_pylist(
            [{"task_index": int(key), "task": value} for key, value in TASKS.items()]
        ),
        root / "meta/tasks.parquet",
    )
    pq.write_table(
        pa.Table.from_pylist(metadata), root / "meta/episodes/chunk-000/file-000.parquet"
    )
    schema = pa.schema(
        [
            ("episode_index", pa.int64()),
            ("frame_index", pa.int64()),
            ("index", pa.int64()),
            ("task_index", pa.int64()),
            ("timestamp", pa.float32()),
            ("observation.state", pa.list_(pa.float32())),
            ("action", pa.list_(pa.float32())),
        ]
    )
    for shard in sorted({row["episode_index"] // 50 for row in all_rows}):
        rows = [row for row in all_rows if row["episode_index"] // 50 == shard]
        pq.write_table(
            pa.Table.from_pylist(rows, schema=schema),
            root / f"data/chunk-000/file-{shard:03d}.parquet",
        )
    files = {
        str(path.relative_to(root)): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "repo_id": "robodataops/synthetic-demo",
        "revision": "synthetic-v1-seed42",
        "source_kind": "injected" if injected else "synthetic",
        "seed": 42,
        "description": "自建合成轨迹；业务参数为模拟，不含真实采集或策略效果",
        "selected_episode_ids": list(range(count)),
        "files": files,
        "mutations": mutations,
        "license": "MIT (project-generated synthetic fixtures)",
    }
    (root / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    return root
