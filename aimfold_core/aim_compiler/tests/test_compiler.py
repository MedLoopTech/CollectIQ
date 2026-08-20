"""Run with: python aimfold_core/aim_compiler/tests/test_compiler.py
(same convention as 02_audit_engine/test_golden.py — plain assertions, no
pytest dependency).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.compiler import AimCompilationError, compile_aim
from aimfold_core.aim_compiler.llm_client import LLMClient, LLMResponse, StubLLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"


def load_collectiq_compiled_spec() -> dict:
    """Extract the compiled_spec jsonb literal straight from the PR3 seed
    migration, so this test breaks if that file and this schema drift."""
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match, "could not find $spec$...$spec$ block in seed migration"
    return json.loads(match.group(1))


def test_real_collectiq_spec_validates_against_schema():
    """Regression check tying PR3's seed data to PR4's schema: if either
    drifts from the other, this fails."""
    spec_dict = load_collectiq_compiled_spec()
    spec = CompiledAimSpec.model_validate(spec_dict)
    assert spec.opportunity_type == "customer_discovery"
    assert len(spec.scoring_weights) == 11
    assert spec.confidence_thresholds.qualified_signal_min_score == 60
    print("PASS: real CollectIQ compiled_spec validates against CompiledAimSpec")


VALID_CANNED_RESPONSE = json.dumps(
    {
        "explanation": "I'll watch for finance/data roles in the US where a background in finance transformation is an unusual advantage.",
        "objective": "Find roles where the user's finance transformation background is a strong differentiator.",
        "opportunity_type": "career_discovery",
        "target_entity_types": ["job", "employer"],
        "geography": ["United States"],
        "industries": [],
        "positive_criteria": ["role mentions finance transformation", "role mentions ERP migration"],
        "negative_criteria": [],
        "exclusions": [],
        "freshness_requirements": None,
        "likely_sources": ["linkedin_jobs_apify", "indeed_jobs_apify"],
        "evidence_requirements": ["job posting text matches a positive_criteria pattern"],
        "scoring_dimensions": ["keyword_match"],
        "scoring_weights": [
            {"pattern": "finance transformation", "points": 40, "label": "finance transformation"},
            {"pattern": "erp migration|erp implementation", "points": 30, "label": "ERP migration"},
        ],
        "confidence_thresholds": {"qualified_signal_min_score": 50, "max_score": 100},
        "likely_actions": ["apply", "research"],
        "notification_preferences": {},
    }
)


def test_compile_aim_happy_path():
    client = StubLLMClient({"finance transformation background": VALID_CANNED_RESPONSE})
    result = compile_aim(
        "Find finance/data roles where my finance transformation background creates an unusual advantage.",
        client,
    )
    assert result.compiled_spec.opportunity_type == "career_discovery"
    assert result.compiled_spec.likely_actions == ["apply", "research"]
    assert "finance transformation" in result.explanation
    assert result.compiler_model == "stub:stub-deterministic"
    print("PASS: compile_aim happy path")


def test_compile_aim_strips_markdown_fences():
    fenced = f"```json\n{VALID_CANNED_RESPONSE}\n```"
    client = StubLLMClient({"fenced intent": fenced})
    result = compile_aim("fenced intent", client)
    assert result.compiled_spec.opportunity_type == "career_discovery"
    print("PASS: compile_aim strips markdown code fences")


class _SequenceLLMClient(LLMClient):
    """Returns a different canned response on each successive call —
    used to test the retry-on-validation-failure path."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.call_count = 0

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        text = self._responses[self.call_count]
        self.call_count += 1
        return LLMResponse(text=text, provider="fake", model="fake-sequence")


def test_compile_aim_retries_on_invalid_output_then_succeeds():
    bad_json = "this is not json at all"
    invalid_schema = json.dumps({"explanation": "missing everything else"})
    client = _SequenceLLMClient([bad_json, invalid_schema, VALID_CANNED_RESPONSE])
    result = compile_aim("retry me", client)
    assert client.call_count == 3
    assert result.compiled_spec.opportunity_type == "career_discovery"
    print("PASS: compile_aim retries invalid output and eventually succeeds")


def test_compile_aim_raises_after_max_attempts():
    client = _SequenceLLMClient(["nope", "still nope", "nope again"])
    try:
        compile_aim("never works", client, max_attempts=3)
        raise AssertionError("expected AimCompilationError")
    except AimCompilationError:
        pass
    assert client.call_count == 3
    print("PASS: compile_aim raises AimCompilationError after exhausting attempts")


def test_scoring_weight_rejects_invalid_regex():
    spec_dict = load_collectiq_compiled_spec()
    spec_dict = {**spec_dict, "scoring_weights": [{"pattern": "(unclosed", "points": 10, "label": "bad"}]}
    try:
        CompiledAimSpec.model_validate(spec_dict)
        raise AssertionError("expected a validation error for an invalid regex pattern")
    except Exception as exc:  # pydantic.ValidationError
        assert "not a valid regex" in str(exc)
    print("PASS: CompiledAimSpec rejects an invalid regex pattern")


def test_confidence_threshold_cannot_exceed_max_score():
    # Both values individually satisfy their own field bounds (0-100); only
    # the cross-field relationship (threshold <= max_score) is violated —
    # isolates the model_validator from the plain per-field le=100 checks.
    spec_dict = load_collectiq_compiled_spec()
    spec_dict = {**spec_dict, "confidence_thresholds": {"qualified_signal_min_score": 90, "max_score": 50}}
    try:
        CompiledAimSpec.model_validate(spec_dict)
        raise AssertionError("expected a validation error for threshold > max_score")
    except Exception as exc:
        assert "cannot exceed max_score" in str(exc)
    print("PASS: CompiledAimSpec rejects qualified_signal_min_score > max_score")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            failures += 1
            print(f"FAIL: {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
