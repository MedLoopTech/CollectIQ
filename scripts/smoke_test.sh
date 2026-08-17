#!/usr/bin/env bash
set -euo pipefail

AUDIT_URL="${COLLECTIQ_AUDIT_ENGINE_PUBLIC_URL:-http://127.0.0.1:8000}"
AGENT_URL="${COLLECTIQ_AGENT_SERVICE_PUBLIC_URL:-http://127.0.0.1:8100}"

printf 'Checking Audit Engine...\n'
curl -fsS "$AUDIT_URL/health" | python -m json.tool

printf '\nChecking Agent Service...\n'
curl -fsS "$AGENT_URL/health" | python -m json.tool

printf '\nRunning Northstar audit API smoke test...\n'
TMP="$(mktemp)"
curl -fsS -X POST \
  -F "file=@02_audit_engine/northstar_sample.csv" \
  -F "as_of=2026-08-16" \
  "$AUDIT_URL/audit/upload" > "$TMP"

python - "$TMP" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
assert d.get('status') != 'validation_failed', d
m=d.get('metrics',{})
assert m.get('total_ar') is not None, d
assert d.get('sprint_seed',{}).get('invoices'), 'missing sprint_seed invoices'
print('Audit status:', d.get('status'))
print('Total AR:', m.get('total_ar'))
print('Priority pool:', m.get('priority_pool'))
print('Sprint seed invoices:', len(d['sprint_seed']['invoices']))
PY
rm -f "$TMP"

printf '\nPASS: core CollectIQ services are healthy.\n'
printf 'LLM-backed endpoints are intentionally not called here unless live provider credentials are configured.\n'
