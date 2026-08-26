from __future__ import annotations

import re
import subprocess

from ..engines.ffmpeg_tools import FFmpegError


def detect_black_frames(path: str, min_duration: float = 0.5) -> list[dict]:
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", path,
            "-vf", f"blackdetect=d={min_duration}:pix_th=0.10",
            "-an", "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=600,
    )
    events = []
    for line in (proc.stderr or "").splitlines():
        m = re.search(r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", line)
        if m:
            events.append(
                {"start": float(m.group(1)), "end": float(m.group(2)), "duration": float(m.group(3))}
            )
    return events


def detect_freeze(path: str, min_duration: float = 2.5) -> list[dict]:
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-i", path,
                "-vf", f"freezedetect=n=0.001:d={min_duration}",
                "-an", "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=600,
        )
    except FFmpegError:
        return []
    events = []
    for line in (proc.stderr or "").splitlines():
        if "freeze_start" in line:
            events.append({"type": "start"})
        elif "freeze_duration" in line:
            m = re.search(r"freeze_duration:([\d.]+)", line)
            if m:
                events.append({"type": "end", "duration": float(m.group(1))})
    return events


def visual_check(path: str, allow_static: bool = False) -> tuple[bool, dict]:
    details: dict = {"path": path}
    black = detect_black_frames(path)
    details["black_frames"] = black
    failures = []
    if black:
        failures.append(f"{len(black)} black frame event(s)")
    if not allow_static:
        freezes = [f for f in detect_freeze(path) if f.get("type") == "end" and f.get("duration", 0) > 3.0]
        details["freezes"] = freezes
        if freezes:
            failures.append("static frozen footage detected")
    if failures:
        details["failed"] = failures
    return len(failures) == 0, details


IDENTITY_CHECKLIST = [
    "character identity matches Character Bible",
    "face proportions stable",
    "clothing unchanged",
    "colors match palette",
    "hands correct",
    "objects consistent",
    "background consistent",
    "composition matches storyboard",
    "safety: age-appropriate",
]


def identity_review_stub(path: str) -> tuple[bool, dict]:
    """Placeholder for VLM-based identity QC; flags for human review in production mode."""
    return True, {"path": path, "checklist": IDENTITY_CHECKLIST, "mode": "manual_review_pending"}
