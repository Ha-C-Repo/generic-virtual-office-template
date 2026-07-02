-- Your Company Staff Training Portal - READ-ONLY diagnostics
-- Safe to run in the Supabase SQL editor. Pure SELECTs, no writes.
-- Purpose: explain why a learner (e.g. Regina) cannot complete tests /
-- why completion is not tracked. Run each block; read the comments.

-- 1) Is the server grader deployed and granted to authenticated users?
--    Expect one row each for submit_quiz and admin_dashboard, grantee=authenticated.
select distinct p.proname, r.grantee, r.privilege_type
from pg_proc p
join information_schema.routine_privileges r
  on r.routine_name = p.proname and r.specific_schema = 'public'
where p.proname in ('submit_quiz','admin_dashboard','is_admin','check_signup_code','handle_new_user')
order by 1,2;

-- 2) progress table: RLS on, grants correct?
--    Expect rowsecurity = true; a select policy for authenticated; SELECT grant to authenticated only.
select relname, relrowsecurity as rls_on
from pg_class where relname in ('progress','module_answers','module_order','profiles');

select schemaname, tablename, policyname, cmd, roles
from pg_policies where tablename in ('progress','profiles','admins','certificates')
order by tablename, policyname;

select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_name in ('progress','module_answers','module_order')
order by table_name, grantee, privilege_type;

-- 3) ANSWER-KEY COMPLETENESS  <<< most likely cause of "can't complete SOME tests"
--    Every module in module_order must have its full set of answer rows.
--    A module with 0 (or a short count) is UNPASSABLE -> submit_quiz raises
--    "Module has no gating check configured" -> everything after it locks.
--    Expect: 30 modules with 3 answers each, shopqc-quality with 5. Flag anything else.
select mo.ord, mo.module_id, mo.title,
       count(ma.q_index) as answer_rows,
       case
         when count(ma.q_index) = 0 then 'NO KEY - UNPASSABLE, BLOCKS REST'
         when mo.module_id = 'shopqc-quality' and count(ma.q_index) <> 5 then 'EXPECTED 5'
         when mo.module_id <> 'shopqc-quality' and count(ma.q_index) <> 3 then 'EXPECTED 3'
         else 'ok'
       end as status
from public.module_order mo
left join public.module_answers ma on ma.module_id = mo.module_id
group by mo.ord, mo.module_id, mo.title
order by mo.ord;

-- 3b) Answer indexes must be 0-based and contiguous (q_index 0..n-1). Flag gaps/dupes.
select module_id, array_agg(q_index order by q_index) as q_indexes
from public.module_answers group by module_id
order by module_id;

-- 4) module_order itself: does it match the client (31 modules, shopqc at 31)?
select ord, module_id, title from public.module_order order by ord;

-- 5) LEARNER PROGRESS - replace the email filter as needed.
--    Shows what Regina has completed and, by ordinal, where her FIRST gap is.
--    The first missing ordinal is the module that is blocking everything after it.
with who as (
  select id as user_id, email, full_name from public.profiles
  where email ilike '%regina%'      -- <-- adjust if her email differs
)
select w.email, mo.ord, mo.module_id,
       (pr.user_id is not null) as completed,
       pr.status, pr.updated_at
from who w
cross join public.module_order mo
left join public.progress pr
  on pr.user_id = w.user_id and pr.module_id = mo.module_id and pr.status = 'complete'
order by w.email, mo.ord;

-- 5b) Her first incomplete module (the actual block point):
with who as (
  select id as user_id, email from public.profiles where email ilike '%regina%'
)
select w.email, min(mo.ord) as first_incomplete_ord,
       (select module_id from public.module_order where ord = min(mo.ord)) as first_incomplete_module
from who w
cross join public.module_order mo
left join public.progress pr
  on pr.user_id = w.user_id and pr.module_id = mo.module_id and pr.status = 'complete'
where pr.user_id is null
group by w.email;

-- 6) Roster sanity: who is enrolled, how many modules each has completed.
select pr_done.email, pr_done.done, (select count(*) from public.module_order) as total
from (
  select p.email, count(pr.module_id) as done
  from public.profiles p
  left join public.progress pr on pr.user_id = p.id and pr.status = 'complete'
  group by p.email
) pr_done
order by pr_done.done desc, pr_done.email;
