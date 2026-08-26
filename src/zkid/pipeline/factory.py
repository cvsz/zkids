from __future__ import annotations

import json
from pathlib import Path

from ..agents import (
    AudioAgent,
    CharacterAgent,
    EditorAgent,
    FactoryContext,
    ImageAgent,
    ManifestGenerator,
    MotionAgent,
    PublishingAgent,
    QCAgent,
    StoryAgent,
    StoryboardAgent,
    default_episode_id,
)
from ..config import FactoryConfig
from ..logging import get_logger
from ..models import CharacterLook, CharacterSpec, SeriesBible, VoiceProfile

log = get_logger("zkid.factory")

FALLBACK_CHARACTER = CharacterSpec(
    character_id="MIMI-001",
    name="Mimi",
    species="rabbit",
    age_appearance="small childlike",
    look=CharacterLook(
        body=["short body", "large rounded head", "short arms", "short legs"],
        face=["round face", "large dark-brown eyes", "tiny pink triangular nose", "soft cheeks"],
        fur=["white fur", "light pink inner ears"],
        clothing=["yellow short-sleeve shirt", "blue overalls", "white shoes"],
    ),
    personality=["curious", "friendly", "energetic", "empathetic"],
    signature_actions=["tilts head when curious", "small jump when excited", "ears move when surprised"],
    never_change=[
        "eye color",
        "fur color",
        "clothing palette",
        "ear proportions",
        "body proportions",
        "facial proportions",
    ],
    voice=VoiceProfile(voice_id="MIMI_VOICE_001"),
)


