-- ===== 20260819120500_opportunity_schema.sql =====
-- Aimfold Core — Opportunity Model + Clustering + Lifecycle (PR8)
--
-- AIMFOLD_MASTER_GOAL.md section 9 (Opportunity Model), section 10
-- (Temporal Opportunity Intelligence), section 11 (Opportunity
-- Lifecycle), section 12 (Opportunity Clustering: "Entity -> Opportunity
-- -> Signals" — multiple signals about the same entity should normally
-- strengthen one Opportunity, not create duplicates).
--
-- Schema only — aimfold_core/opportunity/ (this PR's code) is
-- storage-agnostic like aim_compiler/evidence/scoring before it. No
-- pipeline writes here yet.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- opportunities
-- ---------------------------------------------------------------------------

create table if not exists public.opportunities (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  aim_version_id uuid not null references public.aim_versions(id),
  primary_entity_id uuid not null references public.entities(id) on delete cascade,

  opportunity_type text not null
    check (opportunity_type in (
      'customer_discovery', 'career_discovery', 'funding_discovery',
      'investor_discovery', 'partnership_discovery', 'vendor_discovery',
      'market_discovery', 'acquisition_discovery', 'custom'
    )),

  relevance_explanation text,
  what_changed text,
  why_now text,
  why_it_matters text,
  recommended_action text
    check (recommended_action is null or recommended_action in (
      'contact', 'research', 'apply', 'save', 'monitor', 'request_introduction',
      'prepare_application', 'review_eligibility', 'engage_partner',
      'contact_investor', 'add_to_watchlist', 'ignore', 'wait_for_another_signal'
    )),

  -- Serialized aimfold_core.scoring.schema.DimensionScore list — the
  -- explainable breakdown, not just total_score. confidence/
  -- evidence_confidence/source_confidence are read off the matching
  -- ExplainableScore dimensions (see aimfold_core/opportunity/mapping.py);
  -- stored as their own columns because they're queried/filtered on
  -- directly, unlike the full breakdown.
  component_scores jsonb not null default '[]'::jsonb,
  total_score numeric not null check (total_score >= 0 and total_score <= 100),
  confidence numeric check (confidence is null or (confidence >= 0 and confidence <= 1)),
  evidence_confidence numeric check (evidence_confidence is null or (evidence_confidence >= 0 and evidence_confidence <= 1)),
  source_confidence numeric check (source_confidence is null or (source_confidence >= 0 and source_confidence <= 1)),

  lifecycle_state text not null default 'discovered'
    check (lifecycle_state in (
      'discovered', 'evaluating', 'qualified', 'high_priority', 'actioned', 'outcome',
      'held', 'rejected', 'stale', 'expired', 'revived', 'duplicate', 'invalid'
    )),
  first_detected_at timestamptz not null default now(),
  last_strengthened_at timestamptz not null default now(),
  expires_at timestamptz,

  scoring_version text,
  prompt_versions jsonb not null default '{}'::jsonb,
  model_versions jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Deliberately NOT a hard unique(tenant_id, aim_id, primary_entity_id)
-- constraint. Section 12 says signals "should normally" strengthen one
-- Opportunity per entity, not "must always" — e.g. a long-closed,
-- actioned/outcome opportunity for a company and a genuinely new,
-- unrelated episode for that same company later are both legitimate.
-- The clustering decision (aimfold_core/opportunity/clustering.py) is
-- the soft invariant; this index just makes finding candidates fast, and
-- clustering.py explicitly flags (not silently resolves) the case where
-- more than one non-terminal opportunity exists for the same entity.
create index if not exists opportunities_tenant_aim_entity_idx
  on public.opportunities(tenant_id, aim_id, primary_entity_id);
create index if not exists opportunities_tenant_id_idx on public.opportunities(tenant_id);
create index if not exists opportunities_lifecycle_state_idx on public.opportunities(lifecycle_state);
create index if not exists opportunities_total_score_idx on public.opportunities(total_score desc);
create index if not exists opportunities_last_strengthened_at_idx on public.opportunities(last_strengthened_at desc);

comment on table public.opportunities is
  'Primary business object (AIMFOLD_MASTER_GOAL.md section 9) — an Entity''s standing candidacy against an Aim, strengthened over time by Signals rather than re-created per signal (section 12).';

comment on column public.opportunities.evidence_confidence is
  'Mirrors the ExplainableScore "evidence_confidence" dimension''s raw_value at last scoring — how independently verified the evidence is, not how strong the opportunity itself is (that''s total_score).';

comment on column public.opportunities.source_confidence is
  'Mirrors the ExplainableScore "source_quality" dimension''s raw_value at last scoring. Named source_confidence here to match AIMFOLD_MASTER_GOAL.md section 9''s field list verbatim.';

-- ---------------------------------------------------------------------------
-- opportunity_signals — "Entity -> Opportunity -> Signals" clustering
-- ---------------------------------------------------------------------------

create table if not exists public.opportunity_signals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  signal_id uuid not null references public.signals(id) on delete cascade,
  contribution_note text,
  added_at timestamptz not null default now(),
  unique (opportunity_id, signal_id)
);

create index if not exists opportunity_signals_tenant_id_idx on public.opportunity_signals(tenant_id);
create index if not exists opportunity_signals_opportunity_id_idx on public.opportunity_signals(opportunity_id);
create index if not exists opportunity_signals_signal_id_idx on public.opportunity_signals(signal_id);

comment on table public.opportunity_signals is
  'Every signal that contributed to this Opportunity. A signal normally belongs to at most one Opportunity, but this is an unconstrained join table (not enforced unique on signal_id alone) in case a signal is later judged relevant to more than one Opportunity.';

-- ---------------------------------------------------------------------------
-- opportunity_entities — beyond primary_entity_id, for multi-entity Aims
-- ---------------------------------------------------------------------------

create table if not exists public.opportunity_entities (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  entity_id uuid not null references public.entities(id) on delete cascade,
  role text not null default 'primary',
  created_at timestamptz not null default now(),
  unique (opportunity_id, entity_id)
);

create index if not exists opportunity_entities_tenant_id_idx on public.opportunity_entities(tenant_id);
create index if not exists opportunity_entities_opportunity_id_idx on public.opportunity_entities(opportunity_id);
create index if not exists opportunity_entities_entity_id_idx on public.opportunity_entities(entity_id);

comment on table public.opportunity_entities is
  'Same pattern as signal_entities (PR5): opportunities.primary_entity_id covers the common single-entity case fast; use this for Aims where an opportunity genuinely involves more than one entity (e.g. Career Aim: job + employer).';

-- ---------------------------------------------------------------------------
-- opportunity_lifecycle_events — "Lifecycle transitions must be recorded"
-- ---------------------------------------------------------------------------

create table if not exists public.opportunity_lifecycle_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  from_state text,
  to_state text not null,
  reason text,
  created_at timestamptz not null default now()
);

