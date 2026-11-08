"""Produce public compatibility and hypothetical teaching outputs with the real core."""

import json
from pathlib import Path

from robodataops.ingest import load_batch
from robodataops.media import inspect, references
from robodataops.models import PlanningTask, canonical_json
from robodataops.planning import compare_plans
from robodataops.quality import audit_batch

root = Path(__file__).resolve().parents[1]
sources = []
media = []
for name in ("public_sample", "aloha_sample", "public_delivery"):
    batch = load_batch(root / "data" / name)
    if name == "public_sample":
        for ep in batch.episodes:
            for ref in references(batch.info, ep.metadata, batch.manifest, batch.root):
                if ref.path.exists():
                    result = inspect(ref, full_decode=True)
                    if result["status"] != "decoded":
                        raise RuntimeError(f"Public clip did not decode: {result}")
                    media.append(
                        {
                            "episode_index": ep.episode_index,
                            "source_path": ref.source_path,
                            "source_from_s": ref.source_start,
                            "source_to_s": ref.source_end,
                            **result,
                        }
                    )
    sources.append(
        {
            "cache": name,
            "repo_id": batch.repo_id,
            "revision": batch.revision,
            "snapshot": batch.snapshot_id,
            "episodes": len(batch.episodes),
            "frames": sum(len(ep.rows) for ep in batch.episodes),
            "fps": batch.info["fps"],
            "action_dimensions": batch.info["features"]["action"]["shape"],
            "findings": len(audit_batch(batch).findings),
        }
    )
tasks = [
    PlanningTask("A", "Task A", 8, 6000, 8, 2),
    PlanningTask("B", "Task B", 7, 4500, 5, 1.4),
    PlanningTask("C", "Task C", 10, 2000, 7, 1),
]
scenarios = [
    {"budget_cents": budget, "tasks": tasks, "plans": compare_plans(tasks, budget)}
    for budget in (20000, 35000, 50000, 80000)
]
report = {
    "release": "1.0.0",
    "sources": sources,
    "media": media,
    "scenarios": scenarios,
    "notice": "Public simulation compatibility, reserved offline delivery simulation and hypothetical budget teaching data. No human or policy effectiveness claim.",
}
(root / "reports/v1-evidence.json").write_text(canonical_json(report), encoding="utf-8")
print(json.dumps(sources, indent=2))
