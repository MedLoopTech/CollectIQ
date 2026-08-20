-- ===== health_check.sql =====
-- Aimfold Core — Deployment health check (PR20, section 38: "health checks").
--
-- Read-only. Run against any environment (dev/staging/production) after
-- applying migrations to confirm the schema is actually in the state
-- 22 migrations (PR1-19) expect, before promoting traffic to it. Not a
-- substitute for the live Docker verification every PR in this dev
-- sequence has already done — this is the fast, repeatable check an
-- operator runs against a specific real environment.
--
-- Usage: psql <connection-string> -f supabase/health_check.sql
-- Exits with visible FAIL lines if anything is missing; a clean run
-- prints only PASS lines and one final summary line.

do $$
declare
  expected_tables text[] := array[
    'aim_memory', 'aim_signal_hypotheses', 'aim_versions', 'aims', 'audit_log',
    'entities', 'entity_memory', 'entity_relationships', 'feedback',
    'learning_proposals', 'model_runs', 'opportunities', 'opportunity_entities',
    'opportunity_lifecycle_events', 'opportunity_signals', 'outcomes',
    'scoring_versions', 'signal_entities', 'signals', 'sources',
    'tenant_members', 'tenants', 'workflow_runs'
  ];
  expected_rls_functions text[] := array[
    'is_tenant_member', 'tenant_role', 'opportunity_and_aim_belong_to_tenant'
  ];
  t text;
  f text;
  missing_tables text[] := array[]::text[];
  missing_rls text[] := array[]::text[];
  missing_functions text[] := array[]::text[];
  fail_count integer := 0;
begin
  -- 1. Every expected table exists.
  foreach t in array expected_tables loop
    if not exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = t) then
      missing_tables := array_append(missing_tables, t);
    end if;
  end loop;

  -- 2. RLS is enabled on every expected table that exists.
  foreach t in array expected_tables loop
    if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = t)
       and not exists (
         select 1 from pg_class c
         join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'public' and c.relname = t and c.relrowsecurity
       )
    then
      missing_rls := array_append(missing_rls, t);
    end if;
  end loop;

  -- 3. Every expected SECURITY-relevant function exists (RLS helpers +
  --    PR19's tenant-consistency guard).
  foreach f in array expected_rls_functions loop
    if not exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname = f) then
      missing_functions := array_append(missing_functions, f);
    end if;
  end loop;

  -- 4. pgcrypto extension (gen_random_uuid() — every table's default id).
  if not exists (select 1 from pg_extension where extname = 'pgcrypto') then
    raise notice 'FAIL: pgcrypto extension is not installed (gen_random_uuid() would fail on every insert)';
    fail_count := fail_count + 1;
  else
    raise notice 'PASS: pgcrypto extension installed';
  end if;

  if array_length(missing_tables, 1) is not null then
    raise notice 'FAIL: missing tables: %', missing_tables;
    fail_count := fail_count + array_length(missing_tables, 1);
  else
    raise notice 'PASS: all % expected tables present', array_length(expected_tables, 1);
  end if;

  if array_length(missing_rls, 1) is not null then
    raise notice 'FAIL: RLS not enabled on: %', missing_rls;
    fail_count := fail_count + array_length(missing_rls, 1);
  else
    raise notice 'PASS: RLS enabled on every expected table';
  end if;

  if array_length(missing_functions, 1) is not null then
    raise notice 'FAIL: missing functions: %', missing_functions;
    fail_count := fail_count + array_length(missing_functions, 1);
  else
    raise notice 'PASS: all % expected RLS/tenant-isolation functions present', array_length(expected_rls_functions, 1);
  end if;

  if fail_count = 0 then
    raise notice 'HEALTH CHECK: PASS — schema matches what PR1-19''s migrations expect';
  else
    raise exception 'HEALTH CHECK: FAIL — % issue(s) found, see FAIL lines above', fail_count;
  end if;
end
$$;
