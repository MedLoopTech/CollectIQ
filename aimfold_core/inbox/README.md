# Opportunity Inbox (PR10, feedback wiring added in PR11)

The operator-facing surface `AIMFOLD_MASTER_GOAL.md` section 46 describes:
**Create Aim → Aimfold watches → best Opportunities appear → inspect why →
act/skip → Aimfold learns.** This is the "best Opportunities appear →
inspect why → act/skip" part — and, since PR11, the "learns" part starts
here too: every Approve/Hold/Reject writes a structured `feedback` row
(see `aimfold_core/feedback/`), not just a lifecycle transition.

## What it is

`index.html` — a static page, no build step, styled and structured the
same way as `04_reviewer_dashboard/index.html` (same CSS variable
palette, same Supabase-Auth-login-then-queue-then-detail layout), because
that page is this repo's own working precedent for "human approval queue
backed by Supabase." It queries `opportunities` (joined to `entities`,
`aims`, and — through `opportunity_signals` — `signals`) ordered by
`total_score`, and for the selected opportunity renders section 47's four
questions directly from real columns:

| Question | Source |
|---|---|
| Why this? | `opportunities.relevance_explanation` |
| Why now? | `opportunities.why_now` |
| What proves it? | every linked signal's `extracted_evidence` |
| What next? | `opportunities.recommended_action` + `recommended_action_rationale` |

Also shown: `total_score` / `confidence` / `evidence_confidence` /
`source_confidence`, and the full `component_scores` breakdown (PR7's
`ExplainableScore`, one bar per dimension with its own rationale — not
just the total).

**"What proves it?" renders Evidence-First visually, not just enforces it
in code.** Each `extracted_evidence` entry is tagged `observed_fact` /
`stage1_match` or `inference`; the UI gives them visibly different
styling (green solid vs. purple italic, badged "Observed" vs. "AI
inference") so a reviewer can tell at a glance which is which —
`AIMFOLD_MASTER_GOAL.md` section 8's "AI-generated inference must be
clearly distinguishable from observed facts" applied to the actual
product surface, not only to the backend validation in
`aimfold_core/evidence/evaluator.py`.

## Approve / Hold / Reject

This is the first `aimfold_core` surface where a human writes directly
from the browser — every earlier pipeline table is select-only for
`authenticated` (populated by a service-role-backed backend). The three
buttons update `opportunities.lifecycle_state` and insert a matching
`opportunity_lifecycle_events` row, restricted at the database level by
`supabase/migrations/20260819120700_opportunity_inbox_actions.sql`:

- A **column-level GRANT, preceded by an explicit `REVOKE UPDATE`** —
  `authenticated` can only ever write `lifecycle_state` on
  `opportunities`, nothing else (not the score, not the evidence). The
  `REVOKE` isn't decorative: a column `GRANT` alone doesn't narrow a
  broader table-wide privilege Supabase already grants `authenticated`
  by default, so without it this same "human-writable" request could
  smuggle in a `total_score` change too. Found live while building PR15
  and fixed here retroactively — see `supabase/README.md`'s convention
  entry for the full explanation.
- An **RLS `WITH CHECK`** — the new value must be `held`, `rejected`, or
  `actioned`. A member cannot set `lifecycle_state='high_priority'` to
  fake a better ranking; only the deterministic engine in
  `aimfold_core/opportunity/lifecycle.py` (via service-role) sets
  score-driven states.

Buttons disable themselves once an opportunity reaches a human/action-
controlled state (`actioned`/`held`/`rejected`/`duplicate`/`invalid`).

**Since PR11**, each click also inserts a `feedback` row (Approve →
`feedback_type='accepted'`, Hold → `'held'`, Reject → `'rejected'`),
carrying a snapshot of what was predicted at that exact moment
(`predicted_total_score`, `predicted_confidence`,
`predicted_recommended_action`, `predicted_lifecycle_state`,
`scoring_version` — `AIMFOLD_MASTER_GOAL.md` section 21's Learning Loop).
Clicking Reject doesn't fire immediately — it reveals a required
rejection-reason picker (the 18-value taxonomy from section 19) and only
writes once a reason is chosen and confirmed; `20260819120800_feedback_outcomes_schema.sql`'s
`feedback_rejection_reason_required` CHECK constraint enforces the same
rule at the database level regardless of what the UI does.

## Verified how

Not just read for syntax — actually clicked through in a real browser
against real writes:

1. Spun up a throwaway Postgres + PostgREST stack in Docker (same
   pattern used to verify every migration in this dev sequence), applied
   the full PR1–PR10 migration chain, and seeded two realistic
   opportunities (one reusing the actual scored evidence/action output
   from PR7/PR9's live Gemini runs).
2. Since PostgREST alone doesn't implement Supabase's Auth endpoints,
   `dev_facade.py` (local-only, deleted after testing — not part of the
   shipped page) proxied `/rest/v1/*` to PostgREST and faked just enough
   of `/auth/v1/token`/`/auth/v1/user` for the page's *real, unmodified*
   `signInWithPassword()` login flow to succeed with a locally-minted
   JWT. `index.html` itself only gained a harmless `?sbUrl=&sbKey=`
   endpoint override for this (never bypasses the login call itself —
   see the comment above the constant in the file).
3. In the actual Browser tool: logged in for real, watched the queue
   render both seeded opportunities sorted by score, opened Acme Freight
   Systems and confirmed every field (Why this/Why now/What proves it —
   including the observed-vs-inference badges — score breakdown, What
   next) rendered correctly, clicked **Approve**, and confirmed via
   `psql` that both `opportunities.lifecycle_state` and a new
   `opportunity_lifecycle_events` row landed correctly.
4. **Caught a real bug doing this, not a synthetic one:** the login form
   handler and `sb.auth.onAuthStateChange` both called `showApp()` →
   `loadQueue()`, racing two fetches. `selected` ended up pointing at an
   object from the first (discarded) `opportunities` array, so a
   successful DB write didn't visibly update the sidebar until reload.
   Fixed by removing the redundant `showApp()` call and making the
   transition handler look up the current object by id instead of
   assuming reference equality. Re-verified in the browser after the fix
   — clicking **Hold** on the second opportunity updated the sidebar
   immediately, no reload needed.
5. curl-tested the RLS policy directly too: a disallowed target state
   (`high_priority`) → `403`; a disallowed column (`total_score`) →
   `403`; the allowed write → `200`.

Also verified, separately: navigating the *real* `index.html` (no
overrides) against the real Supabase project reused a real cached login
session from earlier testing and correctly surfaced a real
`"Could not find the table 'public.opportunities'"` error — confirming
the page talks to the real project correctly and that the Aimfold
migrations genuinely aren't applied there yet (see below).

## Before this is real

**The Aimfold migrations (PR1 through PR10) have not been applied to the
real, live Supabase project** this page points at by default (the same
project `01_landing_intake` and `04_reviewer_dashboard` already commit
credentials for). Nothing here does that automatically — schema changes
to a database that presumably has real CollectIQ pilot data in it are
exactly the kind of thing to confirm before doing, not decide
unilaterally. Once you're ready: apply `supabase/migrations/*.sql` in
order (see `supabase/README.md`), and the real page will start showing
real data as soon as a pipeline populates `opportunities` (nothing does
that yet either — see "Deliberately not built" notes throughout
`aimfold_core/README.md`; this inbox reads whatever's there, it doesn't
create opportunities itself).
