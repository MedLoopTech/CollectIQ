"""CollectIQ Phase 5 Recovery Agent.

Operates on persisted Sprint facts. Deterministic database state remains authoritative.
The agent interprets state, prioritizes actions and drafts follow-ups; it does not mark payments,
resolve disputes, or send customer communications by itself.
"""
from __future__ import annotations
from typing import Any
from llm_provider import LLMProvider

SYSTEM_PROMPT="""You are CollectIQ's Recovery Agent. Return JSON only.
Use only supplied Sprint facts. Never invent payments, promises, customer replies, dispute resolutions,
invoice balances, dates or legal conclusions. Do not mark a promise kept unless supplied records show payment.
Do not mark a dispute resolved unless supplied records show it resolved.
Required JSON: {"sprint_health":"on_track|watch|at_risk","summary":"","priority_actions":[
{"account":"","invoice_number":"","priority":0,"reason":"","recommended_action":"","draft_follow_up":"","requires_approval":true}],
"broken_promises":[],"dispute_actions":[],"internal_actions":[],"exceptions":[]}.
Customer-facing drafts are Amber. Legal threats, major disputes, unclear financial claims and sensitive escalation are Red.
"""

def run_recovery(data:dict[str,Any],provider:LLMProvider|None=None)->dict[str,Any]:
    provider=provider or LLMProvider()
    result=provider.json_completion(system_prompt=SYSTEM_PROMPT,user_payload={"sprint_facts":data},temperature=0.0,max_tokens=2200)
    out=result["data"]
    for item in out.get("priority_actions",[]):
        item["requires_approval"]=bool(item.get("draft_follow_up"))
        if item.get("draft_follow_up"): item["risk_tier"]="amber"
        try:item["priority"]=max(0,min(100,int(item.get("priority",50))))
        except Exception:item["priority"]=50
    out["model_run"]=result["run"]
    return out
