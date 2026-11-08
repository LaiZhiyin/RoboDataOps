from dataclasses import replace

from robodataops.demo import generate_demo
from robodataops.ingest import load_batch
from robodataops.models import RuleProfile
from robodataops.quality import audit_batch


def test_clean_synthetic_data_and_episode_timestamp_resets(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False, count=6))
    audit = audit_batch(batch)
    assert audit.findings == []
    assert all(audit.completed.values())


def test_injected_defects_have_localized_evidence(tmp_path):
    batch = load_batch(generate_demo(tmp_path))
    audit = audit_batch(batch)
    pairs = {(f.episode_index, f.rule_id) for f in audit.findings}
    assert {
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
    } <= pairs
    assert all(
        not f.automatic_block
        for f in audit.findings
        if f.rule_id in {"R001", "R002", "T002", "S001"}
    )
    assert next(f for f in audit.findings if f.episode_index == 7).frame_start == 8
    assert audit.completed[97] is False


def test_required_video_does_not_silently_pass(tmp_path):
    batch = load_batch(generate_demo(tmp_path, injected=False, count=2))
    audit = audit_batch(batch, RuleProfile(require_video=True))
    assert not any(audit.completed.values())
    assert {f.rule_id for f in audit.findings} == {"V001"}


def test_changed_rule_profile_changes_run_identity(tmp_path):
    batch = load_batch(generate_demo(tmp_path, count=2))
    first = audit_batch(batch)
    second = audit_batch(batch, replace(RuleProfile(), timestamp_tolerance=0.01))
    assert first.run_id != second.run_id
