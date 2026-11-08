"""Cross-module regressions for cumulative, review, scenario and research workflows."""

import copy
from dataclasses import replace
from pathlib import Path

import pytest

from robodataops.cli import main
from robodataops.contracts import action_contract
from robodataops.cumulative import accumulate
from robodataops.demo import default_targets, generate_demo
from robodataops.errors import DataSourceError, ValidationError
from robodataops.ingest import load_batch
from robodataops.metrics import coverage, planning_tasks
from robodataops.models import Target
from robodataops.quality import audit_batch
from robodataops.research import summarize_study
from robodataops.scenarios import (
    counterfactuals,
    export_scenario,
    import_scenario,
    yield_sensitivity,
)
from robodataops.store import Store

ROOT = Path(__file__).resolve().parents[1]


def test_cumulative_dedup_preserves_rows_and_carries_reviews_idempotently(tmp_path):
    batch = load_batch(generate_demo(tmp_path / "source"))
    batch.episodes = [ep for ep in batch.episodes if ep.rows and not ep.read_error]
    audit = audit_batch(batch)
    store = Store()
    store.record_audit(batch, audit)
    original = next(f for f in audit.findings if f.episode_index == 64)
    store.review(original.finding_id, "dismissed", "有效的等待动作")
    merged = accumulate([batch, batch], tmp_path / "merged")
    result = audit_batch(merged)
    assert len(merged.episodes) == len(batch.episodes)
    assert (
        next(ep for ep in merged.episodes if ep.episode_index == 64).rows
        == next(ep for ep in batch.episodes if ep.episode_index == 64).rows
    )
    assert merged.manifest["parents"] == [batch.snapshot_id]
    assert store.carry_reviews([(batch, audit)], merged, result) == 1
    assert store.carry_reviews([(batch, audit)], merged, result) == 0
    accepted = coverage(
        merged, result, store.reviews(result.run_id), default_targets()
    ).accepted.sum()
    assert accepted == coverage(batch, audit, {}, default_targets()).accepted.sum() + 1
    carried = next(f for f in result.findings if f.episode_index == 64)
    store.review(carried.finding_id, "confirmed", "新证据证明该动作不适用")
    assert store.carry_reviews([(batch, audit)], merged, result) == 0
    assert store.reviews(result.run_id)[carried.finding_id]["decision"] == "confirmed"


def test_cumulative_conflicts_and_contract_changes_rejected(tmp_path):
    batch = load_batch(generate_demo(tmp_path / "source", count=2, injected=False))
    other = copy.deepcopy(batch)
    other.episodes[0].rows[0]["action"][0] += 1
    with pytest.raises(ValidationError, match="冲突"):
        accumulate([batch, other], tmp_path / "conflict")
    other = copy.deepcopy(batch)
    other.info["fps"] *= 2
    with pytest.raises(ValidationError, match="契约"):
        accumulate([batch, other], tmp_path / "incompatible")
    with pytest.raises(ValidationError, match="独立"):
        accumulate([batch], batch.root / "nested")
    with pytest.raises(ValidationError, match="已存在"):
        accumulate([batch], batch.root)
    with pytest.raises(ValidationError):
        accumulate([], tmp_path / "empty")


def test_cumulative_public_delivery_updates_each_task_once(tmp_path):
    base, incoming = [
        load_batch(ROOT / "data" / name) for name in ("public_sample", "public_delivery")
    ]
    merged = accumulate([base, incoming, incoming], tmp_path / "merged")
    assert len(merged.episodes) == 120
    assert len(merged.manifest["video_evidence"]) == 5
    assert not audit_batch(merged).findings
    targets = default_targets(sorted({ep.task_id for ep in base.episodes}))
    before = coverage(base, audit_batch(base), {}, targets)
    after = coverage(merged, audit_batch(merged), {}, targets)
    assert (after.accepted - before.accepted).tolist() == [4] * 5


def test_bulk_review_atomic_and_reopen_retains_history(tmp_path):
    batch = load_batch(generate_demo(tmp_path))
    audit = audit_batch(batch)
    store = Store()
    store.record_audit(batch, audit)
    ids = [f.finding_id for f in audit.findings[:2]]
    with pytest.raises(ValidationError):
        store.bulk_review([ids[0], "unknown"], "dismissed", "reason")
    assert not store.history(audit.run_id)
    store.bulk_review(ids, "confirmed", "核对了原始字段")
    store.reopen(ids[0], "需要补充证据")
    assert len(store.history(audit.run_id)) == 3
    assert store.reviews(audit.run_id)[ids[0]]["decision"] == "deferred"
    with pytest.raises(ValidationError):
        store.reopen(ids[0], " ")


