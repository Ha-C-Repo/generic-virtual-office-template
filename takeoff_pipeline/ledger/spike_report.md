# T2 Census Spike Report - SP183_B1 - 2026-06-14

Test set: `C:\Users\YourUser\.claude\projects\Cowork Virtual Office\Bids To Estimate\06 South Park 183\drawings\Extracted pages from 2026-04-22 Issue For Pricing - Building 1.pdf`
Scoring set: `t2_scoring_set_SP183_B1.csv` (semantics in the companion md)

## Headline numbers, as computed, not massaged

- Designation recall (primary metric, presence-scorable rows): **100 percent** against the 95 percent Section 07 target. MEETS target.
- Recall including SF value rows: 100 percent
- JST-class precision (only class with exhaustive ground truth): 100 percent (census found: 28K7, 30K7, 30K8, 30K9, 32LH07, 36G8N11.5K, 54G8N12.1K, 54G8N12.5K)
- Census hits stored: 369 (12 schedule, 357 plan) in `census.db`
- Conflicts logged, never silently resolved: 0
- Scanned sheets routed out (4x rasterization owns them): none

## Scorecard

Every YES carries its evidence basis. A YES without readable evidence would be a number nobody can verify.

| designation | scoring | found | evidence | count check |
|---|---|---|---|---|
| COLUMNS | count_approx | YES | column TYPES present from a base-plate or column schedule (HSS 10x10, HSS 12x12, HSS 6x6, HSS 8x8); member count not on a schedule, count from the foundation plan, Ivan verify | FAIL: no countable census evidence |
| ANCHOR RODS 3/4 IN | count_min (CONFLICT) | YES | 5 anchor rod text hits on S1.00, S4.00, S4.03 | PRESENCE_ONLY: provenance CONFLICT; presence only until Ivan resolves |
| 28K7 | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 30K7 | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 30K8 | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 30K9 | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 32LH07 | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 36G8N11.5K | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 54G8N12.1K | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| 54G8N12.5K | presence | YES | JST hits on S3.00, confidence medium | NOT_SCORED: presence row, no count semantics |
| CAGED LADDER | presence | YES | ladder text on S5.02 (no CAGE text anywhere; cage attribute UNVERIFIED, ladder presence only) | NOT_SCORED: presence row, no count semantics |
| TILT WALL EMBED PLATES | presence | YES | 25 embed text hits on S2.00, S4.00, S4.01, S4.02, S4.03, S5.00, S5.03, S6.00 | NOT_SCORED: presence row, no count semantics |
| BUILDING SF | value | YES | grid-geometry footprint 413 x 150 ft = 61950 SF on S2.00 (Engine B), confidence medium | PASS: figure 61950 vs verified 61621 (0.5 pct off, tol 2) |
| DECK SF | value_approx | YES | grid-geometry footprint 413 x 150 ft = 61950 SF on S3.00 (Engine B), confidence medium | PASS: figure 61950 vs verified 61621 (0.5 pct off, tol 15) |

## Misses

None. Every scorable designation was found.

## Scale check (T3)

- PAGE-0: NO_CHECK (no plan-magnitude scale string on sheet)
- S1.00: NO_CHECK (no measurable grid bubble row plus overall dimension)
- S1.01: NO_CHECK (no plan-magnitude scale string on sheet)
- S2.00: OK. Bubbles span 1486.3 pt, measured 412.9 ft vs printed 413 ft (0.03 pct off)
- S3.00: OK. Bubbles span 1486.3 pt, measured 412.9 ft vs printed 413 ft (0.03 pct off)
- S3.01: NO_CHECK (no measurable grid bubble row plus overall dimension)
- S4.00: NO_CHECK (no plan-magnitude scale string on sheet)
- S4.01: NO_CHECK (no measurable grid bubble row plus overall dimension)
- S4.02: NO_CHECK (no plan-magnitude scale string on sheet)
- S4.03: NO_CHECK (no plan-magnitude scale string on sheet)
- S4.04: NO_CHECK (no plan-magnitude scale string on sheet)
- S5.00: NO_CHECK (no plan-magnitude scale string on sheet)
- S5.01: NO_CHECK (no plan-magnitude scale string on sheet)
- S5.02: NO_CHECK (no plan-magnitude scale string on sheet)
- S5.03: NO_CHECK (no plan-magnitude scale string on sheet)
- S6.00: NO_CHECK (no plan-magnitude scale string on sheet)
- S6.01: NO_CHECK (no plan-magnitude scale string on sheet)

## Attribute rows (score the router and notes extraction; excluded from census recall)

- FINISH=PAINT: PASS. PAINT present in sheet text
- STAGE=IFC: REVIEW. claimed IFC, but the title block stage strings are ['ISSUE FOR PERMIT', 'ISSUE FOR PRICING']; confirm with Ivan
- CAMBER=NONE: REVIEW. camber text present: 6. BEAMS WITHOUT SPECIFIC CAMBER SHALL BE ORIENTED SUCH THAT
- CONNECTIONS=SIMPLE: NOT_SCORED. needs human judgment; not scored by the spike

## Conflicts (P26)

None logged on this run. The scoring set's anchor-rod CONFLICT (Ivan 64 EA floor vs takeoff 160 EA) lives in the scoring csv and scores as presence only until Ivan resolves it.

## Honest caveats

- The text census counts callout TEXT OBJECTS. A member tagged once with leader fan-out, or tagged on two sheets, is not a member count. Count semantics here are evidence for Ivan, not a takeoff quantity.
- COLUMNS: the base plate schedule is read and its column SIZES classified COL (A1), but it carries no quantity column, so census produces no column member count. The count comes from the foundation plan and Ivan verifies it. The scorecard shows the types found, never a fabricated total.
- Base plates: the same schedule lists plate SIZES, not a count. Census emits no base-plate count from it; the count is derived one per verified column downstream (P29), so it is an honest null pending the column count, never a per-type total. Plan callout plates are counted normally.
- Building and deck SF come from grid geometry (Engine B): the two largest orthogonal overall dimensions define a bounding-box footprint. v1 is bounding-box only and flags a non-rectangular plan for verification; it never reconstructs a polygon, and the area is Ivan's to confirm, never a price.
- Full precision needs a complete verified census. The JST class is scored because its inventory is text-verified and exhaustive; other classes are listed for eyeball review in census.db.

Generated 2026-06-15T00:27:38.259633+00:00 by takeoff_pipeline/score_spike.py. Counts only, no AISC weight math (schema section 4), zero P25 tokens.