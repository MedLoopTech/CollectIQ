"""Deterministic performance-tracking aggregation — no LLM, same
reasoning as aimfold_core.memory: turning recorded feedback/outcomes into
counts and rates is arithmetic, not interpretation.

Tenant isolation (AIMFOLD_MASTER_GOAL.md section 20: "Feedback from one
tenant must not inappropriately alter another tenant's behavior"):

- `compute_performance_report()` operates on whatever `contexts` it's
  given — it does NOT filter by tenant itself, so the caller is
  responsible for scoping input correctly. `rollup()` groups by the
  requested level's key, and for 'tenant'/'aim' that key already implies
  one tenant (an Aim belongs to exactly one tenant), so those levels are
  automatically tenant-isolated by construction.
- 'opportunity_type' and 'global' levels DELIBERATELY aggregate across
  every tenant given to them — these are read-only cross-tenant
  BENCHMARKS for human observability (e.g. "how does customer_discovery
  perform across all tenants using it"), not something a single tenant's
  Aim ever reads back into its own scoring/exclusions. Only
  aimfold_core.memory's Aim Memory (strictly aim_id + tenant_id scoped)
  feeds back into automated behavior — this module never does. That
  boundary is enforced by aimfold_core.memory simply never importing
  from here, not by a runtime check, so it's worth stating plainly.
"""

from __future__ import annotations

from collections import defaultdict

from .schema import EconomicSummary, FunnelMetrics, HierarchyLevel, OpportunityOutcomeContext, OutcomeCorrelation, PerformanceReport

SUCCESSFUL_OUTCOME_TYPES = frozenset({
    "positive_response", "meeting", "application_submitted", "shortlisted",
    "grant_awarded", "partnership_progressed", "investment_conversation", "won",
})
UNSUCCESSFUL_OUTCOME_TYPES = frozenset({"negative_response", "lost"})
# 'custom' is deliberately unclassified — not enough information to call it either way.


def _funnel(contexts: list[OpportunityOutcomeContext], raw_signal_count: int, qualified_signal_count: int) -> FunnelMetrics:
    accepted = [c for c in contexts if c.feedback_type == "accepted"]
    rejected = [c for c in contexts if c.feedback_type == "rejected"]
    held = [c for c in contexts if c.feedback_type == "held"]
    no_decision = [c for c in contexts if c.feedback_type is None]

    accepted_with_outcome = sum(1 for c in accepted if c.outcome_types)

    return FunnelMetrics(
        raw_signal_count=raw_signal_count,
        qualified_signal_count=qualified_signal_count,
        surfaced_opportunity_count=len(contexts),
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        held_count=len(held),
        no_decision_count=len(no_decision),
        accepted_opportunity_rate=round(len(accepted) / len(contexts), 4) if contexts else 0.0,
        action_rate=round(accepted_with_outcome / len(accepted), 4) if accepted else 0.0,
    )


def _outcome_correlation(contexts: list[OpportunityOutcomeContext]) -> OutcomeCorrelation:
    with_outcomes = [c for c in contexts if c.outcome_types]
    if not with_outcomes:
        return OutcomeCorrelation(opportunities_with_outcomes=0)

    type_counts: dict[str, int] = defaultdict(int)
    successful = 0
    unsuccessful = 0
    for c in with_outcomes:
        types = set(c.outcome_types)
        for t in types:
            type_counts[t] += 1
        if types & SUCCESSFUL_OUTCOME_TYPES:
            successful += 1
        elif types & UNSUCCESSFUL_OUTCOME_TYPES:
            unsuccessful += 1

    return OutcomeCorrelation(
        opportunities_with_outcomes=len(with_outcomes),
        successful_outcome_rate=round(successful / len(with_outcomes), 4),
        unsuccessful_outcome_rate=round(unsuccessful / len(with_outcomes), 4),
        outcome_type_counts=dict(type_counts),
    )


def _economic_summary(contexts: list[OpportunityOutcomeContext]) -> EconomicSummary:
    values = [v for c in contexts for v in c.outcome_monetary_values]
    if not values:
        return EconomicSummary(opportunities_with_monetary_value=0, total_monetary_value=0.0)
    with_value_count = sum(1 for c in contexts if c.outcome_monetary_values)
    return EconomicSummary(
        opportunities_with_monetary_value=with_value_count,
        total_monetary_value=round(sum(values), 2),
        average_monetary_value=round(sum(values) / len(values), 2),
    )


def compute_performance_report(
    level: HierarchyLevel,
    scope_key: str,
    contexts: list[OpportunityOutcomeContext],
    *,
    raw_signal_count: int = 0,
    qualified_signal_count: int = 0,
    note: str = "",
) -> PerformanceReport:
    return PerformanceReport(
        level=level,
        scope_key=scope_key,
        funnel=_funnel(contexts, raw_signal_count, qualified_signal_count),
        outcome_correlation=_outcome_correlation(contexts),
        economic=_economic_summary(contexts),
        note=note,
    )


def _scope_key_for(context: OpportunityOutcomeContext, level: HierarchyLevel) -> str:
    if level == "aim":
        return str(context.aim_id)
    if level == "tenant":
        return str(context.tenant_id)
    if level == "opportunity_type":
        return context.opportunity_type
    raise ValueError("rollup() groups by aim/tenant/opportunity_type; use compute_performance_report() directly for 'global'")


def rollup(contexts: list[OpportunityOutcomeContext], level: HierarchyLevel) -> dict[str, PerformanceReport]:
    """Groups contexts by the given level's key and computes one report
    per group. No signal counts here — this module doesn't have a
    per-scope signal count to attach automatically; pass those into
    compute_performance_report() directly if you need funnel counts for
    a single, already-known scope."""

    if level == "global":
        raise ValueError("rollup() is for aim/tenant/opportunity_type; call compute_performance_report(level='global', ...) directly with everything you want aggregated")

    grouped: dict[str, list[OpportunityOutcomeContext]] = defaultdict(list)
    for c in contexts:
        grouped[_scope_key_for(c, level)].append(c)

    note = ""
    if level in ("opportunity_type",):
        note = "Cross-tenant benchmark — informational only, never fed back into any single tenant's automated behavior."

    return {key: compute_performance_report(level, key, group, note=note) for key, group in grouped.items()}


__all__ = ["compute_performance_report", "rollup", "SUCCESSFUL_OUTCOME_TYPES", "UNSUCCESSFUL_OUTCOME_TYPES"]