@pytest.mark.parametrize("ids", [[], ["same", "same"], [str(i) for i in range(501)]])
def test_bulk_review_rejects_empty_duplicate_oversized(ids):
    with pytest.raises(ValidationError):
        Store().bulk_review(ids, "dismissed", "reason")


def test_scenario_round_trip_persistence_and_parameter_evidence():
    targets = [Target("1", 30, 1500, 12, 2, "user_input", "报价单 A，第3项")]
    text = export_scenario("试点A", targets, 80000)
    clean = import_scenario(text, {"1"})
    assert clean["targets"][0]["rationale"] == targets[0].rationale
    store = Store()
    assert store.save_scenario(text) == store.save_scenario(text)
    assert len(store.scenarios()) == 1
    with pytest.raises(ValidationError):
        import_scenario(text, {"2"})
    with pytest.raises(ValidationError):
        export_scenario("缺证据", [replace(targets[0], rationale="")], 80000)


@pytest.mark.parametrize(
    "text", ["{}", "[]", "{", "a" * 128001, '{"format_version":1,"targets":[{}]}']
)
def test_invalid_scenario_inputs(text):
    with pytest.raises(ValidationError):
        import_scenario(text, {"1"})


def test_counterfactual_and_yield_semantics(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False))
    tasks = planning_tasks(coverage(batch, audit_batch(batch), {}, default_targets()))
    changes = counterfactuals(tasks, 30000)
    assert changes and all(r["improvement"] >= -1e-8 for r in changes)
    with pytest.raises(ValidationError, match="尝试成本"):
        yield_sensitivity(tasks, 30000)
    rows = yield_sensitivity(tasks, 30000, costs_are_attempts=True)
    assert rows[0]["residual_loss"] <= rows[-1]["residual_loss"]
    for rate in [0, True, float("nan"), 1.2]:
        with pytest.raises(ValidationError):
            yield_sensitivity(tasks, 30000, [rate], costs_are_attempts=True)


@pytest.mark.parametrize(
    "value", [{"unit": []}, {"unit": "radian"}, {"coordinate_frame": None}, {"extra": "x"}]
)
def test_action_semantics_never_inferred_from_dimension(value):
    with pytest.raises(DataSourceError):
        action_contract({"action_contract": value})
    assert action_contract({})["unit"] == "unknown"


def test_second_source_has_distinct_contract_and_no_fabricated_semantics():
    batch = load_batch(ROOT / "data/aloha_sample")
    assert len(batch.episodes) == 5
    assert batch.info["fps"] == 50
    assert batch.info["features"]["action"]["shape"] == [14]
    assert action_contract(batch.manifest)["control_mode"] == "unknown"
    assert not audit_batch(batch).findings


def test_real_study_template_is_empty_and_cli_does_not_invent_results(tmp_path):
    template = ROOT / "docs/research/study-template.csv"
    with pytest.raises(ValidationError, match="真实参与者"):
        summarize_study(template.read_text())
    assert (
        main(["evaluate-study", "--input", str(template), "--output", str(tmp_path / "fake.json")])
        == 2
    )
    assert not (tmp_path / "fake.json").exists()
    text = (
        template.read_text()
        + "example,developer,T1,baseline,1,100,1,1,0,fixture\nexample,developer,T1,tool,2,70,1,0,0,fixture\n"
    )
    result = summarize_study(text)
    assert result["paired_tasks"] == 1 and result["median_seconds_saved"] == 30
    with pytest.raises(ValidationError):
        summarize_study(text + "example,developer,T1,tool,2,70,1,0,0,fixture\n")


def test_cli_accumulate(tmp_path):
    root = generate_demo(tmp_path / "source", count=2, injected=False)
    assert (
        main(["accumulate", "--sources", str(root), str(root), "--output", str(tmp_path / "out")])
        == 0
    )
    assert len(load_batch(tmp_path / "out").episodes) == 2
