from __future__ import annotations

import json
from pathlib import Path

from ..config import FactoryConfig
from ..db.repo import FactoryRepository
from ..engines.registry import build_image_engine
from ..logging import get_logger
from ..models import CharacterSpec

log = get_logger("zkid.character")

REQUIRED_VIEWS = ["front", "side", "back", "three-quarter"]
EXPRESSIONS = ["happy", "sad", "surprised", "thinking", "excited", "neutral"]


class CharacterAgent:
    def __init__(self, cfg: FactoryConfig, repo: FactoryRepository) -> None:
        self.cfg = cfg
        self.repo = repo

    def load_templates(self) -> list[CharacterSpec]:
        chars_dir = self.cfg.templates_dir / "characters"
        specs: list[CharacterSpec] = []
        if chars_dir.exists():
            for f in sorted(chars_dir.glob("*.json")):
                data = json.loads(f.read_text(encoding="utf-8"))
                specs.append(CharacterSpec.model_validate(data))
        for spec in specs:
            self.repo.save_character(spec)
        log.info("character bible loaded", extra={"stage": ", ".join(c.name for c in specs)})
        return specs

    def ensure_reference_sheets(self, characters: list[CharacterSpec], episode_id: str | None = None) -> dict[str, dict[str, str]]:
        engine = build_image_engine(self.cfg)
        out_map: dict[str, dict[str, str]] = {}
        base = self.cfg.templates_dir / "characters" / "refs"
        for spec in characters:
            views: dict[str, str] = {}
            char_ref_dir = base / slug(spec.name)
            for view in REQUIRED_VIEWS + ["expressions"]:
                fname = f"{view}.png"
                path = char_ref_dir / fname
                rel = str(path.relative_to(self.cfg.root)) if path.is_relative_to(self.cfg.root) else str(path)
                views[view] = rel
                if path.exists():
                    continue
                prompt = (
                    f"{spec.master_prompt()}\n\n"
                    f"Character sheet view: {view.replace('-', ' ')} on plain white background, "
                    "full body, neutral pose, soft 3D children's animation style."
                )
                try:
                    engine.generate_still(
                        prompt,
                        "",
                        path,
                        context={
                            "mode": "character_sheet",
                            "view": view,
                            "character": spec.model_dump(),
                        },
                    )
                    log.info("reference generated", extra={"stage": f"{spec.character_id}/{view}"})
                except Exception as exc:
                    log.warning(
                        "reference generation failed; placeholder required",
                        extra={"stage": f"{spec.character_id}/{view}: {exc}"[:140]},
                    )
            spec.reference_images = {**views, **spec.reference_images}
            self.repo.save_character(spec)
            out_map[spec.character_id] = views
        return out_map


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def refs_for_scene(spec: CharacterSpec) -> list[str]:
    picks = []
    for key in ("front", "three-quarter", "expressions"):
        p = spec.reference_images.get(key)
        if p and Path(p).exists():
            picks.append(p)
    return picks or [p for p in spec.reference_images.values() if Path(p).exists()]
