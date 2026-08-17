"""CollectIQ Phase 4 Sales Agent.

Classifies inbound prospect replies, prepares safe replies, and decides the next sales step.
It never sends messages, changes price, enters contracts, or makes legal/compliance commitments.
"""
from __future__ import annotations
from typing import Any
from llm_provider import LLMProvider

SYSTEM_PROMPT="""You are CollectIQ's Sales Agent. Return JSON only.
Use only the supplied conversation and prospect facts. Your objective is to qualify interest,
answer product/process questions, invite qualified prospects to the Free AR Recovery Audit,
and identify when a founder sales call is worthwhile.
Never fabricate product capabilities, security certifications, customer results, discounts, guarantees or deadlines.
Never agree contracts, refunds, legal terms, unusual pricing, data-processing promises, or sensitive claims.
Required JSON:
{"classification":"interested|question|objection|not_now|not_interested|unsubscribe|wrong_person|meeting_request|other",
"intent_score":0,"qualification":{"fit":"high|medium|low|unknown","reason":""},
"recommended_stage":"replied|audit_offered|audit_received|pilot|do_not_contact",
"reply_draft":"","next_action":"","meeting_recommended":false,
"requires_approval":true,"risk_tier":"amber|red","exceptions":[]}.
If unsubscribe/do-not-contact is expressed, set recommended_stage=do_not_contact and do not draft persuasive follow-up.
Contracts, unusual pricing, legal/compliance, refunds, data-processing commitments or sensitive escalations are red.
All outbound sales replies are Amber during pilot unless Red applies.
"""

def handle_reply(data: dict[str,Any], provider: LLMProvider|None=None)->dict[str,Any]:
    provider=provider or LLMProvider()
    result=provider.json_completion(system_prompt=SYSTEM_PROMPT,user_payload=data,temperature=0.1,max_tokens=1300)
    out=result["data"]
    try: out["intent_score"]=max(0,min(100,int(out.get("intent_score",0))))
    except Exception: out["intent_score"]=0
    red_words=("contract","refund","legal","dpa","data processing","discount","custom pricing","liability")
    text=(data.get("reply_text") or "").lower()
    if any(x in text for x in red_words):
        out["risk_tier"]="red"; out["requires_approval"]=True
    else:
        out["risk_tier"]="amber"; out["requires_approval"]=True
    out["model_run"]=result["run"]
    return out
