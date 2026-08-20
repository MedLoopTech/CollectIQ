"""Run with: python aimfold_core/evaluation/tests/test_evaluation.py

Fully offline (StubLLMClient, no API cost/network) — this is the suite
meant to run on every change, fast. Live calibration against a real
model is a separate, manual, one-off run (see the PR13 write-up), not
part of this automated suite.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.llm_client import StubLLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evaluation.dataset import COLLECTIQ_EVAL_V1
from aimfold_core.evaluation.regression import compare_eval_reports
from aimfold_core.evaluation.runner import run_evaluation

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"


def load_collectiq_spec() -> CompiledAimSpec:
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match
    return CompiledAimSpec.model_validate(json.loads(match.group(1)))


def test_dataset_covers_the_five_evaluable_categories():
    categories = {ex.expected_category for ex in COLLECTIQ_EVAL_V1}
    assert categories == {"excellent", "acceptable", "false_positive", "irrelevant_signal", "ambiguous"}
    print(f"PASS: dataset covers all 5 evaluable categories across {len(COLLECTIQ_EVAL_V1)} examples")


def test_run_evaluation_stage1_only():
    spec = load_collectiq_spec()
    report = run_evaluation(COLLECTIQ_EVAL_V1, spec, None, dataset_name="test-stage1-only")
    assert report.stage2_ran is False
    assert all(r.passed_qualification_check for r in report.results), [
        (r.example_id, r.stage1_qualifies) for r in report.results if not r.passed_qualification_check
    ]
    assert report.calibration_accuracy is None
    assert report.evidence_grounding_accuracy is None
    print(f"PASS: Stage-1-only run — all {report.n_examples} qualification labels correct, calibration/grounding correctly None")


# Canned Stage-2 responses. The false-positive one models what a
# CORRECTLY FUNCTIONING evaluator should say (this offline suite tests
# the harness's own machinery with a controlled "good" response; whether
# the real model actually behaves this well is verified live — see the
# PR13 write-up).
_STAGE2_RESPONSES = {
    "our AR team is drowning in manual work": json.dumps({
        "observed_facts": [
            "our AR team is drowning in manual work",
            "chasing overdue invoices by hand in spreadsheets",
            "Recently rolled out NetSuite",
        ],
        "inferences": ["Manual AR processes are causing operational strain."],
        "relevance_explanation": "Explicit AR hiring with manual spreadsheet workflow and ERP context.",
        "why_now": "Recently rolled out NetSuite",
        "matched_positive_criteria": ["AR hiring", "disputes", "spreadsheet workflow", "ERP/accounting system"],
        "evidence_strength": 0.95,
        "suggested_next_step": "Reach out about the AR Intelligence Audit.",
    }),
    "review aging reports weekly": json.dumps({
        "observed_facts": ["Chase overdue invoices", "review aging reports weekly", "high volume of accounts", "tracked in spreadsheets"],
        "inferences": ["A mid-size collections operation still on manual tracking."],
        "relevance_explanation": "Collections role with aging review and spreadsheet-based high-volume tracking.",
        "why_now": None,
        "matched_positive_criteria": ["collections/credit control", "ageing", "spreadsheet workflow", "high volume"],
        "evidence_strength": 0.65,
        "suggested_next_step": None,
    }),
    "immersive augmented reality experiences": json.dumps({
        "observed_facts": ["Build immersive augmented reality experiences", "We use spreadsheets for high volume project reporting"],
        "inferences": ["This is a software engineering role for AR/VR product development, unrelated to accounts receivable."],
        "relevance_explanation": "The 'AR' match is augmented reality, not accounts receivable; the spreadsheet/reporting mention is about software project tracking, not financial operations. No genuine AR/collections signal present.",
        "why_now": None,
        "matched_positive_criteria": [],
        "evidence_strength": 0.05,
        "suggested_next_step": None,
    }),
    "own the full AR cycle": json.dumps({
        "observed_facts": [
            "own the full AR cycle", "aging, collections calls, dispute resolution", "cash application posting",
            "High volume portfolio", "using Excel for tracking",
        ],
        "inferences": ["A comprehensive, still-manual AR role covering the entire collections cycle."],
        "relevance_explanation": "Matches nearly every positive criterion directly — full AR ownership, collections, aging, disputes, cash application, high volume, and spreadsheet tracking.",
        "why_now": None,
        "matched_positive_criteria": ["AR hiring", "collections/credit control", "ageing", "disputes", "cash application", "high volume", "spreadsheet workflow"],
        "evidence_strength": 0.98,
        "suggested_next_step": "Reach out about the AR Intelligence Audit.",
    }),
}


def test_run_evaluation_with_stage2():
    spec = load_collectiq_spec()
    client = StubLLMClient(_STAGE2_RESPONSES)
    report = run_evaluation(COLLECTIQ_EVAL_V1, spec, client, dataset_name="test-stage1-and-2")

    assert report.stage2_ran is True
    assert report.calibration_accuracy is not None
    assert report.evidence_grounding_accuracy is not None
    assert report.action_recommendation_quality is not None

    by_id = {r.example_id: r for r in report.results}

    fp = by_id["false-positive-ar-vr-engineer"]
    assert fp.stage1_qualifies is True  # Stage 1 is wrong here, by design
    assert fp.stage2_ran is True
    assert fp.matched_positive_criteria == []
    assert fp.passed_grounding_check is True  # correctly found nothing, matching expected_matched_criteria=[]
    assert fp.total_score < by_id["excellent-ar-analyst-acme"].total_score, (
        "a correctly-functioning Stage 2 should score the false positive well below a genuine excellent example"
    )
    print(f"PASS: false-positive example — Stage 1 wrongly qualified it (score={fp.stage1_score}), "
          f"Stage 2 correctly found no supporting evidence, total_score dropped to {fp.total_score}")

    for r in report.results:
        if r.passed_calibration_check is not None:
            assert r.passed_calibration_check, f"{r.example_id} total_score={r.total_score} outside its expected_score_range"
    print("PASS: every example with a Stage-2 result falls within its expected_score_range")

    # precision is measured at the Stage-1 gate (the real gate that routes
    # a signal to Stage 2 in production), so it's honestly imperfect here:
    # 3 positives (2 excellent + 1 acceptable) all qualify at Stage 1, but
    # so does the false-positive example -> 3/(3+1) = 0.75. That's the
    # whole point of including it — Stage 1 alone would surface a false
    # positive 25% of the time in this dataset; Stage 2 is what actually
    # catches it (see the assertions above), which precision-at-Stage-1
    # deliberately does NOT credit, so a real regression in Stage 1's
    # keyword rules would still show up here even if Stage 2 papers over it.
    assert report.precision == 0.75, report.precision
    print(f"PASS: full run metrics — precision={report.precision} (honestly imperfect at the Stage-1 gate, by design), "
          f"false_positive_rate={report.false_positive_rate}, accepted_opportunity_rate={report.accepted_opportunity_rate}, "
          f"ranking_quality={report.ranking_quality}, calibration_accuracy={report.calibration_accuracy}, "
          f"evidence_grounding_accuracy={report.evidence_grounding_accuracy}")


def test_regression_comparator_flags_a_real_regression():
    spec = load_collectiq_spec()
    good_client = StubLLMClient(_STAGE2_RESPONSES)
    baseline = run_evaluation(COLLECTIQ_EVAL_V1, spec, good_client, dataset_name="baseline")

    # Simulate a broken Stage-2 prompt: it now claims to find AR relevance
    # in the false-positive example too (the exact regression this dataset
    # exists to catch).
    broken_responses = dict(_STAGE2_RESPONSES)
    broken_responses["immersive augmented reality experiences"] = json.dumps({
        "observed_facts": ["Build immersive augmented reality experiences", "We use spreadsheets for high volume project reporting"],
        "inferences": ["Strong AR hiring signal."],
        "relevance_explanation": "This role is hiring for AR.",
        "why_now": None,
        "matched_positive_criteria": ["AR hiring", "spreadsheet workflow", "high volume"],
        "evidence_strength": 0.9,
        "suggested_next_step": "Reach out immediately.",
    })
    broken_client = StubLLMClient(broken_responses)
    candidate = run_evaluation(COLLECTIQ_EVAL_V1, spec, broken_client, dataset_name="candidate-broken")

    report = compare_eval_reports(baseline, candidate, tolerance=0.05)
    assert report.has_regression, "expected a flagged regression once the false-positive example starts passing again"
    regressed_metrics = {f.metric for f in report.findings if f.is_regression}
    assert regressed_metrics, "no metric was flagged as regressed"
    print(f"PASS: compare_eval_reports flags a real regression — regressed metrics: {sorted(regressed_metrics)}")


def test_regression_comparator_no_false_alarm_on_identical_runs():
    spec = load_collectiq_spec()
    client = StubLLMClient(_STAGE2_RESPONSES)
    a = run_evaluation(COLLECTIQ_EVAL_V1, spec, client, dataset_name="a")
    b = run_evaluation(COLLECTIQ_EVAL_V1, spec, client, dataset_name="b")
    report = compare_eval_reports(a, b, tolerance=0.05)
    assert not report.has_regression
    print("PASS: compare_eval_reports reports no regression between two identical runs")


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
