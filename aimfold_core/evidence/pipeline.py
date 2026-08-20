"""Two-stage evidence pipeline (AIMFOLD_MASTER_GOAL.md section 14):
Stage 1 always runs and is free; Stage 2 (the LLM call) only runs if
Stage 1 qualifies. Storage-agnostic, like aim_compiler — the caller
decides how/whether to persist the result onto a signals row.
"""

from __future__ import annotations

from aimfold_core.aim_compiler.llm_client import LLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec

from .evaluator import evaluate_evidence
from .extractor import extract_stage1_evidence
from .prompt import PROMPT_VERSION
from .schema import EvidenceEvaluationResult


def assess_signal_evidence(
    normalized_text: str,
    compiled_spec: CompiledAimSpec,
    llm_client: LLMClient | None,
) -> EvidenceEvaluationResult:
    """Runs Stage 1 always. Runs Stage 2 only if Stage 1 qualifies AND an
    llm_client was provided (pass None to force Stage-1-only, e.g. for a
    cost-capped run or before a provider key is configured)."""

    stage1 = extract_stage1_evidence(compiled_spec, normalized_text)

    if not stage1.qualifies or llm_client is None:
        return EvidenceEvaluationResult(stage1=stage1)

    assessment, evaluator_model = evaluate_evidence(normalized_text, compiled_spec, stage1, llm_client)
    return EvidenceEvaluationResult(
        stage1=stage1,
        assessment=assessment,
        evaluator_model=evaluator_model,
        evaluator_prompt_version=PROMPT_VERSION,
    )


__all__ = ["assess_signal_evidence"]
