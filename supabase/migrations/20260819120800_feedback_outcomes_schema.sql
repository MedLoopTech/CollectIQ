-- ===== 20260819120800_feedback_outcomes_schema.sql =====
-- Aimfold Core — Structured Feedback + Outcomes (PR11)
--
-- AIMFOLD_MASTER_GOAL.md section 18 (Self-Improving Architecture: "Do not
-- reduce all learning to binary thumbs-up/down"), section 19 (Structured
-- Rejection Reasons), section 21 (Learning Loop: "For every Opportunity
-- retain: predicted score, ... user decision, actual action, eventual
-- outcome"). Two tables, matching the two distinct things section 18's
-- list actually contains once you separate them:
--
--   feedback  — the human's immediate decision on an Opportunity
--               (accepted/rejected/saved/ignored/...), with a structured
--               rejection_reason when rejected, and a snapshot of what
--               was predicted at that moment (not a live re-join to
--               opportunities, which could be rescored later).
--   outcomes  — downstream real-world results (meeting booked, won,
--               lost, ...), usually recorded well after the fact.
--
-- Both are append-only by policy (see RLS below) — a changed mind is new
-- feedback, not an edited row, same reasoning as aim_versions never
-- being mutated in place.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- feedback
-- ---------------------------------------------------------------------------

create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  user_id uuid references auth.users(id),

  feedback_type text not null
    check (feedback_type in (
      'accepted', 'rejected', 'saved', 'ignored', 'held', 'actioned', 'not_actioned'
    )),
  rejection_reason text
    check (rejection_reason is null or rejection_reason in (
      'wrong_entity_type', 'wrong_industry', 'wrong_geography', 'too_small', 'too_large',
      'weak_evidence', 'poor_timing', 'low_value', 'already_known', 'duplicate',
      'irrelevant_signal', 'source_unreliable', 'not_eligible', 'wrong_role',
      'wrong_seniority', 'poor_strategic_fit', 'not_actionable', 'other'
    )),
  notes text,

  -- Learning Loop snapshot (section 21) — captured AT feedback time, not
  -- re-derived by joining opportunities later, since a rescoring pipeline
  -- could change opportunities.total_score/recommended_action out from
  -- under a historical feedback record.
  predicted_total_score numeric,
  predicted_confidence numeric,
  predicted_recommended_action text,
  predicted_lifecycle_state text,
  aim_version_id uuid references public.aim_versions(id),
  scoring_version text,

  created_at timestamptz not null default now(),

  constraint feedback_rejection_reason_required check (
    (feedback_type = 'rejected' and rejection_reason is not null)
    or (feedback_type <> 'rejected' and rejection_reason is null)
  )
);

create index if not exists feedback_tenant_id_idx on public.feedback(tenant_id);
create index if not exists feedback_aim_id_idx on public.feedback(aim_id);
create index if not exists feedback_opportunity_id_idx on public.feedback(opportunity_id);
create index if not exists feedback_feedback_type_idx on public.feedback(feedback_type);

comment on table public.feedback is
  'One human decision on one Opportunity at one point in time. Append-only — a changed mind is a new row, not an edit, so the full decision history stays intact for learning/analytics (PR14+).';

-- ---------------------------------------------------------------------------
-- outcomes
-- ---------------------------------------------------------------------------

create table if not exists public.outcomes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  aim_id uuid not null references public.aims(id) on delete cascade,
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  user_id uuid references auth.users(id),

  outcome_type text not null
    check (outcome_type in (
      'positive_response', 'negative_response', 'meeting', 'application_submitted',
      'shortlisted', 'grant_awarded', 'partnership_progressed', 'investment_conversation',
      'won', 'lost', 'custom'
    )),
  monetary_value numeric check (monetary_value is null or monetary_value >= 0),
  currency text not null default 'USD',
  notes text,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists outcomes_tenant_id_idx on public.outcomes(tenant_id);
create index if not exists outcomes_aim_id_idx on public.outcomes(aim_id);
create index if not exists outcomes_opportunity_id_idx on public.outcomes(opportunity_id);
create index if not exists outcomes_outcome_type_idx on public.outcomes(outcome_type);

comment on table public.outcomes is
  'Downstream real-world results, usually recorded well after the triggering feedback (a meeting or a won/lost deal). occurred_at is when it actually happened; created_at is when Aimfold learned about it — these will often differ.';

-- ---------------------------------------------------------------------------
-- triggers (outcomes only — feedback has no updated_at, it is never updated)
-- ---------------------------------------------------------------------------

alter table public.outcomes add column if not exists updated_at timestamptz not null default now();

drop trigger if exists set_updated_at on public.outcomes;
create trigger set_updated_at before update on public.outcomes
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.feedback enable row level security;
alter table public.outcomes enable row level security;

-- feedback: tenant members can read their tenant's feedback and insert
-- their own (user_id must be their own uid) — no update/delete policy,
-- append-only by design.
drop policy if exists feedback_select_own_tenant on public.feedback;
create policy feedback_select_own_tenant on public.feedback
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists feedback_insert_own_tenant on public.feedback;
create policy feedback_insert_own_tenant on public.feedback
  for insert with check (
    public.is_tenant_member(tenant_id)
    and (user_id is null or user_id = auth.uid())
  );

-- outcomes: same read/insert pattern, plus update restricted to rows the
-- same user recorded (monetary_value/notes corrections are legitimate;
-- outcome_type/opportunity_id are not covered by any narrower column
-- grant here since, unlike PR10's lifecycle_state case, there's no
-- adjacent invariant to protect beyond "own tenant, own row").
drop policy if exists outcomes_select_own_tenant on public.outcomes;
create policy outcomes_select_own_tenant on public.outcomes
  for select using (public.is_tenant_member(tenant_id));

drop policy if exists outcomes_insert_own_tenant on public.outcomes;
create policy outcomes_insert_own_tenant on public.outcomes
  for insert with check (
    public.is_tenant_member(tenant_id)
    and (user_id is null or user_id = auth.uid())
  );

drop policy if exists outcomes_update_own_rows on public.outcomes;
create policy outcomes_update_own_rows on public.outcomes
  for update using (public.is_tenant_member(tenant_id) and user_id = auth.uid())
  with check (public.is_tenant_member(tenant_id) and user_id = auth.uid());
