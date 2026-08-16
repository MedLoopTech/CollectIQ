# CollectIQ Reviewer Dashboard v0.1

Internal human-review interface for AR audits.

## Features

- Review queue for `needs_review` and `audit_ready`
- Lead/contact context
- AR headline metrics
- validation warnings
- top 10 collection opportunities
- blocker table
- reviewer notes
- approve audit
- gated Send Audit button
- companion n8n send-workflow skeleton

## Security

The dashboard should be protected by Supabase Auth.

Do **not** deploy it publicly using unrestricted anonymous read/update access.

The included SQL grants authenticated users read/update access for the pilot. For production, restrict this to a dedicated reviewer/admin role.

## Setup

1. Run `reviewer_schema_additions.sql`.
2. Configure Supabase Auth for the reviewer.
3. Put your Supabase URL + public anon key into `index.html`.
4. Import `n8n_send_approved_audit_v01.json`.
5. Set its production webhook URL as `SEND_AUDIT_WEBHOOK_URL`.
6. Deploy the dashboard behind authentication.

## Approval flow

`needs_review`
→ reviewer checks metrics/warnings/opportunities
→ adds notes
→ clicks Approve Audit
→ status becomes `audit_ready`
→ Send Audit button unlocks
→ send workflow verifies status again
→ only then should the report/email be sent

## Important

The provided send n8n workflow is intentionally a **send gate + payload builder**.
Add your chosen actual delivery node after `Build Send Payload`:
- Gmail
- Hostinger Mail
- SMTP
- another transactional email service

Also connect the report renderer/output file at that step.
