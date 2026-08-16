-- Reviewer dashboard additions
alter table public.audit_leads
  add column if not exists reviewer_notes text,
  add column if not exists reviewed_at timestamptz,
  add column if not exists sent_at timestamptz;

-- IMPORTANT:
-- The reviewer dashboard must NOT use the anonymous key in production unless
-- protected by Supabase Auth and RLS. The following policy assumes authenticated
-- users only and should be restricted further for production.

drop policy if exists "authenticated_can_read_audit_leads" on public.audit_leads;
create policy "authenticated_can_read_audit_leads"
on public.audit_leads
for select
to authenticated
using (true);

drop policy if exists "authenticated_can_update_audit_leads" on public.audit_leads;
create policy "authenticated_can_update_audit_leads"
on public.audit_leads
for update
to authenticated
using (true)
with check (true);
