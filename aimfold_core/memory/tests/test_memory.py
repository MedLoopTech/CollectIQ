"""Run with: python aimfold_core/memory/tests/test_memory.py"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.memory.aim_memory import compute_aim_memory
from aimfold_core.memory.entity_memory import build_entity_memory_row
from aimfold_core.memory.schema import FeedbackDecisionContext, MemoryType
from aimfold_core.research.schema import EntityContextSummary, ResearchResult

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120900_aim_memory_schema.sql"


def test_memory_type_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"memory_type\s+text[^()]*check\s*\([^()]*?in\s*\((.*?)\)", sql, re.S)
    assert match
    db_values = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    py_values = set(get_args(MemoryType))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: MemoryType matches the DB check constraint ({len(py_values)} values)")


def test_empty_contexts_yields_nothing():
    assert compute_aim_memory([]) == []
    print("PASS: compute_aim_memory([]) returns nothing rather than padded/fake entries")


# Real component_scores shape from PR7's live Gemini-scored run (91.8/100,
# Acme Freight Systems) and a plausible rejected counterpart, used as
# realistic fixtures rather than synthetic round numbers.
ACCEPTED_SCORES = [
    {"name": "aim_fit", "raw_value": 1.0}, {"name": "evidence_strength", "raw_value": 0.95},
    {"name": "timing_trigger_strength", "raw_value": 1.0}, {"name": "opportunity_relevance", "raw_value": 0.636},
    {"name": "evidence_confidence", "raw_value": 1.0}, {"name": "source_quality", "raw_value": 0.7},
    {"name": "actionability", "raw_value": 1.0},
]
REJECTED_SCORES_WEAK = [
    {"name": "aim_fit", "raw_value": 1.0}, {"name": "evidence_strength", "raw_value": 0.2},
    {"name": "evidence_confidence", "raw_value": 0.3},
]


def _ctx(feedback_type, rejection_reason=None, action=None, scores=None, entity_type="company", sources=None) -> FeedbackDecisionContext:
    return FeedbackDecisionContext(
        opportunity_id=uuid4(), feedback_type=feedback_type, rejection_reason=rejection_reason,
        predicted_recommended_action=action, component_scores=scores or [],
        primary_entity_type=entity_type, source_keys=sources or [],
    )


def test_dimension_averages_and_action_performance():
    contexts = [
        _ctx("accepted", action="contact", scores=ACCEPTED_SCORES, sources=["linkedin_jobs_apify"]),
        _ctx("accepted", action="contact", scores=ACCEPTED_SCORES, sources=["indeed_jobs_apify"]),
        _ctx("rejected", rejection_reason="weak_evidence", action="research", scores=REJECTED_SCORES_WEAK, sources=["linkedin_jobs_apify"]),
    ]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}

    assert "accepted_pattern" in by_type
    ap = by_type["accepted_pattern"]
    assert ap.sample_size == 2
    assert ap.payload["average_dimension_scores"]["evidence_strength"] == 0.95

    assert "rejected_pattern" in by_type
    rp = by_type["rejected_pattern"]
    assert rp.sample_size == 1
    assert rp.payload["rejection_reason_breakdown"]["weak_evidence"]["count"] == 1

    assert "successful_action" in by_type
    assert by_type["successful_action"].payload["accepted_counts_by_action"] == {"contact": 2}
    assert "failed_action" in by_type
    assert by_type["failed_action"].payload["rejected_counts_by_action"] == {"research": 1}
    print("PASS: dimension averages, rejection breakdown, and action performance all correct")


def test_source_effectiveness_acceptance_rate():
    contexts = [
        _ctx("accepted", action="contact", scores=ACCEPTED_SCORES, sources=["linkedin_jobs_apify"]),
        _ctx("accepted", action="contact", scores=ACCEPTED_SCORES, sources=["linkedin_jobs_apify"]),
        _ctx("rejected", rejection_reason="poor_timing", scores=REJECTED_SCORES_WEAK, sources=["linkedin_jobs_apify"]),
        _ctx("rejected", rejection_reason="poor_timing", scores=REJECTED_SCORES_WEAK, sources=["indeed_jobs_apify"]),
    ]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    se = by_type["source_effectiveness"].payload["by_source"]
    assert se["linkedin_jobs_apify"] == {"accepted": 2, "rejected": 1, "n": 3, "acceptance_rate": 0.6667}
    assert se["indeed_jobs_apify"] == {"accepted": 0, "rejected": 1, "n": 1, "acceptance_rate": 0.0}
    print("PASS: source_effectiveness computes correct per-source acceptance rates")


def test_learned_exclusion_fires_on_dominant_structural_reason():
    contexts = [_ctx("rejected", rejection_reason="wrong_geography") for _ in range(4)] + [
        _ctx("rejected", rejection_reason="poor_timing")
    ]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    assert "learned_exclusion" in by_type
    assert by_type["learned_exclusion"].payload["suggested_exclusion_reason"] == "wrong_geography"
    assert by_type["learned_exclusion"].payload["fraction_of_rejections"] == 0.8
    print("PASS: learned_exclusion fires when a structural reason dominates (4/5 wrong_geography)")


def test_learned_exclusion_does_not_fire_on_situational_reason():
    # poor_timing is situational, not structural — even if it dominates, no exclusion should be suggested
    contexts = [_ctx("rejected", rejection_reason="poor_timing") for _ in range(5)]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    assert "learned_exclusion" not in by_type
    print("PASS: learned_exclusion never fires for a situational (non-structural) rejection reason, even if dominant")


def test_learned_exclusion_does_not_fire_below_minimum_samples():
    contexts = [_ctx("rejected", rejection_reason="wrong_geography"), _ctx("rejected", rejection_reason="wrong_geography")]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    assert "learned_exclusion" not in by_type
    print("PASS: learned_exclusion requires a minimum sample size (2 rejections isn't enough)")


def test_held_feedback_excluded_from_accepted_and_rejected_patterns():
    contexts = [_ctx("held", scores=ACCEPTED_SCORES)]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    assert "accepted_pattern" not in by_type
    assert "rejected_pattern" not in by_type
    print("PASS: 'held' feedback contributes to neither accepted_pattern nor rejected_pattern")


def test_preferred_entity_attribute():
    contexts = [_ctx("accepted", entity_type="company"), _ctx("accepted", entity_type="company"), _ctx("accepted", entity_type="job")]
    entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in entries}
    assert by_type["preferred_entity_attribute"].payload["accepted_entity_type_counts"] == {"company": 2, "job": 1}
    print("PASS: preferred_entity_attribute counts accepted entity types correctly")


def test_build_entity_memory_row_from_research_result():
    result = ResearchResult(
        context=EntityContextSummary(
            key_facts=["chasing overdue invoices by hand"],
            inferences=["Manual AR processes are causing strain."],
            notable_changes=[], open_questions=["Company size unknown."],
            summary="Acme Freight Systems has manual AR processes.",
        ),
        researcher_model="gemini:gemini-flash-lite-latest",
        researcher_prompt_version="research-synthesizer-2026-08-19-v1",
    )
    row = build_entity_memory_row(result)
    assert row["memory_type"] == "research_synthesis"
    assert row["payload"]["summary"] == "Acme Freight Systems has manual AR processes."
    assert row["payload"]["researcher_model"] == "gemini:gemini-flash-lite-latest"
    print("PASS: build_entity_memory_row formats a ResearchResult into an insertable entity_memory row")


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
