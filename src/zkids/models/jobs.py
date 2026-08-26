from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import JobKind, JobState, QualityTier
from .provenance import utc_now


def idempotency_key(episode_id: str, scene_id: str, kind: str, version: int = 1) -> str:
    return f"{episode_id}:{scene_id}:{kind}:v{version}"


class GenerationJob(BaseModel):
    job_id: str
    kind: JobKind
    scene_id: str | None = None
    episode_id: str | None = None
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_retries: int = 3
    quality_tier: QualityTier = QualityTier.DRAFT
    provider: str = "placeholder"
    model: str | None = None
    payload_hash: str | None = None
    error: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    cost_estimate_usd: float = 0.0
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())
    updated_at: str = Field(default_factory=lambda: utc_now().isoformat())

    def can_transition(self, target: JobState) -> bool:
        from .enums import ALLOWED_TRANSITIONS

        return target in ALLOWED_TRANSITIONS.get(self.state, set())
