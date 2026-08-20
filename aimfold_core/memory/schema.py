"""Aim Memory types — AIMFOLD_MASTER_GOAL.md section 26. memory_type
values match 20260819120900_aim_memory_schema.sql's check constraint
exactly; tests/test_memory.py verifies that directly."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from aimfold_core.feedback.schema import FeedbackType, RejectionReason

MemoryType = Literal[
    "accepted_pattern", "rejected_pattern", "high_value_evidence", "weak_evidence",
    "successful_action", "failed_action", "preferred_entity_attribute",
    "learned_exclusion", "timing_pattern", "source_effectiveness",
]


class AimMemoryEntry(BaseModel):
    memory_type: MemoryType
    payload: dict
    sample_size: int = Field(..., ge=0)


class FeedbackDecisionContext(BaseModel):
    """Everything compute_aim_memory() needs about one feedback decision,
    already joined — this module doesn't query the database itself
    (storage-agnostic, same as the rest of aimfold_core). A caller builds
    one of these per feedback row by joining feedback -> opportunities
    (for component_scores) -> entities (for entity_type) ->
    opportunity_signals -> signals (for source_key)."""

    opportunity_id: UUID
    feedback_type: FeedbackType
    rejection_reason: RejectionReason | None = None
    predicted_recommended_action: str | None = None
    component_scores: list[dict] = Field(default_factory=list, description="Serialized DimensionScore list, e.g. [{'name': 'evidence_strength', 'raw_value': 0.95, ...}]")
    primary_entity_type: str | None = None
    source_keys: list[str] = Field(default_factory=list)
