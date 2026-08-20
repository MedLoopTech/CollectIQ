"""Run with: python aimfold_core/research/tests/test_research.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.llm_client import LLMClient, LLMResponse, StubLLMClient
from aimfold_core.research.synthesizer import ResearchSynthesisError, build_source_material, synthesize_entity_context

SIGNAL_1 = "Senior Accounts Receivable Analyst posting. Acme Freight Systems is scaling fast and chasing overdue invoices by hand in spreadsheets."
SIGNAL_2 = "Collections Specialist posting, two months later. Acme Freight Systems recently rolled out NetSuite but reconciliation across systems is still manual."

VALID_SUMMARY = json.dumps(
    {
        "key_facts": [
            "Acme Freight Systems is scaling fast",
            "chasing overdue invoices by hand in spreadsheets",
            "recently rolled out NetSuite",
        ],
        "inferences": ["The company is growing quickly and its finance operations haven't kept pace with that growth."],
        "notable_changes": ["Between the two postings, Acme adopted NetSuite but manual reconciliation persisted."],
        "open_questions": ["Company size and current AR headcount are not known from these postings."],
        "summary": "Acme Freight Systems is a fast-growing company with manual AR processes that a recent NetSuite rollout hasn't fully resolved.",
    }
)


def test_build_source_material_includes_everything_given():
    material = build_source_material("Acme Freight Systems", "acmefreight.com", [SIGNAL_1, SIGNAL_2], ["prior note: seen twice before"])
    assert "Acme Freight Systems" in material
    assert "acmefreight.com" in material
    assert SIGNAL_1 in material and SIGNAL_2 in material
    assert "prior note: seen twice before" in material
    print("PASS: build_source_material concatenates entity info + all signals + prior notes")


def test_synthesize_entity_context_happy_path():
    client = StubLLMClient({"chasing overdue invoices": VALID_SUMMARY})
    result = synthesize_entity_context("Acme Freight Systems", "acmefreight.com", [SIGNAL_1, SIGNAL_2], [], client)
    assert len(result.context.key_facts) == 3
    assert result.context.notable_changes
    assert result.researcher_model == "stub:stub-deterministic"
    print("PASS: synthesize_entity_context happy path with real substrings")


def test_synthesize_entity_context_requires_some_input():
    client = StubLLMClient({})
    try:
        synthesize_entity_context("Acme Freight Systems", None, [], [], client)
        raise AssertionError("expected ValueError — nothing to synthesize")
    except ValueError as exc:
        assert "Nothing to synthesize" in str(exc)
    print("PASS: synthesize_entity_context refuses to run with zero signals and zero prior notes")


class _SequenceLLMClient(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.call_count = 0

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        text = self._responses[self.call_count]
        self.call_count += 1
        return LLMResponse(text=text, provider="fake", model="fake-sequence")


FABRICATED_SUMMARY = json.dumps(
    {
        "key_facts": ["Acme Freight Systems raised a $50M Series B last quarter"],  # not in either signal
        "inferences": ["Well-funded and expanding rapidly."],
        "notable_changes": [],
        "open_questions": [],
        "summary": "Well-funded, fast-growing logistics company.",
    }
)


def test_synthesize_entity_context_rejects_fabricated_fact():
    client = _SequenceLLMClient([FABRICATED_SUMMARY, FABRICATED_SUMMARY, FABRICATED_SUMMARY])
    try:
        synthesize_entity_context("Acme Freight Systems", None, [SIGNAL_1, SIGNAL_2], [], client, max_attempts=3)
        raise AssertionError("expected ResearchSynthesisError — the funding claim was never in the source material")
    except ResearchSynthesisError as exc:
        assert "not a literal substring" in str(exc)
    assert client.call_count == 3
    print("PASS: synthesize_entity_context rejects a fabricated key_fact (invented funding round) after exhausting retries")


def test_synthesize_entity_context_recovers_after_bad_attempt():
    client = _SequenceLLMClient([FABRICATED_SUMMARY, VALID_SUMMARY])
    result = synthesize_entity_context("Acme Freight Systems", None, [SIGNAL_1, SIGNAL_2], [], client, max_attempts=3)
    assert client.call_count == 2
    assert result.context.summary
    print("PASS: synthesize_entity_context recovers on retry after one fabricated attempt")


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
