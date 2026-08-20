"""Deterministic Action Recommender — no LLM call.

AIMFOLD_MASTER_GOAL.md section 17 (Confidence-Based Automation) already
specifies this as a threshold policy, not a judgment call: "Low confidence
-> discard, hold, or gather more evidence. Medium -> deeper research.
High -> surface as Opportunity. Very high -> prepare recommended action
automatically." Section 28 (Deterministic Before AI) applies directly —
thresholds and taxonomy lookups don't need a model.

The one thing this module refuses to do is recommend an action the Aim
itself didn't propose: every recommendation is chosen from
compiled_spec.likely_actions, never invented (section 15: "Actions must
be appropriate to the Aim and evidence").
"""

from __future__ import annotations

from aimfold_core.aim_compiler.schema import CompiledAimSpec, OpportunityType, RecommendedAction

from .schema import DEFAULT_ACTION_THRESHOLDS, ActionRecommendation, ActionThresholds

# Which action is the "primary," most committal one per opportunity type
# — used only at the top (Very High) tier, and only if the Aim actually
# lists it as plausible.
PRIMARY_ACTION_BY_OPPORTUNITY_TYPE: dict[str, RecommendedAction] = {
    "customer_discovery": "contact",
    "career_discovery": "apply",
    "funding_discovery": "review_eligibility",
    "investor_discovery": "contact_investor",
    "partnership_discovery": "engage_partner",
    "vendor_discovery": "contact",
    "market_discovery": "research",
    "acquisition_discovery": "research",
    "custom": "research",
}

# Preference order for the more conservative tiers (deeper_research,
# surface_as_opportunity, or as a fallback when the primary action isn't
# one of the Aim's likely_actions).
CONSERVATIVE_ACTION_PREFERENCE: list[RecommendedAction] = [
    "research", "save", "monitor", "add_to_watchlist", "wait_for_another_signal",
]


def _first_available(preferred: RecommendedAction | None, fallback_order: list[RecommendedAction], likely: list[RecommendedAction]) -> RecommendedAction | None:
    if preferred is not None and preferred in likely:
        return preferred
    for candidate in fallback_order:
        if candidate in likely:
            return candidate
    return likely[0] if likely else None


def recommend_action(
    compiled_spec: CompiledAimSpec,
    opportunity_type: OpportunityType,
    total_score: float,
    confidence: float | None,
    *,
    thresholds: ActionThresholds = DEFAULT_ACTION_THRESHOLDS,
) -> ActionRecommendation:
    likely = compiled_spec.likely_actions

    if not likely:
        return ActionRecommendation(action=None, tier="discard_or_hold", rationale="Aim defines no likely_actions — nothing to recommend.")

    if total_score < thresholds.qualified_threshold:
        action = "wait_for_another_signal" if "wait_for_another_signal" in likely else None
        return ActionRecommendation(
            action=action,
            tier="discard_or_hold",
            rationale=(
                f"score={total_score:.1f} is below qualified_threshold={thresholds.qualified_threshold:.0f} — "
                + (f"holding for another signal ({action!r} is one of the Aim's likely_actions)." if action else "no action recommended yet.")
            ),
        )

    if total_score < thresholds.high_priority_threshold:
        action = _first_available("research", CONSERVATIVE_ACTION_PREFERENCE, likely)
        return ActionRecommendation(
            action=action,
            tier="deeper_research",
            rationale=(
                f"score={total_score:.1f} qualifies but is below high_priority_threshold={thresholds.high_priority_threshold:.0f} — "
                f"recommend {action!r} before committing further."
            ),
        )

    # total_score >= high_priority_threshold
    if confidence is not None and confidence >= thresholds.very_high_confidence_threshold:
        primary = PRIMARY_ACTION_BY_OPPORTUNITY_TYPE.get(opportunity_type)
        action = _first_available(primary, CONSERVATIVE_ACTION_PREFERENCE, likely)
        return ActionRecommendation(
            action=action,
            tier="prepare_action_automatically",
            rationale=(
                f"score={total_score:.1f} >= high_priority_threshold={thresholds.high_priority_threshold:.0f} and "
                f"confidence={confidence:.2f} >= very_high_confidence_threshold={thresholds.very_high_confidence_threshold:.2f} "
                f"— confident enough to prepare {action!r} automatically."
            ),
        )

    action = _first_available(None, CONSERVATIVE_ACTION_PREFERENCE, likely)
    conf_note = f"confidence={confidence:.2f}" if confidence is not None else "confidence is unknown"
    return ActionRecommendation(
        action=action,
        tier="surface_as_opportunity",
        rationale=(
            f"score={total_score:.1f} >= high_priority_threshold={thresholds.high_priority_threshold:.0f} but {conf_note} "
            f"< very_high_confidence_threshold={thresholds.very_high_confidence_threshold:.2f} — surfacing for human "
            f"review ({action!r} suggested) rather than auto-preparing a committal action."
        ),
    )


__all__ = ["recommend_action", "PRIMARY_ACTION_BY_OPPORTUNITY_TYPE"]
