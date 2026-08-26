from __future__ import annotations

from ..config import FactoryConfig
from ..models import (
    EpisodeScript,
    EpisodeTimeline,
    MusicClip,
    SFXEvent,
    SceneManifest,
    SubtitleEvent,
    TimelineClip,
    VoiceClip,
)

SEGMENT_MUSIC: dict[str | None, str] = {
    "hook": "opening",
    "setup": "playful",
    "problem": "discovery",
    "discovery": "discovery",
    "try": "playful",
    "solution": "learning-song",
    "recap": "learning-song",
    "ending": "ending",
}


class TimelineEngine:
    """Owns all timestamp math; video models only ever produce scene assets."""

    def __init__(self, cfg: FactoryConfig, draft: bool) -> None:
        self.cfg = cfg
        self.draft = draft
        self.width, self.height, self.fps = cfg.baseline(draft)
        self.padding = 0.0 if draft else cfg.audio.padding_after_voice_sec

    def build(
        self,
        script: EpisodeScript,
        manifest: SceneManifest,
        scene_videos: dict[str, str],
        voice_files: dict[str, tuple[str, float]],
        sfx_cues: list[dict] | None = None,
    ) -> EpisodeTimeline:
        timeline = EpisodeTimeline(episode=script.episode_id, fps=self.fps, width=self.width, height=self.height)
        t = 0.0
        for i, scene in enumerate(script.scenes):
            entry = next(
                (e for e in manifest.entries if e.script_scene_id == scene.scene_id),
                None,
            ) or manifest.by_scene(scene.scene_id)
            base_duration = entry.duration if entry else scene.duration_target
            voice_path, voice_len = voice_files.get(scene.scene_id, (None, 0.0))
            duration = max(base_duration, round(voice_len + self.padding, 2)) if voice_path else base_duration
            timeline.tracks["video"].append(
                TimelineClip(
                    clip_id=f"V-{scene.scene_id}",
                    scene_id=scene.scene_id,
                    src=scene_videos[scene.scene_id],
                    start=round(t, 3),
                    duration=round(duration, 3),
                )
            )
            if voice_path:
                timeline.tracks["voice"].append(
                    VoiceClip(
                        clip_id=f"A-{scene.scene_id}",
                        scene_id=scene.scene_id,
                        src=voice_path,
                        start=round(t + 0.2, 3),
                        duration=round(voice_len, 3),
                        speaker=scene.dialogue.speaker if scene.dialogue else None,
                        text=scene.dialogue.text if scene.dialogue else scene.narration,
                    )
                )
            if scene.sfx_cues:
                for j, cue in enumerate(scene.sfx_cues):
                    timeline.tracks["sfx"].append(
                        SFXEvent(
                            clip_id=f"X-{scene.scene_id}-{j}",
                            scene_id=scene.scene_id,
                            src=cue.file,
                            start=round(t + cue.timestamp, 3),
                            duration=0.6,
                        )
                    )
            if sfx_cues:
                for k, ev in enumerate([e for e in sfx_cues if e.get("scene_id") == scene.scene_id]):
                    timeline.tracks["sfx"].append(
                        SFXEvent(
                            clip_id=f"Y-{scene.scene_id}-{k}",
                            scene_id=scene.scene_id,
                            src=ev["file"],
                            start=round(t + float(ev["timestamp"]), 3),
                            duration=ev.get("duration", 0.6),
                        )
                    )
            t += duration
        total = round(t, 3)
        music_cues = _music_plan(script, total)
        timeline.tracks["music"] = [
            MusicClip(
                clip_id=f"M{i}",
                src=cue["src"],
                start=round(cue["start"], 3),
                duration=round(cue["duration"], 3),
                label=cue["cue"],
                fade_in=min(1.0, cue["duration"] / 4),
                fade_out=min(2.0, cue["duration"] / 4),
            )
            for i, cue in enumerate(music_cues)
        ]
        return timeline


def _music_plan(script: EpisodeScript, total: float) -> list[dict]:
    plan: list[dict] = []
    t = 0.0
    for scene in script.scenes:
        dur = scene.duration_target
        cue = SEGMENT_MUSIC.get(scene.segment)
        if cue:
            plan.append({"cue": cue, "start": t, "duration": dur, "src": f"music://{cue}"})
        t += dur
    if not plan and total > 0:
        plan.append({"cue": "playful", "start": 0.0, "duration": total, "src": "music://playful"})
    merged: list[dict] = []
    for item in plan:
        if merged and merged[-1]["cue"] == item["cue"]:
            merged[-1]["duration"] += item["duration"]
        else:
            merged.append(item)
    return merged


def build_subtitles(timeline: EpisodeTimeline) -> list[SubtitleEvent]:
    events: list[SubtitleEvent] = []
    idx = 1
    for clip in sorted(timeline.tracks["voice"], key=lambda c: c.start):
        text = (clip.text or "").strip()
        if not text:
            continue
        chunks = _split_caption(text)
        n = len(chunks)
        span = max(clip.duration, 0.8 * n)
        per = span / n
        for j, chunk in enumerate(chunks):
            events.append(
                SubtitleEvent(
                    index=idx,
                    start=round(clip.start + j * per, 3),
                    end=round(clip.start + (j + 1) * per - 0.05, 3),
                    text=chunk,
                    highlight_words=[w.strip(".,!?") for w in chunk.split() if w.isupper()],
                )
            )
            idx += 1
    return events


def _split_caption(text: str, max_chars: int = 42) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        if sum(len(x) + 1 for x in current) + len(w) > max_chars and current:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))
    return lines or [""]
