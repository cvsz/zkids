from __future__ import annotations

import hashlib
from pathlib import Path

from ..base import MusicEngine
from ..ffmpeg_tools import run_ffmpeg

CUE_FILTERS: dict[str, str] = {
    "opening": "sine=frequency=262,volume=0.25",
    "playful": "sine=frequency=330,tremolo=f=5:d=0.6,volume=0.22",
    "discovery": "sine=frequency=392,tremolo=f=3:d=0.4,volume=0.2",
    "learning-song": "sine=frequency=294,vibrato=f=4:d=0.3,volume=0.24",
    "ending": "sine=frequency=220,tremolo=f=2:d=0.5,volume=0.2",
}

SFX_RECIPES: dict[str, dict] = {
    "pop": {"freq": 620, "duration": 0.28, "tremolo": 18},
    "jump": {"freq": 480, "duration": 0.35, "tremolo": 12},
    "sparkle": {"freq": 1568, "duration": 0.45, "tremolo": 9},
    "magic": {"freq": 1046, "duration": 0.6, "tremolo": 7},
    "bird": {"freq": 1200, "duration": 0.3, "tremolo": 14},
    "footsteps": {"freq": 200, "duration": 0.5, "tremolo": 6},
}


class ProceduralMusicEngine(MusicEngine):
    """Generates simple sine-bed cues as royalty-free placeholder music."""

    name = "procedural"

    def render_bed(self, cue_name: str, duration: float, out_path: Path) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        parts = CUE_FILTERS.get(cue_name, CUE_FILTERS["playful"]).split(",")
        source = parts[0]
        fx = parts[1:]
        fade_out = min(2.0, max(0.5, duration * 0.15))
        filter_chain = ",".join(
            fx
            + [
                f"afade=t=in:st=0:d=1",
                f"afade=t=out:st={max(0.0, duration - fade_out):.2f}:d={fade_out:.2f}",
                "aformat=sample_rates=48000:channel_layouts=stereo",
            ]
        )
        run_ffmpeg(
            [
                "-f", "lavfi",
                "-i", source,
                "-af", filter_chain,
                "-t", f"{duration:.3f}",
                "-c:a", "pcm_s16le",
                str(out_path),
            ]
        )
        return {"provider": self.name, "model": cue_name, "duration": duration, "path": str(out_path)}


class ProceduralSFXLibrary:
    name = "procedural_sfx"

    def render(self, effect: str, out_path: Path) -> dict:
        recipe_key = effect if effect in SFX_RECIPES else _match_effect(effect)
        recipe = SFX_RECIPES[recipe_key]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        d = recipe["duration"]
        freq = recipe["freq"]
        run_ffmpeg(
            [
                "-f", "lavfi",
                "-i", f"sine=frequency={freq}:duration={d}",
                "-af",
                (
                    f"tremolo=f={recipe['tremolo']}:d=0.8,"
                    f"afade=t=in:st=0:d=0.02,afade=t=out:st={d * 0.4:.3f}:d={d * 0.6:.3f},"
                    "aformat=sample_rates=48000:channel_layouts=stereo"
                ),
                "-c:a", "pcm_s16le",
                str(out_path),
            ]
        )
        return {"provider": self.name, "model": recipe_key, "duration": d, "path": str(out_path)}


def _match_effect(effect: str) -> str:
    e = effect.lower()
    for key in SFX_RECIPES:
        if key in e or e in key:
            return key
    idx = int(hashlib.sha256(effect.encode()).hexdigest()[:6], 16) % len(SFX_RECIPES)
    return list(SFX_RECIPES.keys())[idx]


__all__ = ["ProceduralMusicEngine", "ProceduralSFXLibrary"]
