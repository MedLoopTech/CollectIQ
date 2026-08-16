# CollectIQ — Full Program v0.3

CollectIQ is an **AI-assisted Accounts Receivable Intelligence + Managed Recovery system** for B2B finance teams.

The product is intentionally built as a **service-first system**, not a full SaaS platform.

The commercial wedge is:

**Hiring signal → targeted prospect → Free AR Intelligence Audit → 30-Day Recovery Sprint → recurring managed AR intelligence**

---

## 1. Program modules

### 01 — Landing + Audit Intake

Location:

`01_landing_intake/`

Contains:

- CollectIQ landing page
- AR Intelligence Audit intake form
- secure Supabase Storage upload
- initial Supabase schema
- intake n8n workflow skeleton

Primary flow:

```text
Landing page
→ form
→ private CSV/XLSX upload
→ audit_leads
→ n8n
```

---

### 02 — Audit Engine

Location:

`02_audit_engine/`

Python/FastAPI service.

Capabilities:

- CSV/XLSX/XLS ingestion
- automatic column mapping
- explicit column mapping override
- validation
- AR ageing
- 60+ / 90+
- overdue ratio
- concentration analysis
- dispute analysis
- promise-to-pay analysis
- collection-priority scoring
- AR Health Score
- top opportunities
- recommended next action
- JSON audit output

Golden dataset regression testing is included.

Run:

```bash
cd 02_audit_engine
pip install -r requirements.txt
python test_golden.py
```

Start API:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

---

### 03 — Client Report Renderer

Location:

`03_report_renderer/`

Creates customer-facing:

- HTML AR Intelligence Audit
- PDF AR Intelligence Audit

Report contents:

- AR Health Score
- total AR
- overdue AR
- 60+
- 90+
- priority pool
- executive summary
- ageing profile
- top collection opportunities
- disputes/blockers
- next actions
- 30-day recovery workflow

The sample Northstar report is included.

---

### 04 — Reviewer Dashboard

Location:

`04_reviewer_dashboard/`

Human review layer.

Features:

- audit review queue
- lead information
- validation warnings
- AR metrics
- top collection opportunities
- blocker analysis
- reviewer notes
- approval gate
- Send Audit gate

Status flow:

```text
needs_review
→ audit_ready
→ sent
```

Protect this app with Supabase Auth.

---

### 05 — End-to-End Audit n8n Workflow

Location:

`05_n8n_e2e_audit/`

Production workflow:

```text
Lead submitted
→ load Supabase record
→ sign private file URL
→ download AR file
→ call Audit Engine
→ validation branch
→ save audit JSON
→ status = needs_review
→ create review event
```

Human review remains mandatory for pilot audits.

---

### 06 — Apify Multi-Source Lead Generation

Location:

`06_leadgen_apify/`

This is the current lead-generation layer.

Sources:

- LinkedIn Jobs via Apify Actor
- Indeed Jobs via Apify Actor
- other job/career Actors can be added

Flow:

```text
Apify Actor
→ job listings
→ normalize
→ CollectIQ fit score
→ keep score >= 60
→ Supabase prospects
→ enrichment
→ human review
→ outreach draft
```

The workflow currently scores for signals such as:

- Accounts Receivable hiring
- Collections hiring
- credit control
- ageing
- payment promises
- disputes
- Excel/manual workflow
- ERP/accounting software
- high invoice volume
- cash application
- reporting
- manual customer follow-up

This gives CollectIQ a signal-based outbound model instead of generic cold prospecting.

---

# 2. Recommended production stack

## Frontend

- static HTML initially
- Next.js later if needed

## Database

- Supabase PostgreSQL

## Storage

- private Supabase Storage

## Automation

- n8n

## Audit engine

- Python
- pandas
- FastAPI

## Lead acquisition

- Apify

## Contact enrichment

- Hunter or equivalent

## Email

- Gmail / Hostinger Mail / SMTP
- send only after review initially

---

# 3. Required Supabase setup

Run:

`supabase/collectiq_full_schema.sql`

This consolidates:

- audit intake
- audit events
- reviewer fields
- lead prospects
- lead-generation extensions
- RLS

Important:

The reviewer dashboard must be protected with Supabase Auth.

Do not expose service-role credentials in a browser.

---

# 4. Environment variables

Copy:

`.env.example`

Main variables:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY

N8N_WEBHOOK_URL

COLLECTIQ_AUDIT_ENGINE_URL

APIFY_TOKEN
APIFY_LINKEDIN_ACTOR_ID
APIFY_INDEED_ACTOR_ID

HUNTER_API_KEY
```

---

# 5. Deployment order

## Step 1 — Supabase

Create Supabase project.

Run:

`supabase/collectiq_full_schema.sql`

Create at least one authenticated reviewer.

---

## Step 2 — Audit Engine

Deploy `02_audit_engine`.

Recommended initial deployment:

Docker container.

Test:

```text
GET /health
```

Then run golden test.

Do not continue until the Northstar test reconciles.

---

## Step 3 — n8n Audit Pipeline

Import:

`05_n8n_e2e_audit/collectiq_e2e_audit_v01.json`

Set:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
COLLECTIQ_AUDIT_ENGINE_URL
```

