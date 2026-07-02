# TAKEOFF SCHEMA V2

**File:** `takeoff_pipeline/docs/TAKEOFF_SCHEMA_V2.md`
**Status:** SPECIFICATION ONLY. This document defines the schema. It contains no code.
**Date:** 2026-06-11
**Implements:** P24, P25, P26, P27, P28, P29, P30, P34. References: P10, P23, F4. Pattern text lives in `COWORK-HANDOFF-MASTER-2026-06-11.md`, section 03; F4 in the same file's F-track table.
**Governs:** Prompts 4, 5, 6, 7, and 9 in `COWORK-CLAUDE-CODE-PROMPTS-2026-06-11.md`. Code built under those prompts conforms to this document. Where code and this document disagree, this document wins until it is amended.

## 1. Purpose and boundaries

The takeoff is an objective measurement record (P27). Anyone working from the same drawings must be able to reproduce it. The estimate is a different artifact. It adds rates, assumptions, and strategy downstream. Ivan verifies the takeoff. Owner approves the estimate. Different documents, different gates, never merged.

The takeoff file carries zero pricing (P25). Section 12 states the rule in full. The estimate references the takeoff by its version hash (section 13). It never edits the takeoff file.

## 2. The four artifacts (P34)

One xlsx workbook per takeoff. Four sheets. Sheet names are exact, uppercase, and fixed.

| Sheet | Holds | Written by |
|---|---|---|
| `TAKEOFF` | The measurement act. One measured quantity per row. | Takeoff pipeline: census output plus manual-entry rows. |
| `BOQ` | Quantities plus labor, plant, and subcontract context. Hours and time, never dollars. | `apply_assemblies.py` from TAKEOFF rows (Prompt 9). |
| `BOM` | Materials only. What the shop orders. | `apply_assemblies.py` from TAKEOFF rows (Prompt 9). |
| `PRICING_SCHEDULE` | Structure only: line organization and item references. | Skeleton by the exporter (Prompt 5). Never populated further inside this file. Pricing values are populated by the estimate layer in its own workbook copy (section 11), NEVER by the takeoff pipeline. |

No other sheets ship in the takeoff file. A worksheet not named above fails validation.

## 3. TAKEOFF sheet

### 3.1 Layout

- Row 1: metadata row. Stamp fields per section 13.3. Excluded from the version hash.
- Row 2: column headers. Exactly the eleven columns of 3.2 followed by the four columns of 4.2, in order. Fifteen columns, A through O.
- Row 3 and down: one measured quantity per row.

### 3.2 Mandatory fields

Every TAKEOFF row carries all eleven columns. Values are required unless marked otherwise.

| Column | Type | Rule |
|---|---|---|
| `item_id` | text | Unique within the file. Format `<CLASS>-<NNN>`, for example `COL-001`, `JST-014`. Classes: `COL`, `BEAM`, `JST`, `DECK`, `PLATE`, `ANCH`, `MISC`. Assigned once, never reused, never renumbered. |
| `designation` | text | The tag as written on the drawing. Examples: `W12X26`, `HSS6X6X1/4`, `28K7`. Never an invented or normalized tag. |
| `mode` | enum | `COUNT`, `LINEAR`, or `AREA`. Nothing else (P28). |
| `qty` | number | The measured quantity, in the unit on the same row. |
| `unit` | enum | Locked to mode: `EA` for COUNT, `LF` for LINEAR, `SF` for AREA. |
| `primary_source` | text | Sheet reference where the quantity was measured, for example `S2.1 ROOF FRAMING PLAN`. Must follow the class table in section 5. |
| `secondary_source` | text, value optional | Cross-check reference when one exists. Blank is allowed. The column is not. |
| `confidence` | enum | `high`, `medium`, or `low`. Semantics in section 6. |
| `sheet` | text | Sheet number the row's bbox sits on. Manual-entry rows follow section 7. |
| `bbox` | text | `[x0, y0, x1, y1]` in PDF points on that sheet, PyMuPDF page coordinates. Matches `census.db` (Appendix A). Manual-entry rows write `MANUAL`. |
| `notes` | text, value optional | Free text plus the fixed tokens below. |

A row missing `mode` or `primary_source` FAILS validation (section 14). No exceptions.

