from __future__ import annotations

import json
import re
import subprocess


def measure_loudness(path: str) -> dict:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    err = proc.stderr or ""
    max_vol = _extract(err, "max_volume")
    mean_vol = _extract(err, "mean_volume")
    return {
        "path": path,
        "max_volume_db": max_vol,
        "mean_volume_db": mean_vol,
        "clipping": max_vol is not None and max_vol > -0.1,
        "silent": max_vol is not None and max_vol < -60.0,
    }


def _extract(text: str, key: str) -> float | None:
    m = re.search(rf"{key}:\s*(-?[\d.]+)\s*dB", text)
    return float(m.group(1)) if m else None


def audio_check(path: str, require_nonsilent: bool = True) -> tuple[bool, dict]:
    details = measure_loudness(path)
    failures = []
    if details["clipping"]:
        failures.append("clipping detected (max_volume near 0 dBFS)")
    if require_nonsilent and details["silent"]:
        failures.append("audio is silent")
    if failures:
        details["failed"] = failures
    return len(failures) == 0, details


__all__ = ["audio_check", "measure_loudness"]
