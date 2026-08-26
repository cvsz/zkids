from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class EngineNotConfigured(RuntimeError):
    pass


class EngineError(RuntimeError):
    pass


class LLMClient(ABC):
    name: str = "base"

    @abstractmethod
    def generate_json(self, system: str, user: str) -> dict:
        ...


class ImageEngine(ABC):
    name: str = "base"

    @abstractmethod
    def generate_still(self, prompt: str, negative: str, out_path: Path, seed: int | None = None,
                       context: dict | None = None) -> dict:
        ...


class VoiceEngine(ABC):
    name: str = "base"

    @abstractmethod
    def synthesize(self, text: str, voice_name: str | None, out_path: Path) -> dict:
        ...


class MusicEngine(ABC):
    name: str = "base"

    @abstractmethod
    def render_bed(self, cue_name: str, duration: float, out_path: Path) -> dict:
        ...


class MotionEngine(ABC):
    name: str = "base"

    @abstractmethod
    def generate_scene_video(
        self,
        still_path: Path,
        prompt: str,
        duration: float,
        out_path: Path,
        reference_images: list[Path] | None = None,
    ) -> dict:
        ...
