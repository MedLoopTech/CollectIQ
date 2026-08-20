"""Run with: python aimfold_core/feedback/tests/test_feedback.py"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import get_args
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from aimfold_core.feedback.schema import FeedbackRecord, FeedbackType, OutcomeRecord, OutcomeType, RejectionReason

MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20260819120800_feedback_outcomes_schema.sql"


def _values_from_sql_in_clause(sql: str, column: str) -> set[str]:
    """Extract the quoted values inside `<column> ... in (...)` for a
    simple single-line-per-value check constraint, tolerant of the
    surrounding `text not null\\n    check (...)` formatting this file uses."""
    pattern = re.compile(rf"{column}\s+text[^()]*check\s*\([^()]*?in\s*\((.*?)\)", re.S)
    match = pattern.search(sql)
    assert match, f"could not find an `in (...)` clause for column {column!r}"
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


def test_feedback_type_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    db_values = _values_from_sql_in_clause(sql, "feedback_type")
    py_values = set(get_args(FeedbackType))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: FeedbackType matches the DB check constraint ({len(py_values)} values)")


def test_rejection_reason_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    db_values = _values_from_sql_in_clause(sql, "rejection_reason")
    py_values = set(get_args(RejectionReason))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: RejectionReason matches the DB check constraint ({len(py_values)} values)")


def test_outcome_type_matches_migration():
    sql = MIGRATION.read_text(encoding="utf-8")
    db_values = _values_from_sql_in_clause(sql, "outcome_type")
    py_values = set(get_args(OutcomeType))
    assert db_values == py_values, f"DB {db_values} != Python {py_values}"
    print(f"PASS: OutcomeType matches the DB check constraint ({len(py_values)} values)")


def test_rejected_requires_reason():
    try:
        FeedbackRecord(tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(), feedback_type="rejected")
        raise AssertionError("expected ValidationError — rejected with no reason")
    except ValidationError as exc:
        assert "rejection_reason is required" in str(exc)
    rec = FeedbackRecord(
        tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(),
        feedback_type="rejected", rejection_reason="weak_evidence",
    )
    assert rec.rejection_reason == "weak_evidence"
    print("PASS: FeedbackRecord requires rejection_reason iff feedback_type='rejected'")


def test_non_rejected_forbids_reason():
    try:
        FeedbackRecord(
            tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(),
            feedback_type="accepted", rejection_reason="weak_evidence",
        )
        raise AssertionError("expected ValidationError — accepted with a reason set")
    except ValidationError as exc:
        assert "must be null unless" in str(exc)
    print("PASS: FeedbackRecord rejects a rejection_reason on non-rejected feedback")


def test_feedback_record_carries_prediction_snapshot():
    rec = FeedbackRecord(
        tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(),
        feedback_type="accepted",
        predicted_total_score=91.8, predicted_confidence=0.75,
        predicted_recommended_action="contact", scoring_version="scoring-engine-2026-08-19-v1",
    )
    assert rec.predicted_total_score == 91.8
    assert rec.scoring_version == "scoring-engine-2026-08-19-v1"
    print("PASS: FeedbackRecord carries a Learning Loop prediction snapshot (section 21)")


def test_outcome_record_rejects_negative_monetary_value():
    try:
        OutcomeRecord(tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(), outcome_type="won", monetary_value=-500)
        raise AssertionError("expected ValidationError — negative monetary_value")
    except ValidationError:
        pass
    rec = OutcomeRecord(tenant_id=uuid4(), aim_id=uuid4(), opportunity_id=uuid4(), outcome_type="won", monetary_value=15000)
    assert rec.currency == "USD"
    print("PASS: OutcomeRecord rejects negative monetary_value, defaults currency to USD")


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
