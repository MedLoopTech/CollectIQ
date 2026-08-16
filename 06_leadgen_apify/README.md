# CollectIQ Apify Multi-Source Lead Gen v0.2

This upgrades the hiring-signal collector from a single jobs-search source to Apify Actors.

## Architecture

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
