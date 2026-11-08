"""Real static-page and long-trajectory rendering checks (optional Playwright)."""

import base64
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:8765/")
        assert page.locator("[data-language=zh]").is_visible()
        page.locator("#language").click()
        assert page.locator("[data-language=en]").is_visible()
        assert page.locator("html").get_attribute("lang") == "en"
        page.locator("#language").click()
        page.locator("#budget").select_option("3")
        assert "0.900" in page.locator("#scenario-results .optimal strong").inner_text()
        page.locator("#budget").select_option("0")
        assert "3.450" in page.locator("#scenario-results .optimal strong").inner_text()
        video = page.locator("#demo video")
        video.evaluate(
            "v=>new Promise((resolve,reject)=>{if(v.readyState>=1)resolve();else{v.onloadedmetadata=resolve;v.onerror=()=>reject(new Error('demo video unavailable'));}})"
        )
        duration = video.evaluate("v=>v.duration")
        assert 89 <= duration <= 91, duration
        page.screenshot(path=str(ROOT / "docs/images/case-study.png"))
        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        mobile.goto("http://127.0.0.1:8765/")
        assert not mobile.evaluate("document.documentElement.scrollWidth>innerWidth+1")
        mobile.screenshot(path=str(ROOT / "docs/images/case-mobile.png"), full_page=True)
        # Rendering counterexample only: 200 seconds × 50 FPS × 14 channels.
        template = (ROOT / "src/robodataops/web/video-viewer.html").read_text()
        data = {
            "fps": 50,
            "start": 0,
            "end": 200,
            "timestamps": [i / 50 for i in range(10000)],
            "states": [[0] * 14] * 10000,
            "actions": [[1] * 14] * 10000,
        }
        clip = base64.b64encode(
            (ROOT / "data/public_sample/evidence/episode-0047.mp4").read_bytes()
        ).decode()
        fixture = template.replace("__DATA__", json.dumps(data)).replace("__VIDEO__", clip)
        page.set_content(fixture)
        page.locator("#frame").fill("9999")
        page.locator("#frame").dispatch_event("input")
        assert "Frame 9999" in page.locator("#position").inner_text()
        assert not errors, errors
        report = {
            "release": "1.0.0",
            "desktop_width": 1440,
            "mobile_width": 390,
            "horizontal_overflow": False,
            "languages": ["zh", "en"],
            "budget_options_checked": [200, 800],
            "demo_duration_seconds": duration,
            "long_trajectory_render": {
                "frames": 10000,
                "channels": 14,
                "fixture": "synthetic browser rendering regression only",
            },
            "page_errors": errors,
        }
        (ROOT / "reports/portfolio-browser.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2)
        )
        print(json.dumps(report))
        browser.close()


if __name__ == "__main__":
    main()
