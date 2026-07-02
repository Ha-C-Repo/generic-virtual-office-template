# ShopQC app role + RLS (Supabase) - ALREADY APPLIED, do not run

Updated 2026-06-23 with Owner monitoring. Verdict: do NOT run the draft script.
Its work is already live in the database.

## What we found (read-only diagnostics, run live in the SQL editor)

Against the `yourco-training` Supabase project:

- `shopqc_app` role: EXISTS (1).
- `shopqc` schema: EXISTS, with 10 tables.
- Row-level security on all 10 shopqc tables: ENABLED (true) - audit_log,
  bol_items, fastener_lots, ncrs, pieces, projects, release_records,
  rir_records, traveler_fields, weld_records.
- public schema: 6 tables (the training-portal tables).

The draft script's two stated goals were "1. create the dedicated limited role"
and "2. turn on row-level security." Both are already done. The ShopQC app
already connects as `shopqc_app` using the password in each shop PC's
`config.json`.

## Why NOT to run it

Re-running the draft would, at best, error on "role already exists," and at
worst reset the `shopqc_app` password to the placeholder and lock every shop PC
out of the database. There is nothing to gain: the role, schema, tables, and RLS
are all in place.

## Recommended cleanup

The leftover draft snippet in the Supabase SQL editor (titled "Untitled query",
first line "YOUR COMPANY Shop QC - row-level security and the dedicated app role")
should be renamed to flag it as applied, or deleted, so no one runs it later.
Suggested name: "ShopQC role + RLS (APPLIED 2026-06, DO NOT RUN)".

Deleting it is also safe: it is not a source file in the repo, and its effects
are already applied to the database.

## Already done this session (no action needed)

- M31 "Shop QC Software" training module is live on the portal and listed in the
  suite (Phase Eight). Final Knowledge Check enabled and verified
  (1 module_order row, 5 module_answers rows). SQL in
  `training-portal/sql/04_shopqc_module.sql`.
