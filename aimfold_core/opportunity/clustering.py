"""Entity-keyed opportunity clustering — AIMFOLD_MASTER_GOAL.md section 12:
"Entity -> Opportunity -> Signals" rather than one opportunity per signal.

Entity identity is the hard clustering key: a new qualifying signal about
an entity that already has a live opportunity under the same Aim
strengthens that opportunity rather than creating a new row. Time
proximity between signals is NOT used as an additional clustering gate
here — it already shows up as a confidence signal via
aimfold_core.scoring's Timing/Trigger dimension (recency bucketing), so
gating clustering on it too would double-count the same information and
risks splitting one entity's ongoing signal into multiple opportunities
just because two signals happened to land a few days apart.
"""

from __future__ import annotations

from uuid import UUID

from .schema import ClusteringDecision, OpportunityCandidate


def decide_cluster(
    tenant_id: UUID,
    aim_id: UUID,
    primary_entity_id: UUID,
    candidates: list[OpportunityCandidate],
) -> ClusteringDecision:
    eligible = [
        c
        for c in candidates
        if c.tenant_id == tenant_id
        and c.aim_id == aim_id
        and c.primary_entity_id == primary_entity_id
        and c.lifecycle_state not in ("duplicate", "invalid")
    ]

    if not eligible:
        return ClusteringDecision(
            attach_to_opportunity_id=None,
            reason="No existing (non-duplicate, non-invalid) opportunity for this entity under this Aim — creating a new one.",
        )

    eligible.sort(key=lambda c: c.last_strengthened_at, reverse=True)
    chosen = eligible[0]
    others = [c.id for c in eligible[1:]]

    reason = (
        f"Attaching to opportunity {chosen.id} (state={chosen.lifecycle_state!r}, "
        f"last strengthened {chosen.last_strengthened_at.isoformat()}) — most recently "
        "strengthened existing opportunity for this entity under this Aim."
    )
    if others:
        reason += (
            f" NOTE: {len(others)} other eligible opportunity(ies) also exist for this entity "
            "under this Aim — that's likely an unintended duplicate and should be reviewed/merged, "
            "not something this function resolves automatically."
        )

    return ClusteringDecision(attach_to_opportunity_id=chosen.id, reason=reason, other_eligible_opportunity_ids=others)


__all__ = ["decide_cluster"]
