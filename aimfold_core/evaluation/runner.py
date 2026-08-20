"""Runs the real pipeline (extract_stage1_evidence -> evaluate_evidence
-> score_signal -> recommend_action) over a labeled dataset and computes
the metrics AIMFOLD_MASTER_GOAL.md section 29 names. Not a simulation —
these are the exact same functions PR6/PR7/PR9 already ship, called the
same way a production pipeline would call them.

`llm_client=None` runs Stage 1 only (free, deterministic, fast — good
for a pre-commit sanity check). Passing a real LLMClient runs the full
pipeline and unlocks calibration_accuracy / evidence_grounding_accuracy
/ action_recommendation_quality, which need Stage 2's output.
"""

from __future__ import annotations

from aimfold_core.action.recommender import recommend_action
from aimfold_core.aim_compiler.llm_client import LLMClient
from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evidence.evaluator import evaluate_evidence
from aimfold_core.evidence.extractor import extract_stage1_evidence
from aimfold_core.opportunity.mapping import opportunity_confidence_fields
from aimfold_core.scoring.engine import score_signal
from aimfold_core.scoring.schema import SCORING_ENGINE_VERSION

from .schema import EvalExample, EvalReport, EvalResult

# Ordinal "true quality" rank for ranking_quality's pairwise concordance
# check. false_positive and irrelevant_signal share rank 0 on purpose —
# both are genuinely low-value; a false_positive existing at all is
# exactly the case where Stage 1's score would disagree, which is what
# this dataset category exists to catch.
_CATEGORY_RANK = {"excellent": 3, "acceptable": 2, "ambiguous": 1, "false_positive": 0, "irrelevant_signal": 0}
_POSITIVE_CATEGORIES = {"excellent", "acceptable"}


def _evaluate_one(example: EvalExample, compiled_spec: CompiledAimSpec, llm_client: LLMClient | None) -> EvalResult:
    stage1 = extract_stage1_evidence(compiled_spec, example.signal_text)

    evidence_assessment = None
    stage2_ran = False
    if llm_client is not None and stage1.qualifies:
        evidence_assessment, _model = evaluate_evidence(example.signal_text, compiled_spec, stage1, llm_client)
        stage2_ran = True

    score = score_signal(compiled_spec, stage1, evidence_assessment, entity_type_matches=True)
    confidence_fields = opportunity_confidence_fields(score)
    action_rec = recommend_action(compiled_spec, "customer_discovery", score.total_score, confidence_fields.confidence)

    matched = evidence_assessment.matched_positive_criteria if evidence_assessment else []

    passed_calibration = None
    if stage2_ran:
        lo, hi = example.expected_score_range
        passed_calibration = lo <= score.total_score <= hi

    # An empty expected_matched_criteria is meaningful, not "nothing to
    # check" — it means this example (e.g. a false positive) should find
    # NO supporting criteria. Recall-check (expected subset of found) when
    # something's expected; precision-check (found is empty) when not.
    passed_grounding = None
    if stage2_ran:
        expected = set(example.expected_matched_criteria)
        found = set(matched)
        passed_grounding = expected.issubset(found) if expected else (len(found) == 0)

    passed_action = None
    if example.expected_action is not None:
        passed_action = action_rec.action == example.expected_action

    return EvalResult(
        example_id=example.id,
        expected_category=example.expected_category,
        stage1_score=stage1.score,
        stage1_qualifies=stage1.qualifies,
        total_score=score.total_score,
        confidence=confidence_fields.confidence,
        recommended_action=action_rec.action,
        matched_positive_criteria=matched,
        stage2_ran=stage2_ran,
        passed_qualification_check=(stage1.qualifies == example.expected_qualifies),
        passed_calibration_check=passed_calibration,
        passed_grounding_check=passed_grounding,
        passed_action_check=passed_action,
    )


def _ranking_quality(examples: list[EvalExample], results: list[EvalResult]) -> float:
    scores_and_ranks = [
        (r.total_score, _CATEGORY_RANK[e.expected_category])
        for e, r in zip(examples, results)
    ]
    concordant = 0
    total_pairs = 0
    for i in range(len(scores_and_ranks)):
        for j in range(i + 1, len(scores_and_ranks)):
            score_i, rank_i = scores_and_ranks[i]
            score_j, rank_j = scores_and_ranks[j]
            if rank_i == rank_j:
                continue
            total_pairs += 1
            higher_rank_scores_higher = (rank_i > rank_j) == (score_i > score_j)
            if higher_rank_scores_higher:
                concordant += 1
    return round(concordant / total_pairs, 4) if total_pairs else 1.0


def run_evaluation(
    examples: list[EvalExample],
    compiled_spec: CompiledAimSpec,
    llm_client: LLMClient | None,
    *,
    dataset_name: str = "unnamed",
) -> EvalReport:
    results = [_evaluate_one(ex, compiled_spec, llm_client) for ex in examples]
    stage2_ran = any(r.stage2_ran for r in results)

    positives = [(ex, r) for ex, r in zip(examples, results) if ex.expected_category in _POSITIVE_CATEGORIES]
    negatives = [(ex, r) for ex, r in zip(examples, results) if ex.expected_category not in _POSITIVE_CATEGORIES]

    qualifying_positives = sum(1 for _, r in positives if r.stage1_qualifies)
    qualifying_negatives = sum(1 for _, r in negatives if r.stage1_qualifies)
    total_qualifying = qualifying_positives + qualifying_negatives

    # Precision undefined with zero predictions — 1.0 (vacuously no false
    # accepts) is the conventional default rather than dividing by zero.
    precision = round(qualifying_positives / total_qualifying, 4) if total_qualifying else 1.0
    false_positive_rate = round(qualifying_negatives / len(negatives), 4) if negatives else 0.0
    accepted_opportunity_rate = round(qualifying_positives / len(positives), 4) if positives else 0.0

    ranking_quality = _ranking_quality(examples, results)

    calibration_results = [r.passed_calibration_check for r in results if r.passed_calibration_check is not None]
    calibration_accuracy = round(sum(calibration_results) / len(calibration_results), 4) if calibration_results else None

    grounding_results = [r.passed_grounding_check for r in results if r.passed_grounding_check is not None]
    evidence_grounding_accuracy = round(sum(grounding_results) / len(grounding_results), 4) if grounding_results else None

    action_results = [r.passed_action_check for r in results if r.passed_action_check is not None]
    action_recommendation_quality = round(sum(action_results) / len(action_results), 4) if action_results else None

    scores_by_category: dict[str, list[float]] = {}
    for ex, r in zip(examples, results):
        scores_by_category.setdefault(ex.expected_category, []).append(r.total_score)

    return EvalReport(
        dataset_name=dataset_name,
        n_examples=len(examples),
        stage2_ran=stage2_ran,
        scoring_version=SCORING_ENGINE_VERSION,
        aim_objective=compiled_spec.objective,
        precision=precision,
        false_positive_rate=false_positive_rate,
        accepted_opportunity_rate=accepted_opportunity_rate,
        ranking_quality=ranking_quality,
        calibration_accuracy=calibration_accuracy,
        evidence_grounding_accuracy=evidence_grounding_accuracy,
        action_recommendation_quality=action_recommendation_quality,
        scores_by_category=scores_by_category,
        results=results,
    )


__all__ = ["run_evaluation"]
