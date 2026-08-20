"""Run with: python aimfold_core/analytics/tests/test_analytics.py"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.analytics.performance import compute_performance_report, rollup
from aimfold_core.analytics.schema import OpportunityOutcomeContext

TENANT_A = uuid4()
TENANT_B = uuid4()
AIM_A1 = uuid4()
AIM_A2 = uuid4()
AIM_B1 = uuid4()


def _ctx(tenant, aim, opp_type="customer_discovery", feedback_type=None, outcomes=None, values=None) -> OpportunityOutcomeContext:
    return OpportunityOutcomeContext(
        opportunity_id=uuid4(), tenant_id=tenant, aim_id=aim, opportunity_type=opp_type,
        feedback_type=feedback_type, outcome_types=outcomes or [], outcome_monetary_values=values or [],
    )


def test_funnel_counts_and_rates():
    contexts = [
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["meeting"]),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted"),  # accepted, no outcome yet
        _ctx(TENANT_A, AIM_A1, feedback_type="rejected"),
        _ctx(TENANT_A, AIM_A1, feedback_type="held"),
        _ctx(TENANT_A, AIM_A1, feedback_type=None),
    ]
    report = compute_performance_report("aim", str(AIM_A1), contexts, raw_signal_count=50, qualified_signal_count=10)
    f = report.funnel
    assert f.raw_signal_count == 50 and f.qualified_signal_count == 10
    assert f.surfaced_opportunity_count == 5
    assert f.accepted_count == 2 and f.rejected_count == 1 and f.held_count == 1 and f.no_decision_count == 1
    assert f.accepted_opportunity_rate == 0.4  # 2/5
    assert f.action_rate == 0.5  # 1 of 2 accepted has an outcome
    print("PASS: funnel counts and rates computed correctly")


def test_outcome_correlation_classifies_success_and_failure():
    contexts = [
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["meeting"]),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["won"]),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["negative_response"]),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["custom"]),  # unclassified on purpose
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted"),  # no outcome at all
    ]
    report = compute_performance_report("aim", str(AIM_A1), contexts)
    oc = report.outcome_correlation
    assert oc.opportunities_with_outcomes == 4
    assert oc.successful_outcome_rate == 0.5  # 2 of 4 (meeting, won)
    assert oc.unsuccessful_outcome_rate == 0.25  # 1 of 4 (negative_response)
    assert oc.outcome_type_counts == {"meeting": 1, "won": 1, "negative_response": 1, "custom": 1}
    print("PASS: outcome correlation correctly classifies success/failure and leaves 'custom' unclassified")


def test_outcome_correlation_empty_when_no_outcomes():
    contexts = [_ctx(TENANT_A, AIM_A1, feedback_type="accepted")]
    report = compute_performance_report("aim", str(AIM_A1), contexts)
    assert report.outcome_correlation.opportunities_with_outcomes == 0
    assert report.outcome_correlation.successful_outcome_rate is None
    print("PASS: outcome_correlation reports None rates (not 0.0 or a crash) when nothing has an outcome yet")


def test_economic_summary():
    contexts = [
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["won"], values=[15000]),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted", outcomes=["won"], values=[5000]),
        _ctx(TENANT_A, AIM_A1, feedback_type="rejected"),
    ]
    report = compute_performance_report("aim", str(AIM_A1), contexts)
    assert report.economic.opportunities_with_monetary_value == 2
    assert report.economic.total_monetary_value == 20000
    assert report.economic.average_monetary_value == 10000
    print("PASS: economic summary sums and averages monetary_value correctly, ignoring opportunities with none")


def test_empty_contexts_do_not_crash():
    report = compute_performance_report("aim", str(AIM_A1), [])
    assert report.funnel.surfaced_opportunity_count == 0
    assert report.funnel.accepted_opportunity_rate == 0.0
    assert report.economic.total_monetary_value == 0.0
    print("PASS: an empty scope produces a well-formed zeroed report, not a crash or NaN")


def test_rollup_by_aim_never_mixes_tenants():
    contexts = [
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted"),
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted"),
        _ctx(TENANT_A, AIM_A2, feedback_type="rejected"),
        _ctx(TENANT_B, AIM_B1, feedback_type="rejected"),
        _ctx(TENANT_B, AIM_B1, feedback_type="rejected"),
    ]
    reports = rollup(contexts, "aim")
    assert set(reports.keys()) == {str(AIM_A1), str(AIM_A2), str(AIM_B1)}
    assert reports[str(AIM_A1)].funnel.accepted_count == 2
    assert reports[str(AIM_A1)].funnel.rejected_count == 0
    assert reports[str(AIM_B1)].funnel.rejected_count == 2
    assert reports[str(AIM_B1)].funnel.accepted_count == 0
    print("PASS: rollup(level='aim') never blends tenant A's accepted counts into tenant B's aim report")


def test_rollup_by_tenant_is_isolated():
    contexts = [
        _ctx(TENANT_A, AIM_A1, feedback_type="accepted"),
        _ctx(TENANT_A, AIM_A2, feedback_type="accepted"),
        _ctx(TENANT_B, AIM_B1, feedback_type="rejected"),
    ]
    reports = rollup(contexts, "tenant")
    assert reports[str(TENANT_A)].funnel.accepted_count == 2
    assert reports[str(TENANT_A)].funnel.rejected_count == 0
    assert reports[str(TENANT_B)].funnel.rejected_count == 1
    print("PASS: rollup(level='tenant') correctly isolates tenant A's and tenant B's aims into separate reports")


def test_rollup_by_opportunity_type_deliberately_crosses_tenants():
    contexts = [
        _ctx(TENANT_A, AIM_A1, opp_type="customer_discovery", feedback_type="accepted"),
        _ctx(TENANT_B, AIM_B1, opp_type="customer_discovery", feedback_type="accepted"),
    ]
    reports = rollup(contexts, "opportunity_type")
    report = reports["customer_discovery"]
    assert report.funnel.accepted_count == 2  # both tenants combined — intentional, a cross-tenant benchmark
    assert "never fed back into any single tenant" in report.note
    print("PASS: rollup(level='opportunity_type') deliberately aggregates across tenants and says so in the report's note")


def test_rollup_global_level_rejected():
    try:
        rollup([_ctx(TENANT_A, AIM_A1)], "global")
        raise AssertionError("expected ValueError — rollup() doesn't support 'global'")
    except ValueError as exc:
        assert "compute_performance_report" in str(exc)
    print("PASS: rollup() refuses 'global' and points the caller at compute_performance_report() instead")


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
