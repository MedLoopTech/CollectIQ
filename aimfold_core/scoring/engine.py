"""Deterministic scoring aggregation over PR6's evidence output.

No LLM call happens here — by the time a signal reaches this engine,
Stage 1 (extractor.py) and optionally Stage 2 (evaluator.py) have already
done the interpretive work. Scoring is then a pure, explainable weighted
sum (AIMFOLD_MASTER_GOAL.md section 28: deterministic where deterministic
works — combining already-extracted numbers with configurable weights is
exactly that).

Storage-agnostic like aim_compiler and evidence, on purpose: this repo
has no wired-up persistence path yet (no service-role key used directly
by this code), so score_signal() takes plain inputs and returns a plain
ExplainableScore for the caller to persist however it decides to
(eventually: an opportunities row, once PR8 adds that table).

Deliberately NOT built in this PR: a `scoring_versions` table letting an
Aim reference a specific persisted, promotable weight-set. Section 22's
observe -> measure -> propose -> test -> promote loop is what a real
scoring_versions table needs to serve, and there's no learning/proposal
engine yet (that's PR15) to promote anything through it. Until then,
SCORING_ENGINE_VERSION is a plain constant, same as PROMPT_VERSION in
aim_compiler/evidence before any of this had somewhere to log to.
"""

from __future__ import annotations

from datetime import datetime, timezone

from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.evidence.schema import EvidenceAssessment, Stage1EvidenceResult

from .schema import DimensionScore, ExplainableScore, ScoringWeights, SCORING_ENGINE_VERSION, DEFAULT_SCORING_WEIGHTS


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_aim_fit(entity_type_matches: bool, geography_matches: bool | None, industry_matches: bool | None, excluded: bool) -> tuple[float, str]:
    if excluded:
        return 0.0, "Signal/entity matched one of the Aim's exclusions — Aim Fit forced to 0."
    checks = {"entity_type": entity_type_matches}
    if geography_matches is not None:
        checks["geography"] = geography_matches
    if industry_matches is not None:
        checks["industry"] = industry_matches
    value = sum(1.0 for v in checks.values() if v) / len(checks)
    parts = [f"{k}={'match' if v else 'no match'}" for k, v in checks.items()]
    unknown = [k for k in ("geography", "industry") if k not in checks]
    if unknown:
        parts.append(f"{'/'.join(unknown)} unknown (not scored)")
    return value, "; ".join(parts)


def _score_evidence_strength(evidence_assessment: EvidenceAssessment | None, stage1: Stage1EvidenceResult) -> tuple[float, str]:
    if evidence_assessment is not None:
        return evidence_assessment.evidence_strength, "From Stage-2 LLM evidence assessment (verified, non-fabricated observed_facts)."
    value = stage1.score / stage1.max_score if stage1.max_score else 0.0
    return value, "No Stage-2 evaluation ran — using Stage-1 keyword-match score as a weaker proxy."


def _score_timing(evidence_assessment: EvidenceAssessment | None, published_at: datetime | None, now: datetime) -> tuple[float, str]:
    if published_at is not None:
        age_days = max(0.0, (now - published_at).total_seconds() / 86400)
        if age_days <= 7:
            freshness = 1.0
        elif age_days <= 30:
            freshness = 0.6
        elif age_days <= 90:
            freshness = 0.3
        else:
            freshness = 0.1
        freshness_note = f"published {age_days:.0f}d ago"
    else:
        freshness = 0.1
        freshness_note = "published_at unknown"

    if evidence_assessment is not None:
        has_why_now = evidence_assessment.why_now is not None
        value = 0.7 * (1.0 if has_why_now else 0.0) + 0.3 * freshness
        why_now_note = f'why_now="{evidence_assessment.why_now}"' if has_why_now else "no explicit timing signal in evidence"
        return value, f"{why_now_note}; {freshness_note}."
    return freshness, f"No Stage-2 evaluation ran — using recency only ({freshness_note})."


