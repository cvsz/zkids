"""Typed prompt compilation; provider adapters never receive arbitrary scene prompts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterLock:
    character_id: str
    version: str
    canonical_description: str
    immutable_constraints: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneInstruction:
    scene_id: str
    environment: str
    action: str
    camera: str
    motion: str


@dataclass(frozen=True, slots=True)
class CompiledMotionRequest:
    scene_id: str
    prompt_version: str
    character_version: str
    prompt: str


def compile_motion_prompt(
    character: CharacterLock,
    scene: SceneInstruction,
    *,
    prompt_version: str = "motion-v1",
) -> CompiledMotionRequest:
    immutable = "; ".join(character.immutable_constraints)
    prompt = (
        f"[CHARACTER LOCK]\n{character.canonical_description}\n"
        f"[IMMUTABLE]\n{immutable}\n"
        f"[SCENE]\n{scene.environment}\n"
        f"[ACTION]\n{scene.action}\n"
        f"[CAMERA]\n{scene.camera}\n"
        f"[MOTION]\n{scene.motion}\n"
        "[CONSISTENCY]\nPreserve character identity and all immutable fields."
    )
    return CompiledMotionRequest(
        scene_id=scene.scene_id,
        prompt_version=prompt_version,
        character_version=character.version,
        prompt=prompt,
    )
