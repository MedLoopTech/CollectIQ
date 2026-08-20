-- ===== 20260819121400_observability_schema.sql =====
-- Aimfold Core — Production Observability + Cost Tracking (PR18)
--
-- AIMFOLD_MASTER_GOAL.md section 34 (Observability) and section 35
-- (Cost Intelligence). Section 36's core domain list also names
-- prompt_versions/connector_versions/experiments — deliberately NOT
-- added here, same discipline as every earlier PR in this sequence
-- (e.g. PR7 shipped no migration at all; PR8's tables stayed schema-only
-- until something populated them): nothing in this codebase yet
-- versions prompts or connectors independently of the plain text/text
-- columns that already carry that information
-- (aim_versions.compiler_prompt_version, sources.connector_version), and
-- nothing runs A/B experiments yet. Building those tables now would mean
-- guessing their shape rather than deriving it from a real caller.
--
-- Scope actually covered: the two tables sections 34/35's bullet lists
-- map onto something that already exists and is instrumentable today —
-- every LLM call (aim_compiler, evidence Stage 2, research synthesis all
-- already flow through the shared LLMClient interface — see
-- aimfold_core/observability/instrumented_client.py) and the multi-item
-- batch computations that already run as coherent units
-- (run_evaluation(), proposal testing, aim_memory recomputation).
-- Broader operational telemetry section 34 also names — source connector
-- health, retries, queue sizes, scheduled workflow tracking — genuinely
-- needs a scheduler/queue/connector-runner that doesn't exist in this
-- repo yet; tracking it now would mean fabricating data no live system
-- produces.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- model_runs — every LLM call (section 34: "model calls, model failures,
-- model cost, latency"; section 35: "model cost", "cost per Aim").
-- ---------------------------------------------------------------------------

create table if not exists public.model_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid references public.aims(id) on delete cascade,
  stage text not null
    check (stage in ('aim_compilation', 'evidence_stage2', 'research_synthesis')),
  provider text not null,
  model text not null,
  input_tokens integer check (input_tokens is null or input_tokens >= 0),
  output_tokens integer check (output_tokens is null or output_tokens >= 0),
  latency_ms numeric check (latency_ms is null or latency_ms >= 0),
  estimated_cost_usd numeric check (estimated_cost_usd is null or estimated_cost_usd >= 0),
  success boolean not null default true,
  error_message text,
  created_at timestamptz not null default now()
);

create index if not exists model_runs_tenant_id_idx on public.model_runs(tenant_id);
create index if not exists model_runs_aim_id_idx on public.model_runs(aim_id);
create index if not exists model_runs_stage_created_at_idx on public.model_runs(stage, created_at desc);

comment on table public.model_runs is
  'One row per LLM API call across the whole pipeline (aim_compiler, evidence Stage 2, research synthesis — the three call sites that exist today). Populated by aimfold_core/observability/instrumented_client.py wrapping any LLMClient transparently; the modules that make the calls (compiler.py, evaluator.py, synthesizer.py) are unmodified and unaware this exists.';

comment on column public.model_runs.aim_id is
  'Nullable, unlike tenant_id: a fresh Aim compilation happens before any aims/aim_versions row exists (compile_aim() takes only raw text plus whichever tenant the requesting user belongs to) — the model_runs row for that call has no aim_id to point at yet. tenant_id is always known, since every real call happens within an authenticated tenant member''s request context.';

comment on column public.model_runs.estimated_cost_usd is
  'Computed from a hardcoded (provider, model) rate table in aimfold_core/observability/cost.py — null, not guessed, for any model not in that table. Rates need periodic manual updates as providers change pricing; see that file''s header for the source and date they were last checked.';

-- ---------------------------------------------------------------------------
-- workflow_runs — multi-step batch computations that already run as one
-- coherent unit today (section 34: "workflow executions").
-- ---------------------------------------------------------------------------

create table if not exists public.workflow_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid references public.aims(id) on delete cascade,
  workflow_type text not null
    check (workflow_type in ('evaluation_run', 'proposal_test', 'aim_memory_recompute')),
  status text not null default 'running'
    check (status in ('running', 'succeeded', 'failed')),
  items_processed integer not null default 0 check (items_processed >= 0),
  items_qualified integer check (items_qualified is null or items_qualified >= 0),
  metadata jsonb not null default '{}'::jsonb,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists workflow_runs_tenant_id_idx on public.workflow_runs(tenant_id);
create index if not exists workflow_runs_aim_id_idx on public.workflow_runs(aim_id);
create index if not exists workflow_runs_type_started_at_idx on public.workflow_runs(workflow_type, started_at desc);

comment on table public.workflow_runs is
  'One row per execution of a multi-step batch computation. workflow_type is deliberately scoped to the three that exist as real, invokable units today (run_evaluation() across a dataset, proposals/testing.py''s test_*_proposal(), compute_aim_memory()) — not every workflow section 34 eventually wants tracked, only the ones that actually run. Populated by aimfold_core/observability/workflow_tracking.py''s WorkflowRunTracker context manager wrapping a call to any of those, again with zero changes to the wrapped functions.';

comment on column public.workflow_runs.items_qualified is
  'Meaningful for evaluation_run (Stage-1-qualified example count) and null for proposal_test/aim_memory_recompute, which have no equivalent concept.';

-- ---------------------------------------------------------------------------
-- RLS — same read-only-for-authenticated pattern as aim_memory/entity_memory:
-- populated by a backend job (service-role), not written to directly by users.
-- ---------------------------------------------------------------------------

alter table public.model_runs enable row level security;
alter table public.workflow_runs enable row level security;

drop policy if exists model_runs_select_own_tenant on public.model_runs;
create policy model_runs_select_own_tenant on public.model_runs
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists workflow_runs_select_own_tenant on public.workflow_runs;
create policy workflow_runs_select_own_tenant on public.workflow_runs
  for select using (public.is_tenant_member(tenant_id));
