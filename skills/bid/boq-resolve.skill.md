---
name: boq-resolve
version: 1.0.0
inputs:
  - bid_id (int)
  - bid_folder (path, optional)
  - explicit_path (path, optional)
outputs:
  - resolution result (chosen adapter, boq_origin, row_count, source_file)
  - persisted: bids.boq_origin, bids.boq_source_file, bids.boq_resolved_at
mcp_connectors:
  - filesystem
voice: owner
---

# boq-resolve

## Purpose

Pick the best available Bill-of-Quantities source for a bid. Do not
assume a single takeoff tool. The pipeline accepts multiple sources;
this skill walks them in fidelity order and picks the best one present.

The skill never replaces an existing pipeline. It runs ahead of the
spec-boq skill and tells spec-boq which source to read from.

## Fidelity ranks

1. **PlanSwift** (highest). Ivan-run takeoff. CSV or XLSX export. AISC
   weights still verified by `bridge/aisc_validator.py`.
2. **Bluebeam markup**. Measured but not weight-verified. Use when
   PlanSwift not yet provided.
3. **Manual Excel**. Hand-keyed estimator workbook.
4. **Synthetic**. Pattern-derived placeholder. Always flagged by
   reconciliation Rule F.

## Procedure

1. Build a `BoqContext` with bid_id, bid_name, bid_folder, and
   optionally explicit_path (operator-supplied file).
2. Call `bridge.boq_resolver.resolve_boq(ctx)`. The resolver walks the
   registry in fidelity order. First adapter whose `probe()` returns
   True wins.
3. Persist the result onto the bid row:
   - `boq_origin` = "planswift" | "bluebeam" | "manual_excel" | "synthetic"
   - `boq_source_file` = absolute path of file used (or empty)
   - `boq_resolved_at` = ISO timestamp
4. Surface the chosen adapter, the skipped/lower-fidelity adapters, and
   the row count to the operator before spec-boq runs.

## Where each adapter looks

**PlanSwift** (`bridge/planswift_import.py`):
  - `<bid_folder>/planswift/*.csv|.xlsx`
  - `<bid_folder>/*planswift*.csv|.xlsx`
  - `<bid_folder>/boq/*.csv|.xlsx` with PlanSwift-shaped headers
  - `explicit_path` if operator points at a file directly

**Bluebeam** (`bridge/bluebeam_boq_adapter.py`):
  - `<bid_folder>/bluebeam/*.csv`
  - `<bid_folder>/*bluebeam*.csv`
  - `<bid_folder>/markups/*.csv` (Bluebeam Markups List export)

**Synthetic**: always available, last resort.

## Hard rules respected

- Adapters scrub supplier substrings (Vulcraft, Canam, Nucor, Ayamsa)
  before storing descriptions. Tier 1.
- AISC weights NEVER come from this skill. The validator at
  `bridge/aisc_validator.py` v16.0 owns the weight column. This skill
  only sources quantities and descriptions.
- `boq_origin="synthetic"` is acceptable but ALWAYS triggers Ivan-rule
  F in reconciliation: bids cannot ship from a synthetic BOQ.

## Operator workflow

When Ivan emails a PlanSwift export for a bid:

1. Save the file into `<bid_folder>/planswift/`. Filename does not
   matter; the adapter probes by content.
2. Run `resolve_and_record_boq(bid_id, bid_folder=<folder>)`.
3. Confirm `boq_origin` came back as `"planswift"`. If not, the file
   did not have PlanSwift-shaped headers - check that
   description, qty, and unit columns are present.
4. Re-run reconciliation. Rule F should now show GREEN.

## Outputs

Returns:

```
{
  "success": true,
  "bid_id": 42,
  "chosen": "planswift",
  "boq_origin": "planswift",
  "source_file": "C:/.../planswift/NSL-001-takeoff.csv",
  "row_count": 47,
  "fidelity_rank": 1,
  "probed": ["planswift"],
  "skipped": [],
  "notes": []
}
```

Or on synthetic fallback:

```
{
  "success": true,
  "bid_id": 42,
  "chosen": "synthetic",
  "boq_origin": "synthetic",
  "source_file": "",
  "row_count": 0,
  "fidelity_rank": 4,
  "probed": ["planswift", "bluebeam", "synthetic"],
  "skipped": ["planswift", "bluebeam"],
  "notes": []
}
```

## Honest limits

- Adapters do not interpret drawings. PlanSwift and Bluebeam exports
  represent work Ivan or an estimator did upstream. If the upstream
  takeoff is wrong, this skill ships the wrong numbers faithfully.
- The synthetic adapter returns zero rows. It only exists so the
  pipeline always has a callable result. Spec-boq's pattern-derived
  estimator runs separately and uses the same `boq_origin="synthetic"`
  tag when no real source was found.
