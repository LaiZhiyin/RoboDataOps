import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_and_html_preserve_the_same_narrative_and_reported_metrics():
    spec = importlib.util.spec_from_file_location(
        "portfolio_builder", ROOT / "script/build_portfolio.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    outputs = module.build_outputs()
    content = json.loads((ROOT / "portfolio/content.json").read_text())
    for lang in ("zh", "en"):
        readme = outputs[ROOT / ("README.zh-CN.md" if lang == "zh" else "README.md")]
        for section in content[lang]["sections"]:
            assert section["title"] in readme
            assert all(p in readme for p in section["paragraphs"])
    tests = json.loads((ROOT / "reports/test-summary.json").read_text())
    assert f"{tests['coverage_percent']:.2f}%" in outputs[ROOT / "site/index.html"]
    assert str(tests["tests"]) in outputs[ROOT / "README.md"]
