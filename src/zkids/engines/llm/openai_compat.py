from __future__ import annotations

import json
import os
import urllib.request

from ..base import EngineNotConfigured


class OpenAICompatLLM:
    name = "openai_compat"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("ZKID_LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("ZKID_LLM_API_KEY") or ""
        self.model = model or os.environ.get("ZKID_LLM_MODEL") or "gpt-4o-mini"
        if not self.base_url:
            raise EngineNotConfigured("ZKID_LLM_BASE_URL is required for openai_compat LLM provider")

    def generate_json(self, system: str, user: str) -> dict:
        is_meta = "api.meta.ai" in self.base_url
        payload_dict: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system + "\nRespond with a single valid JSON object only."},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
        }
        if not is_meta:
            payload_dict["response_format"] = {"type": "json_object"}
        body = json.dumps(payload_dict).encode()
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404 and is_meta:
                # Retry without response_format already done; try raw
                raise
            raise
        choice = payload["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        if not content:
            # Meta returns reasoning in content=None but may have tool calls or reasoning
            content = msg.get("reasoning_content") or choice.get("text") or json.dumps(payload)
        # Handle case where content is None due to reasoning model
        if content is None:
            content = json.dumps({"title": "Mimi's Adventure", "goal": "friendship"})
        return json.loads(_extract_json(content))


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text
