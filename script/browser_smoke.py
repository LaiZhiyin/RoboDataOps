"""Optional real-browser QA. Run with Python + Playwright and installed Chromium."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
output = root / "docs/images"
output.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.get_by_role("heading", name="从轨迹证据，到采集决策。", exact=True).wait_for(timeout=40000)
    page.get_by_text("数据来源与统计口径", exact=True).wait_for()
    page.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden")
    page.get_by_test_id("stVegaLiteChart").locator("canvas, svg").first.wait_for(state="visible")
    page.screenshot(path=str(output / "overview.png"), full_page=True)
    page.get_by_text("问题复核", exact=True).click()
    page.get_by_role("button", name="保存复核决定", exact=True).wait_for()
    page.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden")
    page.screenshot(path=str(output / "review.png"), full_page=True)
    page.get_by_text("补采规划", exact=True).click()
    page.get_by_role("button", name="生成并保存方案", exact=True).click()
    page.get_by_text("同一预算下的方案比较", exact=True).wait_for()
    page.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden")
    page.screenshot(path=str(output / "planning.png"), full_page=True)
    page.get_by_text("同一预算下的方案比较", exact=True).evaluate("""el => {
        el.scrollIntoView({block: 'start'});
        const main = el.closest('[data-testid="stMain"]');
        if (main) main.scrollTop -= 80;
    }""")
    page.screenshot(path=str(output / "planning-results.png"), full_page=True)
    page.get_by_text("数据概览", exact=True).click()
    page.get_by_test_id("stSidebar").get_by_role("combobox").first.click()
    page.get_by_role("option", name="LIBERO 公开样本", exact=True).click()
    page.get_by_text("公开仿真示教 · 原始样本", exact=True).wait_for()
    page.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden")
    page.screenshot(path=str(output / "public-sample.png"), full_page=True)
    mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    mobile.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    mobile.get_by_role("heading", name="从轨迹证据，到采集决策。", exact=True).wait_for(
        timeout=40000
    )
    mobile.get_by_text("数据来源与统计口径", exact=True).wait_for()
    mobile.get_by_role("button", name="Stop", exact=True).wait_for(state="hidden")
    mobile.screenshot(path=str(output / "mobile.png"), full_page=True)
    overflow = mobile.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    assert not overflow, "Mobile layout overflows viewport"
    assert not errors, errors
    summary = {
        "desktop_pages": ["overview", "review", "planning", "public-sample"],
        "mobile_width": 390,
        "horizontal_overflow": overflow,
        "page_errors": errors,
        "note": "Actual browser smoke; no real user study or policy evaluation.",
    }
    (root / "reports/browser-smoke.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary))
    browser.close()