class EpisodeFactory:
    def __init__(self, cfg: FactoryConfig, draft: bool = True) -> None:
        self.cfg = cfg
        self.ctx = FactoryContext.create(cfg, draft=draft)

    @classmethod
    def create(cls, cfg: FactoryConfig, draft: bool) -> "EpisodeFactory":
        if draft:
            cfg.providers.update({
                "llm": "offline",
                "image": "procedural_cartoon",
                "voice": "silent",
                "music": "procedural",
                "motion": "kenburns",
            })
        return cls(cfg, draft)

    def load_series(self) -> SeriesBible | None:
        path = self.cfg.templates_dir / "series-bible.json"
        if path.exists():
            series = SeriesBible.model_validate_json(path.read_text(encoding="utf-8"))
            self.ctx.repo.save_series(series)
            return series
        return None

    def characters(self):
        agent = CharacterAgent(self.cfg, self.ctx.repo)
        specs = agent.load_templates()
        if not specs:
            log.warning("no character templates found; installing fallback Mimi spec")
            path = self.cfg.templates_dir / "characters" / f"{FALLBACK_CHARACTER.character_id}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(FALLBACK_CHARACTER.model_dump_json(indent=2), encoding="utf-8")
            specs = [FALLBACK_CHARACTER]
            for s in specs:
                self.ctx.repo.save_character(s)
        refs_map = agent.ensure_reference_sheets(specs)
        char_map = {c.character_id: c for c in specs}
        scene_refs = {cid: [r for r in views.values() if Path(r).exists()] for cid, views in refs_map.items()}
        return char_map, scene_refs

    def run_story(self, topic: str, episode_id: str | None, offline: bool):
        eid = episode_id or default_episode_id(topic)
        series = self.load_series()
        chars, _ = self.characters()
        script = StoryAgent(self.cfg, self.ctx.repo).run(topic, eid, series, list(chars.values()), offline=offline)
        return eid, script

    def preflight_gates(self, episode_id: str) -> None:
        self.ctx.gates.require(1, episode_id, draft_mode=self.ctx.draft)
        self.ctx.gates.require(2, episode_id, draft_mode=self.ctx.draft)

    def generate_scenes(self, episode_id: str):
        script = self.ctx.repo.get_episode_script(episode_id)
        sb = self.ctx.repo.get_storyboard(episode_id) or StoryboardAgent(self.cfg, self.ctx.repo).run(script)
        char_map, scene_refs = self.characters()
        manifest = ManifestGenerator(self.cfg, self.ctx.repo).run(script, sb, scene_refs)
        audio_agent = AudioAgent(self.ctx)
        voice_files = audio_agent.generate_voice(script, char_map, quality_tier=None)
        sfx_events = audio_agent.render_sfx_cues(script)
        image_agent = ImageAgent(self.ctx)
        series = self.load_series()
        style = series.visual_style.type if series else "soft 3D children's animation"
        stills = image_agent.generate_stills(manifest, char_map, style, quality_tier=None, script=script)
        motion_agent = MotionAgent(self.ctx)
        videos = motion_agent.generate_videos(manifest, char_map, stills, quality_tier=None)
        return script, manifest, voice_files, sfx_events, videos

    def approve_scene_generation(self, episode_id: str, videos: dict) -> bool:
        jobs = self.ctx.repo.jobs_for_episode(episode_id)
        video_jobs = [j for j in jobs if j.kind.value == "VIDEO"]
        all_ok = bool(video_jobs) and all(j.state.value == "APPROVED" for j in video_jobs) and len(videos) > 0
        status = "approved" if all_ok else "rejected"
        note = "system-qc: all scene jobs APPROVED" if all_ok else "system-qc: some scenes in retry/manual review"
        self.ctx.repo.set_gate(3, episode_id, status, note, "system-qc")
        if not all_ok:
            missing = [j.job_id for j in video_jobs if j.state.value != "APPROVED"]
            log.warning("gate 3 blocked by scenes", extra={"episode_id": episode_id, "stage": ", ".join(missing[:6])})
        return all_ok

    def assemble_and_render(self, episode_id: str):
        script = self.ctx.repo.get_episode_script(episode_id)
        manifest = self.ctx.repo.get_manifest(episode_id)
        editor = EditorAgent(self.ctx)
        audio_agent = AudioAgent(self.ctx)
        char_map, _ = self.characters()
        voice_files = {}
        for scene in script.scenes:
            p = audio_agent.voice_path(episode_id, scene.scene_id)
            if p.exists():
                from ..engines.ffmpeg_tools import probe_video

                try:
                    dur = probe_video(p)["duration"]
                except Exception:
                    dur = 0.0
                voice_files[scene.scene_id] = (str(p), dur)
        scene_videos: dict[str, str] = {}
        for row in self.ctx.db.query_all(
            "SELECT scene_id, artifacts FROM generation_jobs WHERE episode_id=? AND kind='VIDEO' AND state='APPROVED'",
            (episode_id,),
        ):
            arts = json.loads(row["artifacts"])
            if not arts:
                continue
            shot_scene = row["scene_id"] or ""
            base = shot_scene.split("-")[0]
            if base not in scene_videos or shot_scene.endswith("-HERO"):
                scene_videos[base] = str(Path(arts[0]))
        timeline, render_path = editor.assemble(script, manifest, scene_videos, voice_files)
        return script, manifest, timeline, render_path

    def final_qc_and_gate4(self, episode_id: str, render_path: Path, expected_duration: float) -> tuple[bool, dict]:
        w, h, fps = self.cfg.baseline(self.ctx.draft)
        report = QCAgent(self.ctx).check_final(
            episode_id, render_path, expected_duration, w, h, fps, require_nonsilent=False
        )
        ok, details = report
        status = "approved" if ok else "rejected"
        self.ctx.repo.set_gate(4, episode_id, status, f"automated QC: {json.dumps(details)[:200]}", "system-qc")
        self.ctx.repo.save_render(f"{episode_id}-{'draft' if self.ctx.draft else 'final'}", episode_id, "draft" if self.ctx.draft else "final", str(render_path), "passed" if ok else "failed", expected_duration)
        return ok, details

    def produce(
        self,
        topic: str,
        episode_id: str | None = None,
        offline: bool = False,
        force_approve_publish: bool = False,
    ) -> Path:
        eid, script = self.run_story(topic, episode_id, offline)
        self.preflight_gates(eid)
        script, manifest, voice_files, sfx_events, videos = self.generate_scenes(eid)
        self.approve_scene_generation(eid, videos)
        self.ctx.gates.require(3, eid, draft_mode=self.ctx.draft)
        _, _, timeline, render_path = self.assemble_and_render(eid)
        ok, _details = self.final_qc_and_gate4(eid, render_path, timeline.total_duration())
        if not ok:
            raise RuntimeError("final QC failed; see qc_results")
        if force_approve_publish:
            self.ctx.gates.approve(5, eid, note="explicit CLI override", approver="cli-override")
        self.ctx.gates.require(5, eid, draft_mode=False)
        PublishingAgent(self.ctx).build_package(
            eid, script.title, script.topic, script.learning_goal
        )
        self.ctx.repo.set_episode_state(eid, "master-ready")
        log.info("produce complete", extra={"episode_id": eid, "stage": str(render_path)})
        return render_path
