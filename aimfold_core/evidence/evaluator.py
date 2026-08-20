"""Stage-2 evidence evaluation: the one LLM call in this module, reserved
for signals that already qualify at Stage 1 (AIMFOLD_MASTER_GOAL.md
section 14 — deterministic first, AI only where it adds real value).
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from aimfold_core.aim_compiler.llm_client import LLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec

from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from .schema import EvidenceAssessment, Stage1EvidenceResult

MAX_ATTEMPTS = 3

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class EvidenceEvaluationError(RuntimeError):
    """Raised when the model can't produce a valid, non-fabricated
    EvidenceAssessment after MAX_ATTEMPTS tries. Callers should treat this
    signal as unevaluated (hold it), not assume it's weak — a model that
    keeps hallucinating quotes is a model/prompt problem, not evidence
    about the signal itself."""


def _strip_code_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _parse_json_object(raw_text: str) -> dict:
    cleaned = _strip_code_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def _verify_no_fabrication(assessment: EvidenceAssessment, signal_text: str, positive_criteria: list[str]) -> None:
    """The enforcement half of Evidence-First — not just a prompt ask."""
    haystack = signal_text.lower()
    for fact in assessment.observed_facts:
        if fact.strip().lower() not in haystack:
            raise ValueError(
                f"observed_fact {fact!r} is not a literal substring of the signal text — "
                "every observed_fact must be an exact quote, not a paraphrase or invention."
            )
    criteria_set = {c.strip().lower() for c in positive_criteria}
    for claimed in assessment.matched_positive_criteria:
        if claimed.strip().lower() not in criteria_set:
            raise ValueError(
                f"matched_positive_criteria entry {claimed!r} is not one of the Aim's actual "
                "positive_criteria — do not paraphrase or invent criteria."
            )


def evaluate_evidence(
    signal_text: str,
    compiled_spec: CompiledAimSpec,
    stage1_result: Stage1EvidenceResult,
    llm_client: LLMClient,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> tuple[EvidenceAssessment, str]:
    """Returns (assessment, evaluator_model). Raises EvidenceEvaluationError
    if the model can't pass fabrication checks within max_attempts."""

    if not signal_text or not signal_text.strip():
        raise ValueError("signal_text must be non-empty")

    schema_json = json.dumps(EvidenceAssessment.model_json_schema(), indent=2)
    user_prompt = build_user_prompt(
        signal_text, compiled_spec.objective, compiled_spec.positive_criteria, stage1_result.labels, schema_json
    )

    last_error: Exception | None = None
    response = None
    for attempt in range(1, max_attempts + 1):
        response = llm_client.complete(SYSTEM_PROMPT, user_prompt)
        try:
            obj = _parse_json_object(response.text)
            assessment = EvidenceAssessment.model_validate(obj)
            _verify_no_fabrication(assessment, signal_text, compiled_spec.positive_criteria)
            return assessment, f"{response.provider}:{response.model}"
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            user_prompt = (
                build_user_prompt(
                    signal_text, compiled_spec.objective, compiled_spec.positive_criteria, stage1_result.labels, schema_json
                )
                + f"\n\nYour previous response failed validation with this error — fix it and "
                f"respond with the corrected JSON object only:\n{exc}"
            )

    raise EvidenceEvaluationError(
        f"Could not produce a valid, non-fabricated EvidenceAssessment after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )


__all__ = ["evaluate_evidence", "EvidenceEvaluationError", "PROMPT_VERSION"]
