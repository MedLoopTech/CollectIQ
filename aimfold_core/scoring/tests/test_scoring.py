"""Run with: python aimfold_core/scoring/tests/test_scoring.py"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evidence.extractor import extract_stage1_evidence
from aimfold_core.evidence.schema import EvidenceAssessment
from aimfold_core.scoring.engine import score_signal
from aimfold_core.scoring.schema import DEFAULT_SCORING_WEIGHTS, ScoringWeights

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"


def load_collectiq_spec() -> CompiledAimSpec:
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match
    return CompiledAimSpec.model_validate(json.loads(match.group(1)))


def test_default_weights_match_spec_section_13():
    w = DEFAULT_SCORING_WEIGHTS
    assert w.aim_fit == 20
    assert w.evidence_strength == 25
    assert w.timing_trigger_strength == 20
    assert w.opportunity_relevance == 15
    assert w.evidence_confidence == 10
    assert w.source_quality == 5
    assert w.actionability == 5
    print("PASS: DEFAULT_SCORING_WEIGHTS matches AIMFOLD_MASTER_GOAL.md section 13 exactly (20/25/20/15/10/5/5)")


def test_weights_must_sum_to_100():
    try:
        ScoringWeights(aim_fit=50, evidence_strength=25, timing_trigger_strength=20, opportunity_relevance=15, evidence_confidence=10, source_quality=5, actionability=5)
        raise AssertionError("expected a validation error — weights sum to 130, not 100")
    except ValidationError as exc:
        assert "must sum to 100" in str(exc)
    # a custom-but-valid distribution (different Aim type) is fine
    custom = ScoringWeights(aim_fit=30, evidence_strength=30, timing_trigger_strength=15, opportunity_relevance=10, evidence_confidence=10, source_quality=3, actionability=2)
    assert custom.aim_fit == 30
    print("PASS: ScoringWeights rejects a set that doesn't sum to 100, accepts a valid custom distribution")


# Real Gemini output captured while testing PR6 (aimfold_core/evidence) —
# used here as-is rather than a synthetic fixture, so this scoring test is
# grounded in genuine model output, not just hand-written text.
REAL_EVIDENCE_ASSESSMENT = EvidenceAssessment(
    observed_facts=[
        "Senior Accounts Receivable Analyst",
        "our AR team is drowning in manual work",
        "chasing overdue invoices by hand in spreadsheets",
        "reconciling disputes across three different systems",
        "Recently rolled out NetSuite",
        "build weekly aging reports for leadership",
    ],
    inferences=[
        "The team is experiencing significant operational strain due to rapid scaling and inefficient legacy processes.",
        "The recent NetSuite implementation was likely rushed or incomplete, as the manual spreadsheet workflows and reconciliation issues persist across multiple systems.",
        "Management requires better visibility into receivables, indicating pressure on leadership regarding cash flow and collections.",
    ],
    relevance_explanation="The job posting explicitly highlights severe AR operational bottlenecks, including manual spreadsheet workflows, dispute reconciliation across multiple systems, and ageing reporting needs following an ERP rollout.",
    why_now="Recently rolled out NetSuite",
    matched_positive_criteria=["AR hiring", "ageing", "disputes", "spreadsheet workflow", "ERP/accounting system", "reporting", "manual follow-up"],
    evidence_strength=0.95,
    suggested_next_step="Reach out to the hiring manager or finance leadership at Acme Freight Systems to offer CollectIQ's AR Intelligence Audit and Managed Recovery service.",
)

REAL_SIGNAL_TEXT = (
    "Senior Accounts Receivable Analyst. Acme Freight Systems is scaling fast and our AR team "
    "is drowning in manual work — we're chasing overdue invoices by hand in spreadsheets and "
    "reconciling disputes across three different systems. Recently rolled out NetSuite but the "
    "old process hasn't caught up. Looking for someone who can also help us build weekly aging "
    "reports for leadership."
)


def test_score_signal_with_real_stage2_evidence():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, REAL_SIGNAL_TEXT)
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    published_at = now - timedelta(days=2)

    result = score_signal(
        spec,
        stage1,
        REAL_EVIDENCE_ASSESSMENT,
        entity_type_matches=True,
        geography_matches=True,
        excluded=False,
        published_at=published_at,
        source_quality=0.7,
        now=now,
    )

    assert 0 <= result.total_score <= 100
    assert result.dimension("evidence_strength").raw_value == 0.95
    assert result.dimension("timing_trigger_strength").raw_value > 0.6  # has why_now + fresh (2 days)
    assert result.dimension("opportunity_relevance").raw_value == 7 / 11  # 7 matched of 11 CollectIQ positive_criteria
    assert result.dimension("evidence_confidence").raw_value == 1.0  # 6 observed_facts >= 4 cap -> full bonus
    assert result.dimension("aim_fit").raw_value == 1.0  # entity type + geography both match, not excluded
    assert result.scoring_version
    print(f"PASS: score_signal on real Gemini evidence -> total_score={result.total_score}/100")
    for d in result.dimensions:
        print(f"   {d.name}: {d.points:.1f}/{d.weight} — {d.rationale}")


def test_score_signal_stage1_only_scores_lower_than_stage2():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, REAL_SIGNAL_TEXT)
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)

    stage1_only = score_signal(spec, stage1, None, entity_type_matches=True, geography_matches=True, now=now)
    with_stage2 = score_signal(
        spec, stage1, REAL_EVIDENCE_ASSESSMENT, entity_type_matches=True, geography_matches=True,
        published_at=now - timedelta(days=2), now=now,
    )

    assert stage1_only.total_score < with_stage2.total_score
    for d in stage1_only.dimensions:
        if d.name in ("evidence_strength", "timing_trigger_strength", "opportunity_relevance", "evidence_confidence"):
            assert "No Stage-2 evaluation ran" in d.rationale
    print(f"PASS: Stage-1-only score ({stage1_only.total_score}) is honestly lower than Stage-1+2 score ({with_stage2.total_score})")


def test_exclusion_forces_aim_fit_to_zero():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, REAL_SIGNAL_TEXT)
    result = score_signal(spec, stage1, REAL_EVIDENCE_ASSESSMENT, entity_type_matches=True, excluded=True)
    assert result.dimension("aim_fit").raw_value == 0.0
    assert result.dimension("aim_fit").points == 0.0
    print("PASS: excluded=True zeroes out the Aim Fit dimension regardless of other inputs")


def test_timing_freshness_buckets():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, REAL_SIGNAL_TEXT)
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)

    fresh = score_signal(spec, stage1, None, entity_type_matches=True, published_at=now - timedelta(days=1), now=now)
    stale = score_signal(spec, stage1, None, entity_type_matches=True, published_at=now - timedelta(days=120), now=now)
    unknown = score_signal(spec, stage1, None, entity_type_matches=True, published_at=None, now=now)

    assert fresh.dimension("timing_trigger_strength").raw_value == 1.0
    assert stale.dimension("timing_trigger_strength").raw_value == 0.1
    assert unknown.dimension("timing_trigger_strength").raw_value == 0.1
    print("PASS: timing dimension freshness bucketing (fresh=1.0, stale/unknown=0.1)")


def test_total_score_bounds_across_varied_inputs():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, "Warehouse Associate: lift boxes, operate forklift")
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    combos = [
        dict(entity_type_matches=False, geography_matches=False, excluded=True),
        dict(entity_type_matches=True, geography_matches=True, industry_matches=True),
        dict(entity_type_matches=True, published_at=now - timedelta(days=500)),
    ]
    for combo in combos:
        result = score_signal(spec, stage1, None, now=now, **combo)
        assert 0 <= result.total_score <= 100, f"out of bounds: {result.total_score} for {combo}"
    print("PASS: total_score stays within [0, 100] across varied inputs")


def test_custom_weights_are_respected():
    spec = load_collectiq_spec()
    stage1 = extract_stage1_evidence(spec, REAL_SIGNAL_TEXT)
    heavy_evidence_weights = ScoringWeights(
        aim_fit=10, evidence_strength=50, timing_trigger_strength=10, opportunity_relevance=15,
        evidence_confidence=10, source_quality=3, actionability=2,
    )
    result = score_signal(spec, stage1, REAL_EVIDENCE_ASSESSMENT, entity_type_matches=True, weights=heavy_evidence_weights)
    assert result.dimension("evidence_strength").weight == 50
    assert result.weights_used.evidence_strength == 50
    print("PASS: custom per-call ScoringWeights are actually used, not silently ignored")


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
