import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from zkid.models import LiveCharacterPrompt, TransitionRule
from zkid.schema_export import export_schemas

LIVE = Path(__file__).parents[1] / "templates" / "characters" / "NEKO-001-LIVE.json"


def _load() -> dict:
    return json.loads(LIVE.read_text(encoding="utf-8"))


def test_load_neko_live_instance():
    m = LiveCharacterPrompt.model_validate(_load())
    assert m.schema_id == "live-character-prompt"
    assert m.prompt_id == "NEKO-001-LIVE"
    assert m.character.character_id == "NEKO-001"
    assert m.character.identity_locks.fur_color.value == "orange"
    assert m.character.identity_locks.fur_color.enforcement == "hard"
    assert m.live_state_machine.initial_state == "idle"
    assert len(m.live_state_machine.states) == 7
    assert len(m.live_state_machine.transition_rules) == 7
    assert m.voice.language_priority == ["th-TH", "en-US"]
    assert m.safety_policy.rating == "family_friendly"
    assert m.response_contract.example.speech.startswith("สวัสดี")
    assert m.response_contract.example.intensity == 0.72


def test_transition_rule_from_alias():
    r = TransitionRule.model_validate({"event": "user_speaks", "from": ["idle"], "to": "listening"})
    assert r.from_ == ["idle"]
    assert r.to == "listening"


def test_intensity_bounds():
    data = _load()
    data["response_contract"]["example"]["intensity"] = 1.5
    with pytest.raises(ValidationError):
        LiveCharacterPrompt.model_validate(data)


def test_invalid_mode_rejected():
    data = _load()
    data["mode"] = "offline_batch"
    with pytest.raises(ValidationError):
        LiveCharacterPrompt.model_validate(data)


def test_negative_prompt_locks_fur():
    m = LiveCharacterPrompt.model_validate(_load())
    assert "fur color change" in m.negative_prompt
    assert "non-orange fur" in m.negative_prompt


def test_memory_policy_never_remember_secrets():
    m = LiveCharacterPrompt.model_validate(_load())
    assert "access tokens" in m.memory_policy.never_remember
    assert m.memory_policy.consent_required is True


def test_schema_export_includes_live(tmp_path):
    files = export_schemas(tmp_path / "schemas")
    target = tmp_path / "schemas" / "live-character-prompt.schema.json"
    assert target in files
    schema = json.loads(target.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_id"]["const"] == "live-character-prompt"
    assert "live_state_machine" in schema["properties"]


def test_base_neko_character_updated():
    from zkid.models import CharacterSpec

    base = json.loads((Path(__file__).parents[1] / "templates" / "characters" / "NEKO-001.json").read_text(encoding="utf-8"))
    spec = CharacterSpec.model_validate(base)
    assert spec.version == 2
    assert "fur color" in spec.never_change
    prompt = spec.master_prompt()
    assert "Neko is a" in prompt
    assert "orange" in prompt
