# ShopQC Handoff Changelog

## 2026-06-18 - C2 EXE build packaging for Supabase (branch feature/supabase-backend)
Found at build time that build_exe.bat did not install psycopg2, so the frozen EXE
would silently fall back to local SQLite even with storage_mode=supabase. build_exe.bat
now installs psycopg2-binary and passes --hidden-import psycopg2 and --hidden-import
shopqc.selftest to PyInstaller so the driver and the self-test are bundled. main.py
gains a --check-db flag (ShopQC.exe --check-db) that runs the connection self-test and
shows the result in a dialog, since the EXE is windowed and has no console;
shopqc/selftest.py is refactored to a shared summary() used by both the CLI and the
dialog. SUPABASE_SETUP.md documents ShopQC.exe --check-db for the host. App behavior
and the six hard blocks are unchanged. Ship gate 88/88. Backup of edited files:
_handoff/backups/2026-06-19T00-10-43Z/.

## 2026-06-18 - C deployment docs for the Supabase backend (branch feature/supabase-backend)
Docs and the connection self-test for the Supabase cutover. New SUPABASE_SETUP.md
records this deployment as done (project yourco-training, Your Company org,
us-east-1; the shopqc schema, the limited shopqc_app role, and RLS applied;
shopqc_app connected over the session pooler aws-1-us-east-1.pooler.supabase.com:5432
with SSL, search_path resolving to shopqc, audit_log append-only; this host's
config.json already set), then gives the apply steps (schema.sql then rls.sql in the
SQL editor, idempotent so re-applying to add fastener_lots is safe), the role and
password handling, the per-host config.json keys, the self-test, the NTP clock-skew
note, password rotation, and how a new shop PC points at the live database. Every
dashboard-login step is flagged as a Joseph/Owner task; the app never logs in.
DEPLOY_JOSEPH.md is rewritten from the OneDrive shared-folder single-station model to
Supabase-live plus a local SQLite cache/outbox, dropping the do-not-use-OneDrive
note. config.py drops the OneDrive db_path comment for the cache/outbox description
and adds supabase_db_sslmode (default require, with SHOPQC_DB_SSLMODE override), so
the connection enforces SSL on the pooler rather than relying on the driver default.
New shopqc/selftest.py provides "py -m shopqc.selftest": it reports the storage mode,
where it connects (never the password), reachability, and that the schema resolves to
shopqc. Tests: sslmode default, and the self-test sqlite and no-keys branches. No
live connection is needed to build or pass the gate. Ship gate 88/88. No supplier
names, no em-dashes. Backup of edited files: _handoff/backups/2026-06-18T23-05-16Z/.

  This completes A1, A2, B, and C on feature/supabase-backend; main was never
  touched. Not merged: awaiting Owner sign-off. Recommended follow-ups recorded in
  the A2 entry (a post-sync warning when a RELEASED piece has an open NCR; the
  standing K4 R1 ship-load NCR check). The fastener sync is keyed on sync_uid by
  decision (a fastener lot is a distinct receiving event; a silent cross-station
  merge by ROCAP lot would hide a double-receipt), consistent with the other
  receiving-record tables.

