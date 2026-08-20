-- ===== 20260819121100_seed_career_discovery_aim.sql =====
-- Aimfold Core — Second Validation Aim: Career Discovery (PR16)
--
-- AIMFOLD_MASTER_GOAL.md section 41 (Horizontal Validation): "Aimfold is
-- not considered successfully generalized until materially different
-- Aims operate on the same core engine without changing engine code."
-- This is Aim 2 (Career Discovery) of the three the section requires.
--
-- Zero aimfold_core/*.py files changed to produce this — that is the
-- actual test PR16 exists to pass, not incidental. Everything here is
-- DATA: a new tenant, one Aim, and one AimVersion whose compiled_spec is
-- the real, live output of aimfold_core/aim_compiler (PR4) — unedited —
-- given the exact "Career Aim" example from AIMFOLD_MASTER_GOAL.md
-- section 3: "Find finance/data roles where my finance transformation
-- background creates an unusual advantage." Compare its
-- target_entity_types (['job','employer'], not ['company']),
-- scoring_weights (finance-transformation/systems/data-analytics
-- keywords, zero overlap with CollectIQ's AR/collections vocabulary),
-- and likely_actions (apply/research/save, not contact) against
-- 20260819120200_seed_collectiq_aim.sql's CollectIQ Aim — materially
-- different by every measure section 41 cares about, run through the
-- identical evidence/scoring/action code.
--
-- A clearly-labeled validation tenant, not a real customer — see the
-- name/slug below.

-- ---------------------------------------------------------------------------
-- tenant
-- ---------------------------------------------------------------------------

insert into public.tenants (id, name, slug, status)
values (
  '44444444-4444-4444-4444-444444444444',
  'Career Discovery (Horizontal Validation Aim #2)',
  'career-discovery-validation',
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
  '55555555-5555-4555-8555-555555555555',
  '44444444-4444-4444-4444-444444444444',
  'Finance Transformation Career Search',
  'career_discovery',
  'active'
)
on conflict (id) do update set
  name = excluded.name,
  opportunity_type = excluded.opportunity_type,
  status = excluded.status;

-- ---------------------------------------------------------------------------
-- aim version 1 — the real, unedited output of a live aimfold_core.aim_compiler
-- run (gemini-flash-lite-latest) against AIMFOLD_MASTER_GOAL.md section 3's
-- own Career Aim example. Not hand-tuned — this is what generalization
-- actually looks like when the compiler is genuinely reused, not
-- special-cased for this second domain.
-- ---------------------------------------------------------------------------

insert into public.aim_versions (
  id, tenant_id, aim_id, version_number, is_current, raw_user_intent,
  compiled_spec, status, compiler_model, compiler_prompt_version
)
values (
  '66666666-6666-4666-8666-666666666666',
  '44444444-4444-4444-4444-444444444444',
  '55555555-5555-4555-8555-555555555555',
  1,
  true,
  $intent$Find finance/data roles where my finance transformation background creates an unusual advantage.$intent$,
  $spec${
    "objective": "Find finance and data roles where a background in finance transformation provides a distinct strategic advantage.",
    "opportunity_type": "career_discovery",
    "target_entity_types": ["job", "employer"],
    "geography": ["remote", "global"],
    "industries": [],
    "positive_criteria": [
      "role involves finance transformation, process reengineering, or financial systems implementation",
      "role sits at the intersection of finance and data analytics or engineering",
      "job description emphasizes modernizing or scaling finance operations"
    ],
    "negative_criteria": [],
    "exclusions": [],
    "freshness_requirements": null,
    "likely_sources": ["job boards", "company career pages", "professional networks"],
    "evidence_requirements": [
      "mention of finance transformation or process optimization in the job description",
      "clear alignment with finance operations, FP&A transformation, or data strategy"
    ],
    "scoring_dimensions": [
      "relevance of finance transformation focus",
      "blend of finance and data responsibilities",
      "seniority and impact potential"
    ],
    "scoring_weights": [
      {"pattern": "finance transformation", "points": 40, "label": "Finance transformation focus"},
      {"pattern": "financial systems|fp&a transformation|process reengineering", "points": 30, "label": "Systems and process modernization"},
      {"pattern": "finance data|analytics|business intelligence", "points": 30, "label": "Data and analytics integration"}
    ],
    "confidence_thresholds": {"qualified_signal_min_score": 40, "max_score": 100},
    "likely_actions": ["apply", "research", "save"],
    "notification_preferences": {}
  }$spec$::jsonb,
  'approved',
  'gemini:gemini-flash-lite-latest',
  'aim-compiler-2026-08-19-v1'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- signal hypotheses — reusing the SAME two source connectors CollectIQ
-- uses (linkedin_jobs_apify, indeed_jobs_apify) with career-relevant
-- search terms. Proves source-connector reuse across materially
-- different Aims, not just the compiler/evidence/scoring layers.
-- ---------------------------------------------------------------------------

insert into public.aim_signal_hypotheses (
  id, tenant_id, aim_id, aim_version_id, hypothesis, source_key,
  signal_type, is_experimental, status, connector_params
)
values
  (
    'c2000000-0000-4000-8000-000000000001',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role explicitly seeks finance transformation experience',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance transformation", "location": "Remote"}'::jsonb
  ),
  (
    'c2000000-0000-4000-8000-000000000002',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role is for a finance systems manager',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance systems manager", "location": "Remote"}'::jsonb
  ),
  (
    'c2000000-0000-4000-8000-000000000003',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role blends finance operations with data analytics',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance data analytics", "location": "Remote"}'::jsonb
  ),
  (
    'c2000000-0000-4000-8000-000000000004',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role explicitly seeks finance transformation experience',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance transformation", "location": "Remote"}'::jsonb
  ),
  (
    'c2000000-0000-4000-8000-000000000005',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role is for a finance systems manager',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance systems manager", "location": "Remote"}'::jsonb
  ),
  (
    'c2000000-0000-4000-8000-000000000006',
    '44444444-4444-4444-4444-444444444444',
    '55555555-5555-4555-8555-555555555555',
    '66666666-6666-4666-8666-666666666666',
    'A posted role blends finance operations with data analytics',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "finance data analytics", "location": "Remote"}'::jsonb
  )
on conflict (id) do update set
  hypothesis = excluded.hypothesis,
  source_key = excluded.source_key,
  connector_params = excluded.connector_params,
  status = excluded.status;
