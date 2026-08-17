"""CollectIQ Phase 3 agents: Scout, Research and Outreach.

These agents enrich and interpret already-collected public hiring/company signals.
They do not scrape websites themselves and they never send outreach directly.
"""
from __future__ import annotations
from typing import Any
from llm_provider import LLMProvider

RESEARCH_PROMPT = """You are CollectIQ's Research Agent. Return JSON only.
Use only supplied prospect facts and public-signal text. Do not invent revenue, headcount,
software, contacts, customer counts, pain, or buying intent. Clearly distinguish evidence from inference.
CollectIQ ICP: B2B businesses, especially roughly $500k-$20m revenue when evidence exists,
with AR/collections pain and accounting-software + Excel/email-heavy workflows.
Required JSON: {"icp_score":0,"confidence":"low|medium|high","evidence":[],"inferences":[],
"pain_signals":[],"likely_ar_problem":"","decision_maker_profile":"","qualification":"qualified|watch|reject",
"reason":"","research_gaps":[]}.
Score 0-100. Never infer company size from job title alone.
"""

OUTREACH_PROMPT = """You are CollectIQ's Outreach Agent. Return JSON only.
Create concise, evidence-based B2B outreach for the Free AR Recovery Audit.
Never claim the company definitely has a problem; phrase inferred pain as a hypothesis based on supplied signals.
Do not use fake familiarity or fabricated metrics. No legal threats, urgency manipulation or guaranteed recovery claims.
Required JSON: {"subject":"","email":"","linkedin_note":"","personalization_basis":[],
"cta":"","requires_approval":true,"risk_tier":"amber"}.
Offer: Free AR Recovery Audit -> optional $250 Recovery Sprint. Keep email under 130 words.
"""


def research_prospect(prospect: dict[str, Any], provider: LLMProvider | None = None) -> dict[str, Any]:
    provider = provider or LLMProvider()
    safe = {k: prospect.get(k) for k in (
        "company_name","company_domain","company_website","job_title","job_location","posted_at",
        "source","source_url","prospect_score","signals","fit_reason","contact_position","raw_signal"
    )}
    result = provider.json_completion(system_prompt=RESEARCH_PROMPT,user_payload={"prospect_facts":safe},temperature=0.0,max_tokens=1400)
    data=result["data"]
    try: data["icp_score"]=max(0,min(100,int(data.get("icp_score",0))))
    except Exception: data["icp_score"]=0
    data["model_run"]=result["run"]
    return data


def draft_outreach(prospect: dict[str, Any], research: dict[str, Any], provider: LLMProvider | None = None) -> dict[str, Any]:
    provider = provider or LLMProvider()
    result=provider.json_completion(system_prompt=OUTREACH_PROMPT,user_payload={"prospect":prospect,"research":research},temperature=0.2,max_tokens=1100)
    data=result["data"]
    data["requires_approval"]=True
    data["risk_tier"]="amber"
    data["model_run"]=result["run"]
    return data
