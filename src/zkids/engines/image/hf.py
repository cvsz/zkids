from __future__ import annotations

import os
import urllib.request
import urllib.error
import json
from pathlib import Path

from ..base import EngineNotConfigured, ImageEngine


class HFImageEngine(ImageEngine):
    """Free HuggingFace Inference image generation (SDXL, Flux) — uses HF_API_KEY."""

    name = "hf_image"

    def __init__(self, model: str | None = None, timeout: int = 90) -> None:
        self.model = model or os.environ.get("HF_IMAGE_MODEL") or "black-forest-labs/FLUX.1-schnell"
        self.api_key = os.environ.get("HF_API_KEY") or os.environ.get("HF_TOKEN") or ""
        self.base_url = os.environ.get("HF_BASE_URL") or "https://api-inference.huggingface.co"
        self.timeout = timeout
        if not self.api_key:
            raise EngineNotConfigured("HF image requires HF_API_KEY / HF_TOKEN from .env.ai (free)")

    def generate_still(self, prompt: str, negative: str, out_path: Path, seed: int | None = None, context: dict | None = None) -> dict:
        if negative:
            prompt = f"{prompt} --negative {negative[:200]}"
        # Use router endpoint if available
        url = f"{self.base_url.rstrip('/')}/models/{self.model}"
        if "router.huggingface.co" in self.base_url:
            url = f"{self.base_url.rstrip('/')}/hf-inference/models/{self.model}"
        payload = json.dumps({"inputs": prompt, "parameters": {"negative_prompt": negative} if negative else {}}).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if seed is not None:
            headers["X-Use-Cache"] = "false"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = resp.read()
                if resp.headers.get("content-type", "").startswith("application/json"):
                    # HF returns JSON error or base64?
                    try:
                        j = json.loads(data.decode())
                        if "error" in j:
                            raise EngineNotConfigured(f"HF error: {j.get('error')}")
                    except json.JSONDecodeError:
                        pass
                if len(data) < 5000:
                    raise EngineNotConfigured(f"HF returned too small ({len(data)} bytes)")
                out_path.write_bytes(data)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500] if e.fp else str(e)
            raise EngineNotConfigured(f"HF HTTP {e.code}: {body}") from e
        return {"provider": self.name, "model": self.model, "seed": seed, "path": str(out_path)}
