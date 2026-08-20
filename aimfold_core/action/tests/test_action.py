"""Run with: python aimfold_core/action/tests/test_action.py"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from aimfold_core.action.recommender import recommend_action
from aimfold_core.action.schema import ActionThresholds
from aimfold_core.aim_compiler.schema import CompiledAimSpec

SEED_MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120200_seed_collectiq_aim.sql"


def load_collectiq_spec() -> CompiledAimSpec:
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"\$spec\$(.*?)\$spec\$", sql, re.S)
    assert match
    return CompiledAimSpec.model_validate(json.loads(match.group(1)))


def _spec_with_actions(*actions: str, base: CompiledAimSpec | None = None) -> CompiledAimSpec:
    base = base or load_collectiq_spec()
    return base.model_copy(update={"likely_actions": list(actions)})


def test_no_likely_actions_means_discard_or_hold():
    spec = _spec_with_actions()
    rec = recommend_action(spec, "customer_discovery", total_score=95, confidence=0.9)
    assert rec.action is None and rec.tier == "discard_or_hold"
    print("PASS: an Aim with no likely_actions never gets a recommendation")


def test_low_score_holds_for_another_signal_when_available():
    spec = _spec_with_actions("contact", "wait_for_another_signal")
    rec = recommend_action(spec, "customer_discovery", total_score=20, confidence=None)
    assert rec.tier == "discard_or_hold"
    assert rec.action == "wait_for_another_signal"
    print("PASS: low score -> discard_or_hold, picks wait_for_another_signal when the Aim allows it")


def test_low_score_with_no_wait_action_recommends_nothing():
    spec = _spec_with_actions("contact")
    rec = recommend_action(spec, "customer_discovery", total_score=20, confidence=None)
    assert rec.tier == "discard_or_hold"
    assert rec.action is None
    print("PASS: low score with wait_for_another_signal unavailable -> no action, not a fabricated substitute")


def test_medium_score_recommends_research():
    spec = _spec_with_actions("contact", "research")
    rec = recommend_action(spec, "customer_discovery", total_score=65, confidence=0.9)
    assert rec.tier == "deeper_research"
    assert rec.action == "research"
    print("PASS: medium score (qualified but below high_priority) -> deeper_research, picks 'research'")


def test_high_score_low_confidence_surfaces_without_auto_action():
    spec = _spec_with_actions("contact", "research")
    rec = recommend_action(spec, "customer_discovery", total_score=90, confidence=0.3)
    assert rec.tier == "surface_as_opportunity"
    assert rec.action == "research"  # conservative, NOT the committal 'contact'
    print("PASS: high score but low confidence -> surfaced for review, NOT auto-prepared for the committal action")


def test_high_score_high_confidence_prepares_primary_action():
    spec = _spec_with_actions("contact", "research")
    rec = recommend_action(spec, "customer_discovery", total_score=90, confidence=0.85)
    assert rec.tier == "prepare_action_automatically"
    assert rec.action == "contact"  # primary action for customer_discovery
    print("PASS: high score + high confidence -> prepare_action_automatically, picks the type-appropriate primary action")


def test_primary_action_falls_back_when_not_in_likely_actions():
    spec = _spec_with_actions("monitor", "save")  # 'contact' deliberately absent
    rec = recommend_action(spec, "customer_discovery", total_score=90, confidence=0.9)
    assert rec.tier == "prepare_action_automatically"
    assert rec.action in ("monitor", "save")  # never invents 'contact' when the Aim didn't list it
    assert rec.action != "contact"
    print("PASS: never recommends an action outside the Aim's own likely_actions, even at the top tier")


def test_action_thresholds_must_be_ordered():
    try:
        ActionThresholds(qualified_threshold=80, high_priority_threshold=50)
        raise AssertionError("expected validation error")
    except ValidationError as exc:
        assert "qualified_threshold must be lower" in str(exc)
    print("PASS: ActionThresholds rejects inverted threshold pair")


def test_real_collectiq_spec_at_very_high_tier():
    # CollectIQ's actual seeded Aim only lists likely_actions=['contact'].
    spec = load_collectiq_spec()
    assert spec.likely_actions == ["contact"]
    # Using the real score/confidence produced by score_signal() on real
    # Gemini evidence in the PR7 tests (91.8 total, 0.75 confidence).
    rec = recommend_action(spec, "customer_discovery", total_score=91.8, confidence=0.75)
    assert rec.tier == "prepare_action_automatically"
    assert rec.action == "contact"
    print(f"PASS: real CollectIQ Aim + real scored evidence -> {rec.tier} / {rec.action!r}")
    print(f"   rationale: {rec.rationale}")


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