## 2026-06-18 - B high-strength bolt receiving (branch feature/supabase-backend)
Gate 1 receiving acceptance for high-strength bolt assemblies (RCSC Specification /
ASTM F3125). New fastener_lots table holds the lot: project, assembly type (A325,
A490, F1852, F2280), quantity, ROCAP test lot number, markings_verified,
mfr_cert_on_file, galvanized, lube_check_done, rocap_result_reference,
received_complete, received_date. The acceptance rule is a pure, centralized
predicate db.fastener_receiving_blocked_reason, the single source the receiving UI
and the tests share: a lot cannot be marked received-complete without the ROCAP lot
number recorded AND bolt, nut and washer markings verified AND the manufacturer cert
on file, and a galvanized assembly also needs the lubrication check (the ROCAP test
exposes lubrication on galvanized assemblies). The ROCAP lot number that bolt, nut
and washer share in the connection is recorded and surfaced on the receiving record.
This is receiving acceptance, not a new NCR category. shopqc/standards.py adds
FASTENER_ASSEMBLY_TYPES and an RCSC / ASTM F3125 on-screen reference. The Receiving
screen gains a "High-strength bolt lots" sub-section: Add/Edit/Delete plus a "Receive
Fastener Lots" action that enforces the rule before recording (a working list like
the BOL lines). The table is added to db.py SCHEMA (idempotent CREATE TABLE IF NOT
EXISTS), supabase/schema.sql under the shopqc schema (with sync_uid/updated_at and
the touch trigger), the sync map (SYNC_TABLES plus PARENTS, keyed on sync_uid like
the other receiving-record tables), and supabase/rls.sql. Re-applying schema.sql and
rls.sql stays safe. db.py is otherwise additive; the eight existing tables and all
six hard blocks are unchanged. Tests: test_fastener_receiving.py (acceptance rule,
each missing field, lube only when galvanized, idempotent table, no em-dashes) and a
sync round-trip for fastener_lots. Ship gate 85/85. No supplier names, no em-dashes.
Backup of edited files: _handoff/backups/2026-06-18T22-51-57Z/. Awaiting Owner
sign-off before merge.

## 2026-06-18 - A2 Supabase backend plus offline sync (branch feature/supabase-backend)
Supabase Postgres becomes the authoritative system of record, the local SQLite file
an offline cache plus write outbox. shopqc/supabase_backend.py PgConnection is the
adapter the app uses as ctx.conn: online it reads and writes Postgres (so the six
hard blocks evaluate against live cross-station state, INSERT lastrowid via RETURNING
id); when Postgres is unreachable it serves reads from the cache and applies writes
to the cache, where AFTER INSERT/UPDATE/DELETE triggers (shopqc/sync.py) queue an
outbox row with no SQL parsing. A daemon thread flushes the outbox to Postgres on
reconnect, last-write-wins keyed on the natural key (project code, piece_id; sync_uid
for the keyless record tables), remapping child foreign keys by parent natural key,
writing an audit row per applied or superseded change, then rebuilds the cache from
Postgres. shopqc/pg_client.py is the one translation seam (qmark to %s, INSERT OR
IGNORE to ON CONFLICT DO NOTHING, search_path=shopqc) with psycopg2 imported lazily
so a box without it falls back to sqlite. supabase/schema.sql is the Postgres DDL
under a dedicated schema named shopqc (8 tables mirrored plus audit_log, sync_uid and
updated_at on each, deliberate TEXT dates and INTEGER flags to match the app
contract); supabase/rls.sql creates a least-privilege role shopqc_app (not superuser,
not service_role), row-level security denying the public API roles, and an
append-only audit_log. db.py, receiving.py, and all six hard blocks are untouched.
Tests use tests/fakes.py FakePostgres (in-memory, no live connection): queue while
down, flush on reconnect, natural-key LWW with no duplicate on a cross-station
collision, FK remap, audit rows, the cache rebuild, and the six hard blocks driven
through the online adapter. Ship gate 75/75.

  Adversarial review (5 dimensions: sync correctness, adapter contract, hard blocks,
  SQL/schema, concurrency). Fixes applied: last-write-wins switched from sync_uid to
  the natural key so two stations creating the same code or piece_id merge instead of
  colliding on UNIQUE; a non-resolving foreign key is audited (fk_unresolved) and
  skipped, never written as a corrupt NULL; offline writes commit atomically under
  the cache lock and commit() is a no-op so the online write path never contends on
  the lock; the sync thread is joined on shutdown; audit_log is append-only at the
  privilege and policy level. Verified false positives: the SQLite millisecond format
  matches Postgres (both 23-char UTC ms strings), and the sync thread uses its own
  connections so there is no cross-thread connection use. Documented residuals (not
  defects): last-write-wins assumes stations run NTP (clock skew caveat, goes in the
  deploy doc in Phase C); a piece released OFFLINE while another station opens an NCR
  is the accepted offline weakening of hard block 4 (it re-engages online and on
  sync, per the K4 R1 residual); a recommended follow-up is a post-sync warning when
  a RELEASED piece has an open NCR. SupabaseBackend and sync are exercised only
  through FakePostgres; the live Supabase apply and connection self-test are a
  Joseph/Owner step documented in Phase C. Awaiting Owner sign-off before merge.

