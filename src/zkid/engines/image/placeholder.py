from __future__ import annotations

import hashlib
from pathlib import Path

from ..base import ImageEngine
from ..ffmpeg_tools import has_filter, run_ffmpeg

PALETTES = [
    ("#aee1f9", "#fdf6e3"),
    ("#ffd6e0", "#fff7f0"),
    ("#d4f0c0", "#fefae0"),
    ("#e2d5f8", "#fbeff5"),
    ("#ffe9b3", "#fffdf5"),
    ("#bfe6d4", "#f4fbf7"),
]


def _sanitize(text: str, limit: int = 60) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " ,-." else " " for ch in text)
    return cleaned.strip()[:limit] or "scene"


class PlaceholderImageEngine(ImageEngine):
    """Deterministic gradient stills so image QC and motion run without any API key."""

    name = "placeholder"

    def generate_still(self, prompt: str, negative: str, out_path: Path, seed: int | None = None,
                       context: dict | None = None) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256((prompt + str(seed)).encode()).hexdigest()
        idx = int(digest[:8], 16) % len(PALETTES)
        c0, c1 = PALETTES[idx]
        label = _sanitize(prompt)
        args = [
            "-f", "lavfi",
            "-i", f"gradients=s=1280x720:c0={c0}:c1={c1}:n=2",
            "-frames:v", "1",
        ]
        if has_filter("drawtext"):
            args += ["-vf", f"drawtext=text='{label}':fontcolor=0x33334dcc:fontsize=40:x=(w-tw)/2:y=h*0.82"]
        args += [str(out_path)]
        run_ffmpeg(args)
        return {"provider": self.name, "model": "lavfi-gradients", "seed": seed, "path": str(out_path)}
