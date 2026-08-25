"""Asset lineage, budget accounting, and deterministic QC policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BudgetError(RuntimeError):
    pass


@dataclass(slots=True)
class BudgetLedger:
    limit: float
    committed: float = 0.0
    actual: float = 0.0

    def reserve(self, amount: float) -> None:
        if amount < 0:
            raise BudgetError("amount must be non-negative")
        if self.committed + self.actual + amount > self.limit:
            raise BudgetError("budget exhausted")
        self.committed += amount

    def settle(self, reserved: float, actual: float) -> None:
        if reserved < 0 or actual < 0 or reserved > self.committed:
            raise BudgetError("invalid settlement")
        self.committed -= reserved
        self.actual += actual
        if self.actual > self.limit:
            raise BudgetError("actual spend exceeded budget")


@dataclass(slots=True)
class AssetGraph:
    parents: dict[str, set[str]] = field(default_factory=dict)

    def add(self, asset_id: str, dependencies: set[str] | None = None) -> None:
        dependencies = dependencies or set()
        if asset_id in dependencies:
            raise ValueError("asset cannot depend on itself")
        self.parents[asset_id] = set(dependencies)
        if self._has_cycle(asset_id, set(), set()):
            del self.parents[asset_id]
            raise ValueError("asset lineage cycle detected")

    def descendants(self, asset_id: str) -> set[str]:
        result: set[str] = set()
        changed = True
        while changed:
            changed = False
            for child, deps in self.parents.items():
                if child not in result and (asset_id in deps or deps & result):
                    result.add(child)
                    changed = True
        return result

    def _has_cycle(self, node: str, visiting: set[str], visited: set[str]) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in self.parents.get(node, set()):
            if dep in self.parents and self._has_cycle(dep, visiting, visited):
                return True
        visiting.remove(node)
        visited.add(node)
        return False


class QCDecision(StrEnum):
    PASS = "PASS"
    RETRY = "RETRY"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class QCResult:
    hard_failures: tuple[str, ...] = ()
    soft_scores: dict[str, float] = field(default_factory=dict)


def decide_qc(result: QCResult, *, retry_threshold: float = 0.8) -> QCDecision:
    if result.hard_failures:
        return QCDecision.FAIL
    if not result.soft_scores:
        return QCDecision.PASS
    lowest = min(result.soft_scores.values())
    if lowest < 0.5:
        return QCDecision.MANUAL_REVIEW
    if lowest < retry_threshold:
        return QCDecision.RETRY
    return QCDecision.PASS
