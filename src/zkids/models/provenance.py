from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .enums import AssetKind


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeneratorInfo(BaseModel):
    provider: str
    model: str | None = None
    seed: int | None = None
    attempt: int = 1


class AssetProvenance(BaseModel):
    asset_id: str
    scene_id: str | None = None
    episode_id: str | None = None
    kind: AssetKind
    path: str
    generator: GeneratorInfo
    prompt_version: str = "1.0"
    character_version: str | None = None
    prompt_text: str | None = None
    reference_images: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    approved: bool = False
    cost_estimate_usd: float = 0.0

    def write_json(self, sidecar_path: str) -> None:
        import json
        from pathlib import Path

        Path(sidecar_path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
