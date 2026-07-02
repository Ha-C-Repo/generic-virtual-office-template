# Ivan's Feedback - Previous-Session Bids (2026-05-23)

Source: Ivan L. Martinez (Director of Engineering Dept), email to Joseph
W. Hasse, 2026-05-23 16:04 UTC. CC Owner, Amber. Subject line was
"RE: Dollar General Store #30623 REBID" but body discusses the three-bid
verification thread Joseph kicked off on 2026-05-22.

## The actual "last 3" bids in scope

1. **PRJ-2026-IHC-010** IHC Fruita Clinic - 33.14 T, $241,040, paint, GC Stout-Bountiful
2. **PRJ-2026-SOU-011** South Park 183 Bldg 1 - 60.50 T, $449,565, paint, GC Burton Construction-Austin
3. **PRJ-2026-DOL-011** Dolores PEMB - 2.31 T, $49,189, galvanized (PEMB exposure), GC Stout-Bountiful

These were run through the v10 Cowork bid pipeline. Auto-review verdict
was READY on all three. GP held at 27-28% on structural, 23% on the PEMB.
Pricing math, AISC weights, SJI weights, plate density formula, and the
five sanity gates all held.

## Joseph's 12 questions to Ivan

1. BOQ source (Bluebeam vs. PlanSwift assumption)
2. Building SF (Joseph used 15,000 / 30,000 / 9,000)
3. Connection allowance (default 10% applied flat)
4. Anchor rod count (assumed 6 each)
5. Deck SF (assumed = building SF)
6. Joist series and depth (SP183-B1 used K-series defaults)
7. Finish selection (IHC + SP183 paint, Dolores galv)
8. Drawing stage (all priced as IFC)
9. Camber (none flagged)
10. Retention (5% x 90 days)
11. Dolores PEMB scope (misc steel only, pemb_misc_only benchmark)
12. Per-sheet rollup (came back as one sheet, needs real BOQ with sheet column)

## Ivan's answers - IHC Fruita Clinic only (2026-05-23 16:04 UTC)

1. **BOQ Source.** Your Company uses **PlanSwift** for estimation. Estimated qty
   takeoff, but more detailed and efficient than manual. Manual estimating
   takes several days per job.
2. **Building SF.** IHC Fruita ~**14,251 SF gross**. Joseph used 15,000 -
   close but high by ~750 SF.
3. **Connection allowance.** ~4 to 6 braced frames with moment connections,
   remainder standard simple shear.
4. **Anchor Rod Count.** NOT 6 for the project. ~**37 columns**, each with a
   minimum of **4 anchor rods**. Drawing detail 10/S5.0 shows
   **3/4" diameter** anchor rods (not 1"), with PL 1/2" x 2" x 2" washer
   plates. Braced frame base plates can have up to ~8 rods each. True count
   is on the order of 150+, not 6.
5. **Deck SF.** ~equal to building SF. RTU openings and misc penetrations
   are minor and do not create significant reductions.
6. **Joist Series & Depth.** IHC Fruita drawings show **only Wide Flange
   and HSS framing**. **No joists indicated** on the drawings. The 5.50 T
   joist line in the estimate has no source. **Drop it.**
7. **Finish Selection.** Standard paint UNO. Correct for IHC Fruita.
8. **Drawing Stage.** 100% IFC drawing package. Correct.
9. **Camber.** No cambered members identified on IHC Fruita.

Ivan ends: "I will continue reviewing the remaining projects and provide
additional feedback accordingly."

## Status of the other two

- **South Park 183 Bldg 1** - Ivan pending. Was sent 2026-05-21, no verification reply yet.
- **Dolores PEMB** - Ivan pending. Was sent 2026-05-22, no verification reply yet.

## Rules to apply going forward

These derive directly from Ivan's answers and the questions left open.

### Rule A: PlanSwift is the takeoff tool, not Bluebeam

Skills `tender-ingest.skill.md`, `requirement-register.skill.md`, and
`spec-boq.skill.md` must reference PlanSwift as the source-of-record for
manual/semi-automated takeoffs at Your Company. Bluebeam may be used for
markup; the BOQ comes from PlanSwift.

### Rule B: Anchor rod count is computed, not defaulted

Reconciliation engine: never accept anchor rod count of 6 for a project
with more than 4 columns. Compute as:

```
anchor_rod_count = sum_over_columns( bolts_per_column )
default bolts_per_column = 4   (simple column base plate)
default bolts_per_column = 6-8 (braced frame or moment frame base plate)
```

If a bid line shows `Anchor Rods 6 EA`, the engine should flag it as
**Critical - ANCHOR_COUNT_UNREALISTIC** unless the column count is also
proportionally small.

### Rule C: Joist quantity gated by framing-plan evidence

If the framing plan and schedule contain only W-shapes and HSS with no
joist callout, the joist line must be zero. Reconciliation engine should
flag any non-zero joist quantity in this case as
**Critical - JOIST_NO_SOURCE**.

### Rule D: Anchor rod size is per-project, not global

The default 1" x 20" F1554 Gr.55 in the proposal template is a placeholder.
The actual size lives on the anchor schedule sheet (e.g. detail 10/S5.0 on
IHC Fruita shows 3/4"). Spec-boq skill must extract anchor rod diameter
and length from the anchor schedule before pricing.

### Rule E: Connection allowance is variable per job

Default 10% is acceptable for mixed-frame projects. For projects with
predominantly moment connections (e.g. 4-6+ braced frames with moment
connections in a small footprint), bump to 15%. For all-simple-shear
projects, drop to 8%. Reconciliation flag if the project mix is known
and the wrong tier was applied.

### Rule F: Building SF must come from the floor plan, not from a guess

Spec-boq skill must extract building SF from the architectural floor plan
or cover sheet square-footage table. lbs/SF gate logic depends on this
value. Confirm against drawings; do not default.

## Who is Ivan

- **Ivan L. Martinez** - Director of Engineering Department
- Email: ivan@yourcompany.example.com
- Office address per his signature: [COMPANY ADDRESS], Houston, TX 77018
  - This conflicts with the 77064 zip used in the master CLAUDE.md and on
    bid proposals. One of the two is a typo. Confirm with Owner before
    next bid revision.

This name and role should be added to the People section of the master
CLAUDE.md alongside Paul Guerrero, Mario Gutierrez, and Amber.

## What this means for the recon-report

The reconciliation test I just ran against Northside, Kinder Morgan, and
Marathon did not have access to this verification thread. Once Ivan
finishes SP183 and Dolores, the same Q-list should be re-run against
Northside Launchpad VERIFY (whose own GP report flagged the 60-65T vs
85T tonnage exposure - exactly the kind of issue Ivan's questions are
designed to catch upstream).
