"""Production observability + cost tracking types — AIMFOLD_MASTER_GOAL.md
section 34 (Observability) and section 35 (Cost Intelligence).

Scope note (see 20260819121400_observability_schema.sql's header for the
full rationale): `ModelCallStage` and `WorkflowType` are deliberately
narrow — they name only the call sites / batch computations that exist
and run today (aim_compiler, evidence Stage 2, research synthesis;
run_evaluation(), proposal testing, Aim Memory recomputation). Broader
telemetry section 34 eventually wants (connector health, queue depth,
scheduled-workflow tracking) needs infrastructure this repo doesn't have
yet — adding those types now would mean nothing could ever produce them,
same "don't build for what doesn't exist" discipline as every earlier PR.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

ModelCallStage = Literal["aim_compilation", "evidence_stage2", "research_synthesis"]
WorkflowType = Literal["evaluation_run", "proposal_test", "aim_memory_recompute"]
WorkflowStatus = Literal["running", "succeeded", "failed"]


class ModelRun(BaseModel):
    """One LLM API call. Mirrors `model_runs` — see
    aimfold_core/observability/instrumented_client.py for how this gets
    populated without touching the modules that make the calls."""

    tenant_id: UUID
    aim_id: UUID | None = Field(default=None, description="None if compiled before an aims row exists yet")
    stage: ModelCallStage
    provider: str
    model: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0, description="None when the (provider, model) pair has no known rate — never guessed")
    success: bool = True
    error_message: str | None = None

    model_config = {"extra": "forbid"}


class WorkflowRun(BaseModel):
    """One execution of a multi-step batch computation. Mirrors
    `workflow_runs`. Produced by WorkflowRunTracker, a context manager —
    see workflow_tracking.py."""

    tenant_id: UUID
    aim_id: UUID | None = None
    workflow_type: WorkflowType
    status: WorkflowStatus
    items_processed: int = Field(default=0, ge=0)
    items_qualified: int | None = Field(default=None, ge=0, description="Meaningful for evaluation_run only")
    metadata: dict = Field(default_factory=dict)
    error_message: str | None = None
    duration_ms: float | None = Field(default=None, ge=0, description="None while status='running' (still in progress)")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def duration_matches_status(self) -> "WorkflowRun":
        if self.status == "running" and self.duration_ms is not None:
            raise ValueError("duration_ms must be None while status='running' — it isn't known yet")
        if self.status != "running" and self.duration_ms is None:
            raise ValueError(f"duration_ms is required once status={self.status!r}")
        return self


__all__ = ["ModelCallStage", "WorkflowType", "WorkflowStatus", "ModelRun", "WorkflowRun"]
