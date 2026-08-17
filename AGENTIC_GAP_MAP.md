# CollectIQ Agentic Gap Map

This document maps the current repository against the latest Agentic Operating Model.

## Preserve — already working / materially useful

- Landing page + Free AR Audit intake
- Supabase private file storage
- deterministic Audit Engine calculations
- audit review / approval flow
- client-facing audit report renderer
- Apify-based hiring-signal lead generation
- Recovery Sprint data model
- Audit -> Sprint Day-0 conversion
- weekly Sprint refresh, promise ageing, snapshots and draft CFO brief persistence

These remain the financial/operational source of truth. Agents should orchestrate around them, not replace deterministic calculations.

## Partial — keep and extend

### Scout Agent
Current: Apify multi-source job-signal workflow exists.
Missing: unified agent job state, activity logging, source-cost tracking, company watchlists, automatic retry/error state.

### Research Agent
Current: deterministic ICP scoring exists; earlier enrichment logic exists conceptually.
Missing: first-class research job, decision-maker enrichment pipeline, evidence bundle, confidence score and approval policy.

### Outreach Agent
Current: personalized draft generation exists in earlier lead-gen workflow design.
Missing: provider-agnostic LLM service, approval queue, message versioning, policy classification and send-state audit trail.

### Audit Agent
Current: strongest part of the product. Deterministic ageing, validation, priority scoring, AR Health Score, disputes, promises and Sprint seed exist.
Missing: AI recovery narrative, likely-recoverable estimate with explicit assumptions, account-level recovery/risk explanation, ready-to-send follow-up drafts, structured uncertainty routing.

### Recovery Agent
Current: Sprint schema, actions, promises, disputes, collections, weekly refresh and CFO brief facts exist.
Missing: agent task loop that turns state changes into next actions, approval requests, follow-up drafts and exception escalation.

### CFO Agent
Current: factual weekly snapshots and persisted draft CFO briefs exist.
Missing: AI-written management narrative constrained to snapshot facts, approval workflow and delivery policy.

### Sales Agent
Current: not implemented as an agent.
Missing: inbound-reply classification, qualification state, objection handling, follow-up memory, meeting handoff and audit invitation.

### Manager Agent
Current: not implemented.
Missing: one founder-facing brief aggregating pipeline, audits, Sprints, approvals, exceptions and revenue signals.

## Phase 1 foundation gaps

The current repo has workflow-specific states but no shared control plane for autonomous agents. Add:

1. `agent_jobs` — durable job/task state with owner agent, entity, priority, retry/error state and autonomy tier.
2. `agent_activity_log` — immutable record of agent decisions, model/provider, inputs/outputs summary and cost/latency metadata.
3. `approval_queue` — Amber/Red actions requiring explicit human decision.
4. `agent_exceptions` — unresolved operational/financial/compliance exceptions surfaced to the Manager Agent.
5. provider-agnostic OpenAI-compatible LLM adapter with DeepSeek support.
6. Manager Agent API that returns a concise founder brief and never performs consequential writes itself.

## Autonomy policy

### Green — autonomous
Research, enrichment, scoring, file cleaning, deterministic calculations, internal summaries, routine draft generation and CFO draft generation.

### Amber — approval required initially
Outbound prospect messages, customer-facing collection messages, pricing exceptions, unusual audit conclusions and escalation messages.

### Red — founder controlled
Contracts, refunds, legal/compliance issues, major disputes, unclear financial claims and sensitive customer escalation.

## Phase 2 target — Audit Agent

Do not rewrite the Audit Engine. Extend its structured result with a separate agent interpretation layer that consumes deterministic audit JSON and returns:

- likely recoverable amount as an estimate with assumptions/confidence,
- top-priority account explanations,
- dispute/blocker interpretation,
- broken-promise interpretation,
- recommended actions,
- account-level risk/recovery score explanations,
- customer follow-up drafts,
- `requires_approval` flags for unusual or consequential conclusions.

Core financial values remain deterministic and must never be invented by the model.

## Commercial constraint

Engineering priority is governed by the shortest path to:

100 targeted prospects -> 10 audits -> 3 serious conversations -> 1 paid Recovery Sprint.

Do not prioritize dashboard redesign, broad ERP integrations, autonomous payments, a large CRM or a sophisticated client portal before this loop produces revenue.
