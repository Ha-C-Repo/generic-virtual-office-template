---
name: requirement-register
version: 1.0.0
inputs:
  - tender-index.json
outputs:
  - requirement-register.json
mcp_connectors:
  - filesystem
voice: owner
schema: data/schemas/requirement-register.schema.json
---

# requirement-register

## Purpose

The heart of the system. Build the four-bucket scope checklist from the
tender package. Every requirement becomes one row with a verbatim quote
and a page-level source citation. Default status is Gap. Reconciliation
later marks rows Matched, Orphan, ExcludedByDesign, or CategoryMismatch.

## Inputs

`tender-index.json` from the tender-ingest skill.

## Procedure (Sequential Thinking, page by page)

1. Load `tender-index.json`. Iterate documents in order: scope → specs →
   head_contract → other. Skip drawings (handled by drawing skills).
2. For each page, extract every distinct requirement as a separate
   sentence. Quote verbatim. Capture page number and section/clause if
   visible.
3. Classify each requirement into one of four buckets:
   - `Direct` if Your Company self-performs (structural steel fab, deck
     supply and install, stud welding, galvanizing, primer paint, anchor
     bolts, miscellaneous metals).
   - `Subcontractor` if the requirement is outside Your Company's scope but
     listed in the tender (concrete, MEP, roofing membrane, glazing).
   - `ContingencyPrelim` if it is a time-based or indirect cost (project
     management, site supervision, insurances, freight, crane standby).
   - `Excluded` if Your Company will not bid on it. Tag the row so the
     Exclusions list pulls it forward.
4. Tag discipline. Default to Structural for ambiguous structural items.
5. Where the spec gives a quantity, capture `expected_qty` and
   `expected_unit`. Examples: "approx 145 LF of pipe railing",
   "120 stud connectors per bay", "deck area 12,400 SF".
6. Apply hard rules:
   - Deck supply AND deck install ALWAYS classified Direct, never Excluded.
   - Engineering NEVER appears as a separate row in Direct. If the spec
     calls out engineering, fold the note into the related fab/erection
     requirement.
7. Assign `req_id` as `REQ-NNNN` zero-padded sequential, or ULID.
8. Set `confidence` 0.0-1.0. Anything <0.7 marked for human review.
9. Write `requirement-register.json` conforming to schema.

## Realistic accuracy

- Tabulated/clear specs: ~95% recall.
- Prose-only specs: ~70-80% recall.
- Verbatim quotes always preserved (no paraphrasing).
- Drawing-graphical requirements (counting beams from plan view): ~60-70%.
  Flag for LIFT or human verification.

## Hard rules respected

- Deck supply AND install ALWAYS in Inclusions, never Exclusions.
- Engineering folded into fab/erection rows. Never its own row.
- No supplier names surfaced.
- Verbatim quoting only. No paraphrasing of contract language.
