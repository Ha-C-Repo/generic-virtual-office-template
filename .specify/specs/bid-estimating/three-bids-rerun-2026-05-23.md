# Reconciliation Rerun - 3 Bids Sent to Ivan

Process: bid-estimating v1.0.0 + Ivan-rules A-F + BOQ resolver
Run date: 2026-05-23
Source drawings: C:\Users\YourUser\Downloads (granted to Cowork this session)

## Bids run

1. **PRJ-2026-IHC-010** IHC Fruita Clinic - 33.14 T, $241,040, paint, GC Stout-Bountiful
2. **PRJ-2026-SOU-011** South Park 183 Bldg 1 - 60.50 T, $449,565, paint, GC Burton Construction-Austin
3. **PRJ-2026-DOL-011** Dolores PEMB - 2.31 T, $49,189, galvanized, GC Stout-Bountiful

## Summary

| Bid | Verdict | Critical | High | Medium | Low | Ivan verified |
|---|---|---|---|---|---|---|
| IHC Fruita Clinic | REVIEW_AND_ADJUST | 3 | 3 | 0 | 0 | Yes (full Q&A) |
| South Park 183 Bldg 1 | REVIEW_AND_ADJUST | 2 | 2 | 1 | 0 | Pending |
| Dolores PEMB | REVIEW_AND_ADJUST | 2 | 1 | 0 | 1 | Pending |

BOQ origin: **synthetic** on all three. No PlanSwift export was in any bid folder when the resolver ran. Critical BOQ_SYNTHETIC flag applies to all three until Ivan provides a real takeoff.

---

## PRJ-2026-IHC-010 IHC Fruita Clinic

**Verdict: REVIEW_AND_ADJUST** Critical 3, High 3, Medium 0, Low 0.

### Critical issues

1. **BOQ_SYNTHETIC.** No PlanSwift export found. Pipeline used pattern-derived placeholders. Do not ship until Ivan provides PlanSwift takeoff. Ivan-rule F.

2. **ANCHOR_COUNT_UNREALISTIC.** Estimate priced 6 anchors. Ivan verified actual is ~148 (37 columns x 4 rods minimum, with up to 8 each on braced-frame bases). Cost gap at $[ANCHOR RATE]/EA: ~$10,650 underpriced. Ivan-rule A.

3. **JOIST_NO_SOURCE.** Joists priced at 5.50 T but drawings show only Wide Flange and HSS framing - zero joist callouts. Ivan confirmed: "I do not see joists indicated on the drawings. I am not sure where the 5.50 quantity of joists in the estimate originated from." Drop the joist line to zero. Ivan-rule B.

### High issues

4. **ANCHOR_DIAM_DEFAULT.** Proposal template uses 1" x 20" F1554 default. Drawing detail 10/S5.0 shows 3/4" diameter anchor rods with PL 1/2" x 2" x 2" washer plates. Update anchor schedule reference. Ivan-rule C.

5. **CONNECTION_TIER_MISMATCH.** Project has 4-6 braced frames with moment connections per Ivan. 10% connection allowance applied; should be 15%. Ivan-rule D.

6. **BUILDING_SF_DEFAULTED.** Building SF priced at 15,000; drawing actual is 14,251 (5.3% off). lbs/SF gate depends on this value. Ivan-rule E.

### Drawing sweep confirmation

- W-shape mentions: 130
- HSS mentions: 103
- Joist callouts: 0 (confirms Ivan)
- Anchor keyword mentions: 11
- Camber mentions: 0 (confirms Ivan)
- PEMB hints: none

---

## PRJ-2026-SOU-011 South Park 183 Bldg 1

**Verdict: REVIEW_AND_ADJUST** Critical 2, High 2, Medium 1, Low 0.

Ivan verification: pending. The findings below come from the drawing-text sweep plus Joseph's stated assumptions.

### Critical issues

1. **BOQ_SYNTHETIC.** No PlanSwift export found. Do not ship until Ivan provides PlanSwift takeoff.

2. **ANCHOR_COUNT_UNREALISTIC.** Estimate priced 6 anchors but drawings contain 8 distinct anchor mentions. Drawing shows 3/4" and 5/8" diameter rods. Compute as sum(bolts_per_col); 4 min for simple base, up to 8 for braced frame. Ivan-rule A.

### High issues

