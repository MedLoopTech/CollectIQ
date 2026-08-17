# CollectIQ AI Development Workflow

CollectIQ uses a two-model workflow:

1. **DeepSeek + Aider** is the primary implementation agent.
2. **OpenAI Codex** is the independent senior reviewer before merge.

The goal is to keep routine coding inexpensive while preserving a stronger second-model review layer for risky changes.

## 1. Start clean

```bash
git checkout master
git pull
git checkout -b feature/<short-task-name>
```

Verify the working tree is clean:

```bash
git status
```

## 2. Implement with DeepSeek

From the repository root:

```bash
aider
```

Recommended first prompt:

```text
Read AGENTS.md and ARCHITECTURE.md first. Explain the relevant code path and risks before editing. Then implement the smallest safe patch, run relevant validation, and review your diff for secrets, security issues, broken API contracts, and financial calculation regressions.
```

Use `/diff`, `/test`, `/undo`, and `/commit` as needed.

## 3. Push and open a pull request

```bash
git push -u origin HEAD
```

Open the PR against `master` and complete the repository PR checklist.

## 4. Request Codex review

Once the PR is ready for review, ask Codex in the PR conversation:

```text
@codex review
```

For higher-risk changes, use:

```text
@codex review for security vulnerabilities, Supabase/RLS regressions, financial-calculation errors, broken API contracts, and missing tests.
```

Codex is the independent reviewer. DeepSeek should not be treated as having approved its own implementation.

## 5. Resolve findings

For each material Codex finding:

1. Confirm the finding against the code and intended behavior.
2. Use DeepSeek/Aider to make the smallest corrective patch if needed.
3. Run the relevant validation again.
4. Push the fix.
5. Ask Codex to review again if the change is material.

## 6. Merge gate

Do not merge until all of the following are true:

- relevant tests/lint/validation pass;
- no secrets or customer data are present in the diff;
- material Codex findings are resolved or explicitly accepted with rationale;
- Supabase/auth/RLS changes have been checked for privilege regressions;
- financial calculations have been checked against expected examples;
- external API/webhook contracts remain compatible or the breaking change is documented.

## Model responsibilities

### DeepSeek / Aider

Use for:

- implementation;
- refactoring;
- repetitive edits;
- documentation;
- test generation;
- first-pass debugging.

### Codex

Use for:

- independent PR review;
- architecture-risk review;
- security and authorization review;
- financial-logic review;
- test-gap identification;
- difficult debugging when a second opinion is useful.

## Important boundary

DeepSeek is not running inside OpenAI Codex. They are two separate agents sharing Git as the coordination layer:

```text
You -> DeepSeek/Aider -> feature branch -> pull request -> Codex review -> merge
```

That separation is intentional: it gives CollectIQ an independent reviewer rather than asking the same model to implement and approve its own work.
