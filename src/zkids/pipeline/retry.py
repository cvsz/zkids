from __future__ import annotations

from dataclasses import dataclass

from ..logging import get_logger
from ..models import CharacterSpec

log = get_logger("zkid.retry")


@dataclass
class RetryDecision:
    attempt: int
    strategy: str | None
    prompt_modifier: str
    simplify_motion: bool


def escalation_prompt(strategy: str | None, character: CharacterSpec | None) -> str:
    base = ""
    if strategy == "strengthen_character_constraints" and character:
        locked = ", ".join(character.never_change) or "identity"
        base += (
            f"\nSTRICT IDENTITY LOCK: preserve exactly {locked}. "
            "Match reference images precisely; no deviations."
        )
    elif strategy == "simplify_motion":
        base += (
            "\nMOTION SIMPLIFICATION: minimal motion only - slow gentle movement, "
            "no camera movement, no fast action."
        )
    else:
        base += "\nFollow all constraints exactly."
    return base


def plan_retry(attempt: int, max_attempts: int, character: CharacterSpec | None) -> RetryDecision:
    strategies = {
        1: "strengthen_character_constraints",
        2: "simplify_motion",
        3: "manual_review",
    }
    strategy = strategies.get(attempt)
    modifier = escalation_prompt(strategy, character)
    if attempt >= max_attempts:
        log.error("retry budget exhausted", extra={"stage": f"attempt {attempt}"})
        return RetryDecision(attempt=attempt, strategy="manual_review", prompt_modifier=modifier, simplify_motion=True)
    log.info("retry planned", extra={"stage": f"attempt {attempt}: {strategy}"})
    return RetryDecision(
        attempt=attempt,
        strategy=strategy,
        prompt_modifier=modifier,
        simplify_motion=strategy == "simplify_motion",
    )


__all__ = ["RetryDecision", "escalation_prompt", "plan_retry"]
