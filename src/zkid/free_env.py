from __future__ import annotations

import os
from pathlib import Path

_ENV_AI = Path.home() / "zworkforce" / ".env.ai"
_ZKID_ENV = Path(__file__).parents[2] / ".env"

def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v:
            data[k] = v
    return data

def load_free_env() -> dict[str, str]:
    """Load zworkforce/.env.ai into os.environ without overwriting existing vars."""
    loaded: dict[str, str] = {}
    for path in (_ENV_AI, _ZKID_ENV):
        for k, v in _parse_env_file(path).items():
            if k not in os.environ:
                os.environ[k] = v
                loaded[k] = v
            # also track even if already set, for catalog
            if k not in loaded:
                loaded[k] = os.environ.get(k, v)
    return loaded

FREE_CATALOG = None

def get_free_catalog() -> dict:
    global FREE_CATALOG
    if FREE_CATALOG is not None:
        return FREE_CATALOG
    load_free_env()
    FREE_CATALOG = {
        "llm": [
            {"provider": "ollama", "model": os.environ.get("OLLAMA_NATIVE_BASE_URL") and "qwen2.5:3b" or "qwen2.5:3b", "base_url": os.environ.get("OLLAMA_NATIVE_BASE_URL") or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), "env_key": "OLLAMA_API_KEY", "free": True, "offline": True, "desc": "Local Qwen 3B via Ollama — no key, privacy"},
            {"provider": "openrouter_free", "model": os.environ.get("OPENROUTER_FREE_MODEL") or "z-ai/glm-5.2:free", "base_url": os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"), "env_key": "OPENROUTER_API_KEY", "free": True, "desc": "OpenRouter free — 200 req/day, uses OPENROUTER_API_KEY"},
            {"provider": "groq_free", "model": os.environ.get("GROQ_FREE_MODEL") or "openai/gpt-oss-20b", "base_url": os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"), "env_key": "GROQ_API_KEY", "free": True, "desc": "Groq free ultra-fast"},
            {"provider": "gemini_free", "model": os.environ.get("GEMINI_FREE_MODEL") or "gemini-2.5-flash-lite", "base_url": os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"), "env_key": "GEMINI_API_KEY", "free": True, "desc": "Gemini 2.5 Flash Lite free"},
            {"provider": "nvidia_free", "model": os.environ.get("MODEL_META_MUSE_SPARK_1_2") or "meta/llama-3.1-8b-instruct", "base_url": os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"), "env_key": "NVIDIA_API_KEY", "free": True, "desc": "NVIDIA free — Llama 8B via NVIDIA_API_KEY"},
            {"provider": "opencode_free", "model": "qwen/qwen2.5-coder-32b", "base_url": os.environ.get("OPENCODE_ZEN_BASE_URL") or os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1"), "env_key": "OPENCODE_API_KEY", "free": True, "desc": "OpenCode free — Qwen Coder via OPENCODE_API_KEY (zen)"},
            {"provider": "kilocode_free", "model": "glm-4.5-flash", "base_url": os.environ.get("KILO_BASE_URL", "https://api.z.ai/v1"), "env_key": "KILO_API_KEY", "free": True, "desc": "KiloCode/Z.AI free — GLM 4.5 via KILO_API_KEY"},
            {"provider": "meta_free", "model": "muse-spark-1.2-contributor", "base_url": os.environ.get("META_BASE_URL") or "https://api.meta.ai/v1", "env_key": "META_API_KEY", "free": True, "desc": "Meta free — Muse Spark 1.2 via META_API_KEY (api.meta.ai)"},
            {"provider": "hf_free", "model": "meta-llama/Llama-3.2-3B-Instruct", "base_url": os.environ.get("HF_ROUTER_BASE_URL") or os.environ.get("HF_BASE_URL", "https://router.huggingface.co/v1"), "env_key": "HF_API_KEY", "free": True, "desc": "HF Inference free 30k/mo"},
            {"provider": "zai_free", "model": "glm-4.5-flash", "base_url": os.environ.get("ZAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"), "env_key": "ZAI_API_KEY", "free": True, "desc": "Zhipu GLM free"},
            {"provider": "offline", "model": "deterministic", "base_url": "", "env_key": "", "free": True, "offline": True, "desc": "Deterministic template — zero AI, always works"},
        ],
        "image": [
            {"provider": "procedural_cartoon", "model": "pillow-cartoon", "free": True, "offline": True, "desc": "Code-drawn cartoon — offline, no key, instant"},
            {"provider": "pollinations", "model": "flux", "base_url": "https://image.pollinations.ai/prompt", "free": True, "desc": "Pollinations Flux/SD — free API no key"},
            {"provider": "hf_image", "model": "stabilityai/sdxl", "base_url": os.environ.get("HF_BASE_URL", "https://api-inference.huggingface.co"), "env_key": "HF_API_KEY", "free": True, "desc": "HF SDXL free"},
            {"provider": "placeholder", "model": "lavfi-gradients", "free": True, "offline": True, "desc": "Gradient placeholder — offline"},
        ],
        "voice": [
            {"provider": "edge_tts", "model": "en-US-AriaNeural", "free": True, "desc": "Edge TTS neural 40+ voices — free no key"},
            {"provider": "silent", "model": "silence", "free": True, "offline": True, "desc": "Timed silence — offline, correct duration"},
        ],
        "music": [
            {"provider": "procedural", "model": "sine-beds", "free": True, "offline": True, "desc": "Procedural sine beds — offline"},
        ],
        "motion": [
            {"provider": "kenburns", "model": "zoompan+bob", "free": True, "offline": True, "desc": "FFmpeg zoompan — offline, free"},
        ],
    }
    return FREE_CATALOG
