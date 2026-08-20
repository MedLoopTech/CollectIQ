"""Deterministic Aim Memory aggregation — no LLM call, same "deterministic
where deterministic works" reasoning as scoring/opportunity/action.
Pure counting and averaging over accumulated feedback (PR11).

Honesty over completeness: every function returns nothing for a
memory_type it can't actually support from the given data (e.g. no
source_keys anywhere -> no source_effectiveness entry) rather than
padding a payload with zeros or guesses.
"""

from __future__ import annotations

from collections import Counter

from .schema import AimMemoryEntry, FeedbackDecisionContext

# Structural (not situational) rejection reasons — these describe the
# entity/opportunity itself being the wrong shape for the Aim, the kind
# of thing worth learning as a standing exclusion. poor_timing,
# low_value, duplicate, source_unreliable, etc. describe THIS instance,
# not a durable exclusion rule, so they're deliberately not here.
STRUCTURAL_REJECTION_REASONS = frozenset({
    "wrong_entity_type", "wrong_industry", "wrong_geography",
    "too_small", "too_large", "not_eligible", "wrong_role", "wrong_seniority",
})

LEARNED_EXCLUSION_MIN_SAMPLES = 3
LEARNED_EXCLUSION_MIN_FRACTION = 0.5


def _average_dimensions(group: list[FeedbackDecisionContext]) -> dict[str, float]:
    values_by_dim: dict[str, list[float]] = {}
    for ctx in group:
        for dim in ctx.component_scores:
            name = dim.get("name")
            raw_value = dim.get("raw_value")
            if name and raw_value is not None:
                values_by_dim.setdefault(name, []).append(raw_value)
    return {name: round(sum(vals) / len(vals), 4) for name, vals in values_by_dim.items()}


def _rejection_reason_breakdown(rejected: list[FeedbackDecisionContext]) -> dict[str, dict]:
    reasons = [c.rejection_reason for c in rejected if c.rejection_reason]
    if not reasons:
        return {}
    counts = Counter(reasons)
    total = len(reasons)
    return {reason: {"count": n, "fraction": round(n / total, 4)} for reason, n in counts.most_common()}


def _derive_learned_exclusion(rejected: list[FeedbackDecisionContext]) -> AimMemoryEntry | None:
    reasons = [c.rejection_reason for c in rejected if c.rejection_reason]
    if len(reasons) < LEARNED_EXCLUSION_MIN_SAMPLES:
        return None
    counts = Counter(reasons)
    top_reason, top_count = counts.most_common(1)[0]
    fraction = top_count / len(reasons)
    if top_reason in STRUCTURAL_REJECTION_REASONS and fraction > LEARNED_EXCLUSION_MIN_FRACTION:
        return AimMemoryEntry(
            memory_type="learned_exclusion",
            payload={
                "suggested_exclusion_reason": top_reason,
                "fraction_of_rejections": round(fraction, 4),
                "note": "Candidate for compiled_spec.exclusions — not applied automatically.",
            },
            sample_size=len(reasons),
        )
    return None


def _action_performance(accepted: list[FeedbackDecisionContext], rejected: list[FeedbackDecisionContext]) -> list[AimMemoryEntry]:
    entries = []
    accepted_actions = Counter(c.predicted_recommended_action for c in accepted if c.predicted_recommended_action)
    rejected_actions = Counter(c.predicted_recommended_action for c in rejected if c.predicted_recommended_action)
    if accepted_actions:
        entries.append(AimMemoryEntry(
            memory_type="successful_action",
            payload={"accepted_counts_by_action": dict(accepted_actions)},
            sample_size=sum(accepted_actions.values()),
        ))
    if rejected_actions:
        entries.append(AimMemoryEntry(
            memory_type="failed_action",
            payload={"rejected_counts_by_action": dict(rejected_actions)},
            sample_size=sum(rejected_actions.values()),
        ))
    return entries


def _preferred_entity_attribute(accepted: list[FeedbackDecisionContext]) -> AimMemoryEntry | None:
    types = Counter(c.primary_entity_type for c in accepted if c.primary_entity_type)
    if not types:
        return None
    return AimMemoryEntry(
        memory_type="preferred_entity_attribute",
        payload={"accepted_entity_type_counts": dict(types)},
        sample_size=sum(types.values()),
    )


def _source_effectiveness(contexts: list[FeedbackDecisionContext]) -> AimMemoryEntry | None:
    stats: dict[str, dict[str, int]] = {}
    for ctx in contexts:
        if ctx.feedback_type not in ("accepted", "rejected"):
            continue
        for source_key in set(ctx.source_keys):
            bucket = stats.setdefault(source_key, {"accepted": 0, "rejected": 0})
            bucket[ctx.feedback_type] += 1
    if not stats:
        return None
    by_source = {}
    total_n = 0
    for source_key, counts in stats.items():
        n = counts["accepted"] + counts["rejected"]
        total_n += n
        by_source[source_key] = {
            **counts,
            "n": n,
            "acceptance_rate": round(counts["accepted"] / n, 4) if n else None,
        }
    return AimMemoryEntry(memory_type="source_effectiveness", payload={"by_source": by_source}, sample_size=total_n)


def compute_aim_memory(contexts: list[FeedbackDecisionContext]) -> list[AimMemoryEntry]:
    """Recomputes the full Aim Memory picture from every feedback
    decision given (typically: all feedback for one Aim to date). Meant
    to be re-run periodically — each call is a fresh, independent
    snapshot; the caller decides how often and stores the result as a
    new aim_memory row rather than overwriting the last one."""

    accepted = [c for c in contexts if c.feedback_type == "accepted"]
    rejected = [c for c in contexts if c.feedback_type == "rejected"]

    entries: list[AimMemoryEntry] = []

    for memory_type, group in (("accepted_pattern", accepted), ("rejected_pattern", rejected)):
        payload = {}
        averages = _average_dimensions(group)
        if averages:
            payload["average_dimension_scores"] = averages
        if memory_type == "rejected_pattern":
            breakdown = _rejection_reason_breakdown(group)
            if breakdown:
                payload["rejection_reason_breakdown"] = breakdown
        if payload:
            entries.append(AimMemoryEntry(memory_type=memory_type, payload=payload, sample_size=len(group)))

    exclusion = _derive_learned_exclusion(rejected)
    if exclusion:
        entries.append(exclusion)

    entries.extend(_action_performance(accepted, rejected))

    preferred = _preferred_entity_attribute(accepted)
    if preferred:
        entries.append(preferred)

    source_eff = _source_effectiveness(contexts)
    if source_eff:
        entries.append(source_eff)

    return entries


__all__ = ["compute_aim_memory", "STRUCTURAL_REJECTION_REASONS"]
