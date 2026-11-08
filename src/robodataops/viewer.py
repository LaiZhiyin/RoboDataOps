"""Local video/chart component with metadata-based frame seeking."""

import base64
from importlib.resources import files

from robodataops.i18n import get_language
from robodataops.media import VideoRef
from robodataops.models import canonical_json


def viewer_html(episode, ref: VideoRef) -> str:
    if ref.path.stat().st_size > 5_000_000:
        raise ValueError("联动预览仅接受5MB以下片段，请先提取轨迹区间")
    source = {
        "language": get_language(),
        "fps": ref.fps,
        "start": ref.start,
        "end": ref.end,
        "timestamps": [row.get("timestamp") for row in episode.rows],
        "states": [row.get("observation.state") for row in episode.rows],
        "actions": [row.get("action") for row in episode.rows],
    }
    template = files("robodataops").joinpath("web/video-viewer.html").read_text(encoding="utf-8")
    english = get_language() == "en"
    template = (
        template.replace("轨迹帧定位 / Frame", "Episode frame" if english else "轨迹帧定位")
        .replace(
            "播放与曲线游标按 metadata 映射；物理同步未经验证。",
            "Playback and chart cursors follow metadata. Physical synchronization is unverified."
            if english
            else "播放与曲线游标按 metadata 映射；物理同步未经验证。",
        )
        .replace('lang="zh-CN"', 'lang="en"' if english else 'lang="zh-CN"')
    )
    return template.replace("__VIDEO__", base64.b64encode(ref.path.read_bytes()).decode()).replace(
        "__DATA__", canonical_json(source).replace("<", "\\u003c")
    )
