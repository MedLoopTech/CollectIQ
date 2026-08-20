"""Learning Analytics types — AIMFOLD_MASTER_GOAL.md section 24
(Performance Learning: track by Aim, opportunity type, signal type,
source, entity type, recommended action) and section 20 (Hierarchical
Learning: Global / Opportunity-Type / Organization / Aim levels).

Distinct from aimfold_core.memory, which computes PR26's Aim Memory
(inputs that feed back into future scoring/exclusions for one Aim). This
module computes section 24's performance report (output for human
observability — funnel counts, outcome correlation, economic value) and
can roll it up above the Aim level. That distinction matters for tenant
isolation: see performance.py's module docstring.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from aimfold_core.feedback.schema import FeedbackType, OutcomeType

HierarchyLevel = Literal["aim", "tenant", "opportunity_type", "global"]


class OpportunityOutcomeContext(BaseModel):
    """Everything compute_performance_report()/rollup() need about one
    Opportunity, already joined — this module doesn't query the database
    (storage-agnostic, same as the rest of aimfold_core). A caller builds
    one of these per opportunity by joining opportunities -> feedback
    (latest decision) -> outcomes (all of them)."""

    opportunity_id: UUID
    tenant_id: UUID
    aim_id: UUID
    opportunity_type: str
    feedback_type: FeedbackType | None = Field(default=None, description="Most recent human decision, if any")
    outcome_types: list[OutcomeType] = Field(default_factory=list, description="Every outcome recorded for this opportunity — can be more than one over time")
    outcome_monetary_values: list[float] = Field(default_factory=list)


class FunnelMetrics(BaseModel):
    raw_signal_count: int = 0
    qualified_signal_count: int = 0
    surfaced_opportunity_count: int
    accepted_count: int
    rejected_count: int
    held_count: int
    no_decision_count: int
    accepted_opportunity_rate: float = Field(..., ge=0.0, le=1.0)
    action_rate: float = Field(..., ge=0.0, le=1.0, description="Of accepted opportunities, fraction with at least one recorded outcome")


class OutcomeCorrelation(BaseModel):
    opportunities_with_outcomes: int
    successful_outcome_rate: float | None = Field(default=None, description="Of opportunities with a recorded outcome, fraction where at least one outcome was a success type. None if no outcomes recorded yet.")
    unsuccessful_outcome_rate: float | None = None
    outcome_type_counts: dict[str, int] = Field(default_factory=dict)


class EconomicSummary(BaseModel):
    opportunities_with_monetary_value: int
    total_monetary_value: float
    average_monetary_value: float | None = None


class PerformanceReport(BaseModel):
    level: HierarchyLevel
    scope_key: str = Field(..., description="'global' for the global level; a tenant_id/aim_id/opportunity_type value otherwise")
    funnel: FunnelMetrics
    outcome_correlation: OutcomeCorrelation
    economic: EconomicSummary
    note: str = ""