## 2026-06-18 - A1 storage backend abstraction (branch feature/supabase-backend)
First phase of making Supabase Postgres the system of record. Introduces a
StorageBackend seam with zero behavior change. New shopqc/storage.py defines
StorageBackend, SqliteBackend (the shipped single-file path verbatim:
journal_mode=DELETE, WAL off, db.connect plus db.init_db), a StorageError carrying
the two existing startup messages, and make_backend(cfg) which selects on
config.storage_mode and falls back to SqliteBackend when Supabase is unavailable or
its credentials are absent, so a dev box still runs. config.py gains storage_mode
("sqlite" default) plus the Supabase connection keys (supabase_db_url or the five
split fields), and supabase_connection_params(cfg) resolving them with environment
override (SHOPQC_DB_URL, SHOPQC_DB_HOST and friends); config.json stays gitignored,
credentials never committed. shopqc/ui/app.py now builds the backend at the single
connection site, keeps the exact folder and database error dialogs, and shows the
storage mode in the status bar. db.py, receiving.py, and all six hard blocks are
untouched. Tests: test_storage_backend.py (SqliteBackend parity through Gate 2/3,
schema and pragma checks, fallback) and test_config_supabase.py (credential resolver
plus env override). Ship gate 57/57 (was 44). No supplier names, no em-dashes.
Backup of edited files: _handoff/backups/2026-06-18T20-17-03Z/. SupabaseBackend and
sync land in A2. Awaiting Owner sign-off before merge.

## 2026-06-18 - K1 SJI joist traveler variant (branch feature/joist-traveler)
Additive SJI Spec 100-2020 joist traveler variant. Adds pieces.traveler_type
("STRUCTURAL" default, "JOIST"), a parallel 20-field JOIST_TRAVELER_FIELDS set,
spec-driven Gate 2/Gate 3/PDF selection, joist section detection at receiving,
and camber/bridging/seat capture handlers. Structural 18-field sequence unchanged
(diff-verified). All six hard blocks transfer. Safe additive migration via
db.migrate() (ALTER ADD COLUMN, idempotent). Backup of edited files:
_handoff/backups/2026-06-18T15-24-07Z/. Smoke test green (structural + joist).
Awaiting Owner sign-off before merge. See JOIST-TRAVELER-MIGRATION-2026-06-18.md.

  Adversarial review (per-hard-block + structural/migration/detection/SJI): all
  six hard blocks clean; one real PDF-rendering defect found and fixed
  (traveler_pdf NCR substitution hardcoded field 18, which is the joist CWI
  release row; now targets spec ncr_auto via _traveler_cell_value, regression
  added). Camber out-of-tolerance is advisory by design (capture + guide to NCR).

## 2026-06-18 - K2 approved logo on all PDFs (branch feature/joist-traveler)
Embedded the approved Your Company silver-on-dark logo on every PDF via the shared
reports._header (RIR, traveler, NCR log, Final Release Certificate, manifest,
project summary; 6 generators, no separate weld-log PDF). Logo loaded through
config.resource_path from bundled masters at ShopQC/brand/logos/ (byte-identical
copies of the Tier 1 masters); build_exe.bat updated with --add-data for both PNGs
plus pillow. Aspect ratio preserved (no stretch/skew), mark never recolored. Header
band set to the master's own plate color #231F20 (the one permitted change, so the
lockup sits seamlessly) instead of #141414; red #C8102E accent rule kept; legal
name moved to the sub-line since the logo carries the wordmark. _logo() degrades to
title-only if the file is unreadable. Smoke test green (all PDFs build). Backup:
_handoff/backups/2026-06-18T15-52-36Z/.

