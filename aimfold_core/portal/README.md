# Aimfold Portal

The proper, multi-view user portal for Aimfold — separate from CollectIQ
(same principle as `aimfold_site/`: CollectIQ is one Aim running on the
Aimfold engine, not the platform's own identity). Supersedes
`aimfold_core/inbox/index.html` as the primary operator surface;
`inbox/` is kept as-is (still real, still tested) rather than deleted.

## What's here

`index.html` — a single-page app (no build step, no framework — same
pragmatic vanilla-JS approach as `inbox/`), with the full nav structure
from the Aimfold brand board: **Home, Aims, Opportunities, Watchlist,
Activity, Insights, Settings.**

Visual language (revised after initial feedback that the first pass
read as a plain internal tool, not a real product): circular score
rings (color-coded by tier — green/blue/amber/red) reused consistently
across Home cards, the queue, and the detail header instead of a flat
number; a real stats strip on Home; entity initials as avatars; a
data-driven horizontal bar chart on Insights (opportunity count per
lifecycle stage, not just flat numbers); gradient score-breakdown bars;
a gradient sidebar with a glowing active-nav indicator; consistent icon
treatment and empty states with an illustration instead of bare text;
subtle hover/lift transitions and a page fade-in on navigation.

**Copy pass**: user-facing text should never leak implementation
details — a real product doesn't tell its users which internal service
it called or make them read a Postgres error. Fixed several places that
did: the "New Aim" modal's hint used to name the compiler's URL and the
`uvicorn` command to run it locally; the Insights and Settings empty-
states named `aimfold_core/analytics`, `auth.users`, `tenant_members`,
and specific PR numbers; and six different data-loading paths (plus
three write-error paths in the Opportunities detail pane) surfaced raw
Postgres/PostgREST error strings directly via `alert()` or inline
`<div class="warn">`. All now show plain, generic, human language
("Aimfold couldn't process that just now — please try again") — the
real technical detail still goes to `console.error()` for anyone
actually debugging, just never to the page itself.

| View | What it does | Real or placeholder? |
|---|---|---|
| Home | Top-ranked opportunities across every Aim | Real query |
| Aims | Lists the tenant's Aims (name, type, status) | Real query |
| Opportunities | Full queue + detail pane + Approve/Hold/Reject — the exact proven logic from `inbox/index.html`, restyled | Real query + real writes |
| Watchlist | Opportunities with `lifecycle_state='held'` | Real, filtered from the same data |
| Activity | Last 50 `feedback` decisions for the tenant | Real query |
| Insights | Total/average score/accept rate/rejected — computed client-side from whatever's already loaded | Real, but a simplified approximation — see note below |
| Settings | Tenant name/status + member list (role, join date) | Real query, read-only |

**"New Aim" (Aims view)** — a real wizard, not a mockup: type a goal in
plain language, it calls the actual Aim Compiler
(`aimfold_core/aim_compiler`, PR4, a real live LLM call — no fabrication)
and shows the compiled result for review (objective, target entity
types, positive criteria, scoring weights, likely actions); on approve,
it's genuinely persisted (`aims` + `aim_versions`, `status='approved'`,
`is_current=true`). This closes a gap `DEPLOYMENT.md`'s own section-43
self-assessment had flagged as only "partial": *"User can inspect/
correct what Aimfold intends to watch."*

