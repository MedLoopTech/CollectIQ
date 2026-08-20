-- ===== 20260819121000_learning_proposals_schema.sql =====
-- Aimfold Core — Controlled Improvement Proposals (PR15)
--
-- AIMFOLD_MASTER_GOAL.md section 22 (Safe Self-Improvement): "Aimfold
-- must not freely rewrite production behavior. Use: Observe -> Measure
-- -> Propose -> Test -> Promote. Every proposed change should include:
-- current behavior, proposed behavior, supporting observations, affected
-- Aims, sample size, expected impact, evaluation results, possible
-- regressions, rollback path." learning_proposals is section 36's named
-- core-domain table for exactly this.
--
-- scoring_versions also lands here, closing a gap PR7 deliberately left
-- open: "Deliberately NOT built in this PR: a scoring_versions table...
-- there's no learning/proposal engine yet to promote anything through
-- it (that's PR15)." A promoted 'adjust_scoring_weight' proposal is
-- exactly what would create a new scoring_versions row.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- scoring_versions — persisted, promotable ScoringWeights per Aim
-- ---------------------------------------------------------------------------

create table if not exists public.scoring_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  weights jsonb not null,
  is_current boolean not null default false,
  source_proposal_id uuid,  -- FK added after learning_proposals exists below
  created_at timestamptz not null default now()
);

create index if not exists scoring_versions_tenant_id_idx on public.scoring_versions(tenant_id);
create index if not exists scoring_versions_aim_id_idx on public.scoring_versions(aim_id);

-- exactly one current scoring_version per aim, same pattern as
-- aim_versions_one_current_per_aim (20260819120100_aim_schema.sql)
create unique index if not exists scoring_versions_one_current_per_aim
  on public.scoring_versions(aim_id)
  where is_current;

comment on table public.scoring_versions is
  'Persisted aimfold_core.scoring.schema.ScoringWeights per Aim, versioned. Absent a row here, callers use DEFAULT_SCORING_WEIGHTS (section 13''s starting 20/25/20/15/10/5/5) — this table only exists once an Aim''s weights have actually been customized via an approved learning_proposal.';

-- ---------------------------------------------------------------------------
-- learning_proposals
-- ---------------------------------------------------------------------------

create table if not exists public.learning_proposals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  aim_version_id uuid not null references public.aim_versions(id),

  proposal_type text not null
    check (proposal_type in ('add_exclusion', 'adjust_scoring_weight')),

  -- section 22's required fields, verbatim
  current_behavior text not null,
  proposed_behavior text not null,
  supporting_observations jsonb not null default '{}'::jsonb,
  affected_aims uuid[] not null,
  sample_size integer not null check (sample_size >= 0),
  expected_impact text not null,
  evaluation_results jsonb,
  possible_regressions jsonb,
  rollback_path text not null,

  -- the actual candidate change, in a form the corresponding module can
  -- apply directly (exactly one of these is set, matching proposal_type)
  proposed_compiled_spec jsonb,
  proposed_scoring_weights jsonb,

  status text not null default 'proposed'
    check (status in ('proposed', 'tested', 'approved', 'rejected', 'promoted', 'superseded')),
  decided_by uuid references auth.users(id),
  decided_at timestamptz,
  created_at timestamptz not null default now(),

  constraint learning_proposals_exactly_one_candidate check (
    (proposal_type = 'add_exclusion' and proposed_compiled_spec is not null and proposed_scoring_weights is null)
    or (proposal_type = 'adjust_scoring_weight' and proposed_scoring_weights is not null and proposed_compiled_spec is null)
  )
);

alter table public.scoring_versions
  add constraint scoring_versions_source_proposal_id_fkey
  foreign key (source_proposal_id) references public.learning_proposals(id);

create index if not exists learning_proposals_tenant_id_idx on public.learning_proposals(tenant_id);
create index if not exists learning_proposals_aim_id_idx on public.learning_proposals(aim_id);
create index if not exists learning_proposals_status_idx on public.learning_proposals(status);

comment on table public.learning_proposals is
  'AIMFOLD_MASTER_GOAL.md section 22: Observe -> Measure -> Propose -> Test -> Promote. Nothing here is ever auto-applied — approval (status=''approved'') is a human decision, and promotion (status=''promoted'', which actually writes a new aim_versions or scoring_versions row) is a separate, still-manual step. See aimfold_core/proposals/.';

comment on column public.learning_proposals.affected_aims is
  'Usually just [aim_id] — modeled as an array because section 22 says "affected Aims" (plural); a future cross-Aim proposal (e.g. a source_effectiveness finding that generalizes) could legitimately name more than one.';

-- No updated_at trigger on either table. scoring_versions is immutable
-- once created (new weights are a new row, never an edit), same as
-- aim_versions. learning_proposals is append-only except for the one
-- narrow, intentional exception below (status/decided_by/decided_at,
-- the human review step) — everything else about a proposal (its
-- evaluation, its candidate spec/weights) never changes after creation.

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.scoring_versions enable row level security;
alter table public.learning_proposals enable row level security;

-- scoring_versions: read-only for authenticated, same as aim_versions —
-- written by the promotion step (service-role) once a proposal is approved.
drop policy if exists scoring_versions_select_own_tenant on public.scoring_versions;
create policy scoring_versions_select_own_tenant on public.scoring_versions
  for select using (public.is_tenant_member(tenant_id));

-- learning_proposals: tenant members can read every proposal for their
-- tenant (a future proposals-review UI, same shape as PR10's inbox).
drop policy if exists learning_proposals_select_own_tenant on public.learning_proposals;
create policy learning_proposals_select_own_tenant on public.learning_proposals
  for select using (public.is_tenant_member(tenant_id));

-- Human review is a column-scoped write, same pattern as PR10's
-- opportunities.lifecycle_state: authenticated can only ever move status
-- into 'approved' or 'rejected' — proposing, testing, and promoting are
-- all backend/service-role actions. REVOKE first — see the extended
-- comment in 20260819120700_opportunity_inbox_actions.sql for why a
-- column-level GRANT alone doesn't narrow a pre-existing table-wide one
-- (confirmed live: without this REVOKE, `authenticated` could still
-- write proposed_scoring_weights/proposed_compiled_spec in the same
-- request that legitimately updates status).
revoke update on public.learning_proposals from authenticated;
grant update (status, decided_by, decided_at) on public.learning_proposals to authenticated;

drop policy if exists learning_proposals_decide_by_member on public.learning_proposals;
create policy learning_proposals_decide_by_member on public.learning_proposals
  for update using (public.is_tenant_member(tenant_id))
  with check (
    public.is_tenant_member(tenant_id)
    and status in ('approved', 'rejected')
  );
