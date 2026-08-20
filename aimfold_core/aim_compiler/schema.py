"""Formal contract for aim_versions.compiled_spec.

supabase/migrations/20260819120100_aim_schema.sql left compiled_spec as an
unvalidated jsonb blob and said PR4 (this module) would enforce its shape.
CompiledAimSpec is that enforcement — every field here matches a field the
product goal's Aim Compiler section (AIMFOLD_MASTER_GOAL.md section 4) lists,
and every field name matches what 20260819120200_seed_collectiq_aim.sql
already wrote for CollectIQ, so the existing seed is a valid instance of this
schema (see tests/test_compiler.py).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Mirrors the aims.opportunity_type check constraint in
# supabase/migrations/20260819120100_aim_schema.sql — keep these in sync.
OpportunityType = Literal[
    "customer_discovery",
    "career_discovery",
    "funding_discovery",
    "investor_discovery",
    "partnership_discovery",
    "vendor_discovery",
    "market_discovery",
    "acquisition_discovery",
    "custom",
]

# Mirrors AIMFOLD_MASTER_GOAL.md section 5 (Generic Entity Model). Entity
# rows don't exist yet (PR5), but the compiler already needs to name types.
EntityType = Literal[
    "company",
    "organization",
    "job",
    "employer",
    "investor",
    "investment_fund",
    "grant",
    "funding_program",
    "government_body",
    "nonprofit",
    "person",
    "partner",
    "vendor",
    "product",
    "market",
    "tender",
    "project",
    "other",
]

RecommendedAction = Literal[
    "contact",
    "research",
    "apply",
    "save",
    "monitor",
    "request_introduction",
    "prepare_application",
    "review_eligibility",
    "engage_partner",
    "contact_investor",
    "add_to_watchlist",
    "ignore",
    "wait_for_another_signal",
]


class ScoringWeightRule(BaseModel):
    """One Stage-1 (cheap, deterministic) keyword-match rule.

    This is CollectIQ's existing pattern (see the six job-posting
    hypotheses in 20260819120200_seed_collectiq_aim.sql), formalized. It is
    intentionally narrow — a full multi-dimension explainable scorer
    (AIMFOLD_MASTER_GOAL.md section 13: Aim Fit / Evidence Strength /
    Timing / ... summing to 100) is PR7's job, not this one.
    """

    pattern: str = Field(..., min_length=1, description="Python/JS-compatible regex, matched case-insensitively against normalized signal text")
    points: int = Field(..., ge=1, le=100)
    label: str = Field(..., min_length=1)

    @field_validator("pattern")
    @classmethod
    def pattern_must_compile(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"not a valid regex: {v!r} ({exc})") from exc
        return v


class ConfidenceThresholds(BaseModel):
    qualified_signal_min_score: int = Field(..., ge=0, le=100)
    max_score: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def threshold_within_max(self) -> "ConfidenceThresholds":
        if self.qualified_signal_min_score > self.max_score:
            raise ValueError("qualified_signal_min_score cannot exceed max_score")
        return self


class CompiledAimSpec(BaseModel):
    """The structured Aim produced by the Aim Compiler.

    Field set matches AIMFOLD_MASTER_GOAL.md section 4 exactly (objective
    through notification_preferences); nothing added, nothing dropped.
    """

    objective: str = Field(..., min_length=1)
    opportunity_type: OpportunityType
    target_entity_types: list[EntityType] = Field(..., min_length=1)
    geography: list[str] = Field(..., min_length=1)
    industries: list[str] = Field(default_factory=list)
    positive_criteria: list[str] = Field(..., min_length=1)
    negative_criteria: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    freshness_requirements: str | None = None
    likely_sources: list[str] = Field(..., min_length=1)
    evidence_requirements: list[str] = Field(..., min_length=1)
    scoring_dimensions: list[str] = Field(..., min_length=1)
    scoring_weights: list[ScoringWeightRule] = Field(..., min_length=1)
    confidence_thresholds: ConfidenceThresholds
    likely_actions: list[RecommendedAction] = Field(..., min_length=1)
    notification_preferences: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class AimCompilationResult(BaseModel):
    """What the compiler hands back for human review before anything is
    written to aim_versions — nothing here is auto-approved
    (AIMFOLD_MASTER_GOAL.md section 22: proposals require approval)."""

    raw_user_intent: str
    compiled_spec: CompiledAimSpec
    explanation: str = Field(..., min_length=1, description='Human-readable "Here''s what I''ll look for" summary')
    compiler_model: str
    compiler_prompt_version: str
