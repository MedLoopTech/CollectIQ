# CollectIQ Agent Foundation v0.1

This module is the control plane for the Agentic Operating Model. It layers agents around existing CollectIQ functionality rather than rebuilding deterministic finance workflows.

## What Phase 1 adds

- `agent_jobs` durable task/job state
- `agent_activity_log` decision/model audit trail
- `approval_queue` for Amber and Red actions
- `agent_exceptions` for unresolved founder attention
- `agent_model_runs` provider/model telemetry
- `manager_agent_operating_summary` factual manager input view
- provider-agnostic OpenAI-compatible LLM adapter
- DeepSeek support
- read-only Manager Agent

Run:

```bash
psql ... -f 08_agent_foundation/agent_foundation.sql
pip install -r 08_agent_foundation/requirements.txt
cd 08_agent_foundation
uvicorn api:app --host 0.0.0.0 --port 8100
```

## Model configuration

Default provider is DeepSeek:

```text
COLLECTIQ_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

Generic OpenAI-compatible fallback:

```text
COLLECTIQ_LLM_PROVIDER=my-provider
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

Agent business logic does not import a vendor-specific client. All provider selection is isolated in `llm_provider.py`.

## Manager Agent

Endpoint:

```text
POST /manager/brief
{"data": { ... factual operating inputs ... }}
```

The Manager Agent is read-only. It may summarize and recommend founder actions, but it cannot approve messages, send communications, change pricing, sign contracts, resolve legal issues or mutate client state.

Its intended output is the single founder-facing operating brief:

```text
126 prospects found
31 qualified
24 contacted
7 replies
3 interested
2 audits received
$184k overdue AR analyzed
$61k priority recovery opportunity

Needs your attention: 2 items
```

The actual values must come from persisted CollectIQ state, not model inference.

## Phase 2 — Audit Agent

Endpoint:

```text
POST /audit/interpret
{"data": <existing deterministic audit JSON>}
```

The Audit Agent adds:

- executive recovery interpretation
- recovery-opportunity explanation
- account-level recovery views
- recommended actions
- blocker interpretation
- broken-promise interpretation
- customer follow-up drafts
- structured exception flags

Guardrails:

- financial calculations remain in `02_audit_engine`
- the model cannot raise the recovery opportunity above deterministic `priority_pool`
- the opportunity is explicitly not a guarantee
- validation failures block AI interpretation
- every customer-facing collection draft is Amber / approval-required
- legal, sensitive and unclear-financial situations must be escalated

## Next wiring

1. Import `agent_foundation.sql`.
2. Deploy this service next to the Audit Engine.
3. After a deterministic audit succeeds, n8n creates an `audit` agent job and calls `/audit/interpret`.
4. Save the interpretation in the job output/activity log.
5. Create `approval_queue` rows for draft customer-facing actions.
6. Run Manager Agent on a schedule and on high-severity exceptions.

Do not auto-send outbound communication during this phase.
