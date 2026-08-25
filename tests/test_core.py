from __future__ import annotations

import pytest

from zkids.domain import BudgetError, BudgetLedger, QCDecision, QCResult, AssetGraph, decide_qc
from zkids.providers import CapabilityError, MotionRequirements, ProviderCapabilities, require_capabilities
from zkids.prompts import CharacterLock, SceneInstruction, compile_motion_prompt
from zkids.states import EpisodeState, SceneState, TransitionError, EPISODE_TRANSITIONS, SCENE_TRANSITIONS, assert_transition


def test_episode_requires_human_publish_approval() -> None:
    assert_transition(EpisodeState.FINAL_QC_APPROVED, EpisodeState.HUMAN_PUBLISH_APPROVED, EPISODE_TRANSITIONS)
    with pytest.raises(TransitionError):
        assert_transition(EpisodeState.FINAL_QC_APPROVED, EpisodeState.PUBLISHED, EPISODE_TRANSITIONS)


def test_scene_illegal_skip_fails_closed() -> None:
    with pytest.raises(TransitionError):
        assert_transition(SceneState.CREATED, SceneState.VIDEO_GENERATING, SCENE_TRANSITIONS)


def test_capability_rejection_happens_before_submission() -> None:
    caps = ProviderCapabilities(reference_images=False, durations_seconds=frozenset({8}))
    with pytest.raises(CapabilityError):
        require_capabilities(caps, MotionRequirements(reference_images=1))


def test_prompt_compiler_preserves_locked_character_contract() -> None:
    result = compile_motion_prompt(
        CharacterLock("MIMI-001", "v3", "white rabbit in blue overalls", ("white fur", "blue overalls")),
        SceneInstruction("EP001-S003", "apple garden", "walk to red apple", "medium shot", "gentle walk"),
    )
    assert result.character_version == "v3"
    assert "white fur" in result.prompt
    assert "EP001-S003" == result.scene_id


def test_asset_graph_descendants_support_invalidation() -> None:
    graph = AssetGraph()
    graph.add("character-v3")
    graph.add("still-s3-v2", {"character-v3"})
    graph.add("video-s3-v4", {"still-s3-v2"})
    assert graph.descendants("character-v3") == {"still-s3-v2", "video-s3-v4"}


def test_hard_qc_failure_cannot_be_overridden_by_soft_score() -> None:
    result = QCResult(hard_failures=("missing provenance",), soft_scores={"identity": 1.0})
    assert decide_qc(result) is QCDecision.FAIL


def test_budget_fails_closed() -> None:
    ledger = BudgetLedger(limit=10)
    ledger.reserve(8)
    with pytest.raises(BudgetError):
        ledger.reserve(3)
