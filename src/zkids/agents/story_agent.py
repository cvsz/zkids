from __future__ import annotations

import json
from pathlib import Path

from ..config import FactoryConfig
from ..db import slugify
from ..db.repo import FactoryRepository
from ..engines.llm.offline import OfflineStoryFactory
from ..engines.registry import build_llm
from ..logging import get_logger
from ..models import CharacterSpec, EpisodeScript, SeriesBible

log = get_logger("zkid.story")

SYSTEM_PROMPT = """You are the Story Agent for a children's cartoon factory.
Write a complete episode script as JSON matching this shape:
{"episode_id": str, "title": str, "learning_goal": str,
 "scenes": [{"scene_id": "S001", "segment": one of hook|setup|problem|discovery|try|solution|recap|ending,
             "duration_target": 8.0, "characters": [character_id], "location": str,
             "dialogue": {"speaker": character_id, "text": short kid-friendly line},
             "action": str, "camera": {"shot": str}, "learning_point": str|null}]}
Rules: original IP only; simple sentences for ages 4-7; one clear learning goal;
follow HOOK->SETUP->PROBLEM->DISCOVERY->TRY->SOLUTION->RECAP->ENDING."""


class StoryAgent:
    def __init__(self, cfg: FactoryConfig, repo: FactoryRepository) -> None:
        self.cfg = cfg
        self.repo = repo

    def run(
        self,
        topic: str,
        episode_id: str,
        series: SeriesBible | None,
        characters: list[CharacterSpec],
        offline: bool = False,
    ) -> EpisodeScript:
        script = self._generate(topic, episode_id, series, characters, offline)
        out = self.cfg.episode_dir(episode_id) / "metadata" / "episode.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(script.model_dump_json(indent=2), encoding="utf-8")
        self.repo.save_episode_script(script)
        log.info("script ready", extra={"episode_id": episode_id, "stage": f"{len(script.scenes)} scenes"})
        return script

    def _generate(self, topic, episode_id, series, characters, offline) -> EpisodeScript:
        if not offline:
            try:
                llm = build_llm(self.cfg)
                user = json.dumps(
                    {
                        "topic": topic,
                        "series": series.model_dump() if series else None,
                        "characters": [c.character_id + ": " + c.name for c in characters],
                    }
                )
                data = llm.generate_json(SYSTEM_PROMPT, user)
                data["episode_id"] = episode_id
                if series:
                    data.setdefault("series_id", series.series_id)
                return EpisodeScript.model_validate(data)
            except Exception as exc:
                log.warning("LLM failed, using offline story factory", extra={"stage": str(exc)[:120]})
        scene_count = max(4, min(8, round((series.episode_duration_target_sec if series else 240) / 30)))
        return OfflineStoryFactory().generate_script(
            episode_id=episode_id,
            topic=topic,
            series=series,
            characters=characters,
            scene_count=min(scene_count, 8),
            scene_duration=8.0,
            segments=["hook", "setup", "problem", "discovery", "try", "solution", "recap", "ending"],
        )


def default_episode_id(topic: str, n: int | None = None) -> str:
    base = "EP" + slugify(topic).upper().replace("-", "")[:8]
    return base + (str(n) if n else "")
