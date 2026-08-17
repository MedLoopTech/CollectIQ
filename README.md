# CollectIQ — AI AR Recovery Analyst

CollectIQ is an **AI AR Recovery Analyst** for B2B businesses still managing collections through accounting software, Excel, and email.

The commercial wedge is:

**Free AR Recovery Audit → $250 Recovery Sprint → $300–$500/month Managed AR Intelligence → optional self-serve SaaS later**

The product is intentionally service-first. Do not wait for every ERP integration, payment-matching edge case, or customer portal feature before selling.

## Current system

- Public website + secure AR audit intake
- deterministic AR Audit Engine
- AI Audit Agent interpretation layer
- human-review / approval queue
- report renderer
- Recovery Sprint Command Center
- promise, dispute, action and collection tracking
- weekly Sprint refresh + CFO Brief generation
- Manager Agent control plane
- Apify-based lead-signal collection
- Supabase state + n8n orchestration

## Positioning

CollectIQ should answer:

- Which receivables should we work first?
- Which payment promises are due or broken?
- Which balances are blocked by disputes or missing documents?
- Which accounts need management attention?
- What changed in recovery this week?
- What should finance do next?

It should **not** be positioned as another AR dashboard or a generic automated reminder tool.

## Autonomy

### Green — autonomous

- prospect research and scoring
- enrichment
- file cleaning
- deterministic audit calculations
- internal recovery analysis
- promise / blocker monitoring
- internal reporting
- CFO brief generation

### Amber — approval required during pilot

- outbound prospect messages
- customer-facing collection communications
- unusual audit conclusions
- pricing exceptions
- escalation messages

### Red — founder controlled

- contracts
- refunds
- legal / compliance issues
- major disputes
- unclear financial claims
- sensitive escalation

## Architecture

```text
Scout / Research signals
        ↓
Prospect state in Supabase
        ↓
Outreach approval
        ↓
Free AR Recovery Audit
        ↓
Deterministic Audit Engine
        ↓
AI Audit Agent interpretation
        ↓
Human review / approval
        ↓
$250 Recovery Sprint
        ↓
Actions + Promises + Disputes + Collections
        ↓
Weekly CFO Recovery Brief
        ↓
$300–$500/month Managed AR Intelligence
```

## Key modules

- `01_landing_intake/` — website + audit intake
- `02_audit_engine/` — deterministic AR engine
- `03_report_renderer/` — client audit report
- `04_reviewer_dashboard/` — review / approval UI
- `05_n8n_e2e_audit/` — audit workflow
- `06_leadgen_apify/` — hiring-signal prospect collector
- `07_recovery_sprint/` — paid Recovery Sprint operating layer
- `08_agent_foundation/` — agent jobs, approvals, exceptions, model abstraction, Audit Agent and Manager Agent

## Immediate commercial experiment

Target:

```text
100 targeted prospects
→ 20–30 high-quality outreach messages/day
→ 10 free audits
→ 3 serious conversations
→ 1 paid $250 Recovery Sprint
```

The critical milestone is **first payment from a stranger**.

## Intentional limitations

Do not overstate current capabilities:

- payment matching / automatic invoice allocation is still incomplete
- customer-facing collection messages remain approval-controlled during the pilot
- legal / contractual actions are never delegated to AI
- customer portal / full SaaS workflow is not a launch dependency
- deterministic finance calculations remain the source of truth; LLMs interpret and draft, they do not invent balances

## Deployment

Existing deployment notes remain within each module README. For the newest agent layer, apply the SQL migrations under `08_agent_foundation/`, deploy the agent service, configure an OpenAI-compatible provider such as DeepSeek, then import the n8n Audit Agent and Manager Agent workflows.
