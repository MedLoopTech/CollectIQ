# CollectIQ AI Coding Instructions

## Objective
Maintain and extend CollectIQ safely. Prefer small, reviewable changes over broad rewrites.

## Repository map
- `01_landing_intake/` — landing page and intake flow
- `02_audit_engine/` — AR audit logic
- `03_report_renderer/` — audit/report generation
- `04_reviewer_dashboard/` — human review workflow
- `05_n8n_e2e_audit/` — end-to-end n8n automation
- `06_leadgen_apify/` — lead generation and Apify integration
- `supabase/` — database assets

## Safety rules
1. Never commit `.env`, API keys, service-role keys, access tokens, customer files, or production credentials.
2. Do not modify production Supabase schema, auth, RLS, or destructive migrations unless the user explicitly asks.
3. Do not delete existing data, workflows, or features as part of a refactor unless explicitly requested.
4. Preserve current external API contracts unless the task explicitly requires a breaking change.
5. Before making a large change, inspect the relevant module and explain the intended files to modify.
6. Run the narrowest available test or validation after edits. If no test exists, state that clearly.
7. Keep financial/audit calculations deterministic. AI-generated narrative must not silently alter underlying numerical results.
8. Treat all uploaded customer AR data as confidential.

## Working style
- Read `ARCHITECTURE.md` and `README.md` before cross-module changes.
- Prefer minimal patches.
- Reuse existing patterns and dependencies.
- Add comments only where business logic is non-obvious.
- Do not add a new framework or service when the existing stack can reasonably solve the task.
- Surface assumptions instead of inventing missing business rules.

## Git
- Work on a feature branch.
- Keep commits focused.
- Do not force-push or rewrite history.
- Show a concise summary of changed files and validation performed at the end of each task.
