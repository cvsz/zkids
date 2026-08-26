from __future__ import annotations

from pathlib import Path

from ..config import FactoryConfig
from ..db.repo import FactoryRepository
from ..engines.registry import build_sfx_library, build_voice_engine
from ..engines.voice.silent import estimate_speech_duration
from ..logging import get_logger
from ..models import (
    AssetKind,
    AssetProvenance,
    CharacterSpec,
    EpisodeScript,
    GeneratorInfo,
    JobKind,
    QualityTier,
)
from .base import FactoryContext

log = get_logger("zkid.audio")


class AudioAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx
        self.cfg: FactoryConfig = ctx.cfg
        self.repo: FactoryRepository = ctx.repo
        self.engine = build_voice_engine(self.cfg)
        self.sfx = build_sfx_library(self.cfg)

    def voice_path(self, episode_id: str, scene_id: str) -> Path:
        return self.ctx.episode_dir(episode_id) / "voice" / f"{episode_id}_{scene_id}.wav"

    def generate_voice(
        self,
        script: EpisodeScript,
        characters: dict[str, CharacterSpec],
        quality_tier: QualityTier,
        version: int = 1,
    ) -> dict[str, tuple[str, float]]:
        out: dict[str, tuple[str, float]] = {}
        tier = "production" if not self.ctx.draft else "draft"
        for scene in script.scenes:
            text = scene.dialogue.text if scene.dialogue else scene.narration
            if not text:
                continue
            speaker = scene.dialogue.speaker if scene.dialogue else None
            profile = characters.get(speaker or "").voice if speaker else None
            voice_name = profile.provider_voice_name if profile else None
            job = self.ctx.queue.make_job(
                episode_id=script.episode_id,
                scene_id=scene.scene_id,
                kind=JobKind.VOICE,
                version=version,
                quality_tier=QualityTier.DRAFT if self.ctx.draft else QualityTier.PRODUCTION,
                provider=self.engine.name,
                model=voice_name,
                payload_hash=self.ctx.db.sha({"text": text, "voice": voice_name}),
                max_retries=self.cfg.retry.max_attempts,
            )
            existing = self.repo.get_job(job.job_id)
            if existing and existing.state.value == "APPROVED" and existing.artifacts:
                p = Path(existing.artifacts[0])
                if p.exists():
                    out[scene.scene_id] = (str(p), _duration(p))
                    continue
            self.ctx.queue.submit(job)
            self.ctx.queue.start(job.job_id)
            try:
                dest = self.voice_path(script.episode_id, scene.scene_id)
                info = self.engine.synthesize(text, voice_name, dest)
                prov = AssetProvenance(
                    asset_id=f"VOICE-{script.episode_id}-{scene.scene_id}",
                    scene_id=scene.scene_id,
                    episode_id=script.episode_id,
                    kind=AssetKind.VOICE,
                    path=str(dest),
                    generator=GeneratorInfo(provider=info["provider"], model=info["model"], attempt=job.attempts),
                    prompt_text=text,
                )
                self.repo.record_asset(prov)
                self.ctx.queue.succeed(job.job_id, str(dest))
                out[scene.scene_id] = (str(dest), info.get("duration") or _duration(dest))
            except Exception as exc:
                log.error("voice generation failed", extra={"scene_id": scene.scene_id, "stage": str(exc)[:160]})
                self.ctx.queue.fail(job.job_id, str(exc))
                out[scene.scene_id] = (str(self.voice_path(script.episode_id, scene.scene_id)), estimate_speech_duration(text))
        return out

    def render_sfx_cues(self, script: EpisodeScript, extra_cues: list[dict] | None = None) -> list[dict]:
        events: list[dict] = []
        sfx_dir = self.ctx.episode_dir(script.episode_id) / "sfx"
        seen: set[str] = set()
        for scene in script.scenes:
            for cue in scene.sfx_cues or []:
                name = Path(cue.file).stem
                path = sfx_dir / f"{name}.wav"
                if name not in seen or not path.exists():
                    self.sfx.render(name, path)
                    seen.add(name)
                events.append({"scene_id": scene.scene_id, "file": str(path), "timestamp": cue.timestamp, "duration": 0.6})
        for ev in extra_cues or []:
            name = Path(ev["file"]).stem
            path = sfx_dir / f"{name}.wav"
            if not path.exists():
                self.sfx.render(name, path)
            events.append({**ev, "file": str(path)})
        return events


def _duration(path: Path) -> float:
    from ..engines.ffmpeg_tools import probe_video

    try:
        return probe_video(path)["duration"]
    except Exception:
        return estimate_speech_duration("x" * 20)


__all__ = ["AudioAgent"]
