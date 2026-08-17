## Summary

Describe what changed and why.

## DeepSeek implementation pass

- [ ] Changes were implemented on a feature branch, not directly on `master`.
- [ ] Aider/DeepSeek reviewed `AGENTS.md` and `ARCHITECTURE.md` before editing.
- [ ] The diff is intentionally small and scoped to the requested task.
- [ ] Relevant lint/tests/validation were run.
- [ ] No secrets, production credentials, or customer AR data were committed.

## High-risk checks

- [ ] Supabase auth/RLS changes were reviewed carefully.
- [ ] Database migrations are backward-safe or explicitly documented.
- [ ] Financial calculations (aging, balances, recovery estimates, totals) were checked for regressions.
- [ ] External integrations (n8n, Apify, email/webhooks) preserve existing contracts.

## Codex senior review

After the PR is ready, request a second-model review in the PR conversation:

`@codex review`

For risky changes, use a focused request such as:

`@codex review for security vulnerabilities, Supabase/RLS regressions, financial-calculation errors, broken API contracts, and missing tests.`

Do not merge until material Codex findings are resolved or explicitly accepted with rationale.
