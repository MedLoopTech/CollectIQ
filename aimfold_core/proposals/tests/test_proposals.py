"""Run with: python aimfold_core/proposals/tests/test_proposals.py"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import get_args
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.llm_client import StubLLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evaluation.dataset import COLLECTIQ_EVAL_V1
from aimfold_core.evaluation.runner import run_evaluation
from aimfold_core.memory.aim_memory import compute_aim_memory
from aimfold_core.memory.schema import AimMemoryEntry, FeedbackDecisionContext
from aimfold_core.proposals.generator import propose_exclusion, propose_scoring_weight_adjustment
from aimfold_core.proposals.schema import ProposalStatus, ProposalType
from aimfold_core.proposals.testing import test_exclusion_proposal as run_exclusion_proposal_test
from aimfold_core.proposals.testing import test_scoring_weight_proposal as run_scoring_weight_proposal_test
from aimfold_core.scoring.schema import DEFAULT_SCORING_WEIGHTS

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"
PROPOSALS_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819121000_learning_proposals_schema.sql"
AIM_ID = uuid4()
AIM_VERSION_ID = uuid4()


def load_collectiq_spec() -> CompiledAimSpec:
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match
    return CompiledAimSpec.model_validate(json.loads(match.group(1)))


def _extract_check_values(sql: str, column: str) -> set[str]:
    pattern = re.compile(rf"{column}\s+text[^()]*check\s*\([^()]*?in\s*\((.*?)\)", re.S)
    match = pattern.search(sql)
    assert match, f"no in (...) clause for {column!r}"
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


def test_proposal_type_and_status_match_migration():
    sql = PROPOSALS_MIGRATION.read_text(encoding="utf-8")
    assert _extract_check_values(sql, "proposal_type") == set(get_args(ProposalType))
    assert _extract_check_values(sql, "status") == set(get_args(ProposalStatus))
    print("PASS: ProposalType and ProposalStatus match the migration's check constraints")


def test_propose_exclusion_from_learned_exclusion_entry():
    spec = load_collectiq_spec()
    entry = AimMemoryEntry(
        memory_type="learned_exclusion",
        payload={"suggested_exclusion_reason": "wrong_industry", "fraction_of_rejections": 0.8},
        sample_size=5,
    )
    proposal = propose_exclusion(entry, spec, AIM_ID, AIM_VERSION_ID)
    assert proposal is not None
    assert proposal.proposal_type == "add_exclusion"
    assert "wrong_industry" in proposal.proposed_behavior
    assert proposal.sample_size == 5
    assert "no exclusion-matching logic exists yet" in proposal.expected_impact
    assert proposal.proposed_compiled_spec.exclusions == spec.exclusions + [proposal.proposed_compiled_spec.exclusions[-1]] or len(proposal.proposed_compiled_spec.exclusions) == len(spec.exclusions) + 1
    print("PASS: propose_exclusion builds a proposal from a learned_exclusion entry, with an honest expected_impact caveat")


def test_propose_exclusion_ignores_wrong_memory_type():
    spec = load_collectiq_spec()
    entry = AimMemoryEntry(memory_type="successful_action", payload={}, sample_size=5)
    assert propose_exclusion(entry, spec, AIM_ID, AIM_VERSION_ID) is None
    print("PASS: propose_exclusion returns None for a non-learned_exclusion entry")


def test_propose_exclusion_skips_already_applied():
    spec = load_collectiq_spec()
    entry = AimMemoryEntry(
        memory_type="learned_exclusion",
        payload={"suggested_exclusion_reason": "wrong_industry", "fraction_of_rejections": 0.8},
        sample_size=5,
    )
    first = propose_exclusion(entry, spec, AIM_ID, AIM_VERSION_ID)
    already_applied_spec = spec.model_copy(update={"exclusions": [*spec.exclusions, first.proposed_compiled_spec.exclusions[-1]]})
    assert propose_exclusion(entry, already_applied_spec, AIM_ID, AIM_VERSION_ID) is None
    print("PASS: propose_exclusion returns None once the same exclusion is already in compiled_spec.exclusions")


def test_propose_scoring_weight_adjustment_fires_on_clear_discriminator():
    accepted = AimMemoryEntry(
        memory_type="accepted_pattern",
        payload={"average_dimension_scores": {"evidence_strength": 0.9, "source_quality": 0.5}},
        sample_size=6,
    )
    rejected = AimMemoryEntry(
        memory_type="rejected_pattern",
        payload={"average_dimension_scores": {"evidence_strength": 0.2, "source_quality": 0.48}},
        sample_size=6,
    )
    proposal = propose_scoring_weight_adjustment(accepted, rejected, DEFAULT_SCORING_WEIGHTS, AIM_ID)
    assert proposal is not None
    assert proposal.proposal_type == "adjust_scoring_weight"
    assert proposal.proposed_scoring_weights.evidence_strength == DEFAULT_SCORING_WEIGHTS.evidence_strength + 2
    assert proposal.proposed_scoring_weights.source_quality == DEFAULT_SCORING_WEIGHTS.source_quality - 2
    total = sum(getattr(proposal.proposed_scoring_weights, d) for d in ("aim_fit", "evidence_strength", "timing_trigger_strength", "opportunity_relevance", "evidence_confidence", "source_quality", "actionability"))
    assert abs(total - 100) < 0.01
    print(f"PASS: propose_scoring_weight_adjustment nudges evidence_strength up and source_quality down, weights still sum to {total}")


def test_propose_scoring_weight_adjustment_requires_minimum_samples():
    accepted = AimMemoryEntry(memory_type="accepted_pattern", payload={"average_dimension_scores": {"evidence_strength": 0.9, "source_quality": 0.5}}, sample_size=2)
    rejected = AimMemoryEntry(memory_type="rejected_pattern", payload={"average_dimension_scores": {"evidence_strength": 0.2, "source_quality": 0.48}}, sample_size=2)
    assert propose_scoring_weight_adjustment(accepted, rejected, DEFAULT_SCORING_WEIGHTS, AIM_ID) is None
    print("PASS: propose_scoring_weight_adjustment refuses to propose from too little data (2 samples)")


def test_propose_scoring_weight_adjustment_no_op_when_nothing_discriminates():
    accepted = AimMemoryEntry(memory_type="accepted_pattern", payload={"average_dimension_scores": {"evidence_strength": 0.5, "source_quality": 0.5}}, sample_size=6)
    rejected = AimMemoryEntry(memory_type="rejected_pattern", payload={"average_dimension_scores": {"evidence_strength": 0.5, "source_quality": 0.5}}, sample_size=6)
    assert propose_scoring_weight_adjustment(accepted, rejected, DEFAULT_SCORING_WEIGHTS, AIM_ID) is None
    print("PASS: propose_scoring_weight_adjustment proposes nothing when accepted and rejected look identical")


# ---------------------------------------------------------------------------
# Integrated end-to-end: PR12 (Aim Memory) -> PR15 (proposal) -> PR15 (test),
# built from a real PR13 evaluation run rather than hand-crafted fixtures.
# ---------------------------------------------------------------------------

_STAGE2_RESPONSES = {
    "our AR team is drowning in manual work": json.dumps({
        "observed_facts": ["our AR team is drowning in manual work", "Recently rolled out NetSuite"],
        "inferences": ["Manual AR processes are causing operational strain."],
        "relevance_explanation": "Explicit AR hiring with manual workflow and ERP context.",
        "why_now": "Recently rolled out NetSuite",
        "matched_positive_criteria": ["AR hiring", "ERP/accounting system"],
        "evidence_strength": 0.95, "suggested_next_step": "Reach out about the AR Intelligence Audit.",
    }),
    "review aging reports weekly": json.dumps({
        "observed_facts": ["review aging reports weekly", "high volume of accounts"],
        "inferences": ["Manual tracking despite decent volume."],
        "relevance_explanation": "Collections role with aging review.",
        "why_now": None, "matched_positive_criteria": ["collections/credit control", "ageing"],
        "evidence_strength": 0.6, "suggested_next_step": None,
    }),
    "immersive augmented reality experiences": json.dumps({
        "observed_facts": ["Build immersive augmented reality experiences"],
        "inferences": ["Unrelated AR/VR software role."],
        "relevance_explanation": "The 'AR' match is augmented reality, not accounts receivable.",
        "why_now": None, "matched_positive_criteria": [], "evidence_strength": 0.05, "suggested_next_step": None,
    }),
    "own the full AR cycle": json.dumps({
        "observed_facts": ["own the full AR cycle", "High volume portfolio"],
        "inferences": ["Comprehensive, still-manual AR role."],
        "relevance_explanation": "Matches nearly every positive criterion directly.",
        "why_now": None, "matched_positive_criteria": ["AR hiring", "collections/credit control", "high volume"],
        "evidence_strength": 0.95, "suggested_next_step": "Reach out.",
    }),
}

# What a human reviewing each example in the PR13 dataset would plausibly
# have decided, and why — used to build FeedbackDecisionContext rows so
# compute_aim_memory() has something real to learn from. 'irrelevant' and
# 'false_positive' both get the same *structural* reason on purpose, so
# learned_exclusion has a real majority pattern to find.
_DECISIONS = {
    "excellent-ar-analyst-acme": ("accepted", None),
    "acceptable-credit-controller": ("accepted", None),
    "excellent-ar-manager-full-cycle": ("accepted", None),
    "false-positive-ar-vr-engineer": ("rejected", "wrong_industry"),
    "irrelevant-warehouse": ("rejected", "wrong_industry"),
    "ambiguous-finance-ops-coordinator": ("rejected", "low_value"),
}


def _build_contexts(baseline_report):
    contexts = []
    for r in baseline_report.results:
        feedback_type, reason = _DECISIONS[r.example_id]
        contexts.append(FeedbackDecisionContext(
            opportunity_id=uuid4(), feedback_type=feedback_type, rejection_reason=reason,
            predicted_recommended_action=r.recommended_action,
            component_scores=_dims_from_score(r),
            primary_entity_type="company",
        ))
    return contexts


def _dims_from_score(result):
    # EvalResult doesn't carry component_scores directly (that's on
    # ExplainableScore, one layer up) — for this test we only need
    # evidence_strength/source_quality, which we can approximate from
    # what's already on the cached stage1/evidence objects closely enough
    # to exercise the real propose_scoring_weight_adjustment path.
    if result.evidence_assessment is not None:
        return [
            {"name": "evidence_strength", "raw_value": result.evidence_assessment.evidence_strength},
            {"name": "source_quality", "raw_value": 0.5},
        ]
    return [{"name": "evidence_strength", "raw_value": result.stage1_score / 100}, {"name": "source_quality", "raw_value": 0.5}]


def test_end_to_end_memory_to_tested_proposal():
    spec = load_collectiq_spec()
    client = StubLLMClient(_STAGE2_RESPONSES)
    baseline = run_evaluation(COLLECTIQ_EVAL_V1, spec, client, dataset_name="proposals-e2e-baseline")

    contexts = _build_contexts(baseline)
    memory_entries = compute_aim_memory(contexts)
    by_type = {e.memory_type: e for e in memory_entries}

    assert "learned_exclusion" in by_type, "expected wrong_industry to dominate rejections (2/3) and be structural"
    exclusion_proposal = propose_exclusion(by_type["learned_exclusion"], spec, AIM_ID, AIM_VERSION_ID)
    assert exclusion_proposal is not None
    print(f"PASS: Aim Memory -> propose_exclusion — {exclusion_proposal.proposed_behavior}")

    tested_exclusion = run_exclusion_proposal_test(exclusion_proposal, COLLECTIQ_EVAL_V1, baseline, None)
    assert tested_exclusion.status == "tested"
    assert tested_exclusion.evaluation_results is not None
    print(f"PASS: exclusion proposal tested (Stage-1-only) — possible_regressions={tested_exclusion.possible_regressions}")

    assert "accepted_pattern" in by_type and "rejected_pattern" in by_type
    # min_sample_size=2 here only because this dataset has just 3 accepted/3
    # rejected examples total — MIN_SAMPLE_SIZE_FOR_SCORING_PROPOSAL's real
    # default (5) is deliberately higher for actual use; lowering it here is
    # a test-only override to exercise this path with so little data, not a
    # statement that 2 samples is normally enough to trust a weight change.
    weight_proposal = propose_scoring_weight_adjustment(
        by_type["accepted_pattern"], by_type["rejected_pattern"], DEFAULT_SCORING_WEIGHTS, AIM_ID, min_sample_size=2
    )
    assert weight_proposal is not None, "expected evidence_strength to discriminate accepted from rejected in this dataset"

    # run_scoring_weight_proposal_test's signature has no llm_client
    # parameter at all — that absence, not a mock, is what proves no
    # Stage-2 call is even possible here.
    tested_weight = run_scoring_weight_proposal_test(weight_proposal, COLLECTIQ_EVAL_V1, baseline, spec)
    assert tested_weight.status == "tested"
    assert tested_weight.evaluation_results is not None
    print(f"PASS: scoring-weight proposal tested with ZERO new LLM calls — possible_regressions={tested_weight.possible_regressions}")


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
