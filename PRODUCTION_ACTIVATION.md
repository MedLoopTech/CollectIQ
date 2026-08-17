# CollectIQ Production Activation — v0.4 Agentic AR Recovery

## Code readiness

GitHub Actions CI now gates:

- Audit Engine Python compile
- Northstar golden regression (`python test_golden.py`)
- Agent Service Python compile across Phases 1–7
- Agent Service `/health` smoke check
- Docker Compose configuration validation

Do not deploy a commit unless all CI jobs are green.

## Services

Docker Compose now includes:

- `collectiq-audit-engine` — internal port 8000
- `collectiq-agent-service` — internal port 8100

Both are bound to `127.0.0.1` on the host and share `root_default` with n8n.

## DeepSeek runtime

Current supported configuration:

```env
COLLECTIQ_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=<secret>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
```

Keep the API key server-side only.

## Activation sequence

### 1. Merge reviewed code

Merge only after CI is green.

### 2. VPS update

From the existing CollectIQ deployment directory:

```bash
git pull origin master
cp .env.example .env   # only on first setup; otherwise preserve existing .env
# edit .env and add real secrets
docker compose build --pull
docker compose up -d
```

Never commit `.env`.

### 3. Supabase migrations

Apply in order:

1. `supabase/recovery_sprint_v01.sql`
2. `07_recovery_sprint/audit_to_sprint.sql`
3. `07_recovery_sprint/weekly_cycle.sql`
4. `08_agent_foundation/agent_foundation.sql`
5. `08_agent_foundation/audit_agent_persistence.sql`
6. `08_agent_foundation/agent_business_state.sql`
7. `08_agent_foundation/manager_summary_v02.sql`

Do not expose the service-role key to browser code.

### 4. Service smoke test

```bash
bash scripts/smoke_test.sh
```

This checks both health endpoints and runs Northstar through the live Audit API, including `sprint_seed` generation.

### 5. n8n environment

Set server-side:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
COLLECTIQ_AUDIT_ENGINE_URL=http://collectiq-audit-engine:8000
COLLECTIQ_AGENT_SERVICE_URL=http://collectiq-agent-service:8100
APIFY_TOKEN
HUNTER_API_KEY (if used)
```

### 6. Import workflows

Import and validate manually before activation:

- `05_n8n_e2e_audit/collectiq_e2e_audit_v01.json`
- `06_leadgen_apify/collectiq_apify_multisource_leadgen_v02.json`
- `08_agent_foundation/n8n_audit_agent_v01.json`
- `08_agent_foundation/n8n_phase3_prospecting_v01.json`
- `08_agent_foundation/n8n_phase4_sales_reply_v01.json`
- `08_agent_foundation/n8n_phase5_recovery_v01.json`
- `08_agent_foundation/n8n_phase6_cfo_v01.json`
- `08_agent_foundation/n8n_manager_agent_v01.json`
- `07_recovery_sprint/n8n_weekly_sprint_cycle_v01.json`

### 7. Apify validation

Run the chosen LinkedIn and Indeed Actors manually once and confirm their current input/output schema before enabling schedules. Actor marketplace schemas are external dependencies and must not be assumed stable.

### 8. Email integration

Connect an authenticated mailbox to the Phase 4 inbound-reply workflow and to approved outbound sends.

Rules:

- cold outreach is Amber during pilot
- sales replies are Amber unless classified Red
- unsubscribe is applied immediately
- customer collection messages remain Amber
- contracts, refunds, legal/compliance, unusual pricing and sensitive escalations remain Red

### 9. Approval release

Approval must be more than a database status. The send workflow must fetch the approval row and verify `status='approved'` immediately before sending.

### 10. End-to-end launch test

Run one controlled prospect through:

```text
Scout signal
-> Research Agent
-> Outreach draft
-> Amber approval
-> approved send
-> inbound reply
-> Sales Agent
-> Free AR Recovery Audit
-> deterministic audit
-> Audit Agent
-> reviewed report
-> $250 Recovery Sprint
-> Day-0 conversion
-> Recovery Agent
-> weekly CFO Agent
-> Manager Agent CEO brief
```

## Live threshold

Do not call CollectIQ autonomous/live until:

- all CI gates pass
- SQL migrations are applied
- both service health checks pass
- Northstar live API test passes
- at least one n8n test execution succeeds for every active workflow
- outbound send is approval-gated server-side
- inbound unsubscribe handling is verified
- one full sandbox prospect/audit/Sprint flow completes

## Known limitation retained intentionally

Payment allocation/matching against individual invoice balances is not yet automated. `sprint_collections` records recovered cash, but invoice balance refresh should come from explicit allocation or a refreshed AR export. Do not imply otherwise in CFO reports.
