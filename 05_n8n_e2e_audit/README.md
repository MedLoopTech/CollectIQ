# CollectIQ End-to-End n8n Audit Workflow v0.1

This workflow connects the existing landing-page intake to the CollectIQ Audit Engine.

## Flow

Landing page
→ Supabase `audit_leads`
→ n8n webhook receives `lead_id`
→ load authoritative lead from Supabase
→ mark `validating`
→ create short-lived signed URL for private AR file
→ download file
→ POST multipart file to CollectIQ Audit Engine
→ branch on validation result
→ persist validation + audit JSON
→ set lead to `needs_review`
→ create `audit_events` review event
→ respond to landing-page trigger

## Environment variables

Configure in n8n:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `COLLECTIQ_AUDIT_ENGINE_URL`

Example engine URL when using Docker on the same network:

`http://collectiq-audit-engine:8000`

## Important

The n8n workflow intentionally stops at **human review**.

It does not:
- send the report automatically,
- contact debtors,
- approve AI-generated communication,
- expose the private AR file publicly.

That is deliberate for the first pilot.

## Next optional node

After `Build Review Notification`, add your preferred internal notification:
- Gmail
- Hostinger Mail
- Slack
- Telegram
- Microsoft Teams

The payload already contains a concise review summary.

## Report generation

After human approval, call the report renderer with the stored `audit_summary`.
For v0.1, report generation should remain approval-gated.

## Expected lead states

`file_received`
→ `validating`
→ `needs_review`
→ `audit_ready`
→ `sent`
→ `pilot`
→ `won` / `lost`

## Testing sequence

1. Deploy Audit Engine and confirm `/health`.
2. Run Supabase schema from the intake package.
3. Import this n8n workflow.
4. Set environment variables.
5. Activate workflow.
6. Put its production webhook URL into the landing page.
7. Submit the Northstar sample CSV.
8. Confirm `audit_leads.audit_summary` contains metrics.
9. Confirm status becomes `needs_review`.
10. Compare results with the golden dataset.

