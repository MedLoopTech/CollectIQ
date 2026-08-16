# CollectIQ Audit Intake v0.1

This package makes the CollectIQ landing page operational for the first pilot.

## Files

- `index.html` — responsive landing page + AR audit intake form
- `supabase_schema.sql` — Supabase tables, RLS, private storage bucket, upload policy
- `n8n_ar_audit_intake_v01.json` — importable n8n workflow skeleton
- `env.example` — deployment placeholders

## Setup

1. Create/use a Supabase project.
2. Run `supabase_schema.sql` in the Supabase SQL Editor.
3. Import `n8n_ar_audit_intake_v01.json` into n8n.
4. In n8n, configure environment variables:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
5. Activate the workflow and copy its production webhook URL.
6. Edit `index.html`:
   - replace `YOUR_SUPABASE_URL`
   - replace `YOUR_SUPABASE_ANON_KEY`
   - replace `YOUR_N8N_WEBHOOK_URL`
7. Deploy `index.html` to your preferred host.

## Current flow

Landing page
→ private file upload to Supabase Storage
→ lead record inserted in `audit_leads`
→ n8n receives `lead_id`
→ n8n reloads authoritative lead data from Supabase
→ lead marked `validating`
→ placeholder waits for the CollectIQ Audit Engine

## Security notes

- The `ar-intake` storage bucket is private.
- Anonymous users can upload but cannot read files.
- Anonymous users can create audit leads but cannot read/update/delete them.
- n8n should use the Supabase service role key server-side only.
- Never place the Supabase service role key in the HTML.
- The pilot accepts files up to 10 MB.

## Next implementation

Replace the `Audit Engine Placeholder` n8n node with an HTTP Request to the CollectIQ Audit Engine v0.1. That engine should:

1. fetch the private uploaded file,
2. map/validate columns,
3. calculate ageing and AR metrics,
4. calculate priority scores,
5. generate structured audit JSON,
6. update `audit_leads.audit_summary`,
7. set status to `needs_review`,
8. notify the internal reviewer.