Fixed notes tokens. Machine-readable. Each is uppercase and ends with a colon.

| Token | Meaning |
|---|---|
| `CONFLICT:` | Two-source disagreement (section 8). |
| `GROUP: <item_id>` | Links a dual-mode row to its COUNT anchor row (3.3). |
| `OPENING: <item_id>` | Deck opening row naming its parent deck row (3.4). |
| `QTY_BASIS: min` or `QTY_BASIS: approx` | Qty is a floor or an approximation. Absence means exact. Mirrors the scoring semantics in `takeoff_pipeline/ledger/t2_scoring_set_SP183_B1.md`. |
| `REMOVED: R<n>` | Member removed by revision export n (section 13.4). |

### 3.3 Measurement modes (P28)

Three modes. Every quantity declares one.

- `COUNT`: discrete items. Columns, joists, base plates, anchor rods, stair flights. Unit `EA`.
- `LINEAR`: lengths in decimal feet. Beams, columns as stick material, angles, rails. Unit `LF`.
- `AREA`: surfaces in square feet. Roof deck, composite deck, grating. Unit `SF`.

Weight and volume are DERIVED, never measured. No row carries a measured weight. Derived values follow section 4.

An item may appear in more than one mode. Columns carry a COUNT row from the column schedule and a LINEAR row for stick length. Height attributes from SECTIONS and ELEVATIONS go in `notes`. Each row declares its own `mode` and `primary_source`.

Dual-mode rows for the same physical items must link. The COUNT row is the anchor. Every other mode row for the same items carries `GROUP: <item_id of the COUNT row>` in `notes`. Assembly definitions are scoped per class and mode pair. COUNT drives per-piece components and labor. LINEAR drives material weight. Never both. This closes the double-count path between a column assembly and a stick-material assembly.

### 3.4 Deck openings

Deck openings (RTU, stair, skylight) are their own TAKEOFF rows. `mode` AREA, `unit` SF, class `DECK`, `designation` `OPENING`. `notes` starts with `OPENING: <item_id of the parent deck row>`. `apply_assemblies.py` deducts openings over the threshold declared in the deck assembly definition and adds framed-opening steel (angles, headers) per F4, the openings and deduction logic in the F-track table of `COWORK-HANDOFF-MASTER-2026-06-11.md`. Openings recorded anywhere else are invisible to the pipeline and prohibited.

## 4. Derived values

### 4.1 Rules

- Derived values are never typed in by hand. In the xlsx they are formula cells.
- Weight from LINEAR rows: `weight_lb = qty x lb_per_ft`. Tonnage: `tons = weight_lb / 2000`. Short tons, 2000 lb.
- Every derived value carries a `formula_ref` naming its formula and data source.
- AISC unit weights (`lb_per_ft`) come from `bridge/aisc_validator.py` only. The validator wraps the AISC v16.0 shape database, 2,299 shapes. No other source. No LLM math. No memory. This is Hard Rule 5 in `CLAUDE.md`. The validator gate in section 14 re-checks every typed `lb_per_ft` against `bridge/aisc_validator.py`.
- `lb_per_ft` is an input cell, not a derived cell. The operator fills it from `bridge/aisc_validator.py` output. The exporter never computes weights itself and never calls an LLM for them.
- Items outside the AISC database (joist series, deck) name their published source table in `formula_ref`. Supplier catalogs are internal references. Supplier names never appear in any client-facing output.

### 4.2 Derived columns on the TAKEOFF sheet

Derived columns sit to the right of the eleven mandatory columns, in this order. Column O, `formula_ref`, is the last header.

| Column | Type | Rule |
|---|---|---|
| `lb_per_ft` | number, input | LINEAR rows only. Filled from `bridge/aisc_validator.py` output. Blank on COUNT and AREA rows. Blank on non-AISC designations. |
| `weight_lb` | formula | `= qty * lb_per_ft` on LINEAR rows. Never a typed constant. |
| `tons` | formula | `= weight_lb / 2000`. Never a typed constant. |
| `formula_ref` | text | Names the source. Examples: `AISC:bridge/aisc_validator.py:W12X26`, `DERIVED:weight_lb/2000`, `SJI:K-series load table`. Required on any row with a derived value. |

## 5. Primary sources per quantity class (P30)

