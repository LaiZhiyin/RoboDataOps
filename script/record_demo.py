"""Record a real 90-second browser walkthrough with burned-in bilingual captions."""

import json
import os
import subprocess
import time
from pathlib import Path

from browser_v1 import ready, select_source
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("ROBODATAOPS_QA_URL", "http://127.0.0.1:8503")
SCENES = [
    (
        0,
        10,
        "收到示教数据后：哪些计入，哪些任务仍有缺口？",
        "After data delivery: what counts, and where are the remaining gaps?",
    ),
    (
        10,
        25,
        "定位 EP 7 的 NaN：字段、原始行和规则证据一起查看。",
        "Inspect EP 7: a NaN, its original rows and the explicit rule evidence.",
    ),
    (
        25,
        40,
        "低运动不等于无用。驳回 EP 64 信号后，覆盖按新结论重算。",
        "Low motion is not automatically useless. Dismiss with a reason; coverage updates.",
    ),
    (
        40,
        60,
        "同一预算比较三种方案。调整预算，保留旧方案与完整约束。",
        "Compare three strategies under one budget. Replan without rewriting history.",
    ),
    (
        60,
        75,
        "公开 LIBERO 仿真片段：按 metadata 定位，视频与动作游标联动。",
        "Public LIBERO simulation: metadata-based video seeking and action/state cursors.",
    ),
    (
        75,
        85,
        "同源保留池模拟到货：去重后 100 → 120 条，保留父版本。",
        "Reserved public data simulates delivery: deduplicate, keep lineage, 100 → 120 episodes.",
    ),
    (
        85,
        90,
        "代码、测试与证据可追溯。AI 辅助开发；真人与策略收益仍待验证。",
        "Inspect code, tests and evidence. AI-assisted; user and policy benefits remain unverified.",
    ),
]


def overlay(page, scene):
    page.evaluate(
        """({zh,en}) => {
      let box=document.getElementById('demo-captions');
      if(!box){box=document.createElement('aside');box.id='demo-captions';
        Object.assign(box.style,{position:'fixed',bottom:'16px',left:'320px',right:'24px',zIndex:'999999',padding:'16px 22px',background:'rgba(17,47,49,.96)',color:'#f5f5ee',border:'1px solid #75988a',borderRadius:'5px',boxShadow:'0 6px 25px #0002',fontFamily:'Avenir Next,PingFang SC,sans-serif',pointerEvents:'none'});document.body.appendChild(box);}
      box.replaceChildren();
      const label=document.createElement('div');label.textContent='DEMO CAPTIONS · v1.0.0 · SYNTHETIC INPUTS / PUBLIC SIMULATION';Object.assign(label.style,{fontSize:'9px',letterSpacing:'1px',color:'#adcdbd',marginBottom:'5px'});
      const a=document.createElement('div');a.textContent=zh;a.style.fontSize='17px';
      const b=document.createElement('div');b.textContent=en;Object.assign(b.style,{fontSize:'12px',color:'#c9dfd2',marginTop:'4px'});box.append(label,a,b);
    }""",
        {"zh": scene[2], "en": scene[3]},
    )


