from __future__ import annotations

import asyncio
import os
from pathlib import Path

from ..base import EngineNotConfigured, VoiceEngine


VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "en-child": "en-US-AnaNeural",
    "en-gb": "en-GB-SoniaNeural",
    "th": "th-TH-PremwadeeNeural",
    "ja": "ja-JP-NanamiNeural",
}


class EdgeTTSEngine(VoiceEngine):
    """Free neural TTS via Microsoft Edge (edge-tts). No API key, 40+ languages, very natural."""

    name = "edge_tts"

    def __init__(self, voice: str | None = None, rate: str = "+0%", pitch: str = "+0Hz") -> None:
        self.voice = voice or os.environ.get("ZKID_EDGE_VOICE") or "en-US-AriaNeural"
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, text: str, voice_name: str | None, out_path: Path) -> dict:
        try:
            import edge_tts
        except ImportError as e:
            raise EngineNotConfigured("edge-tts not installed. Run: pip install edge-tts") from e
        voice = voice_name or self.voice
        # Map generic language codes
        voice = VOICE_MAP.get(voice, voice)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # edge-tts is async; run in new loop
        async def _run():
            communicate = edge_tts.Communicate(text, voice, rate=self.rate, pitch=self.pitch)
            await communicate.save(str(out_path))
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_run())
            loop.close()
        # Validate output
        if not out_path.exists() or out_path.stat().st_size < 1000:
            raise EngineNotConfigured(f"edge-tts produced empty audio for voice {voice}")
        # Convert mp3 (edge-tts default) to wav 48k stereo for pipeline uniformity
        # If output is mp3, transcode via ffmpeg to wav
        if out_path.suffix.lower() == ".mp3" or out_path.suffix.lower() not in (".wav",):
            wav_path = out_path.with_suffix(".wav")
            try:
                from ..ffmpeg_tools import run_ffmpeg
                run_ffmpeg(["-i", str(out_path), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(wav_path)])
                out_path.unlink(missing_ok=True)
                out_path = wav_path
            except Exception:
                pass
        # Probe duration
        try:
            from ..ffmpeg_tools import probe_video
            dur = probe_video(out_path).get("duration") or 0
        except Exception:
            dur = max(1.0, len(text.split()) * 0.38)
        return {"provider": self.name, "model": voice, "duration": float(dur), "path": str(out_path)}

    @staticmethod
    def list_voices():
        try:
            import edge_tts
            return asyncio.run(edge_tts.list_voices())
        except Exception:
            return []
