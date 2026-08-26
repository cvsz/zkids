from __future__ import annotations

import hashlib
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from ..base import EngineNotConfigured, ImageEngine


class PollinationsImageEngine(ImageEngine):
    """Free image generation — no API key. https://image.pollinations.ai (Pollinations AI, Flux/SD)."""

    name = "pollinations"

    BASE = "https://image.pollinations.ai/prompt"

    def __init__(self, width: int = 1280, height: int = 720, model: str | None = None, timeout: int = 90) -> None:
        self.width = width
        self.height = height
        self.model = model or os.environ.get("ZKID_POLLINATIONS_MODEL") or "flux"
        self.timeout = timeout

    def generate_still(self, prompt: str, negative: str, out_path: Path, seed: int | None = None, context: dict | None = None) -> dict:
        # Use deterministic seed from prompt if not provided
        if seed is None:
            seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16) % 2147483647
        # Enhance prompt for kids cartoon style if not already
        style_suffix = ", soft 3D children's animation, warm soft lighting, bright pastel, Pixar-like, high detail, 16:9"
        if "children" not in prompt.lower():
            prompt = prompt[:1200] + style_suffix
        if negative:
            prompt += f" --negative {negative[:300]}"
        encoded = urllib.parse.quote(prompt, safe="")
        qs = urllib.parse.urlencode({
            "width": self.width,
            "height": self.height,
            "seed": seed,
            "model": self.model,
            "nologo": "true",
            "enhance": "false",
        })
        url = f"{self.BASE}/{encoded}?{qs}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "zkid/0.1", "Accept": "image/*"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    raise EngineNotConfigured(f"Pollinations HTTP {resp.status}")
                data = resp.read()
                if len(data) < 5000 or data[:4] == b"<htm":
                    raise EngineNotConfigured(f"Pollinations returned invalid image ({len(data)} bytes)")
                out_path.write_bytes(data)
        except (urllib.error.HTTPError, urllib.error.URLError, EngineNotConfigured) as e:
            # Fallback to offline procedural cartoon so free tier never hard-fails
            try:
                from .cartoon import ProceduralCartoonEngine
                fallback = ProceduralCartoonEngine()
                info = fallback.generate_still(prompt, negative, out_path, seed=seed, context=context)
                info["fallback_from"] = self.name
                info["fallback_reason"] = str(e)[:200]
                return info
            except Exception as fe:
                raise EngineNotConfigured(f"Pollinations failed ({e}) and fallback also failed ({fe})") from e
        return {"provider": self.name, "model": self.model, "seed": seed, "path": str(out_path)}