This needed real backend work, not just UI — `aim_compiler/api.py`
previously only exposed `POST /aims/compile` (propose, never persisted —
its own docstring said persistence "is a separate, still-open piece of
PR4"). Added `POST /aims/propose`: given the exact `compiled_spec` the
browser already has (never re-compiled — no wasted LLM call, matching
the "persist before expensive next steps" rule), it independently
**re-validates that spec via the same `CompiledAimSpec` Pydantic model**
the compiler itself uses (a raw client `INSERT` could never do this,
which is exactly why `aim_versions` has no client-facing insert policy —
see `20260819120100_aim_schema.sql`'s own comment), **verifies the
caller's identity** via their real access token against Supabase Auth's
`/auth/v1/user`, and **explicitly checks tenant membership** before
writing anything with a service-role key the browser never sees. This
is deliberately not a client-side RLS `INSERT` policy — that would have
meant either accepting arbitrary unvalidated `compiled_spec` JSON or
duplicating Pydantic's validation logic in SQL; a thin, narrowly-scoped
backend endpoint was the more correct call.

Requires running `aim_compiler/api.py` locally (`uvicorn
aimfold_core.aim_compiler.api:app`) — nothing is deployed anywhere yet.
`?compilerUrl=` overrides where the portal looks for it (defaults to
`http://localhost:8000`), same pattern as `?sbUrl=`/`?sbKey=`.

Auth, styling, and the Supabase client setup (including the
`?sbUrl=&sbKey=` local-testing override) match `inbox/index.html`'s
already-proven pattern exactly — this file reuses that logic rather than
reinventing it, restyled with the Aimfold brand palette from
`aimfold_site/`.

## Honest limitations (not silently glossed over)

- **Insights is not a port of `aimfold_core/analytics`** (PR14). PR14's
  full funnel/outcome-correlation/economic reporting is a backend
  Python module with no HTTP endpoint yet — this view is a much simpler,
  genuinely real approximation computed in the browser from whatever
  opportunities RLS already returned, not the same thing. The view's own
  copy says a deeper report is on the way, in plain language — see the
  next bullet for why it doesn't name `aimfold_core/analytics` directly.
- **Settings can't show other members' email addresses.** `tenant_members`
  only stores `user_id`; resolving that to an email needs `auth.users`,
  which client-side code can't query directly (by design — it's not
  exposed via PostgREST). Shows "Team member" for other members instead
  of fabricating a lookup or exposing a raw user id. Member invites and
  role changes from this UI aren't built — would need a small
  service-role-backed endpoint, which doesn't exist yet.
- **Single-tenant-per-session assumption.** A user can belong to more
  than one tenant (`tenant_members` is many-to-many); this portal shows
  the first membership found, same simplification `inbox/index.html`
  already makes.
- **"New Aim" needs the compiler service running locally** — there's no
  deployed instance anywhere, same as everything else in this repo. If
  it can't reach it, the modal shows a plain "couldn't process that"
  message (see the copy note below for why it doesn't name the URL or
  the service); the real reason is only in the browser console.
- **No cross-request transaction between `aims` and `aim_versions`** in
  `/aims/propose` — if the `aims` insert succeeds but `aim_versions`
  fails, the orphaned `aims` row is invisible in practice (every read
  path here joins through `aim_versions.is_current`), but it's not
  cleaned up automatically. Disclosed in `api.py`'s own comment rather
  than solved with saga/retry logic this scope doesn't need.

## Verified how

Not just opened and eyeballed — the full authenticated flow was
exercised against real data:

1. Docker Postgres with the complete PR1-20 migration chain applied
   (same `ALTER DEFAULT PRIVILEGES` harness used throughout this dev
   sequence), plus PostgREST pointed at it.
2. A local-only `dev_facade.py` (deleted after use, same approach PR10's
   original inbox verification used) faking just enough of Supabase
   Auth's `/auth/v1/token` and `/auth/v1/user` for the page's real,
   unmodified `signInWithPassword()`/`getSession()`/`getUser()` calls to
   succeed against one seeded test user — CORS-enabled so the page
   (served from a separate static-file port) could reach it.
3. Seeded one real tenant member and two real opportunities (one
   high-scoring, one mid-scoring) against the existing CollectIQ Aim.
4. In the actual Browser tool: logged in for real, and confirmed every
   view against real query results — Home and Opportunities showed both
   seeded opportunities with correct scores/states; the Opportunities
   detail pane rendered the correct metrics, why-this/why-now text, and
   score breakdown; **clicked Approve on one and Hold on the other** —
   confirmed via `psql` that `opportunities.lifecycle_state`, a new
   `opportunity_lifecycle_events` row, and a new `feedback` row (with
   the correct prediction snapshot) all landed correctly; Watchlist then
   correctly showed only the held opportunity; Activity showed both
   decisions in the right order; Insights' computed aggregates
   (total=2, average score=75, accept rate=50%) matched hand-calculation
   exactly; Settings showed the real tenant and the real signed-in
   member's role.

**Re-verified after the visual revamp** with a fresh instance of the
same harness (4 seeded opportunities across 4 different lifecycle states
this time, to exercise the Insights bar chart's color-per-stage logic):
confirmed in the Browser tool with real screenshots — score rings render
with the correct tier colors, the Insights chart's bar widths and colors
match each stage's actual count, and gradient score-breakdown bars
render correctly. Clicked a real Approve on a second opportunity through
the redesigned UI and confirmed via `psql` that `lifecycle_state` and
the `feedback` row landed correctly — the visual changes didn't touch
any of the real query/write logic.

**"New Aim" verified with the full real stack running together** — a
third fresh instance of the Docker+PostgREST harness, `aim_compiler/api.py`
actually running (`uvicorn`, real `GEMINI_API_KEY`), and the dev auth
facade extended to genuinely validate JWTs (not just hand back a
hardcoded user) since `/aims/propose` depends on that check being real.
First hit a real, previously-undiagnosed intermittent `503` from
`gemini-flash-latest` under load — the same flakiness this whole dev
sequence has repeatedly worked around by using `gemini-flash-lite-latest`
instead; fixed properly by adding a `GEMINI_MODEL` env override to
`build_llm_client_from_env()` (`aim_compiler/llm_client.py`) rather than
hardcoding a model string at yet another call site. Then, via curl before
touching the browser: a real compile (200, real Gemini output), a real
propose (200, confirmed via `psql` — correct `status`, `is_current`,
`approved_by`), and three attack tests — proposing into a tenant the
caller doesn't belong to (403), no auth token at all (401), and a
hand-crafted incomplete `compiled_spec` (422, real Pydantic validation
errors) — all rejected correctly. Then the actual browser: typed a real
intent into the modal, watched a real ~10s Gemini call render a full
compiled-spec preview (criteria, gradient scoring-weight bars, likely
actions), clicked **Approve & Create Aim**, and confirmed both in the UI
(new Aim appears in the Aims list immediately) and via `psql` (correct
`opportunity_type`, `status='approved'`, `is_current=true`,
`compiler_model='gemini:gemini-flash-lite-latest'`).

**Caught and fixed a real bug during this pass**: the modal CSS edit
had accidentally dropped the `</style>` closing tag, which silently
swallowed the entire rest of the page (including the main `<script>`
block) into inert style-element text — `document.body` rendered
completely empty despite `document.readyState` reporting `'complete'`
and zero console errors. Found by checking tag-balance across the file
programmatically rather than continuing to guess from symptoms.
