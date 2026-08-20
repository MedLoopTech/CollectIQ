-- ===== 20260819120300_entity_signal_schema.sql =====
-- Aimfold Core — Generic Entity + Signal Schema (PR5)
--
-- AIMFOLD_MASTER_GOAL.md section 5 (Generic Entity Model) and section 7
-- (Signal Model). Entities generalize "company" to any opportunity
-- participant (job, employer, investor, grant, person, ...); Signals
-- generalize CollectIQ's lead_prospects rows to any observable change
-- relevant to an Aim, from any source connector.
--
-- Schema only — this does NOT yet migrate 06_leadgen_apify's v0.3
-- workflow off lead_prospects, and does not backfill existing
-- lead_prospects rows into entities/signals. That cutover belongs with
-- evidence extraction (PR6) / the scoring engine (PR7), once there's
-- somewhere meaningful for extracted_evidence and Stage-2 evaluation to
-- write. lead_prospects keeps working exactly as it does today until then.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- entities
-- ---------------------------------------------------------------------------

create table if not exists public.entities (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  entity_type text not null
    check (entity_type in (
      'company', 'organization', 'job', 'employer', 'investor', 'investment_fund',
      'grant', 'funding_program', 'government_body', 'nonprofit', 'person',
      'partner', 'vendor', 'product', 'market', 'tender', 'project', 'other'
    )),
  name text not null,
  domain text,
  external_ids jsonb not null default '{}'::jsonb,
  attributes jsonb not null default '{}'::jsonb,
  fingerprint text not null,
  status text not null default 'active'
    check (status in ('active', 'merged', 'archived')),
  merged_into_entity_id uuid references public.entities(id),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, fingerprint)
);

create index if not exists entities_tenant_id_idx on public.entities(tenant_id);
create index if not exists entities_entity_type_idx on public.entities(entity_type);
create index if not exists entities_domain_idx on public.entities(domain);

comment on table public.entities is
  'Generic opportunity participant — company, job, investor, grant, person, etc. (AIMFOLD_MASTER_GOAL.md section 5). fingerprint is a deterministic dedup key whose composition is entity_type-specific (e.g. lower(name)+domain for company); computing it is a connector/normalizer responsibility, not enforced here.';

comment on column public.entities.merged_into_entity_id is
  'Set when this entity was identified as a duplicate of another and merged — prefer this over deleting rows so existing signals/opportunities referencing the old id stay resolvable.';

-- ---------------------------------------------------------------------------
-- entity_relationships — generic edges between entities
-- ---------------------------------------------------------------------------

create table if not exists public.entity_relationships (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  from_entity_id uuid not null references public.entities(id) on delete cascade,
  to_entity_id uuid not null references public.entities(id) on delete cascade,
  relationship_type text not null,
  attributes jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (tenant_id, from_entity_id, to_entity_id, relationship_type)
);

create index if not exists entity_relationships_tenant_id_idx on public.entity_relationships(tenant_id);
create index if not exists entity_relationships_from_entity_id_idx on public.entity_relationships(from_entity_id);
create index if not exists entity_relationships_to_entity_id_idx on public.entity_relationships(to_entity_id);

comment on table public.entity_relationships is
  'E.g. job -[employed_by]-> employer, fund -[managed_by]-> partner (AIMFOLD_MASTER_GOAL.md section 5 examples). relationship_type is free text by design — a fixed enum would need a migration every time a new Aim type introduces a new relationship shape.';

-- ---------------------------------------------------------------------------
-- entity_memory — append-only journal of notable facts/changes about an entity
-- ---------------------------------------------------------------------------

create table if not exists public.entity_memory (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  entity_id uuid not null references public.entities(id) on delete cascade,
  memory_type text not null,
  payload jsonb not null default '{}'::jsonb,
  recorded_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists entity_memory_tenant_id_idx on public.entity_memory(tenant_id);
create index if not exists entity_memory_entity_id_recorded_at_idx on public.entity_memory(entity_id, recorded_at desc);

comment on table public.entity_memory is
  'AIMFOLD_MASTER_GOAL.md section 25: persistent context about a previously observed entity. Deliberately NOT a duplicate of signals/opportunities/feedback history (those remain queryable directly) — this is for derived, notable facts a Research/Learning agent chooses to record (e.g. "switched ERP systems in Q2"), not a mirror of every row.';

-- ---------------------------------------------------------------------------
-- signals
-- ---------------------------------------------------------------------------

create table if not exists public.signals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  aim_version_id uuid not null references public.aim_versions(id),
  signal_hypothesis_id uuid references public.aim_signal_hypotheses(id),
  entity_id uuid not null references public.entities(id) on delete cascade,
  signal_type text not null,
  title text,
  description text,
  source_key text not null references public.sources(key),
  source_url text,
  source_record_id text,
  published_at timestamptz,
  discovered_at timestamptz not null default now(),
  raw_payload jsonb,
  normalized_text text,
  extracted_evidence jsonb not null default '[]'::jsonb,
  source_quality numeric,
  confidence numeric,
  fingerprint text not null,
  freshness text
    check (freshness is null or freshness in ('fresh', 'stale')),
  status text not null default 'new'
    check (status in ('new', 'processed', 'qualified', 'discarded', 'duplicate', 'error')),
  connector_version text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, fingerprint)
);

