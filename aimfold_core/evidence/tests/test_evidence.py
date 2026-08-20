"""Run with: python aimfold_core/evidence/tests/test_evidence.py"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.llm_client import LLMClient, LLMResponse, StubLLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evidence.evaluator import EvidenceEvaluationError, evaluate_evidence
from aimfold_core.evidence.extractor import extract_stage1_evidence
from aimfold_core.evidence.pipeline import assess_signal_evidence

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"


def load_collectiq_spec() -> CompiledAimSpec:
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match
    return CompiledAimSpec.model_validate(json.loads(match.group(1)))


# ---- ground truth, transcribed from the n8n "Score Signal Against Aim" node ----
def original_n8n_score(job_title: str, description: str) -> tuple[int, list[str]]:
    text = f"{job_title or ''} {description or ''}".lower()
    score = 0
    signals = []

    def hit(pattern, pts, label):
        nonlocal score
        if re.search(pattern, text):
            score += pts
            signals.append(label)

    hit(r"accounts receivable|\bar\b", 25, "AR hiring")
    hit(r"collections?|credit controller", 30, "collections/credit control")
    hit(r"aging|ageing", 10, "ageing")
    hit(r"promise to pay|payment promise|payment commitment|ptp", 15, "payment commitments")
    hit(r"dispute|billing discrepancy|invoice discrepancy", 15, "disputes")
    hit(r"excel|spreadsheet|google sheets", 10, "spreadsheet workflow")
    hit(r"netsuite|quickbooks|xero|sage|dynamics|sap|oracle", 15, "ERP/accounting system")
    hit(r"high volume|large volume|portfolio|hundreds of invoices", 15, "high volume")
    hit(r"cash application", 8, "cash application")
    hit(r"weekly report|reporting|aging report|ageing report", 10, "reporting")
    hit(r"follow[- ]?up|chase invoices|contact customers|customer outreach", 10, "manual follow-up")
    return min(score, 100), signals


def test_stage1_matches_n8n_scorer_behavior():
    spec = load_collectiq_spec()
    cases = [
        ("Accounts Receivable Specialist", "Manage aging reports, chase invoices, follow up with customers using Excel spreadsheets. QuickBooks experience a plus."),
        ("Credit Controller", "Handle disputes and payment promise tracking across a large volume portfolio of accounts."),
        ("Warehouse Associate", "Lift boxes, operate forklift, general warehouse duties."),
        ("Collections Specialist", "Cash application, weekly reporting, NetSuite, high volume of hundreds of invoices."),
    ]
    for title, desc in cases:
        expected_score, expected_labels = original_n8n_score(title, desc)
        result = extract_stage1_evidence(spec, f"{title} {desc}")
        assert result.score == expected_score, f"{title}: {result.score} != {expected_score}"
        assert result.labels == expected_labels, f"{title}: {result.labels} != {expected_labels}"
    print("PASS: extract_stage1_evidence matches the n8n scorer byte-for-byte")


def test_stage1_qualification_threshold():
    spec = load_collectiq_spec()
    warehouse = extract_stage1_evidence(spec, "Warehouse Associate: lift boxes, operate forklift")
    assert warehouse.score == 0 and not warehouse.qualifies
    ar_specialist = extract_stage1_evidence(
        spec, "Accounts Receivable Specialist: aging reports, chase invoices, Excel spreadsheets, QuickBooks"
    )
    assert ar_specialist.qualifies and ar_specialist.score >= 60
    print("PASS: stage1 qualification threshold (60) behaves correctly")


class _PoisonLLMClient(LLMClient):
    """Raises if called at all — proves Stage 2 was skipped, not just discarded."""

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        raise AssertionError("LLM should not have been called — Stage 1 did not qualify")


def test_pipeline_skips_stage2_when_stage1_fails():
    spec = load_collectiq_spec()
    result = assess_signal_evidence("Warehouse Associate: lift boxes, operate forklift", spec, _PoisonLLMClient())
    assert not result.stage1.qualifies
    assert result.assessment is None
    assert result.evaluator_model is None
    print("PASS: pipeline skips Stage 2 entirely when Stage 1 doesn't qualify")


def test_pipeline_skips_stage2_when_no_client_provided():
    spec = load_collectiq_spec()
    result = assess_signal_evidence(
        "Accounts Receivable Specialist: aging reports, chase invoices, Excel spreadsheets, QuickBooks", spec, None
    )
    assert result.stage1.qualifies
    assert result.assessment is None
    print("PASS: pipeline stays Stage-1-only when llm_client=None, even if Stage 1 qualifies")


SIGNAL_TEXT = (
    "Accounts Receivable Specialist. We need someone to manage our aging reports and chase "
    "invoices. Currently using Excel spreadsheets for everything. QuickBooks experience a plus."
)

VALID_ASSESSMENT = json.dumps(
    {
        "observed_facts": ["manage our aging reports and chase", "using Excel spreadsheets for everything"],
        "inferences": ["The company likely lacks a dedicated AR system and relies on manual processes."],
        "relevance_explanation": "This role directly matches AR hiring and manual spreadsheet-based collections workflow.",
        "why_now": None,
        "matched_positive_criteria": ["AR hiring", "spreadsheet workflow"],
        "evidence_strength": 0.8,
        "suggested_next_step": "Worth deeper research on company size and AR volume.",
    }
)


def test_evaluate_evidence_happy_path():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, SIGNAL_TEXT)
    client = StubLLMClient({"aging reports and chase": VALID_ASSESSMENT})
    assessment, model = evaluate_evidence(SIGNAL_TEXT, spec, stage1, client)
    assert assessment.evidence_strength == 0.8
    assert "AR hiring" in assessment.matched_positive_criteria
    assert model == "stub:stub-deterministic"
    print("PASS: evaluate_evidence happy path with real substrings")


class _SequenceLLMClient(LLMClient):
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.call_count = 0

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        text = self._responses[self.call_count]
        self.call_count += 1
        return LLMResponse(text=text, provider="fake", model="fake-sequence")


FABRICATED_ASSESSMENT = json.dumps(
    {
        "observed_facts": ["the company just fired their entire finance team"],  # not in SIGNAL_TEXT at all
        "inferences": ["Desperate need for AR help."],
        "relevance_explanation": "Strong AR signal.",
        "why_now": "Immediate — team was just fired",
        "matched_positive_criteria": ["AR hiring"],
        "evidence_strength": 0.95,
        "suggested_next_step": None,
    }
)


def test_evaluate_evidence_rejects_fabricated_observed_fact():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, SIGNAL_TEXT)
    client = _SequenceLLMClient([FABRICATED_ASSESSMENT, FABRICATED_ASSESSMENT, FABRICATED_ASSESSMENT])
    try:
        evaluate_evidence(SIGNAL_TEXT, spec, stage1, client, max_attempts=3)
        raise AssertionError("expected EvidenceEvaluationError — the observed_fact was never in the source text")
    except EvidenceEvaluationError as exc:
        assert "not a literal substring" in str(exc)
    assert client.call_count == 3
    print("PASS: evaluate_evidence rejects a fabricated observed_fact after exhausting retries")


INVENTED_CRITERION_ASSESSMENT = json.dumps(
    {
        "observed_facts": ["manage our aging reports and chase"],
        "inferences": [],
        "relevance_explanation": "Matches AR hiring.",
        "why_now": None,
        "matched_positive_criteria": ["AR hiring", "a criterion that was never in the Aim"],
        "evidence_strength": 0.7,
        "suggested_next_step": None,
    }
)


def test_evaluate_evidence_rejects_invented_criterion():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, SIGNAL_TEXT)
    client = _SequenceLLMClient([INVENTED_CRITERION_ASSESSMENT, INVENTED_CRITERION_ASSESSMENT, INVENTED_CRITERION_ASSESSMENT])
    try:
        evaluate_evidence(SIGNAL_TEXT, spec, stage1, client, max_attempts=3)
        raise AssertionError("expected EvidenceEvaluationError — the criterion was never in compiled_spec.positive_criteria")
    except EvidenceEvaluationError as exc:
        assert "not one of the Aim's actual" in str(exc)
    print("PASS: evaluate_evidence rejects an invented positive_criteria entry")


def test_evaluate_evidence_recovers_after_one_bad_attempt():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, SIGNAL_TEXT)
    client = _SequenceLLMClient([FABRICATED_ASSESSMENT, VALID_ASSESSMENT])
    assessment, _ = evaluate_evidence(SIGNAL_TEXT, spec, stage1, client, max_attempts=3)
    assert client.call_count == 2
    assert assessment.evidence_strength == 0.8
    print("PASS: evaluate_evidence recovers on retry after one fabricated attempt")


def test_full_pipeline_end_to_end_with_stub():
    spec = load_collectiq_spec()
    client = StubLLMClient({"aging reports and chase": VALID_ASSESSMENT})
    result = assess_signal_evidence(SIGNAL_TEXT, spec, client)
    assert result.stage1.qualifies
    assert result.assessment is not None
    assert result.evaluator_model == "stub:stub-deterministic"
    assert result.evaluator_prompt_version
    print("PASS: full assess_signal_evidence pipeline end-to-end (stage1 + stage2)")


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
