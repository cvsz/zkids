from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from ..base import EngineNotConfigured


class OllamaLLM:
    """Free local LLM via Ollama (http://127.0.0.1:11434). No API key, fully offline after pull."""

    name = "ollama"

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: int = 120) -> None:
        self.base_url = (base_url or os.environ.get("ZKID_OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.environ.get("ZKID_OLLAMA_MODEL") or "qwen2.5:3b"
        self.timeout = timeout

    def _check(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=5) as r:
                if r.status != 200:
                    raise EngineNotConfigured(f"Ollama not reachable at {self.base_url}")
        except Exception as e:
            raise EngineNotConfigured(f"Ollama not reachable at {self.base_url}: {e}. Run: ollama serve & ollama pull {self.model}") from e

    def generate_json(self, system: str, user: str) -> dict:
        self._check()
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system + "\nRespond with a single valid JSON object only. No markdown."},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.7, "num_predict": 2000},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
                content = body.get("message", {}).get("content", "") or body.get("response", "")
                return json.loads(_extract_json(content))
        except urllib.error.HTTPError as e:
            raise EngineNotConfigured(f"Ollama error {e.code}: {e.read().decode()[:400]}") from e

    def generate_text(self, prompt: str) -> str:
        self._check()
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{self.base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode())
            return body.get("response", "")


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        return text[s:e+1]
    return text
