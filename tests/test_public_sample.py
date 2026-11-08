from pathlib import Path

from robodataops.ingest import load_batch
from robodataops.quality import audit_batch
from robodataops.validation import run_validation

ROOT = Path(__file__).resolve().parents[1]


def test_pinned_public_analysis_cache_loads_without_network():
    batch = load_batch(ROOT / "data/public_sample")
    assert len(batch.episodes) == 100
    assert len({ep.task_id for ep in batch.episodes}) == 5
    assert batch.info["total_episodes"] == 1693
    assert all(len(ep.rows) == ep.declared_length for ep in batch.episodes)
    assert not audit_batch(batch).findings  # Regression expectation for this rule profile only.


def test_validation_keeps_public_and_synthetic_evidence_separate():
    report = run_validation(ROOT, scenarios=3)
    assert report["planning"]["oracle_matches"] == 3
    assert report["synthetic_quality"]["recovered_fault_cases"] == 13
    assert report["public_sample"]["episodes"] == 100
    assert report["not_conducted"]
