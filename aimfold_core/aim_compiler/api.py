"""FastAPI wrapper around compile_aim — mirrors 02_audit_engine/api.py's
shape (a thin HTTP layer over a pure function) so the two services stay
consistent to operate.

This endpoint only returns a *proposed* AimCompilationResult. It does not
write to aim_versions — persistence + the approval flow (status: proposed
-> approved, flipping is_current) is a separate, still-open piece of PR4
that needs a Supabase service-role key this module doesn't have. Wiring
that in is the natural next step once this is reviewed.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .compiler import AimCompilationError, compile_aim
from .llm_client import build_llm_client_from_env

app = FastAPI(title="Aimfold Aim Compiler", version="0.1.0")


class CompileAimRequest(BaseModel):
    raw_user_intent: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/aims/compile")
def compile_aim_endpoint(payload: CompileAimRequest) -> dict:
    try:
        client = build_llm_client_from_env()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        result = compile_aim(payload.raw_user_intent, client)
    except AimCompilationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result.model_dump()
