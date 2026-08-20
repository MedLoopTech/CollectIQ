# Deployment (PR20)

`AIMFOLD_MASTER_GOAL.md` section 38 (Deployment): maintain separate
dev/staging/production, and provide migrations, environment
documentation, deployment instructions, rollback procedures, health
checks, automated tests, regression tests, and a release process —
"avoid undocumented manual production steps." This document is that —
process and tooling, written and live-verified, not an executed
deployment. **Nothing in this repo has been applied to the real
production Supabase project** (the one `01_landing_intake` and
`04_reviewer_dashboard` already commit non-secret config for) — that
remains a deliberate, explicit human decision, held per standing
instruction throughout this entire dev sequence. Executing any step
below against that project requires a new, explicit instruction; this
document exists so that when it's given, the steps are already written
down and already tested against a throwaway environment, not improvised
live against production.

## Environments

Only one environment currently exists in practice: the real Supabase
project referenced by `01_landing_intake`/`04_reviewer_dashboard`'s
config (call it **production** — it already has real CollectIQ pilot
data). Every verification step in PR1-19 used a second, throwaway one:
**dev** — `docker run postgres:16`, migrations applied via `psql`, torn
down after each check (see `supabase/README.md`'s verification-
methodology paragraph). Section 38 also wants a **staging** tier — a
real, linked Supabase project that is *not* production, used to run the
release checklist below against real Supabase infrastructure (real
`ALTER DEFAULT PRIVILEGES`, real PostgREST, real Auth) before anything
touches production. Staging does not exist yet; creating one is a real
step this document doesn't take unilaterally (creating cloud
infrastructure is exactly the kind of action to confirm before doing).

| Tier | What it is | State |
|---|---|---|
| dev | Local Docker Postgres, ephemeral | Used for every PR's live verification throughout this sequence |
| staging | A real, separate Supabase project | Does not exist yet |
| production | The real, live CollectIQ Supabase project | Exists; has real pilot data; migrations NOT applied |

## Environment documentation

