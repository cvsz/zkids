from __future__ import annotations

from pathlib import Path

from ..assembly import TimelineEngine, build_subtitles, concat_clips, conform_clip, mix_and_mux, render_srt
from ..config import FactoryConfig
from ..db.repo import FactoryRepository
from ..engines.registry import build_music_engine
from ..logging import get_logger
from ..models import EpisodeScript, EpisodeTimeline, SceneManifest
from .base import FactoryContext
from .qc_agent import QCAgent

log = get_logger("zkid.editor")


class EditorAgent:
    def __init__(self, ctx: FactoryContext) -> None:
        self.ctx = ctx
        self.cfg: FactoryConfig = ctx.cfg
        self.repo: FactoryRepository = ctx.repo
        self.music_engine = build_music_engine(self.cfg)

    def assemble(
        self,
        script: EpisodeScript,
        manifest: SceneManifest,
        scene_videos: dict[str, str],
        voice_files: dict[str, tuple[str, float]],
        sfx_events: list[dict] | None = None,
    ) -> tuple[EpisodeTimeline, Path]:
        ep_dir = self.ctx.episode_dir(script.episode_id)
        engine = TimelineEngine(self.cfg, draft=self.ctx.draft)
        timeline = engine.build(script, manifest, scene_videos, voice_files, sfx_events)
        (ep_dir / "metadata" / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")

        w, h, fps = self.cfg.baseline(self.ctx.draft)
        conformed_dir = ep_dir / "video" / "conformed"
        conformed: list[Path] = []
        for clip in timeline.tracks["video"]:
            dst = conformed_dir / f"{clip.scene_id}.mp4"
            conform_clip(Path(clip.src), dst, w, h, fps, clip.duration, self.cfg.master.sample_rate, self.cfg.master.channels)
            conformed.append(dst)

        silent_cut = ep_dir / "output" / "_silent_cut.mp4"
        concat_clips(conformed, silent_cut)

        music_clips = []
        for i, mc in enumerate(timeline.tracks["music"]):
            cue = mc.label or "playful"
            path = ep_dir / "music" / f"M{i}_{cue}.wav"
            if not path.exists() or path.stat().st_size == 0:
                self.music_engine.render_bed(cue, mc.duration, path)
            music_clips.append((mc.start, path, mc.duration))

        voice_paths = [(vc.start, Path(vc.src), vc.duration) for vc in timeline.tracks["voice"]]
        sfx_paths = [(ev.start, Path(ev.src), ev.duration) for ev in timeline.tracks["sfx"]]

        mode = "draft" if self.ctx.draft else "final"
        out = ep_dir / "output" / ("draft.mp4" if self.ctx.draft else "final.mp4")
        duck_ratio = self.cfg.audio.music_ducking_ratio if not self.ctx.draft else 0.5
        mix_and_mux(silent_cut, voice_paths, music_clips, sfx_paths, out, ducking_ratio=duck_ratio)

        subs = build_subtitles(timeline)
        srt_path = ep_dir / "subtitles" / f"{script.episode_id}_{mode}.srt"
        render_srt(subs, srt_path)

        total = timeline.total_duration()
        self.repo.save_render(f"{script.episode_id}-{mode}", script.episode_id, mode, str(out), "pending", total)
        log.info(
            "render complete",
            extra={"episode_id": script.episode_id, "stage": f"{mode} {total:.1f}s -> {out.name}"},
        )
        return timeline, out


__all__ = ["EditorAgent"]
