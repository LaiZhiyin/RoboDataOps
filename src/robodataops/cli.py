"""CLI entry points share exactly the same domain pipeline as the UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from robodataops.demo import default_targets, generate_demo
from robodataops.errors import RoboDataOpsError
from robodataops.export import plan_csv, plan_json
from robodataops.ingest import load_batch
from robodataops.metrics import context_for, coverage, episode_states, planning_tasks
from robodataops.models import RuleProfile, Target, canonical_json
from robodataops.planning import compare_plans, money_to_cents
from robodataops.quality import audit_batch
from robodataops.store import Store


def _write(path: str, content: str | bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RoboDataOps 轨迹质检与补采规划")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="生成明确标记的合成 v3 样例")
    demo.add_argument("--output", default="data/demo")
    demo.add_argument("--clean", action="store_true")
    fetch = sub.add_parser("fetch-libero", help="下载固定版本公开数据，仅元数据与所需表格")
    fetch.add_argument("--output", default="data/raw/libero")
    fetch.add_argument("--tasks", type=int, default=5)
    fetch.add_argument("--per-task", type=int, default=20)
    fetch.add_argument("--seed", type=int, default=42)
    for command in ("audit", "plan"):
        item = sub.add_parser(command)
        item.add_argument("--source", default=None)
        item.add_argument("--config", default=None, help="JSON 配置，含 source/profile/targets")
        item.add_argument("--db", default="var/robodataops.duckdb")
        item.add_argument("--output", default=f"reports/{command}.json")
        if command == "plan":
            item.add_argument("--budget", default="800.00", help="元，最多两位小数")
            item.add_argument(
                "--strategy", choices=["optimal", "greedy", "equal"], default="optimal"
            )
            item.add_argument("--csv", default="reports/plan.csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = None
    try:
        if args.command == "demo":
            print(generate_demo(args.output, injected=not args.clean))
            return 0
        if args.command == "fetch-libero":
            from robodataops.fetch import fetch_libero

            print(
                fetch_libero(
                    args.output, task_count=args.tasks, per_task=args.per_task, seed=args.seed
                )
            )
            return 0
        config = json.loads(Path(args.config).read_text()) if args.config else {}
        if not isinstance(config, dict):
            raise RoboDataOpsError("配置必须是 JSON 对象")
        source = Path(args.source or config.get("source", "data/demo"))
        if source == Path("data/demo") and not (source / "manifest.json").exists():
            generate_demo(source)
        batch = load_batch(source)
        profile = RuleProfile(**config.get("profile", {}))
        audit = audit_batch(batch, profile)
        store = Store(args.db)
        store.record_audit(batch, audit)
        reviews = store.reviews(audit.run_id)
        ids = sorted({ep.task_id for ep in batch.episodes if ep.task_id in batch.tasks})
        targets = (
            [Target(**row) for row in config["targets"]]
            if "targets" in config
            else default_targets(ids)
        )
        frame = coverage(batch, audit, reviews, targets)
        if args.command == "audit":
            report = {
                "source": batch.manifest,
                "snapshot_id": batch.snapshot_id,
                "run_id": audit.run_id,
                "profile": profile,
                "findings": audit.findings,
                "states": episode_states(batch, audit, reviews),
                "coverage": frame.to_dict("records"),
                "elapsed_seconds": audit.elapsed_seconds,
                "notice": "合成测试、公开样本和模拟业务参数分别标记；未验证策略或真实成本收益",
            }
            _write(args.output, canonical_json(report))
            print(
                f"已检查 {len(batch.episodes)} 条轨迹，生成 {len(audit.findings)} 项发现；报告：{args.output}"
            )
        else:
            tasks = planning_tasks(frame)
            if not targets:
                raise RoboDataOpsError("尚未定义目标任务，请补充任务映射与目标")
            plans = compare_plans(tasks, money_to_cents(args.budget))
            plan = next(item for item in plans if item.strategy == args.strategy)
            context = context_for(batch, audit, reviews, targets)
            plan_id = store.save_plan(plan, tasks, context)
            payload = store.plan(plan_id)
            payload["comparison"] = plans
            _write(args.output, plan_json(payload))
            _write(args.csv, plan_csv(payload))
            print(
                f"方案 {plan_id}：{plan.message}；预计费用 ¥{plan.spent_cents / 100:.2f}；结果：{args.output}"
            )
        return 0
    except (RoboDataOpsError, OSError, ValueError, TypeError) as exc:
        print(f"输入或数据错误：{exc}", file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
