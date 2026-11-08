"""Validate real study records without manufacturing participant evidence."""

import csv
import io
import math
import statistics

from robodataops.errors import ValidationError


def summarize_study(text: str) -> dict:
    if len(text.encode()) > 128_000:
        raise ValidationError("研究记录超过128KB")
    rows = list(csv.DictReader(io.StringIO(text)))
    pairs = {}
    for row in rows:
        try:
            if (
                not row["participant_id"].strip()
                or not row["task_id"].strip()
                or row["condition"] not in {"baseline", "tool"}
            ):
                raise ValueError("identity/condition")
            seconds = float(row["seconds"])
            errors = int(row["critical_errors"])
            complete = row["completed"]
            if (
                not math.isfinite(seconds)
                or seconds <= 0
                or errors < 0
                or complete not in {"0", "1"}
            ):
                raise ValueError("measurement")
            key = (row["participant_id"], row["task_id"])
            if row["condition"] in pairs.setdefault(key, {}):
                raise ValueError("duplicate condition")
            pairs[key][row["condition"]] = {
                "seconds": seconds,
                "errors": errors,
                "complete": complete == "1",
            }
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(
                "研究记录缺字段、存在重复，或测量值不合法；空模板不能当作实验结果"
            ) from exc
    if not rows:
        raise ValidationError("尚无真实参与者记录")
    matched = [value for value in pairs.values() if {"baseline", "tool"} <= value.keys()]
    return {
        "participants": len({key[0] for key in pairs}),
        "paired_tasks": len(matched),
        "median_seconds_saved": statistics.median(
            [p["baseline"]["seconds"] - p["tool"]["seconds"] for p in matched]
        )
        if matched
        else None,
        "tool_completion": sum(p["tool"]["complete"] for p in matched) / len(matched)
        if matched
        else None,
        "critical_errors_baseline": sum(p["baseline"]["errors"] for p in matched),
        "critical_errors_tool": sum(p["tool"]["errors"] for p in matched),
        "notice": "仅对输入的匿名记录做描述性统计；不自动验证参与者身份，不推断总体显著性",
    }