3. **ANCHOR_DIAM_DEFAULT.** Proposal template uses 1" F1554 default. Drawings show 3/4" and 5/8". Per Ivan-rule C, update anchor schedule reference.

4. **DRAWING_STAGE_MISMATCH.** Priced as IFC but drawing set says "Issue for Pricing". Stage adder needs to bump (per Joseph's Q8). Pricing tier should account for less-than-IFC information.

### Medium issues

5. **CAMBER_PRESENT.** Drawings mention camber 2 times. Estimate did not carry a camber line. Confirm long-span beams (per Joseph's Q9). Camber adds shop time and ought to surface in the estimate.

### Drawing sweep confirmation

- Joist callouts: 140 (samples: 30K7, 30K8, 28K7, 30K9, joist girder) - heavy joist project, K-series
- HSS mentions: 20
- Anchor diameter hits: 3/4" and 5/8"
- Drawing stage: "Issue for Pricing" (NOT IFC)
- Camber: 2 mentions

---

## PRJ-2026-DOL-011 Dolores PEMB

**Verdict: REVIEW_AND_ADJUST** Critical 2, High 1, Medium 0, Low 1.

Ivan verification: pending.

### Critical issues

1. **BOQ_SYNTHETIC.** No PlanSwift export found. Do not ship until Ivan provides PlanSwift takeoff.

2. **ANCHOR_COUNT_UNREALISTIC.** Estimate priced 6 anchors but drawings contain 6 anchor mentions. The flag fires because Rule A demands a computed count (sum of bolts_per_col), not a fixed 6. For a PEMB foundation anchor system, count needs to come from the anchor schedule sheet.

### High issues

3. **DRAWING_STAGE_MISMATCH.** Priced as IFC but drawing set says "Issued for Permit". Permit drawings frequently change before IFC; price tier should reflect that risk (per Joseph's Q8).

### Low issues

4. **PEMB_SCOPE_CONFIRMED.** Drawings confirm PEMB framing. Bid scoped as misc steel only (matches `pemb_misc_only` benchmark). Per Joseph's Q11: confirmed primary frames are NOT being pulled in by accident.

### Drawing sweep confirmation

- PEMB hints: pre-engineered, metal building, PEMB (all present)
- W-shape mentions: 0
- HSS mentions: 0
- Joist callouts: 0
- Anchor diameter hits: 1"
- Building SF candidates: 1,212 / 8,920 / 10,640 (Joseph used 9,000 - aligns with 8,920)
- Finish: galvanized + paint mentioned (estimate priced galvanized - correct for PEMB exposure)

---

## What this rerun proves

The new process catches the exact issues Ivan flagged in his email, plus more that he hasn't gotten to yet:

- The IHC anchor count error (6 vs ~148) - **caught by Ivan-rule A** with the dollar impact computed.
- The IHC joist line that has no source - **caught by Ivan-rule B** with verbatim Ivan citation.
- The IHC anchor diameter mismatch (1" default vs 3/4" actual) - **caught by Ivan-rule C**.
- The IHC moment-frame connection tier - **caught by Ivan-rule D**.
- The IHC building SF (15,000 vs 14,251) - **caught by Ivan-rule E**.
- The synthetic BOQ on all three - **caught by Ivan-rule F** with Critical severity.
- Drawing stage mismatches on SP183 and Dolores (priced IFC, actual Pricing/Permit) - caught by stage adder logic.
- Camber on SP183 long-span beams - flagged before Ivan gets to it.

## Recommended next actions

1. Wait for Ivan's PlanSwift exports for IHC Fruita Clinic, South Park 183 Bldg 1, Dolores PEMB.
2. Drop the exports into `<bid_folder>/planswift/<filename>.csv|xlsx`.
3. Call `resolve_and_record_boq(bid_id, bid_folder=<folder>)` per bid.
4. Re-run reconciliation. BOQ_SYNTHETIC clears once `boq_origin` flips to `planswift`.
5. For IHC specifically: drop joists to zero, bump anchor count to ~148, switch diameter to 3/4", bump connection allowance to 15%, correct SF to 14,251. Re-price.
6. For SP183: bump stage adder for "Issue for Pricing", add camber line, fix anchor diameter and count.
7. For Dolores PEMB: bump stage adder for "Issued for Permit", fix anchor count from anchor schedule.

Source artifact: `three-bids-rerun-2026-05-23.json` (machine-readable, same folder).
