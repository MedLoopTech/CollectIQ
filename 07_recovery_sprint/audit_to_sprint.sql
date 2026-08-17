-- CollectIQ Audit -> Recovery Sprint conversion v0.1
-- Run after recovery_sprint_v01.sql.
-- Expects audit_leads.audit_summary to contain the audit engine's `sprint_seed` payload.

create or replace function public.start_recovery_sprint_from_audit(
  p_audit_lead_id uuid,
  p_start_date date default current_date
)
returns uuid
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_lead public.audit_leads%rowtype;
  v_audit jsonb;
  v_seed jsonb;
  v_metrics jsonb;
  v_sprint_id uuid;
  v_account jsonb;
  v_invoice jsonb;
  v_account_id uuid;
  v_invoice_id uuid;
  v_currency text;
  v_action_type text;
begin
  select * into v_lead from public.audit_leads where id = p_audit_lead_id for update;
  if not found then raise exception 'Audit lead % not found', p_audit_lead_id; end if;
  if v_lead.status not in ('audit_ready','sent') then
    raise exception 'Audit must be reviewed before Sprint conversion. Current status: %', v_lead.status;
  end if;

  select id into v_sprint_id from public.recovery_sprints where audit_lead_id = p_audit_lead_id limit 1;
  if v_sprint_id is not null then return v_sprint_id; end if;

  v_audit := coalesce(v_lead.audit_summary, '{}'::jsonb);
  v_seed := v_audit -> 'sprint_seed';
  v_metrics := coalesce(v_audit -> 'metrics', '{}'::jsonb);
  if v_seed is null or jsonb_typeof(v_seed -> 'invoices') <> 'array' then
    raise exception 'Audit has no complete sprint_seed. Re-run the audit with Audit Engine API v0.2+ before conversion.';
  end if;

  select coalesce(nullif(x->>'currency',''), 'USD') into v_currency from jsonb_array_elements(v_seed->'invoices') x limit 1;
  v_currency := coalesce(v_currency, 'USD');

  insert into public.recovery_sprints(
    audit_lead_id, company_name, contact_name, contact_email, status,
    start_date, end_date, current_week, base_currency,
    baseline_total_ar, baseline_overdue_ar, baseline_60_plus, baseline_90_plus, baseline_priority_pool
  ) values (
    p_audit_lead_id, v_lead.company_name, v_lead.contact_name, v_lead.work_email, 'active',
    p_start_date, p_start_date + 30, 0, v_currency,
    coalesce((v_metrics->>'total_ar')::numeric,0), coalesce((v_metrics->>'overdue_ar')::numeric,0),
    coalesce((v_metrics->>'ar_60_plus')::numeric,0), coalesce((v_metrics->>'ar_90_plus')::numeric,0),
    coalesce((v_metrics->>'priority_pool')::numeric,0)
  ) returning id into v_sprint_id;

  for v_account in select * from jsonb_array_elements(v_seed->'accounts') loop
    insert into public.sprint_accounts(
      sprint_id, external_customer_id, customer_name, contact_email, sales_owner,
      total_outstanding, overdue_amount, priority_score, priority_band
    ) values (
      v_sprint_id, nullif(v_account->>'external_customer_id',''), v_account->>'customer_name',
      nullif(v_account->>'contact_email',''), nullif(v_account->>'sales_owner',''),
      coalesce((v_account->>'total_outstanding')::numeric,0), coalesce((v_account->>'overdue_amount')::numeric,0),
      nullif(v_account->>'priority_score','')::numeric, nullif(v_account->>'priority_band','')
    );
  end loop;

  for v_invoice in select * from jsonb_array_elements(v_seed->'invoices') loop
    select id into v_account_id from public.sprint_accounts
      where sprint_id=v_sprint_id and customer_name=v_invoice->>'customer_name' limit 1;

    insert into public.sprint_invoices(
      sprint_id, account_id, invoice_number, invoice_date, due_date, currency, invoice_amount,
      outstanding_amount, days_overdue, age_bucket, priority_score, priority_band, collection_status
    ) values (
      v_sprint_id, v_account_id, v_invoice->>'invoice_number', nullif(v_invoice->>'invoice_date','')::date,
      nullif(v_invoice->>'due_date','')::date, coalesce(nullif(v_invoice->>'currency',''),v_currency),
      coalesce((v_invoice->>'invoice_amount')::numeric,0), coalesce((v_invoice->>'outstanding_amount')::numeric,0),
      coalesce((v_invoice->>'days_overdue')::integer,0), nullif(v_invoice->>'age_bucket',''),
      nullif(v_invoice->>'priority_score','')::numeric, nullif(v_invoice->>'priority_band',''),
      case when coalesce((v_invoice->>'days_overdue')::integer,0)>0 then 'open' else 'hold' end
    ) returning id into v_invoice_id;

    if coalesce(v_invoice->>'promise_status','')<>'' and coalesce((v_invoice->>'promise_amount')::numeric,0)>0 and nullif(v_invoice->>'promise_date','') is not null then
      insert into public.sprint_promises(sprint_id,account_id,invoice_id,promise_amount,promise_date,status,source,notes)
      values(v_sprint_id,v_account_id,v_invoice_id,(v_invoice->>'promise_amount')::numeric,(v_invoice->>'promise_date')::date,
        case v_invoice->>'promise_status' when 'missed' then 'missed' when 'kept' then 'kept' when 'partially_kept' then 'partially_kept' else 'pending' end,
        'day_0_audit','Imported from approved Free AR Audit');
    end if;

    if coalesce(v_invoice->>'dispute_type','')<>'' then
      insert into public.sprint_disputes(sprint_id,account_id,invoice_id,category,amount,status,next_action)
      values(v_sprint_id,v_account_id,v_invoice_id,v_invoice->>'dispute_type',coalesce((v_invoice->>'outstanding_amount')::numeric,0),'open',v_invoice->>'recommended_action');
    end if;

    if coalesce((v_invoice->>'days_overdue')::integer,0)>0 and coalesce((v_invoice->>'priority_score')::numeric,0)>=50 then
      v_action_type := case when coalesce(v_invoice->>'dispute_type','')<>'' then 'resolve_dispute' when v_invoice->>'promise_status'='missed' then 'check_promise' else 'follow_up' end;
      insert into public.sprint_actions(sprint_id,account_id,invoice_id,action_type,priority,reason,recommended_action,due_at,status)
      values(v_sprint_id,v_account_id,v_invoice_id,v_action_type,
        least(100,greatest(0,round(coalesce((v_invoice->>'priority_score')::numeric,50)))::integer),
        'Seeded from approved Day-0 AR audit',coalesce(nullif(v_invoice->>'recommended_action',''),'Review overdue invoice and assign next action.'),now(),'open');
    end if;
  end loop;

  insert into public.sprint_weekly_snapshots(
    sprint_id,week_number,snapshot_date,total_ar,overdue_ar,ar_60_plus,ar_90_plus,priority_pool,cash_collected_to_date
  ) values(v_sprint_id,0,p_start_date,
    coalesce((v_metrics->>'total_ar')::numeric,0),coalesce((v_metrics->>'overdue_ar')::numeric,0),
    coalesce((v_metrics->>'ar_60_plus')::numeric,0),coalesce((v_metrics->>'ar_90_plus')::numeric,0),
    coalesce((v_metrics->>'priority_pool')::numeric,0),0);

  return v_sprint_id;
end;
$$;

comment on function public.start_recovery_sprint_from_audit(uuid,date) is
'Converts a reviewed Free AR Audit into a complete Day-0 Recovery Sprint. Idempotent per audit_lead_id.';
