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
