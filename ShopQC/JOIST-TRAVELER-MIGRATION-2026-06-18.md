# SJI Joist Traveler Variant - Migration Note (K1)

**Date:** 2026-06-18
**Branch:** feature/joist-traveler
**Status:** Built and green. Awaiting Owner sign-off before merge (this change
adds a traveler variant, so it was gated on CEO approval; approval recorded
2026-06-18).
**Scope:** Additive SJI Spec 100-2020 joist traveler variant. The locked 18-field
structural sequence is untouched. The triggering case is Elite Crossing (Lake
Jackson TX): 42 of 30KCS4 at 50 ft, a deflection issue under a field modification.
This variant is the instrument meant to catch that.

## 1. What changed, in one line

A piece now carries a `traveler_type` ("STRUCTURAL" default, "JOIST"). Joist pieces
get a parallel 20-field SJI traveler instead of the 18-field structural one. Gate 2,
Gate 3, and the traveler PDF read the field set off the piece. Nothing about an
existing piece changes.

## 2. Schema change (safe and additive)

One column, added two ways so both new and existing databases are correct:

- New databases: `pieces.traveler_type TEXT NOT NULL DEFAULT 'STRUCTURAL'` is in
  the `CREATE TABLE` in `db.SCHEMA`.
- Existing databases: `db.migrate(conn)` runs on every startup (called at the end
  of `init_db`). It checks `PRAGMA table_info(pieces)` and, if the column is
  absent, runs `ALTER TABLE pieces ADD COLUMN traveler_type TEXT NOT NULL DEFAULT
  'STRUCTURAL'`. `ADD COLUMN` with a constant default rewrites no rows and drops no
  data, which is the only safe shape on the shared network file (journal_mode=
  DELETE, no WAL). `migrate` is idempotent: a second run is a no-op.

No other table changed. No destructive ALTER. No data backfill needed: every row
that existed before gets `'STRUCTURAL'` automatically, so every traveler already in
the field keeps its exact 18-field set and every gate behaves as before.

