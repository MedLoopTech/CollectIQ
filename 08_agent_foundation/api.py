from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from audit_agent import interpret_audit
from manager_agent import build_manager_brief
from prospect_agents import research_prospect, draft_outreach
from sales_agent import handle_reply
from recovery_agent import run_recovery
from cfo_agent import build_cfo_brief

app = FastAPI(title="CollectIQ Agent Service", version="0.4.0")


class Payload(BaseModel):
    data: dict


@app.get("/health")
def health():
    return {"ok": True, "service": "collectiq-agent-service", "version": "0.4.0"}


def _run(fn, data):
    try:
        return fn(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/manager/brief")
def manager_brief(payload: Payload):
    return _run(build_manager_brief, payload.data)


@app.post("/audit/interpret")
def audit_interpret(payload: Payload):
    return _run(interpret_audit, payload.data)


@app.post("/research/prospect")
def prospect_research(payload: Payload):
    return _run(research_prospect, payload.data)


@app.post("/outreach/draft")
def outreach_draft(payload: Payload):
    data = payload.data
    try:
        return draft_outreach(data.get("prospect", {}), data.get("research", {}))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/sales/reply")
def sales_reply(payload: Payload):
    return _run(handle_reply, payload.data)


@app.post("/recovery/run")
def recovery_run(payload: Payload):
    return _run(run_recovery, payload.data)


@app.post("/cfo/brief")
def cfo_brief(payload: Payload):
    return _run(build_cfo_brief, payload.data)
