"""Record each language's actual UI, captions, play thumbnail and English narration."""

import argparse
import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from browser_v1 import ready, select_source
from demo_scenes import SCENES
from playwright.sync_api import sync_playwright

from robodataops.i18n import set_language, tr

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("ROBODATAOPS_QA_URL", "http://127.0.0.1:8503")
VERSION = json.loads((ROOT / "portfolio/content.json").read_text())["version"]


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size:stream=codec_type",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def overlay(page, scene, language):
    page.evaluate(
        """({caption,version})=>{
      let box=document.getElementById('demo-captions');
      if(!box){box=document.createElement('aside');box.id='demo-captions';Object.assign(box.style,{position:'fixed',bottom:'16px',left:'320px',right:'24px',zIndex:'999999',padding:'16px 22px',background:'rgba(17,47,49,.96)',color:'#f5f5ee',border:'1px solid #75988a',borderRadius:'5px',fontFamily:'Avenir Next,PingFang SC,sans-serif',pointerEvents:'none'});document.body.appendChild(box);}
      box.replaceChildren();const label=document.createElement('div');label.textContent=`DEMO · v${version} · SYNTHETIC INPUTS / PUBLIC SIMULATION`;Object.assign(label.style,{fontSize:'10px',color:'#adcdbd',marginBottom:'6px'});
      const text=document.createElement('div');text.textContent=caption;text.style.fontSize='18px';box.append(label,text);
    }""",
        {"caption": scene[3 if language == "en" else 2], "version": VERSION},
    )


def english_narration(silent, destination, directory):
    """Use an installed system TTS voice; no fabricated human speaker identity."""
    audio = []
    for index, scene in enumerate(SCENES):
        text_path, clip = directory / f"voice-{index}.txt", directory / f"voice-{index}.aiff"
        text_path.write_text(
            scene[3].replace("→", "to").replace("EP ", "episode "), encoding="utf-8"
        )
        subprocess.run(
            ["say", "-v", "Daniel", "-r", "160", "-f", str(text_path), "-o", str(clip)], check=True
        )
        duration = float(probe(clip)["format"]["duration"])
        speed = max(1, duration / (scene[1] - scene[0] - 0.4))
        audio.append((clip, scene[0], speed))
        print(f"English narration {index + 1}/7", flush=True)
    command = ["ffmpeg", "-v", "error", "-y", "-i", str(silent)]
    filters = []
    for index, (clip, start, speed) in enumerate(audio, 1):
        command += ["-i", str(clip)]
        filters.append(f"[{index}:a]atempo={speed},adelay={start * 1000}:all=1[a{index}]")
    filters.append(
        "".join(f"[a{i}]" for i in range(1, 8))
        + "amix=inputs=7:duration=longest:normalize=0,apad=whole_dur=90,alimiter=limit=0.95[voice]"
    )
    command += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v",
        "-map",
        "[voice]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-t",
        "90",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)


