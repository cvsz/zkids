from __future__ import annotations

import os
import struct
import wave
from pathlib import Path

from ..base import EngineNotConfigured, VoiceEngine
from .silent import estimate_speech_duration


class GoogleTTSEngine(VoiceEngine):
    name = "google_tts"

    MODEL_DEFAULT = "gemini-2.5-flash-preview-tts"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ZKID_GOOGLE_API_KEY") or ""
        self.model = model or os.environ.get("ZKID_TTS_MODEL") or self.MODEL_DEFAULT
        if not self.api_key:
            raise EngineNotConfigured("google_tts requires ZKID_GOOGLE_API_KEY; install zkid[google]")

    def synthesize(self, text: str, voice_name: str | None, out_path: Path) -> dict:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name or "Kore")
                )
            ),
        )
        response = client.models.generate_content(model=self.model, contents=text, config=config)
        pcm = response.candidates[0].content.parts[0].inline_data.data
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_pcm_wav(pcm, out_path, sample_rate=24000)
        return {
            "provider": self.name,
            "model": self.model,
            "duration": len(pcm) / (24000 * 2),
            "path": str(out_path),
        }


def _write_pcm_wav(pcm: bytes, path: Path, sample_rate: int = 24000, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


__all__ = ["GoogleTTSEngine", "estimate_speech_duration"]
