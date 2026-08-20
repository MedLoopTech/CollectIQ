"""Run with: python aimfold_core/observability/tests/test_observability.py"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from aimfold_core.aim_compiler.llm_client import StubLLMClient
from aimfold_core.observability.cost import estimate_model_cost
from aimfold_core.observability.cost_analytics import CostContext, compute_cost_report, rollup
from aimfold_core.observability.instrumented_client import InstrumentedLLMClient
from aimfold_core.observability.schema import ModelCallStage, WorkflowRun, WorkflowType
from aimfold_core.observability.workflow_tracking import WorkflowRunTracker

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819121400_observability_schema.sql"

TENANT_A = uuid4()
TENANT_B = uuid4()
AIM_A1 = uuid4()
AIM_A2 = uuid4()
AIM_B1 = uuid4()


def _db_check_values(sql: str, column: str) -> set[str]:
    match = re.search(rf"{column}\s+text[^()]*check\s*\([^()]*?in\s*\((.*?)\)", sql, re.S)
    assert match, f"couldn't find a CHECK constraint for {column} in the migration"
    return set(re.findall(r"'([a-z0-9_]+)'", match.group(1)))


def test_model_call_stage_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    db_values = _db_check_values(sql, "stage")
    py_values = set(get_args(ModelCallStage))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: ModelCallStage matches the DB check constraint ({len(py_values)} values)")


def test_workflow_type_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    db_values = _db_check_values(sql, "workflow_type")
    py_values = set(get_args(WorkflowType))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: WorkflowType matches the DB check constraint ({len(py_values)} values)")


# --- cost.py -----------------------------------------------------------


def test_known_model_cost_is_computed():
    cost = estimate_model_cost("gemini", "gemini-flash-lite-latest", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.50  # $0.10 + $0.40 per the rate table
    print("PASS: estimate_model_cost computes a known (provider, model) rate correctly")


def test_unknown_model_returns_none_not_zero():
    cost = estimate_model_cost("gemini", "some-future-model-not-in-the-table", input_tokens=100, output_tokens=100)
    assert cost is None
    print("PASS: estimate_model_cost returns None (not 0.0) for an unpriced model — never guesses")


def test_missing_token_counts_returns_none():
    cost = estimate_model_cost("gemini", "gemini-flash-lite-latest", input_tokens=None, output_tokens=100)
    assert cost is None
    print("PASS: estimate_model_cost returns None when token counts are missing, even for a known model")


# --- instrumented_client.py ---------------------------------------------


def test_instrumented_client_records_a_successful_call():
    stub = StubLLMClient({"hello": '{"objective": "test"}'})
    client = InstrumentedLLMClient(stub, tenant_id=TENANT_A, stage="aim_compilation", provider="stub", model="stub-deterministic", aim_id=AIM_A1)
    response = client.complete("system", "hello world")
    assert response.text == '{"objective": "test"}'
    assert len(client.model_runs) == 1
    run = client.model_runs[0]
    assert run.success is True
    assert run.tenant_id == TENANT_A and run.aim_id == AIM_A1 and run.stage == "aim_compilation"
    assert run.latency_ms is not None and run.latency_ms >= 0
    print("PASS: InstrumentedLLMClient records a ModelRun for a successful call without altering the response")


def test_instrumented_client_records_and_reraises_a_failure():
    stub = StubLLMClient({"hello": "canned"})
    client = InstrumentedLLMClient(stub, tenant_id=TENANT_A, stage="evidence_stage2", provider="stub", model="stub-deterministic")
    try:
        client.complete("system", "this prompt has no canned response")
        raise AssertionError("expected NotImplementedError from StubLLMClient")
    except NotImplementedError:
        pass
    assert len(client.model_runs) == 1
    run = client.model_runs[0]
    assert run.success is False
    assert run.error_message is not None and "no canned response" in run.error_message
    assert run.input_tokens is None and run.estimated_cost_usd is None
    print("PASS: InstrumentedLLMClient records a failed ModelRun and re-raises the original exception")


def test_instrumented_client_never_calls_estimate_cost_for_unknown_model():
    stub = StubLLMClient({"x": "y"})
    client = InstrumentedLLMClient(stub, tenant_id=TENANT_A, stage="research_synthesis", provider="stub", model="stub-deterministic")
    client.complete("s", "x")
    assert client.model_runs[0].estimated_cost_usd is None
    print("PASS: a stub/unpriced model correctly yields estimated_cost_usd=None, not a fabricated number")


# --- workflow_tracking.py ------------------------------------------------


def test_workflow_run_invariant_duration_vs_status():
    try:
        WorkflowRun(tenant_id=TENANT_A, workflow_type="evaluation_run", status="running", duration_ms=5.0)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    try:
        WorkflowRun(tenant_id=TENANT_A, workflow_type="evaluation_run", status="succeeded")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    print("PASS: WorkflowRun rejects duration_ms/status combinations that can't have happened yet")


def test_workflow_run_tracker_success_path():
    with WorkflowRunTracker(tenant_id=TENANT_A, workflow_type="evaluation_run", aim_id=AIM_A1) as tracker:
        tracker.items_processed = 5
        tracker.items_qualified = 3
    assert tracker.run is not None
    assert tracker.run.status == "succeeded"
    assert tracker.run.items_processed == 5 and tracker.run.items_qualified == 3
    assert tracker.run.duration_ms is not None and tracker.run.duration_ms >= 0
    print("PASS: WorkflowRunTracker produces a succeeded WorkflowRun with a real measured duration")


def test_workflow_run_tracker_failure_path_reraises():
    try:
        with WorkflowRunTracker(tenant_id=TENANT_A, workflow_type="proposal_test") as tracker:
            tracker.items_processed = 2
            raise RuntimeError("something in the wrapped workflow broke")
        raise AssertionError("expected RuntimeError to propagate out of the with block")
    except RuntimeError as exc:
        assert "broke" in str(exc)
    assert tracker.run.status == "failed"
    assert tracker.run.error_message is not None and "broke" in tracker.run.error_message
    print("PASS: WorkflowRunTracker records a failed WorkflowRun and still re-raises the original exception")


# --- cost_analytics.py -----------------------------------------------------


def _cost_ctx(tenant, aim, opp_type="customer_discovery", cost=0.0, unknown=0, surfaced=0, accepted=0, successful=0) -> CostContext:
    return CostContext(
        aim_id=aim, tenant_id=tenant, opportunity_type=opp_type, total_model_cost_usd=cost,
        unknown_cost_model_call_count=unknown, surfaced_opportunity_count=surfaced,
        accepted_opportunity_count=accepted, successful_outcome_count=successful,
    )


def test_compute_cost_report_arithmetic():
    ctx = _cost_ctx(TENANT_A, AIM_A1, cost=10.0, surfaced=20, accepted=5, successful=2)
    report = compute_cost_report([ctx], "aim", str(AIM_A1))
    assert report.total_cost_usd == 10.0
    assert report.cost_per_surfaced_opportunity == 0.5
    assert report.cost_per_accepted_opportunity == 2.0
    assert report.cost_per_successful_outcome == 5.0
    print("PASS: compute_cost_report divides total cost by each funnel stage correctly")


def test_compute_cost_report_guards_division_by_zero():
    ctx = _cost_ctx(TENANT_A, AIM_A1, cost=10.0, surfaced=0, accepted=0, successful=0)
    report = compute_cost_report([ctx], "aim", str(AIM_A1))
    assert report.cost_per_surfaced_opportunity is None
    assert report.cost_per_accepted_opportunity is None
    assert report.cost_per_successful_outcome is None
    print("PASS: compute_cost_report returns None (not 0.0 or a ZeroDivisionError) when a funnel stage has zero items")


def test_unknown_cost_calls_are_reported_not_hidden():
    ctx = _cost_ctx(TENANT_A, AIM_A1, cost=10.0, unknown=3, surfaced=10)
    report = compute_cost_report([ctx], "aim", str(AIM_A1))
    assert report.unknown_cost_model_call_count == 3
    assert "3 model call" in report.note
    print("PASS: unknown-cost model calls are surfaced in the report, not silently treated as free")


def test_rollup_by_aim_never_mixes_tenants():
    contexts = [
        _cost_ctx(TENANT_A, AIM_A1, cost=5.0, surfaced=10),
        _cost_ctx(TENANT_A, AIM_A2, cost=3.0, surfaced=5),
        _cost_ctx(TENANT_B, AIM_B1, cost=7.0, surfaced=20),
    ]
    reports = rollup(contexts, "aim")
    assert set(reports.keys()) == {str(AIM_A1), str(AIM_A2), str(AIM_B1)}
    assert reports[str(AIM_A1)].total_cost_usd == 5.0
    assert reports[str(AIM_B1)].total_cost_usd == 7.0
    print("PASS: rollup(level='aim') keeps every Aim's cost separate, never blended across tenants")


def test_rollup_by_tenant_sums_its_own_aims_only():
    contexts = [
        _cost_ctx(TENANT_A, AIM_A1, cost=5.0),
        _cost_ctx(TENANT_A, AIM_A2, cost=3.0),
        _cost_ctx(TENANT_B, AIM_B1, cost=7.0),
    ]
    reports = rollup(contexts, "tenant")
    assert reports[str(TENANT_A)].total_cost_usd == 8.0
    assert reports[str(TENANT_B)].total_cost_usd == 7.0
    print("PASS: rollup(level='tenant') sums only that tenant's own Aims")


def test_rollup_global_deliberately_crosses_tenants():
    contexts = [_cost_ctx(TENANT_A, AIM_A1, cost=5.0), _cost_ctx(TENANT_B, AIM_B1, cost=7.0)]
    reports = rollup(contexts, "global")
    assert reports["global"].total_cost_usd == 12.0
    assert "cross-tenant" in reports["global"].note
    print("PASS: rollup(level='global') sums across every tenant given, and says so in the report")


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
