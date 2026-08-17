-- CollectIQ Phase 7 Manager Agent factual summary v0.2
-- Read-only source for the founder/CEO brief.
create or replace view public.manager_agent_operating_summary as
select
  (select count(*) from public.lead_prospects) as prospects_total,
  (select count(*) from public.lead_prospects where prospect_score >= 60) as prospects_qualified,
  (select count(*) from public.lead_prospects where status='contacted') as prospects_contacted,
  (select count(*) from public.lead_prospects where status='replied') as prospect_replies,
  (select count(*) from public.lead_prospects where status in ('audit_offered','audit_received')) as audit_interest,
  (select count(*) from public.audit_leads where status in ('file_received','validating','needs_review','audit_ready')) as audits_open,
  (select count(*) from public.audit_leads where status='sent') as audits_sent,
  (select coalesce(sum((audit_summary->'metrics'->>'overdue_ar')::numeric),0) from public.audit_leads where audit_summary is not null) as overdue_ar_analyzed,
  (select coalesce(sum((audit_summary->'metrics'->>'priority_pool')::numeric),0) from public.audit_leads where audit_summary is not null) as recovery_opportunity_identified,
  (select count(*) from public.recovery_sprints where status='active') as active_sprints,
  (select count(*) from public.recovery_sprints where status='completed') as completed_sprints,
  (select coalesce(sum(amount),0) from public.sprint_collections) as cash_recovered_recorded,
  (select count(*) from public.approval_queue where status='pending') as pending_approvals,
  (select count(*) from public.approval_queue where status='pending' and risk_tier='red') as pending_red_approvals,
  (select count(*) from public.agent_exceptions where status in ('open','acknowledged') and severity in ('high','critical')) as high_exceptions,
  (select count(*) from public.agent_jobs where status='failed') as failed_agent_jobs,
  (select count(*) from public.sales_messages where direction='inbound' and intent_score >= 70) as hot_inbound_messages,
  now() as generated_at;
