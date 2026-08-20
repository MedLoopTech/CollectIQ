-- ===== 20260819121300_seed_funding_discovery_aim.sql =====
-- Aimfold Core — Third Validation Aim: Funding/Grant Discovery (PR17)
--
-- AIMFOLD_MASTER_GOAL.md section 41 (Horizontal Validation): three
-- materially different Aims must operate on the same core engine with
-- zero engine code changes. This is Aim 3 (Funding Discovery), closing
-- out the section's minimum requirement (Aim 1 = CollectIQ,
-- 20260819120200; Aim 2 = Career Discovery, 20260819121100).
--
-- Zero aimfold_core/*.py files changed to produce this, same as PR16 —
-- that is the actual test this PR exists to pass. Everything here is
-- DATA: a new tenant, one Aim, one AimVersion whose compiled_spec is the
-- real, live, unedited output of aimfold_core/aim_compiler (PR4) given
-- the exact "Funding Aim" example from AIMFOLD_MASTER_GOAL.md section 3:
-- "Find active grants relevant to climate-health infrastructure in
-- emerging markets." One new source connector (registered 'planned', not
-- 'active' — see 20260819121200's header for why: no grant-database
-- scraper exists in this repo, and one should not be fabricated just to
-- exercise this seed).
--
-- Compare against the other two Aims on every axis section 41 cares
-- about: opportunity_type ('funding_discovery', not
-- 'customer_discovery'/'career_discovery'), target_entity_types
-- (['grant','funding_program','organization'], not ['company'] or
-- ['job','employer']), scoring_weights vocabulary (grant/climate/health
-- keywords, zero overlap with either other Aim), likely_actions
-- (['review_eligibility','prepare_application','apply','save'], not
-- ['contact'] or ['apply','research','save']), and
-- confidence_thresholds.qualified_signal_min_score (70 — meaningfully
-- higher than CollectIQ's and Career Discovery's 40/50, proving
-- thresholds are read from compiled_spec per-Aim, not hardcoded anywhere
-- in the scoring engine).
--
-- A clearly-labeled validation tenant, not a real customer — see the
-- name/slug below.

-- ---------------------------------------------------------------------------
-- source connector — registered 'planned', see 20260819121200
-- ---------------------------------------------------------------------------

insert into public.sources (id, key, name, connector_type, connector_version, status, config_schema)
values (
  'a1000000-0000-4000-8000-000000000003',
  'grants_database_web_search',
  'Grant/Funding Database Search (not yet implemented)',
  'web_search',
  '0.0.0',
  'planned',
  '{"keyword": "string", "region": "string", "sector": "string"}'::jsonb
)
on conflict (key) do update set
  name = excluded.name,
  connector_type = excluded.connector_type,
  status = excluded.status,
  config_schema = excluded.config_schema;

-- ---------------------------------------------------------------------------
-- tenant
-- ---------------------------------------------------------------------------

insert into public.tenants (id, name, slug, status)
values (
  '77777777-7777-4777-8777-777777777777',
  'Funding Discovery (Horizontal Validation Aim #3)',
  'funding-discovery-validation',
  'active'
)
on conflict (id) do update set
  name = excluded.name,
  status = excluded.status;

-- ---------------------------------------------------------------------------
-- aim
-- ---------------------------------------------------------------------------

insert into public.aims (id, tenant_id, name, opportunity_type, status)
values (
  '88888888-8888-4888-8888-888888888888',
  '77777777-7777-4777-8777-777777777777',
  'Climate-Health Infrastructure Grants',
  'funding_discovery',
  'active'
)
on conflict (id) do update set
  name = excluded.name,
  opportunity_type = excluded.opportunity_type,
  status = excluded.status;

-- ---------------------------------------------------------------------------
-- aim version 1 — the real, unedited output of a live aimfold_core.aim_compiler
-- run (gemini-flash-lite-latest) against AIMFOLD_MASTER_GOAL.md section 3's
-- own Funding Aim example. Not hand-tuned.
-- ---------------------------------------------------------------------------

insert into public.aim_versions (
  id, tenant_id, aim_id, version_number, is_current, raw_user_intent,
  compiled_spec, status, compiler_model, compiler_prompt_version
)
values (
  '99999999-9999-4999-8999-999999999999',
  '77777777-7777-4777-8777-777777777777',
  '88888888-8888-4888-8888-888888888888',
  1,
  true,
  $intent$Find active grants relevant to climate-health infrastructure in emerging markets.$intent$,
  $spec${
    "objective": "Find active grants relevant to climate-health infrastructure in emerging markets",
    "opportunity_type": "funding_discovery",
    "target_entity_types": ["grant", "funding_program", "organization"],
    "geography": ["emerging markets"],
    "industries": ["Climate Change", "Healthcare", "Infrastructure"],
    "positive_criteria": [
      "opportunity is an active grant or funding program",
      "focuses on climate change impacts on health or health infrastructure",
      "targets emerging markets or developing economies"
    ],
    "negative_criteria": [],
    "exclusions": [],
    "freshness_requirements": "Active and currently accepting applications",
    "likely_sources": [
      "grant databases",
      "philanthropic foundation websites",
      "multilateral development bank portals"
    ],
    "evidence_requirements": [
      "explicit mention of grant funding",
      "reference to climate and health or resilient health infrastructure",
      "geographic eligibility including emerging markets"
    ],
    "scoring_dimensions": [
      "relevance to climate-health",
      "geographic alignment",
      "funding type (grant)"
    ],
    "scoring_weights": [
      {"pattern": "grant|funding opportunity|call for proposals|request for applications", "points": 40, "label": "Grant Mechanism"},
      {"pattern": "climate|resilience|adaptation|mitigation|carbon", "points": 30, "label": "Climate Focus"},
      {"pattern": "health|healthcare|hospital|public health|clinic", "points": 30, "label": "Health Infrastructure Focus"}
    ],
    "confidence_thresholds": {"qualified_signal_min_score": 70, "max_score": 100},
    "likely_actions": ["review_eligibility", "prepare_application", "apply", "save"],
    "notification_preferences": {}
  }$spec$::jsonb,
  'approved',
  'gemini:gemini-flash-lite-latest',
  'aim-compiler-2026-08-19-v1'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- signal hypotheses — the new (planned, not yet running) grant-database
-- connector. Registering hypotheses against a not-yet-implemented source
-- is intentional: they express what this Aim expects to see once the
-- connector exists, independent of whether it can run today (section 22's
-- Observe->Measure->Propose loop and this Aim's own activation are both
-- still meaningful without live discovery — evidence/scoring/action can
-- already be exercised against hand-provided or backfilled signal text,
-- exactly as this PR's evaluation dataset does).
-- ---------------------------------------------------------------------------

insert into public.aim_signal_hypotheses (
  id, tenant_id, aim_id, aim_version_id, hypothesis, source_key,
  signal_type, is_experimental, status, connector_params
)
values
  (
    'd3000000-0000-4000-8000-000000000001',
    '77777777-7777-4777-8777-777777777777',
    '88888888-8888-4888-8888-888888888888',
    '99999999-9999-4999-8999-999999999999',
    'An active grant program explicitly funds climate-health infrastructure projects',
    'grants_database_web_search', 'grant_listing', true, 'active',
    '{"keyword": "climate health infrastructure grant", "region": "emerging markets", "sector": "climate,health"}'::jsonb
  ),
  (
    'd3000000-0000-4000-8000-000000000002',
    '77777777-7777-4777-8777-777777777777',
    '88888888-8888-4888-8888-888888888888',
    '99999999-9999-4999-8999-999999999999',
    'A multilateral development bank has an open call for proposals on climate-resilient health facilities',
    'grants_database_web_search', 'grant_listing', true, 'active',
    '{"keyword": "climate resilient health facilities call for proposals", "region": "emerging markets", "sector": "climate,health"}'::jsonb
  ),
  (
    'd3000000-0000-4000-8000-000000000003',
    '77777777-7777-4777-8777-777777777777',
    '88888888-8888-4888-8888-888888888888',
    '99999999-9999-4999-8999-999999999999',
    'A philanthropic foundation grant targets health system resilience in developing regions',
    'grants_database_web_search', 'grant_listing', true, 'active',
    '{"keyword": "health system resilience grant developing countries", "region": "emerging markets", "sector": "health"}'::jsonb
  )
on conflict (id) do update set
  hypothesis = excluded.hypothesis,
  source_key = excluded.source_key,
  connector_params = excluded.connector_params,
  status = excluded.status;
