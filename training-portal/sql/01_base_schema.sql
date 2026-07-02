-- Your Company Staff Training Portal - base schema
-- Run FIRST in the Supabase SQL editor.

-- ============================================================
-- profiles (one row per auth user, created by trigger)
-- ============================================================
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- ============================================================
-- admins (flagged manually by SQL after self-registration)
-- ============================================================
create table public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null
);

alter table public.admins enable row level security;

-- helper: is the current user an admin
create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public, pg_temp
stable
as $$
  select exists (select 1 from public.admins a where a.user_id = auth.uid());
$$;

revoke all on function public.is_admin() from public;
grant execute on function public.is_admin() to authenticated;

-- profiles policies (after is_admin exists)
create policy "profiles_select_own_or_admin" on public.profiles
  for select to authenticated
  using (id = auth.uid() or public.is_admin());

-- admins: each user may check their own flag
create policy "admins_select_self" on public.admins
  for select to authenticated
  using (user_id = auth.uid());

-- ============================================================
-- module_order (server-side prerequisite chain; locked like the key)
-- ============================================================
create table public.module_order (
  module_id text primary key,
  ord int not null unique,
  title text not null
);

alter table public.module_order enable row level security;
-- NO policies on purpose. Client never reads this.

insert into public.module_order (module_id, ord, title) values
  ('front-desk',          1,  'Front Desk Procedural'),
  ('w11-m365-lab',        2,  'Windows 11 & M365 Lab'),
  ('ai-productivity',     3,  'AI Productivity'),
  ('steel-101',           4,  'Steel 101'),
  ('teams-full',          5,  'Microsoft Teams'),
  ('office-full',         6,  'Office Apps'),
  ('comms',               7,  'Professional Business Communication'),
  ('doc-flow',            8,  'Document Flow'),
  ('scheduling',          9,  'Scheduling'),
  ('isn-compliance',      10, 'ISNetworld & Compliance'),
  ('job-lifecycle',       11, 'Job Lifecycle'),
  ('vendor-client',       12, 'Vendor & Client Management'),
  ('outlook-depth',       13, 'Outlook in Depth'),
  ('pdf-pdfgear',         14, 'PDF and PDFGear'),
  ('buildingconnected',   15, 'BuildingConnected'),
  ('isn-portal',          16, 'ISNetworld Portal'),
  ('ap-ar',               17, 'AP and AR'),
  ('phone-scripts',       18, 'Phone Scripts'),
  ('change-orders',       19, 'Change Orders'),
  ('safety-fundamentals', 20, 'Safety Fundamentals'),
  ('ceo-inbox',           21, 'Managing the CEO Inbox'),
  ('ceo-drafting',        22, 'CEO Drafting'),
  ('meetings',            23, 'Meetings'),
  ('travel',              24, 'Travel'),
  ('discretion',          25, 'Discretion'),
  ('three-companies',     26, 'Three Companies'),
  ('office-ops',          27, 'Office Ops'),
  ('purchasing',          28, 'Purchasing'),
  ('onboarding',          29, 'Onboarding'),
  ('supervising',         30, 'Supervising');

-- ============================================================
-- module_answers (hidden key; rows inserted by 03_answer_key.sql)
-- ============================================================
create table public.module_answers (
  module_id text not null references public.module_order(module_id),
  q_index int not null,
  correct_idx int not null,
  primary key (module_id, q_index)
);

alter table public.module_answers enable row level security;
-- NO policies on purpose. Client never reads this.

-- ============================================================
-- progress (SELECT for portal/dashboard; writes only via grader)
-- ============================================================
create table public.progress (
  user_id uuid not null references auth.users(id) on delete cascade,
  module_id text not null references public.module_order(module_id),
  status text not null default 'complete',
  score int,
  updated_at timestamptz not null default now(),
  primary key (user_id, module_id)
);

alter table public.progress enable row level security;

create policy "progress_select_own_or_admin" on public.progress
  for select to authenticated
  using (user_id = auth.uid() or public.is_admin());

-- ============================================================
-- explicit grants ("expose new tables" is OFF for this project)
-- ============================================================
grant usage on schema public to anon, authenticated;
grant select on public.profiles to authenticated;
grant select on public.admins to authenticated;
grant select on public.progress to authenticated;
-- module_answers and module_order: NO grants. RLS has no policies either.

-- ============================================================
-- signup gate: shared code required, profile auto-created
-- ============================================================
-- Code check must run BEFORE insert (to reject), but the profile insert must
-- run AFTER insert: profiles.id has an FK to auth.users(id), which does not
-- exist yet in a BEFORE trigger. Two triggers, fixed 2026-06-09.
create or replace function public.check_signup_code()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if coalesce(new.raw_user_meta_data->>'signup_code', '') <> 'STEEL2026' then
    raise exception 'Invalid signup code';
  end if;
  return new;
end;
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name', ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger a_check_signup_code
  before insert on auth.users
  for each row execute function public.check_signup_code();

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
