-- CollectIQ Recovery Sprint weekly operating engine v0.1
-- Run after recovery_sprint_v01.sql and audit_to_sprint.sql.

create or replace function public.refresh_recovery_sprint(p_sprint_id uuid, p_as_of date default current_date)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_sprint public.recovery_sprints%rowtype;
  v_week integer;
  v_total_ar numeric;
  v_overdue_ar numeric;
  v_60 numeric;
  v_90 numeric;
  v_priority numeric;
  v_collected_total numeric;
  v_collected_week numeric;
  v_promises_due numeric;
  v_promises_kept numeric;
  v_promises_missed numeric;
  v_disputed numeric;
  v_disputes_resolved numeric;
  v_open_actions integer;
  v_attention integer;
  v_snapshot_id uuid;
  v_brief_id uuid;
  v_summary text;
  v_management jsonb;
  v_top_accounts jsonb;
  v_blockers jsonb;
begin
  select * into v_sprint from public.recovery_sprints where id = p_sprint_id for update;
  if not found then raise exception 'Sprint % not found', p_sprint_id; end if;
  if v_sprint.status not in ('active','paused','completed') then raise exception 'Sprint is not active: %', v_sprint.status; end if;

  update public.sprint_promises
  set status='missed', updated_at=now()
  where sprint_id=p_sprint_id and status='pending' and promise_date < p_as_of;

  update public.sprint_invoices
  set days_overdue = greatest(0, p_as_of - due_date),
      age_bucket = case
        when due_date is null or p_as_of <= due_date then 'Current'
        when p_as_of - due_date <= 30 then '1-30'
        when p_as_of - due_date <= 60 then '31-60'
        when p_as_of - due_date <= 90 then '61-90'
        else '90+'
      end,
      updated_at = now()
  where sprint_id=p_sprint_id and collection_status not in ('paid','written_off');

  update public.sprint_accounts a
  set total_outstanding = x.total_outstanding,
      overdue_amount = x.overdue_amount,
      priority_score = x.max_priority,
      priority_band = case when x.max_priority>=85 then 'Critical' when x.max_priority>=70 then 'High' when x.max_priority>=50 then 'Elevated' when x.max_priority>=30 then 'Moderate' else 'Low' end,
      current_status = case
        when x.total_outstanding <= 0 then 'paid'
        when exists(select 1 from public.sprint_disputes d where d.account_id=a.id and d.status not in ('resolved','closed')) then 'disputed'
        when exists(select 1 from public.sprint_promises p where p.account_id=a.id and p.status in ('pending','partially_kept','renegotiated')) then 'promise'
        else 'open'
      end,
      updated_at=now()
  from (
    select account_id,
      coalesce(sum(case when collection_status not in ('paid','written_off') then outstanding_amount else 0 end),0) total_outstanding,
      coalesce(sum(case when collection_status not in ('paid','written_off') and days_overdue>0 then outstanding_amount else 0 end),0) overdue_amount,
      coalesce(max(case when collection_status not in ('paid','written_off') then priority_score else 0 end),0) max_priority
    from public.sprint_invoices where sprint_id=p_sprint_id group by account_id
  ) x
  where a.id=x.account_id;

  -- Day 0-6 stays Week 0; Week 1 starts on Day 7.
  v_week := least(4, greatest(0, floor((p_as_of - coalesce(v_sprint.start_date,p_as_of))/7.0)::integer));
  update public.recovery_sprints set current_week=v_week, updated_at=now() where id=p_sprint_id;

  select coalesce(sum(outstanding_amount),0),
         coalesce(sum(case when days_overdue>0 then outstanding_amount else 0 end),0),
         coalesce(sum(case when days_overdue>60 then outstanding_amount else 0 end),0),
         coalesce(sum(case when days_overdue>90 then outstanding_amount else 0 end),0),
         coalesce(sum(case when days_overdue>0 and priority_score>=70 then outstanding_amount else 0 end),0)
    into v_total_ar,v_overdue_ar,v_60,v_90,v_priority
  from public.sprint_invoices
  where sprint_id=p_sprint_id and collection_status not in ('paid','written_off');

  select coalesce(sum(amount),0) into v_collected_total from public.sprint_collections where sprint_id=p_sprint_id and payment_date<=p_as_of;
  select coalesce(sum(amount),0) into v_collected_week from public.sprint_collections where sprint_id=p_sprint_id and payment_date between greatest(coalesce(v_sprint.start_date,p_as_of), p_as_of-6) and p_as_of;

  select coalesce(sum(promise_amount),0) into v_promises_due from public.sprint_promises where sprint_id=p_sprint_id and promise_date between greatest(coalesce(v_sprint.start_date,p_as_of), p_as_of-6) and p_as_of;
  select coalesce(sum(actual_payment_amount),0) into v_promises_kept from public.sprint_promises where sprint_id=p_sprint_id and status in ('kept','partially_kept') and coalesce(fulfilled_at::date,promise_date) between greatest(coalesce(v_sprint.start_date,p_as_of),p_as_of-6) and p_as_of;
  select coalesce(sum(promise_amount),0) into v_promises_missed from public.sprint_promises where sprint_id=p_sprint_id and status='missed' and promise_date between greatest(coalesce(v_sprint.start_date,p_as_of),p_as_of-6) and p_as_of;

  select coalesce(sum(amount),0) into v_disputed from public.sprint_disputes where sprint_id=p_sprint_id and status not in ('resolved','closed');
  select coalesce(sum(amount),0) into v_disputes_resolved from public.sprint_disputes where sprint_id=p_sprint_id and status in ('resolved','closed') and resolved_at::date between greatest(coalesce(v_sprint.start_date,p_as_of),p_as_of-6) and p_as_of;
  select count(*) into v_open_actions from public.sprint_actions where sprint_id=p_sprint_id and status in ('open','in_progress');
  select count(*) into v_attention from public.sprint_accounts where sprint_id=p_sprint_id and (priority_score>=70 or current_status='disputed');

  insert into public.sprint_weekly_snapshots(
    sprint_id,week_number,snapshot_date,total_ar,overdue_ar,ar_60_plus,ar_90_plus,priority_pool,
    cash_collected_to_date,cash_collected_this_week,promises_due,promises_kept,promises_missed,
    disputed_ar,disputes_resolved,open_actions,management_attention_accounts
  ) values (
    p_sprint_id,v_week,p_as_of,v_total_ar,v_overdue_ar,v_60,v_90,v_priority,
    v_collected_total,v_collected_week,v_promises_due,v_promises_kept,v_promises_missed,
    v_disputed,v_disputes_resolved,v_open_actions,v_attention
  )
  on conflict (sprint_id,week_number) do update set
    snapshot_date=excluded.snapshot_date,total_ar=excluded.total_ar,overdue_ar=excluded.overdue_ar,
    ar_60_plus=excluded.ar_60_plus,ar_90_plus=excluded.ar_90_plus,priority_pool=excluded.priority_pool,
    cash_collected_to_date=excluded.cash_collected_to_date,cash_collected_this_week=excluded.cash_collected_this_week,
    promises_due=excluded.promises_due,promises_kept=excluded.promises_kept,promises_missed=excluded.promises_missed,
    disputed_ar=excluded.disputed_ar,disputes_resolved=excluded.disputes_resolved,open_actions=excluded.open_actions,
    management_attention_accounts=excluded.management_attention_accounts
  returning id into v_snapshot_id;

  if v_week between 1 and 4 then
    select coalesce(jsonb_agg(jsonb_build_object(
      'account',customer_name,'overdue_amount',overdue_amount,'priority_score',priority_score,'status',current_status
    ) order by priority_score desc, overdue_amount desc),'[]'::jsonb)
    into v_top_accounts
    from (select * from public.sprint_accounts where sprint_id=p_sprint_id and total_outstanding>0 order by priority_score desc,overdue_amount desc limit 5) q;

    select coalesce(jsonb_agg(jsonb_build_object(
      'account',a.customer_name,'category',d.category,'amount',d.amount,'status',d.status,'next_action',d.next_action
    ) order by d.amount desc),'[]'::jsonb)
    into v_blockers
    from public.sprint_disputes d join public.sprint_accounts a on a.id=d.account_id
    where d.sprint_id=p_sprint_id and d.status not in ('resolved','closed');

    select coalesce(jsonb_agg(jsonb_build_object(
      'account',a.customer_name,'action',x.recommended_action,'priority',x.priority,'due_at',x.due_at
    ) order by x.priority desc,x.due_at asc),'[]'::jsonb)
    into v_management
    from (select * from public.sprint_actions where sprint_id=p_sprint_id and status in ('open','in_progress') order by priority desc,due_at asc limit 5) x
    left join public.sprint_accounts a on a.id=x.account_id;

    v_summary := format(
      'Week %s: %s collected this week (%s to date). Overdue AR is %s versus %s at baseline. %s of promises were missed this week. Open disputed AR is %s. %s accounts require management attention.',
      v_week, round(v_collected_week,2), round(v_collected_total,2), round(v_overdue_ar,2), round(v_sprint.baseline_overdue_ar,2), round(v_promises_missed,2), round(v_disputed,2), v_attention
    );

    insert into public.sprint_cfo_briefs(sprint_id,snapshot_id,week_number,status,executive_summary,management_actions,top_accounts,blockers)
    values(p_sprint_id,v_snapshot_id,v_week,'draft',v_summary,v_management,v_top_accounts,v_blockers)
    on conflict(sprint_id,week_number) do update set
      snapshot_id=excluded.snapshot_id,status='draft',executive_summary=excluded.executive_summary,
      management_actions=excluded.management_actions,top_accounts=excluded.top_accounts,blockers=excluded.blockers,generated_at=now()
    returning id into v_brief_id;
  end if;

  return jsonb_build_object(
    'sprint_id',p_sprint_id,'week_number',v_week,'snapshot_id',v_snapshot_id,'brief_id',v_brief_id,
    'total_ar',v_total_ar,'overdue_ar',v_overdue_ar,'cash_collected_to_date',v_collected_total,
    'cash_collected_this_week',v_collected_week,'promises_missed',v_promises_missed,
    'disputed_ar',v_disputed,'open_actions',v_open_actions,'management_attention_accounts',v_attention
  );
end;
$$;

comment on function public.refresh_recovery_sprint(uuid,date) is
'Runs the deterministic weekly operating cycle: ages promises, refreshes portfolio state, persists a Week 0-4 snapshot, and generates a factual draft CFO brief for Weeks 1-4.';
