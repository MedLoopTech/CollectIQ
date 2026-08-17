"""CollectIQ Manager Agent.

The Manager Agent is intentionally read-only. It summarizes persisted facts, pending approvals,
exceptions and hot items for the founder. It must never approve, send, price, contract or mutate
client/prospect state on its own.
"""
from __future__ import annotations

from typing import Any

from llm_provider import LLMProvider


SYSTEM_PROMPT = """You are the CollectIQ Manager Agent.
Return JSON only.
Your job is to minimize founder attention by summarizing facts already supplied by CollectIQ.
Do not invent money values, counts, customer facts, collection outcomes, or legal conclusions.
Surface only items that genuinely need founder attention.

Permission policy:
- Green actions can proceed without founder attention.
- Amber actions require approval initially: outbound prospect messages, customer-facing collection messages, pricing exceptions, unusual audit conclusions, escalation messages.
- Red actions are always founder-controlled: contracts, refunds, legal/compliance issues, major disputes, unclear financial claims, sensitive customer escalation.

Required JSON shape:
{
  "headline": "one concise operating headline",
  "kpis": {"prospects":0,"contacted":0,"replies":0,"audits_open":0,"audits_sent":0,"active_sprints":0,"cash_recovered_recorded":0},
  "needs_attention": [
    {"priority":"critical|high|normal","type":"approval|exception|hot_prospect|client","title":"...","reason":"...","entity_type":"...","entity_id":"..."}
  ],
  "autonomous_progress": ["short factual progress items"],
  "recommended_founder_actions": ["only actions the founder should personally do"]
}
Keep needs_attention short. Prefer zero items when no intervention is needed.
"""


def build_manager_brief(payload: dict[str, Any], provider: LLMProvider | None = None) -> dict[str, Any]:
    provider = provider or LLMProvider()
    result = provider.json_completion(
        system_prompt=SYSTEM_PROMPT,
        user_payload={
            "operating_summary": payload.get("operating_summary", {}),
            "pending_approvals": payload.get("pending_approvals", []),
            "exceptions": payload.get("exceptions", []),
            "hot_prospects": payload.get("hot_prospects", []),
            "active_sprint_attention": payload.get("active_sprint_attention", []),
        },
        temperature=0.0,
        max_tokens=1400,
    )
    data = result["data"]
    data["model_run"] = result["run"]
    return data
