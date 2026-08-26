from __future__ import annotations

import hashlib
from pathlib import Path

from ..base import MotionEngine
from ..ffmpeg_tools import run_ffmpeg


class KenBurnsMotionEngine(MotionEngine):
    """Offline motion: cinematic pan/zoom over the scene still via FFmpeg zoompan."""

    name = "kenburns"

    def generate_scene_video(
        self,
        still_path: Path,
        prompt: str,
        duration: float,
        out_path: Path,
        reference_images: list[Path] | None = None,
    ) -> dict:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256((prompt + str(still_path)).encode()).hexdigest()
        direction = int(digest[:4], 16) % 4
        fps = 24
        frames = max(int(duration * fps), 1)
        cycles = max(duration / 2.6, 1)
        zoom_expr = f"min(1+0.0018*on/{max(frames,1)}*{frames},1.14)"
        bob = f"+ih*0.008*sin(2*PI*on/{frames}*{cycles:.2f})"
        pan = [
            f"x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2{bob}'",
            f"x='(iw-iw/zoom)*(on/{frames})':y='ih/2-(ih/zoom)/2{bob}'",
            f"x='iw/2-(iw/zoom)/2':y='(ih-ih/zoom)*(on/{frames})'",
            f"x='(iw-iw/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom)/2{bob}'",
        ][direction]
        vf = (
            f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
            f"zoompan=z='{zoom_expr}':{pan}:d={frames}:s=1280x720:fps={fps},"
            f"format=yuv420p"
        )
        run_ffmpeg(
            [
                "-loop", "1",
                "-i", str(still_path),
                "-vf", vf,
                "-t", f"{duration:.3f}",
                "-r", str(fps),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                str(out_path),
            ],
            timeout=900,
        )
        return {"provider": self.name, "model": "zoompan", "duration": duration, "path": str(out_path)}


__all__ = ["KenBurnsMotionEngine"]