One primary source per quantity class, declared on every row. This kills double counting. The first five rows restate P30 exactly.

| Quantity class | Primary source | Cross-check / note |
|---|---|---|
| Column counts | COLUMN/FOOTING SCHEDULE | Framing-plan cross-check |
| Member sizes/lengths | FRAMING PLANS | Grid dimensions for lengths |
| Joist counts/types | ROOF/FLOOR FRAMING PLAN plus joist schedule | |
| Elevations/heights | SECTIONS and ELEVATIONS | Attributes only |
| Base plates/anchors | Column schedule plus typical details | |

Where P30 names two sources for one class, the schedule is the single primary for the section 8 mechanism and the plan is the cross-check. Joist counts/types: joist schedule primary, plan callouts to `secondary_source`. Member sizes/lengths stay plan-primary.

Added by this spec, same pattern:

| Quantity class | Primary source | Cross-check / note |
|---|---|---|
| Deck areas | ROOF/FLOOR FRAMING PLAN for extent | GENERAL NOTES for gauge and type |
| MISC and loose plates | The sheet where the item is scheduled or detailed, named in `primary_source` | Confidence capped at `medium` unless from a schedule |

Elevations and heights never form COUNT, LINEAR, or AREA rows of their own. They are attributes on member rows, recorded in `notes`. They size LINEAR lengths and nothing else.

Validator conformance rule, mechanical and case-insensitive: the `primary_source` string must contain the class keyword. `COL`: `SCHEDULE`. `JST`: `SCHEDULE`. `ANCH` and `PLATE`: `SCHEDULE` or `DETAIL`. `BEAM` and `DECK`: `FRAMING PLAN`. `MISC`: any non-empty value.

Any quantity measured from two sources must reconcile or become a CONFLICT (section 8).

## 6. Confidence (P24)

Every row declares one of three values.

- `high`: schedule-table hit. The quantity reads directly from a schedule.
- `medium`: plan-text callout hit. The quantity comes from counting plan callouts.
- `low`: anything ambiguous. Congested regions, partial tags, hand annotations, scanned-source text.

Low-confidence rows are flagged for human check. They never pass silently into a count, a weight, or a price. Ivan works the exception list top to bottom (P23). The QA overlay (Prompt 6) draws every census-derived `low` row at its bbox. Manual-entry `low` rows have no drawable bbox. They appear in the validator warning block (section 14) and on the overlay summary page when the takeoff xlsx is supplied to the overlay.

## 7. Manual-entry rows

Rows the census cannot produce are entered by hand. They follow the same eleven mandatory columns. `bbox` is `MANUAL`. `sheet` holds the drawing sheet the quantity was read from, or the literal `MANUAL` when no drawing sheet applies. `notes` cites the source document and date. `confidence` is set by the operator, never defaulted to `high`.

## 8. Conflicts (P26)

When `primary_source` and `secondary_source` give different quantities, the row becomes a CONFLICT row. Conflicts are findings, not errors. They are EOR errors caught before they cost us.

A CONFLICT row:

- keeps the primary-source quantity in `qty`, because P30 declares the primary source as the system of record
- sets `confidence` to `low`
- starts `notes` with the literal token `CONFLICT:` followed by both values and both sources

Example note, fictitious numbers: `CONFLICT: COLUMN/FOOTING SCHEDULE 18 EA vs S2.1 plan callouts 17 EA. RFI candidate.`

CONFLICT rows are never silently resolved. No averaging. No silent pick. The validator lists every CONFLICT row as an RFI candidate (section 14). A conflict clears only when a human resolves it: Ivan, or the EOR through an RFI. The resolution and its source are appended to `notes`, then `confidence` is re-set. If the file is already stamped, resolution edits produce a new export with a new hash (section 13.4).

## 9. BOQ sheet

Row 1 holds the headers below, written by the exporter at pipeline step 1 (13.1). Data rows are written only by `apply_assemblies.py` (Prompt 9), starting at row 2. Every row cites the TAKEOFF row that drives it. Four streams per P29: materials, labor, equipment, subcontract. `EQUIPMENT` is the plant stream in P34 and P29 wording.

