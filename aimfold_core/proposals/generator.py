"""Turns aimfold_core.memory's Aim Memory findings into candidate
LearningProposals — deterministic, no LLM (same reasoning as memory/ and
analytics/: this is arithmetic and thresholding over already-computed
statistics, not interpretation).

Every function here only PROPOSES — nothing is applied. AIMFOLD_MASTER_GOAL.md
section 22: "Aimfold must not freely rewrite production behavior."
"""

from __future__ import annotations

from uuid import UUID

from aimfold_core.aim_compiler.schema import CompiledAimSpec
from aimfold_core.memory.schema import AimMemoryEntry
from aimfold_core.scoring.schema import DIMENSION_NAMES, ScoringWeights

from .schema import LearningProposal

# Small, conservative nudge — a proposal engine that isn't allowed to
# auto-promote anything (section 22) should still propose CHANGES a
# human can sanity-check at a glance, not a wholesale rebalance.
SCORING_WEIGHT_ADJUSTMENT_STEP = 2.0
MIN_SAMPLE_SIZE_FOR_SCORING_PROPOSAL = 5


def propose_exclusion(memory_entry: AimMemoryEntry, current_spec: CompiledAimSpec, aim_id: UUID, aim_version_id: UUID) -> LearningProposal | None:
    """From aimfold_core.memory.aim_memory's learned_exclusion entries.

    Note this proposal's real-world effect is currently limited: nothing
    in aimfold_core/evidence or aimfold_core/scoring reads
    compiled_spec.exclusions to compute the `excluded` flag score_signal()
    takes — that matching logic doesn't exist yet. Approving this today
    records the exclusion as data (and would be picked up by exclusion-
    matching logic once built); it does not yet change automated
    behavior on its own. Said plainly in expected_impact rather than
    implied — AIMFOLD_MASTER_GOAL.md section 8's no-fabrication
    discipline applies to what this engine claims about its own effects,
    not only to evidence about entities.
    """

    if memory_entry.memory_type != "learned_exclusion":
        return None

    reason = memory_entry.payload.get("suggested_exclusion_reason")
    fraction = memory_entry.payload.get("fraction_of_rejections")
    if not reason:
        return None

    exclusion_text = f"rejection_reason={reason} (learned from {memory_entry.sample_size} rejections, {fraction:.0%} citing this reason)"
    if exclusion_text in current_spec.exclusions:
        return None  # already proposed/applied

    new_spec = current_spec.model_copy(update={"exclusions": [*current_spec.exclusions, exclusion_text]})

    return LearningProposal(
        proposal_type="add_exclusion",
        aim_id=aim_id,
        current_behavior=f"No exclusion for rejection_reason={reason!r} — matching signals continue to be scored and surfaced normally.",
        proposed_behavior=f"Add to compiled_spec.exclusions: {exclusion_text!r}.",
        supporting_observations={
            "aim_memory_type": "learned_exclusion", "reason": reason, "fraction_of_rejections": fraction,
        },
        affected_aims=[aim_id],
        sample_size=memory_entry.sample_size,
        expected_impact=(
            "Records the exclusion as data on the Aim. NOTE: no exclusion-matching logic exists yet in "
            "aimfold_core/evidence or aimfold_core/scoring, so this does not change scoring behavior until "
            "that matching logic is built — approving this proposal captures the learned pattern, it does "
            "not yet enforce it."
        ),
        rollback_path=f"Remove {exclusion_text!r} from this Aim's compiled_spec.exclusions (aim_version_id={aim_version_id}).",
        proposed_compiled_spec=new_spec,
    )


def propose_scoring_weight_adjustment(
    accepted_entry: AimMemoryEntry,
    rejected_entry: AimMemoryEntry,
    current_weights: ScoringWeights,
    aim_id: UUID,
    *,
    min_sample_size: int = MIN_SAMPLE_SIZE_FOR_SCORING_PROPOSAL,
    step: float = SCORING_WEIGHT_ADJUSTMENT_STEP,
) -> LearningProposal | None:
    """Compares average per-dimension scores between accepted and
    rejected opportunities (from aimfold_core.memory's accepted_pattern/
    rejected_pattern entries). If one dimension clearly separates
    accepted from rejected better than another, proposes a small shift
    of weight toward it — unlike add_exclusion, this DOES have immediate
    real effect once promoted: aimfold_core.scoring.engine.score_signal
    already takes a `weights` parameter and uses it in real computation.
    """

    if accepted_entry.memory_type != "accepted_pattern" or rejected_entry.memory_type != "rejected_pattern":
        return None
    if accepted_entry.sample_size < min_sample_size or rejected_entry.sample_size < min_sample_size:
        return None  # not enough data to trust a weight change

    accepted_avgs = accepted_entry.payload.get("average_dimension_scores", {})
    rejected_avgs = rejected_entry.payload.get("average_dimension_scores", {})
    shared_dims = set(accepted_avgs) & set(rejected_avgs) & set(DIMENSION_NAMES)
    if len(shared_dims) < 2:
        return None  # need at least two dimensions to shift weight between

    deltas = {d: accepted_avgs[d] - rejected_avgs[d] for d in shared_dims}
    most_discriminative = max(deltas, key=deltas.get)
    least_discriminative = min(deltas, key=deltas.get)
    if deltas[most_discriminative] <= 0 or most_discriminative == least_discriminative:
        return None  # nothing meaningfully discriminates

    current_map = current_weights.model_dump()
    if current_map[least_discriminative] < step:
        return None  # can't take weight away from a dimension that's already near zero

    new_map = dict(current_map)
    new_map[most_discriminative] += step
    new_map[least_discriminative] -= step
    new_weights = ScoringWeights(**new_map)  # re-validates sum == 100

    return LearningProposal(
        proposal_type="adjust_scoring_weight",
        aim_id=aim_id,
        current_behavior=f"{most_discriminative} weight={current_map[most_discriminative]}, {least_discriminative} weight={current_map[least_discriminative]}.",
        proposed_behavior=f"{most_discriminative} weight={new_map[most_discriminative]} (+{step}), {least_discriminative} weight={new_map[least_discriminative]} (-{step}).",
        supporting_observations={
            "accepted_avg_dimension_scores": accepted_avgs,
            "rejected_avg_dimension_scores": rejected_avgs,
            "most_discriminative_dimension": most_discriminative,
            "least_discriminative_dimension": least_discriminative,
            "delta": round(deltas[most_discriminative], 4),
        },
        affected_aims=[aim_id],
        sample_size=accepted_entry.sample_size + rejected_entry.sample_size,
        expected_impact=(
            f"{most_discriminative} separates accepted from rejected opportunities by "
            f"{deltas[most_discriminative]:.2f} on average (0-1 scale) — a small weight increase should "
            f"improve ranking_quality without materially changing which opportunities qualify at Stage 1 "
            f"(Stage-1 qualification doesn't use these weights at all)."
        ),
        rollback_path="Set a new scoring_versions row back to the previous weights and mark it is_current.",
        proposed_scoring_weights=new_weights,
    )


__all__ = ["propose_exclusion", "propose_scoring_weight_adjustment"]
