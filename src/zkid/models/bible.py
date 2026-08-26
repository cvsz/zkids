from __future__ import annotations

from pydantic import BaseModel, Field


class VisualStyle(BaseModel):
    type: str = "soft 3D children's animation"
    lighting: str = "warm soft"
    palette: str = "bright pastel"


class SeriesBible(BaseModel):
    schema_version: str = "1.0"
    series_id: str
    name: str
    audience: str = "4-7"
    genre: list[str] = Field(default_factory=lambda: ["educational", "adventure", "comedy"])
    episode_duration_target_sec: int = 240
    learning_topics: list[str] = Field(default_factory=list)
    visual_style: VisualStyle = Field(default_factory=VisualStyle)
    music_style: str | None = None
    logline: str | None = None


class VoiceDelivery(BaseModel):
    energy: str = "cheerful"
    pace: str = "medium-slow"
    articulation: str = "clear"
    emotion: str = "friendly"


class VoiceProfile(BaseModel):
    voice_id: str
    language: str = "en"
    gender: str = "neutral"
    delivery: VoiceDelivery = Field(default_factory=VoiceDelivery)
    rules: list[str] = Field(
        default_factory=lambda: ["avoid shouting", "clear pronunciation", "short sentences"]
    )
    provider_voice_name: str | None = None
    cloning_consent: bool = False


class CharacterLook(BaseModel):
    body: list[str] = Field(default_factory=list)
    face: list[str] = Field(default_factory=list)
    fur: list[str] = Field(default_factory=list)
    clothing: list[str] = Field(default_factory=list)


class CharacterSpec(BaseModel):
    character_id: str
    name: str
    species: str
    age_appearance: str
    look: CharacterLook = Field(default_factory=CharacterLook)
    personality: list[str] = Field(default_factory=list)
    signature_actions: list[str] = Field(default_factory=list)
    never_change: list[str] = Field(default_factory=list)
    version: int = 1
    voice: VoiceProfile | None = None
    reference_images: dict[str, str] = Field(default_factory=dict)
    palette_hex: list[str] = Field(default_factory=list)

    def master_prompt(self) -> str:
        lines: list[str] = [
            f"{self.name} is a {self.age_appearance} {self.species}.",
            "",
            "Canonical characteristics:",
        ]
        traits = self.look.face + self.look.fur + self.look.body
        if traits:
            lines.append(",\n".join(traits) + ".")
        if self.look.clothing:
            lines.append("")
            lines.append("Clothing:")
            lines.append(",\n".join(self.look.clothing) + ".")
        locked = self.never_change or []
        lines.append("")
        lines.append("Maintain exactly the same:")
        keep = locked or ["facial proportions", "colors", "proportions", "clothing design"]
        lines.append(",\n".join(keep) + ".")
        lines.append("")
        lines.append("Do not add:")
        lines.append("new accessories,\nnew clothing,\ndifferent shoes,\ndifferent markings.")
        return "\n".join(lines)


def build_master_prompt(spec: CharacterSpec) -> str:
    return spec.master_prompt()
