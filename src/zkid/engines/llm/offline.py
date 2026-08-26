from __future__ import annotations

from ...models import CharacterSpec, EpisodeScript, ScriptScene, SeriesBible
from .offline_story import build_offline_script

SEGMENT_ORDER = ["hook", "setup", "problem", "discovery", "try", "solution", "recap", "ending"]


class OfflineLLM:
    name = "offline"

    def generate_json(self, system: str, user: str) -> dict:
        del system
        return {"note": "offline llm returns no freeform json", "input": user[:200]}


class OfflineStoryFactory:
    """Deterministic template story generator so the pipeline runs with zero API keys."""

    name = "offline"

    def generate_script(
        self,
        episode_id: str,
        topic: str,
        series: SeriesBible | None,
        characters: list[CharacterSpec],
        scene_count: int = 8,
        scene_duration: float = 8.0,
        segments: list[str] | None = None,
    ) -> EpisodeScript:
        hero = characters[0] if characters else None
        friend = characters[1] if len(characters) > 1 else None
        learning = (series.learning_topics[0] if series and series.learning_topics else "curiosity")
        return build_offline_script(
            episode_id=episode_id,
            series_id=series.series_id if series else None,
            title=_title_from_topic(topic),
            topic=topic,
            learning_goal=learning,
            hero=hero,
            friend=friend,
            scene_count=scene_count,
            scene_duration=scene_duration,
            segments=segments or SEGMENT_ORDER,
            visual_style=series.visual_style.type if series else "soft 3D children's animation",
        )


def _title_from_topic(topic: str) -> str:
    cleaned = topic.strip().rstrip(".!?")
    words = cleaned.split()
    title = " ".join(w.capitalize() for w in words[:7])
    return title or "A New Adventure"


def script_from_dict(data: dict) -> EpisodeScript:
    scenes = [ScriptScene(**s) for s in data.get("scenes", [])]
    payload = {k: v for k, v in data.items() if k != "scenes"}
    return EpisodeScript(**payload, scenes=scenes)
