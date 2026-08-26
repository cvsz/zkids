from __future__ import annotations

from pydantic import BaseModel, Field

from .episode import CameraSpec


class MotionSpec(BaseModel):
    body: str = "gentle natural movement"
    face: str = "soft blinking and smiling"
    secondary: str = "subtle secondary movement"


class SceneManifestEntry(BaseModel):
    scene_id: str
    script_scene_id: str | None = None
    shot_type: str = "hero"
    timeline_start: float = 0.0
    duration: float = 8.0
    characters: list[str] = Field(default_factory=list)
    reference_images: list[str] = Field(default_factory=list)
    environment: str = "simple soft background"
    action: str = ""
    camera: CameraSpec = Field(default_factory=CameraSpec)
    motion: MotionSpec = Field(default_factory=MotionSpec)
    aspect_ratio: str = "16:9"
    learning_point: str | None = None
    negative_prompt: str = (
        "change clothing, change face, add characters, add accessories, "
        "change body proportions, scary imagery, watermarks, text overlays"
    )


class SceneManifest(BaseModel):
    schema_version: str = "1.0"
    episode_id: str
    entries: list[SceneManifestEntry] = Field(default_factory=list)

    def by_scene(self, scene_id: str) -> SceneManifestEntry | None:
        for e in self.entries:
            if e.scene_id == scene_id:
                return e
        return None


class TimelineClip(BaseModel):
    clip_id: str
    scene_id: str | None = None
    src: str
    start: float = 0.0
    duration: float = 0.0
    label: str | None = None


class VoiceClip(TimelineClip):
    speaker: str | None = None
    text: str | None = None


class MusicClip(TimelineClip):
    fade_in: float = 1.0
    fade_out: float = 2.0
    loop: bool = False


class SFXEvent(TimelineClip):
    pass


class SubtitleEvent(BaseModel):
    index: int
    start: float
    end: float
    text: str
    highlight_words: list[str] = Field(default_factory=list)


class EpisodeTimeline(BaseModel):
    schema_version: str = "1.0"
    episode: str
    fps: int = 30
    width: int = 1920
    height: int = 1080
    tracks: dict[str, list] = Field(
        default_factory=lambda: {
            "video": [],
            "voice": [],
            "music": [],
            "sfx": [],
            "subtitle": [],
        }
    )

    def total_duration(self) -> float:
        end = 0.0
        for clips in self.tracks["video"]:
            end = max(end, clips.start + clips.duration)
        return end
