"""Cost rollups — AIMFOLD_MASTER_GOAL.md section 35 (Cost Intelligence):
"cost per Aim, cost per surfaced Opportunity, cost per accepted
Opportunity, cost per successful Outcome." Deterministic arithmetic over
already-aggregated inputs, same "Deterministic Before AI" reasoning as
aimfold_core.analytics (PR14) — no LLM call in this module.

Grain and tenant isolation, mirroring analytics/performance.py's
documented reasoning: `CostContext` is already summed to one Aim (the
natural cost-attribution unit — an Aim belongs to exactly one tenant, so
per-aim reports are tenant-isolated by construction). `rollup()` groups
many already-per-aim contexts up to a coarser level; 'tenant' stays
isolated as long as the caller only passes one tenant's Aims for a given
tenant_id key (same caller responsibility PR14's rollup() documents).
'opportunity_type' and 'global' deliberately aggregate across every
tenant given to them — cross-tenant cost BENCHMARKS for human
observability, never fed back into a single tenant's own behavior, same
boundary analytics/performance.py draws.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from pydantic import BaseModel, Field

from aimfold_core.analytics.schema import HierarchyLevel


class CostContext(BaseModel):
    """Already-summed cost/outcome totals for one Aim — a caller builds
    one of these by joining model_runs -> aims and opportunities/outcomes
    -> aims, summing in SQL or Python before calling this module."""

    aim_id: UUID
    tenant_id: UUID
    opportunity_type: str
    total_model_cost_usd: float = Field(default=0.0, ge=0.0)
    unknown_cost_model_call_count: int = Field(default=0, ge=0, description="model_runs rows with estimated_cost_usd IS NULL — an unpriced model, not a free one. Reported, never folded silently into total_model_cost_usd as 0.")
    surfaced_opportunity_count: int = Field(default=0, ge=0)
    accepted_opportunity_count: int = Field(default=0, ge=0)
    successful_outcome_count: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class CostReport(BaseModel):
    level: HierarchyLevel
    scope_key: str
    total_cost_usd: float
    unknown_cost_model_call_count: int
    cost_per_surfaced_opportunity: float | None = Field(default=None, description="None if surfaced_opportunity_count is 0 — not 0.0, which would misleadingly read as free")
    cost_per_accepted_opportunity: float | None = None
    cost_per_successful_outcome: float | None = None
    note: str = ""

    model_config = {"extra": "forbid"}


def _safe_ratio(numerator: float, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator > 0 else None


def compute_cost_report(contexts: list[CostContext], level: HierarchyLevel, scope_key: str) -> CostReport:
    total_cost = sum(c.total_model_cost_usd for c in contexts)
    unknown_calls = sum(c.unknown_cost_model_call_count for c in contexts)
    surfaced = sum(c.surfaced_opportunity_count for c in contexts)
    accepted = sum(c.accepted_opportunity_count for c in contexts)
    successful = sum(c.successful_outcome_count for c in contexts)

    note = ""
    if level in ("opportunity_type", "global"):
        note = f"Aggregates across every tenant in the given contexts ({len(contexts)} Aim(s)) — a cross-tenant cost benchmark for observability, not a figure any single tenant's Aim reads back into its own behavior."
    if unknown_calls:
        note = (note + " " if note else "") + f"{unknown_calls} model call(s) had no known price (see aimfold_core/observability/cost.py's rate table) and are excluded from total_cost_usd, not counted as free."

    return CostReport(
        level=level,
        scope_key=scope_key,
        total_cost_usd=round(total_cost, 6),
        unknown_cost_model_call_count=unknown_calls,
        cost_per_surfaced_opportunity=_safe_ratio(total_cost, surfaced),
        cost_per_accepted_opportunity=_safe_ratio(total_cost, accepted),
        cost_per_successful_outcome=_safe_ratio(total_cost, successful),
        note=note,
    )


def rollup(contexts: list[CostContext], level: HierarchyLevel) -> dict[str, CostReport]:
    if level == "global":
        return {"global": compute_cost_report(contexts, "global", "global")}

    key_fn = {
        "aim": lambda c: str(c.aim_id),
        "tenant": lambda c: str(c.tenant_id),
        "opportunity_type": lambda c: c.opportunity_type,
    }[level]

    grouped: dict[str, list[CostContext]] = defaultdict(list)
    for c in contexts:
        grouped[key_fn(c)].append(c)

    return {key: compute_cost_report(group, level, key) for key, group in grouped.items()}


__all__ = ["CostContext", "CostReport", "compute_cost_report", "rollup"]
