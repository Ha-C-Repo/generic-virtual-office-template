---
name: reconciliation
version: 1.0.0
inputs:
  - requirement-register.json
  - estimate.json
  - library/production-rates.yaml
outputs:
  - recon-report.json
  - artifact: artifacts/templates/reconciliation-dashboard.html.tpl
mcp_connectors:
  - filesystem
voice: owner
---

# reconciliation

## Purpose

The engine. Deterministic diff between the Requirement Register and the
priced Estimate. Flags gaps, orphans, category mismatches, rate
anomalies, arithmetic errors, unit mismatches, and excluded-but-priced
items. Output is a JSON report and a Live Artifact dashboard.

This skill produces a verdict, a critical-issue count, and a prioritized
issue list. Structure mirrors Operum's Submission Analysis output so
benchmarks are directly comparable.

## Inputs

- `requirement-register.json`
- `estimate.json`
- `library/production-rates.yaml`

## Procedure (Sequential Thinking, deterministic)

1. Build two hash maps:
   - `req_to_line`: req_id -> priced_line_ref
   - `line_to_reqs`: line_id -> list of req_ids (from requirement_refs)

2. For each requirement-register row:
   - If category in {Direct, Subcontractor, ContingencyPrelim} AND
     priced_line_ref is null: set status=Gap, write issue.
   - If category=Excluded AND priced_line_ref is not null: write issue
     "Excluded but priced" (severity=High).

3. For each estimate line:
   - If requirement_refs is empty: status=Orphan, write issue.
   - Category-alignment check: if requirement.category != line.category
     for any matched pair, write issue "CategoryMismatch".
   - Arithmetic check: if abs(qty * unit_rate - extended) > 0.01, write
     issue "ArithmeticError" (severity=Critical).
   - Unit sanity: if discipline=Structural and unit not in {TON, EA, LF},
     write issue "UnitMismatch" (severity=High).
   - Rate-band check: lookup matching rate row in production-rates.yaml
     by discipline + item_class + unit. Compute band [P25*0.7, P75*1.4].
     - If unit_rate < P25*0.7: issue "RateAnomalyLow" (severity=Critical).
     - If unit_rate > P75*1.4: issue "RateAnomalyHigh" (severity=High).

4. Compute verdict:
   - 0 Critical issues: verdict = "READY_TO_SUBMIT"
   - 1-3 Critical: verdict = "REVIEW_AND_ADJUST"
   - 4+ Critical: verdict = "DO_NOT_SUBMIT"
   - Always: critical_count = count(severity=Critical)

5. Sort issues by severity then by source page. Each issue carries:
   - priority (Critical | High | Medium | Low)
   - title
   - req_id (or line_id) reference
   - source_doc + source_page
   - section/category
   - recommended_action (one short imperative sentence)

6. Write `recon-report.json`.

7. Render `artifacts/templates/reconciliation-dashboard.html.tpl` with
   the report data. Three panels: Gaps, Orphans, Rate Anomalies.

## Output structure

```
{
  "verdict": "REVIEW_AND_ADJUST",
  "critical_count": 3,
  "high_count": 5,
  "medium_count": 12,
  "low_count": 8,
  "issues": [
    {
      "priority": "Critical",
      "title": "Stud connectors required by spec, no priced line",
      "req_id": "REQ-0123",
      "source_doc": "Scope of Works.pdf",
      "source_page": 8,
      "section": "Structural",
      "recommended_action": "Add stud welding line. 120 EA at $[ANCHOR RATE]/EA."
    }
  ]
}
```

## Ivan-rules (added 2026-05-23 from his verification feedback)

Run after the deterministic checks above. Each catches an input error the
pricing engine misses on its own.

A. **Anchor rod count.** Never accept anchor_rod_count = 6 (or any
   suspiciously small fixed default) for projects with > 4 columns.
   Expected = sum(bolts_per_column) where default bolts_per_column = 4
   (simple base), 6-8 (braced/moment-frame base). Flag
   `Critical - ANCHOR_COUNT_UNREALISTIC` when the priced line falls below
   the floor of 4 x column_count.

B. **Joist gate.** If framing plan + schedule show only W-shapes and
   HSS with no joist callout, joist line MUST be zero. Any non-zero
   joist qty in that case is `Critical - JOIST_NO_SOURCE`.

C. **Anchor rod diameter is per-project.** The 1" x 20" F1554 Gr.55
   default is a placeholder. Real size comes from the anchor schedule
   (e.g. detail 10/S5.0 on IHC Fruita = 3/4"). Spec-boq skill extracts
   from anchor schedule; reconciliation flags `High - ANCHOR_DIAM_DEFAULT`
   if the line still shows the default and the anchor schedule was read.

D. **Connection allowance tier.** Default 10% for mixed-frame jobs. Bump
   to 15% for moment-frame-heavy. Drop to 8% for all-simple-shear. Flag
   `High - CONNECTION_TIER_MISMATCH` when the engine knows the project
   mix and the wrong tier is applied.

E. **Building SF source.** Must come from the architectural cover sheet
   or floor-plan SF table. lbs/SF gate logic depends on it. Flag
   `High - BUILDING_SF_DEFAULTED` if the spec-boq skill used a guess.

F. **Takeoff tool of record.** Read `bids.boq_origin` from
   bid_pipeline.db. Acceptable values are `planswift` (best), `bluebeam`,
   `manual_excel`, or `synthetic` (worst). Flag levels:
   - `boq_origin = synthetic` -> `Critical - BOQ_SYNTHETIC` (no Ivan-verified takeoff)
   - `boq_origin = bluebeam` -> `High - BOQ_NOT_PLANSWIFT` (lower fidelity than canonical)
   - `boq_origin = manual_excel` -> `Medium - BOQ_MANUAL` (hand-keyed, no PlanSwift coverage)
   - `boq_origin = planswift` -> no flag (clean)
   - `boq_origin = ''` (empty) -> `Critical - BOQ_UNRESOLVED` (resolver never ran on this bid)

   The resolver lives in `bridge/boq_resolver.py`. Adapters self-register
   from `bridge/planswift_import.py` and `bridge/bluebeam_boq_adapter.py`.
   To resolve and record onto a bid row, call
   `bridge.bid_pipeline.resolve_and_record_boq(bid_id, bid_folder=...)`.

Reference: `.specify/specs/bid-estimating/ivan-feedback-2026-05-23.md`.

## Honest limits

- Engine is deterministic. It flags. It does not correct.
- Rate-band check requires populated production-rates.yaml with p25,
  p75, floor, ceiling. Until 20+ closed projects loaded, bands are
  loose (P10/P90) to avoid false positives.
- Engine cannot catch what the Requirement Register missed. If a
  requirement was never extracted from the tender, the engine has no
  way to flag the gap. Drawing-graphical requirements remain the
  primary blind spot.
- Ivan-rules A-F still depend on the verification gate. They reduce the
  blast radius of bad synthetic inputs but do not replace Ivan's review.

## Hard rules respected

- All flagged issues link back to verbatim source quotes.
- No supplier names in any output.
- Estimator reviews every flag before bid submission.
