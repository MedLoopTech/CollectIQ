# CollectIQ Recovery Sprint Command Center v0.1

This module turns the paid 30-Day Recovery Sprint from marketing copy into a software-assisted internal delivery workflow.

## Included

- Sprint/client record and baseline
- account and invoice portfolio model
- daily action queue
- payment promise tracking
- dispute/blocker tracking
- collection ledger
- activity model
- weekly snapshot model
- CFO Brief persistence model
- browser-based internal Command Center
- factual current-state CFO Brief draft generator
- Audit -> Sprint conversion
- deterministic weekly operating engine
- scheduled n8n Sprint refresh workflow

## Setup

Run these SQL files in order:

1. `supabase/recovery_sprint_v01.sql`
2. `07_recovery_sprint/audit_to_sprint.sql`
3. `07_recovery_sprint/weekly_engine.sql`

Then:

4. Protect the Command Center with the same Supabase Auth approach used by the reviewer dashboard.
5. Replace `YOUR_SUPABASE_URL` and `YOUR_SUPABASE_ANON_KEY` in `index.html`.
6. Import `n8n_weekly_sprint_refresh_v01.json` into n8n and configure `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.

Do not expose the service-role key in the browser.

## Audit -> Sprint

The Audit Engine API now returns a complete `sprint_seed` for valid audits. This includes all open accounts and invoices, not only the top opportunities.

After an audit is reviewed (`audit_ready` or `sent`), call:

```sql
select public.start_recovery_sprint_from_audit('<audit-lead-uuid>');
```

The transaction creates:

- active Sprint + 30-day window
- Day-0 baseline metrics
- complete account portfolio
- complete invoice portfolio
- known payment promises
- known disputes/blockers
- initial action queue for overdue invoices scoring 50+
- Week-0 snapshot

The function is idempotent per audit lead.

Audits generated before Audit Engine API v0.2 have no `sprint_seed`; rerun those audits before conversion.

## Weekly operating engine

Call:

```sql
select public.refresh_recovery_sprint('<sprint-uuid>', current_date);
```

The deterministic refresh performs:

1. marks pending payment promises as `missed` after their promise date passes,
2. refreshes invoice days-overdue and ageing buckets,
3. refreshes account balances/status from the Sprint invoice ledger,
4. derives the current Sprint week (Day 0-6 = Week 0; Day 7-13 = Week 1; capped at Week 4),
5. persists/upserts the current weekly snapshot,
6. generates/upserts a factual draft CFO Brief for Weeks 1-4.

The CFO brief stores:

- executive summary
- top management actions
- top accounts
- open blockers
- link to the factual weekly snapshot

No LLM is required for these financial calculations.

## n8n automation

`n8n_weekly_sprint_refresh_v01.json` runs daily at 08:00 and calls `refresh_recovery_sprint` for every active Sprint. The SQL layer determines whether the Sprint is still Week 0 or which weekly brief should be updated.

Keep CFO Brief delivery human-reviewed during the pilot.

## Current MVP boundary

This is an internal delivery tool, not a customer portal.

The first paid Sprints can still use manual invoices and human-reviewed customer communication. The goal is to capture the operational state of the Sprint in CollectIQ instead of scattered spreadsheets.

## Known limitation: payment allocation

`sprint_collections` currently records recovered cash, but account-level payments are not automatically allocated across invoice balances. Therefore:

- `cash_collected_*` metrics are authoritative from the collection ledger,
- invoice-level outstanding and ageing remain authoritative only after invoice balances are updated or the portfolio is refreshed from a new AR export.

Do not present invoice-level post-payment balances as automatically reconciled yet. Payment matching/allocation is the next accounting-control layer.

## Security

The SQL uses a broad `authenticated` internal policy for the pilot. This is appropriate only while CollectIQ is operated by a small internal team.

Before external/customer accounts are introduced, replace this with organization-scoped roles and tenant-aware RLS.
