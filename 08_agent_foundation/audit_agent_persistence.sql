-- Persist one Audit Agent result transactionally.
create or replace function public.persist_audit_agent_result(
  p_job_id uuid,
  p_audit_lead_id uuid,
  p_output jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path=public
as $$
declare
  v_row jsonb;
  v_approvals integer := 0;
  v_exceptions integer := 0;
  v_run jsonb := coalesce(p_output->'model_run','{}'::jsonb);
begin
  if not exists(select 1 from public.agent_jobs where id=p_job_id and agent_name='audit') then
    raise exception 'Audit agent job % not found', p_job_id;
  end if;

  for v_row in select * from jsonb_array_elements(coalesce(p_output->'priority_accounts','[]'::jsonb)) loop
    if coalesce((v_row->>'requires_approval')::boolean,false) and coalesce(v_row->>'draft_follow_up','') <> '' then
      insert into public.approval_queue(
        job_id,agent_name,action_type,entity_type,entity_id,risk_tier,title,summary,proposed_action,evidence,status
      ) values (
        p_job_id,'audit','customer_collection_message','audit_lead',p_audit_lead_id::text,'amber',
        'Approve follow-up draft: ' || coalesce(v_row->>'customer','account'),
        coalesce(v_row->>'recommended_action',''),
        jsonb_build_object('customer',v_row->>'customer','invoice_number',v_row->>'invoice_number','draft_follow_up',v_row->>'draft_follow_up'),
        jsonb_build_array(jsonb_build_object('outstanding',v_row->'outstanding','priority_score',v_row->'priority_score')),
        'pending'
      );
      v_approvals := v_approvals + 1;
    end if;
  end loop;

  for v_row in select * from jsonb_array_elements(coalesce(p_output->'exceptions','[]'::jsonb)) loop
    insert into public.agent_exceptions(
      job_id,agent_name,entity_type,entity_id,severity,category,title,details,status
    ) values (
      p_job_id,'audit','audit_lead',p_audit_lead_id::text,
      case when v_row->>'severity' in ('low','medium','high','critical') then v_row->>'severity' else 'high' end,
      coalesce(v_row->>'category','uncertainty'),
      coalesce(v_row->>'title','Audit Agent exception'),
      jsonb_build_object('reason',coalesce(v_row->>'reason','')),
      'open'
    );
    v_exceptions := v_exceptions + 1;
  end loop;

  insert into public.agent_activity_log(
    job_id,agent_name,action,entity_type,entity_id,autonomy_tier,provider,model,prompt_version,
    output_summary,requires_approval,latency_ms,input_tokens,output_tokens
  ) values (
    p_job_id,'audit','interpret_audit','audit_lead',p_audit_lead_id::text,'green',
    v_run->>'provider',v_run->>'model','audit-agent-v0.1',
    jsonb_build_object('recovery_opportunity',p_output->'recovery_opportunity','priority_accounts_count',jsonb_array_length(coalesce(p_output->'priority_accounts','[]'::jsonb)),'exceptions_count',v_exceptions),
    v_approvals>0 or v_exceptions>0,
    nullif(v_run->>'latency_ms','')::integer,
    nullif(v_run->>'input_tokens','')::integer,
    nullif(v_run->>'output_tokens','')::integer
  );

  update public.agent_jobs
  set status=case when v_approvals>0 or v_exceptions>0 then 'waiting_approval' else 'completed' end,
      output_payload=p_output,
      completed_at=now(),
      last_error=null
  where id=p_job_id;

  return jsonb_build_object('job_id',p_job_id,'approvals',v_approvals,'exceptions',v_exceptions);
end;
$$;
