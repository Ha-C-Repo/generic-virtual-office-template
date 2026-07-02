# T2 Census Scoring Set - South Park 183 Building 1
**Built:** 2026-06-11 by Cowork, from the Owner's directive to assemble the set from Outlook and PC data.
**Scoring file:** `t2_scoring_set_SP183_B1.csv`
**Test drawing set:** `Bids To Estimate/06 South Park 183/drawings/Extracted pages from 2026-04-22 Issue For Pricing - Building 1.pdf`

## Why SP183 B1
It is the only completed bid with a written, item-by-item verification from Ivan on file. Fruita has a parallel Ivan review (email 2026-05-23) and serves as the second set when needed.

## Sources
1. Ivan Martinez email, 2026-05-25 10:15 UTC, RE: Dollar General Store #30623 REBID thread. Item-by-item verification of SP183 B1: building SF approx 61,621 gross, approx 16 columns, 4 anchor rods per column minimum at 3/4 in dia UNO, deck SF approx equal to building SF, joists 28K7 / 30K8 / 32LH07 class with 54G8N12.5K joist girders, mostly simple connections, paint UNO, complete 100 percent IFC set, no camber, caged ladder in scope, tilt wall embed plates in scope.
2. `_handoff/bid-intel/PRJ-2026-KEAT-001/takeoff.xlsx`, Joist Inventory sheet, B1 row: 28K7, 30K7, 30K8, 30K9, 32LH07, 36G8N11.5K, 54G8N12.1K, 54G8N12.5K (text-verified tags).
3. Ivan calibration ranges: `data/calibration/ivan_confirmed_2026Q2.json`.

## Known conflict (logged, not resolved)
Anchor rods: Ivan's 2026-05-25 floor is 64 EA (16 columns x 4 minimum). The 2026-06 KEAT takeoff carries B1 anchors at 160 EA. Per P26 this is a CONFLICT row in the csv. Ask Ivan which number is the verified truth before treating either as ground truth for count scoring. Designation-presence scoring is unaffected.

## How the spike scores against this set
Primary metric: designation recall. The census must find every presence row (8 joist tags, columns, anchors, caged ladder, embeds) on the B1 sheets. Secondary: count accuracy on rows with qty_verified, respecting count_min and count_approx semantics. Attribute rows (paint, IFC, no camber, simple connections) score the T1 router and general-notes extraction, not the census. Zero pricing anywhere in this set per P25.
