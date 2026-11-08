"""Build the bilingual case study and README files from one narrative source."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_outputs() -> dict[Path, str]:
    content = json.loads((ROOT / "portfolio/content.json").read_text())
    tests = json.loads((ROOT / "reports/test-summary.json").read_text())
    evidence = json.loads((ROOT / "reports/v1-evidence.json").read_text())
    validation = json.loads((ROOT / "reports/validation.json").read_text())
    oracle = validation["planning"]
    public_count = sum(
        s["episodes"]
        for s in evidence["sources"]
        if s["cache"] in {"public_sample", "aloha_sample"}
    )
    repo, home, version = content["repository"], content["homepage"], content["version"]

    def url(path):
        return f"{repo}/blob/v{version}/{path}"

    def esc(value):
        return html.escape(str(value), quote=True)

    pages, outputs = [], {}
    for lang in ("zh", "en"):
        text = content[lang]
        metrics = [
            (
                str(tests["tests"]),
                "通过的软件测试" if lang == "zh" else "passing software tests",
                "reports/test-summary.json",
            ),
            (
                f"{tests['coverage_percent']:.2f}%",
                "核心包行覆盖率" if lang == "zh" else "core package line coverage",
                "reports/test-summary.json",
            ),
            (
                f"{oracle['oracle_matches']} / {oracle['scenarios']}",
                "独立枚举目标一致" if lang == "zh" else "exhaustive oracle matches",
                "reports/validation.json",
            ),
            (
                str(public_count),
                "公开基线 / 兼容轨迹"
                if lang == "zh"
                else "public baseline / compatibility episodes",
                "reports/v1-evidence.json",
            ),
        ]
        md = [
            "<!-- Generated from portfolio/content.json. Run script/build_portfolio.py. -->",
            "# RoboDataOps",
            f"**{text['tagline']}**",
            text["description"],
            f"[中文]({repo}/blob/main/README.md) · [English]({repo}/blob/main/README.en.md) · [HTML {version}]({home}) · [GitHub Actions]({repo}/actions) · [Codespaces](https://codespaces.new/laizhiyin/RoboDataOps?quickstart=1)",
            f"[![{text['video_label']}]({home}assets/video-poster.jpg)]({home}#demo)",
            text["path_label"],
            " | ".join(f"[**{value}** {label}]({url(path)})" for value, label, path in metrics),
            f"[{'验证数字来源' if lang == 'zh' else 'Evidence for metrics'}]({url('reports/test-summary.json')})",
        ]
        body = []
        for section in text["sections"]:
            md.extend(["## " + section["title"], *section["paragraphs"]])
            blocks = []
            for item in section.get("items", []):
                link = f" [{item['label']}]({url(item['href'])})" if "href" in item else ""
                md.append(f"- **{item['title']}**：{item['body']}{link}")
                anchor = (
                    f'<a href="{esc(url(item["href"]))}">{esc(item["label"])} <span aria-hidden="true">↗</span></a>'
                    if "href" in item
                    else ""
                )
                blocks.append(
                    f'<article class="detail"><h3>{esc(item["title"])}</h3><p>{esc(item["body"])}</p>{anchor}</article>'
                )
            code = ""
            if section.get("code"):
                md.extend(["```bash\n" + section["code"] + "\n```"])
                code = f"<pre><code>{esc(section['code'])}</code></pre>"
            body.append(
                f'<section id="{section["id"]}-{lang}" class="chapter"><div class="chapter-title"><span class="eyebrow">{esc(section["kicker"])}</span><h2>{esc(section["title"])}</h2></div><div class="chapter-body">'
                + "".join(f"<p>{esc(p)}</p>" for p in section["paragraphs"])
                + code
                + f'<div class="details">{"".join(blocks)}</div></div></section>'
            )
        metrics_html = "".join(
            f'<a class="metric" href="{esc(url(path))}"><strong>{esc(value)}</strong><span>{esc(label)}</span></a>'
            for value, label, path in metrics
        )
        pages.append(
            f'<div data-language="{lang}" {"hidden" if lang == "en" else ""}><header class="hero"><div class="hero-copy"><span class="eyebrow">EMBODIED DATA / DECISION WORKBENCH · V{version}</span><h1>{esc(text["tagline"])}</h1><p class="lede">{esc(text["description"])}</p><div class="actions"><a class="primary" href="#demo">{esc(text["video_label"])} <span aria-hidden="true">↘</span></a><a class="secondary" href="#engineering-{lang}">{esc(text["code_label"])} ↗</a></div><p class="reading-path">{esc(text["path_label"])}</p><p class="reading-path"><a href="https://codespaces.new/laizhiyin/RoboDataOps?quickstart=1">{"启动完整工作台 / Codespaces ↗" if lang == "zh" else "Launch full workbench / Codespaces ↗"}</a></p></div><figure class="product-shot"><img src="assets/overview.png" alt="RoboDataOps workbench: task coverage and acceptance states" width="1440" height="1100"><figcaption>ACTUAL WORKBENCH / SYNTHETIC FAULT DEMONSTRATION</figcaption></figure></header><div class="metrics">{metrics_html}</div>{"".join(body)}<div class="footer-note">AI-assisted project · MIT code · separately attributed public simulation data · v{version}</div></div>'
        )
        md.extend(
            [
                "## " + ("静态预算教学案例" if lang == "zh" else "Static budget teaching case"),
                "以下结果由同一 Python 规划模块预计算；成本与权重均为模拟。网页切换预算不会调用实时后端。"
                if lang == "zh"
                else "Precomputed by the same Python planning module. Costs and weights are simulated; changing the web budget does not call a live backend.",
                "| Budget / 元 | Equal loss | Greedy loss | Optimal loss |",
                "|---:|---:|---:|---:|",
            ]
        )
        table = [md.pop(), md.pop()]
        table.reverse()
        for scenario in evidence["scenarios"]:
            table.append(
                f"| {scenario['budget_cents'] / 100:g} | "
                + " | ".join(f"{p['residual_loss']:.3f}" for p in scenario["plans"])
                + " |"
            )
        md.append("\n".join(table))
        outputs[ROOT / ("README.md" if lang == "zh" else "README.en.md")] = "\n\n".join(md) + "\n"
    template = (ROOT / "portfolio/template.html").read_text()
    outputs[ROOT / "site/index.html"] = (
        template.replace("__PAGES__", "\n".join(pages))
        .replace(
            "__SCENARIOS__",
            json.dumps(evidence["scenarios"], ensure_ascii=False).replace("<", "\\u003c"),
        )
        .replace("__VERSION__", version)
    )
    for asset in ("style.css", "app.js"):
        outputs[ROOT / "site/assets" / asset] = (ROOT / "portfolio" / asset).read_text()
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build_outputs()
    if args.check:
        stale = [
            str(path.relative_to(ROOT))
            for path, text in outputs.items()
            if not path.exists() or path.read_text() != text
        ]
        if stale:
            raise SystemExit("Generated content is stale: " + ", ".join(stale))
        print("HTML and both README files match their shared content and reports.")
        return
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for image in ("overview.png", "video-poster.jpg"):
        source = ROOT / "docs/images" / image
        if source.exists():
            shutil.copyfile(source, ROOT / "site/assets" / image)
    print("Built site/index.html, README.md and README.en.md from portfolio/content.json")


if __name__ == "__main__":
    main()
