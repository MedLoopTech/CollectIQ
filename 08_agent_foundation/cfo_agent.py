"""CollectIQ Phase 6 CFO Agent.

Turns deterministic weekly Sprint metrics into a concise management brief.
It cannot alter financial values or make guaranteed recovery claims.
"""
from __future__ import annotations
from typing import Any
from llm_provider import LLMProvider

SYSTEM_PROMPT="""You are CollectIQ's CFO Agent. Return JSON only.
Write a concise weekly recovery brief from supplied deterministic metrics and recorded events.
Never invent financial values or imply guaranteed recovery. Distinguish cash already collected from promises due.
Required JSON: {"headline":"","executive_summary":"","metrics_commentary":[],"management_attention":[],
"next_week_actions":[],"risks":[],"client_ready_summary":""}.
Client-ready text must stay factual and professional. Legal/compliance or unclear financial issues go into risks.
"""

def build_cfo_brief(data:dict[str,Any],provider:LLMProvider|None=None)->dict[str,Any]:
    provider=provider or LLMProvider()
    result=provider.json_completion(system_prompt=SYSTEM_PROMPT,user_payload={"weekly_recovery_facts":data},temperature=0.0,max_tokens=1500)
    out=result["data"]
    out["source_metrics"]=data.get("snapshot") or data.get("metrics") or {}
    out["model_run"]=result["run"]
    return out
