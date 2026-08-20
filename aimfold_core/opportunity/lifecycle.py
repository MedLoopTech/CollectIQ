"""Deterministic lifecycle state machine — AIMFOLD_MASTER_GOAL.md
section 11 (default sequence: discovered -> evaluating -> qualified ->
high_priority -> actioned -> outcome, plus held/rejected/stale/expired/
revived/duplicate/invalid) and section 10 (temporal momentum).

next_lifecycle_state() only ever moves an opportunity between the
score/staleness-driven states (discovered, evaluating, qualified,
high_priority, stale, expired, revived). It never transitions into or out
of HUMAN_OR_ACTION_CONTROLLED_STATES — those come from real user
decisions or downstream action/outcome tracking (PR9/PR11), not from
re-scoring. Section 16: humans handle ambiguous opportunities, strategic
decisions, and final decisions; the deterministic engine's job stops at
"here's what the evidence and elapsed time say," not at deciding
someone's fate.
"""

from __future__ import annotations

from datetime import datetime

from .schema import (
    DEFAULT_LIFECYCLE_THRESHOLDS,
    HUMAN_OR_ACTION_CONTROLLED_STATES,
    LifecycleState,
    LifecycleThresholds,
    LifecycleTransition,
    TemporalMomentum,
)


def next_lifecycle_state(
    current_state: LifecycleState | None,
    total_score: float,
    days_since_last_strengthened: float,
    *,
    thresholds: LifecycleThresholds = DEFAULT_LIFECYCLE_THRESHOLDS,
) -> LifecycleTransition:
    if current_state is not None and current_state in HUMAN_OR_ACTION_CONTROLLED_STATES:
        return LifecycleTransition(
            from_state=current_state,
            to_state=current_state,
            reason=f"{current_state!r} is human/action-controlled — not auto-transitioned by re-scoring.",
        )

    effective_from = current_state or "discovered"

    if days_since_last_strengthened >= thresholds.expired_after_days:
        return LifecycleTransition(
            from_state=effective_from,
            to_state="expired",
            reason=f"No new signal in {days_since_last_strengthened:.0f}d (>= expired_after_days={thresholds.expired_after_days:.0f}).",
        )

    if days_since_last_strengthened >= thresholds.stale_after_days:
        return LifecycleTransition(
            from_state=effective_from,
            to_state="stale",
            reason=f"No new signal in {days_since_last_strengthened:.0f}d (>= stale_after_days={thresholds.stale_after_days:.0f}).",
        )

    if effective_from in ("stale", "expired") and total_score >= thresholds.qualified_threshold:
        would_be = "high_priority" if total_score >= thresholds.high_priority_threshold else "qualified"
        return LifecycleTransition(
            from_state=effective_from,
            to_state="revived",
            reason=f"New qualifying signal arrived after being {effective_from} — score={total_score:.1f} now supports {would_be!r} on the next pass.",
        )

    if total_score >= thresholds.high_priority_threshold:
        return LifecycleTransition(
            from_state=effective_from,
            to_state="high_priority",
            reason=f"score={total_score:.1f} >= high_priority_threshold={thresholds.high_priority_threshold:.0f}.",
        )

    if total_score >= thresholds.qualified_threshold:
        return LifecycleTransition(
            from_state=effective_from,
            to_state="qualified",
            reason=f"score={total_score:.1f} >= qualified_threshold={thresholds.qualified_threshold:.0f}.",
        )

    return LifecycleTransition(
        from_state=effective_from,
        to_state="evaluating",
        reason=f"score={total_score:.1f} below qualified_threshold={thresholds.qualified_threshold:.0f}.",
    )


def classify_momentum(
    previous_score: float | None,
    current_score: float,
    *,
    stable_band: float = 3.0,
) -> TemporalMomentum:
    """Section 10's finer-grained descriptive label, not a stored
    lifecycle_state — this is meant for UI/explanation ("this was not
    especially actionable before; new evidence makes it relevant now"),
    computed fresh from whatever score history the caller has, not
    persisted by this PR (no score-history table exists yet)."""

    if previous_score is None:
        return "emerging"
    delta = current_score - previous_score
    if delta > stable_band:
        return "strengthening"
    if delta < -stable_band:
        return "weakening"
    return "stable"


def days_between(earlier: datetime, later: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds() / 86400)


__all__ = ["next_lifecycle_state", "classify_momentum", "days_between"]