---

## Step 4 — Landing Page

Use:

`01_landing_intake/index.html`

Insert:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
N8N_WEBHOOK_URL
```

Deploy to your web host.

---

## Step 5 — Reviewer Dashboard

Deploy:

`04_reviewer_dashboard/index.html`

behind Supabase Auth.

Configure:

```text
SUPABASE_URL
SUPABASE_ANON_KEY
SEND_AUDIT_WEBHOOK_URL
```

---

## Step 6 — Report Renderer

Use:

`03_report_renderer/`

Initially report rendering can remain manual/human-reviewed.

Later convert it into a service endpoint:

```text
POST /render-report
```

---

## Step 7 — Apify Lead Engine

Choose LinkedIn and Indeed Actors.

Before activating:

1. run each Actor manually,
2. inspect its input schema,
3. inspect Dataset output,
4. update the n8n `Build Actor Input` node,
5. verify normalization,
6. run manually,
7. check Supabase prospect rows,
8. activate schedule.

Import:

`06_leadgen_apify/collectiq_apify_multisource_leadgen_v02.json`

---

# 6. Commercial funnel

The intended funnel is:

```text
Hiring signal
↓
Qualified company
↓
Finance contact
↓
Personalized outreach
↓
Free AR Intelligence Audit
↓
Ageing file received
↓
Audit completed
↓
Human review
↓
Audit sent
↓
30-Day Recovery Sprint
↓
Recurring managed AR service
```

---

# 7. Initial offer

## Free

### AR Intelligence Audit

Customer sends:

CSV or Excel AR ageing.

They receive:

- AR Health Score
- ageing
- priority pool
- top accounts
- disputes
- promises
- recommended actions

---

## Paid Pilot

### 30-Day AR Recovery Sprint

Suggested first-customer pricing:

```text
$250 onboarding
+
$300 service fee
+
optional performance component
```

The goal is case-study creation and workflow learning, not maximizing initial price.

---

# 8. Product positioning

Do not sell:

> AI debt collector

Do not sell:

> automated reminder emails

Do not sell:

> n8n automation

Position as:

> **Accounts Receivable Intelligence + Managed Recovery**

Core questions CollectIQ answers:

- Who should finance chase today?
- Which payment promises are due?
- Which customers break promises repeatedly?
- Which invoices are blocked internally?
- What is the highest-impact next action?
- How much AR deserves immediate attention?
- Where is cash getting stuck?

---

# 9. Human-in-the-loop rules

For the pilot:

AI must not:

- auto-send debtor communications
- threaten legal action
- invent penalties
- invent invoice balances
- invent payment promises
- negotiate autonomously
- mark disputes resolved automatically
- send customer reports without review

Human approval remains required.

---

# 10. Current version scope

CollectIQ v0.3 includes:

- ✅ demand validation
- ✅ landing page
- ✅ audit intake
- ✅ secure file upload
- ✅ Supabase schema
- ✅ audit engine
- ✅ column mapping
- ✅ validation
- ✅ AR scoring
- ✅ AR Health Score
- ✅ golden dataset test
- ✅ report renderer
- ✅ PDF client report
- ✅ reviewer dashboard
- ✅ approval gate
- ✅ end-to-end n8n audit flow
- ✅ Apify multi-source hiring-signal lead generation
- ✅ prospect scoring
- ✅ Supabase prospect storage

Not yet completed:

- ⬜ fully integrated contact enrichment after Apify
- ⬜ approval-gated email draft creation
- ⬜ inbox reply classification
- ⬜ automatic lead stage updates
- ⬜ direct report attachment/send node
- ⬜ payment matching
- ⬜ cash collection tracking
- ⬜ recovery-sprint dashboard
- ⬜ customer-facing SaaS onboarding
- ⬜ ERP integrations

---

# 11. What to build next

Do **not** add more SaaS features yet.

The next milestone is:

> **Run the entire funnel with one real prospect.**

Specifically:

```text
Apify identifies company
↓
human approves prospect
↓
outreach sent
↓
prospect agrees to audit
↓
prospect uploads ageing file
↓
CollectIQ processes it
↓
you review report
↓
report is sent
↓
ask for 30-day paid pilot
```

If this works, CollectIQ has crossed from a product concept into a revenue experiment.

---

# 12. Success metrics

Track:

## Lead generation

- raw hiring signals
- unique companies
- score >=60
- score >=80
- valid contacts
- approved outreach
- replies
- positive replies

## Audit funnel

- audits offered
- ageing files received
- audits completed
- audits sent
- calls booked

## Revenue

- pilots sold
- recovered cash
- monthly recurring clients

The strongest first milestone is still:

> **A CFO or finance leader gives CollectIQ a real ageing file.**

The second:

> **The audit identifies useful priorities they act on.**

The third:

> **They pay for the recovery sprint.**
