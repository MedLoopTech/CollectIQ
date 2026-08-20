"""The 'Test' step of Observe -> Measure -> Propose -> Test -> Promote
(AIMFOLD_MASTER_GOAL.md section 22). Populates a LearningProposal's
evaluation_results/possible_regressions by actually running it through
aimfold_core.evaluation (PR13) — "every significant change to prompts,
models, scoring or signal logic should be evaluated against this
benchmark" (section 29), applied to a proposal specifically.
"""

from __future__ import annotations

from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evaluation.regression import compare_eval_reports
from aimfold_core.evaluation.runner import rescore_with_weights, run_evaluation
from aimfold_core.evaluation.schema import EvalExample, EvalReport

from .schema import LearningProposal


def test_scoring_weight_proposal(
    proposal: LearningProposal,
    examples: list[EvalExample],
    baseline_report: EvalReport,
    compiled_spec: CompiledAimSpec,
    *,
    tolerance: float = 0.05,
) -> LearningProposal:
    """No LLM call — re-scores baseline_report's already-gathered
    evidence with the proposal's candidate weights (rescore_with_weights,
    PR13) rather than re-running Stage 2. Matches AIMFOLD_MASTER_GOAL.md
    section 49's 'Persist before expensive next steps' rule: testing a
    scoring-only change must never repeat the reasoning that already ran
    once for baseline_report."""

    if proposal.proposal_type != "adjust_scoring_weight" or proposal.proposed_scoring_weights is None:
        raise ValueError("test_scoring_weight_proposal requires a proposal_type='adjust_scoring_weight' proposal")

    candidate_report = rescore_with_weights(
        examples, baseline_report.results, compiled_spec, proposal.proposed_scoring_weights,
        dataset_name=f"{baseline_report.dataset_name}-candidate-weights",
    )
    regression = compare_eval_reports(baseline_report, candidate_report, tolerance=tolerance)

    return proposal.model_copy(update={
        "evaluation_results": {
            "baseline": baseline_report.model_dump(exclude={"results"}),
            "candidate": candidate_report.model_dump(exclude={"results"}),
        },
        "possible_regressions": [f.metric for f in regression.findings if f.is_regression],
        "status": "tested",
    })


def test_exclusion_proposal(
    proposal: LearningProposal,
    examples: list[EvalExample],
    baseline_report: EvalReport,
    llm_client,
    *,
    tolerance: float = 0.05,
) -> LearningProposal:
    """Exclusion proposals change compiled_spec itself (not just
    weights), and exclusion-matching isn't wired into extract_stage1_evidence
    yet (see generator.py's docstring) — so there's no cheaper way to
    test one than a full run_evaluation() against the candidate spec.
    Pass llm_client=None to test only the free, deterministic parts
    (Stage-1 qualification labels) without repeating Stage-2 calls."""

    if proposal.proposal_type != "add_exclusion" or proposal.proposed_compiled_spec is None:
        raise ValueError("test_exclusion_proposal requires a proposal_type='add_exclusion' proposal")

    candidate_report = run_evaluation(
        examples, proposal.proposed_compiled_spec, llm_client,
        dataset_name=f"{baseline_report.dataset_name}-candidate-exclusion",
    )
    regression = compare_eval_reports(baseline_report, candidate_report, tolerance=tolerance)

    return proposal.model_copy(update={
        "evaluation_results": {
            "baseline": baseline_report.model_dump(exclude={"results"}),
            "candidate": candidate_report.model_dump(exclude={"results"}),
        },
        "possible_regressions": [f.metric for f in regression.findings if f.is_regression],
        "status": "tested",
    })


__all__ = ["test_scoring_weight_proposal", "test_exclusion_proposal"]
