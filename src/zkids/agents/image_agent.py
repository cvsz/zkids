from __future__ import annotations

from pathlib import Path

from ..config import FactoryConfig
from ..engines.registry import build_image_engine
from ..logging import get_logger
from ..models import (
    AssetKind,
    AssetProvenance,
    CharacterSpec,
    GeneratorInfo,
    JobKind,
    QualityTier,
)
from ..pipeline.retry import plan_retry
from .base import FactoryContext

log = get_logger("zkid.image")


class ImageAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx
        self.cfg = ctx.cfg
        self.engine = build_image_engine(self.cfg)

    def build_prompt(
        self,
        action: str,
        environment: str,
        camera_shot: str,
        camera_move: str | None,
        characters: list[CharacterSpec],
        visual_style: str,
        extra_constraints: str = "",
    ) -> str:
        parts = [c.master_prompt() for c in characters]
        parts += [
            f"Visual style: {visual_style}.",
            f"Scene: {action}",
            f"Environment: {environment}",
            f"Camera: {camera_shot}" + (f", {camera_move}" if camera_move else ""),
        ]
        if extra_constraints:
            parts.append(extra_constraints)
        return "\n\n".join(parts)

    def generate_stills(
        self,
        manifest,
        characters: dict[str, CharacterSpec],
        visual_style: str,
        quality_tier: QualityTier,
        script=None,
    ) -> dict[str, Path]:
        stills_dir = self.ctx.episode_dir(manifest.episode_id) / "stills"
        results: dict[str, Path] = {}
        for entry in manifest.entries:
            shot_id = entry.scene_id
            dest = stills_dir / f"{shot_id}.png"
            scene = None
            if script:
                scene = next(
                    (s for s in script.scenes if s.scene_id == entry.script_scene_id or s.scene_id == shot_id.split("-")[0]),
                    None,
                )
            chars = [characters[c] for c in entry.characters if c in characters]
            context = {
                "environment": entry.environment,
                "action": entry.action,
                "camera_shot": entry.camera.shot,
                "shot_type": entry.shot_type,
                "script_scene_id": entry.script_scene_id,
                "segment": scene.segment if scene else None,
                "learning_point": scene.learning_point if scene else None,
                "characters": [c.model_dump() for c in chars],
            }
            job = self.ctx.queue.make_job(
                episode_id=manifest.episode_id,
                scene_id=shot_id,
                kind=JobKind.STILL,
                version=1,
                quality_tier=QualityTier.DRAFT if self.ctx.draft else QualityTier.PRODUCTION,
                provider=self.engine.name,
                model=None,
                payload_hash=self.ctx.db.sha(entry.model_dump()),
                max_retries=self.cfg.budgets.max_retries_per_scene,
            )
            if self._approved_artifact(job.job_id, dest):
                results[shot_id] = dest
                continue
            self.ctx.queue.submit(job)
            attempt = 0
            while attempt < job.max_retries:
                attempt += 1
                self.ctx.queue.start(job.job_id)
                decision = plan_retry(attempt - 1, job.max_retries, chars[0] if chars else None)
                prompt = self.build_prompt(
                    entry.action,
                    entry.environment,
                    entry.camera.shot,
                    entry.camera.movement,
                    chars,
                    visual_style,
                    decision.prompt_modifier if attempt > 1 else "",
                )
                try:
                    info = self.engine.generate_still(prompt, entry.negative_prompt, dest, context=context)
                    self.ctx.budget.charge_image(0.0)
                    ok, details = self._validate_still(dest)
                    if ok:
                        prov = AssetProvenance(
                            asset_id=f"STILL-{manifest.episode_id}-{shot_id}-v{job.attempts}",
                            scene_id=shot_id,
                            episode_id=manifest.episode_id,
                            kind=AssetKind.STILL,
                            path=str(dest),
                            generator=GeneratorInfo(
                                provider=info.get("provider", self.engine.name),
                                model=info.get("model"),
                                seed=info.get("seed"),
                                attempt=attempt,
                            ),
                            prompt_version="1.0",
                            prompt_text=prompt,
                            reference_images=entry.reference_images,
                        )
                        self.repo_record(prov)
                        self.ctx.queue.succeed(job.job_id, str(dest))
                        break
                    raise RuntimeError(f"still QC failed: {details.get('failed')}")
                except Exception as exc:
                    log.warning(
                        "still attempt failed",
                        extra={"scene_id": shot_id, "stage": f"attempt {attempt}: {exc}"[:160]},
                    )
                    self.ctx.queue.fail(job.job_id, str(exc))
                    if job.state.value in ("MANUAL_REVIEW", "FAILED"):
                        break
                    self.ctx.queue.requeue_for_retry(job.job_id)
            results[shot_id] = dest
        log.info("stills ready", extra={"episode_id": manifest.episode_id, "stage": f"{len(results)} files"})
        return results

    def _approved_artifact(self, job_id: str, dest: Path) -> bool:
        existing = self.ctx.repo.get_job(job_id)
        return bool(existing and existing.state.value == "APPROVED" and dest.exists())

    def _validate_still(self, path: Path) -> tuple[bool, dict]:
        if not path.exists():
            return False, {"failed": ["file missing"]}
        from ..engines.ffmpeg_tools import probe_video

        try:
            info = probe_video(path)
        except Exception as exc:
            return False, {"failed": [f"unreadable: {exc}"]}
        if (info["width"] or 0) < 320:
            return False, {"failed": ["resolution too small"]}
        return True, {"probe": info}

    def repo_record(self, prov: AssetProvenance) -> None:
        self.ctx.repo.record_asset(prov)
