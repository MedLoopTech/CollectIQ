alter table public.lead_prospects
  add column if not exists source_platform text,
  add column if not exists search_query text,
  add column if not exists raw_signal jsonb;

create index if not exists idx_lead_prospects_source_platform
on public.lead_prospects(source_platform);
