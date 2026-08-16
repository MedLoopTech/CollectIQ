
-- ===== supabase_schema.sql =====
-- CollectIQ Audit Intake v0.1
-- Run in Supabase SQL editor.

create extension if not exists pgcrypto;

create table if not exists public.audit_leads (
  id uuid primary key default gen_random_uuid(),
  company_name text not null,
  company_website text,
  contact_name text not null,
  work_email text not null,
  role text not null,
  accounting_system text,
  ar_size_band text,
  invoice_volume_band text,
  notes text,
  anonymized boolean not null default false,
  consent boolean not null default false,
  file_path text not null,
  file_name text not null,
  file_size bigint,
  status text not null default 'new'
    check (status in ('new','file_received','validating','needs_review','audit_ready','sent','pilot','won','lost')),
  validation_summary jsonb,
  audit_summary jsonb,
  source text not null default 'landing_page',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.audit_leads(id) on delete cascade,
  event_type text not null,
  message text,
  payload jsonb,
  created_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_audit_leads_updated_at on public.audit_leads;
create trigger trg_audit_leads_updated_at
before update on public.audit_leads
for each row execute function public.set_updated_at();

alter table public.audit_leads enable row level security;
alter table public.audit_events enable row level security;

-- Pilot policy: allow anonymous/public insert only.
-- Do NOT allow public SELECT/UPDATE/DELETE.
drop policy if exists "public_can_create_audit_lead" on public.audit_leads;
create policy "public_can_create_audit_lead"
on public.audit_leads
for insert
to anon
with check (
  consent = true
  and char_length(company_name) between 2 and 200
  and char_length(contact_name) between 2 and 200
  and char_length(work_email) between 5 and 320
  and file_path is not null
);

-- No anon policies are intentionally created for audit_events.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'ar-intake',
  'ar-intake',
  false,
  10485760,
  array[
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ]
)
on conflict (id) do update set
  public = false,
  file_size_limit = 10485760;

-- Allow anonymous uploads only into ar-intake.
-- Since the bucket is private, public cannot read uploaded files.
drop policy if exists "anon_can_upload_ar_intake" on storage.objects;
create policy "anon_can_upload_ar_intake"
on storage.objects
for insert
to anon
with check (
  bucket_id = 'ar-intake'
  and (storage.foldername(name))[1] is not null
);

-- Recommended: n8n uses the Supabase service role key server-side.
-- Never expose the service role key in the browser.


-- ===== reviewer_schema_additions.sql =====
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


-- ===== supabase_v02_additions.sql =====
alter table public.lead_prospects
  add column if not exists source_platform text,
  add column if not exists search_query text,
  add column if not exists raw_signal jsonb;

create index if not exists idx_lead_prospects_source_platform
on public.lead_prospects(source_platform);


-- ===== supabase_leadgen_schema.sql =====
-- CollectIQ lead-gen schema
create extension if not exists pgcrypto;

create table if not exists public.lead_prospects (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,

  company_name text not null,
  company_domain text,
  company_website text,

  job_title text,
  job_location text,
  posted_at text,

  source text,
  source_job_id text,
  source_url text,

  prospect_score integer,
  signals jsonb not null default '[]'::jsonb,
  fit_reason text,

  contact_email text,
  contact_first_name text,
  contact_last_name text,
  contact_position text,
  contact_confidence numeric,

  outreach_angle text,
  outreach_draft text,

  status text not null default 'new'
    check (status in ('new','reviewed','approved','contacted','replied','audit_offered','audit_received','pilot','won','lost','do_not_contact')),

  reviewer_notes text,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  contacted_at timestamptz,
  replied_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_lead_prospects_score on public.lead_prospects(prospect_score desc);
create index if not exists idx_lead_prospects_status on public.lead_prospects(status);
create index if not exists idx_lead_prospects_company on public.lead_prospects(company_name);

create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_lead_prospects_updated_at on public.lead_prospects;
create trigger trg_lead_prospects_updated_at
before update on public.lead_prospects
for each row execute function public.touch_updated_at();

alter table public.lead_prospects enable row level security;

-- Internal reviewer access only.
drop policy if exists "authenticated_read_lead_prospects" on public.lead_prospects;
create policy "authenticated_read_lead_prospects"
on public.lead_prospects for select to authenticated using (true);

drop policy if exists "authenticated_update_lead_prospects" on public.lead_prospects;
create policy "authenticated_update_lead_prospects"
on public.lead_prospects for update to authenticated using (true) with check (true);

-- n8n should use service-role credentials server-side for upserts.
