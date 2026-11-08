"""Budget planning with independently validated integer allocations."""

from __future__ import annotations

import math
import time
from decimal import Decimal, InvalidOperation

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from robodataops.errors import ValidationError
from robodataops.models import Plan, PlanningTask


def money_to_cents(value: str | float | int) -> int:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError("金额必须为有效数字") from exc
    if (
        not amount.is_finite()
        or amount < 0
        or amount > Decimal("10000000000")
        or amount * 100 != (amount * 100).to_integral_value()
    ):
        raise ValidationError("金额必须非负，且最多包含两位小数")
    cents = int(amount * 100)
    if cents > 10**12:
        raise ValidationError("金额超出本地规划支持范围")
    return cents


def _integer(value: object, name: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name}必须为整数")
    if value < (1 if positive else 0) or value > 10**12:
        raise ValidationError(f"{name}超出允许范围")


def validate_task_fields(tasks: list[PlanningTask], budget_cents: int) -> None:
    _integer(budget_cents, "预算")
    ids = [t.task_id for t in tasks]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValidationError("任务 ID 必须非空且唯一")
    for item in tasks:
        _integer(item.demand, "缺口")
        _integer(item.capacity, "产能")
        _integer(item.cost_cents, "单价", positive=True)
        if (
            isinstance(item.weight, bool)
            or not isinstance(item.weight, (int, float))
            or not math.isfinite(item.weight)
            or item.weight < 0
        ):
            raise ValidationError("权重必须是有限的非负数")


def validate_inputs(tasks: list[PlanningTask], budget_cents: int) -> None:
    validate_task_fields(tasks, budget_cents)
    if any(t.demand for t in tasks) and not any(t.demand and t.weight > 0 for t in tasks):
        raise ValidationError("存在缺口时，至少一个任务的权重必须大于零")


def validate_allocation(
    tasks: list[PlanningTask], budget_cents: int, allocation: dict[str, int] | None
) -> None:
    """Recompute feasibility with Python integers, outside the solver model."""
    validate_inputs(tasks, budget_cents)
    if allocation is None or set(allocation) != {t.task_id for t in tasks}:
        raise ValidationError("分配结果缺少任务或包含未知任务")
    spent = 0
    for item in tasks:
        count = allocation[item.task_id]
        _integer(count, "新增数量")
        if count > min(item.demand, item.capacity):
            raise ValidationError(f"任务 {item.task_id} 的分配超过缺口或产能")
        spent += count * item.cost_cents
    if spent > budget_cents:
        raise ValidationError("分配超出预算")


def _result(tasks, budget, xs, strategy, status, started, message, gap=None, bound=None):
    allocation = None if xs is None else {t.task_id: int(x) for t, x in zip(tasks, xs, strict=True)}
    if allocation is not None:
        validate_allocation(tasks, budget, allocation)
    initial = sum(t.weight for t in tasks if t.demand)
    loss = sum(
        t.weight * (t.demand - (allocation[t.task_id] if allocation else 0)) / t.demand
        for t in tasks
        if t.demand
    )
    return Plan(
        strategy,
        status,
        allocation,
        budget,
        sum(t.cost_cents * allocation[t.task_id] for t in tasks) if allocation else 0,
        float(loss),
        float(initial),
        time.perf_counter() - started,
        message,
        gap,
        bound,
    )


