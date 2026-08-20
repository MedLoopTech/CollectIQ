"""Transparent LLM-call instrumentation — AIMFOLD_MASTER_GOAL.md section
34 ("model calls, model failures, model cost, latency").

`InstrumentedLLMClient` wraps any real `LLMClient` and implements the
exact same interface, so it drops into `compile_aim()`,
`evaluate_evidence()`, and `synthesize_entity_context()` with **zero
changes to those modules** — each already depends only on the abstract
LLMClient.complete() contract (see aim_compiler/compiler.py,
evidence/evaluator.py, research/synthesizer.py), the same "Model
Independence" (section 27) property this class relies on.

Usage: construct one instance per call site, per (tenant, Aim, stage) —
`client = InstrumentedLLMClient(real_client, tenant_id=..., stage="aim_compilation")`
— then pass `client` wherever the wrapped client would have gone.
`client.model_runs` accumulates one ModelRun per `.complete()` call,
success or failure, ready for a caller to persist to `model_runs`.
"""

from __future__ import annotations

import time
from uuid import UUID

from aimfold_core.aim_compiler.llm_client import LLMClient, LLMResponse

from .cost import estimate_model_cost
from .schema import ModelCallStage, ModelRun


class InstrumentedLLMClient(LLMClient):
    def __init__(
        self,
        wrapped: LLMClient,
        *,
        tenant_id: UUID,
        stage: ModelCallStage,
        provider: str,
        model: str,
        aim_id: UUID | None = None,
    ):
        self._wrapped = wrapped
        self._tenant_id = tenant_id
        self._aim_id = aim_id
        self._stage = stage
        self._provider = provider
        self._model = model
        self.model_runs: list[ModelRun] = []

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.perf_counter()
        try:
            response = self._wrapped.complete(system_prompt, user_prompt)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self.model_runs.append(
                ModelRun(
                    tenant_id=self._tenant_id,
                    aim_id=self._aim_id,
                    stage=self._stage,
                    provider=self._provider,
                    model=self._model,
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(exc),
                )
            )
            raise

        latency_ms = (time.perf_counter() - start) * 1000
        cost = estimate_model_cost(response.provider, response.model, response.input_tokens, response.output_tokens)
        self.model_runs.append(
            ModelRun(
                tenant_id=self._tenant_id,
                aim_id=self._aim_id,
                stage=self._stage,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=cost,
                success=True,
            )
        )
        return response


__all__ = ["InstrumentedLLMClient"]
