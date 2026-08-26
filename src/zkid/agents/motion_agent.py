from __future__ import annotations

from pathlib import Path

from ..config import FactoryConfig
from ..engines.registry import build_motion_engine
from ..logging import get_logger
from ..models import (
    AssetKind,
    AssetProvenance,
    CharacterSpec,
    GeneratorInfo,
    JobKind,
    MotionSpec,
    QualityTier,
    SceneManifestEntry,
)
from ..pipeline.retry import plan_retry
from .base import FactoryContext
from .image_agent import ImageAgent

log = get_logger("zkid.motion")


class MotionAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx
        self.cfg = ctx.cfg
        self.engine = build_motion_engine(self.cfg)
        self.image_agent = ImageAgent(ctx)

    def build_video_prompt(
        self,
        entry: SceneManifestEntry,
        characters: list[CharacterSpec],
        extra: str = "",
        simplify_motion: bool = False,
    ) -> str:
        identity = "\n\n".join(c.master_prompt() for c in characters)
        motion = entry.motion or MotionSpec()
        if simplify_motion:
            motion = MotionSpec(body="almost still, tiny sway", face="slow blink", secondary="none")
        parts = [
            "Maintain exactly the character identity, facial structure, body proportions, "
            "fur colors, clothing design and clothing colors from the provided reference images.",
            "",
            identity,
            "",
            f"Action:\n{entry.action}",
            "",
            f"Camera:\n{entry.camera.shot} shot"
            + (f", {entry.camera.movement}" if entry.camera.movement else ""),
            "",
            f"Motion:\n{motion.body},\n{motion.face},\n{motion.secondary}",
            "",
            f"Do not:\n{entry.negative_prompt}",
        ]
        if extra:
            parts.append(extra)
        return "\n".join(parts)

    def generate_videos(
        self,
        manifest,
        characters: dict[str, CharacterSpec],
        stills: dict[str, Path],
        quality_tier: QualityTier,
    ) -> dict[str, Path]:
        video_dir = self.ctx.episode_dir(manifest.episode_id) / "video" / "raw"
        video_dir.mkdir(parents=True, exist_ok=True)
        results: dict[str, Path] = {}
        for entry in manifest.entries:
            shot_id = entry.scene_id
            dest = video_dir / f"{shot_id}.mp4"
            job = self.ctx.queue.make_job(
                episode_id=manifest.episode_id,
                scene_id=shot_id,
                kind=JobKind.VIDEO,
                version=1,
                quality_tier=QualityTier.DRAFT if self.ctx.draft else QualityTier.PRODUCTION,
                provider=self.engine.name,
                model=getattr(self.engine, "model", None),
                payload_hash=self.ctx.db.sha({"still": str(stills.get(shot_id)), "duration": entry.duration}),
                max_retries=self.cfg.budgets.max_retries_per_scene,
                cost_estimate_usd=0.0 if self.ctx.draft else 0.30,
            )
            existing = self.ctx.repo.get_job(job.job_id)
            if existing and existing.state.value == "APPROVED" and dest.exists():
                results[shot_id] = dest
                continue
            self.ctx.queue.submit(job)
            chars = [characters[c] for c in entry.characters if c in characters]
            attempt = 0
            while attempt < job.max_retries:
                attempt += 1
                self.ctx.queue.start(job.job_id)
                decision = plan_retry(attempt - 1, job.max_retries, chars[0] if chars else None)
                prompt = self.build_video_prompt(
                    entry,
                    chars,
                    extra=decision.prompt_modifier if attempt > 1 else "",
                    simplify_motion=decision.simplify_motion,
                )
                try:
                    refs = [Path(p) for p in entry.reference_images if Path(p).exists()]
                    info = self.engine.generate_scene_video(
                        stills[shot_id], prompt, entry.duration, dest, reference_images=refs
                    )
                    self.ctx.budget.charge_video(job.cost_estimate_usd)
                    ok, details = self._validate(dest, entry.duration)
                    if ok:
                        prov = AssetProvenance(
                            asset_id=f"VIDEO-{manifest.episode_id}-{shot_id}-v{job.attempts}",
                            scene_id=shot_id,
                            episode_id=manifest.episode_id,
                            kind=AssetKind.VIDEO,
                            path=str(dest),
                            generator=GeneratorInfo(
                                provider=info.get("provider", self.engine.name),
                                model=info.get("model"),
                                attempt=attempt,
                            ),
                            prompt_version="1.0",
                            prompt_text=prompt,
                            reference_images=[str(r) for r in refs],
                        )
                        self.ctx.repo.record_asset(prov)
                        self.ctx.queue.succeed(job.job_id, str(dest))
                        break
                    raise RuntimeError(f"video QC failed: {details.get('failed')}")
                except Exception as exc:
                    log.warning(
                        "video attempt failed",
                        extra={"scene_id": shot_id, "stage": f"attempt {attempt}: {exc}"[:160]},
                    )
                    self.ctx.queue.fail(job.job_id, str(exc))
                    if job.state.value in ("MANUAL_REVIEW", "FAILED"):
                        break
                    self.ctx.queue.requeue_for_retry(job.job_id)
            if dest.exists():
                results[shot_id] = dest
            else:
                log.error("scene has no video after retries", extra={"scene_id": shot_id})
        return results

    def _validate(self, path: Path, expected_duration: float) -> tuple[bool, dict]:
        from ..engines.ffmpeg_tools import probe_video

        info = probe_video(path)
        failures = []
        if info["duration"] < max(expected_duration - 1.5, 0.5):
            failures.append(f"too short {info['duration']:.2f}s")
        if (info["width"] or 0) < 320:
            failures.append("resolution too small")
        if failures:
            return False, {"failed": failures}
        return True, {"probe": info}
