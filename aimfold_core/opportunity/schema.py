"""Opportunity clustering + lifecycle types — AIMFOLD_MASTER_GOAL.md
sections 9-12."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

LifecycleState = Literal[
    "discovered", "evaluating", "qualified", "high_priority", "actioned", "outcome",
    "held", "rejected", "stale", "expired", "revived", "duplicate", "invalid",
]

# States a human/action/feedback pipeline controls — the deterministic
# lifecycle engine in lifecycle.py never transitions a signal INTO or OUT
# OF these on its own (AIMFOLD_MASTER_GOAL.md section 16: humans handle
# ambiguous opportunities, strategic decisions, final decisions).
HUMAN_OR_ACTION_CONTROLLED_STATES = frozenset({"actioned", "outcome", "held", "rejected", "duplicate", "invalid"})

TemporalMomentum = Literal["emerging", "strengthening", "weakening", "stable"]


class OpportunityCandidate(BaseModel):
    """Minimal projection of an existing opportunities row, enough to
    decide clustering — callers build this from a real query, this
    module doesn't run one itself (storage-agnostic, same as
    aim_compiler/evidence/scoring)."""

    id: UUID
    tenant_id: UUID
    aim_id: UUID
    primary_entity_id: UUID
    lifecycle_state: LifecycleState
    last_strengthened_at: datetime
    total_score: float


class ClusteringDecision(BaseModel):
    attach_to_opportunity_id: UUID | None = Field(default=None, description="None means: create a new opportunity")
    reason: str
    other_eligible_opportunity_ids: list[UUID] = Field(
        default_factory=list,
        description="Non-empty only when more than one existing opportunity was eligible — a possible duplicate that should be reviewed/merged, not auto-resolved here.",
    )


class LifecycleThresholds(BaseModel):
    qualified_threshold: float = Field(default=50, ge=0, le=100)
    high_priority_threshold: float = Field(default=80, ge=0, le=100)
    stale_after_days: float = Field(default=30, gt=0)
    expired_after_days: float = Field(default=90, gt=0)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "LifecycleThresholds":
        if self.qualified_threshold >= self.high_priority_threshold:
            raise ValueError("qualified_threshold must be lower than high_priority_threshold")
        if self.stale_after_days >= self.expired_after_days:
            raise ValueError("stale_after_days must be lower than expired_after_days")
        return self


DEFAULT_LIFECYCLE_THRESHOLDS = LifecycleThresholds()


class LifecycleTransition(BaseModel):
    from_state: LifecycleState | None
    to_state: LifecycleState
    reason: str


class ConfidenceFields(BaseModel):
    """opportunities.confidence / evidence_confidence / source_confidence,
    derived from a scored ExplainableScore — see mapping.py."""

    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_confidence: float = Field(..., ge=0.0, le=1.0)
    source_confidence: float = Field(..., ge=0.0, le=1.0)
