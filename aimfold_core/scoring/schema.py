"""Explainable, configurable scoring — AIMFOLD_MASTER_GOAL.md section 13.

"Do not store only the final score. Store: component score, rationale,
supporting evidence, scoring version." — ExplainableScore is that: every
dimension keeps its own weight, raw 0-1 value, weighted points, and a
plain-language rationale, not just a total.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

SCORING_ENGINE_VERSION = "scoring-engine-2026-08-19-v1"

DIMENSION_NAMES = (
    "aim_fit",
    "evidence_strength",
    "timing_trigger_strength",
    "opportunity_relevance",
    "evidence_confidence",
    "source_quality",
    "actionability",
)


class ScoringWeights(BaseModel):
    """AIMFOLD_MASTER_GOAL.md section 13's recommended starting
    structure, as defaults — "weights may differ by Aim type" means
    callers can construct a different ScoringWeights per Aim/opportunity
    type; this module doesn't hardcode that lookup (see engine.py's
    docstring for why persistence isn't wired up yet)."""

    aim_fit: float = Field(default=20, ge=0)
    evidence_strength: float = Field(default=25, ge=0)
    timing_trigger_strength: float = Field(default=20, ge=0)
    opportunity_relevance: float = Field(default=15, ge=0)
    evidence_confidence: float = Field(default=10, ge=0)
    source_quality: float = Field(default=5, ge=0)
    actionability: float = Field(default=5, ge=0)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def weights_sum_to_100(self) -> "ScoringWeights":
        total = sum(getattr(self, name) for name in DIMENSION_NAMES)
        if abs(total - 100) > 0.01:
            raise ValueError(f"ScoringWeights must sum to 100, got {total}")
        return self


DEFAULT_SCORING_WEIGHTS = ScoringWeights()


class DimensionScore(BaseModel):
    name: str
    weight: float
    raw_value: float = Field(..., ge=0.0, le=1.0, description="Normalized 0-1 before weighting")
    points: float = Field(..., description="raw_value * weight")
    rationale: str


class ExplainableScore(BaseModel):
    dimensions: list[DimensionScore]
    total_score: float = Field(..., ge=0, le=100)
    scoring_version: str
    weights_used: ScoringWeights

    def dimension(self, name: str) -> DimensionScore:
        for d in self.dimensions:
            if d.name == name:
                return d
        raise KeyError(name)
