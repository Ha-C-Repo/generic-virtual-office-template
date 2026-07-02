-- Your Company Staff Training Portal - tamper-proof mastery gate
-- Run SECOND, after 01_base_schema.sql.

-- ============================================================
-- 1. Lock the answer key and module order hard
-- ============================================================
revoke all on table public.module_answers from anon, authenticated;
revoke all on table public.module_order from anon, authenticated;

-- ============================================================
-- 2. Lock progress writes (SELECT stays for portal + dashboard)
-- ============================================================
revoke insert, update, delete on table public.progress from anon, authenticated;
revoke all on table public.profiles from anon;
revoke all on table public.admins from anon;
revoke all on table public.progress from anon;
-- no insert/update policies were ever created on progress; this is belt and braces.

-- ============================================================
-- 3. The one server grader
-- ============================================================
create or replace function public.submit_quiz(p_module_id text, p_answers int[])
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_ord int;
  v_prev_module text;
  v_q_count int;
  v_wrong int[] := '{}';
  r record;
begin
  if v_uid is null then
    raise exception 'Not signed in';
  end if;

  -- unknown module ids are rejected (no zero-question auto-pass)
  select ord into v_ord from public.module_order where module_id = p_module_id;
  if v_ord is null then
    raise exception 'Unknown module';
  end if;

  select count(*) into v_q_count from public.module_answers where module_id = p_module_id;
  if v_q_count = 0 then
    raise exception 'Module has no gating check configured';
  end if;

  if p_answers is null or coalesce(array_length(p_answers, 1), 0) <> v_q_count then
    raise exception 'Expected % answers', v_q_count;
  end if;

  -- prerequisite: prior module must be complete
  if v_ord > 1 then
    select module_id into v_prev_module from public.module_order where ord = v_ord - 1;
    if not exists (
      select 1 from public.progress
      where user_id = v_uid and module_id = v_prev_module and status = 'complete'
    ) then
      raise exception 'Previous module not complete';
    end if;
  end if;

  -- grade. Return wrong question indexes only, never the correct answers.
  for r in
    select q_index, correct_idx from public.module_answers
    where module_id = p_module_id order by q_index
  loop
    if p_answers[r.q_index + 1] is distinct from r.correct_idx then
      v_wrong := v_wrong || r.q_index;
    end if;
  end loop;

  if coalesce(array_length(v_wrong, 1), 0) = 0 then
    insert into public.progress (user_id, module_id, status, score, updated_at)
    values (v_uid, p_module_id, 'complete', v_q_count, now())
    on conflict (user_id, module_id)
    do update set status = 'complete', score = excluded.score, updated_at = now();
    return jsonb_build_object('passed', true, 'wrong', '[]'::jsonb);
  end if;

  return jsonb_build_object('passed', false, 'wrong', to_jsonb(v_wrong));
end;
$$;

revoke all on function public.submit_quiz(text, int[]) from public, anon;
grant execute on function public.submit_quiz(text, int[]) to authenticated;

-- ============================================================
-- 4. Admin dashboard reader (roster + per-person progress)
-- ============================================================
create or replace function public.admin_dashboard()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_total int;
begin
  if not public.is_admin() then
    raise exception 'Admins only';
  end if;
  select count(*) into v_total from public.module_order;
  return (
    select coalesce(jsonb_agg(row_data order by row_data->>'email'), '[]'::jsonb)
    from (
      select jsonb_build_object(
        'email', p.email,
        'full_name', p.full_name,
        'enrolled_at', p.created_at,
        'completed', coalesce(pr.done, 0),
        'total', v_total,
        'certified', coalesce(pr.done, 0) >= v_total,
        'last_activity', pr.last_at,
        'modules', coalesce(pr.mods, '[]'::jsonb)
      ) as row_data
      from public.profiles p
      left join (
        select user_id, count(*) as done, max(updated_at) as last_at,
               jsonb_agg(jsonb_build_object('module_id', module_id, 'updated_at', updated_at) order by updated_at) as mods
        from public.progress where status = 'complete' group by user_id
      ) pr on pr.user_id = p.id
    ) t
  );
end;
$$;

revoke all on function public.admin_dashboard() from public, anon;
grant execute on function public.admin_dashboard() to authenticated;

-- ============================================================
-- 5. Certificates: defined but OFF (no execute grant)
-- ============================================================
create table public.certificates (
  user_id uuid not null references auth.users(id) on delete cascade,
  issued_at timestamptz not null default now(),
  primary key (user_id)
);
alter table public.certificates enable row level security;
create policy "certificates_select_own_or_admin" on public.certificates
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin());
grant select on public.certificates to authenticated;
revoke insert, update, delete on table public.certificates from anon, authenticated;

create or replace function public.claim_certificate()
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_total int;
  v_done int;
begin
  if v_uid is null then raise exception 'Not signed in'; end if;
  select count(*) into v_total from public.module_order;
  select count(*) into v_done from public.progress where user_id = v_uid and status = 'complete';
  if v_done < v_total then raise exception 'Not all modules complete'; end if;
  insert into public.certificates (user_id) values (v_uid) on conflict do nothing;
  return jsonb_build_object('issued', true);
end;
$$;

-- OFF by default: no execute grant.
revoke all on function public.claim_certificate() from public, anon, authenticated;
