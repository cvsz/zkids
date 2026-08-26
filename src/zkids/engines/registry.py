from __future__ import annotations

import os

from ..config import FactoryConfig
from ..free_env import load_free_env
from .base import ImageEngine, LLMClient, MotionEngine, MusicEngine, VoiceEngine
from .image.google_imagen import GoogleImagenEngine
from .image.placeholder import PlaceholderImageEngine
from .llm.offline import OfflineLLM
from .llm.openai_compat import OpenAICompatLLM
from .motion.kenburns import KenBurnsMotionEngine
from .motion.veo import VeoMotionEngine
from .music.procedural import ProceduralMusicEngine, ProceduralSFXLibrary
from .voice.google_tts import GoogleTTSEngine
from .voice.silent import SilentVoiceEngine

load_free_env()


def build_llm(cfg: FactoryConfig) -> LLMClient:
    provider = cfg.providers.get("llm", "offline")
    if provider == "ollama":
        from .llm.ollama import OllamaLLM
        return OllamaLLM()
    if provider in ("openai_compat", "openrouter_free", "groq_free", "hf_free", "zai_free", "together_free", "nvidia_free", "opencode_free", "kilocode_free", "meta_free"):
        mapping = {
            "openrouter_free": (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1", os.environ.get("OPENROUTER_API_KEY"), os.environ.get("OPENROUTER_FREE_MODEL") or "openrouter/free"),
            "groq_free": (os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1", os.environ.get("GROQ_API_KEY"), os.environ.get("GROQ_FREE_MODEL") or "openai/gpt-oss-20b"),
            "hf_free": (os.environ.get("HF_ROUTER_BASE_URL") or os.environ.get("HF_BASE_URL") or "https://router.huggingface.co/v1", os.environ.get("HF_API_KEY") or os.environ.get("HF_TOKEN"), os.environ.get("HF_FREE_MODEL") or "meta-llama/Llama-3.2-3B-Instruct"),
            "zai_free": (os.environ.get("ZAI_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4", os.environ.get("ZAI_API_KEY"), "glm-4.5-flash"),
            "together_free": (os.environ.get("TOGETHER_BASE_URL") or "https://api.together.xyz/v1", os.environ.get("TOGETHER_API_KEY"), "meta-llama/Llama-3-8b-chat-hf"),
            "nvidia_free": (os.environ.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1", os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY"), os.environ.get("MODEL_META_MUSE_SPARK_1_2") or "meta/llama-3.1-8b-instruct"),
            "opencode_free": (os.environ.get("OPENCODE_ZEN_BASE_URL") or os.environ.get("OPENCODE_BASE_URL") or "https://opencode.ai/zen/v1", os.environ.get("OPENCODE_API_KEY"), "qwen/qwen2.5-coder-32b"),
            "kilocode_free": (os.environ.get("KILO_BASE_URL") or "https://api.z.ai/v1", os.environ.get("KILO_API_KEY"), "glm-4.5-flash"),
            "meta_free": (os.environ.get("META_BASE_URL") or "https://api.meta.ai/v1", os.environ.get("META_API_KEY") or os.environ.get("HF_API_KEY") or os.environ.get("HF_TOKEN"), "muse-spark-1.2-contributor"),
        }
        if provider in mapping:
            base_url, api_key, model = mapping[provider]
            return OpenAICompatLLM(base_url=base_url, api_key=api_key or "", model=model)
        return OpenAICompatLLM()
    if provider == "gemini_free":
        try:
            base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
            return OpenAICompatLLM(base_url=base.rstrip("/") + "/openai", api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "", model=os.environ.get("GEMINI_FREE_MODEL") or "gemini-2.5-flash-lite")
        except Exception:
            return OfflineLLM()
    if provider == "free":
        # Auto-select first available free that is configured
        for cand in ("ollama", "openrouter_free", "nvidia_free", "opencode_free", "groq_free", "kilocode_free", "meta_free", "hf_free"):
            try:
                cfg.providers["llm"] = cand
                return build_llm(cfg)
            except Exception:
                continue
        return OfflineLLM()
    return OfflineLLM()


def build_image_engine(cfg: FactoryConfig) -> ImageEngine:
    provider = cfg.providers.get("image", "placeholder")
    if provider == "google_imagen":
        return GoogleImagenEngine()
    if provider == "pollinations":
        from .image.pollinations import PollinationsImageEngine
        return PollinationsImageEngine()
    if provider in ("hf_image", "hf_free"):
        from .image.hf import HFImageEngine
        return HFImageEngine()
    if provider == "procedural_cartoon":
        from .image.cartoon import ProceduralCartoonEngine

        return ProceduralCartoonEngine()
    return PlaceholderImageEngine()


def build_voice_engine(cfg: FactoryConfig) -> VoiceEngine:
    provider = cfg.providers.get("voice", "silent")
    if provider == "google_tts":
        return GoogleTTSEngine()
    if provider == "edge_tts":
        from .voice.edge_tts import EdgeTTSEngine
        return EdgeTTSEngine()
    return SilentVoiceEngine()


def build_music_engine(cfg: FactoryConfig) -> MusicEngine:
    provider = cfg.providers.get("music", "procedural")
    if provider == "procedural":
        return ProceduralMusicEngine()
    raise ValueError(f"unknown music provider: {provider}")


def build_motion_engine(cfg: FactoryConfig) -> MotionEngine:
    provider = cfg.providers.get("motion", "kenburns")
    if provider == "veo":
        return VeoMotionEngine()
    if provider == "google_imagen":
        return GoogleImagenEngine()  # pragma: no cover - misconfig guard
    return KenBurnsMotionEngine()


def build_sfx_library(cfg: FactoryConfig):
    del cfg
    return ProceduralSFXLibrary()


__all__ = [
    "build_image_engine",
    "build_llm",
    "build_motion_engine",
    "build_music_engine",
    "build_sfx_library",
    "build_voice_engine",
]
