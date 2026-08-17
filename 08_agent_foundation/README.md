# CollectIQ Agentic Operating Model v0.4

This module layers agents around the existing deterministic CollectIQ application. It does not replace finance calculations, storage, audit intake or Recovery Sprint state.

## Phase status

### Phase 1 — Foundation
Implemented:
- durable `agent_jobs`
- `agent_activity_log`
- Amber/Red `approval_queue`
- `agent_exceptions`
- provider/model telemetry
- provider-agnostic OpenAI-compatible adapter
- DeepSeek support
- read-only Manager Agent

### Phase 2 — Audit Agent
Implemented:
- deterministic audit JSON remains authoritative
- AI recovery interpretation
- priority-account explanation
- blocker and promise interpretation
- recommended actions
- customer follow-up drafts
- validation guardrail
- recovery opportunity capped at deterministic `priority_pool`
- customer-facing drafts routed to Amber approval

Endpoint: `POST /audit/interpret`

### Phase 3 — Scout + Research + Outreach
Scout uses the existing Apify multi-source hiring-signal collector in `06_leadgen_apify`.
Research and Outreach are now agent layers on top of `lead_prospects`.

Implemented:
- `/research/prospect`
- `/outreach/draft`
- evidence vs inference separation
- ICP scoring
- pain-signal interpretation
- decision-maker profile hypothesis
- concise personalized email + LinkedIn draft
- all outbound outreach routed to Amber approval
- `n8n_phase3_prospecting_v01.json`

### Phase 4 — Sales Agent
Implemented:
- `/sales/reply`
- inbound reply classification
- intent score
- qualification
- objection/question handling draft
- audit invitation / next-step recommendation
- hot-call recommendation
- unsubscribe/do-not-contact handling
- Red routing for contracts, refunds, legal/compliance, unusual pricing and sensitive commitments
- `n8n_phase4_sales_v01.json`

The workflow is designed to receive inbound email/webhook data from the chosen mail layer. It does not bypass email-provider permissions.

### Phase 5 — Recovery Agent
Implemented:
- `/recovery/run`
- reads persisted Sprint actions/promises/disputes
- Sprint-health interpretation
- broken-promise prioritization
- dispute next actions
- priority recovery actions
- customer follow-up drafts remain Amber
- no invented payment/dispute resolution state
- daily `n8n_phase5_recovery_v01.json`

Deterministic Sprint tables remain authoritative. The agent cannot record a payment or resolve a dispute unless the underlying workflow/state shows it.

### Phase 6 — CFO Agent
Implemented:
- `/cfo/brief`
- factual weekly recovery narrative
- management-attention list
- next-week actions
- risk summary
- client-ready draft
- source metrics preserved
- Friday `n8n_phase6_cfo_v01.json`
- client-facing CFO brief routed to Amber approval

### Phase 7 — Manager Agent
Implemented:
- read-only `/manager/brief`
- scheduled Manager workflow
- expanded factual operating summary
- founder attention queue
- qualified prospects / replies / audits / Sprints / cash / approvals / exceptions
- no approval, sending, pricing, contracting or client-state mutation privileges

## Persistent business state

Apply migrations in this order:

```text
08_agent_foundation/agent_foundation.sql
08_agent_foundation/audit_agent_persistence.sql
08_agent_foundation/agent_business_state.sql
08_agent_foundation/phase7_manager_summary.sql
```

Sprint migrations remain under `07_recovery_sprint` and `supabase/`.

## Service startup

```bash
pip install -r 08_agent_foundation/requirements.txt
cd 08_agent_foundation
uvicorn api:app --host 0.0.0.0 --port 8100
```

## Model configuration

DeepSeek example:

```text
COLLECTIQ_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=
```

Do not hardcode a model name if the deployed account uses another current DeepSeek model. Provider selection is isolated in `llm_provider.py`.

Generic OpenAI-compatible provider:

```text
COLLECTIQ_LLM_PROVIDER=my-provider
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
```

## Autonomy policy

### Green
- prospect research
- enrichment interpretation
- lead scoring
- file cleaning
- deterministic audit calculations
- internal analysis
- recovery prioritization
- internal CFO/Manager summaries

### Amber
- cold outreach
- sales replies
- customer-facing collection follow-ups
- client-facing CFO briefs
- unusual audit conclusions
- escalation messages

### Red
Always founder-controlled:
- contracts
- refunds
- legal/compliance issues
- major disputes
- unclear financial claims
- sensitive customer escalation
- unusual pricing/terms

## n8n workflows

Import as required:

```text
n8n_audit_agent_v01.json
n8n_manager_agent_v01.json
n8n_phase3_prospecting_v01.json
n8n_phase4_sales_v01.json
n8n_phase5_recovery_v01.json
n8n_phase6_cfo_v01.json
```

The existing Apify Scout workflow remains in `06_leadgen_apify`.

## Important production boundary

The agent architecture is implemented, but it still requires deployment credentials and live integrations before it can operate autonomously in production. In particular:
- Apify Actor schemas must be verified against the selected Actors.
- email ingestion/sending must be connected to Gmail, Hostinger Mail, SMTP or another provider.
- n8n workflows must be imported and activated.
- SQL migrations must be applied.
- the agent service must be deployed and configured with a valid LLM provider key.
- approval actions need an operator UI/process before Amber customer messages can be released.

This is intentional. Agent logic can be Green while external side effects remain permission-gated.

## Commercial objective

Optimize the system for:

```text
100 targeted prospects
-> 20–30 quality outreach messages/day
-> 10 Free AR Recovery Audits
-> 3 serious conversations
-> 1 paid $250 Recovery Sprint
```

The key milestone is first payment from a stranger, not feature completeness.
