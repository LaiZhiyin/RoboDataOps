"""The supported v3 tabular contract; absent declarations never mean a pass."""

import math

from robodataops.errors import DataSourceError

REQUIRED_FIELDS = (
    "episode_index",
    "frame_index",
    "index",
    "task_index",
    "timestamp",
    "observation.state",
    "action",
)
NUMERIC_DTYPES = {"float32", "float64", "int32", "int64"}


def action_contract(manifest: dict) -> dict:
    value = manifest.get("action_contract", {})
    if not isinstance(value, dict):
        raise DataSourceError("action_contract 必须是对象")
    allowed = {
        "unit": {"unknown", "radian", "degree", "meter", "normalized", "mixed"},
        "control_mode": {
            "unknown",
            "absolute_position",
            "delta_position",
            "velocity",
            "torque",
            "mixed",
        },
    }
    result = {
        "unit": "unknown",
        "control_mode": "unknown",
        "coordinate_frame": "unknown",
        "evidence": "not provided",
    }
    if set(value) - set(result):
        raise DataSourceError("动作契约包含不支持的字段")
    result.update(value)
    for key, choices in allowed.items():
        if not isinstance(result[key], str) or result[key] not in choices:
            raise DataSourceError(f"动作契约 {key} 不在支持范围")
    for key in ("coordinate_frame", "evidence"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise DataSourceError(f"动作契约 {key} 必须有明确声明")
    if any(result[key] != "unknown" for key in allowed) and result["evidence"] == "not provided":
        raise DataSourceError("已知动作单位或控制模式需要提供依据")
    return result


def compatibility_signature(info: dict, manifest: dict) -> dict:
    return {
        "robot_type": info.get("robot_type", "unknown"),
        "fps": info["fps"],
        "features": {
            key: {name: info["features"][key][name] for name in ("dtype", "shape")}
            for key in REQUIRED_FIELDS
        },
        "action_contract": action_contract(manifest),
        "video_path": info.get("video_path"),
        "cameras": {
            k: v
            for k, v in info["features"].items()
            if isinstance(v, dict) and v.get("dtype") == "video"
        },
    }


def validate_info(info: dict) -> None:
    if not isinstance(info, dict):
        raise DataSourceError("info.json 必须是 JSON 对象")
    if info.get("codebase_version") != "v3.0":
        raise DataSourceError("当前适配器仅支持 LeRobot v3.0 Parquet 布局")
    try:
        fps = info["fps"]
        if (
            isinstance(fps, bool)
            or not isinstance(fps, (int, float))
            or not math.isfinite(fps)
            or not 0 < fps < 100000
        ):
            raise ValueError("invalid fps")
        for key in ("total_frames", "total_episodes", "total_tasks"):
            if type(info[key]) is not int or info[key] < 0:
                raise ValueError(f"invalid count: {key}")
        for key in REQUIRED_FIELDS:
            feature = info["features"][key]
            if feature["dtype"] not in NUMERIC_DTYPES:
                raise ValueError(f"unsupported dtype: {key}")
            shape = feature["shape"]
            if (
                not isinstance(shape, list)
                or len(shape) != 1
                or type(shape[0]) is not int
                or shape[0] <= 0
            ):
                raise ValueError(f"unsupported shape: {key}")
            if key not in {"observation.state", "action"} and shape != [1]:
                raise ValueError(f"expected scalar feature: {key}")
            if key in {"episode_index", "frame_index", "index", "task_index"} and feature[
                "dtype"
            ] not in {"int32", "int64"}:
                raise ValueError(f"expected integer index: {key}")
    except (KeyError, TypeError, ValueError) as exc:
        raise DataSourceError("缺少有效 FPS 或必需字段的数值 dtype/shape 声明") from exc
