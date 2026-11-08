"""Local video/chart component with metadata-based frame seeking."""

import base64
from importlib.resources import files

from robodataops.media import VideoRef
from robodataops.models import canonical_json


def viewer_html(episode, ref: VideoRef) -> str:
    if ref.path.stat().st_size > 5_000_000:
        raise ValueError("联动预览仅接受5MB以下片段，请先提取轨迹区间")
    source = {
        "fps": ref.fps,
        "start": ref.start,
        "end": ref.end,
        "timestamps": [row.get("timestamp") for row in episode.rows],
        "states": [row.get("observation.state") for row in episode.rows],
        "actions": [row.get("action") for row in episode.rows],
    }
    template = files("robodataops").joinpath("web/video-viewer.html").read_text(encoding="utf-8")
    return template.replace("__VIDEO__", base64.b64encode(ref.path.read_bytes()).decode()).replace(
        "__DATA__", canonical_json(source).replace("<", "\\u003c")
    )
