-- CollectIQ Agent Foundation v0.1
-- Shared control plane for Scout, Research, Outreach, Sales, Audit, Recovery, CFO and Manager agents.

create extension if not exists pgcrypto;

create table if not exists public.agent_jobs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null check (agent_name in ('scout','research','outreach','sales','audit','recovery','cfo','manager')),
  job_type text not null,
  entity_type text,
  entity_id text,
  status text not null default 'queued' check (status in ('queued','running','waiting_approval','blocked','completed','failed','cancelled')),
  autonomy_tier text not null default 'green' check (autonomy_tier in ('green','amber','red')),
  priority integer not null default 50 check (priority between 0 and 100),
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb,
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  last_error text,
  scheduled_for timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agent_activity_log (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.agent_jobs(id) on delete set null,
  agent_name text not null,
  action text not null,
  entity_type text,
  entity_id text,
  autonomy_tier text check (autonomy_tier in ('green','amber','red')),
  provider text,
  model text,
  prompt_version text,
  input_summary jsonb,
  output_summary jsonb,
  confidence numeric,
  requires_approval boolean not null default false,
  latency_ms integer,
  input_tokens integer,
  output_tokens integer,
  estimated_cost_usd numeric,
  created_at timestamptz not null default now()
);

create table if not exists public.approval_queue (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.agent_jobs(id) on delete cascade,
  agent_name text not null,
  action_type text not null,
  entity_type text,
  entity_id text,
  risk_tier text not null check (risk_tier in ('amber','red')),
  title text not null,
  summary text,
  proposed_action jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '[]'::jsonb,
  status text not null default 'pending' check (status in ('pending','approved','rejected','expired','cancelled')),
  requested_at timestamptz not null default now(),
  decided_at timestamptz,
  decided_by uuid,
  decision_notes text
);

create table if not exists public.agent_exceptions (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.agent_jobs(id) on delete set null,
  agent_name text not null,
  entity_type text,
  entity_id text,
  severity text not null default 'medium' check (severity in ('low','medium','high','critical')),
  category text not null,
  title text not null,
  details jsonb not null default '{}'::jsonb,
  status text not null default 'open' check (status in ('open','acknowledged','resolved','dismissed')),
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolution_notes text
);

create table if not exists public.agent_model_runs (
  id uuid primary key default gen_random_uuid(),
  activity_id uuid references public.agent_activity_log(id) on delete set null,
  provider text not null,
  model text not null,
  request_id text,
  response_format text,
  latency_ms integer,
  input_tokens integer,
  output_tokens integer,
  estimated_cost_usd numeric,
  error text,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_jobs_queue on public.agent_jobs(status, priority desc, scheduled_for);
create index if not exists idx_agent_jobs_entity on public.agent_jobs(entity_type, entity_id);
create index if not exists idx_agent_activity_entity on public.agent_activity_log(entity_type, entity_id, created_at desc);
create index if not exists idx_approval_queue_pending on public.approval_queue(status, risk_tier, requested_at);
create index if not exists idx_agent_exceptions_open on public.agent_exceptions(status, severity, created_at);

create or replace function public.touch_agent_job_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

drop trigger if exists trg_agent_jobs_updated_at on public.agent_jobs;
create trigger trg_agent_jobs_updated_at before update on public.agent_jobs
for each row execute function public.touch_agent_job_updated_at();

alter table public.agent_jobs enable row level security;
alter table public.agent_activity_log enable row level security;
alter table public.approval_queue enable row level security;
alter table public.agent_exceptions enable row level security;
alter table public.agent_model_runs enable row level security;

-- Pilot internal access. Replace with organization/role-scoped policies before external multi-tenant access.
do $$
declare t text;
begin
  foreach t in array array['agent_jobs','agent_activity_log','approval_queue','agent_exceptions','agent_model_runs']
  loop
    execute format('drop policy if exists authenticated_internal_access on public.%I', t);
    execute format('create policy authenticated_internal_access on public.%I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

-- Manager Agent factual input view. It exposes counts only; no LLM should infer financial facts outside persisted records.
create or replace view public.manager_agent_operating_summary as
select
  (select count(*) from public.lead_prospects where status in ('new','reviewed','approved')) as prospects_open,
  (select count(*) from public.lead_prospects where status='contacted') as prospects_contacted,
  (select count(*) from public.lead_prospects where status='replied') as prospect_replies,
  (select count(*) from public.audit_leads where status in ('file_received','validating','needs_review','audit_ready')) as audits_open,
  (select count(*) from public.audit_leads where status='sent') as audits_sent,
  (select count(*) from public.recovery_sprints where status='active') as active_sprints,
  (select coalesce(sum(amount),0) from public.sprint_collections) as cash_recovered_recorded,
  (select count(*) from public.approval_queue where status='pending') as pending_approvals,
  (select count(*) from public.agent_exceptions where status in ('open','acknowledged') and severity in ('high','critical')) as high_exceptions,
  (select count(*) from public.agent_jobs where status='failed') as failed_agent_jobs,
  now() as generated_at;
