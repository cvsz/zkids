"""Provider capability negotiation and production adapter boundaries."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


class CapabilityError(ValueError):
    pass


class ProviderError(RuntimeError):
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


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider: str
    model: str
    asset_uri: str
    cost_usd: float
    metadata: dict[str, Any]


class MediaProvider(Protocol):
    name: str

    def generate(self, request: dict[str, Any]) -> ProviderResult: ...


@dataclass(frozen=True, slots=True)
class HTTPProviderConfig:
    name: str
    endpoint: str
    model: str
    api_key_env: str
    timeout_seconds: float = 60.0
    estimated_cost_usd: float = 0.0


class JSONHTTPProvider:
    """Vendor-neutral production HTTP adapter with environment-only credentials."""

    name = "http"

    def __init__(self, config: HTTPProviderConfig) -> None:
        self.config = config
        self.name = config.name

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"model": self.config.model, **request}

    def parse_response(self, payload: dict[str, Any]) -> str:
        uri = payload.get("asset_uri") or payload.get("url")
        if not isinstance(uri, str) or not uri:
            raise ProviderError("provider response did not contain an asset URI")
        return uri

    def generate(self, request: dict[str, Any]) -> ProviderResult:
        api_key = os.getenv(self.config.api_key_env)
        if not api_key:
            raise ProviderError(f"missing provider credential: {self.config.api_key_env}")
        body = json.dumps(self.build_payload(request)).encode("utf-8")
        http_request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "zkids/0.2",
            },
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - trusted operator-configured endpoint
                http_request, timeout=self.config.timeout_seconds
            ) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ProviderError(f"provider request failed: {exc}") from exc
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ProviderError("provider response must be a JSON object")
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            asset_uri=self.parse_response(parsed),
            cost_usd=self.config.estimated_cost_usd,
            metadata={"response": parsed},
        )


class ImageProvider(JSONHTTPProvider):
    name = "image"

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "prompt": request["prompt"],
            "references": request.get("references", []),
            "size": request.get("size", "1920x1080"),
        }


class VoiceProvider(JSONHTTPProvider):
    name = "voice"

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "text": request["text"],
            "voice": request.get("voice", "default"),
            "language": request.get("language", "en"),
        }


class MotionProvider(JSONHTTPProvider):
    name = "motion"

    def build_payload(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "prompt": request["prompt"],
            "image_uri": request.get("image_uri"),
            "duration": request.get("duration", 8),
            "aspect_ratio": request.get("aspect_ratio", "16:9"),
            "resolution": request.get("resolution", "1080p"),
            "reference_uris": request.get("reference_uris", []),
        }


class FakeProvider:
    def __init__(self, name: str, model: str = "fake-v1", cost_usd: float = 0.0) -> None:
        self.name = name
        self.model = model
        self.cost_usd = cost_usd

    def generate(self, request: dict[str, Any]) -> ProviderResult:
        entity_id = request.get("scene_id") or request.get("episode_id") or "asset"
        return ProviderResult(
            provider=self.name,
            model=self.model,
            asset_uri=f"fake://{self.name}/{entity_id}",
            cost_usd=self.cost_usd,
            metadata={"request": request, "fake": True},
        )
