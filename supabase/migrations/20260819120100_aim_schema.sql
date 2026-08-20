-- ===== 20260819120100_aim_schema.sql =====
-- Aimfold Core — Aim + AimVersion Schema (PR2)
--
-- An Aim is what a tenant wants Aimfold to continuously look for. The Aim
-- row is a stable identity; its actual executable definition (objective,
-- criteria, sources, scoring weights, thresholds, ...) lives in an
-- immutable AimVersion so historical Signal/Opportunity decisions stay
-- reproducible against the version that produced them (AIMFOLD_MASTER_GOAL.md
-- section 4, 37). The Aim Compiler that fills in compiled_spec is PR4;
-- this migration only establishes the schema it writes into.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- aims
-- ---------------------------------------------------------------------------

create table if not exists public.aims (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  name text not null,
  opportunity_type text not null
    check (opportunity_type in (
      'customer_discovery', 'career_discovery', 'funding_discovery',
      'investor_discovery', 'partnership_discovery', 'vendor_discovery',
      'market_discovery', 'acquisition_discovery', 'custom'
    )),
  status text not null default 'draft'
    check (status in ('draft', 'active', 'paused', 'archived')),
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists aims_tenant_id_idx on public.aims(tenant_id);
create index if not exists aims_status_idx on public.aims(status);

comment on table public.aims is
  'What a tenant wants Aimfold to continuously look for. Stable identity; the executable definition lives in aim_versions.';

-- ---------------------------------------------------------------------------
-- aim_versions — immutable, versioned compiled Aim definitions
-- ---------------------------------------------------------------------------

create table if not exists public.aim_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  version_number integer not null check (version_number > 0),
  is_current boolean not null default false,
  raw_user_intent text,
  compiled_spec jsonb not null default '{}'::jsonb,
  status text not null default 'proposed'
    check (status in ('proposed', 'approved', 'rejected', 'superseded')),
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  compiler_model text,
  compiler_prompt_version text,
  created_at timestamptz not null default now(),
  unique (aim_id, version_number)
);

create index if not exists aim_versions_aim_id_idx on public.aim_versions(aim_id);
create index if not exists aim_versions_tenant_id_idx on public.aim_versions(tenant_id);

-- exactly one current version per aim
create unique index if not exists aim_versions_one_current_per_aim
  on public.aim_versions(aim_id)
  where is_current;

comment on column public.aim_versions.compiled_spec is
  'Structured Aim produced by the Aim Compiler: objective, target_entity_types, geography, industries, positive_criteria, negative_criteria, exclusions, freshness_requirements, likely_sources, evidence_requirements, scoring_dimensions, scoring_weights, confidence_thresholds, likely_actions, notification_preferences. Intentionally schemaless (jsonb) here — PR4 (Aim Compiler) enforces the contract.';

comment on table public.aim_versions is
  'Immutable snapshots of an Aim''s compiled definition. Changing an Aim creates a new version rather than mutating history so past decisions stay reproducible against aim_version_id.';

-- ---------------------------------------------------------------------------
-- aim_signal_hypotheses — observable indicators a given Aim version watches for
-- ---------------------------------------------------------------------------

create table if not exists public.aim_signal_hypotheses (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  aim_version_id uuid not null references public.aim_versions(id) on delete cascade,
  hypothesis text not null,
  source_key text references public.sources(key),
  signal_type text not null,
  is_experimental boolean not null default false,
  weight numeric,
  status text not null default 'active'
    check (status in ('active', 'paused', 'retired')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists aim_signal_hypotheses_aim_version_id_idx
  on public.aim_signal_hypotheses(aim_version_id);
create index if not exists aim_signal_hypotheses_tenant_id_idx
  on public.aim_signal_hypotheses(tenant_id);

comment on table public.aim_signal_hypotheses is
  'Observable changes that might indicate an opportunity for this Aim version (e.g. "company posts an AR/collections specialist job"). is_experimental tags exploration-vs-exploitation allocation (AIMFOLD_MASTER_GOAL.md section 23).';

-- ---------------------------------------------------------------------------
-- triggers
-- ---------------------------------------------------------------------------

drop trigger if exists set_updated_at on public.aims;
create trigger set_updated_at before update on public.aims
  for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.aim_signal_hypotheses;
create trigger set_updated_at before update on public.aim_signal_hypotheses
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.aims enable row level security;
alter table public.aim_versions enable row level security;
alter table public.aim_signal_hypotheses enable row level security;

-- aims: tenant members can read/create/update their own tenant's aims.
-- No delete policy — archive via status='archived' instead, to keep
-- historical aim_versions/signals/opportunities reproducible.
drop policy if exists aims_select_own_tenant on public.aims;
create policy aims_select_own_tenant on public.aims
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists aims_insert_own_tenant on public.aims;
create policy aims_insert_own_tenant on public.aims
  for insert with check (public.is_tenant_member(tenant_id));

drop policy if exists aims_update_own_tenant on public.aims;
create policy aims_update_own_tenant on public.aims
  for update using (public.is_tenant_member(tenant_id))
  with check (public.is_tenant_member(tenant_id));

-- aim_versions: readable by tenant members. Written by the Aim Compiler /
-- approval flow (service-role) — no insert/update policy for authenticated,
-- since a version's own approval workflow (PR4) needs to validate compiled_spec
-- before it lands.
drop policy if exists aim_versions_select_own_tenant on public.aim_versions;
create policy aim_versions_select_own_tenant on public.aim_versions
  for select using (public.is_tenant_member(tenant_id));

-- aim_signal_hypotheses: readable by tenant members; generated by the
-- Signal Hypothesis Engine (service-role), not authored directly by users.
drop policy if exists aim_signal_hypotheses_select_own_tenant on public.aim_signal_hypotheses;
create policy aim_signal_hypotheses_select_own_tenant on public.aim_signal_hypotheses
  for select using (public.is_tenant_member(tenant_id));
