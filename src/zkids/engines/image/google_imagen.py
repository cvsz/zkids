from __future__ import annotations

import os
from pathlib import Path

from ..base import EngineNotConfigured, ImageEngine


class GoogleImagenEngine(ImageEngine):
    name = "google_imagen"

    MODEL_DEFAULT = "imagen-3.0-generate-002"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ZKID_GOOGLE_API_KEY") or ""
        self.model = model or os.environ.get("ZKID_IMAGE_MODEL") or self.MODEL_DEFAULT
        if not self.api_key:
            raise EngineNotConfigured(
                "google_imagen requires ZKID_GOOGLE_API_KEY; install zkid[google]"
            )

    def _client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise EngineNotConfigured("google-genai package not installed (zkid[google])") from exc
        return genai.Client(api_key=self.api_key)

    def generate_still(self, prompt: str, negative: str, out_path: Path, seed: int | None = None,
                       context: dict | None = None) -> dict:
        from google.genai import types

        client = self._client()
        config = types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="16:9",
            negative_prompt=negative or None,
            seed=seed,
        )
        response = client.models.generate_images(
            model=self.model,
            prompt=prompt,
            config=config,
        )
        image = response.generated_images[0]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(image.image.image_bytes)
        return {
            "provider": self.name,
            "model": self.model,
            "seed": seed,
            "path": str(out_path),
            "filtered": bool(getattr(response, "filtered_reason", "")),
        }
