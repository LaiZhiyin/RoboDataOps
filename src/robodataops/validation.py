"""Generate a reproducible evidence report, keeping synthetic/public results separate."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import tempfile
import time
from collections import Counter
from datetime import datetime
from fractions import Fraction
from itertools import product
from pathlib import Path
from random import Random
from zoneinfo import ZoneInfo

from robodataops.demo import generate_demo
from robodataops.ingest import file_sha256, load_batch
from robodataops.metrics import episode_states
from robodataops.models import PlanningTask, canonical_json
from robodataops.planning import compare_plans, validate_allocation
from robodataops.quality import audit_batch


def enumerated_loss(tasks, budget):
    best = None
    for quantities in product(*(range(min(t.demand, t.capacity) + 1) for t in tasks)):
        if sum(t.cost_cents * x for t, x in zip(tasks, quantities, strict=True)) > budget:
            continue
        value = sum(
            Fraction(str(t.weight)) * Fraction(t.demand - x, t.demand)
            for t, x in zip(tasks, quantities, strict=True)
            if t.demand
        )
        if best is None or value < best:
            best = value
    return float(best or 0)


def run_validation(project: Path, *, scenarios: int = 100) -> dict:
    started = time.perf_counter()
    rng = Random(42)
    cases = []
    for index in range(scenarios):
        tasks = [
            PlanningTask(
                str(i),
                f"Task {i}",
                rng.randint(1, 4),
                rng.randint(1, 9),
                rng.randint(0, 4),
                rng.randint(1, 6),
            )
            for i in range(rng.randint(1, 5))
        ]
        budget = rng.randint(0, 50)
        plans = compare_plans(tasks, budget)
        for plan in plans:
            validate_allocation(tasks, budget, plan.allocation)
        expected = enumerated_loss(tasks, budget)
        actual = next(p for p in plans if p.strategy == "optimal")
        if abs(actual.residual_loss - expected) > 1e-7 or actual.status != "optimal":
            raise AssertionError(f"Oracle mismatch in scenario {index}")
        cases.append(
            {
                "scenario": index,
                "tasks": tasks,
                "budget_cents": budget,
                "oracle_loss": expected,
                "results": plans,
            }
        )
    with tempfile.TemporaryDirectory() as directory:
        clean = load_batch(generate_demo(Path(directory) / "clean", injected=False))
        clean_audit = audit_batch(clean)
        injected = load_batch(generate_demo(Path(directory) / "injected"))
        injected_audit = audit_batch(injected)
        expected = {
            (1, "T001"),
            (7, "D003"),
            (13, "D002"),
            (25, "I001"),
            (34, "B001"),
            (49, "I003"),
            (58, "T002"),
            (64, "R002"),
            (72, "K001"),
            (83, "D001"),
            (90, "I003"),
            (96, "R001"),
            (97, "S001"),
        }
        observed = {(f.episode_index, f.rule_id) for f in injected_audit.findings}
        missing = sorted(expected - observed)
        if clean_audit.findings or missing:
            raise AssertionError("Synthetic checks did not match expected outcomes")
        synthetic = {
            "clean_episodes": 100,
            "clean_findings": len(clean_audit.findings),
            "injected_episodes": 100,
            "expected_fault_cases": len(expected),
            "recovered_fault_cases": len(expected) - len(missing),
            "findings": len(injected_audit.findings),
            "states": dict(Counter(s["status"] for s in episode_states(injected, injected_audit))),
            "notice": "受控合成故障，非真实分布准确率；相关变体不作为独立真实样本",
        }
    public = None
    for path in (project / "data/public_sample", project / "data/raw/libero"):
        if (path / "manifest.json").exists():
            batch = load_batch(path)
            audit = audit_batch(batch)
            public = {
                "repo_id": batch.repo_id,
                "revision": batch.revision,
                "snapshot_id": batch.snapshot_id,
                "episodes": len(batch.episodes),
                "frames": sum(len(ep.rows) for ep in batch.episodes),
                "task_ids": sorted({ep.task_id for ep in batch.episodes}),
                "findings": len(audit.findings),
                "rules": dict(Counter(f.rule_id for f in audit.findings)),
                "states": dict(Counter(s["status"] for s in episode_states(batch, audit))),
                "audit_seconds": audit.elapsed_seconds,
                "ground_truth": "尚无独立人工标签，不估计真实 precision/recall；视频未检查",
            }
            break
    hashes = {
        str(path.relative_to(project)): file_sha256(path)
        for path in sorted((project / "src").rglob("*.py"))
    }
    hashes["app.py"] = file_sha256(project / "app.py")
    hashes["src/robodataops/sql/coverage.sql"] = file_sha256(
        project / "src/robodataops/sql/coverage.sql"
    )
    return {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "dependencies": {
                name: importlib.metadata.version(name)
                for name in ["numpy", "pandas", "scipy", "duckdb", "pyarrow", "streamlit"]
            },
        },
        "source_hashes": hashes,
        "synthetic_quality": synthetic,
        "public_sample": public,
        "planning": {
            "seed": 42,
            "scenarios": scenarios,
            "oracle_matches": scenarios,
            "constraint_checks": scenarios * 3,
            "cases": cases,
            "notice": "随机合成业务情景，非真实采集成本收益",
        },
        "elapsed_seconds": time.perf_counter() - started,
        "not_conducted": [
            "独立人工金标准",
            "真实用户对照测试",
            "机器人训练与rollout",
            "真实采集成本试点",
        ],
    }


def main():
    project = Path.cwd()
    report = run_validation(project)
    output = project / "reports"
    output.mkdir(exist_ok=True)
    (output / "validation.json").write_text(canonical_json(report), encoding="utf-8")
    synthetic, planning, public = (
        report["synthetic_quality"],
        report["planning"],
        report["public_sample"],
    )
    lines = [
        "# RoboDataOps 实际验证结果",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 自动化数据与规划验证",
        "",
        f"- 干净合成数据：{synthetic['clean_episodes']} 条，发现 {synthetic['clean_findings']} 项。",
        f"- 注入样本：{synthetic['injected_episodes']} 条，{synthetic['recovered_fault_cases']}/{synthetic['expected_fault_cases']} 个已知案例产生预期证据，共 {synthetic['findings']} 项发现。",
        f"- 独立整数枚举：{planning['oracle_matches']}/{planning['scenarios']} 情景目标值一致。",
        f"- 三种策略约束核对：{planning['constraint_checks']} 次。",
        "",
    ]
    if public:
        lines += [
            "## 固定版本公开样本",
            "",
            f"数据集：{public['repo_id']}，revision `{public['revision']}`。",
            f"本次实际读取 {public['episodes']} 条完整轨迹、{public['frames']} 帧、{len(public['task_ids'])} 个任务；产生 {public['findings']} 项发现。",
            f"规则分布：`{json.dumps(public['rules'])}`。",
            "",
            "上述发现未全部获得独立人工确认，不能解释为真实缺陷率。本报告默认仅检查表格；5段视频证据与其他V1兼容结果另见 v1-evidence.json，未做全量相机验收。",
            "",
        ]
    lines += [
        "## 结论边界",
        "",
        "合成故障验证规则逻辑；公开数据验证实际接入；规划结果验证给定目标与约束。",
        "用户效率、真实成本与机器人策略表现仍待实验。逐情景原始结果、环境与源码校验记录见同目录 validation.json。",
        "",
    ]
    (output / "validation.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"验证完成：{output / 'validation.md'}")


if __name__ == "__main__":
    main()
