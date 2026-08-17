# DeepSeek + Aider Setup for CollectIQ

This repository is configured for an agentic coding workflow using Aider with DeepSeek.

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

## 3. Start the coding agent

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

## 4. Recommended workflow

Start from a clean branch:

```bash
git checkout master
git pull
git checkout -b feature/my-task
aider
```

Example prompts:

```text
Read AGENTS.md and ARCHITECTURE.md first. Review the audit engine and explain how invoice aging is calculated. Do not edit anything yet.
```

```text
Implement the requested change with the smallest patch possible. Run the most relevant validation available and summarize every file changed.
```

```text
Review your own diff for security issues, accidental secret exposure, broken API contracts, and financial calculation regressions before finishing.
```

## 5. Useful Aider commands

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

## 6. Model choice

Use V4 Pro for architecture, debugging, cross-module implementation, and difficult reasoning. Use V4 Flash when you want faster/cheaper work such as documentation, small fixes, repetitive edits, or first-pass code review.

To override the configured model for one session:

```bash
aider --model deepseek/deepseek-v4-flash
```

## 7. Security

Never paste or commit production Supabase service-role keys, DeepSeek keys, n8n credentials, Apify tokens, customer AR files, or other secrets. The repository `.gitignore` excludes `.env` files; verify `git status` before every push.

## 8. Current limitation

This setup provides a Codex-like terminal coding agent through Aider. It does not replace the model inside OpenAI Codex itself. DeepSeek is the LLM backend used by Aider while Git remains the safety and review layer.
