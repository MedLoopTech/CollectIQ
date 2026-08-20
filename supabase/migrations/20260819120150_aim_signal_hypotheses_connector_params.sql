-- ===== 20260819120150_aim_signal_hypotheses_connector_params.sql =====
-- Aimfold Core — Signal Hypothesis Connector Params (PR3, schema addition)
--
-- PR2's aim_signal_hypotheses stored only a human-readable `hypothesis`
-- string. Converting CollectIQ's hardcoded scouting logic (PR3) into
-- data requires each hypothesis to also carry the structured parameters
-- its source connector needs to actually run a search (e.g. a job-board
-- connector needs {keyword, location, country}). Small additive
-- migration rather than reopening 20260819120100 so that file stays a
-- faithful record of what PR2 actually shipped.

alter table public.aim_signal_hypotheses
  add column if not exists connector_params jsonb not null default '{}'::jsonb;

comment on column public.aim_signal_hypotheses.connector_params is
  'Structured parameters this hypothesis passes to its source connector (source_key). Shape is connector-specific — for the Apify job-board connectors (linkedin_jobs_apify, indeed_jobs_apify) it is {keyword, location}.';
