from __future__ import annotations

from pathlib import Path

from ..base import VoiceEngine
from ..ffmpeg_tools import run_ffmpeg

WORDS_PER_SECOND = 2.6
MIN_SECONDS = 1.5


def estimate_speech_duration(text: str) -> float:
    words = len(text.split())
    return max(MIN_SECONDS, round(words / WORDS_PER_SECOND, 2))


class SilentVoiceEngine(VoiceEngine):
    """Generates correctly-timed silence so audio-first timing works offline."""

    name = "silent"

    def synthesize(self, text: str, voice_name: str | None, out_path: Path) -> dict:
        del voice_name
        duration = estimate_speech_duration(text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        run_ffmpeg(
            [
                "-f", "lavfi",
                "-i", f"anullsrc=r=48000:cl=stereo",
                "-t", f"{duration:.3f}",
                "-c:a", "pcm_s16le",
                str(out_path),
            ]
        )
        return {"provider": self.name, "model": "silence", "duration": duration, "path": str(out_path)}
