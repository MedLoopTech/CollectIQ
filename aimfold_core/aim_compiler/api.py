"""FastAPI wrapper around compile_aim — mirrors 02_audit_engine/api.py's
shape (a thin HTTP layer over a pure function) so the two services stay
consistent to operate.

`/aims/compile` only returns a *proposed* AimCompilationResult — nothing
is written yet, matching section 22 (proposals require approval).
`/aims/propose` is the approval step this module's docstring used to
flag as "a separate, still-open piece of PR4": given a compiled_spec the
caller already has (from `/aims/compile`, never re-compiled — see its
own docstring for why), it independently re-validates that spec via the
same CompiledAimSpec Pydantic model (never trusts a client round-trip
blindly), verifies the caller is really who their access token says and
really belongs to the tenant they're proposing an Aim for, and only then
writes `aims`/`aim_versions` using a service-role key — the same
approval-gated persistence pattern PR1's RLS design always intended
(`aims` already allows an authenticated INSERT for exactly this reason;
`aim_versions` deliberately does not, since compiled_spec's structural
validity has to be enforced somewhere before it lands, and a raw client
INSERT can't do that).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from .compiler import AimCompilationError, compile_aim
from .llm_client import build_llm_client_from_env
from .schema import CompiledAimSpec

app = FastAPI(title="Aimfold Aim Compiler", version="0.1.0")

# Dev-scoped: this service isn't deployed anywhere yet (see
# aimfold_core/portal/README.md), so there's no real production origin
# to restrict to. A real deployment should replace "*" with the actual
# portal origin(s).
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class CompileAimRequest(BaseModel):
    raw_user_intent: str


class ProposeAimRequest(BaseModel):
    tenant_id: str
    aim_name: str
    raw_user_intent: str
    compiled_spec: dict
    compiler_model: str
    compiler_prompt_version: str


def _supabase_env() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set — /aims/propose needs "
            "a service-role key to persist an approved Aim (see aim_compiler/.env.example).",
        )
    return url, key


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


@app.post("/aims/propose")
async def propose_aim_endpoint(payload: ProposeAimRequest, request: Request) -> dict:
    try:
        validated_spec = CompiledAimSpec(**payload.compiled_spec)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"compiled_spec failed re-validation: {exc}") from exc

    auth_header = request.headers.get("authorization", "")
    access_token = auth_header.removeprefix("Bearer ").strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing Authorization bearer token")

    supabase_url, service_key = _supabase_env()

    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {access_token}", "apikey": service_key},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        user_id = user_resp.json()["id"]

        # Explicit tenant-membership check — service-role bypasses RLS,
        # so this endpoint has to do by hand exactly what
        # is_tenant_member() would have enforced for a normal client insert.
        member_resp = await client.get(
            f"{supabase_url}/rest/v1/tenant_members",
            params={"tenant_id": f"eq.{payload.tenant_id}", "user_id": f"eq.{user_id}", "select": "role"},
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
        )
        if member_resp.status_code != 200 or not member_resp.json():
            raise HTTPException(status_code=403, detail="Not a member of this tenant")

        service_headers = {
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

        aim_resp = await client.post(
            f"{supabase_url}/rest/v1/aims",
            headers=service_headers,
            json={
                "tenant_id": payload.tenant_id,
                "name": payload.aim_name,
                "opportunity_type": validated_spec.opportunity_type,
                "status": "active",
                "created_by": user_id,
            },
        )
        if aim_resp.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"Failed to create aim: {aim_resp.text}")
        aim_id = aim_resp.json()[0]["id"]

        version_resp = await client.post(
            f"{supabase_url}/rest/v1/aim_versions",
            headers=service_headers,
            json={
                "tenant_id": payload.tenant_id,
                "aim_id": aim_id,
                "version_number": 1,
                "is_current": True,
                "raw_user_intent": payload.raw_user_intent,
                "compiled_spec": validated_spec.model_dump(mode="json"),
                "status": "approved",
                "approved_by": user_id,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "compiler_model": payload.compiler_model,
                "compiler_prompt_version": payload.compiler_prompt_version,
            },
        )
        if version_resp.status_code >= 300:
            # No cross-table transaction over two REST calls — a failure
            # here leaves an orphan `aims` row with no current version.
            # Surfaced directly rather than papered over with saga/retry
            # logic this scope doesn't need; the aim stays invisible in
            # practice since every UI reads via aim_versions.is_current.
            raise HTTPException(status_code=502, detail=f"Failed to create aim_version: {version_resp.text}")
        aim_version_id = version_resp.json()[0]["id"]

    return {"aim_id": aim_id, "aim_version_id": aim_version_id}
