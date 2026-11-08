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
        assert page.locator("[data-language=en]").first.is_visible()
        page.locator("[data-language=en] .secondary").click()
        page.locator("#language").click()
        assert page.locator("[data-language=zh]").first.is_visible()
        page.go_back()
        page.wait_for_function("document.documentElement.lang==='en'")
        assert page.locator("[data-language=en]").first.is_visible()
        page.go_forward()
        page.wait_for_function("document.documentElement.lang==='zh-CN'")
        page.locator("#language").click()
        page.locator("#budget").select_option("3")
        assert "0.900" in page.locator("#scenario-results .optimal strong").inner_text()
        page.locator("#budget").select_option("0")
        assert "3.450" in page.locator("#scenario-results .optimal strong").inner_text()
        video = page.locator("#demo-en")
        video.evaluate(
            "v=>new Promise((resolve,reject)=>{if(v.readyState>=1)resolve();else{v.onloadedmetadata=resolve;v.onerror=()=>reject(new Error('demo video unavailable'));}})"
        )
        duration = video.evaluate("v=>v.duration")
        assert 89 <= duration <= 91, duration
        video.evaluate("async v=>{v.muted=true;await v.play()}")
        page.locator("#language").click()
        assert video.evaluate("v=>v.paused")
        assert page.locator("#demo-zh").is_visible()
        chinese = page.locator("#demo-zh")
        chinese.evaluate(
            "v=>new Promise(resolve=>{if(v.readyState>=1)resolve();else v.onloadedmetadata=resolve})"
        )
        assert 89 <= chinese.evaluate("v=>v.duration") <= 91
        page.goto("http://127.0.0.1:8765/?lang=zh#demo")
        assert page.locator("#demo-zh").is_visible()
        page.goto("http://127.0.0.1:8765/?lang=en#demo")
        assert page.locator("#demo-en").is_visible()
        page.goto("http://127.0.0.1:8765/")
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
        page.locator("#video").evaluate(
            "v=>new Promise(resolve=>{if(v.readyState>=1)resolve();else v.onloadedmetadata=resolve})"
        )
        # Seek within the short real clip; the 10,000-row fixture tests drawing,
        # not a claim that this source video contains 200 seconds of evidence.
        page.locator("#frame").fill("100")
        page.locator("#frame").dispatch_event("input")
        assert "Frame 100" in page.locator("#position").inner_text()
        assert not errors, errors
        report = {
            "release": json.loads((ROOT / "portfolio/content.json").read_text())["version"],
            "desktop_width": 1440,
            "mobile_width": 390,
            "horizontal_overflow": False,
            "languages": ["zh", "en"],
            "default_language": "en",
            "language_deep_links": True,
            "history_language_sync": True,
            "hidden_video_pauses": True,
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
