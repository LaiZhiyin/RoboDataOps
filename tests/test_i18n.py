import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from robodataops.cli import main
from robodataops.i18n import ENGLISH, get_language, set_language, tr
from robodataops.localized_ui import localized_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def reset_language():
    set_language("en")
    yield
    set_language("en")


def test_catalog_placeholders_and_unknown_source_text():
    for source, target in ENGLISH.items():
        assert sorted(re.findall(r"\{\d+\}", source)) == sorted(re.findall(r"\{\d+\}", target))
    assert tr("复核队列 · 14 项") == "Review queue · 14 findings"
    assert tr("非有限或非数值数据") == "Non-finite or non-numeric data"
    assert tr("EP customer note: 数据概览") == "EP customer note: 数据概览"
    assert tr("<p>用户原文：预算</p>") == "<p>用户原文：预算</p>"
    assert tr("已生成描述性统计：预算") == "Descriptive summary written to 预算"
    assert tr("这是用户的目标.csv") == "这是用户的目标.csv"
    set_language("zh")
    assert tr("数据概览") == "数据概览"
    with pytest.raises(ValueError):
        set_language("invalid")


def test_language_contexts_are_isolated_between_threads():
    from threading import Barrier

    barrier = Barrier(2)

    def task(language):
        set_language(language)
        barrier.wait()
        return tr("数据概览")

    with ThreadPoolExecutor(2) as pool:
        english = pool.submit(task, "en")
        chinese = pool.submit(task, "zh")
        assert english.result() == "Data overview"
        assert chinese.result() == "数据概览"
    assert get_language() == "en"


def test_table_localization_never_mutates_source():
    frame = pd.DataFrame({"任务": ["抓取方块并放入托盘"], "当前计入": [3]})
    original = frame.copy(deep=True)
    translated = localized_frame(frame)
    assert translated["Task"][0] == "Pick the block and place it in the tray"
    pd.testing.assert_frame_equal(frame, original)


def test_default_english_and_round_trip_preserves_plan_and_review(monkeypatch):
    monkeypatch.setenv("ROBODATAOPS_DEMO_MODE", "1")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=40).run()
    assert not app.exception
    assert app.title[0].value == "From trajectory evidence to collection decisions."
    app.sidebar.radio[0].set_value("问题复核").run()
    audit = app.session_state["_audit"]
    finding = next(f for f in audit.findings if f.episode_index == 64)
    app.selectbox(key="finding-selector").set_value(finding.finding_id).run()
    app.radio(key=f"decision-{finding.finding_id}").set_value("dismissed")
    app.text_area(key=f"reason-{finding.finding_id}").set_value("Waiting is allowed for this task")
    next(b for b in app.button if b.label == "Save review decision").click().run()
    app.sidebar.radio[0].set_value("补采规划").run()
    app.number_input(key="budget-yuan").set_value(500.0).run()
    next(b for b in app.button if b.label == "Generate and save plans").click().run()
    comparison = app.session_state["_comparison"]["ids"]
    snapshot = app.session_state["_batch"].snapshot_id
    app.selectbox(key="ui-language").set_value("zh").run()
    assert not app.exception and not app.error
    assert app.title[0].value == "把有限预算，分配给明确缺口。"
    assert app.number_input(key="budget-yuan").value == 500.0
    assert app.session_state["_comparison"]["ids"] == comparison
    app.selectbox(key="ui-language").set_value("en").run()
    assert app.session_state["_batch"].snapshot_id == snapshot
    assert (
        app.session_state["_store"].reviews(audit.run_id)[finding.finding_id]["decision"]
        == "dismissed"
    )


def test_language_switch_preserves_audit_settings_and_run_id(monkeypatch):
    monkeypatch.setenv("ROBODATAOPS_DEMO_MODE", "1")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=40).run()
    next(c for c in app.checkbox if c.label == "Review short and low-motion episodes").set_value(
        False
    ).run()
    run_id = app.session_state["_audit"].run_id
    app.selectbox(key="ui-language").set_value("zh").run()
    assert not app.exception
    assert next(c for c in app.checkbox if c.label == "启用短轨迹与低运动复核信号").value is False
    assert app.session_state["_audit"].run_id == run_id


def test_cli_defaults_to_english_and_accepts_chinese(tmp_path, capsys):
    args = ["audit", "--source", str(tmp_path / "missing"), "--db", ":memory:"]
    assert main(args) == 2
    assert "Input or data error" in capsys.readouterr().err
    assert main([*args, "--lang", "zh"]) == 2
    assert "输入或数据错误" in capsys.readouterr().err


def test_readme_default_and_video_routes_match_language():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "portfolio_builder", ROOT / "script/build_portfolio.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    outputs = module.build_outputs()
    english, chinese = outputs[ROOT / "README.md"], outputs[ROOT / "README.zh-CN.md"]
    assert english == outputs[ROOT / "README.en.md"]
    assert "WATCH THE PRODUCT DEMO — CLICK TO PLAY" in english
    assert "?lang=en#demo" in english and "robodataops-demo-en.mp4" in english
    assert "?lang=zh#demo" in chinese and "robodataops-demo-zh.mp4" in chinese
    assert "点击播放产品讲解视频" in chinese
    content = json.loads((ROOT / "portfolio/content.json").read_text())
    assert content["en"]["tagline"] in english
