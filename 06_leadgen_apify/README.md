# CollectIQ Apify Multi-Source Lead Gen

## v0.3 — Aim-driven (current)

`collectiq_apify_multisource_leadgen_v03.json` is the current workflow.
It runs the exact same six searches and the same 11-rule keyword scorer
as v0.2, but neither is hardcoded in the workflow anymore — both are read
from Aimfold's Aim schema (see `AIMFOLD_MASTER_GOAL.md`, PR3 in its dev
sequence) at the start of each run:

```
Load Active Aim (aim_versions.compiled_spec, is_current=true)
→ Load Signal Hypotheses (aim_signal_hypotheses for that version)
→ Build Searches From Aim Hypotheses
→ [unchanged v0.2 pipeline: Apify → normalize → score → threshold → upsert]
```

This is CollectIQ converted into the first Aim per Aimfold's own dev
sequence — the search list, keyword-scoring weights and qualification
threshold now all live in
`supabase/migrations/20260819120200_seed_collectiq_aim.sql` as one
`aims` row, one approved+current `aim_versions` row, and six
`aim_signal_hypotheses` rows (one per search). Changing what CollectIQ
scouts for is now a data change (a new AimVersion), not a workflow edit.

Two real bugs found while doing this conversion were fixed in v0.3, not
just carried forward:

1. **Dropped columns**: v0.2's `Upsert Qualified Signal` never populated
   `source_platform`, `search_query` or `raw_signal`, even though the
   normalizer already computed all three and the schema has had columns
   for them since `supabase_v02_additions.sql`. v0.3 includes them.
2. **Wrong country code**: v0.2 hardcoded `country: 'US'` in
   `Build Actor Input` for every search, including the UK
   credit-controller ones. v0.3 derives it from `location`
   (`United States` → `US`, `United Kingdom` → `GB`).

Both the scoring-equivalence (v0.2 hardcoded rules vs. v0.3 reading the
same rules from `compiled_spec.scoring_weights`) and the search-list
reconstruction were verified with a standalone Node script comparing
outputs byte-for-byte before this workflow was written — v0.3 produces
identical scores/signals to v0.2 for the same input, only the country
fix changes behavior.

**Before activating v0.3**, apply, in order:
`20260819120000_core_multi_tenant_schema.sql` →
`20260819120150_aim_signal_hypotheses_connector_params.sql` →
`20260819120200_seed_collectiq_aim.sql` (see `supabase/README.md`), and
set `AIMFOLD_COLLECTIQ_AIM_ID` in your n8n environment (see
`env.example`).

`collectiq_apify_multisource_leadgen_v02.json` is kept as-is for
rollback/reference — it still reflects exactly what has run in
production (including the two bugs above).

## v0.2 — Apify Actors (superseded)

This upgraded the hiring-signal collector from a single jobs-search source to Apify Actors.

### Architecture

Apify LinkedIn Jobs Actor
+
Apify Indeed Jobs Actor
(+ Google Jobs / company career crawlers later)
→ n8n normalization
→ CollectIQ deterministic signal score
→ score >= 60
→ Supabase `lead_prospects`
→ existing domain/contact enrichment
→ human review
→ approved outreach

## Why the workflow isolates Actor input

Apify Actors are marketplace apps and their input/output schemas can differ by Actor and can change.

The `Build Actor Input` node is therefore the only node you should need to adapt when swapping Actors.

The `Normalize Multi-Source Jobs` node accepts several common output field names so downstream CollectIQ logic stays stable.

## Current default Actor IDs

- LinkedIn: `jobscrawler~linkedin-jobs-scraper`
- Indeed: `jobscrawler~indeed-jobs-scraper`

These are configurable environment variables; they are not hard dependencies.

## Important first-run step

Before activating the schedule:

1. Open each selected Actor in Apify.
2. Run one search manually.
3. Inspect its Input tab and Dataset output.
4. Update `Build Actor Input` to match that Actor's exact input schema.
5. Execute the n8n workflow manually.
6. Inspect `Normalize Multi-Source Jobs`.
7. Confirm company/title/description/location/source URL are populated.
8. Only then activate the daily schedule.

This is important because Actor marketplace schemas are not standardized.

## Suggested initial searches

As of v0.3, only "accounts receivable" / "collections specialist" (US)
and "credit controller" (UK) are live, one `aim_signal_hypotheses` row
each per source — see `20260819120200_seed_collectiq_aim.sql`. Adding
one of the searches below is now a new `aim_signal_hypotheses` row
(and, once the Aim Compiler/approval flow exists in PR4, a new
AimVersion) rather than an edit to `Build Searches From Aim Hypotheses`.

US:
- accounts receivable
- collections specialist
- accounts receivable manager
- order to cash
- billing and collections

UK:
- credit controller
- accounts receivable
- collections manager

Then add UAE, Saudi Arabia, Canada and Australia after measuring qualified-prospect economics.

## Cost controls

Start with 50 results per search.

Track:
- raw jobs collected
- unique jobs after dedupe
- score >= 60
- score >= 80
- valid company domains
- valid finance contacts
- replies
- AR audits booked
- cost per qualified prospect
- cost per audit

Do not optimize for number of scraped jobs.

## Enrichment

This v0.2 package focuses on replacing the acquisition layer.

After `Upsert Qualified Signal`, reuse the enrichment logic already built in v0.1:

qualified company
→ official domain
→ Hunter/public contact discovery
→ personalized draft
→ reviewer queue.

## Next phase

Add a `company_watchlist` table and an Apify website crawler that periodically checks known target companies' own career pages. A newly published AR/collections role then becomes a first-party hiring signal.
