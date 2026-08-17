-- CollectIQ Agent Business State v0.1
-- Persistent records for Phase 3 Scout/Research/Outreach, Phase 4 Sales,
-- Phase 5 Recovery Agent and Phase 6 CFO Agent.

create table if not exists public.prospect_research (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references public.lead_prospects(id) on delete cascade,
  job_id uuid references public.agent_jobs(id) on delete set null,
  icp_score integer check (icp_score between 0 and 100),
  confidence text check (confidence in ('low','medium','high')),
  qualification text check (qualification in ('qualified','watch','reject')),
  evidence jsonb not null default '[]'::jsonb,
  inferences jsonb not null default '[]'::jsonb,
  pain_signals jsonb not null default '[]'::jsonb,
  likely_ar_problem text,
  decision_maker_profile text,
  reason text,
  research_gaps jsonb not null default '[]'::jsonb,
  model_run jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.prospect_outreach (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references public.lead_prospects(id) on delete cascade,
  research_id uuid references public.prospect_research(id) on delete set null,
  job_id uuid references public.agent_jobs(id) on delete set null,
  channel text not null default 'email' check (channel in ('email','linkedin','other')),
  subject text,
  body text not null,
  personalization_basis jsonb not null default '[]'::jsonb,
  approval_id uuid references public.approval_queue(id) on delete set null,
  status text not null default 'draft' check (status in ('draft','pending_approval','approved','sent','rejected','cancelled')),
  sent_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.sales_conversations (
  id uuid primary key default gen_random_uuid(),
  prospect_id uuid not null references public.lead_prospects(id) on delete cascade,
  external_thread_id text,
  channel text not null default 'email' check (channel in ('email','linkedin','other')),
  status text not null default 'open' check (status in ('open','waiting_prospect','waiting_internal','qualified','closed','do_not_contact')),
  last_inbound_at timestamptz,
  last_outbound_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sales_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.sales_conversations(id) on delete cascade,
  direction text not null check (direction in ('inbound','outbound')),
  sender text,
  recipient text,
  subject text,
  body text not null,
  external_message_id text,
  classification text,
  intent_score integer check (intent_score between 0 and 100),
  agent_output jsonb,
  approval_id uuid references public.approval_queue(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.recovery_agent_runs (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  job_id uuid references public.agent_jobs(id) on delete set null,
  sprint_health text check (sprint_health in ('on_track','watch','at_risk')),
  summary text,
  priority_actions jsonb not null default '[]'::jsonb,
  broken_promises jsonb not null default '[]'::jsonb,
  dispute_actions jsonb not null default '[]'::jsonb,
  internal_actions jsonb not null default '[]'::jsonb,
  exceptions jsonb not null default '[]'::jsonb,
  model_run jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.cfo_agent_runs (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  snapshot_id uuid references public.sprint_weekly_snapshots(id) on delete set null,
  job_id uuid references public.agent_jobs(id) on delete set null,
  headline text,
  executive_summary text,
  metrics_commentary jsonb not null default '[]'::jsonb,
  management_attention jsonb not null default '[]'::jsonb,
  next_week_actions jsonb not null default '[]'::jsonb,
  risks jsonb not null default '[]'::jsonb,
  client_ready_summary text,
  model_run jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_prospect_research_prospect on public.prospect_research(prospect_id, created_at desc);
create index if not exists idx_prospect_outreach_status on public.prospect_outreach(status, created_at);
create index if not exists idx_sales_conversations_prospect on public.sales_conversations(prospect_id, updated_at desc);
create index if not exists idx_sales_messages_conversation on public.sales_messages(conversation_id, created_at);
create index if not exists idx_recovery_agent_runs_sprint on public.recovery_agent_runs(sprint_id, created_at desc);
create index if not exists idx_cfo_agent_runs_sprint on public.cfo_agent_runs(sprint_id, created_at desc);

alter table public.prospect_research enable row level security;
alter table public.prospect_outreach enable row level security;
alter table public.sales_conversations enable row level security;
alter table public.sales_messages enable row level security;
alter table public.recovery_agent_runs enable row level security;
alter table public.cfo_agent_runs enable row level security;

do $$
declare t text;
begin
  foreach t in array array['prospect_research','prospect_outreach','sales_conversations','sales_messages','recovery_agent_runs','cfo_agent_runs']
  loop
    execute format('drop policy if exists authenticated_internal_access on public.%I', t);
    execute format('create policy authenticated_internal_access on public.%I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

-- Founder/Manager Agent queue view: intentionally concise.
create or replace view public.manager_agent_attention_queue as
select 'approval'::text as item_type, id::text as item_id, risk_tier as severity,
       title, summary, requested_at as created_at
from public.approval_queue where status='pending'
union all
select 'exception', id::text, severity, title, details::text, created_at
from public.agent_exceptions where status in ('open','acknowledged')
order by created_at desc;