def play_thumbnail(language, screenshot):
    image = base64.b64encode(screenshot.read_bytes()).decode()
    heading = (
        "CLICK TO PLAY · ENGLISH PRODUCT DEMO" if language == "en" else "点击播放 · 中文产品讲解"
    )
    detail = (
        "90 seconds · English interface, captions and narration"
        if language == "en"
        else "约90秒 · 中文界面与字幕 · 真实操作演示"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1)
        page.set_content(
            f'<html><style>*{{box-sizing:border-box}}body{{margin:0;background:#173d3c;font-family:"Avenir Next","PingFang SC",sans-serif}}img{{width:100%;height:675px;object-fit:cover;object-position:top;opacity:.68}}.play{{position:absolute;top:230px;left:535px;width:130px;height:130px;border-radius:50%;background:#fff9;display:grid;place-items:center;color:#173d3c;font-size:70px;padding-left:12px;box-shadow:0 0 0 8px #fff4}}.banner{{position:absolute;bottom:0;width:100%;padding:28px 42px;background:#173d3c;color:#fff}}h1{{font-size:30px;margin:0 0 8px}}p{{font-size:18px;margin:0;color:#cce7d6}}</style><img src="data:image/png;base64,{image}" alt="Actual workbench"><div class="play">▶</div><div class="banner"><h1>{heading}</h1><p>{detail}</p></div></html>'
        )
        page.screenshot(path=str(ROOT / f"site/assets/video-preview-{language}.png"))
        browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "zh"], default="en")
    language = parser.parse_args().lang
    set_language(language)
    raw = ROOT / "artifacts/recording" / language
    raw.mkdir(parents=True, exist_ok=True)
    screenshot = ROOT / f"docs/images/overview-{language}.png"
    errors = []
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
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE)
        page.get_by_role(
            "heading", name="From trajectory evidence to collection decisions.", exact=True
        ).wait_for(timeout=40000)
        if language == "zh":
            page.get_by_test_id("stSidebar").get_by_role("combobox").first.click()
            page.get_by_role("option", name="中文", exact=True).click()
            page.get_by_role("heading", name=tr("从轨迹证据，到采集决策。"), exact=True).wait_for()
        ready(page)
        page.wait_for_timeout(500)
        page.screenshot(path=str(screenshot), full_page=True)
        started = time.monotonic()
        lead = started - created

        def hold(end):
            remaining = started + end - time.monotonic()
            if remaining > 0:
                page.wait_for_timeout(remaining * 1000)

        for number, scene in enumerate(SCENES):
            if number in {1, 2}:
                if number == 1:
                    page.get_by_text(tr("问题复核"), exact=True).click()
                    page.get_by_role("button", name=tr("保存复核决定"), exact=True).wait_for()
                    ready(page)
                    page.wait_for_timeout(400)
                page.get_by_test_id("stSelectbox").filter(has_text=tr("选择问题")).get_by_role(
                    "combobox"
                ).click()
                label = (
                    f"EP 0007 · D003 · {tr('非有限或非数值数据')}"
                    if number == 1
                    else f"EP 0064 · R002 · {tr('动作变化较低，需要复核')}"
                )
                page.get_by_role("option", name=label, exact=True).click()
                ready(page)
                if number == 2:
                    page.get_by_text(tr("驳回标记，保留数据"), exact=True).click()
                    page.get_by_role("textbox", name=tr("复核理由"), exact=True).fill(
                        "Waiting is allowed for this use; low motion alone does not justify exclusion."
                        if language == "en"
                        else "当前用途允许等待动作；仅低运动信号不足以排除该轨迹。"
                    )
                    page.get_by_role("button", name=tr("保存复核决定"), exact=True).click()
                    ready(page)
                    page.get_by_text(tr("数据概览"), exact=True).click()
                    ready(page)
            elif number == 3:
                page.get_by_text(tr("补采规划"), exact=True).click()
                page.get_by_role("button", name=tr("生成并保存方案"), exact=True).click()
                page.get_by_text(tr("同一预算下的方案比较"), exact=True).wait_for()
                ready(page)
                page.get_by_text(tr("同一预算下的方案比较"), exact=True).evaluate(
                    "el=>el.scrollIntoView({block:'start'})"
                )
            elif number == 4:
                select_source(page, "LIBERO 公开样本")
                page.get_by_text(tr("问题复核"), exact=True).click()
                page.get_by_text(tr("轨迹视频与动作联动"), exact=True).click()
                frame = page.frame_locator("iframe").first
                frame.locator("#video").wait_for()
                page.wait_for_timeout(700)
                page.locator("iframe").first.evaluate(
                    "e=>e.scrollIntoView({block:'center',behavior:'instant'})"
                )
                frame.locator("#video").evaluate("v=>{v.muted=true;v.play();}")
            elif number == 5:
                page.get_by_text(tr("累计快照"), exact=True).click()
                page.get_by_role("button", name=tr("生成累计分析快照"), exact=True).click()
                page.get_by_role("button", name=tr("切换到累计快照"), exact=True).wait_for(
                    timeout=30000
                )
                ready(page)
            elif number == 6:
                page.goto(f"http://127.0.0.1:8765/?lang={language}#engineering-{language}")
                page.locator(f"#engineering-{language}").scroll_into_view_if_needed()
            overlay(page, scene, language)
            print(f"Recording {language} scene {number + 1}/7", flush=True)
            if number == 3:
                hold(50)
                field = page.get_by_role("spinbutton", name=tr("总预算 / 元"), exact=True)
                field.fill("500")
                field.press("Enter")
                page.get_by_role("button", name=tr("生成并保存方案"), exact=True).click()
                ready(page)
                page.get_by_text(tr("同一预算下的方案比较"), exact=True).evaluate(
                    "el=>el.scrollIntoView({block:'start'})"
                )
                overlay(page, scene, language)
            hold(scene[1])
        video_path = page.video.path()
        context.close()
        browser.close()
    assert not errors, errors
    silent = raw / "silent.mp4"
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
            "-vf",
            "tpad=stop_mode=clone:stop_duration=1",
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
            str(silent),
        ],
        check=True,
    )
    destination = ROOT / f"site/assets/robodataops-demo-{language}.mp4"
    if language == "en":
        english_narration(silent, destination, raw)
    else:
        shutil.copyfile(silent, destination)

    def stamp(seconds):
        return f"00:{seconds // 60:02d}:{seconds % 60:02d}.000"

    cues = [f"{stamp(s[0])} --> {stamp(s[1])}\n{s[3 if language == 'en' else 2]}" for s in SCENES]
    (ROOT / f"site/assets/captions-{language}.vtt").write_text(
        "WEBVTT\n\n" + "\n\n".join(cues) + "\n", encoding="utf-8"
    )
    play_thumbnail(language, screenshot)
    report = {
        "release": VERSION,
        "language": language,
        "interface_language": language,
        "method": "Actual browser recording; narration captions are separate from app UI",
        "narration": "macOS Daniel system TTS, English"
        if language == "en"
        else "Chinese captions, no voiceover",
        "media": probe(destination),
        "scenes": SCENES,
        "page_errors": errors,
        "notice": "Synthetic faults, hypothetical budgets and public simulation. No human efficiency or policy benefits claimed.",
    }
    (ROOT / f"reports/video-{language}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
