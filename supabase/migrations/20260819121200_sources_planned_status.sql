-- ===== 20260819121200_sources_planned_status.sql =====
-- Aimfold Core — Sources: add 'planned' status (PR17, schema addition)
--
-- PR17 (third Horizontal Validation Aim, section 41) needs to register a
-- Funding/Grant Discovery source connector (e.g. a grants-database
-- scraper) that has no working implementation yet — this repo has no
-- Apify actor (or equivalent) for grant listings the way it does for
-- LinkedIn/Indeed job postings, and one should not be fabricated. The
-- 'Filter before paid acquisition' / 'Qualify before expensive
-- enrichment' rules added to AIMFOLD_MASTER_GOAL.md's Pipeline Cost &
-- Evidence Discipline section argue directly against wiring up a paid
-- connector before the Aim structure around it is even validated.
--
-- 'disabled' (the existing status for a connector that was working and
-- got turned off) would misrepresent this: it was never wired up in the
-- first place. 'planned' names that state honestly — registered in the
-- catalog, not yet implemented, not currently expected to run.
--
-- Small additive migration rather than reopening 20260819120000, same
-- rationale as 20260819120150 (keep that file a faithful record of what
-- PR1 actually shipped).

alter table public.sources drop constraint if exists sources_status_check;
alter table public.sources add constraint sources_status_check
  check (status in ('active', 'disabled', 'deprecated', 'planned'));

comment on column public.sources.status is
  '''active'': in use. ''disabled'': was in use, turned off. ''deprecated'': superseded, kept for historical FK integrity. ''planned'': registered in the catalog for an Aim that wants it, no working connector implementation yet (added PR17).';
