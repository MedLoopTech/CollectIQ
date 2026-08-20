"""Run with: python aimfold_core/opportunity/tests/test_opportunity.py"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from aimfold_core.opportunity.clustering import decide_cluster
from aimfold_core.opportunity.lifecycle import classify_momentum, next_lifecycle_state
from aimfold_core.opportunity.mapping import opportunity_confidence_fields
from aimfold_core.opportunity.schema import LifecycleThresholds, OpportunityCandidate
from aimfold_core.scoring.schema import DimensionScore, ExplainableScore, DEFAULT_SCORING_WEIGHTS

TENANT = uuid4()
AIM = uuid4()
ENTITY_A = uuid4()
ENTITY_B = uuid4()
NOW = datetime(2026, 8, 19, tzinfo=timezone.utc)


def _candidate(id_: UUID, *, tenant=TENANT, aim=AIM, entity=ENTITY_A, state="qualified", days_ago=1, score=70.0) -> OpportunityCandidate:
    return OpportunityCandidate(
        id=id_, tenant_id=tenant, aim_id=aim, primary_entity_id=entity,
        lifecycle_state=state, last_strengthened_at=NOW - timedelta(days=days_ago), total_score=score,
    )


def test_clustering_creates_new_when_no_candidates():
    decision = decide_cluster(TENANT, AIM, ENTITY_A, [])
    assert decision.attach_to_opportunity_id is None
    print("PASS: clustering creates a new opportunity when there are no candidates")


def test_clustering_ignores_unrelated_candidates():
    other_tenant = _candidate(uuid4(), tenant=uuid4())
    other_aim = _candidate(uuid4(), aim=uuid4())
    other_entity = _candidate(uuid4(), entity=ENTITY_B)
    decision = decide_cluster(TENANT, AIM, ENTITY_A, [other_tenant, other_aim, other_entity])
    assert decision.attach_to_opportunity_id is None
    print("PASS: clustering ignores candidates from a different tenant/aim/entity")


def test_clustering_excludes_duplicate_and_invalid_states():
    dup = _candidate(uuid4(), state="duplicate")
    invalid = _candidate(uuid4(), state="invalid")
    decision = decide_cluster(TENANT, AIM, ENTITY_A, [dup, invalid])
    assert decision.attach_to_opportunity_id is None
    print("PASS: clustering never attaches to a 'duplicate' or 'invalid' opportunity")


def test_clustering_attaches_to_matching_entity_regardless_of_state():
    stale = _candidate(uuid4(), state="stale")
    decision = decide_cluster(TENANT, AIM, ENTITY_A, [stale])
    assert decision.attach_to_opportunity_id == stale.id
    print("PASS: clustering attaches even to a stale/rejected/actioned opportunity for the same entity (not just active ones)")


def test_clustering_picks_most_recently_strengthened_and_flags_others():
    old = _candidate(uuid4(), days_ago=20)
    recent = _candidate(uuid4(), days_ago=1)
    decision = decide_cluster(TENANT, AIM, ENTITY_A, [old, recent])
    assert decision.attach_to_opportunity_id == recent.id
    assert decision.other_eligible_opportunity_ids == [old.id]
    assert "duplicate" in decision.reason.lower()
    print("PASS: clustering picks the most recently strengthened candidate and flags the other as a likely duplicate")


def test_lifecycle_thresholds_must_be_ordered():
    try:
        LifecycleThresholds(qualified_threshold=80, high_priority_threshold=50)
        raise AssertionError("expected validation error")
    except ValidationError as exc:
        assert "qualified_threshold must be lower" in str(exc)
    try:
        LifecycleThresholds(stale_after_days=90, expired_after_days=30)
        raise AssertionError("expected validation error")
    except ValidationError as exc:
        assert "stale_after_days must be lower" in str(exc)
    print("PASS: LifecycleThresholds rejects inverted threshold pairs")


def test_lifecycle_progression_by_score():
    low = next_lifecycle_state(None, total_score=20, days_since_last_strengthened=0)
    mid = next_lifecycle_state("evaluating", total_score=65, days_since_last_strengthened=0)
    high = next_lifecycle_state("qualified", total_score=90, days_since_last_strengthened=0)
    assert low.to_state == "evaluating" and low.from_state == "discovered"
    assert mid.to_state == "qualified"
    assert high.to_state == "high_priority"
    print("PASS: lifecycle progresses discovered->evaluating->qualified->high_priority as score rises")


def test_lifecycle_staleness_and_expiry():
    stale = next_lifecycle_state("qualified", total_score=70, days_since_last_strengthened=35)
    expired = next_lifecycle_state("stale", total_score=70, days_since_last_strengthened=95)
    assert stale.to_state == "stale"
    assert expired.to_state == "expired"
    print("PASS: lifecycle moves to stale after 30d and expired after 90d of no new signal")


def test_lifecycle_revival():
    revived = next_lifecycle_state("stale", total_score=85, days_since_last_strengthened=0)
    still_stale = next_lifecycle_state("stale", total_score=10, days_since_last_strengthened=0)
    assert revived.to_state == "revived"
    assert "high_priority" in revived.reason
    assert still_stale.to_state == "evaluating"  # score too low to revive, correctly does NOT claim revival
    print("PASS: a fresh qualifying signal revives a stale/expired opportunity; a weak one does not")


def test_lifecycle_never_touches_human_controlled_states():
    for state in ("actioned", "outcome", "held", "rejected", "duplicate", "invalid"):
        # even an extreme score/staleness combo must not move these
        result = next_lifecycle_state(state, total_score=99, days_since_last_strengthened=500)
        assert result.to_state == state, f"{state} was auto-transitioned to {result.to_state}"
    print("PASS: next_lifecycle_state never auto-transitions actioned/outcome/held/rejected/duplicate/invalid")


def test_classify_momentum():
    assert classify_momentum(None, 50) == "emerging"
    assert classify_momentum(50, 80) == "strengthening"
    assert classify_momentum(80, 50) == "weakening"
    assert classify_momentum(50, 51) == "stable"
    print("PASS: classify_momentum (emerging/strengthening/weakening/stable) behaves correctly")


def _fake_score(evidence_confidence: float, source_quality: float) -> ExplainableScore:
    dims = []
    for name in ("aim_fit", "evidence_strength", "timing_trigger_strength", "opportunity_relevance", "evidence_confidence", "source_quality", "actionability"):
        weight = getattr(DEFAULT_SCORING_WEIGHTS, name)
        value = {"evidence_confidence": evidence_confidence, "source_quality": source_quality}.get(name, 0.5)
        dims.append(DimensionScore(name=name, weight=weight, raw_value=value, points=value * weight, rationale="test"))
    total = sum(d.points for d in dims)
    return ExplainableScore(dimensions=dims, total_score=total, scoring_version="test", weights_used=DEFAULT_SCORING_WEIGHTS)


def test_opportunity_confidence_fields_mapping():
    score = _fake_score(evidence_confidence=1.0, source_quality=0.5)
    fields = opportunity_confidence_fields(score)
    assert fields.evidence_confidence == 1.0
    assert fields.source_confidence == 0.5
    assert fields.confidence == 0.75  # average of the two
    print("PASS: opportunity_confidence_fields correctly reads evidence_confidence/source_quality dimensions and averages them")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            failures += 1
            print(f"FAIL: {t.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    sys.exit(1 if failures else 0)
