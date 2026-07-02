---
name: spec-boq
version: 1.0.0
inputs:
  - requirement-register.json
  - library/production-rates.yaml
outputs:
  - estimate.json
mcp_connectors:
  - filesystem
voice: owner
schema: data/schemas/estimate-line.schema.json
---

# spec-boq

## Purpose

Generate a preliminary Bill of Quantities and priced estimate from
text-extractable spec data. Items requiring drawing takeoff are emitted
with `qty=TBD` and a note pointing to LIFT or the human estimator.

## Inputs

- `requirement-register.json`
- `library/production-rates.yaml` (CEO-locked Q2 2026 rates)

## Procedure (Sequential Thinking)

1. Iterate requirement-register rows with category in
   {Direct, ContingencyPrelim}.
2. For each row with `expected_qty` and `expected_unit`:
   a. Look up matching rate in production-rates.yaml by discipline +
      item_class + unit.
   b. Build the estimate line:
      - `qty` = expected_qty
      - `unit` = expected_unit
      - `unit_rate` = computed from hr_per_unit * labor_rate_usd_per_hr
        + material_basis, then * overhead_mult (1.15x default).
      - `extended` = qty * unit_rate.
      - `rate_basis` = plain text. Example:
        "11 hr/ton x $145/hr x 1.15 + material baseline"
      - `requirement_refs` = [source req_id]
3. For rows without `expected_qty`:
   - Emit placeholder line: `qty="TBD"`, `unit_rate=null`,
     `notes="Verify against drawing takeoff (LIFT or human)"`.
4. Apply Your Company hard rules:
   - Structural steel tonnage uses 11 hr/ton blended fab baseline.
   - $145/hr shop, $175/hr engineering, both folded into the rate via
     production-rates.yaml. Engineering never gets its own line.
   - Overhead multiplier 1.15x already in unit_rate. Mark
     `markup_applied=true`.
   - Deck supply and install always included.
5. Assign `line_id` as `LINE-NNNN` zero-padded.
6. Write `estimate.json`.

## Realistic accuracy

- Spec-tabulated items: ~85-90%.
- Items requiring graphical interpretation: not handled by this skill.
  They appear as TBD placeholders for the estimator.

## Hard rules respected

- AISC weights from `bridge/aisc_validator.py` (v16.0) only. Never trust
  LLM math.
- BID_RATES from `bridge/bid_rates.py` are CEO-locked.
- Engineering folded into fab/erection.
- Deck supply and install in scope.
- No supplier names in any output line.
