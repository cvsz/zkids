from __future__ import annotations

import os
import time
from pathlib import Path

from ..base import EngineNotConfigured, MotionEngine


class VeoMotionEngine(MotionEngine):
    """Google Veo image-to-video adapter (Veo 3.1: 8s clips, first-frame + up to 3 reference images)."""

    name = "veo"

    MODEL_DEFAULT = "veo-3.1-generate-preview"
    POLL_INTERVAL_SEC = 10
    POLL_TIMEOUT_SEC = 600

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ZKID_GOOGLE_API_KEY") or ""
        self.model = model or os.environ.get("ZKID_VEO_MODEL") or self.MODEL_DEFAULT
        if not self.api_key:
            raise EngineNotConfigured("veo requires ZKID_GOOGLE_API_KEY; install zkid[google]")

    def _client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise EngineNotConfigured("google-genai package not installed (zkid[google])") from exc
        return genai.Client(api_key=self.api_key)

    def generate_scene_video(
        self,
        still_path: Path,
        prompt: str,
        duration: float,
        out_path: Path,
        reference_images: list[Path] | None = None,
    ) -> dict:
        from google.genai import types

        client = self._client()
        first_frame = types.Image(image_bytes=still_path.read_bytes(), mime_type="image/png")
        refs = []
        for ref in (reference_images or [])[:3]:
            if ref.exists():
                refs.append(types.Image(image_bytes=ref.read_bytes(), mime_type="image/png"))
        config = types.GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=int(min(max(duration, 4), 8)),
            number_of_videos=1,
            reference_images=refs or None,
        )
        operation = client.models.generate_videos(
            model=self.model,
            prompt=prompt,
            image=first_frame,
            config=config,
        )
        deadline = time.monotonic() + self.POLL_TIMEOUT_SEC
        while not operation.done:
            if time.monotonic() > deadline:
                raise TimeoutError(f"veo generation exceeded {self.POLL_TIMEOUT_SEC}s")
            time.sleep(self.POLL_INTERVAL_SEC)
            operation = client.operations.get(operation)
        if operation.error:
            raise RuntimeError(f"veo operation failed: {operation.error}")
        generated = operation.response.generated_videos[0]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        client.files.download(file=generated.video)
        generated.video.save(str(out_path))
        return {"provider": self.name, "model": self.model, "duration": duration, "path": str(out_path)}


__all__ = ["VeoMotionEngine"]
