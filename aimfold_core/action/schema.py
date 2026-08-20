"""Recommended-action types — AIMFOLD_MASTER_GOAL.md section 15
(taxonomy) and section 17 (Confidence-Based Automation)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from aimfold_core.aim_compiler.schema import RecommendedAction

# The four tiers section 17 names explicitly:
# Low -> discard/hold, Medium -> deeper research,
# High -> surfaced as an Opportunity (no auto action),
# Very High -> prepare the recommended action automatically.
AutomationTier = Literal["discard_or_hold", "deeper_research", "surface_as_opportunity", "prepare_action_automatically"]


class ActionThresholds(BaseModel):
    """Reuses the same score thresholds as
    aimfold_core.opportunity.schema.LifecycleThresholds by convention
    (not imported directly, to keep `action` independent of
    `opportunity`) — same numbers, same meaning: qualified_threshold and
    high_priority_threshold gate the Low/Medium/High tiers.
    very_high_confidence_threshold is the extra gate between High and
    Very High: a high total_score with low `confidence` (the
    opportunity's own evidence/source-confidence, not total_score) stays
    at "surface, don't auto-act" rather than being auto-prepared.
    """

    qualified_threshold: float = Field(default=50, ge=0, le=100)
    high_priority_threshold: float = Field(default=80, ge=0, le=100)
    very_high_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> "ActionThresholds":
        if self.qualified_threshold >= self.high_priority_threshold:
            raise ValueError("qualified_threshold must be lower than high_priority_threshold")
        return self


DEFAULT_ACTION_THRESHOLDS = ActionThresholds()


class ActionRecommendation(BaseModel):
    action: RecommendedAction | None = Field(default=None, description="None means: no action recommended yet")
    tier: AutomationTier
    rationale: str
