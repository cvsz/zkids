from __future__ import annotations

from pathlib import Path

from ..config import FactoryConfig
from ..db.repo import FactoryRepository
from ..logging import get_logger
from ..models import EpisodeScript, SceneManifest, SceneManifestEntry, ShotType, Storyboard, ShotSpec

log = get_logger("zkid.storyboard")


class StoryboardAgent:
    """Scene-based breakdown with reusable shot types to cut generation cost."""

    def __init__(self, cfg: FactoryConfig, repo: FactoryRepository) -> None:
        self.cfg = cfg
        self.repo = repo

    def run(self, script: EpisodeScript) -> Storyboard:
        shots: list[ShotSpec] = []
        for i, scene in enumerate(script.scenes):
            shots.append(
                ShotSpec(
                    shot_id=f"{scene.scene_id}-HERO",
                    scene_id=scene.scene_id,
                    type=ShotType.HERO,
                    description=scene.action,
                    camera=scene.camera,
                    duration_target=scene.duration_target,
                    characters=list(scene.characters),
                )
            )
            if scene.dialogue and i > 0 and i % 2 == 0:
                prev = shots[-2]
                shots.append(
                    ShotSpec(
                        shot_id=f"{scene.scene_id}-REACTION",
                        scene_id=scene.scene_id,
                        type=ShotType.REACTION,
                        description=f"reaction cutaway reusing {prev.shot_id} framing",
                        camera=prev.camera,
                        duration_target=scene.duration_target,
                        characters=list(scene.characters),
                        reusable=True,
                    )
                )
        sb = Storyboard(episode_id=script.episode_id, shots=shots)
        out = self.cfg.episode_dir(script.episode_id) / "metadata" / "storyboard.json"
        out.write_text(sb.model_dump_json(indent=2), encoding="utf-8")
        self.repo.save_storyboard(sb)
        log.info(
            "storyboard ready",
            extra={"episode_id": script.episode_id, "stage": f"{len(shots)} shots ({sb.generation_shots().__len__()} to generate)"},
        )
        return sb


class ManifestGenerator:
    def __init__(self, cfg: FactoryConfig, repo: FactoryRepository) -> None:
        self.cfg = cfg
        self.repo = repo

    def run(self, script: EpisodeScript, storyboard: Storyboard, character_refs: dict[str, list[str]]) -> SceneManifest:
        entries: list[SceneManifestEntry] = []
        t = 0.0
        for shot in storyboard.generation_shots():
            scene = next((s for s in script.scenes if s.scene_id == shot.scene_id), None)
            refs: list[str] = []
            for cid in shot.characters:
                refs += character_refs.get(cid, [])
            entry = SceneManifestEntry(
                scene_id=shot.shot_id,
                script_scene_id=shot.scene_id,
                shot_type=shot.type.value,
                timeline_start=round(t, 3),
                duration=shot.duration_target,
                characters=list(shot.characters),
                reference_images=sorted(set(refs)),
                environment=(scene.location.replace("-", " ").lower() if scene and scene.location else "sunny meadow"),
                action=shot.description or (scene.action if scene else ""),
                camera={"shot": shot.camera.shot, "movement": shot.camera.movement},
                learning_point=scene.learning_point if scene else None,
            )
            entries.append(entry)
            t += shot.duration_target
        manifest = SceneManifest(episode_id=script.episode_id, entries=entries)
        out = self.cfg.episode_dir(script.episode_id) / "metadata" / "scene-manifest.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        self.repo.save_manifest(manifest)
        log.info("scene manifest ready", extra={"episode_id": script.episode_id, "stage": f"{len(entries)} render units"})
        return manifest