| Column | Type | Rule |
|---|---|---|
| `boq_id` | text | Unique within the sheet. |
| `source_item_id` | text | The driving TAKEOFF `item_id`. Required on every row. Must exist on the TAKEOFF sheet. |
| `assembly_id` | text | The assembly definition that produced the row. |
| `stream` | enum | `MATERIAL`, `LABOR`, `EQUIPMENT`, or `SUBCONTRACT`. |
| `description` | text | What the line is. |
| `qty` | number | Output quantity after waste and rounding from the assembly definition. |
| `unit` | enum | MATERIAL and SUBCONTRACT: `EA`, `LF`, `SF`, `LB`, `TON`. LABOR: `HR`. EQUIPMENT: `HR` or `MIN`. |
| `formula_ref` | text | Required on derived quantities. Same format as section 4.2. |
| `notes` | text, optional | Free text. |

Labor is hours. Equipment is time. Subcontract rows are scope context with quantity and unit. No dollar values in any stream (P25, P29). Pricing happens downstream against `bridge/bid_rates.py`, outside this file.

Measured-class rule. An assembly never emits an order line for a class that has measured TAKEOFF rows. `ANCH` and `PLATE` are measured classes (section 5). For those classes the assembly emits a cross-check count instead. The validator compares the assembly-derived count against the measured count. A mismatch raises a CONFLICT-style warning for Ivan, section 8 semantics. Measured rows are the system of record for ordering, per P30. This closes the anchor-rod double-count path: counted from the column schedule AND generated by the column-base assembly.

## 10. BOM sheet

Materials only. What the shop orders. Row 1 holds the headers below, written by the exporter at pipeline step 1 (13.1). Data rows are written only by `apply_assemblies.py` (Prompt 9), starting at row 2.

| Column | Type | Rule |
|---|---|---|
| `bom_id` | text | Unique within the sheet. |
| `source_item_id` | text | The driving TAKEOFF `item_id`. Required on every row. Must exist on the TAKEOFF sheet. |
| `designation` | text | Material designation as ordered. |
| `description` | text | Plain description. |
| `qty` | number | Order quantity after waste and round-up rules from the assembly definition. |
| `unit` | enum | `EA`, `LF`, `SF`, `LB`, `TON`. |
| `length_lf` | number, optional | Stick material only. Decimal feet. |
| `lb_per_ft` | number, input | AISC shapes: from `bridge/aisc_validator.py` output only. Blank on non-AISC rows. |
| `weight_lb` | formula | Formula by unit case, below. Never a typed constant. |
| `tons` | formula | `= weight_lb / 2000`. Never a typed constant. |
| `formula_ref` | text | Required on any row with a derived value. Names which weight case applies. |
| `notes` | text, optional | Free text. |

Weight cases:

- `unit` LF: `weight_lb = qty * lb_per_ft`.
- `unit` EA stick material with `length_lf`: `weight_lb = qty * length_lf * lb_per_ft`.
- `unit` LB or TON: no derived weight columns. The quantity is already a weight.
- Non-AISC rows: `lb_per_ft` blank. `weight_lb` only when `formula_ref` names a published table.

Waste factors and rounding rules live inside the assembly definitions, version controlled (P29). Never ad hoc in chat. Round UP to sheet and stick increments. The measured-class rule in section 9 applies to BOM rows too.

## 11. PRICING_SCHEDULE sheet

Structure only. The takeoff pipeline writes the skeleton and stops. Row 1 holds the headers below. Data starts at row 2.

| Column | Type | Rule |
|---|---|---|
| `line_id` | text | Bid line identifier. |
| `description` | text | Line scope description. |
| `source_refs` | text | The TAKEOFF and BOQ rows the line draws from. |
| `qty` | number | Carried from the TAKEOFF measured `qty` or its derived columns (4.2). TON lines carry the derived `tons` value and cite the driving cells in `source_refs`. |
| `unit` | enum | `EA`, `LF`, `SF`, `TON`. `LB` is intentionally excluded here. |

Skeleton rows, deterministic, built at pipeline step 1 (13.1) from the TAKEOFF sheet alone:

