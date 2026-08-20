-- ===== 20260819121500_security_hardening.sql =====
-- Aimfold Core — Security and Multi-Tenant Hardening (PR19)
--
-- AIMFOLD_MASTER_GOAL.md section 31 (Multi-Tenant Production Architecture)
-- and section 33 (Security). Not new features — a systematic audit of
-- every RLS policy and grant this dev sequence has shipped so far
-- (all 22 tables across PR1-18), in the same spirit that found PR15's
-- column-GRANT-without-REVOKE bug: read every policy asking "what could
-- an authenticated member actually write that this policy doesn't
-- intend to allow," then live-test the answer with a real Postgres role
-- rather than trust the SQL by inspection alone.
--
-- Three real, narrow gaps found this way (none previously known or
-- flagged — see each section below for the live attack-scenario test
-- that proves both the exploit and the fix):
--
--   1. tenant_members: an 'admin' could promote anyone (including
--      themselves) to 'owner', or edit/remove an existing owner's row —
--      a privilege-escalation path role-based access is supposed to
--      prevent (section 31: "role-based access").
--   2. learning_proposals: the decide-a-proposal policy never checked
--      that decided_by equals the acting user's own id — anyone
--      deciding a proposal could attribute that decision to an
--      arbitrary uuid, corrupting the one thing decided_by exists to
--      record.
--   3. feedback/outcomes: PR11's original design comment (still visible
--      in 20260819120800_feedback_outcomes_schema.sql, lines ~139-143)
--      explicitly reasoned "no adjacent invariant to protect beyond own
--      tenant, own row" — true for tenant_id, but opportunity_id/aim_id
--      were never checked to actually belong to that same tenant. A
--      member of two tenants (a normal, supported multi-tenant scenario
--      per section 31) could attach a fabricated feedback/outcome row to
--      another tenant's opportunity, corrupting that tenant's PR14/PR18
--      cost and outcome analytics.
--
-- Also closes the actual "audit logging" requirement (sections 31, 33):
-- `audit_log` (PR1) has existed since the very first migration with a
-- select policy and a comment saying "inserts are service-role only" —
-- and nothing, anywhere in this codebase, has ever inserted into it.
-- Rather than open it to direct client writes (which a buggy or
-- malicious client could simply skip), two SECURITY DEFINER triggers
-- populate it automatically from the two genuinely administrative
-- write paths that exist today: tenant_members changes, and
-- learning_proposals decisions. This is tamper-resistant in a way an
-- application-level "also call this insert" convention isn't — the
-- audit row gets written even if a future UI, script, or raw API call
-- makes the underlying change and forgets to log it.
--
-- Deliberately NOT done here (see section headers in aimfold_core/README.md
-- for the full reasoning): rate limiting and secure webhook validation
-- need an API gateway/edge-function layer that doesn't exist in this
-- repo yet (today's only write surface is PostgREST + RLS directly);
-- building either now would mean nothing real enforces them.

-- ---------------------------------------------------------------------------
-- Finding 1: tenant_members privilege escalation to 'owner'
-- ---------------------------------------------------------------------------
-- Before this fix: `tenant_members_manage_admin` only checked the
-- ACTOR's role (owner/admin), never what row they were creating/editing/
-- removing. Live-tested: an 'admin' could insert a new row with
-- role='owner' (for themselves or anyone), update an existing member's
-- role to 'owner', or delete an existing owner's membership row
-- entirely. Fix: an admin (not owner) may still manage member/viewer/
-- admin rows, but any row that currently has role='owner', OR is being
-- assigned role='owner', requires the actor to already be 'owner'.

drop policy if exists tenant_members_manage_admin on public.tenant_members;
create policy tenant_members_manage_admin on public.tenant_members
  for all
  using (
    public.tenant_role(tenant_id) in ('owner', 'admin')
    and (role != 'owner' or public.tenant_role(tenant_id) = 'owner')
  )
  with check (
    public.tenant_role(tenant_id) in ('owner', 'admin')
    and (role != 'owner' or public.tenant_role(tenant_id) = 'owner')
  );

-- ---------------------------------------------------------------------------
-- Finding 2: learning_proposals decision-attribution spoofing
-- ---------------------------------------------------------------------------
-- Before this fix: `decided_by` was writable to ANY uuid (or left null)
-- when a member moved status to approved/rejected — nothing required it
-- to be their own id. Fix: WITH CHECK now requires decided_by = auth.uid().

drop policy if exists learning_proposals_decide_by_member on public.learning_proposals;
create policy learning_proposals_decide_by_member on public.learning_proposals
  for update using (public.is_tenant_member(tenant_id))
  with check (
    public.is_tenant_member(tenant_id)
    and status in ('approved', 'rejected')
    and decided_by = auth.uid()
  );

-- ---------------------------------------------------------------------------
-- Finding 3: feedback/outcomes cross-tenant opportunity_id/aim_id reassignment
-- ---------------------------------------------------------------------------
-- Shared helper, same pattern as is_tenant_member()/tenant_role(): not
-- security definer, on purpose — opportunities/aims already carry a
-- select policy gated on is_tenant_member(), and check_tenant_id here is
-- always a tenant the actor already belongs to (validated separately by
-- the calling policy's own is_tenant_member(tenant_id) check), so the
-- natural RLS-filtered visibility this function runs under is exactly
-- the check we want — if RLS would hide the row, the row doesn't count
-- as belonging to that tenant, which is the safe/deny-by-default answer.

create or replace function public.opportunity_and_aim_belong_to_tenant(
  check_opportunity_id uuid, check_aim_id uuid, check_tenant_id uuid
)
returns boolean
language sql
stable
as $$
  select
    exists (select 1 from public.opportunities o where o.id = check_opportunity_id and o.tenant_id = check_tenant_id)
    and exists (select 1 from public.aims a where a.id = check_aim_id and a.tenant_id = check_tenant_id);
$$;

comment on function public.opportunity_and_aim_belong_to_tenant is
  'Used by feedback/outcomes INSERT/UPDATE policies to stop a member of tenant A from attaching a feedback/outcome row to tenant B''s opportunity or aim, even when they legitimately belong to both tenants (PR19 hardening finding 3).';

drop policy if exists feedback_insert_own_tenant on public.feedback;
create policy feedback_insert_own_tenant on public.feedback
  for insert with check (
    public.is_tenant_member(tenant_id)
    and (user_id is null or user_id = auth.uid())
    and public.opportunity_and_aim_belong_to_tenant(opportunity_id, aim_id, tenant_id)
  );

drop policy if exists outcomes_insert_own_tenant on public.outcomes;
create policy outcomes_insert_own_tenant on public.outcomes
  for insert with check (
    public.is_tenant_member(tenant_id)
    and (user_id is null or user_id = auth.uid())
    and public.opportunity_and_aim_belong_to_tenant(opportunity_id, aim_id, tenant_id)
  );

drop policy if exists outcomes_update_own_rows on public.outcomes;
create policy outcomes_update_own_rows on public.outcomes
  for update using (public.is_tenant_member(tenant_id) and user_id = auth.uid())
  with check (
    public.is_tenant_member(tenant_id)
    and user_id = auth.uid()
    and public.opportunity_and_aim_belong_to_tenant(opportunity_id, aim_id, tenant_id)
  );

-- ---------------------------------------------------------------------------
-- audit_log: populate it for real, via triggers (not client inserts)
-- ---------------------------------------------------------------------------

create or replace function public.audit_tenant_members_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'DELETE' then
    insert into public.audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
    values (old.tenant_id, auth.uid(), 'tenant_member_removed', 'tenant_members', old.id,
      jsonb_build_object('removed_user_id', old.user_id, 'removed_role', old.role));
    return old;
  elsif tg_op = 'UPDATE' then
    insert into public.audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
    values (new.tenant_id, auth.uid(), 'tenant_member_role_changed', 'tenant_members', new.id,
      jsonb_build_object('user_id', new.user_id, 'old_role', old.role, 'new_role', new.role));
    return new;
  else
    insert into public.audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
    values (new.tenant_id, auth.uid(), 'tenant_member_added', 'tenant_members', new.id,
      jsonb_build_object('user_id', new.user_id, 'role', new.role));
    return new;
  end if;
end;
$$;

comment on function public.audit_tenant_members_change is
  'SECURITY DEFINER so it can write to audit_log despite authenticated having no direct INSERT grant there (audit_log stays writable only via triggers, not client code — a client that skips logging still gets logged). auth.uid() inside a SECURITY DEFINER function still reflects the real calling user (it reads the session-level JWT claim, unaffected by function ownership), so actor_user_id is accurate, not the function owner.';

drop trigger if exists tenant_members_audit on public.tenant_members;
create trigger tenant_members_audit
  after insert or update or delete on public.tenant_members
  for each row execute function public.audit_tenant_members_change();

create or replace function public.audit_learning_proposal_decision()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if new.status in ('approved', 'rejected') and new.status is distinct from old.status then
    insert into public.audit_log (tenant_id, actor_user_id, action, target_type, target_id, metadata)
    values (new.tenant_id, auth.uid(), 'learning_proposal_' || new.status, 'learning_proposals', new.id,
      jsonb_build_object('proposal_type', new.proposal_type, 'decided_by', new.decided_by));
  end if;
  return new;
end;
$$;

drop trigger if exists learning_proposals_decision_audit on public.learning_proposals;
create trigger learning_proposals_decision_audit
  after update on public.learning_proposals
  for each row execute function public.audit_learning_proposal_decision();

-- opportunities.lifecycle_state (PR10) and feedback (PR11) already have
-- purpose-built audit trails (opportunity_lifecycle_events,
-- feedback itself is already an immutable decision record) — a third,
-- generic audit_log row for the same event would just be duplicate data
-- with no new information, so they deliberately don't also trigger here.
