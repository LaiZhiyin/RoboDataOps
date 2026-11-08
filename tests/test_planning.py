from fractions import Fraction
from itertools import product
from random import Random
from types import SimpleNamespace

import numpy as np
import pytest

from robodataops.errors import ValidationError
from robodataops.models import PlanningTask
from robodataops.planning import compare_plans, solve, validate_allocation


def task(name, demand, cost, weight=1, capacity=None):
    return PlanningTask(name, name, demand, cost, demand if capacity is None else capacity, weight)


def independent_optimum(tasks, budget):
    values = []
    for xs in product(*(range(min(t.demand, t.capacity) + 1) for t in tasks)):
        if sum(t.cost_cents * x for t, x in zip(tasks, xs, strict=True)) <= budget:
            values.append(
                sum(
                    Fraction(str(t.weight)) * Fraction(t.demand - x, t.demand)
                    for t, x in zip(tasks, xs, strict=True)
                    if t.demand
                )
            )
    return float(min(values, default=0))


@pytest.mark.parametrize("budget,loss", [(0, 6), (10, 3), (20, 5 / 3), (34, 0)])
def test_attachment_regression(budget, loss):
    tasks = [task("A", 4, 3, 1), task("B", 3, 4, 2), task("C", 2, 5, 3)]
    plan = solve(tasks, budget)
    assert plan.status == "optimal"
    assert plan.residual_loss == pytest.approx(loss)
    validate_allocation(tasks, budget, plan.allocation)


def test_integer_counterexample_beats_greedy():
    tasks = [task("A", 1, 6, 7), task("B", 1, 5, 5), task("C", 1, 5, 5)]
    plans = {p.strategy: p for p in compare_plans(tasks, 10)}
    assert plans["optimal"].allocation == {"A": 0, "B": 1, "C": 1}
    assert plans["greedy"].residual_loss == 10
    assert plans["optimal"].residual_loss == 7


def test_seeded_small_problems_match_independent_enumeration():
    rng = Random(42)
    for _ in range(100):
        tasks = [
            task(str(i), rng.randint(1, 4), rng.randint(1, 9), rng.randint(1, 6), rng.randint(0, 4))
            for i in range(rng.randint(1, 5))
        ]
        budget = rng.randint(0, 50)
        for plan in compare_plans(tasks, budget):
            validate_allocation(tasks, budget, plan.allocation)
        assert solve(tasks, budget).residual_loss == pytest.approx(
            independent_optimum(tasks, budget)
        )


@pytest.mark.parametrize("cost", [0, -1, float("nan"), 1.5, True])
def test_invalid_money_rejected(cost):
    with pytest.raises(ValidationError):
        solve([task("A", 1, cost)], 10)


def test_zero_gap_and_zero_capacity():
    assert solve([task("A", 0, 1)], 0).status == "no_gap"
    assert solve([task("A", 5, 1, capacity=0)], 50).allocation == {"A": 0}


def test_zero_weights_and_duplicate_ids_rejected():
    with pytest.raises(ValidationError):
        solve([task("A", 2, 1, 0)], 10)
    with pytest.raises(ValidationError):
        solve([task("A", 1, 1), task("A", 1, 2)], 10)


def test_budget_monotonicity_of_objective():
    tasks = [task("A", 4, 3, 1), task("B", 3, 4, 2)]
    losses = [solve(tasks, budget).residual_loss for budget in range(20)]
    assert all(a + 1e-8 >= b for a, b in zip(losses, losses[1:], strict=False))


@pytest.mark.parametrize(
    "status,candidate,expected",
    [(1, [0.0], "feasible"), (1, None, "no_solution"), (2, None, "infeasible"), (4, None, "error")],
)
def test_solver_status_is_not_overstated(monkeypatch, status, candidate, expected):
    monkeypatch.setattr(
        "robodataops.planning.milp",
        lambda **kwargs: SimpleNamespace(
            status=status,
            x=np.array(candidate) if candidate is not None else None,
            message="controlled test status",
        ),
    )
    assert solve([task("A", 3, 2)], 10).status == expected
