"""Controlled improvement proposal types — AIMFOLD_MASTER_GOAL.md
section 22 (Safe Self-Improvement): Observe -> Measure -> Propose -> Test
-> Promote. Field names match 20260819121000_learning_proposals_schema.sql's
columns and section 22's required-fields list exactly."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.scoring.schema import ScoringWeights

ProposalType = Literal["add_exclusion", "adjust_scoring_weight"]
ProposalStatus = Literal["proposed", "tested", "approved", "rejected", "promoted", "superseded"]


class LearningProposal(BaseModel):
    proposal_type: ProposalType
    aim_id: UUID

    # Section 22's required fields, verbatim.
    current_behavior: str = Field(..., min_length=1)
    proposed_behavior: str = Field(..., min_length=1)
    supporting_observations: dict = Field(default_factory=dict)
    affected_aims: list[UUID] = Field(..., min_length=1)
    sample_size: int = Field(..., ge=0)
    expected_impact: str = Field(..., min_length=1)
    evaluation_results: dict | None = Field(default=None, description="Populated by the Test step — see aimfold_core/proposals/testing.py")
    possible_regressions: list[str] | None = Field(default=None, description="Metric names compare_eval_reports flagged, if any — populated by the Test step")
    rollback_path: str = Field(..., min_length=1)

    proposed_compiled_spec: CompiledAimSpec | None = None
    proposed_scoring_weights: ScoringWeights | None = None

    status: ProposalStatus = "proposed"

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def exactly_one_candidate_matching_type(self) -> "LearningProposal":
        if self.proposal_type == "add_exclusion":
            if self.proposed_compiled_spec is None or self.proposed_scoring_weights is not None:
                raise ValueError("proposal_type='add_exclusion' requires proposed_compiled_spec and forbids proposed_scoring_weights")
        elif self.proposal_type == "adjust_scoring_weight":
            if self.proposed_scoring_weights is None or self.proposed_compiled_spec is not None:
                raise ValueError("proposal_type='adjust_scoring_weight' requires proposed_scoring_weights and forbids proposed_compiled_spec")
        return self
