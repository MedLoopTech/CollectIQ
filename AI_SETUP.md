# DeepSeek + Aider + Codex Setup for CollectIQ

This repository is configured for a two-model agentic coding workflow:

- **DeepSeek + Aider** is the primary implementation agent.
- **OpenAI Codex** is the independent senior reviewer before merge.

See `AI_WORKFLOW.md` for the operating process.

## 1. Install Aider

### Windows / macOS / Linux

```bash
python -m pip install aider-install
aider-install
```

Close and reopen your terminal if the `aider` command is not immediately available.

## 2. Create your local environment file

Copy the example file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Add your DeepSeek API key to `.env`:

```env
DEEPSEEK_API_KEY=your_real_key_here
```

Never commit `.env`.

## 3. Start the DeepSeek coding agent

From the repository root:

```bash
aider
```

The repo-level `.aider.conf.yml` uses:

- main model: `deepseek/deepseek-v4-pro`
- weak/secondary model: `deepseek/deepseek-v4-flash`
- automatic Git commits: enabled
- dirty-repo commits: disabled
- automatic linting: enabled
- automatic tests: disabled until module-specific test commands are standardized

## 4. Install Codex for independent review

Install the Codex CLI:

```bash
npm install -g @openai/codex
```

Then authenticate:

```bash
codex --login
```

Use Codex as a reviewer, not as the default implementation agent in this workflow.

## 5. Recommended workflow

Start from a clean feature branch:

```bash
git checkout master
git pull
git checkout -b feature/my-task
aider
```

Example implementation prompts:

```text
Read AGENTS.md and ARCHITECTURE.md first. Review the relevant code path and explain the risks before editing.
```

```text
Implement the requested change with the smallest patch possible. Run the most relevant validation available and summarize every file changed.
```

```text
Review your own diff for security issues, accidental secret exposure, broken API contracts, Supabase/RLS regressions, and financial calculation regressions before finishing.
```

Push the branch and open a pull request. The repository PR template contains the final review checklist.

## 6. Request Codex review on the pull request

Once the PR is ready, request the independent review in the PR conversation:

```text
@codex review
```

For riskier CollectIQ changes, use:

```text
@codex review for security vulnerabilities, Supabase/RLS regressions, financial-calculation errors, broken API contracts, and missing tests.
```

Resolve material findings before merging. If a fix is substantial, push the new patch and request another Codex review.

## 7. Useful Aider commands

Inside Aider:

```text
/help
/map
/diff
/undo
/run <command>
/test <command>
/commit
/exit
```

Use `/undo` if an AI edit is wrong. Because the project is in Git, you can also inspect or revert individual commits normally.

## 8. Model choice

Use V4 Pro for architecture, debugging, cross-module implementation, and difficult reasoning. Use V4 Flash when you want faster/cheaper work such as documentation, small fixes, repetitive edits, or first-pass code review.

To override the configured model for one session:

```bash
aider --model deepseek/deepseek-v4-flash
```

## 9. Security

Never paste or commit production Supabase service-role keys, DeepSeek keys, n8n credentials, Apify tokens, customer AR files, or other secrets. The repository `.gitignore` excludes `.env` files; verify `git status` before every push.

## 10. Architecture boundary

DeepSeek is not running inside OpenAI Codex. They are separate agents coordinated through Git and pull requests:

```text
You -> DeepSeek/Aider -> feature branch -> pull request -> Codex review -> merge
```

That separation is deliberate: the implementation model does not approve its own work.
