from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def run_ffmpeg(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-2000:]}")
    return proc


def run_ffprobe(path: Path | str) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {proc.stderr[-1000:]}")
    return json.loads(proc.stdout or "{}")


@lru_cache(maxsize=1)
def has_filter(filter_name: str) -> bool:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return f" {filter_name} " in proc.stdout


def probe_video(path: Path | str) -> dict:
    info = run_ffprobe(path)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    def _num(s, k):
        v = (s or {}).get(k)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    fps = None
    if video:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if rate and "/" in rate:
            num, den = rate.split("/")
            try:
                if float(den):
                    fps = float(num) / float(den)
            except (ValueError, ZeroDivisionError):
                fps = None
    return {
        "duration": float(fmt.get("duration") or 0.0),
        "width": int(video["width"]) if video else None,
        "height": int(video["height"]) if video else None,
        "fps": round(fps, 3) if fps else None,
        "video_codec": video.get("codec_name") if video else None,
        "pixel_format": video.get("pix_fmt") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        "channels": int(audio["channels"]) if audio and audio.get("channels") else None,
        "size_bytes": int(fmt.get("size") or 0),
    }