- One line per quantity class present, in class order `COL`, `BEAM`, `JST`, `DECK`, `PLATE`, `ANCH`, `MISC`. `line_id` is `PS-<CLASS>`, plus a sequence number when a class needs more than one line.
- Steel classes `COL`, `BEAM`, `JST`: one `TON` line each. `qty` is a formula cell summing the class's derived `tons` cells on the TAKEOFF sheet.
- `PLATE` and `ANCH`: one `EA` line each. `qty` sums the measured counts.
- `DECK`: one `SF` line per deck `designation`. `qty` sums gross measured SF. `OPENING` rows are cited in `source_refs`; deductions ride downstream in BOQ and BOM.
- `MISC`: one line per `unit` present in the class.
- `source_refs` lists every contributing TAKEOFF `item_id`.

This sheet carries NO pricing columns. Not even empty ones. No rate header, no amount header, no cost header. The estimate layer copies this structure into its own workbook and adds its pricing columns there, outside this file. That copy is where the commissioned rule "populated by the estimate layer" happens. Populating it inside this file would break the zero pricing rule (section 12) and the stamp (section 13). The takeoff pipeline NEVER writes a price, a rate, or a dollar amount into this sheet.

## 12. Zero pricing rule (P25)

ZERO pricing fields anywhere in the takeoff file. All four sheets. This is the wall between the quantity layer and the pricing layer.

- No dollar amounts. No rates. No unit prices. No cost, margin, markup, or amount columns or cells.
- Mandatory token list: `$`, `rate`, `price`, `cost`, `margin`, `markup`, `amount`.
- Header cells, every sheet: case-insensitive substring match on any token is a HARD FAIL.
- Data cells, every sheet: any `$` character is a HARD FAIL. A case-insensitive whole-word match on `rate`, `price`, `cost`, `margin`, or `markup` is a HARD FAIL. Whole word means bounded by non-letters: `(?i)(?<![a-z])(rate|price|cost|margin|markup)(?![a-z])`. Words that merely contain a token pass: accurate, separate, operated, strategy.
- Implementations may extend either list. They may never shrink one.
- Labor appears as hours. Equipment appears as time. Materials appear as quantities and weights.
- Rates live in `bridge/bid_rates.py`, CEO-locked, pointed to and never copied (P10). The estimate layer applies them downstream against the takeoff's version hash.

## 13. Lifecycle, version hash, and stamp

### 13.1 Pipeline order

Stamping is the last write. Nothing writes to the file after the stamp.

1. `export_xlsx.py` builds the unstamped workbook: TAKEOFF from `census.db` plus manual-entry rows, the PRICING_SCHEDULE skeleton (section 11), and BOQ and BOM as header rows only.
2. The operator fills `lb_per_ft` input cells from `bridge/aisc_validator.py` output. Open conflicts stay open.
3. `apply_assemblies.py` populates BOQ and BOM.
4. `validate_takeoff.py` runs the section 14 table. Any HARD FAIL stops the pipeline. No stamp.
5. The stamp is written: hash, export number, metadata (13.3). The file takes its final name. Any later edit starts the pipeline again and produces a new export.

### 13.2 Hash computation

SHA-256 over the TAKEOFF sheet contents.

1. Take the TAKEOFF sheet from the header row (row 2) down to the last data row. The last data row is the last row with at least one non-empty cell in columns A through O.
2. For each row, take the cells in columns A through O. Column O is `formula_ref`, the last header.
3. Each cell contributes its stored content as text. Formula cells contribute the formula string including the leading equals sign. Integral numbers serialize without a decimal point. Non-integral numbers serialize as Python `repr`. Booleans serialize as `TRUE` or `FALSE`. Dates serialize as ISO 8601. Empty cells contribute the empty string.
4. Escape cell text before joining, in this order, each escape a two-character sequence: backslash becomes `\\`, newline becomes `\n`, pipe becomes `\|`.
5. Join cells with the pipe character. Join rows with a single newline. Encode UTF-8. SHA-256 over the bytes. Lowercase hex digest.

The metadata row (row 1) is excluded. The stamp cannot change its own hash. One shared function computes this digest. `export_xlsx.py` stamps with it and `validate_takeoff.py` re-verifies with it. Never two implementations. An Excel re-save of a stamped file is a forbidden edit: Excel may rewrite stored number forms and silently change the recomputed digest.

### 13.3 Stamp

Row 1 of the TAKEOFF sheet:

- `A1` the literal `TAKEOFF_SCHEMA_V2`
- `B1` the job identifier
- `C1` the export timestamp, UTC ISO 8601
- `D1` the full 64-character digest
- `E1` the export number, `R<n>`, monotonic per job, starting at `R1`
- `F1` the assembly-library version: the git short hash of `takeoff_pipeline/assemblies/` at apply time, or the literal `NONE` when BOQ and BOM are empty

The filename carries the export number and the first 12 hex characters: `<job>_TAKEOFF_R<n>_<hash12>.xlsx`. Two exports never share a filename, even when their TAKEOFF contents are identical.

### 13.4 Reference, immutability, revisions

- Estimates reference the takeoff by the full digest plus the export number. An estimate that cites a stamp no current file carries is stale and must be rerun.
- A stamped file is immutable. Any post-stamp edit, including conflict resolution (section 8) and revision-diff deltas (Prompt 7), produces a new export with a new export number and a new stamp. Never an in-place edit. Superseded files are kept, never overwritten.
- The hash detects TAKEOFF-sheet changes only. BOQ, BOM, and PRICING_SCHEDULE are derived artifacts. They are reproducible from the TAKEOFF rows plus the stamped assembly-library version in `F1`. They carry no independent identity.
- `item_id` values persist across revision exports. A member removed by a new issue keeps its row at `qty` 0 with the notes token `REMOVED: R<n>`. History stays traceable for census diffs and Ivan's review.

## 14. Validation rules

`validate_takeoff.py` (Prompt 5) enforces this table. Non-zero exit on any HARD FAIL. The pipeline order in 13.1 runs validation before any file is stamped.

| Sheet | Check | Result |
|---|---|---|
| TAKEOFF | Row missing `mode` | HARD FAIL, row numbers reported |
| TAKEOFF | Row missing `primary_source` | HARD FAIL, row numbers reported |
| TAKEOFF | `mode` not one of `COUNT`, `LINEAR`, `AREA` | HARD FAIL |
| TAKEOFF | `unit` does not match `mode` (EA/COUNT, LF/LINEAR, SF/AREA) | HARD FAIL |
| TAKEOFF | `confidence` not one of `high`, `medium`, `low` | HARD FAIL |
| TAKEOFF | Header row not exactly the fifteen columns of 3.2 plus 4.2, in order | HARD FAIL |
| TAKEOFF | `item_id` duplicated or not matching `<CLASS>-<NNN>` | HARD FAIL |
| TAKEOFF | `bbox` neither `[x0, y0, x1, y1]` nor `MANUAL` | HARD FAIL |
| TAKEOFF | `primary_source` fails the section 5 conformance keyword rule for the row's class | HARD FAIL |
| TAKEOFF | `lb_per_ft` populated on a non-LINEAR row | HARD FAIL |
| TAKEOFF | Row carrying a `CONFLICT:` token with `confidence` not `low` | HARD FAIL |
| TAKEOFF | `GROUP:` or `OPENING:` token citing an `item_id` absent from the sheet, an `OPENING:` parent that is not a `DECK` row, or a `GROUP:` anchor that is not a COUNT row | HARD FAIL |
| TAKEOFF, BOM | `lb_per_ft` on an AISC-resolvable designation differs from `bridge/aisc_validator.py` | HARD FAIL |
| TAKEOFF, BOM | `weight_lb` or `tons` cell holding a typed constant instead of a formula | HARD FAIL |
| TAKEOFF, BOM | Derived value present without `formula_ref` | HARD FAIL |
| BOQ, BOM | Row missing `source_item_id`, or `source_item_id` absent from the TAKEOFF sheet | HARD FAIL |
| BOQ, BOM, PRICING_SCHEDULE | Header row not exactly the columns of sections 9, 10, 11 | HARD FAIL |
| BOQ | `unit` not valid for the row's `stream` (section 9) | HARD FAIL |
| BOM, PRICING_SCHEDULE | `unit` outside that sheet's enum (sections 10, 11) | HARD FAIL |
| All | Pricing token rule of section 12 | HARD FAIL |
| All | Worksheet present that is not one of the four named sheets | HARD FAIL |
| TAKEOFF | Stamped file: recomputed digest does not match `D1` | HARD FAIL |
| PRICING_SCHEDULE | Supplier-name token (Hard Rule 4 list) in `description` or `source_refs` | WARN, flagged before stamping |
| BOQ, BOM | Assembly cross-check count disagrees with measured `ANCH` or `PLATE` rows (section 9) | WARN, CONFLICT-style, listed for Ivan |
| TAKEOFF | CONFLICT rows present | PASS with a warning block listing each as an RFI candidate |
| TAKEOFF | `low` confidence rows present | PASS with a warning block routing them to human review |

