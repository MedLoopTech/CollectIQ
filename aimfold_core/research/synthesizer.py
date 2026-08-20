"""Research synthesis: one LLM call, same shape as
aimfold_core.evidence.evaluator (parse -> validate -> anti-fabrication
check -> retry-with-feedback, up to 3 attempts)."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from aimfold_core.aim_compiler.llm_client import LLMClient

from .prompt import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from .schema import EntityContextSummary, ResearchResult

MAX_ATTEMPTS = 3

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class ResearchSynthesisError(RuntimeError):
    """Raised when the model can't produce a valid, non-fabricated
    EntityContextSummary after MAX_ATTEMPTS tries."""


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


def _verify_no_fabrication(summary: EntityContextSummary, source_material: str) -> None:
    haystack = source_material.lower()
    for fact in summary.key_facts:
        if fact.strip().lower() not in haystack:
            raise ValueError(
                f"key_fact {fact!r} is not a literal substring of the provided source material — "
                "every key_fact must be an exact quote, not a paraphrase or invention."
            )


def build_source_material(entity_name: str, entity_domain: str | None, signal_texts: list[str], prior_notes: list[str]) -> str:
    """Concatenates everything Aimfold actually knows about an entity
    into one block of text — the ONLY thing the model is allowed to draw
    key_facts from. Callers build signal_texts/prior_notes from real
    signals.normalized_text and entity_memory.payload rows; this function
    doesn't query the database itself (storage-agnostic, same as the
    rest of aimfold_core)."""

    parts = [f"Entity name: {entity_name}"]
    if entity_domain:
        parts.append(f"Entity domain: {entity_domain}")
    for i, text in enumerate(signal_texts, 1):
        parts.append(f"--- Signal {i} ---\n{text}")
    for i, note in enumerate(prior_notes, 1):
        parts.append(f"--- Prior research note {i} ---\n{note}")
    return "\n\n".join(parts)


def synthesize_entity_context(
    entity_name: str,
    entity_domain: str | None,
    signal_texts: list[str],
    prior_notes: list[str],
    llm_client: LLMClient,
    *,
    max_attempts: int = MAX_ATTEMPTS,
) -> ResearchResult:
    if not signal_texts and not prior_notes:
        raise ValueError("Nothing to synthesize — need at least one signal text or prior research note.")

    source_material = build_source_material(entity_name, entity_domain, signal_texts, prior_notes)
    schema_json = json.dumps(EntityContextSummary.model_json_schema(), indent=2)
    user_prompt = build_user_prompt(entity_name, entity_domain, source_material, schema_json)

    last_error: Exception | None = None
    response = None
    for attempt in range(1, max_attempts + 1):
        response = llm_client.complete(SYSTEM_PROMPT, user_prompt)
        try:
            obj = _parse_json_object(response.text)
            summary = EntityContextSummary.model_validate(obj)
            _verify_no_fabrication(summary, source_material)
            return ResearchResult(
                context=summary,
                researcher_model=f"{response.provider}:{response.model}",
                researcher_prompt_version=PROMPT_VERSION,
            )
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            last_error = exc
            user_prompt = (
                build_user_prompt(entity_name, entity_domain, source_material, schema_json)
                + f"\n\nYour previous response failed validation with this error — fix it and "
                f"respond with the corrected JSON object only:\n{exc}"
            )

    raise ResearchSynthesisError(
        f"Could not produce a valid, non-fabricated EntityContextSummary after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )


__all__ = ["synthesize_entity_context", "build_source_material", "ResearchSynthesisError", "PROMPT_VERSION"]