def main():
    raw = ROOT / "artifacts/recording"
    raw.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1080},
            record_video_dir=raw,
            record_video_size={"width": 1440, "height": 1080},
            reduced_motion="reduce",
        )
        created = time.monotonic()
        page = context.new_page()
        page.goto(BASE)
        page.get_by_role("heading", name="从轨迹证据，到采集决策。", exact=True).wait_for(
            timeout=40000
        )
        ready(page)
        started = time.monotonic()
        lead = started - created

        def hold(end):
            remaining = started + end - time.monotonic()
            if remaining > 0:
                page.wait_for_timeout(remaining * 1000)

        for number, scene in enumerate(SCENES):
            if number == 1:
                page.get_by_text("问题复核", exact=True).click()
                page.get_by_role("button", name="保存复核决定", exact=True).wait_for()
                ready(page)
                page.wait_for_timeout(400)
                page.get_by_test_id("stSelectbox").filter(has_text="选择问题").get_by_role(
                    "combobox"
                ).click()
                page.get_by_role(
                    "option", name="EP 0007 · D003 · 非有限或非数值数据", exact=True
                ).click()
                ready(page)
            elif number == 2:
                page.get_by_test_id("stSelectbox").filter(has_text="选择问题").get_by_role(
                    "combobox"
                ).click()
                page.get_by_role(
                    "option", name="EP 0064 · R002 · 动作变化较低，需要复核", exact=True
                ).click()
                ready(page)
                page.get_by_text("驳回标记，保留数据", exact=True).click()
                page.get_by_role("textbox", name="复核理由", exact=True).fill(
                    "当前用途允许等待动作；仅低运动信号不足以排除该轨迹。"
                )
                page.get_by_role("button", name="保存复核决定", exact=True).click()
                ready(page)
                page.get_by_text("数据概览", exact=True).click()
                ready(page)
            elif number == 3:
                page.get_by_text("补采规划", exact=True).click()
                page.get_by_role("button", name="生成并保存方案", exact=True).click()
                page.get_by_text("同一预算下的方案比较", exact=True).wait_for()
                ready(page)
                page.get_by_text("同一预算下的方案比较", exact=True).evaluate(
                    "el=>el.scrollIntoView({block:'start'})"
                )
            elif number == 4:
                select_source(page, "LIBERO 公开样本")
                page.get_by_text("问题复核", exact=True).click()
                page.get_by_text("轨迹视频与动作联动", exact=True).click()
                frame = page.frame_locator("iframe").first
                frame.locator("#video").wait_for()
                page.wait_for_timeout(600)
                page.locator("iframe").first.evaluate(
                    "e=>e.scrollIntoView({block:'center',behavior:'instant'})"
                )
                frame.locator("#video").evaluate("v => {v.muted=true;v.play();}")
            elif number == 5:
                page.get_by_text("累计快照", exact=True).click()
                page.get_by_role("button", name="生成累计分析快照", exact=True).click()
                page.get_by_role("button", name="切换到累计快照", exact=True).wait_for(
                    timeout=30000
                )
                ready(page)
            elif number == 6:
                page.goto("http://127.0.0.1:8765/#engineering-zh")
                page.locator("#engineering-zh").scroll_into_view_if_needed()
            overlay(page, scene)
            print(f"Recording scene {number + 1}/7", flush=True)
            if number == 3:
                hold(50)
                page.get_by_role("spinbutton", name="总预算 / 元", exact=True).fill("500")
                page.get_by_role("spinbutton", name="总预算 / 元", exact=True).press("Enter")
                page.get_by_role("button", name="生成并保存方案", exact=True).click()
                ready(page)
                page.get_by_text("同一预算下的方案比较", exact=True).evaluate(
                    "el=>el.scrollIntoView({block:'start'})"
                )
                overlay(page, scene)
            hold(scene[1])
        video_path = page.video.path()
        context.close()
        browser.close()
    output = ROOT / "site/assets/robodataops-demo.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            str(lead),
            "-i",
            str(video_path),
            "-t",
            "90",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            "2",
            "-i",
            str(output),
            "-frames:v",
            "1",
            str(ROOT / "docs/images/video-poster.jpg"),
        ],
        check=True,
    )
    for lang, index in (("zh", 2), ("en", 3)):

        def stamp(seconds):
            return f"00:{seconds // 60:02d}:{seconds % 60:02d}.000"

        cues = [f"{stamp(s[0])} --> {stamp(s[1])}\n{s[index]}" for s in SCENES]
        (ROOT / f"site/assets/captions-{lang}.vtt").write_text(
            "WEBVTT\n\n" + "\n\n".join(cues) + "\n", encoding="utf-8"
        )
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        check=True,
    )
    report = {
        "release": "1.0.0",
        "method": "Actual Playwright browser recording with clearly marked bilingual demo captions; no fabricated app results",
        "media": json.loads(probe.stdout),
        "scenes": SCENES,
        "notice": "Silent walkthrough. Synthetic faults, hypothetical budgets and public simulation clips. No real user efficiency or policy claim.",
    }
    (ROOT / "reports/video.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