def _score_opportunity_relevance(evidence_assessment: EvidenceAssessment | None, compiled_spec: CompiledAimSpec, stage1: Stage1EvidenceResult) -> tuple[float, str]:
    if evidence_assessment is not None:
        total = len(compiled_spec.positive_criteria)
        matched = len(evidence_assessment.matched_positive_criteria)
        value = matched / total if total else 0.0
        return value, f"{matched}/{total} of the Aim's positive_criteria matched (verified against the Aim's real list)."
    total = len(compiled_spec.scoring_weights)
    matched = len(stage1.matches)
    value = matched / total if total else 0.0
    return value, f"No Stage-2 evaluation ran — {matched}/{total} Stage-1 rule categories matched, used as a proxy."


def _score_evidence_confidence(evidence_assessment: EvidenceAssessment | None) -> tuple[float, str]:
    if evidence_assessment is None:
        return 0.3, "No Stage-2 evaluation ran — confidence capped low; Stage-1 keyword matches alone aren't independently verified."
    n = len(evidence_assessment.observed_facts)
    bonus = min(n, 4) / 4 * 0.4
    value = _clamp01(0.6 + bonus)
    return value, f"Stage-2 evaluation ran with {n} verified observed_fact(s) (each confirmed to be a literal quote from the source text)."


def _score_source_quality(source_quality: float | None) -> tuple[float, str]:
    if source_quality is None:
        return 0.5, "No measured source_quality yet for this source — neutral default (real Source Performance Tracking is future work, not this PR)."
    return _clamp01(source_quality), f"signals.source_quality = {source_quality}"


def _score_actionability(compiled_spec: CompiledAimSpec, evidence_assessment: EvidenceAssessment | None) -> tuple[float, str]:
    if not compiled_spec.likely_actions:
        return 0.0, "Aim defines no likely_actions."
    if evidence_assessment is not None and evidence_assessment.suggested_next_step:
        return 1.0, f"Aim defines likely_actions and evidence suggests a concrete next step: {evidence_assessment.suggested_next_step!r}."
    return 0.5, "Aim defines likely_actions, but no concrete next step was suggested by the evidence evaluation."


def score_signal(
    compiled_spec: CompiledAimSpec,
    stage1_result: Stage1EvidenceResult,
    evidence_assessment: EvidenceAssessment | None,
    *,
    entity_type_matches: bool,
    geography_matches: bool | None = None,
    industry_matches: bool | None = None,
    excluded: bool = False,
    published_at: datetime | None = None,
    source_quality: float | None = None,
    weights: ScoringWeights = DEFAULT_SCORING_WEIGHTS,
    now: datetime | None = None,
) -> ExplainableScore:
    now = now or datetime.now(timezone.utc)

    aim_fit_v, aim_fit_r = _score_aim_fit(entity_type_matches, geography_matches, industry_matches, excluded)
    evidence_strength_v, evidence_strength_r = _score_evidence_strength(evidence_assessment, stage1_result)
    timing_v, timing_r = _score_timing(evidence_assessment, published_at, now)
    relevance_v, relevance_r = _score_opportunity_relevance(evidence_assessment, compiled_spec, stage1_result)
    confidence_v, confidence_r = _score_evidence_confidence(evidence_assessment)
    source_quality_v, source_quality_r = _score_source_quality(source_quality)
    actionability_v, actionability_r = _score_actionability(compiled_spec, evidence_assessment)

    raw = {
        "aim_fit": (aim_fit_v, aim_fit_r),
        "evidence_strength": (evidence_strength_v, evidence_strength_r),
        "timing_trigger_strength": (timing_v, timing_r),
        "opportunity_relevance": (relevance_v, relevance_r),
        "evidence_confidence": (confidence_v, confidence_r),
        "source_quality": (source_quality_v, source_quality_r),
        "actionability": (actionability_v, actionability_r),
    }

    dimensions = [
        DimensionScore(
            name=name,
            weight=getattr(weights, name),
            raw_value=value,
            points=round(value * getattr(weights, name), 4),
            rationale=rationale,
        )
        for name, (value, rationale) in raw.items()
    ]
    total_score = round(sum(d.points for d in dimensions), 4)

    return ExplainableScore(
        dimensions=dimensions,
        total_score=total_score,
        scoring_version=SCORING_ENGINE_VERSION,
        weights_used=weights,
    )


__all__ = ["score_signal", "SCORING_ENGINE_VERSION"]
