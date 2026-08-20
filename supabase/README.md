# Supabase — Database Layer

This directory holds two generations of schema, side by side during the
transition from CollectIQ (single-tenant AR-audit pilot) to **Aimfold**
(multi-tenant, self-improving Opportunity Intelligence engine — see
`AIMFOLD_MASTER_GOAL.md`, the product source of truth).

## `collectiq_full_schema.sql` (legacy)

The original CollectIQ pilot schema (`audit_leads`, `audit_events`,
`lead_prospects`), hand-run in the Supabase SQL editor. No migration
tracking — this file is a point-in-time concatenation of the per-module
`*.sql` files under `01_landing_intake/`, `04_reviewer_dashboard/` and
`06_leadgen_apify/`. It is **not** re-run by anything in `migrations/`.
PR3 converted CollectIQ's *configuration* (search terms, scoring
weights) into Aim/AimVersion data; `lead_prospects` itself still holds
the actual signal rows and `06_leadgen_apify`'s workflow still writes to
it — moving that data (and the workflow) onto `entities`/`signals`
(added schema-only in PR5) is still open, expected around PR6/PR7 once
there's a reason (evidence extraction, Stage-2 scoring) to actually
populate the new tables.

## `migrations/` (Aimfold core, new)

Proper, ordered, idempotent Supabase CLI-style migrations
(`<14-digit-timestamp>_description.sql`), starting with Aimfold's own
recommended PR sequence:

| File | PR | Adds |
|---|---|---|
| `20260819120000_core_multi_tenant_schema.sql` | PR1 | `tenants`, `tenant_members`, `sources` (connector catalog), `audit_log`, shared `set_updated_at()` trigger, and the `is_tenant_member()` / `tenant_role()` RLS helper functions every later table's RLS policies build on. |
| `20260819120100_aim_schema.sql` | PR2 | `aims`, `aim_versions` (immutable, one `is_current` per Aim), `aim_signal_hypotheses`. |
| `20260819120150_aim_signal_hypotheses_connector_params.sql` | PR3 | Additive: `connector_params jsonb` on `aim_signal_hypotheses`, needed to drive an actual source connector (keyword/location) from a hypothesis row. |
| `20260819120200_seed_collectiq_aim.sql` | PR3 | Seeds the CollectIQ tenant, its first Aim ("CollectIQ AR Signal Discovery"), and one approved+current AimVersion whose `compiled_spec`/hypotheses are a 1:1 transcription of the search list and scoring rules that were hardcoded in `06_leadgen_apify/collectiq_apify_multisource_leadgen_v02.json`. Fixed (non-random) UUIDs — see the file header. |
| `20260819120300_entity_signal_schema.sql` | PR5 | `entities`, `entity_relationships`, `entity_memory`, `signals`, `signal_entities`. Schema only — `06_leadgen_apify`'s workflow still writes to `lead_prospects`, not here; see the file header for why. |
| `20260819120400_signals_evidence_versioning.sql` | PR6 | Additive: `evidence_model`, `evidence_prompt_version` on `signals`, populated when `aimfold_core/evidence/`'s Stage-2 evaluator runs for a signal. |
| `20260819120500_opportunity_schema.sql` | PR8 | `opportunities`, `opportunity_signals`, `opportunity_entities`, `opportunity_lifecycle_events`. Schema only, same as PR5 — see `aimfold_core/opportunity/` for the clustering/lifecycle logic that would populate these. |
| `20260819120600_opportunities_action_rationale.sql` | PR9 | Additive: `recommended_action_rationale` on `opportunities`, populated by `aimfold_core/action/`'s deterministic recommender alongside PR8's `recommended_action` column. |
| `20260819120700_opportunity_inbox_actions.sql` | PR10 | The first authenticated-writable path in the whole schema: `authenticated` is limited to writing only `opportunities.lifecycle_state` (an explicit `REVOKE UPDATE` followed by a column-scoped `GRANT` — see below for why the revoke is load-bearing, not decorative), plus RLS `WITH CHECK` restricting the value to `held`/`rejected`/`actioned`, and a matching `opportunity_lifecycle_events` insert policy. Backs `aimfold_core/inbox/`'s Approve/Hold/Reject buttons. |
| `20260819120800_feedback_outcomes_schema.sql` | PR11 | `feedback` (structured human decision + rejection taxonomy + a Learning Loop prediction snapshot, `feedback_rejection_reason_required` CHECK constraint) and `outcomes` (downstream commercial results). Both append-only-by-policy (insert-only RLS, `outcomes` additionally allows updating your own rows). |
| `20260819120900_aim_memory_schema.sql` | PR12 | `aim_memory` — versioned aggregate snapshots (accepted/rejected patterns, learned exclusions, source effectiveness, ...) computed from accumulated `feedback`. Select-only for `authenticated`; `entity_memory` (PR5) already existed as a table but nothing wrote to it until `aimfold_core/memory/entity_memory.py` in this PR. |
| `20260819121000_learning_proposals_schema.sql` | PR15 | `learning_proposals` (section 22's Observe→Measure→Propose→Test→Promote, with a `learning_proposals_exactly_one_candidate` CHECK ensuring a proposal carries exactly one of `proposed_compiled_spec`/`proposed_scoring_weights`) and `scoring_versions` (closing a gap PR7 deliberately deferred — persisted, promotable `ScoringWeights` per Aim). Same `REVOKE`-then-column-`GRANT` pattern as PR10 for the human decide-this-proposal step (`status`/`decided_by`/`decided_at` only). |
| `20260819121100_seed_career_discovery_aim.sql` | PR16 | Seeds Aim #2 of section 41's Horizontal Validation (a new tenant + Aim + AimVersion whose `compiled_spec` is the real, unedited live output of `aimfold_core/aim_compiler` — see the file header). No schema changes — pure data, same shape as PR3's CollectIQ seed. |
| `20260819121200_sources_planned_status.sql` | PR17 | Additive: adds `'planned'` to `sources.status`'s CHECK constraint (previously `active`/`disabled`/`deprecated`) — needed to honestly register a connector that's in the catalog but has no working implementation yet (see next row), rather than mislabeling it `'disabled'`. |
| `20260819121300_seed_funding_discovery_aim.sql` | PR17 | Seeds Aim #3 of section 41's Horizontal Validation (Funding/Grant Discovery — the section requirement's minimum of three materially different Aims). Same shape as PR16's seed, plus one new `'planned'`-status source connector (`grants_database_web_search`) and three `is_experimental=true` signal hypotheses against it, since no real grant-database scraper exists in this repo. |

`06_leadgen_apify/collectiq_apify_multisource_leadgen_v03.json` is the
workflow that now reads this seed data instead of hardcoding it — see
`06_leadgen_apify/README.md` for what changed and why.

PR7 (explainable scoring engine) added no migration — it's a pure
deterministic function over PR6's output with nowhere to persist to yet
(see `aimfold_core/README.md`). Later PRs (model/workflow run tracking —
PR18, etc.) will add further files here in the same style.

### Applying migrations

Preferred (once a Supabase project is linked locally):

```bash
supabase db push
```

Until the project is linked, paste each file into the Supabase SQL
editor **in filename order** — every statement is idempotent
(`create table if not exists`, `create or replace function`,
`drop policy/trigger if exists` before `create`), so re-running a file
that has already been applied is safe. On a real Supabase project the
`REVOKE`/`GRANT` pairs in PR10 and PR15 work correctly with no extra
setup — Supabase already configures `authenticated`/`anon`'s default
privileges platform-side, which is exactly the baseline those migrations
assume and narrow.

### Conventions established here (carry forward into later PRs)

- Every tenant-scoped table has a `tenant_id uuid not null references
  public.tenants(id) on delete cascade`, RLS enabled, and a `select`
  policy gated by `public.is_tenant_member(tenant_id)`.
- Tables holding decision history that must stay reproducible (`aims`,
  `aim_versions`) have **no delete policy** for `authenticated` — use a
  `status` column (`archived`, `superseded`, ...) instead of deleting rows.
- Writes that should only happen through a backend/agent (e.g.
  `aim_versions`, `aim_signal_hypotheses`, `sources`) get a `select`
  policy only; the service-role key bypasses RLS for those writes, same
  pattern the existing n8n workflows already use against `audit_leads`.
- `updated_at` is kept current via the shared `public.set_updated_at()`
  trigger — attach it to any new table with an `updated_at` column
  rather than re-defining the trigger function.
- Dedup keys (`entities.fingerprint`, `signals.fingerprint`) are unique
  **per tenant** (`unique (tenant_id, fingerprint)`), not globally unique
  — `lead_prospects.fingerprint` is globally unique today, which would
  incorrectly collide across tenants once more than one exists.
- Tables that back a single obvious "main" relationship
  (`signals.entity_id`) still get a join table (`signal_entities`) for
  the genuinely multi-entity case, rather than forcing every Aim into a
  single-entity shape.
- **A column-scoped `GRANT` must be preceded by `REVOKE UPDATE ON
  <table> FROM authenticated`** whenever an RLS `UPDATE` policy also
  exists for that role on that table (PR10, PR15). `GRANT UPDATE
  (col)` only *adds* a privilege — it never narrows a broader one
  already in effect, and Supabase's own default privileges for
  `authenticated`/`anon` are table-wide (RLS, not table grants, is
  meant to be Supabase's primary boundary). Without the `REVOKE` first,
  `authenticated` can still write *any* column on that table in the
  same request that legitimately satisfies the RLS `WITH CHECK` on the
  one column you meant to expose — confirmed live while building PR15
  (caught the exact gap on `opportunities.total_score`, retroactively
  fixed in `20260819120700_opportunity_inbox_actions.sql` too).

All of the above (including the RLS/tenant-isolation behavior) has been
verified against a real Postgres instance (`docker run postgres:16`,
migrations applied via `psql` with `ALTER DEFAULT PRIVILEGES` set up to
mirror how Supabase actually grants new tables — a one-time `GRANT ...
ON ALL TABLES` only covers tables that already exist, which is not how
Supabase's project bootstrap works — then exercised as the `anon` /
`authenticated` / `service_role` Postgres roles with a stubbed `auth`
schema) — not just read for syntax.
