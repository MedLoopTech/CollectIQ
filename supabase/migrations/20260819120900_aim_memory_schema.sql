-- ===== 20260819120900_aim_memory_schema.sql =====
-- Aimfold Core — Aim Memory (PR12)
--
-- AIMFOLD_MASTER_GOAL.md section 26 (Aim Memory): "Each Aim should
-- maintain its own learning context: accepted patterns, rejected
-- patterns, high-value evidence, weak evidence, successful actions,
-- failed actions, preferred entity attributes, learned exclusions,
-- timing patterns, source effectiveness. Aim Memory must be version-
-- aware." No table name is specified there or in section 36's core
-- domain list, so this follows entity_memory's (PR5) shape, adapted:
-- entity_memory is an append-only journal of individual observed facts;
-- aim_memory instead holds RECOMPUTED AGGREGATE SNAPSHOTS (each
-- memory_type is a statistic derived from all feedback so far, not a
-- single event) — still append-only (a fresh computation inserts a new
-- row rather than overwriting), so "get the current picture" is "most
-- recent row per (aim_id, memory_type)" and history of how the
-- aggregate has shifted over time is preserved for free.

create extension if not exists pgcrypto;

create table if not exists public.aim_memory (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  aim_version_id uuid not null references public.aim_versions(id),
  memory_type text not null
    check (memory_type in (
      'accepted_pattern', 'rejected_pattern', 'high_value_evidence', 'weak_evidence',
      'successful_action', 'failed_action', 'preferred_entity_attribute',
      'learned_exclusion', 'timing_pattern', 'source_effectiveness'
    )),
  payload jsonb not null default '{}'::jsonb,
  sample_size integer not null default 0 check (sample_size >= 0),
  computed_at timestamptz not null default now()
);

create index if not exists aim_memory_tenant_id_idx on public.aim_memory(tenant_id);
create index if not exists aim_memory_aim_id_type_computed_at_idx
  on public.aim_memory(aim_id, memory_type, computed_at desc);

comment on table public.aim_memory is
  'Versioned aggregate snapshots of what an Aim has learned from its accumulated feedback (AIMFOLD_MASTER_GOAL.md section 26). "Version-aware" via aim_version_id (which AimVersion was current when this snapshot was computed) and via computed_at (append-only history of how the aggregate has shifted). Query the max(computed_at) row per (aim_id, memory_type) for the current picture.';

comment on column public.aim_memory.sample_size is
  'How many feedback rows fed this computation — a transparency/confidence signal so a low-sample-size snapshot (e.g. sample_size=2) isn''t weighted the same as a mature one.';

-- ---------------------------------------------------------------------------
-- RLS — same read-only-for-authenticated pattern as entity_memory (PR5):
-- populated by a backend analytics job (service-role), not written to
-- directly by users.
-- ---------------------------------------------------------------------------

alter table public.aim_memory enable row level security;

drop policy if exists aim_memory_select_own_tenant on public.aim_memory;
create policy aim_memory_select_own_tenant on public.aim_memory
  for select using (public.is_tenant_member(tenant_id));
