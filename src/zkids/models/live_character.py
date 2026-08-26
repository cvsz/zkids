from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LiveCharacterLook(BaseModel):
    body: list[str] = Field(default_factory=list)
    face: list[str] = Field(default_factory=list)
    fur: list[str] = Field(default_factory=list)
    clothing: list[str] = Field(default_factory=list)


class IdentityLock(BaseModel):
    value: str
    enforcement: Literal["hard", "preferred"] = "hard"
    never_change: bool = True


class LiveCharacterIdentityLocks(BaseModel):
    fur_color: IdentityLock | None = None
    red_scarf: IdentityLock | None = None


class LiveCharacterSpec(BaseModel):
    character_id: str
    name: str
    species: str
    role: str = "family-friendly virtual companion"
    age_appearance: str = "childlike"
    presentation: str = "innocent, playful, warm, never sexualized"
    look: LiveCharacterLook = Field(default_factory=LiveCharacterLook)
    personality: list[str] = Field(default_factory=list)
    signature_actions: list[str] = Field(default_factory=list)
    identity_locks: LiveCharacterIdentityLocks = Field(default_factory=LiveCharacterIdentityLocks)


class RenderConfig(BaseModel):
    target_fps: int = 60
    fallback_fps: int = 30
    camera: str = "medium close-up"
    background: str = "scene-dependent"
    lighting: str = "soft warm key light with subtle rim light"


class TrackingConfig(BaseModel):
    face_tracking: bool = True
    eye_tracking: bool = True
    head_tracking: bool = True
    voice_lip_sync: bool = True
    hand_tracking: bool = True
    tail_and_ear_automation: bool = True


class LatencyTargets(BaseModel):
    input_acknowledgement_ms: int = 250
    first_audio_ms: int = 800
    user_interrupt_response_ms: int = 150


class StreamingConfig(BaseModel):
    stream_text: bool = True
    stream_audio: bool = True
    support_barge_in: bool = True
    pause_when_user_speaks: bool = True
    resume_after_interruption: bool = True


class RealtimeRuntime(BaseModel):
    target_platforms: list[str] = Field(
        default_factory=lambda: [
            "live stream",
            "interactive avatar",
            "VTuber runtime",
            "virtual companion",
            "game character",
        ]
    )
    render: RenderConfig = Field(default_factory=RenderConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    latency_targets: LatencyTargets = Field(default_factory=LatencyTargets)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)


class LiveState(BaseModel):
    emotion: str
    animation: str


class TransitionRule(BaseModel):
    event: str
    from_: list[str] = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class LiveStateMachine(BaseModel):
    initial_state: str = "idle"
    states: dict[str, LiveState] = Field(default_factory=dict)
    transition_rules: list[TransitionRule] = Field(default_factory=list)


class TTSRequirements(BaseModel):
    phoneme_visemes: bool = True
    emotion_control: bool = True
    streaming_audio: bool = True
    natural_pauses: bool = True


class LiveVoiceConfig(BaseModel):
    language_priority: list[str] = Field(default_factory=lambda: ["th-TH", "en-US"])
    style: str = "warm, bright, friendly, concise, natural"
    pitch: str = "light and expressive, never imitate an identifiable person"
    speed_wpm: int = 145
    prosody: list[str] = Field(default_factory=list)
    tts_requirements: TTSRequirements = Field(default_factory=TTSRequirements)


class RuntimeInputs(BaseModel):
    required: list[str] = Field(default_factory=lambda: ["user_message"])
    optional: list[str] = Field(default_factory=list)


class ResponseContractExample(BaseModel):
    speech: str
    emotion: str
    intensity: float = Field(ge=0, le=1)
    gesture: str | None = None
    safety_action: Literal["allow", "redirect", "refuse"] = "allow"


class ResponseContractRequiredFields(BaseModel):
    speech: str = "string"
    emotion: str = "neutral|curious|happy|excited|comforting|confused|concerned"
    intensity: str = "number between 0 and 1"
    gesture: str = "string or null"
    safety_action: str = "allow|redirect|refuse"


class ResponseContract(BaseModel):
    format: Literal["json"] = "json"
    required_fields: ResponseContractRequiredFields = Field(default_factory=ResponseContractRequiredFields)
    example: ResponseContractExample | None = None


class MemoryPolicy(BaseModel):
    consent_required: bool = True
    may_remember: list[str] = Field(default_factory=list)
    never_remember: list[str] = Field(default_factory=list)


class ToolActions(BaseModel):
    confirmation_required: bool = True
    never_execute_without_confirmation: list[str] = Field(default_factory=list)


class SafetyPolicy(BaseModel):
    rating: Literal["family_friendly"] = "family_friendly"
    never_generate: list[str] = Field(default_factory=list)
    refusal_style: str = "brief, kind, clear, and provide a safe alternative"
    tool_actions: ToolActions = Field(default_factory=ToolActions)


class LiveCharacterPrompt(BaseModel):
    schema_id: Literal["live-character-prompt"] = "live-character-prompt"
    schema_version: str = "1.0.0"
    prompt_id: str
    version: str = "1.0.0"
    mode: Literal["real_time_interactive_avatar"] = "real_time_interactive_avatar"
    character: LiveCharacterSpec
    system_prompt: str
    visual_prompt: str
    negative_prompt: list[str] = Field(default_factory=list)
    realtime_runtime: RealtimeRuntime = Field(default_factory=RealtimeRuntime)
    live_state_machine: LiveStateMachine = Field(default_factory=LiveStateMachine)
    voice: LiveVoiceConfig = Field(default_factory=LiveVoiceConfig)
    conversation_rules: list[str] = Field(default_factory=list)
    runtime_inputs: RuntimeInputs = Field(default_factory=RuntimeInputs)
    response_contract: ResponseContract = Field(default_factory=ResponseContract)
    memory_policy: MemoryPolicy = Field(default_factory=MemoryPolicy)
    safety_policy: SafetyPolicy = Field(default_factory=SafetyPolicy)
    quality_gates: list[str] = Field(default_factory=list)
