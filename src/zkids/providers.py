"""Provider capability negotiation."""
from __future__ import annotations

from dataclasses import dataclass, field


class CapabilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    reference_images: bool = False
    first_last_frame: bool = False
    seed: bool = False
    audio: bool = False
    max_reference_images: int = 0
    durations_seconds: frozenset[int] = field(default_factory=frozenset)
    aspect_ratios: frozenset[str] = field(default_factory=lambda: frozenset({"16:9"}))
    resolutions: frozenset[str] = field(default_factory=lambda: frozenset({"720p"}))


@dataclass(frozen=True, slots=True)
class MotionRequirements:
    reference_images: int = 0
    needs_first_last_frame: bool = False
    needs_seed: bool = False
    needs_audio: bool = False
    duration_seconds: int = 8
    aspect_ratio: str = "16:9"
    resolution: str = "720p"


def require_capabilities(caps: ProviderCapabilities, req: MotionRequirements) -> None:
    failures: list[str] = []
    if req.reference_images and not caps.reference_images:
        failures.append("reference_images")
    if req.reference_images > caps.max_reference_images:
        failures.append("max_reference_images")
    if req.needs_first_last_frame and not caps.first_last_frame:
        failures.append("first_last_frame")
    if req.needs_seed and not caps.seed:
        failures.append("seed")
    if req.needs_audio and not caps.audio:
        failures.append("audio")
    if caps.durations_seconds and req.duration_seconds not in caps.durations_seconds:
        failures.append("duration_seconds")
    if req.aspect_ratio not in caps.aspect_ratios:
        failures.append("aspect_ratio")
    if req.resolution not in caps.resolutions:
        failures.append("resolution")
    if failures:
        raise CapabilityError("provider lacks required capabilities: " + ", ".join(failures))
