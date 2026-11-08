"""Small domain objects shared by the CLI, analysis layer, and UI."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any


def jsonable(value: Any) -> Any:
    """Keep non-finite evidence readable while emitting standards-compliant JSON."""
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(jsonable(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: Any, length: int = 24) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()[:length]


@dataclass(frozen=True)
class RuleProfile:
    name: str = "tabular-v3"
    version: str = "1.0.0"
    timestamp_tolerance: float = 0.0001
    max_gap_factor: float = 1.8
    review_signals: bool = True
    short_episode_seconds: float = 0.5
    low_motion_threshold: float = 0.00001
    require_video: bool = False

    @property
    def profile_id(self) -> str:
        return digest(self)


@dataclass
class Episode:
    episode_index: int
    task_id: str | None
    declared_length: int
    rows: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    source_files: tuple[str, ...] = ()
    read_error: str | None = None


@dataclass
class Batch:
    repo_id: str
    revision: str
    source_kind: str
    snapshot_id: str
    info: dict[str, Any]
    tasks: dict[str, str]
    episodes: list[Episode]
    manifest: dict[str, Any]
    root: Path


@dataclass(frozen=True)
class Finding:
    finding_id: str
    run_id: str
    episode_index: int
    rule_id: str
    title: str
    field: str
    severity: str
    observed: Any
    expected: Any
    frame_start: int | None = None
    frame_end: int | None = None
    hit_count: int = 1
    automatic_block: bool = True


@dataclass
class Audit:
    run_id: str
    snapshot_id: str
    profile: RuleProfile
    findings: list[Finding]
    completed: dict[int, bool]
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class Target:
    task_id: str
    target: int
    cost_cents: int
    capacity: int
    weight: float = 1.0
    parameter_source: str = "simulated"


@dataclass(frozen=True)
class PlanningTask:
    task_id: str
    label: str
    demand: int
    cost_cents: int
    capacity: int
    weight: float = 1.0
    current: int = 0
    target: int = 0
    parameter_source: str = "simulated"


@dataclass
class Plan:
    strategy: str
    status: str
    allocation: dict[str, int] | None
    budget_cents: int
    spent_cents: int
    residual_loss: float
    initial_loss: float
    elapsed_seconds: float
    message: str
    solver_gap: float | None = None
    solver_bound: float | None = None

    @property
    def fulfilled_fraction(self) -> float | None:
        if not self.initial_loss or self.allocation is None:
            return None
        return 1 - self.residual_loss / self.initial_loss
