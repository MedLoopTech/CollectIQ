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

## Setup

1. Run `supabase/recovery_sprint_v01.sql` in the existing CollectIQ Supabase project.
2. Protect this page with the same Supabase Auth approach used by the reviewer dashboard.
3. Replace `YOUR_SUPABASE_URL` and `YOUR_SUPABASE_ANON_KEY` in `index.html`.
4. Open `07_recovery_sprint/index.html` through your internal deployment.

Do not expose the service-role key in this page.

## Current MVP boundary

This is an internal delivery tool, not a customer portal.

The first paid Sprints can still use manual invoices and human-reviewed customer communication. The goal of v0.1 is to capture the operational state of the Sprint in CollectIQ instead of scattered spreadsheets.

## Data flow

```text
Approved AR Audit
  -> Recovery Sprint
  -> baseline portfolio
  -> accounts + invoices
  -> actions
  -> promises / disputes
  -> collections
  -> weekly snapshots
  -> CFO Brief
  -> final Sprint outcome
```

## Important next integration

The UI can create an empty Sprint today. The next engineering step is the Audit-to-Sprint conversion workflow that takes an approved audit's structured JSON and seeds:

- `recovery_sprints`
- `sprint_accounts`
- `sprint_invoices`
- initial `sprint_actions`

That should become the standard way to start a paid engagement, so the Free Audit becomes Day 0 of the Sprint rather than a disconnected process.

## CFO Brief

The current browser generator only summarizes persisted Sprint records. It does not invent figures and does not use an LLM.

A later server-side workflow should persist weekly snapshots and a reviewed `sprint_cfo_briefs` record before client delivery.

## Security

The SQL uses a broad `authenticated` internal policy for the pilot. This is appropriate only while CollectIQ is operated by a small internal team.

Before external/customer accounts are introduced, replace this with organization-scoped roles and tenant-aware RLS.
