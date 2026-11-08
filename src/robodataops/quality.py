"""Episode-aware checks with evidence; review signals never delete data."""

from __future__ import annotations

import math
import time

import numpy as np

from robodataops.contracts import REQUIRED_FIELDS, validate_info
from robodataops.errors import ValidationError
from robodataops.models import Audit, Batch, Finding, RuleProfile, digest

REQUIRED = REQUIRED_FIELDS
RULES = {
    "D001": "必需字段或值缺失",
    "D002": "向量维度不符合契约",
    "D003": "非有限或非数值数据",
    "D004": "存储 dtype 与声明不一致",
    "I001": "帧索引不连续或重复",
    "I002": "episode 归属不一致",
    "I003": "全局索引或元数据边界不一致",
    "B001": "轨迹长度不一致",
    "T001": "时间戳倒退或重复",
    "T002": "时间间隔需要复核",
    "K001": "任务映射不明确",
    "R001": "轨迹较短，需要复核",
    "R002": "动作变化较低，需要复核",
    "S001": "本地文件不可用或无法解析",
    "V001": "图像验收尚未完成",
    "V002": "视频区间无法解码",
    "V003": "视频黑帧或冻结信号需要复核",
    "V004": "视频区间与轨迹时长不一致",
}


def audit_batch(batch: Batch, profile: RuleProfile | None = None) -> Audit:
    started = time.perf_counter()
    profile = profile or RuleProfile()
    validate_info(batch.info)
    for value in (
        profile.timestamp_tolerance,
        profile.short_episode_seconds,
        profile.low_motion_threshold,
    ):
        if not math.isfinite(value) or value < 0:
            raise ValidationError("规则阈值必须为有限非负数")
    if not math.isfinite(profile.max_gap_factor) or profile.max_gap_factor <= 1:
        raise ValidationError("时间间隔倍数必须大于 1")
    run_id = digest({"snapshot": batch.snapshot_id, "profile": profile})
    findings = []
    media_results = {}
    completed = {}
    fps = float(batch.info["fps"])
    global_seen: dict[int, int] = {}
    for ep in batch.episodes:

        def add(
            rule,
            field,
            observed,
            expected,
            positions=None,
            *,
            review=False,
            episode_index=ep.episode_index,
        ):
            positions = positions or []
            evidence = {
                "run": run_id,
                "ep": episode_index,
                "rule": rule,
                "field": field,
                "observed": observed,
                "positions": positions,
            }
            findings.append(
                Finding(
                    digest(evidence),
                    run_id,
                    episode_index,
                    rule,
                    RULES[rule],
                    field,
                    "review" if review else "blocker",
                    observed,
                    expected,
                    min(positions) if positions else None,
                    max(positions) if positions else None,
                    len(positions) or 1,
                    not review,
                )
            )

        rows = ep.rows
        completed[ep.episode_index] = bool(rows) and ep.read_error is None
        if ep.read_error:
            add("S001", "data_file", ep.read_error, "文件已获取并可解析", review=True)
            continue
        if len(rows) != ep.declared_length or not rows:
            add("B001", "length", len(rows), ep.declared_length)
        missing = {
            key: [i for i, row in enumerate(rows) if key not in row or row[key] is None]
            for key in REQUIRED
        }
        for key, positions in missing.items():
            if positions:
                add("D001", key, {"missing_rows": positions[:12]}, "必需字段均有值", positions)
                completed[ep.episode_index] = False
        if not rows:
            continue
        schema = ep.metadata.get("arrow_schema", {})
        for key in REQUIRED:
            declared = batch.info["features"].get(key, {}).get("dtype")
            actual = schema.get(key)
            expected = {
                "float32": "float",
                "float64": "double",
                "int64": "int64",
                "int32": "int32",
            }.get(declared)
            if actual and expected:
                scalar = (
                    actual.split(":")[-1].strip().split(">")[0].strip() if ":" in actual else actual
                )
                if scalar != expected:
                    add("D004", key, actual, declared)
        for key in ("observation.state", "action"):
            shape = batch.info["features"][key]["shape"]
            bad_shape, bad_numeric = [], []
            for i, row in enumerate(rows):
                value = row.get(key)
                if value is None:
                    continue
                try:
                    arr = np.asarray(value)
                    if list(arr.shape) != shape:
                        bad_shape.append(i)
                    if arr.dtype.kind not in "fiu" or not np.all(np.isfinite(arr)):
                        bad_numeric.append(i)
                except (TypeError, ValueError):
                    bad_numeric.append(i)
            if bad_shape:
                add(
                    "D002",
                    key,
                    {"examples": [rows[i][key] for i in bad_shape[:3]]},
                    shape,
                    bad_shape,
                )
            if bad_numeric:
                add(
                    "D003",
                    key,
                    {"examples": [rows[i][key] for i in bad_numeric[:3]]},
                    "有限数值",
                    bad_numeric,
                )
        frames = [row.get("frame_index") for row in rows]
        if frames != list(range(len(rows))):
            positions = [i for i, value in enumerate(frames) if value != i]
            add("I001", "frame_index", {"examples": frames[:12]}, "从 0 连续递增且唯一", positions)
        wrong = [i for i, row in enumerate(rows) if row.get("episode_index") != ep.episode_index]
        if wrong:
            add("I002", "episode_index", "帧归属与 episode 元数据不同", ep.episode_index, wrong)
        start = ep.metadata.get("dataset_from_index")
        end = ep.metadata.get("dataset_to_index")
        indices = [row.get("index") for row in rows]
        wrong_global = []
        if isinstance(start, int) and isinstance(end, int):
            wrong_global = [i for i, value in enumerate(indices) if value != start + i]
            if end - start != len(rows):
                wrong_global = sorted(set(wrong_global + [0]))
            if start < 0 or end < start or end > batch.info["total_frames"]:
                wrong_global = sorted(set(wrong_global + [0]))
        else:
            completed[ep.episode_index] = False
            add("D001", "dataset_from/to_index", {"from": start, "to": end}, "必需的全局边界")
        for i, value in enumerate(indices):
            if isinstance(value, int):
                if value in global_seen and global_seen[value] != ep.episode_index:
                    wrong_global.append(i)
                global_seen[value] = ep.episode_index
        if wrong_global:
            add(
                "I003",
                "index",
                {"from": start, "to": end, "first": indices[:8]},
                "全局索引与 metadata 范围一致且不跨轨迹重复",
                sorted(set(wrong_global)),
            )
        task_ids = {str(row.get("task_index")) for row in rows}
        task_names = ep.metadata.get("tasks", [])
        if (
            ep.task_id not in batch.tasks
            or task_ids != {ep.task_id}
            or (task_names and batch.tasks.get(ep.task_id) not in task_names)
        ):
            add(
                "K001",
                "task_index",
                {"ids": sorted(task_ids), "metadata_tasks": task_names},
                "唯一且存在于任务映射，符合 episode 声明",
            )
        timestamps = [row.get("timestamp") for row in rows]
        valid_times = all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in timestamps
        )
        if not valid_times:
            positions = [
                i
                for i, v in enumerate(timestamps)
                if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
            ]
            add(
                "D003",
                "timestamp",
                {"examples": [timestamps[i] for i in positions[:3]]},
                "有限秒数",
                positions,
            )
        elif len(timestamps) > 1:
            delta = np.diff(timestamps)
            wrong_time = np.flatnonzero(delta <= 0).tolist()
            if wrong_time:
                add(
                    "T001",
                    "timestamp",
                    {"intervals": [float(delta[i]) for i in wrong_time[:12]]},
                    "episode 内严格递增",
                    [i + 1 for i in wrong_time],
                )
            gaps = np.flatnonzero(
                delta > profile.max_gap_factor / fps + profile.timestamp_tolerance
            ).tolist()
            if gaps:
                add(
                    "T002",
                    "timestamp",
                    {"max_gap_s": float(delta.max())},
                    {"max_gap_s": profile.max_gap_factor / fps},
                    [i + 1 for i in gaps],
                    review=True,
                )
        if profile.review_signals:
            if len(rows) / fps < profile.short_episode_seconds:
                add(
                    "R001",
                    "duration",
                    len(rows) / fps,
                    {"review_below_s": profile.short_episode_seconds},
                    review=True,
                )
            try:
                actions = np.asarray([row.get("action") for row in rows], dtype=float)
                if len(rows) > 1 and actions.ndim == 2 and np.all(np.isfinite(actions)):
                    movement = float(np.max(np.ptp(actions, axis=0)))
                    if movement <= profile.low_motion_threshold:
                        add(
                            "R002",
                            "action",
                            {"max_range": movement},
                            {"review_below": profile.low_motion_threshold},
                            review=True,
                        )
            except (TypeError, ValueError):
                pass  # Shape/null defects already have explicit evidence above.
        if profile.video_checks or profile.require_video:
            from robodataops.media import inspect, references

            refs = references(batch.info, ep.metadata, batch.manifest, batch.root)
            results = [inspect(ref, full_decode=profile.require_video) for ref in refs]
            media_results[ep.episode_index] = results
            for ref in refs:
                expected_duration = len(rows) / fps
                if abs((ref.end - ref.start) - expected_duration) > 2 / fps:
                    add(
                        "V004",
                        ref.camera,
                        {"interval_s": ref.end - ref.start},
                        {"trajectory_s": expected_duration, "tolerance_s": 2 / fps},
                        review=True,
                    )
            if profile.require_video and (
                not results or any(r["status"] != "decoded" for r in results)
            ):
                completed[ep.episode_index] = False
                add(
                    "V001",
                    "video",
                    results or "未声明相机",
                    "所有必需相机在声明区间完整解码；不代表物理同步",
                    review=True,
                )
            for result in results:
                if result["status"] in {"decode_error", "interval_out_of_bounds", "timeout"}:
                    add(
                        "V002",
                        result["camera"],
                        result,
                        "指定区间可解码",
                        review=not profile.require_video,
                    )
                if result["status"] == "decoded" and (
                    result["black_signal"] or result["freeze_signal"]
                ):
                    add(
                        "V003",
                        result["camera"],
                        result,
                        "抽查信号需结合任务判断，不自动排除静止示范",
                        review=True,
                    )
    return Audit(
        run_id,
        batch.snapshot_id,
        profile,
        findings,
        completed,
        time.perf_counter() - started,
        media_results,
    )
