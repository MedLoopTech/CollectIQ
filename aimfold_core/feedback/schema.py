"""Structured feedback + outcomes types — AIMFOLD_MASTER_GOAL.md
sections 18-21. Field names and taxonomy values match
20260819120800_feedback_outcomes_schema.sql's check constraints exactly;
tests/test_feedback.py verifies that directly by parsing the migration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

FeedbackType = Literal["accepted", "rejected", "saved", "ignored", "held", "actioned", "not_actioned"]

RejectionReason = Literal[
    "wrong_entity_type", "wrong_industry", "wrong_geography", "too_small", "too_large",
    "weak_evidence", "poor_timing", "low_value", "already_known", "duplicate",
    "irrelevant_signal", "source_unreliable", "not_eligible", "wrong_role",
    "wrong_seniority", "poor_strategic_fit", "not_actionable", "other",
]

OutcomeType = Literal[
    "positive_response", "negative_response", "meeting", "application_submitted",
    "shortlisted", "grant_awarded", "partnership_progressed", "investment_conversation",
    "won", "lost", "custom",
]


class FeedbackRecord(BaseModel):
    """One human decision on one Opportunity. Mirrors the `feedback`
    table — same rejected-requires-a-reason invariant enforced here as in
    the DB's `feedback_rejection_reason_required` check constraint
    (defense in depth: a caller building this object gets the same
    validation before it ever reaches the database)."""

    tenant_id: UUID
    aim_id: UUID
    opportunity_id: UUID
    user_id: UUID | None = None

    feedback_type: FeedbackType
    rejection_reason: RejectionReason | None = None
    notes: str | None = None

    predicted_total_score: float | None = None
    predicted_confidence: float | None = None
    predicted_recommended_action: str | None = None
    predicted_lifecycle_state: str | None = None
    aim_version_id: UUID | None = None
    scoring_version: str | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def rejection_reason_matches_type(self) -> "FeedbackRecord":
        if self.feedback_type == "rejected" and self.rejection_reason is None:
            raise ValueError("rejection_reason is required when feedback_type='rejected'")
        if self.feedback_type != "rejected" and self.rejection_reason is not None:
            raise ValueError("rejection_reason must be null unless feedback_type='rejected'")
        return self


class OutcomeRecord(BaseModel):
    tenant_id: UUID
    aim_id: UUID
    opportunity_id: UUID
    user_id: UUID | None = None

    outcome_type: OutcomeType
    monetary_value: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    notes: str | None = None
    occurred_at: datetime | None = None

    model_config = {"extra": "forbid"}
