-- YOUR COMPANY Shop QC - row-level security and the dedicated app role
--
-- Run this in the Supabase SQL editor AFTER schema.sql (a Joseph/Owner task; see
-- SUPABASE_SETUP.md). It does two things:
--   1. Creates a dedicated, limited Postgres role the desktop app logs in as. This
--      role is NOT the superuser and NOT the Supabase service_role. It can read and
--      write only the eight shopqc tables and the audit log, nothing else.
--   2. Turns on row-level security so the public API roles (anon, authenticated)
--      get no access at all, and the app role gets full access to its own schema.
--
-- ShopQC connects with a direct Postgres connection (psycopg2), not the anon or
-- JWT PostgREST API, so RLS here is defense in depth: it denies the public roles
-- and keeps the blast radius to the shopqc schema. The app role's password lives
-- only in each host's gitignored config.json. Never commit it and never paste it
-- into chat. Replace the placeholder below before running.

-- ---------------------------------------------------------------------------
-- 1. Dedicated limited login role
-- ---------------------------------------------------------------------------
-- Change the password to a strong value and record it only in config.json
-- (supabase_db_password) on each shop PC.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shopqc_app') THEN
    CREATE ROLE shopqc_app LOGIN PASSWORD 'REPLACE_WITH_A_STRONG_PASSWORD';
  END IF;
END $$;

-- Least privilege: usage on the schema, data rights on its tables, and the
-- sequences behind the IDENTITY columns. No CREATE, no rights on other schemas.
GRANT USAGE ON SCHEMA shopqc TO shopqc_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA shopqc TO shopqc_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA shopqc TO shopqc_app;

-- Apply the same rights to tables and sequences added later (for example the
-- fastener_lots table in Phase B), so a follow-up migration needs no role edit.
ALTER DEFAULT PRIVILEGES IN SCHEMA shopqc
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO shopqc_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA shopqc
  GRANT USAGE, SELECT ON SEQUENCES TO shopqc_app;

-- The app always resolves unqualified table names in the shopqc schema.
ALTER ROLE shopqc_app SET search_path = shopqc;

-- The audit log is append-only: the app inserts and reads it, but must not edit or
-- delete its own trail. Revoke at the privilege level as well as via RLS below. The
-- data tables (and fastener_lots in Phase B) keep their UPDATE and DELETE rights.
REVOKE UPDATE, DELETE ON shopqc.audit_log FROM shopqc_app;

-- ---------------------------------------------------------------------------
-- 2. Row-level security
-- ---------------------------------------------------------------------------
-- Enable RLS on every shopqc table, then grant the app role full access through a
-- permissive policy. With RLS on and no policy for anon or authenticated, the
-- public Supabase API cannot see or change QC records; only a direct connection as
-- shopqc_app (or the schema owner) can.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['projects','bol_items','pieces','traveler_fields',
                           'ncrs','rir_records','weld_records','release_records',
                           'fastener_lots'] LOOP
    EXECUTE format('ALTER TABLE shopqc.%I ENABLE ROW LEVEL SECURITY;', t);
    EXECUTE format('DROP POLICY IF EXISTS shopqc_app_all ON shopqc.%I;', t);
    EXECUTE format(
      'CREATE POLICY shopqc_app_all ON shopqc.%I FOR ALL TO shopqc_app '
      'USING (true) WITH CHECK (true);', t);
  END LOOP;
END $$;

-- audit_log: RLS on, and the app may only append (INSERT) and read (SELECT). No
-- UPDATE or DELETE policy, so the trail cannot be altered through the app role.
ALTER TABLE shopqc.audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS shopqc_app_audit_insert ON shopqc.audit_log;
DROP POLICY IF EXISTS shopqc_app_audit_select ON shopqc.audit_log;
CREATE POLICY shopqc_app_audit_insert ON shopqc.audit_log
  FOR INSERT TO shopqc_app WITH CHECK (true);
CREATE POLICY shopqc_app_audit_select ON shopqc.audit_log
  FOR SELECT TO shopqc_app USING (true);

-- Notes for the administrator (Joseph/Owner):
--   - Keep the Supabase service_role key for dashboard and admin use only. The app
--     never uses it; it logs in as shopqc_app.
--   - To rotate the app password: ALTER ROLE shopqc_app PASSWORD '...'; then update
--     supabase_db_password in each host's config.json. Nothing in git changes.
--   - To revoke a lost laptop: rotate the password as above; the old credential
--     stops working at the next connection.
