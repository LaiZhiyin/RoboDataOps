"""Portable scenario contracts and explicitly hypothetical sensitivity analyses."""

import json
import math
from dataclasses import asdict, replace

from robodataops.errors import ValidationError
from robodataops.models import Target, canonical_json
from robodataops.planning import solve, validate_task_fields


def export_scenario(name: str, targets: list[Target], budget_cents: int) -> str:
    from robodataops.models import PlanningTask

    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise ValidationError("情景名称需为1–100字符")
    validate_task_fields(
        [
            PlanningTask(t.task_id, t.task_id, t.target, t.cost_cents, t.capacity, t.weight)
            for t in targets
        ],
        budget_cents,
    )
    if not targets or len(targets) > 100:
        raise ValidationError("情景应包含1–100个任务")
    for target in targets:
        if not isinstance(target.parameter_source, str) or target.parameter_source not in {
            "simulated",
            "user_input",
            "historical_estimate",
        }:
            raise ValidationError("情景参数来源不合法")
        if not isinstance(target.rationale, str):
            raise ValidationError("参数依据必须是文本")
        if target.parameter_source != "simulated" and not target.rationale.strip():
            raise ValidationError("非模拟参数需填写依据")
    return canonical_json(
        {
            "format_version": 1,
            "name": name.strip(),
            "budget_cents": budget_cents,
            "targets": [asdict(t) for t in targets],
        }
    )


def import_scenario(text: str, task_ids: set[str]) -> dict:
    if len(text.encode("utf-8")) > 128_000:
        raise ValidationError("情景文件超过128KB")
    try:
        value = json.loads(text)
        if (
            not isinstance(value, dict)
            or value["format_version"] != 1
            or not isinstance(value["targets"], list)
        ):
            raise ValueError("format")
        targets = [Target(**row) for row in value["targets"]]
        if {t.task_id for t in targets} - task_ids:
            raise ValueError("unknown tasks")
        return json.loads(export_scenario(value["name"], targets, value["budget_cents"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("情景格式不正确，或任务不属于当前数据集") from exc


def counterfactuals(tasks, budget_cents):
    baseline = solve(tasks, budget_cents)
    if baseline.status not in {"optimal", "no_gap"}:
        return []
    changes = [("预算增加25%", tasks, budget_cents + max(1, budget_cents // 4))]
    for task in tasks:
        if task.capacity < task.demand:
            changed = [
                replace(t, capacity=min(t.demand, t.capacity + 5))
                if t.task_id == task.task_id
                else t
                for t in tasks
            ]
            changes.append((f"任务 {task.task_id} 产能增加5条", changed, budget_cents))
    result = []
    for name, altered, budget in changes:
        plan = solve(altered, budget)
        proven = plan.status in {"optimal", "no_gap"}
        improvement = baseline.residual_loss - plan.residual_loss if proven else None
        result.append(
            {
                "change": name,
                "loss_before": baseline.residual_loss,
                "loss_after": plan.residual_loss if plan.allocation is not None else None,
                "improvement": improvement,
                "status": plan.status,
                "interpretation": (
                    "给定数量目标改善" if improvement > 1e-8 else "单独放宽后目标未改善"
                )
                if proven
                else "求解未证最优，不能判断瓶颈",
            }
        )
    return result


def yield_sensitivity(tasks, budget_cents, rates=(1.0, 0.8, 0.6), *, costs_are_attempts=False):
    if not costs_are_attempts:
        raise ValidationError("必须明确将单价解释为尝试成本，避免把合格单价再次除以成品率")
    results = []
    for rate in rates:
        if (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(rate)
            or not 0 < rate <= 1
        ):
            raise ValidationError("成品率需大于0且不超过1")
        altered = [replace(t, cost_cents=math.ceil(t.cost_cents / rate)) for t in tasks]
        plan = solve(altered, budget_cents)
        results.append(
            {
                "assumed_yield": rate,
                "status": plan.status,
                "expected_spend_cents": plan.spent_cents if plan.allocation is not None else None,
                "planned_accepted": sum(plan.allocation.values())
                if plan.allocation is not None
                else None,
                "residual_loss": plan.residual_loss if plan.allocation is not None else None,
                "notice": "期望成本假设；不是交付保证，不是实际成品率估计",
            }
        )
    return results
