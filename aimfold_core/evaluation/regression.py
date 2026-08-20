"""AIMFOLD_MASTER_GOAL.md section 30 (Regression Protection): "An
improvement cannot be judged from one metric alone... Historical
decisions must remain reproducible through version metadata."

compare_eval_reports() is what "every significant change to prompts,
models, scoring or signal logic should be evaluated against this
benchmark" (section 29) means in practice: run the dataset before and
after the change, compare.
"""

from __future__ import annotations

from .schema import EvalReport, RegressionFinding, RegressionReport

# metric name -> "higher is better"? (false_positive_rate is the one
# metric where a DECREASE is the improvement, everything else increases)
_HIGHER_IS_BETTER = {
    "precision": True,
    "false_positive_rate": False,
    "accepted_opportunity_rate": True,
    "ranking_quality": True,
    "calibration_accuracy": True,
    "evidence_grounding_accuracy": True,
    "action_recommendation_quality": True,
}


def _compare_metric(name: str, baseline: float | None, candidate: float | None, tolerance: float) -> RegressionFinding | None:
    if baseline is None or candidate is None:
        return None  # can't compare a metric that wasn't computed in one of the two runs (e.g. Stage 2 didn't run)
    delta = candidate - baseline
    higher_is_better = _HIGHER_IS_BETTER[name]
    worsened = -delta if higher_is_better else delta
    is_regression = worsened > tolerance
    return RegressionFinding(
        metric=name, baseline_value=baseline, candidate_value=candidate, delta=round(delta, 4),
        is_regression=is_regression,
        note=f"{'regressed' if is_regression else 'stable/improved'} by {abs(round(worsened, 4))} (tolerance={tolerance})",
    )


def compare_eval_reports(baseline: EvalReport, candidate: EvalReport, *, tolerance: float = 0.05) -> RegressionReport:
    """Compares top-level metrics plus a per-category breakdown (section
    30: "Check regressions across... high-value examples, edge cases" —
    here, category is the available breakdown axis; broader breakdowns
    by Aim type/tenant/geography need the second/third validation Aim
    from PR16/17 to have anything to compare)."""

    findings: list[RegressionFinding] = []

    for metric in _HIGHER_IS_BETTER:
        finding = _compare_metric(metric, getattr(baseline, metric), getattr(candidate, metric), tolerance)
        if finding:
            findings.append(finding)

    all_categories = set(baseline.scores_by_category) | set(candidate.scores_by_category)
    for category in sorted(all_categories):
        base_scores = baseline.scores_by_category.get(category)
        cand_scores = candidate.scores_by_category.get(category)
        if not base_scores or not cand_scores:
            continue
        base_avg = sum(base_scores) / len(base_scores)
        cand_avg = sum(cand_scores) / len(cand_scores)
        # Category average total_score isn't itself a 0-1 metric, so express
        # the regression check as a fractional drop rather than reusing
        # the flat `tolerance` (which is calibrated for 0-1 metrics).
        relative_drop = (base_avg - cand_avg) / base_avg if base_avg else 0.0
        is_regression = relative_drop > tolerance
        findings.append(RegressionFinding(
            metric=f"avg_total_score[{category}]", baseline_value=round(base_avg, 4), candidate_value=round(cand_avg, 4),
            delta=round(cand_avg - base_avg, 4), is_regression=is_regression,
            note=f"{'regressed' if is_regression else 'stable/improved'} (relative drop {round(relative_drop, 4)}, tolerance={tolerance})",
        ))

    return RegressionReport(has_regression=any(f.is_regression for f in findings), findings=findings)


__all__ = ["compare_eval_reports"]
