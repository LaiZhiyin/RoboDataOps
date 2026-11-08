"""Episode-local video evidence. Decode checks never certify physical synchronization."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from robodataops.errors import DataSourceError
from robodataops.ingest import file_sha256, safe_path


@dataclass(frozen=True)
class VideoRef:
    camera: str
    path: Path
    start: float
    end: float
    source_path: str
    source_start: float
    source_end: float
    fps: float = 10.0


def references(info, metadata, manifest, root: Path) -> list[VideoRef]:
    result = []
    cameras = [k for k, value in info["features"].items() if value.get("dtype") == "video"]
    for camera in cameras:
        prefix = f"videos/{camera}/"
        try:
            chunk, index = metadata[prefix + "chunk_index"], metadata[prefix + "file_index"]
            if type(chunk) is not int or type(index) is not int or min(chunk, index) < 0:
                raise ValueError("video indices")
            start, end = (
                float(metadata[prefix + "from_timestamp"]),
                float(metadata[prefix + "to_timestamp"]),
            )
            if (
                not all(math.isfinite(x) for x in (start, end))
                or not 0 <= start < end
                or end - start > 1800
            ):
                raise ValueError("video interval")
            relative = info["video_path"].format(
                video_key=camera, chunk_index=chunk, file_index=index
            )
            entry = manifest.get("video_evidence", {}).get(f"{metadata['episode_index']}/{camera}")
            path = safe_path(root, relative)
            playback_start, playback_end = start, end
            if entry:
                if (
                    entry["source_path"] != relative
                    or abs(entry["source_from_s"] - start) > 1e-5
                    or abs(entry["source_to_s"] - end) > 1e-5
                ):
                    raise ValueError("clip provenance differs from metadata")
                path = safe_path(root, entry["path"])
                playback_start, playback_end = 0.0, end - start
                if path.exists() and file_sha256(path) != entry["sha256"]:
                    raise DataSourceError("视频片段校验失败")
            result.append(
                VideoRef(
                    camera,
                    path,
                    playback_start,
                    playback_end,
                    relative,
                    start,
                    end,
                    float(info["fps"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSourceError(f"视频映射或片段来源不合法：{camera}") from exc
    return result


def ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise DataSourceError("未安装 FFmpeg；视频检查保持未完成，请按运行文档安装")
    return executable


def inspect(ref: VideoRef, *, full_decode: bool = False) -> dict:
    result = {
        "camera": ref.camera,
        "status": "not_fetched",
        "scope": "full_interval_decode" if full_decode else "sampled",
        "from_s": ref.start,
        "to_s": ref.end,
        "samples": 0,
        "black_signal": False,
        "freeze_signal": False,
        "physical_sync": "not_verified",
    }
    if not ref.path.exists():
        return result
    try:
        executable = ffmpeg()
    except DataSourceError:
        return {**result, "status": "decoder_unavailable"}
    probe = shutil.which("ffprobe")
    if not probe:
        return {**result, "status": "decoder_unavailable"}
    base = [
        executable,
        "-nostdin",
        "-v",
        "error",
        "-xerror",
        "-err_detect",
        "explode",
        "-ss",
        str(ref.start),
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(ref.path),
        "-t",
        str(ref.end - ref.start),
    ]
    try:
        probed = subprocess.run(
            [
                probe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(ref.path),
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        if probed.returncode:
            return {**result, "status": "decode_error"}
        try:
            duration = float(json.loads(probed.stdout)["format"]["duration"])
        except (ValueError, KeyError, TypeError):
            return {**result, "status": "decode_error"}
        if not math.isfinite(duration) or ref.end > duration + 1.1 / ref.fps:
            return {**result, "status": "interval_out_of_bounds"}
        if full_decode:
            decoded = subprocess.run(
                [*base, "-f", "null", "-"], capture_output=True, timeout=60, check=False
            )
            if decoded.returncode or decoded.stderr.strip():
                return {
                    **result,
                    "status": "decode_error",
                    "detail": decoded.stderr.decode(errors="replace")[-400:],
                }
        decoded = subprocess.run(
            [
                *base,
                "-vf",
                "fps=1,scale=64:64",
                "-frames:v",
                "12",
                "-pix_fmt",
                "rgb24",
                "-f",
                "rawvideo",
                "-",
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {**result, "status": "timeout"}
    if decoded.returncode or decoded.stderr.strip() or len(decoded.stdout) < 64 * 64 * 3:
        return {
            **result,
            "status": "decode_error",
            "detail": decoded.stderr.decode(errors="replace")[-400:],
        }
    frames = np.frombuffer(decoded.stdout, dtype=np.uint8).reshape(-1, 64, 64, 3).astype(float)
    black = bool(np.all(frames.mean(axis=(1, 2, 3)) < 3))
    frozen = len(frames) >= 3 and bool(np.max(np.abs(np.diff(frames, axis=0))) < 2)
    return {
        **result,
        "status": "decoded",
        "samples": len(frames),
        "black_signal": black,
        "freeze_signal": frozen,
    }


def extract_clip(ref: VideoRef, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg(),
        "-nostdin",
        "-v",
        "error",
        "-y",
        "-ss",
        str(ref.start),
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(ref.path),
        "-t",
        str(ref.end - ref.start),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True, capture_output=True, timeout=90)
    return {
        "source_path": ref.source_path,
        "source_from_s": ref.source_start,
        "source_to_s": ref.source_end,
        "sha256": file_sha256(destination),
        "transform": "FFmpeg H264 interval extraction; source metadata unchanged",
    }
