-- CollectIQ Recovery Sprint v0.1
-- Internal service-delivery schema for the 30-day AR Recovery Sprint.

create extension if not exists pgcrypto;

create table if not exists public.recovery_sprints (
  id uuid primary key default gen_random_uuid(),
  audit_lead_id uuid references public.audit_leads(id) on delete set null,
  company_name text not null,
  contact_name text,
  contact_email text,
  status text not null default 'draft' check (status in ('draft','active','paused','completed','cancelled')),
  start_date date,
  end_date date,
  current_week integer not null default 0 check (current_week between 0 and 4),
  base_currency text not null default 'USD',
  baseline_total_ar numeric not null default 0,
  baseline_overdue_ar numeric not null default 0,
  baseline_60_plus numeric not null default 0,
  baseline_90_plus numeric not null default 0,
  baseline_priority_pool numeric not null default 0,
  target_notes text,
  owner_user_id uuid,
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sprint_accounts (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  external_customer_id text,
  customer_name text not null,
  contact_name text,
  contact_email text,
  sales_owner text,
  total_outstanding numeric not null default 0,
  overdue_amount numeric not null default 0,
  priority_score numeric,
  priority_band text,
  last_contact_at timestamptz,
  next_action_at timestamptz,
  current_status text not null default 'open' check (current_status in ('open','promise','disputed','paid','hold','closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sprint_id, customer_name)
);

create table if not exists public.sprint_invoices (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid not null references public.sprint_accounts(id) on delete cascade,
  invoice_number text not null,
  invoice_date date,
  due_date date,
  currency text not null default 'USD',
  invoice_amount numeric not null default 0,
  outstanding_amount numeric not null default 0,
  days_overdue integer not null default 0,
  age_bucket text,
  priority_score numeric,
  priority_band text,
  collection_status text not null default 'open' check (collection_status in ('open','contacted','awaiting_reply','promise','disputed','paid','hold','written_off')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sprint_id, invoice_number)
);

create table if not exists public.sprint_actions (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid references public.sprint_accounts(id) on delete cascade,
  invoice_id uuid references public.sprint_invoices(id) on delete set null,
  action_type text not null check (action_type in ('follow_up','check_promise','resolve_dispute','contact_sales_owner','request_document','call_customer','manual_review','other')),
  priority integer not null default 50 check (priority between 0 and 100),
  reason text,
  recommended_action text,
  owner text,
  due_at timestamptz,
  completed_at timestamptz,
  status text not null default 'open' check (status in ('open','in_progress','done','cancelled')),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sprint_promises (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid not null references public.sprint_accounts(id) on delete cascade,
  invoice_id uuid references public.sprint_invoices(id) on delete set null,
  promise_amount numeric not null,
  promise_date date not null,
  status text not null default 'pending' check (status in ('pending','kept','partially_kept','missed','renegotiated','cancelled')),
  source text,
  actual_payment_amount numeric not null default 0,
  fulfilled_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sprint_disputes (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid not null references public.sprint_accounts(id) on delete cascade,
  invoice_id uuid references public.sprint_invoices(id) on delete set null,
  category text not null,
  description text,
  amount numeric not null default 0,
  owner text,
  status text not null default 'open' check (status in ('open','investigating','waiting_internal','waiting_customer','resolved','closed')),
  next_action text,
  opened_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolution_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sprint_collections (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid not null references public.sprint_accounts(id) on delete cascade,
  invoice_id uuid references public.sprint_invoices(id) on delete set null,
  amount numeric not null check (amount > 0),
  payment_date date not null,
  currency text not null default 'USD',
  source text default 'manual',
  reference text,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.sprint_activities (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  account_id uuid references public.sprint_accounts(id) on delete cascade,
  invoice_id uuid references public.sprint_invoices(id) on delete set null,
  activity_type text not null check (activity_type in ('email','call','note','meeting','internal','status_change','document','other')),
  direction text check (direction in ('inbound','outbound','internal')),
  subject text,
  body text,
  occurred_at timestamptz not null default now(),
  created_by uuid default auth.uid(),
  created_at timestamptz not null default now()
);

create table if not exists public.sprint_weekly_snapshots (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  week_number integer not null check (week_number between 0 and 4),
  snapshot_date date not null default current_date,
  total_ar numeric not null default 0,
  overdue_ar numeric not null default 0,
  ar_60_plus numeric not null default 0,
  ar_90_plus numeric not null default 0,
  priority_pool numeric not null default 0,
  cash_collected_to_date numeric not null default 0,
  cash_collected_this_week numeric not null default 0,
  promises_due numeric not null default 0,
  promises_kept numeric not null default 0,
  promises_missed numeric not null default 0,
  disputed_ar numeric not null default 0,
  disputes_resolved numeric not null default 0,
  open_actions integer not null default 0,
  management_attention_accounts integer not null default 0,
  created_at timestamptz not null default now(),
  unique (sprint_id, week_number)
);

create table if not exists public.sprint_cfo_briefs (
  id uuid primary key default gen_random_uuid(),
  sprint_id uuid not null references public.recovery_sprints(id) on delete cascade,
  snapshot_id uuid references public.sprint_weekly_snapshots(id) on delete set null,
  week_number integer not null check (week_number between 1 and 4),
  status text not null default 'draft' check (status in ('draft','reviewed','sent')),
  executive_summary text,
  management_actions jsonb not null default '[]'::jsonb,
  top_accounts jsonb not null default '[]'::jsonb,
  blockers jsonb not null default '[]'::jsonb,
  generated_at timestamptz not null default now(),
  reviewed_at timestamptz,
  sent_at timestamptz,
  unique (sprint_id, week_number)
);

create index if not exists idx_sprint_accounts_sprint on public.sprint_accounts(sprint_id);
create index if not exists idx_sprint_invoices_sprint on public.sprint_invoices(sprint_id);
create index if not exists idx_sprint_actions_due on public.sprint_actions(sprint_id, status, due_at);
create index if not exists idx_sprint_promises_due on public.sprint_promises(sprint_id, status, promise_date);
create index if not exists idx_sprint_disputes_status on public.sprint_disputes(sprint_id, status);
create index if not exists idx_sprint_collections_date on public.sprint_collections(sprint_id, payment_date);

create or replace function public.touch_recovery_sprint_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

create trigger trg_recovery_sprints_updated_at before update on public.recovery_sprints for each row execute function public.touch_recovery_sprint_updated_at();
create trigger trg_sprint_accounts_updated_at before update on public.sprint_accounts for each row execute function public.touch_recovery_sprint_updated_at();
create trigger trg_sprint_invoices_updated_at before update on public.sprint_invoices for each row execute function public.touch_recovery_sprint_updated_at();
create trigger trg_sprint_actions_updated_at before update on public.sprint_actions for each row execute function public.touch_recovery_sprint_updated_at();
create trigger trg_sprint_promises_updated_at before update on public.sprint_promises for each row execute function public.touch_recovery_sprint_updated_at();
create trigger trg_sprint_disputes_updated_at before update on public.sprint_disputes for each row execute function public.touch_recovery_sprint_updated_at();

alter table public.recovery_sprints enable row level security;
alter table public.sprint_accounts enable row level security;
alter table public.sprint_invoices enable row level security;
alter table public.sprint_actions enable row level security;
alter table public.sprint_promises enable row level security;
alter table public.sprint_disputes enable row level security;
alter table public.sprint_collections enable row level security;
alter table public.sprint_activities enable row level security;
alter table public.sprint_weekly_snapshots enable row level security;
alter table public.sprint_cfo_briefs enable row level security;

-- Pilot: any authenticated internal reviewer can operate Sprint data.
-- Tighten this to explicit organization/admin roles before external multi-tenant access.
do $$
declare t text;
begin
  foreach t in array array['recovery_sprints','sprint_accounts','sprint_invoices','sprint_actions','sprint_promises','sprint_disputes','sprint_collections','sprint_activities','sprint_weekly_snapshots','sprint_cfo_briefs']
  loop
    execute format('drop policy if exists authenticated_internal_access on public.%I', t);
    execute format('create policy authenticated_internal_access on public.%I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;
