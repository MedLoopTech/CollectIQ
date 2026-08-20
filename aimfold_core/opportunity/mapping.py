"""Converts a PR7 ExplainableScore into the three confidence fields
AIMFOLD_MASTER_GOAL.md section 9 lists separately from total_score."""

from __future__ import annotations

from aimfold_core.scoring.schema import ExplainableScore

from .schema import ConfidenceFields


def opportunity_confidence_fields(score: ExplainableScore) -> ConfidenceFields:
    evidence_confidence = score.dimension("evidence_confidence").raw_value
    source_confidence = score.dimension("source_quality").raw_value
    # "confidence" is deliberately distinct from total_score: total_score
    # says how GOOD the opportunity looks, confidence says how much to
    # trust that assessment. A low-scoring opportunity can still be a
    # confident (correctly-scored-low) assessment.
    confidence = (evidence_confidence + source_confidence) / 2
    return ConfidenceFields(
        confidence=round(confidence, 4),
        evidence_confidence=round(evidence_confidence, 4),
        source_confidence=round(source_confidence, 4),
    )


__all__ = ["opportunity_confidence_fields"]
