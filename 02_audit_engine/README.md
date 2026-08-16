# CollectIQ Audit Engine v0.1

Deterministic AR intelligence engine for the CollectIQ Free AR Intelligence Audit.

## Capabilities
- CSV/XLSX/XLS ingestion
- common-column auto-mapping + explicit mapping override
- row validation and structured warnings/errors
- ageing buckets and overdue metrics
- AR concentration analysis
- missed-promise and dispute value
- deterministic collection priority scoring
- AR Health Score
- top collection opportunities + recommended actions
- optional scored invoice CSV
- FastAPI endpoint for n8n integration
- Northstar golden-dataset regression test

## Install and test
```bash
pip install -r requirements.txt
python test_golden.py
```

## CLI
```bash
python collectiq_engine.py northstar_sample.csv --as-of 2026-08-16 --output audit.json --write-scored-csv
```

## API
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Then POST multipart data to `/audit/upload` with:
- `file`
- optional `as_of=YYYY-MM-DD`

## Required canonical fields
- customer_name
- invoice_number
- invoice_date
- due_date
- outstanding_amount

## Important v0.1 limitations
- Multi-currency portfolios are not FX-normalized.
- DSO is not calculated unless revenue/credit-sales data is separately available.
- Payment matching is not included yet.
- No LLM is used for financial calculations.
- Legal disputes must be human-reviewed.

## n8n integration
Replace the current `Audit Engine Placeholder` node with an HTTP Request to this API. Persist the returned JSON to `audit_leads.audit_summary`; validation failures and successful audits should both route to internal human review during the pilot.