create index if not exists signals_tenant_id_idx on public.signals(tenant_id);
create index if not exists signals_aim_id_idx on public.signals(aim_id);
create index if not exists signals_aim_version_id_idx on public.signals(aim_version_id);
create index if not exists signals_entity_id_idx on public.signals(entity_id);
create index if not exists signals_status_idx on public.signals(status);
create index if not exists signals_discovered_at_idx on public.signals(discovered_at desc);
create index if not exists signals_source_key_idx on public.signals(source_key);

comment on table public.signals is
  'Normalized observation from any source connector (AIMFOLD_MASTER_GOAL.md section 7). aim_version_id and connector_version are denormalized snapshots of which AimVersion/connector produced this signal, for reproducibility (section 37) even after the Aim or connector changes later. entity_id is the signal''s primary entity; use signal_entities for additional related entities (e.g. a job-posting signal that is also about its employer entity).';

comment on column public.signals.extracted_evidence is
  'Structured, inspectable evidence — e.g. [{"pattern": "...", "label": "...", "matched_text": "..."}] for a Stage-1 keyword match, richer shapes once PR6 (Evidence extraction and provenance) adds an evaluator. Never fabricated: only what was actually matched/observed goes here.';

comment on column public.signals.status is
  'Signal processing lifecycle (new -> processed -> qualified/discarded/duplicate/error), distinct from an Opportunity''s lifecycle (PR8).';

-- ---------------------------------------------------------------------------
-- signal_entities — additional entities a signal relates to beyond entity_id
-- ---------------------------------------------------------------------------

create table if not exists public.signal_entities (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  signal_id uuid not null references public.signals(id) on delete cascade,
  entity_id uuid not null references public.entities(id) on delete cascade,
  role text not null default 'related',
  created_at timestamptz not null default now(),
  unique (signal_id, entity_id)
);

create index if not exists signal_entities_tenant_id_idx on public.signal_entities(tenant_id);
create index if not exists signal_entities_signal_id_idx on public.signal_entities(signal_id);
create index if not exists signal_entities_entity_id_idx on public.signal_entities(entity_id);

comment on table public.signal_entities is
  'Use for Aims where one signal genuinely involves multiple entities (AIMFOLD_MASTER_GOAL.md section 5''s Career Aim example: a job-posting signal relates to both a job entity and an employer entity). Not required for the common single-entity case — signals.entity_id already covers that.';

-- ---------------------------------------------------------------------------
-- triggers
-- ---------------------------------------------------------------------------

drop trigger if exists set_updated_at on public.entities;
create trigger set_updated_at before update on public.entities
  for each row execute function public.set_updated_at();

drop trigger if exists set_updated_at on public.signals;
create trigger set_updated_at before update on public.signals
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.entities enable row level security;
alter table public.entity_relationships enable row level security;
alter table public.entity_memory enable row level security;
alter table public.signals enable row level security;
alter table public.signal_entities enable row level security;

-- All five are populated by source connectors / evidence-evaluation /
-- research agents (service-role), same as aim_versions and
-- aim_signal_hypotheses — tenant members get read-only access here until
-- there's a reviewed, audited edit flow (e.g. correcting an entity's
-- name) worth exposing directly.
drop policy if exists entities_select_own_tenant on public.entities;
create policy entities_select_own_tenant on public.entities
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists entity_relationships_select_own_tenant on public.entity_relationships;
create policy entity_relationships_select_own_tenant on public.entity_relationships
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists entity_memory_select_own_tenant on public.entity_memory;
create policy entity_memory_select_own_tenant on public.entity_memory
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists signals_select_own_tenant on public.signals;
create policy signals_select_own_tenant on public.signals
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists signal_entities_select_own_tenant on public.signal_entities;
create policy signal_entities_select_own_tenant on public.signal_entities
  for select using (public.is_tenant_member(tenant_id));
