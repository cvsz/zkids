from __future__ import annotations

from pathlib import Path

from ..engines.ffmpeg_tools import probe_video


def check_video_file(path: Path, expect_width: int | None, expect_height: int | None,
                     expect_fps: float | None, expect_duration: float | None,
                     tolerance: float = 0.6) -> tuple[bool, dict]:
    details: dict = {"path": str(path)}
    checks: dict[str, bool] = {}

    checks["exists"] = path.exists()
    if not checks["exists"]:
        return False, {**details, "failed": ["exists"]}

    info = probe_video(path)
    details["probe"] = info
    failures = []

    if info["duration"] <= 0:
        failures.append("positive_duration")
    elif expect_duration is not None and abs(info["duration"] - expect_duration) > tolerance:
        failures.append(f"duration {info['duration']:.2f} != {expect_duration:.2f}")

    if expect_width and expect_height:
        if (info["width"], info["height"]) != (expect_width, expect_height):
            failures.append(f"resolution {info['width']}x{info['height']} != {expect_width}x{expect_height}")

    if expect_fps and info["fps"]:
        if abs(info["fps"] - expect_fps) > 1.0:
            failures.append(f"fps {info['fps']} != {expect_fps}")
    if expect_fps and not info["fps"]:
        failures.append("missing fps")

    if info["pixel_format"] != "yuv420p":
        failures.append(f"pixel_format {info['pixel_format']}")

    details["checks"] = checks
    passed = len(failures) == 0
    if failures:
        details["failed"] = failures
    return passed, details


def check_audio_file(path: Path, expect_sample_rate: int = 48000, expect_channels: int = 2) -> tuple[bool, dict]:
    details: dict = {"path": str(path)}
    if not path.exists():
        return False, {**details, "failed": ["exists"]}
    info = probe_video(path)
    details["probe"] = info
    failures = []
    if info["duration"] <= 0:
        failures.append("positive_duration")
    if info["sample_rate"] != expect_sample_rate:
        failures.append(f"sample_rate {info['sample_rate']} != {expect_sample_rate}")
    if info["channels"] != expect_channels:
        failures.append(f"channels {info['channels']} != {expect_channels}")
    if failures:
        details["failed"] = failures
    return len(failures) == 0, details