create index if not exists opportunity_lifecycle_events_tenant_id_idx on public.opportunity_lifecycle_events(tenant_id);
create index if not exists opportunity_lifecycle_events_opportunity_id_created_at_idx
  on public.opportunity_lifecycle_events(opportunity_id, created_at desc);

comment on table public.opportunity_lifecycle_events is
  'AIMFOLD_MASTER_GOAL.md section 11: "Lifecycle transitions must be recorded." from_state is null for the event that created the opportunity.';

-- ---------------------------------------------------------------------------
-- triggers
-- ---------------------------------------------------------------------------

drop trigger if exists set_updated_at on public.opportunities;
create trigger set_updated_at before update on public.opportunities
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS — same read-only-for-authenticated pattern as entities/signals (PR5):
-- populated by a backend pipeline (service-role), not directly by users.
-- ---------------------------------------------------------------------------

alter table public.opportunities enable row level security;
alter table public.opportunity_signals enable row level security;
alter table public.opportunity_entities enable row level security;
alter table public.opportunity_lifecycle_events enable row level security;

drop policy if exists opportunities_select_own_tenant on public.opportunities;
create policy opportunities_select_own_tenant on public.opportunities
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists opportunity_signals_select_own_tenant on public.opportunity_signals;
create policy opportunity_signals_select_own_tenant on public.opportunity_signals
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists opportunity_entities_select_own_tenant on public.opportunity_entities;
create policy opportunity_entities_select_own_tenant on public.opportunity_entities
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists opportunity_lifecycle_events_select_own_tenant on public.opportunity_lifecycle_events;
create policy opportunity_lifecycle_events_select_own_tenant on public.opportunity_lifecycle_events
  for select using (public.is_tenant_member(tenant_id));
