from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LockedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Series(LockedModel):
    series_id: str
    title: str
    audience_min_age: int = Field(ge=0)
    audience_max_age: int = Field(ge=0)
    style: dict[str, Any] = Field(default_factory=dict)


class Character(LockedModel):
    character_id: str
    version: str
    name: str
    immutable_traits: dict[str, Any]
    mutable_traits: dict[str, Any] = Field(default_factory=dict)
    reference_assets: list[str] = Field(default_factory=list)


class Scene(LockedModel):
    scene_id: str
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    characters: list[str] = Field(default_factory=list)
    action: str
    camera: dict[str, Any] = Field(default_factory=dict)
    dialogue: str | None = None


class Episode(LockedModel):
    episode_id: str
    series_id: str
    title: str
    language: str
    duration_target: float = Field(gt=0)
    scenes: list[Scene] = Field(default_factory=list)
    max_retries_per_scene: int = Field(default=3, ge=0, le=10)
    budget_limit: float = Field(default=0, ge=0)


class AssetProvenance(LockedModel):
    asset_id: str
    scene_id: str | None = None
    provider: str
    model: str
    prompt_version: str
    character_version: str | None = None
    references: list[str] = Field(default_factory=list)
    seed: int | None = None
    approved: bool = False


class GenerationJob(LockedModel):
    job_id: str
    idempotency_key: str
    episode_id: str
    scene_id: str | None = None
    kind: Literal["story", "character", "storyboard", "voice", "music", "image", "motion", "render", "publish"]
    max_attempts: int = Field(default=3, ge=1, le=10)
    budget_limit: float = Field(default=0, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class QCResult(LockedModel):
    entity_id: str
    hard_failures: list[str] = Field(default_factory=list)
    soft_scores: dict[str, float] = Field(default_factory=dict)
    decision: Literal["PASS", "RETRY", "MANUAL_REVIEW", "FAIL"]


class Publication(LockedModel):
    episode_id: str
    human_approved: bool = False
    approved_by: str | None = None
    destination: str | None = None

    def assert_publishable(self) -> None:
        if not self.human_approved:
            raise ValueError("human publish approval is required")
