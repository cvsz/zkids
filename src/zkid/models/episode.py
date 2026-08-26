from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import ShotType


class Dialogue(BaseModel):
    speaker: str
    text: str
    direction: str | None = None


class CameraSpec(BaseModel):
    shot: str = "medium"
    movement: str | None = None


class SFXCue(BaseModel):
    file: str
    timestamp: float


class ScriptScene(BaseModel):
    scene_id: str
    segment: str | None = None
    duration_target: float = 8.0
    characters: list[str] = Field(default_factory=list)
    location: str | None = None
    dialogue: Dialogue | None = None
    narration: str | None = None
    action: str = ""
    camera: CameraSpec = Field(default_factory=CameraSpec)
    learning_point: str | None = None
    sfx_cues: list[SFXCue] | None = None


class EpisodeScript(BaseModel):
    schema_version: str = "1.0"
    episode_id: str
    series_id: str | None = None
    title: str
    topic: str | None = None
    learning_goal: str | None = None
    hook: str | None = None
    scenes: list[ScriptScene] = Field(default_factory=list)

    def total_target_duration(self) -> float:
        return sum(s.duration_target for s in self.scenes)


class ShotSpec(BaseModel):
    shot_id: str
    scene_id: str
    type: ShotType = ShotType.HERO
    description: str = ""
    camera: CameraSpec = Field(default_factory=CameraSpec)
    duration_target: float = 8.0
    characters: list[str] = Field(default_factory=list)
    reusable: bool = False


class Storyboard(BaseModel):
    schema_version: str = "1.0"
    episode_id: str
    shots: list[ShotSpec] = Field(default_factory=list)

    def generation_shots(self) -> list[ShotSpec]:
        unique_types = {ShotType.TRANSITION, ShotType.GRAPHICS}
        return [s for s in self.shots if s.type not in unique_types and not s.reusable]
