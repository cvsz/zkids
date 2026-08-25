from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain import BudgetLedger
from .providers import MediaProvider, ProviderResult


@dataclass(frozen=True, slots=True)
class UsageEvent:
    tenant_id: str
    provider: str
    model: str
    operation: str
    cost_usd: float
    metadata: dict[str, Any]


class UsageSink:
    def __init__(self) -> None:
        self.events: list[UsageEvent] = []

    def record(self, event: UsageEvent) -> None:
        self.events.append(event)


class ProductionExecutor:
    def __init__(self, *, usage: UsageSink | None = None) -> None:
        self.usage = usage or UsageSink()

    def generate(
        self,
        *,
        tenant_id: str,
        operation: str,
        provider: MediaProvider,
        request: dict[str, Any],
        budget_limit: float,
    ) -> ProviderResult:
        ledger = BudgetLedger(limit=budget_limit)
        estimated = float(request.get("estimated_cost_usd", 0.0))
        ledger.reserve(estimated)
        result = provider.generate(request)
        ledger.settle(estimated, result.cost_usd)
        self.usage.record(
            UsageEvent(
                tenant_id=tenant_id,
                provider=result.provider,
                model=result.model,
                operation=operation,
                cost_usd=result.cost_usd,
                metadata=result.metadata,
            )
        )
        return result