def solve(tasks: list[PlanningTask], budget_cents: int, time_limit: float = 2.0) -> Plan:
    started = time.perf_counter()
    validate_inputs(tasks, budget_cents)
    if not math.isfinite(time_limit) or time_limit <= 0:
        raise ValidationError("求解时限必须大于零")
    zeros = [0] * len(tasks)
    if not any(t.demand for t in tasks):
        return _result(
            tasks, budget_cents, zeros, "optimal", "no_gap", started, "当前目标均已满足，无需补采"
        )
    upper = [
        min(t.demand, t.capacity) if t.weight > 0 and t.cost_cents <= budget_cents else 0
        for t in tasks
    ]
    if not any(upper):
        return _result(
            tasks,
            budget_cents,
            zeros,
            "optimal",
            "optimal",
            started,
            "预算或产能不足以新增交付，保留剩余缺口",
        )
    gains = np.array([t.weight / t.demand if t.demand else 0 for t in tasks])
    result = milp(
        c=-gains,
        integrality=np.ones(len(tasks)),
        bounds=Bounds(np.zeros(len(tasks)), np.asarray(upper)),
        constraints=LinearConstraint(
            np.array([[t.cost_cents for t in tasks]], dtype=float), -np.inf, budget_cents
        ),
        options={"time_limit": time_limit, "mip_rel_gap": 0.0},
    )
    candidate = None
    if result.x is not None and np.all(np.isfinite(result.x)):
        rounded = np.rint(result.x)
        if np.max(np.abs(result.x - rounded)) <= 1e-6:
            candidate = [int(x) for x in rounded]
            validate_allocation(
                tasks, budget_cents, {t.task_id: x for t, x in zip(tasks, candidate, strict=True)}
            )
    if result.status == 0 and candidate is not None:
        status, message = "optimal", "已证明当前数量目标下的最优解；等优分配可能不唯一"
    elif result.status == 1:
        status = "feasible" if candidate is not None else "no_solution"
        message = (
            "达到求解时限，已有可行方案但未证明最优"
            if candidate is not None
            else "达到求解时限，未返回可行方案；可查看基线或延长时限"
        )
    elif result.status == 2:
        status, message = (
            "infeasible",
            "求解器报告不可行；基础模型已有零分配可行解，请检查输入或模型",
        )
    else:
        status, message = "error", "求解未成功：" + str(result.message)
    gap = getattr(result, "mip_gap", None)
    dual = getattr(result, "mip_dual_bound", None)
    initial = sum(t.weight for t in tasks if t.demand)
    bound = initial + float(dual) if dual is not None and math.isfinite(dual) else None
    return _result(
        tasks,
        budget_cents,
        candidate,
        "optimal",
        status,
        started,
        message,
        float(gap) if gap is not None and math.isfinite(gap) else None,
        bound,
    )


def greedy(tasks: list[PlanningTask], budget_cents: int) -> Plan:
    started = time.perf_counter()
    validate_inputs(tasks, budget_cents)
    xs = [0] * len(tasks)
    left = budget_cents
    order = sorted(
        range(len(tasks)),
        key=lambda i: (
            -(tasks[i].weight / tasks[i].demand / tasks[i].cost_cents) if tasks[i].demand else 0,
            tasks[i].task_id,
        ),
    )
    for i in order:
        item = tasks[i]
        if item.weight <= 0:
            continue
        xs[i] = min(item.demand, item.capacity, left // item.cost_cents)
        left -= xs[i] * item.cost_cents
    return _result(
        tasks,
        budget_cents,
        xs,
        "greedy",
        "heuristic",
        started,
        "按单位成本的加权缺口收益排序，整数购买，任务 ID 打破并列",
    )


def equal_budget(tasks: list[PlanningTask], budget_cents: int) -> Plan:
    started = time.perf_counter()
    validate_inputs(tasks, budget_cents)
    xs = [0] * len(tasks)
    left = budget_cents
    while True:
        eligible = sorted(
            (
                i
                for i, t in enumerate(tasks)
                if t.weight > 0 and xs[i] < min(t.demand, t.capacity) and t.cost_cents <= left
            ),
            key=lambda i: tasks[i].task_id,
        )
        if not eligible:
            break
        share = left // len(eligible)
        bought = 0
        for i in eligible:
            t = tasks[i]
            count = min(t.demand - xs[i], t.capacity - xs[i], share // t.cost_cents)
            xs[i] += count
            left -= count * t.cost_cents
            bought += count
        if not bought:
            i = eligible[0]
            xs[i] += 1
            left -= tasks[i].cost_cents
    return _result(
        tasks,
        budget_cents,
        xs,
        "equal",
        "heuristic",
        started,
        "有缺口的任务均分剩余预算；取整余款反复均分，零星余款按任务 ID 分配",
    )


def compare_plans(
    tasks: list[PlanningTask], budget_cents: int, time_limit: float = 2.0
) -> list[Plan]:
    return [
        equal_budget(tasks, budget_cents),
        greedy(tasks, budget_cents),
        solve(tasks, budget_cents, time_limit),
    ]
