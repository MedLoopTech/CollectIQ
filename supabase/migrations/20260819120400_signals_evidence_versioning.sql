-- ===== 20260819120400_signals_evidence_versioning.sql =====
-- Aimfold Core — Signal Evidence Versioning (PR6, schema addition)
--
-- aimfold_core/evidence/ (PR6) adds a Stage-2 LLM evidence evaluator.
-- Reproducibility (AIMFOLD_MASTER_GOAL.md section 37: "every significant
-- decision should record ... model, prompt version") needs somewhere to
-- record which model/prompt version produced a signal's evidence
-- assessment — same denormalized-columns pattern as
-- aim_versions.compiler_model/compiler_prompt_version from PR2, rather
-- than standing up the full model_runs table early (that's PR18's job,
-- once there's more than one call site's worth of cost/latency to track).

alter table public.signals
  add column if not exists evidence_model text,
  add column if not exists evidence_prompt_version text;

comment on column public.signals.evidence_model is
  'Set only when Stage 2 (LLM evidence evaluation) actually ran for this signal — null means only the free Stage-1 deterministic filter ran (AIMFOLD_MASTER_GOAL.md section 14).';

comment on column public.signals.evidence_prompt_version is
  'aimfold_core/evidence/prompt.py PROMPT_VERSION at evaluation time.';
