-- ===== 20260819120700_opportunity_inbox_actions.sql =====
-- Aimfold Core — Opportunity Inbox Human Actions (PR10)
--
-- Every prior pipeline table (aim_versions, aim_signal_hypotheses,
-- entities, signals, opportunities, ...) is select-only for authenticated
-- users — populated by a backend/service-role pipeline. The Opportunity
-- Inbox (aimfold_core/inbox/) is the first place a human is actually
-- meant to write directly from the browser: approving, holding, or
-- rejecting an opportunity (AIMFOLD_MASTER_GOAL.md section 16:
-- "Humans should primarily handle: approving sensitive outreach,
-- ambiguous opportunities, ... final decisions").
--
-- This is scoped as tightly as Postgres allows:
--   1. Column-level GRANT — authenticated can only ever write
--      lifecycle_state on opportunities, not score/evidence/anything else.
--   2. RLS WITH CHECK — the new lifecycle_state value must be one of the
--      human-controlled states. A member cannot, say, set
--      lifecycle_state='high_priority' to fake a better ranking — only
--      the deterministic engine in aimfold_core/opportunity/lifecycle.py
--      (via service-role) sets score-driven states.
--   3. opportunity_lifecycle_events inserts are scoped the same way, so
--      the transition is always recorded (section 11).

grant update (lifecycle_state) on public.opportunities to authenticated;

drop policy if exists opportunities_update_lifecycle_by_member on public.opportunities;
create policy opportunities_update_lifecycle_by_member on public.opportunities
  for update using (public.is_tenant_member(tenant_id))
  with check (
    public.is_tenant_member(tenant_id)
    and lifecycle_state in ('held', 'rejected', 'actioned')
  );

drop policy if exists opportunity_lifecycle_events_insert_by_member on public.opportunity_lifecycle_events;
create policy opportunity_lifecycle_events_insert_by_member on public.opportunity_lifecycle_events
  for insert with check (
    public.is_tenant_member(tenant_id)
    and to_state in ('held', 'rejected', 'actioned')
  );

comment on policy opportunities_update_lifecycle_by_member on public.opportunities is
  'Human-in-the-loop write path for the Opportunity Inbox — restricted by column GRANT to lifecycle_state only, and by this policy to the three human-controlled target states.';
