from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_three_pages_and_budget_recompute(monkeypatch):
    monkeypatch.setenv("ROBODATAOPS_DEMO_MODE", "1")
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    assert not app.exception
    assert not app.error
    assert app.metric[0].value == "100"
    app.sidebar.radio[0].set_value("问题复核").run()
    assert not app.exception
    assert any(w.label == "Save review decision" for w in app.button)
    app.sidebar.radio[0].set_value("补采规划").run()
    assert not app.exception
    next(w for w in app.button if w.label == "Generate and save plans").click().run()
    assert not app.exception
    assert not app.error
    assert any(w.label == "Expected cost" for w in app.metric)
    next(w for w in app.number_input if w.label == "Total budget / CNY").set_value(0.0).run()
    next(w for w in app.button if w.label == "Generate and save plans").click().run()
    assert not app.exception
    assert next(w for w in app.metric if w.label == "Expected cost").value == "¥ 0.00"


def test_review_requires_reason_and_updates_state(monkeypatch):
    monkeypatch.setenv("ROBODATAOPS_DEMO_MODE", "1")
    app = AppTest.from_file(str(APP), default_timeout=40).run()
    app.sidebar.radio[0].set_value("问题复核").run()
    audit = app.session_state["_audit"]
    finding = next(f for f in audit.findings if f.episode_index == 64)
    next(w for w in app.selectbox if w.label == "Select a finding").set_value(
        finding.finding_id
    ).run()
    next(w for w in app.radio if w.label == "Review decision").set_value("dismissed")
    next(w for w in app.button if w.label == "Save review decision").click().run()
    assert app.error
    app.text_area[0].set_value("正常保持动作，当前用途允许")
    next(w for w in app.button if w.label == "Save review decision").click().run()
    assert not app.exception
    assert (
        app.session_state["_store"].reviews(audit.run_id)[finding.finding_id]["decision"]
        == "dismissed"
    )