Camber, bridging, seat, span/depth, and anchorage values are stored in the
existing `traveler_fields.value` and `.notes` columns (for example "0.75 in vs SJI
0.75 in", "3 rows / Diagonal", "5.0 in / Underslung"). No new table was needed.

## 3. How existing pieces keep working

`db.spec_meta(traveler_type)` returns the variant metadata and falls back to
STRUCTURAL for any null or unknown value. So a legacy piece (column just added,
value defaulted) and any future bad data both resolve to the structural 18-field
behavior. The structural `TRAVELER_FIELDS` tuple is byte-for-byte identical to
before (verified by diff against the pre-change backup). The structural smoke-test
path is unchanged and still passes.

## 4. The joist field set (SJI Spec 100-2020) - PROVISIONAL, flagged for Owner

The NC-QC-FAB-001 program PDF was not available and does not enumerate joist
fields, so this set is proposed from SJI Spec 100-2020 and the Joseph brief, per
the brief's instruction to propose and flag rather than block. It lives in
`db.JOIST_TRAVELER_FIELDS`. It mirrors the structural gate structure on purpose, so
all six hard blocks transfer without new enforcement code.

| # | Field | Kind | Gate |
|---|---|---|---|
| 1 | Project Name / Job No. | info | receiving |
| 2 | Joist Mark (SJI designation) | info | receiving |
| 3 | Joist Designation + Heat/Lot | info | receiving |
| 4 | MTR / SJI mill cert on file (lot no.) | info | receiving |
| 5 | Span and depth verified vs SJI spec | measure | 2 |
| 6 | Top and bottom chord check | op | 2 |
| 7 | Web member check | op | 2 |
| 8 | Pre-weld inspection (CWI) | cwi | 2 (HARD BLOCK) |
| 9 | Welder ID / WPS (chord, web, seat welds) | weld | 2 |
| 10 | Post-weld VT (CWI) | cwi | 2 |
| 11 | Bearing seat depth and type | seat | 2 |
| 12 | Bridging rows installed and type | bridging | 2 |
| 13 | End anchorage / support attachment | measure | 2 |
| 14 | Camber measured vs SJI-specified | camber | 2 (deflection catch) |
| 15 | UT / MT result reference | optional | 2 |
| 16 | Surface prep / paint / DFT reading | dft | 2 |
| 17 | Final Release - Shop Director | release | 3 |
| 18 | Final Release - CWI | release | 3 |
| 19 | Shipped - date + truck/load | release | ship |
| 20 | NCR number (if any) | auto | any |

Decisions in this set that Owner should confirm against the program when it is
in hand:

- Camber (field 14) is MANDATORY for joists (not the optional "may be N/A" that
  structural field 13 is). It captures measured camber against the SJI-specified
  value. This is the deflection-catch. The out-of-tolerance threshold used to nudge
  the inspector toward an NCR is a PROVISIONAL 0.25 in placeholder, because SJI
  camber is span-dependent and the program table was not available. The number is
  marked in `fabrication.py` `_sign_camber` and should be replaced with the SJI
  span-based value or a per-joist specified input when confirmed.
- Pre-weld CWI is at field 8 and post-weld VT at field 10, the same positions as
  structural, so `_sign_cwi` and `_sign_weld` are reused unchanged.

## 5. Type detection at receiving

`piece_ids.traveler_type_for_section(section)` picks the variant from the section or
mark. SJI marks lead with a depth number then a series token (K, KCS, LH, DLH, SLH,
G) and a chord/size digit; structural shapes lead with a letter, so the two separate
cleanly. Examples detected as JOIST: 30KCS4, 30K7, 22K9, 24LH06, 52DLH15, 60G8,
48G8N10K. `section_format_ok` was extended to accept joist designations by format (it
previously rejected them), so a joist mark can be entered manually at receiving.
Validation is by format only; the app never invents or weighs a joist (weights stay
in `bridge/aisc_validator.py` in the Virtual Office).

NOTE (tightened in K3): the trailing chord/size digit after the series is required.
A bare series like 30K or 60G, and common BOL tokens like 50K or 5G, are NOT
detected as joist marks; bare series in a proposal ("30K and 20K series") are scope
language found by `bol_import.detect_scope`, not piece marks. K3 also extended the
BOL parser (`bol_import.py`) to detect complete joist marks and package scope. The
Hillcrest 380 fixture is a scope and tonnage proposal, not a per-piece schedule, so
its per-piece joist marks are entered at receiving from the shipper BOL and SJI mill
certs; the parser confirms the package carries joist/deck/anchor scope.

## 6. How the six hard blocks hold for the joist variant

1. Pre-weld CWI block: field 8 is kind "cwi" and sits in the floor sequence, so
   weld and downstream steps are unreachable until a CWI name is recorded.
   `_sign_cwi` rejects an empty CWI name. Same code as structural.
2. Locked sequence: `_active_field` and `sign_active` sign only the lowest unsigned
   field in the variant floor range (5..16 for joist), from `db.spec_meta`.
3. NCR hold freeze: `sign_active` blocks while an open NCR exists; `open_ncr` sets
   NCR_HOLD and writes the NCR number to the variant auto field (20 for joist).
4. Gate 3 completeness re-verify: `release.py` uses `db.gate3_last_field` (16 for
   joist) on load and again at sign time.
5. CEO co-sign at >= 50T or IAS: unchanged, project-level. The joist test runs a
   212T project, so the co-sign is exercised on the joist path.
6. EOR reference before closing an unauthorized field modification NCR: centralized
   in `db.ncr_close_blocked_reason`, called from the NCR UI and asserted in the
   test. The joist camber handler explicitly routes a deflection / field-
   modification failure into this category, which is the Elite Crossing path.

## 7. Files touched (all additive)

- `shopqc/db.py`: JOIST_TRAVELER_FIELDS, TRAVELER_SPECS, spec helpers, EOR_CATEGORY,
  ncr_close_blocked_reason, traveler_type column, migrate(), variant-aware
  seed_traveler and field_kind.
- `shopqc/piece_ids.py`: JOIST_RE, is_joist_section, traveler_type_for_section,
  section_format_ok extended.
- `shopqc/ui/receiving.py`: detect and store traveler_type per piece.
- `shopqc/ui/fabrication.py`: per-piece floor range, variant dispatch, new handlers
  (_sign_measure, _sign_seat, _sign_bridging, _sign_camber, _sign_dft), spec-driven
  NCR auto field; structural _sign_op number branches guarded to STRUCTURAL only.
- `shopqc/ui/release.py`: spec-driven Gate 3 completeness, release fields, ship field.
- `shopqc/ui/ncr.py`: hard block 6 routed through db.ncr_close_blocked_reason
  (behavior preserving).
- `shopqc/reports.py`: traveler PDF and release certificate read the variant.
- `tests/smoke_test.py`: joist Gate 1-2-3 path plus detection, migration, camber,
  bridging, seat, CWI block, and EOR-before-close assertions. Structural path
  unchanged.

Pre-change backup: `_handoff/backups/2026-06-18T15-24-07Z/`.

## 8. One finding to hand to K3/K4 (not fixed here, out of K1 scope)

Info field 4 (MTR lot) is auto-signed at receiving only when a lot value is
present. `receiving.receive()` currently seeds lot as empty, and info fields sit
outside the floor range, so they cannot be signed afterward. With an empty lot,
field 4 lingers in the Gate 3 completeness check and would block release. The
existing structural smoke test masks this by seeding a lot. This is pre-existing
structural behavior, not introduced by the joist variant. It is a design call for
Owner (require a lot at receiving, capture it on the receiving screen, or exclude
info fields from the completeness window), so it is flagged for the K3 test suite
and the K4 hard-block review rather than changed under K1.

## 9. Verification

```
SMOKE TEST PASS: gates, hard blocks, IDs, scan parse, labels, all 6 PDFs
JOIST VARIANT PASS: detection, migration, 20-field SJI traveler, camber +
bridging + seat capture, CWI block, EOR-before-close, Gate 3 CEO co-sign
```

All modules byte-compile. The structural `TRAVELER_FIELDS` tuple is identical to
the pre-change backup.

## 10. Adversarial review outcome

A multi-agent review ran one reviewer per hard block plus reviewers for the
structural-preservation, migration, detection, and SJI-data-source dimensions,
with every flagged defect independently refuted before it was trusted. Result:

- All six hard blocks: zero defects for the joist variant.
- Migration safety and detection: zero defects.
- One real defect found and FIXED: `reports.traveler_pdf` substituted the NCR
  list on a hardcoded field 18. On the joist traveler field 18 is the CWI
  Final-Release row, so printing a joist traveler for a piece that ever carried an
  NCR overwrote that Gate 3 release cell with NCR ids. Fixed by targeting the
  variant NCR field from `db.spec_meta(...)["ncr_auto"]` (18 structural, 20 joist),
  extracted into the testable `_traveler_cell_value` helper, with a regression in
  the smoke test that prints the joist traveler with a non-empty NCR list. No hard
  block was ever bypassed by this defect; it was a PDF rendering issue only.
- One finding dismissed on verify (by design, not a defect): camber out of
  tolerance is advisory (a strong inspector warning) and does not itself block
  sign-off or auto-open an NCR. The brief asks the instrument to CAPTURE camber vs
  the SJI-specified value and make a field modification TRACEABLE into the NCR
  path, which it does; the human opens the NCR, consistent with verify-don't-
  generate. Auto-opening an NCR on an out-of-tolerance camber is a possible future
  hardening for Owner to decide, recorded here, not changed under K1.
