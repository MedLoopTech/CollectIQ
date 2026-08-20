"""Evaluation framework types — AIMFOLD_MASTER_GOAL.md section 29
(Evaluation Framework) and section 30 (Regression Protection).

Scope note: section 29's category list is "excellent opportunities,
acceptable opportunities, false positives, irrelevant signals, ambiguous
cases, stale opportunities, revived opportunities, multi-signal
opportunities." The last three describe TEMPORAL SEQUENCES of signals,
not a single signal's evidence quality, and are already covered by
aimfold_core/opportunity/tests/test_opportunity.py (lifecycle staleness/
revival, clustering multi-signal behavior) — duplicating them here as
static labeled examples would mean faking a fixed evaluation dataset;
this module covers the five categories that ARE evaluable from one
signal's text: excellent, acceptable, false_positive, irrelevant_signal,
ambiguous.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExampleCategory = Literal["excellent", "acceptable", "false_positive", "irrelevant_signal", "ambiguous"]


class EvalExample(BaseModel):
    id: str
    signal_text: str
    entity_type: str = "company"
    expected_category: ExampleCategory
    expected_qualifies: bool = Field(..., description="Should Stage 1 qualify this signal (score >= threshold)?")
    expected_score_range: tuple[float, float] = Field(
        ..., description="Expected total_score band once Stage 2 has run — see runner.py for why Stage-1-only scores aren't compared against this."
    )
    expected_matched_criteria: list[str] = Field(default_factory=list, description="Subset of the Aim's positive_criteria a correct Stage-2 assessment should find. Empty is meaningful, not 'not checked' — it means a correct assessment should find NONE (e.g. a false positive).")
    expected_action: str | None = Field(default=None, description="Expected recommended_action. None = not checked.")
    notes: str = Field(..., description="Why this example exists / what it's testing — required, an unlabeled example is not useful.")

    model_config = {"extra": "forbid"}


class EvalResult(BaseModel):
    example_id: str
    expected_category: ExampleCategory
    stage1_score: float
    stage1_qualifies: bool
    total_score: float
    confidence: float
    recommended_action: str | None
    matched_positive_criteria: list[str] = Field(default_factory=list)
    stage2_ran: bool

    passed_qualification_check: bool
    passed_calibration_check: bool | None
    passed_grounding_check: bool | None
    passed_action_check: bool | None


class EvalReport(BaseModel):
    dataset_name: str
    n_examples: int
    stage2_ran: bool
    scoring_version: str
    aim_objective: str = Field(..., description="compiled_spec.objective this run was evaluated against — reproducibility (section 30/37): which Aim definition produced these numbers.")

    precision: float
    false_positive_rate: float
    accepted_opportunity_rate: float
    ranking_quality: float
    calibration_accuracy: float | None
    evidence_grounding_accuracy: float | None
    action_recommendation_quality: float | None

    scores_by_category: dict[str, list[float]] = Field(default_factory=dict)
    results: list[EvalResult] = Field(default_factory=list)


class RegressionFinding(BaseModel):
    metric: str
    baseline_value: float
    candidate_value: float
    delta: float
    is_regression: bool
    note: str = ""


class RegressionReport(BaseModel):
    has_regression: bool
    findings: list[RegressionFinding]
