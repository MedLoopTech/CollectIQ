"""Structured evidence for a Signal — AIMFOLD_MASTER_GOAL.md section 8
(Evidence-First Requirement) and section 7 (signals.extracted_evidence).

Evidence-First is not just a prompt instruction here — the sharpest part
of section 8 ("AI-generated inference must be clearly distinguishable
from observed facts... must not fabricate evidence") is enforced in code
(evaluator.py checks every observed_fact is a literal substring of the
signal's own text), not only asked for nicely in the prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceMatch(BaseModel):
    """One Stage-1 (deterministic, no LLM) keyword-rule hit."""

    pattern: str
    label: str
    points: int
    matched_text: str = Field(..., description="The actual substring that matched — provenance for this specific match")


class Stage1EvidenceResult(BaseModel):
    """Output of the cheap deterministic filter (AIMFOLD_MASTER_GOAL.md
    section 14, Stage 1). Pure function of (compiled_spec, text) — no AI
    call, so this always runs, for every signal."""

    matches: list[EvidenceMatch]
    score: int = Field(..., ge=0)
    max_score: int
    qualifies: bool = Field(..., description="score >= the Aim's confidence_thresholds.qualified_signal_min_score")

    @property
    def labels(self) -> list[str]:
        return [m.label for m in self.matches]


class EvidenceAssessment(BaseModel):
    """Output of the Stage-2 (LLM) Evidence Evaluator — only runs for
    signals that already qualify at Stage 1 (AIMFOLD_MASTER_GOAL.md
    section 14: "Expensive model calls should not be wasted on obviously
    poor prospects").

    Answers AIMFOLD_MASTER_GOAL.md section 8's questions at signal level
    (the Opportunity-level version of these same questions is PR8/PR9's
    job, once Opportunities exist): what was observed, why it's relevant
    to the Aim, how strong the evidence is, and — separately, and never
    blended with the above — what the model additionally infers.
    """

    observed_facts: list[str] = Field(
        ...,
        min_length=1,
        description="Direct quotes copied verbatim from the signal's normalized_text. Not paraphrases — evaluator.py verifies each one is a literal substring.",
    )
    inferences: list[str] = Field(
        default_factory=list,
        description="The model's interpretation of what the observed_facts likely mean. Clearly separate from observed_facts — never presented as fact.",
    )
    relevance_explanation: str = Field(..., min_length=1, description="Why this is relevant to the Aim's objective")
    why_now: str | None = Field(default=None, description="What makes this timely, if anything — null if there's no timing signal, not guessed")
    matched_positive_criteria: list[str] = Field(
        default_factory=list,
        description="Subset of the Aim's compiled_spec.positive_criteria this evidence supports — evaluator.py verifies these are real entries, not invented ones.",
    )
    evidence_strength: float = Field(..., ge=0.0, le=1.0)
    suggested_next_step: str | None = Field(
        default=None,
        description="Free-text suggestion only — the Recommended Action taxonomy is PR9's job, not this schema's.",
    )

    model_config = {"extra": "forbid"}


class EvidenceEvaluationResult(BaseModel):
    stage1: Stage1EvidenceResult
    assessment: EvidenceAssessment | None = Field(
        default=None, description="None when Stage 1 didn't qualify — Stage 2 was correctly skipped, not run and discarded"
    )
    evaluator_model: str | None = None
    evaluator_prompt_version: str | None = None
