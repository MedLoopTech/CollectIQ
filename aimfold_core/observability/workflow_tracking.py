"""Transparent workflow-execution tracking — AIMFOLD_MASTER_GOAL.md
section 34 ("workflow executions").

`WorkflowRunTracker` is a context manager, not a decorator or a change to
any pipeline function — it wraps a *call site*, so the multi-step
computations it tracks (`run_evaluation()`, `proposals/testing.py`'s
`test_*_proposal()`, `compute_aim_memory()`) stay completely unaware this
exists, same non-invasive approach as InstrumentedLLMClient.

Usage:

    with WorkflowRunTracker(tenant_id=t, workflow_type="evaluation_run", aim_id=a) as tracker:
        report = run_evaluation(examples, compiled_spec, client, dataset_name="...")
        tracker.items_processed = report.n_examples
        tracker.items_qualified = sum(1 for r in report.results if r.stage1_qualifies)
    tracker.run  # -> WorkflowRun, status='succeeded' or 'failed', duration measured automatically

An exception raised inside the `with` block is recorded as a `'failed'`
WorkflowRun (with the error message) and then re-raised — this class
observes, it never swallows failures.
"""

from __future__ import annotations

import time
from uuid import UUID

from .schema import WorkflowRun, WorkflowType


class WorkflowRunTracker:
    def __init__(
        self,
        *,
        tenant_id: UUID,
        workflow_type: WorkflowType,
        aim_id: UUID | None = None,
        metadata: dict | None = None,
    ):
        self.tenant_id = tenant_id
        self.workflow_type = workflow_type
        self.aim_id = aim_id
        self.metadata = metadata or {}
        self.items_processed = 0
        self.items_qualified: int | None = None
        self.run: WorkflowRun | None = None
        self._start: float | None = None

    def __enter__(self) -> "WorkflowRunTracker":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        duration_ms = (time.perf_counter() - self._start) * 1000
        if exc_type is not None:
            self.run = WorkflowRun(
                tenant_id=self.tenant_id,
                aim_id=self.aim_id,
                workflow_type=self.workflow_type,
                status="failed",
                items_processed=self.items_processed,
                items_qualified=self.items_qualified,
                metadata=self.metadata,
                error_message=str(exc_val),
                duration_ms=duration_ms,
            )
            return False
        self.run = WorkflowRun(
            tenant_id=self.tenant_id,
            aim_id=self.aim_id,
            workflow_type=self.workflow_type,
            status="succeeded",
            items_processed=self.items_processed,
            items_qualified=self.items_qualified,
            metadata=self.metadata,
            duration_ms=duration_ms,
        )
        return False


__all__ = ["WorkflowRunTracker"]
