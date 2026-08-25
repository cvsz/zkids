"""Canonical domain state machines for zkids."""
from __future__ import annotations

from enum import StrEnum


class TransitionError(ValueError):
    pass


class EpisodeState(StrEnum):
    DRAFT = "DRAFT"
    STORY_APPROVED = "STORY_APPROVED"
    PRODUCTION = "PRODUCTION"
    FINAL_QC_APPROVED = "FINAL_QC_APPROVED"
    HUMAN_PUBLISH_APPROVED = "HUMAN_PUBLISH_APPROVED"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class SceneState(StrEnum):
    CREATED = "CREATED"
    SCRIPT_READY = "SCRIPT_READY"
    STILL_PENDING = "STILL_PENDING"
    STILL_GENERATING = "STILL_GENERATING"
    STILL_QC = "STILL_QC"
    VIDEO_PENDING = "VIDEO_PENDING"
    VIDEO_GENERATING = "VIDEO_GENERATING"
    VIDEO_QC = "VIDEO_QC"
    TIMELINE_READY = "TIMELINE_READY"
    APPROVED = "APPROVED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"


class JobState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    SUCCEEDED = "SUCCEEDED"
    RETRY = "RETRY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


EPISODE_TRANSITIONS: dict[EpisodeState, set[EpisodeState]] = {
    EpisodeState.DRAFT: {EpisodeState.STORY_APPROVED, EpisodeState.REJECTED},
    EpisodeState.STORY_APPROVED: {EpisodeState.PRODUCTION, EpisodeState.REJECTED},
    EpisodeState.PRODUCTION: {EpisodeState.FINAL_QC_APPROVED, EpisodeState.REJECTED},
    EpisodeState.FINAL_QC_APPROVED: {EpisodeState.HUMAN_PUBLISH_APPROVED, EpisodeState.REJECTED},
    EpisodeState.HUMAN_PUBLISH_APPROVED: {EpisodeState.PUBLISHED, EpisodeState.REJECTED},
    EpisodeState.PUBLISHED: set(),
    EpisodeState.REJECTED: set(),
}

SCENE_TRANSITIONS: dict[SceneState, set[SceneState]] = {
    SceneState.CREATED: {SceneState.SCRIPT_READY, SceneState.FAILED},
    SceneState.SCRIPT_READY: {SceneState.STILL_PENDING, SceneState.FAILED},
    SceneState.STILL_PENDING: {SceneState.STILL_GENERATING, SceneState.FAILED},
    SceneState.STILL_GENERATING: {SceneState.STILL_QC, SceneState.FAILED},
    SceneState.STILL_QC: {SceneState.VIDEO_PENDING, SceneState.STILL_PENDING, SceneState.MANUAL_REVIEW},
    SceneState.VIDEO_PENDING: {SceneState.VIDEO_GENERATING, SceneState.FAILED},
    SceneState.VIDEO_GENERATING: {SceneState.VIDEO_QC, SceneState.FAILED},
    SceneState.VIDEO_QC: {SceneState.TIMELINE_READY, SceneState.VIDEO_PENDING, SceneState.MANUAL_REVIEW},
    SceneState.TIMELINE_READY: {SceneState.APPROVED, SceneState.MANUAL_REVIEW},
    SceneState.APPROVED: set(),
    SceneState.MANUAL_REVIEW: {SceneState.STILL_PENDING, SceneState.VIDEO_PENDING, SceneState.FAILED},
    SceneState.FAILED: set(),
}


def assert_transition(current: StrEnum, target: StrEnum, table: dict[StrEnum, set[StrEnum]]) -> None:
    if target not in table.get(current, set()):
        raise TransitionError(f"illegal transition: {current} -> {target}")
