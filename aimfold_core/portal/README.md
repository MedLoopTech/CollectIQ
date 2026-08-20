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

| View | What it does | Real or placeholder? |
|---|---|---|
| Home | Top-ranked opportunities across every Aim | Real query |
| Aims | Lists the tenant's Aims (name, type, status) | Real query |
| Opportunities | Full queue + detail pane + Approve/Hold/Reject — the exact proven logic from `inbox/index.html`, restyled | Real query + real writes |
| Watchlist | Opportunities with `lifecycle_state='held'` | Real, filtered from the same data |
| Activity | Last 50 `feedback` decisions for the tenant | Real query |
| Insights | Total/average score/accept rate/rejected — computed client-side from whatever's already loaded | Real, but a simplified approximation — see note below |
| Settings | Tenant name/status + member list (role, join date) | Real query, read-only |

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
  opportunities RLS already returned, not the same thing. Said so
  explicitly in the view itself, not just here.
- **Settings can't show other members' email addresses.** `tenant_members`
  only stores `user_id`; resolving that to an email needs `auth.users`,
  which client-side code can't query directly (by design — it's not
  exposed via PostgREST). Shows a truncated user id for other members
  instead of fabricating a lookup. Member invites and role changes from
  this UI aren't built — would need a small service-role-backed endpoint,
  which doesn't exist yet.
- **Single-tenant-per-session assumption.** A user can belong to more
  than one tenant (`tenant_members` is many-to-many); this portal shows
  the first membership found, same simplification `inbox/index.html`
  already makes.

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
