"""Actual browser acceptance, optional dependency: Playwright with Chromium."""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from robodataops.i18n import set_language, tr  # noqa: E402

BASE = os.environ.get("ROBODATAOPS_QA_URL", "http://127.0.0.1:8503")


def ready(page):
    page.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden", timeout=40000)
    assert page.get_by_test_id("stException").count() == 0


def select_source(page, name):
    page.get_by_test_id("stSidebar").get_by_role("combobox").nth(1).click()
    page.get_by_role("option", name=tr(name), exact=True).click()
    ready(page)


def main():
    set_language("en")
    output = ROOT / "docs/images"
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(BASE)
        page.get_by_role("heading", name=tr("从轨迹证据，到采集决策。"), exact=True).wait_for(
            timeout=40000
        )
        ready(page)
        page.get_by_test_id("stVegaLiteChart").locator("canvas,svg").first.wait_for()
        page.screenshot(path=str(output / "overview.png"), full_page=True)
        page.get_by_text(tr("问题复核"), exact=True).click()
        page.get_by_role("button", name=tr("保存复核决定"), exact=True).wait_for()
        ready(page)
        assert "Json Parse Error" not in page.locator("body").inner_text()
        page.screenshot(path=str(output / "review.png"), full_page=True)
        page.get_by_text(tr("补采规划"), exact=True).click()
        page.get_by_role("button", name=tr("生成并保存方案"), exact=True).click()
        page.get_by_text(tr("同一预算下的方案比较"), exact=True).wait_for()
        ready(page)
        page.screenshot(path=str(output / "planning.png"), full_page=True)
        page.get_by_text(tr("同一预算下的方案比较"), exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "planning-results.png"))
        page.get_by_text(tr("保存、载入或导入情景"), exact=True).click()
        page.get_by_text(tr("情景版本、反事实与成品率敏感性"), exact=True).click()
        page.get_by_role("button", name=tr("保存当前情景"), exact=True).click()
        ready(page)
        page.get_by_text(tr("数据概览"), exact=True).click()
        select_source(page, tr("LIBERO 公开样本"))
        page.get_by_text(tr("公开仿真示教 · 原始样本"), exact=True).wait_for()
        page.screenshot(path=str(output / "public-sample.png"), full_page=True)
        page.get_by_text(tr("问题复核"), exact=True).click()
        page.get_by_text(tr("轨迹视频与动作联动"), exact=True).click()
        frame = page.frame_locator("iframe").first
        frame.locator("#video").wait_for(timeout=30000)
        frame.locator("#video").evaluate(
            "v => new Promise(resolve => {if(v.readyState>=1) resolve(); else v.onloadedmetadata=resolve;})"
        )
        frame.locator("#frame").fill("20")
        frame.locator("#frame").dispatch_event("input")
        time = frame.locator("#video").evaluate("v=>v.currentTime")
        assert abs(time - 2.0) < 0.15, time
        assert "Frame 20" in frame.locator("#position").inner_text()
        page.get_by_text(tr("轨迹视频与动作联动"), exact=True).scroll_into_view_if_needed()
        page.screenshot(path=str(output / "video-evidence.png"))
        page.get_by_text(tr("累计快照"), exact=True).click()
        page.get_by_role("button", name=tr("生成累计分析快照"), exact=True).click()
        page.get_by_role("button", name=tr("切换到累计快照"), exact=True).wait_for(timeout=40000)
        ready(page)
        assert not page.get_by_test_id("stAlert").filter(has_text=tr("冲突")).count()
        page.screenshot(path=str(output / "cumulative.png"), full_page=True)
        page.get_by_role("button", name=tr("切换到累计快照"), exact=True).click()
        ready(page)
        page.get_by_text(tr("数据概览"), exact=True).click()
        ready(page)
        expect(page.get_by_test_id("stMetricValue").first).to_have_text("120", timeout=30000)
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto(BASE)
        mobile.get_by_role("heading", name=tr("从轨迹证据，到采集决策。"), exact=True).wait_for(
            timeout=40000
        )
        ready(mobile)
        overflow = mobile.evaluate("document.documentElement.scrollWidth>innerWidth+1")
        assert not overflow
        mobile.screenshot(path=str(output / "mobile.png"), full_page=True)
        assert not errors, errors
        summary = {
            "release": json.loads((ROOT / "portfolio/content.json").read_text())["version"],
            "desktop_pages": [
                "overview",
                "review",
                "planning",
                "public-sample",
                "scenario-save",
                "video-frame-seek",
                "cumulative-120",
            ],
            "mobile_width": 390,
            "horizontal_overflow": overflow,
            "video_frame_20_seconds": time,
            "page_errors": errors,
            "notice": "Real isolated browser session. No real user study or policy evaluation.",
        }
        (ROOT / "reports/browser-smoke.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2)
        )
        print(json.dumps(summary))
        browser.close()


if __name__ == "__main__":
    main()
