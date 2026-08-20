"""Turns a user's natural-language intent into a validated CompiledAimSpec.

Deterministic before AI (AIMFOLD_MASTER_GOAL.md section 28): the only AI
call here is interpreting free-text intent into structured fields. Parsing,
schema validation and retry control are plain code.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .llm_client import LLMClient
from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from .schema import AimCompilationResult, CompiledAimSpec

MAX_ATTEMPTS = 3

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AimCompilationError(RuntimeError):
    """Raised when the model's output can't be turned into a valid
    CompiledAimSpec after MAX_ATTEMPTS tries. Callers should surface this
    to a human rather than retry indefinitely (AIMFOLD_MASTER_GOAL.md
    section 4: the user approves or corrects the interpretation — a
    compiler that can't produce anything sensible is exactly the case
    that needs a human)."""


def _strip_code_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _extract_explanation_and_spec(raw_text: str) -> tuple[dict, str]:
    """The model is instructed to return only a JSON object, but models
    sometimes add a caption or wrap in prose anyway — extract the first
    top-level JSON object defensively rather than failing outright."""
    cleaned = _strip_code_fences(raw_text)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        obj = json.loads(cleaned[start : end + 1])
    explanation = obj.pop("explanation", None)
    if not explanation:
        raise ValueError("model output is missing required 'explanation' field")
    return obj, explanation


def compile_aim(
    raw_user_intent: str,
    llm_client: LLMClient,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> AimCompilationResult:
    """Compile raw_user_intent into a proposed (not yet approved)
    AimCompilationResult. Raises AimCompilationError if the model can't
    produce something schema-valid within max_attempts tries."""

    if not raw_user_intent or not raw_user_intent.strip():
        raise ValueError("raw_user_intent must be non-empty")

    schema_json = json.dumps(
        {**CompiledAimSpec.model_json_schema(), "explanation": "string, required — see instructions"},
        indent=2,
    )
    user_prompt = build_user_prompt(raw_user_intent, schema_json)

    last_error: Exception | None = None
    response = None
    for attempt in range(1, max_attempts + 1):
        response = llm_client.complete(SYSTEM_PROMPT, user_prompt)
        try:
            spec_dict, explanation = _extract_explanation_and_spec(response.text)
            compiled_spec = CompiledAimSpec.model_validate(spec_dict)
            return AimCompilationResult(
                raw_user_intent=raw_user_intent,
                compiled_spec=compiled_spec,
                explanation=explanation,
                compiler_model=f"{response.provider}:{response.model}",
                compiler_prompt_version=PROMPT_VERSION,
            )
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            user_prompt = (
                build_user_prompt(raw_user_intent, schema_json)
                + f"\n\nYour previous response failed validation with this error — fix it and "
                f"respond with the corrected JSON object only:\n{exc}"
            )

    raise AimCompilationError(
        f"Could not compile a valid Aim after {max_attempts} attempts. Last error: {last_error}"
    )
