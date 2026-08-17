"""CollectIQ Audit Agent — AI AR Recovery Analyst layer.

Consumes deterministic Audit Engine JSON. It does not modify core financial calculations.
Customer-facing drafts and unusual conclusions are Amber and must enter the approval queue.
"""
from __future__ import annotations

from typing import Any

from llm_provider import LLMProvider


SYSTEM_PROMPT = """You are CollectIQ's AI AR Recovery Analyst.
Return JSON only. Use only the supplied deterministic audit facts.
Never invent balances, dates, payment promises, disputes, customer history, recovery outcomes or legal conclusions.
If the supplied evidence is insufficient, say so explicitly.

Your job is interpretation and action design, not accounting calculation.
Customer-facing messages are drafts only and require approval.
Legal disputes, unclear financial claims, sensitive escalation and unusual conclusions must be flagged for founder review.

Required JSON shape:
{
  "executive_recovery_view": "short factual interpretation",
  "recovery_opportunity": {
    "amount": 0,
    "basis": "must point to a supplied deterministic amount such as priority_pool; do not invent a new balance",
    "confidence": "low|medium|high",
    "assumptions": ["..."]
  },
  "priority_accounts": [
    {
      "customer":"...",
      "invoice_number":"...",
      "outstanding":0,
      "priority_score":0,
      "recovery_view":"...",
      "recommended_action":"...",
      "draft_follow_up":"...",
      "requires_approval":true,
      "approval_reason":"customer-facing message"
    }
  ],
  "blocker_analysis": [{"blocker":"...","amount":0,"interpretation":"...","next_action":"..."}],
  "promise_analysis": {"missed_promise_value":0,"interpretation":"..."},
  "exceptions": [{"severity":"high|critical","category":"financial_claim|legal|sensitive_escalation|uncertainty","title":"...","reason":"..."}],
  "internal_next_actions": ["..."]
}

For recovery_opportunity.amount, default to the supplied priority_pool. Describe it as an opportunity pool, not guaranteed recoverable cash. Do not apply invented recovery percentages.
"""


def interpret_audit(audit: dict[str, Any], provider: LLMProvider | None = None) -> dict[str, Any]:
    if audit.get("status") == "validation_failed":
        return {
            "status": "blocked",
            "reason": "Audit validation failed; AI interpretation is not permitted until the data issue is resolved.",
            "exceptions": [{
                "severity": "high",
                "category": "data_quality",
                "title": "Audit validation failed",
                "reason": "Resolve deterministic validation errors before recovery interpretation.",
            }],
        }

    provider = provider or LLMProvider()
    facts = {
        "as_of": audit.get("as_of"),
        "metrics": audit.get("metrics", {}),
        "top_opportunities": audit.get("top_opportunities", []),
        "blockers": audit.get("blockers", []),
        "ageing": audit.get("ageing", {}),
        "validation": audit.get("validation", {}),
    }
    result = provider.json_completion(
        system_prompt=SYSTEM_PROMPT,
        user_payload={"deterministic_audit_facts": facts},
        temperature=0.0,
        max_tokens=2600,
    )
    data = result["data"]

    # Guardrail: opportunity amount can never exceed the deterministic priority pool.
    priority_pool = float(audit.get("metrics", {}).get("priority_pool") or 0)
    recovery = data.setdefault("recovery_opportunity", {})
    try:
        proposed = float(recovery.get("amount") or 0)
    except (TypeError, ValueError):
        proposed = 0
    recovery["amount"] = min(max(proposed, 0), priority_pool)
    recovery["deterministic_ceiling"] = priority_pool
    recovery["not_a_guarantee"] = True

    # Every customer-facing follow-up stays Amber initially.
    for row in data.get("priority_accounts", []):
        if row.get("draft_follow_up"):
            row["requires_approval"] = True
            row["approval_reason"] = row.get("approval_reason") or "Customer-facing collection communication is Amber during pilot."

    data["model_run"] = result["run"]
    return data