## 2026-06-18 - K3 pytest suite + ship gate (branch feature/joist-traveler)
Raised from one smoke test to green-before-ship. Added a 41-test pytest suite
(tests/test_*.py) covering BOL parse of the Hillcrest fixture incl joist/deck/anchor
scope, confidence tagging, piece ID sequencing, full QR + bare-ID scan, ZPL build,
locked sequence, pre-weld CWI block, NCR hold + release, Gate 3 completeness
re-verify, CEO co-sign trigger at >=50T and IAS plus exact-name, EOR-before-close,
joist variant, migration, MTR capture, and all 6 PDF generators (structural +
joist). One-line ship gate tests/run_all.py prints PASS/COUNT and exits non-zero on
failure; wired into build_exe.bat (build aborts if red) with pytest added to deps.
pytest.ini restricts collection to test_*.py so smoke_test.py is not double-run.
Item 3: structured MTR capture at Gate 1 - bol_items gains astm_grade/fy/fu/ce
(additive migration), captured in the receiving line dialog, shown on the RIR PDF;
shopqc/standards.py holds ASTM specified minimums + astm_shortfall flag. Also fixed
the K1-flagged Gate 3 blocker: receiving now captures the MTR lot and passes it to
seed_traveler so info field 4 auto-signs (no hard block weakened; empty lot still
leaves field 4 unsigned). Item 4: AISC 303-22 tolerance helper text on the Gate 2
dimensional field (field 12, via a new FormDialog 'note' kind) and the receiving
straightness check. Hard block 5 centralized into db.needs_ceo_cosign /
ceo_name_matches / CEO_NAME (behavior-preserving). Structural TRAVELER_FIELDS
unchanged (diff-verified). Legacy smoke test still green. Backup:
_handoff/backups/2026-06-18T16-30-16Z/.

  Adversarial review of K3 (8 hard-block/parser/test dimensions): 8 defects found
  and fixed, 0 outstanding. Root fix: the joist mark pattern (piece_ids.JOIST_RE,
  bol_import.JOIST_PAT) now requires a chord/size digit and handles joist girders
  (48G8N10K), so bare series and common tokens (50K, 5G, 250K, 600G) no longer
  mis-detect and real girder marks are no longer missed; bare-series scope is found
  by detect_scope. Test quality: extracted the UI-run hard-block logic into testable
  db helpers (lowest_unsigned_floor=block 2, cwi_signature_ok=block 1,
  release_blockers=block 4), wired the UI to call them, and rewrote the weak NCR/
  Gate-3 tests to assert real behavior. Fixed _sign_optional mislabeling the joist
  UT/MT field as Camber (now reads the field name). Final suite 42/42; smoke green.

## 2026-06-18 - K4 hard-block code review (branch feature/joist-traveler)
Final consolidated hard-block review across K1+K2+K3 plus an independent 6-block
red-team. Five blocks clean as built (pre-weld CWI, locked sequence, NCR traveler
freeze, CEO co-sign, EOR-before-close), with exact enforcement lines recorded in
K4-SHIP-READINESS-2026-06-18.md. One hard-block defect found and FIXED: Gate 3
(block 4) re-verified release_blockers only BEFORE the modal sign-off dialog, a
TOCTOU window through which a late NCR from another station could release a piece;
release() now re-verifies again immediately before the commit (regression
test_release_reverify_runs_after_signoff_dialog added). Concurrency confirmed:
journal_mode=DELETE (no WAL), busy_timeout 15s, execute_write 5x retry; gates
re-read live state so a stale UI cannot pass. Residual (not hard blocks, not
changed): ship_load does not check open NCRs (a post-release NCR'd piece can ship -
recommend a fix), fabrication.open_ncr lacks a status guard, NCR auto-number uses
MAX(id). Suite 43/43; smoke green; structural tuple identical; no em-dashes. EXE
build NOT run here (Windows-host step, Cowork runs build_exe.bat via Windows MCP).
