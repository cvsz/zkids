from __future__ import annotations

from pathlib import Path

from .models import (
    AssetProvenance,
    CharacterSpec,
    EpisodeScript,
    EpisodeTimeline,
    GenerationJob,
    LiveCharacterPrompt,
    SceneManifest,
    SeriesBible,
    Storyboard,
)

SCHEMA_TARGETS = {
    "series-bible.schema.json": SeriesBible,
    "character-bible.schema.json": CharacterSpec,
    "episode.schema.json": EpisodeScript,
    "storyboard.schema.json": Storyboard,
    "scene-manifest.schema.json": SceneManifest,
    "timeline.schema.json": EpisodeTimeline,
    "provenance.schema.json": AssetProvenance,
    "generation-job.schema.json": GenerationJob,
    "live-character-prompt.schema.json": LiveCharacterPrompt,
}


def export_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in SCHEMA_TARGETS.items():
        schema = model.model_json_schema()
        path = out_dir / name
        path.write_text(_pretty(schema), encoding="utf-8")
        written.append(path)
    return written


def _pretty(obj) -> str:
    import json

    return json.dumps(obj, indent=2, ensure_ascii=False)


__all__ = ["SCHEMA_TARGETS", "export_schemas"]
