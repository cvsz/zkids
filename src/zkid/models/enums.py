from enum import Enum


class JobState(str, Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    RETRY = "RETRY"
    APPROVED = "APPROVED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class JobKind(str, Enum):
    STORY = "STORY"
    VOICE = "VOICE"
    STILL = "STILL"
    VIDEO = "VIDEO"
    MUSIC = "MUSIC"
    SFX = "SFX"
    RENDER = "RENDER"


class ShotType(str, Enum):
    HERO = "hero"
    REACTION = "reaction"
    ENVIRONMENT = "environment"
    CLOSEUP = "closeup"
    TRANSITION = "transition"
    GRAPHICS = "graphics"


class QualityTier(str, Enum):
    DRAFT = "draft"
    PRODUCTION = "production"


class GateId(int, Enum):
    STORY_APPROVED = 1
    CHARACTER_STORYBOARD_APPROVED = 2
    SCENE_GENERATION_APPROVED = 3
    FINAL_VIDEO_QC = 4
    HUMAN_PUBLISH_APPROVAL = 5


class AssetKind(str, Enum):
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    MANIFEST = "manifest"
    TIMELINE = "timeline"
    CHARACTER_REF = "character_ref"
    STILL = "still"
    VIDEO = "video"
    VOICE = "voice"
    MUSIC = "music"
    SFX = "sfx"
    SUBTITLE = "subtitle"
    MASTER = "master"


ALLOWED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.PENDING: {JobState.GENERATING, JobState.FAILED},
    JobState.GENERATING: {JobState.VALIDATING, JobState.RETRY, JobState.FAILED, JobState.MANUAL_REVIEW},
    JobState.VALIDATING: {JobState.APPROVED, JobState.RETRY, JobState.MANUAL_REVIEW, JobState.FAILED},
    JobState.RETRY: {JobState.GENERATING, JobState.MANUAL_REVIEW, JobState.FAILED},
    JobState.APPROVED: {JobState.PENDING},
    JobState.FAILED: {JobState.PENDING, JobState.MANUAL_REVIEW},
    JobState.MANUAL_REVIEW: {JobState.APPROVED, JobState.PENDING},
}