| File | Covers | Committed? |
|---|---|---|
| `.env.example` (repo root) | `SUPABASE_URL`/`SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_ROLE_KEY` and the pre-Aimfold pilot's own config (Apify, Hunter, n8n webhooks) | Yes |
| `06_leadgen_apify/env.example` | Same Supabase vars plus `AIMFOLD_COLLECTIQ_AIM_ID` | Yes |
| `aimfold_core/aim_compiler/.env.example` (added this PR — didn't exist before) | `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` — the Aim Compiler's own LLM credentials, used for every live-Gemini verification in PR4/13/15/16/17/18 | Yes (the real `.env` next to it is gitignored via the root `*.env` pattern — confirmed with `git check-ignore -v`) |

No environment currently distinguishes dev/staging/production by
variable naming (e.g. `SUPABASE_URL` is just one value, not
`SUPABASE_URL_STAGING`/`SUPABASE_URL_PROD`) — since staging doesn't
exist yet, there's nothing to distinguish. When staging is created, the
straightforward approach already used elsewhere in this repo
(`aimfold_core/aim_compiler/.env` vs. the root `.env`) is separate `.env`
files per environment, not prefixed variable names.

## Deployment instructions

Preferred, once a Supabase project (staging or production) is linked:

```bash
supabase link --project-ref <project-ref>
supabase db push
```

`supabase db push` applies every file in `supabase/migrations/` in
filename order and tracks what's already applied — this repo's migration
files already follow the Supabase CLI's exact naming convention
(`<14-digit-timestamp>_description.sql`) for this reason, even though
every PR so far has been verified by hand-applying them via `psql`
instead (see `supabase/README.md`).

Fallback, documented since PR1 and still valid: paste each file into the
Supabase SQL editor in filename order. Every statement is idempotent
(`create table if not exists`, `create or replace function`,
`drop policy/trigger if exists` before `create`), so re-running a file
already applied is safe — this is also exactly what makes the rollback
mechanism below work.

Order matters and is fixed by filename timestamp — see
`supabase/README.md`'s migration table for what each file adds.

## Health checks

- **Schema health**: `supabase/health_check.sql` (added this PR). Checks
  all 23 expected tables exist, RLS is enabled on every one, and the
  three RLS/tenant-isolation helper functions
  (`is_tenant_member`/`tenant_role`/`opportunity_and_aim_belong_to_tenant`)
  exist. Run with `psql <connection-string> -f supabase/health_check.sql`
  — exits non-zero with `FAIL` lines listing exactly what's missing.
  Live-verified both ways: run against an empty database (27 FAIL lines,
  non-zero exit) and against the full PR1-19 chain (clean PASS, all four
  checks).
- **Service health**: `aimfold_core/aim_compiler/api.py` already exposes
  `GET /health` → `{"status": "ok"}` (built in PR4, unrelated to this
  PR) — the only actual running service in this codebase today. No other
  service exists yet to health-check (no scheduler, no worker process —
  see "What this does not make production-ready" below).

## Automated tests / regression tests (already exist — not new to this PR)

- `python -m pytest aimfold_core/` — 107 offline tests across every
  module (aim_compiler, evidence, scoring, opportunity, action, research,
  feedback, memory, evaluation, analytics, proposals, observability).
- `aimfold_core/evaluation/`'s regression framework (PR13) — the
  mechanism for catching a scoring/prompt change that regresses accuracy
  against a labeled dataset, run live against a real model.
- Live Docker migration-chain verification — done fresh for every PR in
  this sequence (23 tables, RLS, grants — most recently including PR19's
  attack-scenario tests). `health_check.sql` is the fast repeatable
  version of the schema-shape part of that check.

## Release process (pre-promotion checklist)

Before promoting a change from dev → staging → production:

1. `python -m pytest aimfold_core/` passes (currently 107/107).
2. Full migration chain applies cleanly to a fresh dev Postgres
   (`docker run postgres:16` + apply `supabase/migrations/*.sql` in
   order — see `supabase/README.md`'s verification-methodology
   paragraph for the exact `ALTER DEFAULT PRIVILEGES` setup that
   accurately mirrors Supabase's real bootstrap).
3. `supabase/health_check.sql` passes clean against that same database.
4. If the change touches RLS/grants: a live attack-scenario test proving
   the specific thing that changed (see PR15's and PR19's migrations for
   the pattern — attack fails, legitimate use still works). Not
   optional for security-relevant changes; this dev sequence has found
   three real gaps this way that pure SQL review missed.
5. If the change touches scoring/prompts: run PR13's evaluation
   framework against the relevant Aim's labeled dataset(s) and confirm
   no regression.
6. Promote: apply the same migration files, in the same order, to the
   next tier up (staging, then production) — via `supabase db push`
   against that project, or manual SQL-editor paste per "Deployment
   instructions" above.
7. Run `health_check.sql` against the newly-promoted tier before
   declaring the promotion complete.

## Rollback procedures

This dev sequence has no down-migrations — every file is a forward-only,
idempotent `create ... if not exists` / `drop ... if exists; create ...`
statement (see `supabase/README.md`'s conventions). Rollback strategy
differs by what a given migration actually did:

| Migration shape | Example | Rollback |
|---|---|---|
| Purely additive (new table/column, nothing pre-existing touched) | PR1, PR2, PR5, PR8, PR11, PR12, PR14 (no migration), PR18 | Leave in place. An unused table/column is inert — dropping it is a destructive action with no corresponding benefit; this repo's own safety rules already treat dropping data as something to avoid by default. |
| Seed data (idempotent upsert) | `20260819120200`/`20260819121100`/`20260819121300` (Aim seeds) | Re-running the file is itself the rollback if seed data was accidentally changed — `on conflict do update` restores the file's own values. |
| Redefines a policy/grant on an existing table | `20260819120700` (PR10), `20260819121500` (PR19) | Re-apply the specific earlier migration file that originally defined that policy — its own `drop policy if exists ... ; create policy ...` block recreates the prior definition, since every policy statement is self-contained and idempotent. **PR19 is the one case where this is dangerous**: rolling `20260819121500` back by re-running `20260819120000`/`20260819120800`/`20260819121000` un-fixes the three real security gaps that migration closed (see `supabase/README.md`'s "Security audit findings"). Only do this if the hardening migration itself is the confirmed cause of a production incident, and re-apply it again as soon as the underlying issue is fixed. |
| Redefines a CHECK constraint on an existing table | `20260819121200` (adds `'planned'` to `sources.status`) | No earlier file defines the constraint standalone (it was inline in PR1's `create table`). Manual rollback SQL: `alter table public.sources drop constraint sources_status_check; alter table public.sources add constraint sources_status_check check (status in ('active','disabled','deprecated'));` — only needed if something is actually relying on `'planned'` being rejected, which nothing in this codebase does. |

No migration in this sequence drops a column, drops a table, or deletes
rows — so no migration has an irreversible-data-loss rollback scenario
to plan for.

## MVP Success Criteria — honest self-assessment (section 43)

Read against the actual code, not aspirationally:

| # | Criterion | Status |
|---|---|---|
| 1 | User describes an Aim in natural language | ✅ `compile_aim()` / `POST /aims/compile` (PR4) |
| 2 | Aimfold compiles it into a structured Aim | ✅ PR4 |
| 3 | User can inspect/correct what Aimfold intends to watch | ⚠️ Partial — `compiled_spec` is inspectable in the DB and `aim_versions.status` supports proposed/approved/rejected, but no UI exists for a human to review a freshly-compiled Aim before approval (the Inbox UI, PR10, reviews Opportunities, not Aims) |
| 4 | Scheduled scouting runs reliably | ❌ Not built — no scheduler/cron/queue exists anywhere in this codebase; every pipeline stage has been invoked manually or via a one-off script for live verification |
| 5 | Sources normalize into a common Signal model | ✅ `entities`/`signals` schema (PR5) |
| 6 | Weak and duplicate signals are automatically suppressed | ⚠️ Partial — two-stage evidence/scoring (PR6/PR7) suppresses weak signals, `entities.fingerprint` dedup exists, but nothing currently populates `entities`/`signals` from a live connector run (`06_leadgen_apify` still writes to the legacy `lead_prospects` table — noted as open since PR5) |
| 7 | Strong Opportunities contain verifiable evidence | ✅ Evidence-first design + anti-fabrication substring checks (PR6) |
| 8 | Opportunities explain why they matter and why now | ✅ PR8/PR9, rendered in the Inbox UI |
| 9 | Opportunities include an appropriate recommended action | ✅ PR9 |
| 10 | Opportunity scores are explainable | ✅ `component_scores` + rationale (PR7) |
| 11 | Opportunity relevance can change when new signals arrive | ⚠️ Partial — clustering/lifecycle logic (stale/revived states, PR8) exists and is tested, but nothing automatically re-triggers it when a new signal arrives, for the same reason as #4 |
| 12 | Feedback and outcomes are captured | ✅ PR11 |
| 13 | Aim-specific learning data is retained | ✅ Aim Memory (PR12) |
| 14 | Costs are measurable | ✅ PR18 |
| 15 | Failures are observable and retryable | ⚠️ Partial — PR18 makes failures *observable* (`model_runs`/`workflow_runs` record `success=false`), but no retry/backoff logic is implemented anywhere (section 32) |
| 16 | Tenant data is isolated | ✅ PR1 + PR19, extensively live-tested including real attack scenarios |
| 17 | CollectIQ operates as an Aim rather than hard-coded engine logic | ✅ PR3 |
| 18 | At least one unrelated Aim operates without changing core engine code | ✅✅ Two (Career Discovery PR16, Funding Discovery PR17) — exceeds the stated minimum |

**12 met, 4 partial, 2 not met.** The two "not met" items (scheduled
execution, retry/backoff) are the same root gap: nothing in this
codebase runs anything automatically yet — every AI-backed module has
been proven live but only via manual/scripted invocation. That gap,
not RLS or schema completeness, is what actually stands between this
codebase and a genuine production release.

## What this does not make production-ready

This PR documents and tooling-tests the release *process*. It does not:

- Apply anything to the real production Supabase project (see the top of
  this document).
- Create a staging environment (would require provisioning real cloud
  infrastructure — a decision to confirm, not take unilaterally).
- Build a scheduler, queue, or retry/backoff mechanism (section 32,
  Production Reliability) — the single largest gap against section 43's
  MVP criteria, honestly assessed above rather than glossed over.
- Add rate limiting or webhook validation (section 33) — both need an
  API gateway/edge-function layer that doesn't exist yet (flagged
  already in PR19).

Those are real, substantial follow-on work, not something this document
can respond to with a bulleted line item. Recommended: those come after
an explicit decision to actually deploy to staging, not before —
building a scheduler for a system that has never run against a real
Supabase project would mean testing it against nothing real.
