-- ===== 20260819120200_seed_collectiq_aim.sql =====
-- Aimfold Core — CollectIQ as the First Aim (PR3)
--
-- Converts the hardcoded scouting logic in
-- 06_leadgen_apify/collectiq_apify_multisource_leadgen_v02.json (search
-- queries, keyword scoring rules, qualification threshold) into data:
-- one tenant, one Aim, one approved+current AimVersion, two source
-- connectors, and the six signal hypotheses that already run in
-- production today. No behavior is invented here — every value below is
-- transcribed from the existing n8n workflow so this seed is a faithful
-- snapshot, not a redesign. See 06_leadgen_apify/README.md for the n8n
-- side of this change (workflow now reads this data instead of inlining it).
--
-- Fixed (non-random) UUIDs are used throughout so the n8n workflow and
-- docs can reference them as stable constants — see env.example additions
-- AIMFOLD_COLLECTIQ_TENANT_ID / AIMFOLD_COLLECTIQ_AIM_ID.
--
-- NOT done here: no tenant_members row is created, because that requires
-- a real auth.users id and none is known at migration time. Until someone
-- is added to tenant_members for this tenant, only the service-role key
-- can read/write these rows (which is exactly what the n8n workflow uses).

-- ---------------------------------------------------------------------------
-- source connectors
-- ---------------------------------------------------------------------------

insert into public.sources (id, key, name, connector_type, connector_version, status, config_schema)
values
  (
    'a1000000-0000-4000-8000-000000000001',
    'linkedin_jobs_apify',
    'LinkedIn Jobs (Apify)',
    'apify_actor',
    '0.1.0',
    'active',
    '{"keyword": "string", "location": "string", "country": "string", "maxItems": "number"}'::jsonb
  ),
  (
    'a1000000-0000-4000-8000-000000000002',
    'indeed_jobs_apify',
    'Indeed Jobs (Apify)',
    'apify_actor',
    '0.1.0',
    'active',
    '{"keyword": "string", "location": "string", "country": "string", "maxItems": "number"}'::jsonb
  )
on conflict (key) do update set
  name = excluded.name,
  connector_type = excluded.connector_type,
  config_schema = excluded.config_schema;

-- ---------------------------------------------------------------------------
-- tenant
-- ---------------------------------------------------------------------------

insert into public.tenants (id, name, slug, status)
values (
  '11111111-1111-4111-8111-111111111111',
  'CollectIQ',
  'collectiq',
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
  '22222222-2222-4222-8222-222222222222',
  '11111111-1111-4111-8111-111111111111',
  'CollectIQ AR Signal Discovery',
  'customer_discovery',
  'active'
)
on conflict (id) do update set
  name = excluded.name,
  opportunity_type = excluded.opportunity_type,
  status = excluded.status;

-- ---------------------------------------------------------------------------
-- aim version 1 — transcribed 1:1 from the live v0.2 n8n workflow
-- ---------------------------------------------------------------------------

insert into public.aim_versions (
  id, tenant_id, aim_id, version_number, is_current, raw_user_intent,
  compiled_spec, status, compiler_model, compiler_prompt_version
)
values (
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
  1,
  true,
  $intent$Find US and UK companies showing evidence of accounts-receivable / collections operational strain — manual AR workflows, aging or overdue invoice backlogs, payment-dispute handling, spreadsheet-based tracking, or a recent ERP/accounting system change — that CollectIQ's AR Intelligence Audit and Managed Recovery service can address.$intent$,
  $spec${
    "objective": "Find companies whose hiring signals indicate AR/collections operational strain that CollectIQ's AR Intelligence Audit + Managed Recovery service can address.",
    "opportunity_type": "customer_discovery",
    "target_entity_types": ["company"],
    "geography": ["United States", "United Kingdom"],
    "industries": [],
    "positive_criteria": [
      "AR hiring", "collections/credit control", "ageing", "payment commitments",
      "disputes", "spreadsheet workflow", "ERP/accounting system", "high volume",
      "cash application", "reporting", "manual follow-up"
    ],
    "negative_criteria": [],
    "exclusions": [],
    "freshness_requirements": null,
    "likely_sources": ["linkedin_jobs_apify", "indeed_jobs_apify"],
    "evidence_requirements": ["job posting title and/or description must match at least one positive_criteria pattern"],
    "scoring_dimensions": ["keyword_match"],
    "scoring_weights": [
      {"pattern": "accounts receivable|\\bar\\b", "points": 25, "label": "AR hiring"},
      {"pattern": "collections?|credit controller", "points": 30, "label": "collections/credit control"},
      {"pattern": "aging|ageing", "points": 10, "label": "ageing"},
      {"pattern": "promise to pay|payment promise|payment commitment|ptp", "points": 15, "label": "payment commitments"},
      {"pattern": "dispute|billing discrepancy|invoice discrepancy", "points": 15, "label": "disputes"},
      {"pattern": "excel|spreadsheet|google sheets", "points": 10, "label": "spreadsheet workflow"},
      {"pattern": "netsuite|quickbooks|xero|sage|dynamics|sap|oracle", "points": 15, "label": "ERP/accounting system"},
      {"pattern": "high volume|large volume|portfolio|hundreds of invoices", "points": 15, "label": "high volume"},
      {"pattern": "cash application", "points": 8, "label": "cash application"},
      {"pattern": "weekly report|reporting|aging report|ageing report", "points": 10, "label": "reporting"},
      {"pattern": "follow[- ]?up|chase invoices|contact customers|customer outreach", "points": 10, "label": "manual follow-up"}
    ],
    "confidence_thresholds": {"qualified_signal_min_score": 60, "max_score": 100},
    "likely_actions": ["contact"],
    "notification_preferences": {}
  }$spec$::jsonb,
  'approved',
  'n/a (transcribed from existing n8n workflow, not compiler-generated)',
  'n/a'
)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- signal hypotheses — the six searches the workflow already runs
-- ---------------------------------------------------------------------------

insert into public.aim_signal_hypotheses (
  id, tenant_id, aim_id, aim_version_id, hypothesis, source_key,
  signal_type, is_experimental, status, connector_params
)
values
  (
    'b1000000-0000-4000-8000-000000000001',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is actively hiring for an AR-titled role in the United States',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "accounts receivable", "location": "United States"}'::jsonb
  ),
  (
    'b1000000-0000-4000-8000-000000000002',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is hiring a collections specialist in the United States',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "collections specialist", "location": "United States"}'::jsonb
  ),
  (
    'b1000000-0000-4000-8000-000000000003',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is hiring a credit controller in the United Kingdom',
    'linkedin_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "credit controller", "location": "United Kingdom"}'::jsonb
  ),
  (
    'b1000000-0000-4000-8000-000000000004',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is actively hiring for an AR-titled role in the United States',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "accounts receivable", "location": "United States"}'::jsonb
  ),
  (
    'b1000000-0000-4000-8000-000000000005',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is hiring a collections specialist in the United States',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "collections specialist", "location": "United States"}'::jsonb
  ),
  (
    'b1000000-0000-4000-8000-000000000006',
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'Company is hiring a credit controller in the United Kingdom',
    'indeed_jobs_apify', 'job_posting', false, 'active',
    '{"keyword": "credit controller", "location": "United Kingdom"}'::jsonb
  )
on conflict (id) do update set
  hypothesis = excluded.hypothesis,
  source_key = excluded.source_key,
  connector_params = excluded.connector_params,
  status = excluded.status;
