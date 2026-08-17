from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from audit_agent import interpret_audit
from manager_agent import build_manager_brief

app = FastAPI(title="CollectIQ Agent Service", version="0.1.0")


class Payload(BaseModel):
    data: dict


@app.get("/health")
def health():
    return {"ok": True, "service": "collectiq-agent-service", "version": "0.1.0"}


@app.post("/manager/brief")
def manager_brief(payload: Payload):
    try:
        return build_manager_brief(payload.data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/audit/interpret")
def audit_interpret(payload: Payload):
    try:
        return interpret_audit(payload.data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
