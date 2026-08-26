from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/factory.yaml")


@dataclass
class MasterBaseline:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    sample_rate: int = 48000
    channels: int = 2


@dataclass
class DraftBaseline:
    width: int = 640
    height: int = 360
    fps: int = 24


@dataclass
class Budgets:
    image_generations: int = 40
    video_generations: int = 35
    max_retries_per_scene: int = 3
    max_cost_usd_per_episode: float = 50.0


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    escalation: dict[int, str] = field(default_factory=dict)

    def strategy_for_attempt(self, attempt: int) -> str | None:
        return self.escalation.get(attempt)


@dataclass
class AudioConfig:
    dialogue_lufs_target: float = -16.0
    music_ducking_ratio: float = 0.25
    padding_after_voice_sec: float = 0.6


@dataclass
class FactoryConfig:
    root: Path
    db_path: Path
    episodes_dir: Path
    templates_dir: Path
    master: MasterBaseline = field(default_factory=MasterBaseline)
    draft: DraftBaseline = field(default_factory=DraftBaseline)
    budgets: Budgets = field(default_factory=Budgets)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    audio: AudioConfig = field(default_factory=AudioConfig)
    providers: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "offline",
            "image": "placeholder",
            "voice": "silent",
            "music": "procedural",
            "motion": "kenburns",
        }
    )
    auto_approve_in_draft: list[int] = field(default_factory=lambda: [1, 2])

    @classmethod
    def load(cls, root: Path | None = None, config_path: Path | None = None) -> "FactoryConfig":
        root = (root or Path.cwd()).resolve()
        path = config_path or root / DEFAULT_CONFIG_PATH
        raw: dict = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        f = raw.get("factory", {})
        master_raw = raw.get("master_baseline", {})
        video_raw = master_raw.get("video", {})
        audio_master = master_raw.get("audio", {})
        draft_raw = raw.get("draft_baseline", {})
        budgets = Budgets(**(raw.get("budgets") or {}))
        retry_raw = raw.get("retry_policy") or {}
        retry = RetryPolicy(
            max_attempts=int(retry_raw.get("max_attempts", 3)),
            escalation={int(k): v for k, v in (retry_raw.get("escalation") or {}).items()},
        )
        audio = AudioConfig(**(raw.get("audio") or {}))
        gates = raw.get("gates") or {}
        providers_raw = raw.get("providers") or {}
        cfg = cls(
            root=root,
            db_path=root / f.get("db_path", "factory.db"),
            episodes_dir=root / f.get("episodes_dir", "episodes"),
            templates_dir=root / f.get("templates_dir", "templates"),
            master=MasterBaseline(
                width=int(video_raw.get("width", 1920)),
                height=int(video_raw.get("height", 1080)),
                fps=int(video_raw.get("fps", 30)),
                sample_rate=int(audio_master.get("sample_rate", 48000)),
                channels=int(audio_master.get("channels", 2)),
            ),
            draft=DraftBaseline(
                width=int(draft_raw.get("width", 640)),
                height=int(draft_raw.get("height", 360)),
                fps=int(draft_raw.get("fps", 24)),
            ),
            budgets=budgets,
            retry=retry,
            audio=audio,
            providers={**cfg_env_overrides(), **providers_raw},
            auto_approve_in_draft=[int(g) for g in gates.get("auto_approve_in_draft", [1, 2])],
        )
        cfg.episodes_dir.mkdir(parents=True, exist_ok=True)
        cfg.templates_dir.mkdir(parents=True, exist_ok=True)
        return cfg

    def baseline(self, draft: bool) -> tuple[int, int, int]:
        if draft:
            return self.draft.width, self.draft.height, self.draft.fps
        return self.master.width, self.master.height, self.master.fps

    def episode_dir(self, episode_id: str) -> Path:
        d = self.episodes_dir / episode_id.lower()
        for sub in (
            "metadata",
            "characters",
            "stills",
            "video",
            "voice",
            "music",
            "sfx",
            "subtitles",
            "output",
            "provenance",
        ):
            (d / sub).mkdir(parents=True, exist_ok=True)
        return d


def cfg_env_overrides() -> dict[str, str]:
    out: dict[str, str] = {}
    mapping = {
        "ZKID_LLM_PROVIDER": "llm",
        "ZKID_IMAGE_PROVIDER": "image",
        "ZKID_VOICE_PROVIDER": "voice",
        "ZKID_MUSIC_PROVIDER": "music",
        "ZKID_MOTION_PROVIDER": "motion",
    }
    for env_key, provider_key in mapping.items():
        v = os.environ.get(env_key)
        if v:
            out[provider_key] = v
    return out