Two-source quantities that disagree are logged as CONFLICT rows for RFI. They are never silently resolved. A validator that resolves, averages, or drops a conflict is broken.

## 15. Units

All units imperial. No metric anywhere in the file.

- `EA` each, `LF` decimal feet, `SF` square feet
- `LB` pounds, `TON` short tons of 2000 lb
- `HR` hours, `MIN` minutes
- `lb/ft` pounds per foot is a column quantity (the `lb_per_ft` input), not a row unit
- Drawing dimensions read as feet and inches. They convert to decimal feet in `qty`.

## 16. What each governed prompt takes from this spec

| Prompt | Binds to |
|---|---|
| 4 (census spike) | Row fields and notes tokens (3.2), confidence semantics (6), conflict handling (8), primary-source classes (5), census.db contract and class mapping (Appendix A). |
| 5 (export and validation) | Sheet set (2), layouts (3.1, 9, 10, 11), pipeline order (13.1), hash, stamp, filename (13.2, 13.3), validation table (14). |
| 6 (QA overlays) | Confidence routing (6), CONFLICT rows (8) feed the exception list, manual-row listing on the summary page (6). |
| 7 (revision diff) | Delta output produces a new export, new export number, new hash (13.4). Removed members keep their rows per 13.4. |
| 9 (assembly library) | BOQ (9) and BOM (10) population rules, four streams, hours and time never dollars, `source_item_id` on every output row, openings (3.4), dual-mode scoping (3.3), measured-class cross-check rule (9). |

## Appendix A. census.db handoff (Prompt 4)

The census is the machine source of TAKEOFF rows. This appendix fixes the handoff so Prompts 4 and 5 cannot drift.

Minimum columns per census hit:

| Column | Rule |
|---|---|
| `designation` | Raw tag as found. |
| `item_class` | One of the 3.2 classes, mapped per the table below. |
| `sheet` | Sheet number of the hit. |
| `bbox` | `[x0, y0, x1, y1]` PDF points. |
| `raw_text` | The matched text object, unmodified. |
| `source_kind` | `SCHEDULE` or `PLAN`. |
| `primary_source` | The sheet reference string carried to the TAKEOFF row. |
| `confidence` | `high`, `medium`, or `low` per section 6. |
| `conflict_group` | Nullable. Shared key linking disagreeing schedule and plan counts. |

Class mapping, deterministic:

| Hit | Class |
|---|---|
| Any hit from a COLUMN/FOOTING SCHEDULE | `COL` |
| `K`, `LH`, `DLH`, and joist girder series tags | `JST` |
| `PL` tags | `PLATE` |
| Anchor rod callouts | `ANCH` |
| Deck callouts and deck extent | `DECK` |
| `W`, `HSS`, `C`, `MC`, `L`, `WT`, pipe from framing plans | `BEAM` |
| Anything unresolved | `MISC` |

Aggregation into TAKEOFF rows: one row per designation, mode, and primary_source. `SCHEDULE` hits carry the schedule quantity. `PLAN` hits carry the hit count.

When both exist for one quantity, primacy follows the section 5 class table. Count classes (`COL`, `JST`, `ANCH`, `PLATE`): the schedule is primary, plan callouts are the cross-check. Member sizes and lengths (`BEAM`): the framing plan is primary per P30, a schedule entry is the cross-check. The cross-check's sheet reference goes to `secondary_source`. Both counts are written into `notes` only when they disagree, per section 8.

Anchor for aggregated rows: `sheet` and `bbox` come from the first contributing hit in reading order. Reading order: lowest sheet number first, then top to bottom, then left to right on the page. The full hit list stays in `census.db`. The overlay (Prompt 6) draws every individual hit from `census.db`; the TAKEOFF row's bbox is a review anchor only.

End of specification.
