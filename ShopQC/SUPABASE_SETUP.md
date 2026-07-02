# Shop QC - Supabase setup and connection

Supabase Postgres is the live system of record. Each shop PC keeps a local SQLite
file that is only an offline cache and a write outbox: when the network drops the
floor keeps capturing scans locally, and they flush to Supabase on reconnect with
last-write-wins and an audit-log row per change. The schema lives under a dedicated
`shopqc` schema, never `public`.

Every step that needs a Supabase dashboard login is a Joseph or Owner task. The app
never logs in; it connects only as the limited role with the credentials in
config.json.

## Status for this deployment (already done)

- Project: `yourco-training` (Your Company org, region us-east-1).
- Schema `shopqc` applied from `supabase/schema.sql`: the eight QC tables plus
  `fastener_lots` and `audit_log`, all under `shopqc.*`.
- Security applied from `supabase/rls.sql`: the limited login role `shopqc_app`
  (not the superuser, not the Supabase service_role), row-level security on every
  table, and an append-only `audit_log`.
- Connection verified as `shopqc_app` over the session pooler with SSL; the role's
  search_path resolves to `shopqc`.
- This host's `dist/config.json` already has `storage_mode=supabase` pointed at the
  session pooler `aws-1-us-east-1.pooler.supabase.com:5432` with the `shopqc_app`
  credentials.

So the apply steps below are a reference. You repeat them only to stand up a fresh
project, and you run the config and self-test steps on each new shop PC. Because
`schema.sql` and `rls.sql` are idempotent, re-running them to pick up a new table
(for example `fastener_lots`) is safe and does not disturb existing data.

## 1. Apply the schema (Supabase SQL editor; Joseph/Owner task)

1. Open the project's SQL editor in the Supabase dashboard.
2. Run the contents of `supabase/schema.sql`. It creates the `shopqc` schema and its
   tables, the sync columns, and the updated_at trigger. Safe to re-run.
3. Run the contents of `supabase/rls.sql`. It creates the `shopqc_app` role, grants
   it least-privilege rights on the `shopqc` tables, sets its search_path to
   `shopqc`, enables row-level security, and makes `audit_log` append-only.

## 2. The limited app role and its password (Joseph/Owner task)

`rls.sql` creates `shopqc_app` with a placeholder password. Set a strong one in the
SQL editor and record it only in config.json (next section), never in git or chat:

    ALTER ROLE shopqc_app PASSWORD 'a-strong-password';

`shopqc_app` can read and write only the `shopqc` tables and can only append to
`audit_log`. Keep the Supabase service_role key for dashboard and admin use; the app
never uses it.

## 3. Point a shop PC's config.json at Supabase

`config.json` sits next to the EXE, is gitignored, and is never committed. Set:

- `storage_mode`: `supabase`
- Either `supabase_db_url` (a full `postgresql://...` string with `sslmode=require`),
  or the split keys:
  - `supabase_db_host`: `aws-1-us-east-1.pooler.supabase.com`
  - `supabase_db_port`: `5432`
  - `supabase_db_name`, `supabase_db_user`, `supabase_db_password`: the exact values
    from the Supabase Connect dialog, session pooler / Session mode. The pooler often
    shows the user as a project-qualified form; use exactly what the dialog shows for
    `shopqc_app`.
  - `supabase_db_sslmode`: `require` (the default; the pooler requires SSL)
- `station_name`: `GATE1`, `FAB`, or `GATE3`

Environment variables override any of these at runtime: `SHOPQC_DB_URL`, or
`SHOPQC_DB_HOST` / `SHOPQC_DB_PORT` / `SHOPQC_DB_NAME` / `SHOPQC_DB_USER` /
`SHOPQC_DB_PASSWORD` / `SHOPQC_DB_SSLMODE`. If no keys are present, the app falls back
to the local SQLite file so a dev box still runs.

## 4. Connection self-test

On a shop PC that has the EXE, run it from a command prompt in the `dist` folder:

    ShopQC.exe --check-db

It reads the `config.json` next to the EXE (the host's real credentials) and shows a
dialog: the storage mode, where it is connecting (never the password), whether
Postgres is reachable, and that the schema resolves to `shopqc` with a project row
count. From a source checkout you can instead run `py -m shopqc.selftest`, which
prints the same result and reads the `config.json` in the project root (point it at
Supabase with the `SHOPQC_DB_*` environment variables or a configured config.json).
In the running app, the bottom status bar shows `Storage: supabase` when the Supabase
backend is active; if it shows `Storage: sqlite`, the app fell back to the local file
(check the credentials and that psycopg2 is present).

## 5. Clock sync (NTP)

The reconnect merge is last-write-wins by a wall-clock timestamp. Keep the shop PCs
on NTP (the Windows default internet time sync is enough). A badly wrong clock on one
station could make its edits win or lose incorrectly when the outbox flushes. Stations
on a LAN with normal time sync are fine.

## 6. Rotate the app password (Joseph/Owner task)

In the SQL editor:

    ALTER ROLE shopqc_app PASSWORD 'a-new-strong-password';

Then update `supabase_db_password` in each host's config.json. Nothing in git
changes. The old credential stops working at the next connection, which is also how
you revoke a lost laptop.

## 7. Add a new shop PC

1. Copy `ShopQC.exe`, run it once to create `config.json`.
2. Fill the config.json keys in section 3 with the `shopqc_app` credentials.
3. Run the self-test in section 4. When it reports OK, the PC is on the live data.
