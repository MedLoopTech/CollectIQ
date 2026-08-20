-- ===== 20260819120000_core_multi_tenant_schema.sql =====
-- Aimfold Core — Multi-Tenant Foundation (PR1)
--
-- Generic multi-tenant schema and core terminology for the Aimfold
-- opportunity-intelligence engine (see AIMFOLD_MASTER_GOAL.md). This is
-- shared infrastructure every future Aim, Entity, Signal and Opportunity
-- table will depend on. None of those exist yet — Aim/AimVersion lands in
-- the next migration (PR2); Entity/Signal/Opportunity are later PRs.
--
-- Apply via `supabase db push`, or paste into the Supabase SQL editor.
-- Existing CollectIQ tables (audit_leads, audit_events, lead_prospects in
-- collectiq_full_schema.sql) are untouched by this migration; converting
-- them into the first Aim is PR3.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- tenants
-- ---------------------------------------------------------------------------

create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  status text not null default 'active'
    check (status in ('active', 'trial', 'suspended', 'archived')),
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.tenants is
  'An independent organization/account using Aimfold. All tenant-scoped data must carry tenant_id and be isolated via RLS.';

-- ---------------------------------------------------------------------------
-- tenant_members — links Supabase auth users to tenants with a role
-- ---------------------------------------------------------------------------

create table if not exists public.tenant_members (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member'
    check (role in ('owner', 'admin', 'member', 'viewer')),
  created_at timestamptz not null default now(),
  unique (tenant_id, user_id)
);

create index if not exists tenant_members_user_id_idx on public.tenant_members(user_id);
create index if not exists tenant_members_tenant_id_idx on public.tenant_members(tenant_id);

-- ---------------------------------------------------------------------------
-- sources — catalog of source connector types (system-level, not tenant data)
-- ---------------------------------------------------------------------------

create table if not exists public.sources (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  name text not null,
  connector_type text not null,
  connector_version text not null default '0.1.0',
  status text not null default 'active'
    check (status in ('active', 'disabled', 'deprecated')),
  config_schema jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.sources is
  'Registry of pluggable source connector types (e.g. linkedin_jobs_apify, indeed_jobs_apify, career_page_crawler). Shared across tenants; per-Aim usage/config is tracked elsewhere (see aim_signal_hypotheses in PR2).';

-- ---------------------------------------------------------------------------
-- audit_log — generic, tenant-scoped audit trail for security-relevant actions
-- ---------------------------------------------------------------------------

create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references public.tenants(id) on delete cascade,
  actor_user_id uuid references auth.users(id),
  action text not null,
  target_type text,
  target_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists audit_log_tenant_id_idx on public.audit_log(tenant_id);
create index if not exists audit_log_created_at_idx on public.audit_log(created_at desc);

-- ---------------------------------------------------------------------------
-- shared trigger: keep updated_at current
-- ---------------------------------------------------------------------------

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_updated_at on public.tenants;
create trigger set_updated_at before update on public.tenants
  for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.sources;
create trigger set_updated_at before update on public.sources
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- shared RLS helpers
--
-- security definer so membership can be checked without recursively
-- re-evaluating RLS on tenant_members itself (standard Supabase pattern
-- for multi-tenant isolation).
-- ---------------------------------------------------------------------------

create or replace function public.is_tenant_member(check_tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.tenant_members tm
    where tm.tenant_id = check_tenant_id
      and tm.user_id = auth.uid()
  );
$$;

create or replace function public.tenant_role(check_tenant_id uuid)
returns text
language sql
stable
security definer
set search_path = public
as $$
  select tm.role
  from public.tenant_members tm
  where tm.tenant_id = check_tenant_id
    and tm.user_id = auth.uid()
  limit 1;
$$;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.tenants enable row level security;
alter table public.tenant_members enable row level security;
alter table public.sources enable row level security;
alter table public.audit_log enable row level security;

-- tenants: visible to members; only owners/admins may update. No public
-- insert/delete policy — tenant creation/removal is a service-role operation.
drop policy if exists tenants_select_own on public.tenants;
create policy tenants_select_own on public.tenants
  for select using (public.is_tenant_member(id));

drop policy if exists tenants_update_admin on public.tenants;
create policy tenants_update_admin on public.tenants
  for update using (public.tenant_role(id) in ('owner', 'admin'))
  with check (public.tenant_role(id) in ('owner', 'admin'));

-- tenant_members: visible to fellow members; only owners/admins manage membership.
drop policy if exists tenant_members_select_own_tenant on public.tenant_members;
create policy tenant_members_select_own_tenant on public.tenant_members
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists tenant_members_manage_admin on public.tenant_members;
create policy tenant_members_manage_admin on public.tenant_members
  for all using (public.tenant_role(tenant_id) in ('owner', 'admin'))
  with check (public.tenant_role(tenant_id) in ('owner', 'admin'));

-- sources: readable by any authenticated user; writes are service-role only.
drop policy if exists sources_select_authenticated on public.sources;
create policy sources_select_authenticated on public.sources
  for select using (auth.role() = 'authenticated');

-- audit_log: members may read their own tenant's log; inserts are service-role only.
drop policy if exists audit_log_select_own_tenant on public.audit_log;
create policy audit_log_select_own_tenant on public.audit_log
  for select using (public.is_tenant_member(tenant_id));
