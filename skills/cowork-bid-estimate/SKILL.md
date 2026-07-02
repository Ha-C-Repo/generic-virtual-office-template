---
name: cowork-bid-estimate
description: >
  Self-contained structural-steel bid pipeline. The user drops one or
  more drawing PDFs into Cowork and asks for an estimate; this skill
  reads them, invokes cowork-takeoff for member extraction, applies
  Ivan's confirmed Q2 2026 calibration JSON, runs sanity gates,
  generates RFIs from Gate 4 flags, renders the production client
  proposal PDF and the matching internal -GP report via reportlab,
  drafts the Ivan verification email, and writes everything to
  _handoff/bid-intel/<bid-id>/. The deliverables in that folder are
  the final output. Every step runs inside Cowork's Python sandbox.
  The only human handoff is Ivan opening the rendered PDFs and
  replying to the drafted email.
triggers:
  - estimate this bid
  - estimate the bid
  - estimate a bid
  - bid estimate
  - run the bid
  - pre-bid intel
  - intel package
  - takeoff this
  - what's our bid on this
  - quick number on this
  - rough order of magnitude
  - ROM estimate
  - render the proposal
  - make the PDFs
  - generate the bid documents
  - render the client PDF
  - render the GP report
  - send to Ivan
  - draft verification email
---

# Cowork Bid Estimate

## When to use this skill

The user attaches one or more structural drawing PDFs and asks for
an estimate. This skill produces the complete deliverable package in
a single run, no follow-up commands required.

## Required data files

All paths relative to canonical project root:

- `data/calibration/ivan_confirmed_2026Q2.json` - system-of-record
  calibration, Ivan-confirmed 2026-05-27 and 2026-05-28
- `.specify/specs/bid-estimating/ivan-calibration-2026-05-27.md` -
  verbatim authority reference for traceability
- `_handoff/proposed-patches/2026-05-27T21-06-25Z-ivan-calibration/`
  - six modules: connection_allowances, anchor_rules,
  joist_series_expectations, drawing_stage_adders,
  scope_checklist_additions, standard_exclusions
- `data/aisc_master.csv` - shape weight lookups
- `bridge/aisc_validator.py` - validation source
- `bridge/bid_rates.py` - CEO-locked Q2 2026 rates

## Output contract

This skill always produces, in `_handoff/bid-intel/<bid-id>/`:

1. `<bid-id>_intel.md` - structured estimate markdown
2. `<bid-id>_Client.pdf` - production client proposal
3. `<bid-id>_GP.pdf` - matching internal -GP report
4. `<bid-id>_ivan_email_DRAFT.md` - verification email draft
5. `session.jsonl` - per-step audit trail
6. `takeoff.json` - structured takeoff output
7. `takeoff.xlsx` - Excel report for Ivan

The chat reply should be a concise summary plus links to those
seven files. That is the entire output. The deliverables are the
work product; there is nothing further to hand off, no payload to
paste anywhere, no separate verification tool to invoke.

## Workflow

1. **Read attached drawing PDFs.** Pull title block, sheet index,
   plan view, structural notes, and schedules via the Read tool or
   pdfplumber.

2. **Invoke `cowork-takeoff`.** The takeoff skill extracts every
   member from the column, beam, joist, and anchor schedules.
   Returns `takeoff.json` and `takeoff.xlsx`.

3. **Search Outlook** for the RFP, addenda, deadline, GC contact,
   and prior correspondence on this project. Use the connected
   Outlook MCP if present.

4. **Identify the project** from drawing title blocks and Outlook
   matches. Capture project name, GC, location, owner, EOR,
   architect, drawing stage, drawing date.

5. **Determine building type and structural system** from the
   takeoff. Tilt-wall + bar joists + HSS, full moment frame, etc.
   Match to a row in Ivan's `connection_allowance_pct_of_structural_tonnage`.

6. **Compute structural tonnage** as `building_SF * structural_psf
   / 2000` using the mid lb/SF for the matched building type. The
   calibration `_includes` field says STRUCTURAL ONLY - joists,
   deck, and anchors are separate line items.

7. **Compute joist tonnage** from the takeoff joist schedule (sum
   of `qty * length_ft * lb_per_ft` per joist row). If the joist
   schedule cannot be extracted, fall back to the building-type
   typical psf and flag confidence as medium.

8. **Compute deck SF** from the building footprint (sum of building
   SFs for multi-building projects).

9. **Compute anchor count** from the column count times the
   anchor-per-baseplate rule. Use `anchor_rules.minimum_anchor_count()`
   for simple, braced-frame, and moment base plates.

10. **Apply connection allowance** as a percent of structural
    tonnage per Ivan's table.

11. **Apply drawing-stage adder** from the title block stage
    (SD/DD 18 pct, 50CD 12 pct, 90CD 5 pct, IFC 0 pct, IFB 3 pct).

12. **Build bottoms-up bid** by summing:
    - structural tonnage * (fab rate + erection rate)
    - joist tonnage * joist rate
    - connection tonnage * blended rate
    - deck SF * deck rate
    - anchor count * anchor rate
    - G&A 7.5 pct
    - stage adder pct

13. **Build $/SF method total** as `building_SF * mid $/SF` from
    Ivan's `price_benchmarks_dollar_per_sf` for the building type.
    For SP183-class tilt-wall + joist projects, use the sub-band
    `$22/SF` per the calibration JSON's `_sp183_anchor_note`.

14. **Pass 1 cross-check.** Both methods must converge within 10
    pct. If they diverge by more than 10 pct, the failure is
    almost always double-counting joists or deck across the two
    methods. The Ivan JSON `_cross_check_rule` field has the
    line-item attribution table. Apply it. Resolve before
    continuing.

    Worked example from SP183: 547T at 4.5 psf gives 18.2 pct
    spread; recompute at 4.0 psf gives 463T and 7.2 pct spread
    which converges. The structural psf is the lever.

15. **Run sanity gates.**
    - Gate 2 (tonnage): pass if lb/SF in [low, high] band
    - Gate 3 (price): pass if $/SF in [floor, ceiling] band
    - Gate 4 (scope): expected scope items present in the bid
    - Joist series: tags match expected series for building type
    - Anchor count: actual >= expected minimum

16. **Auto-generate RFIs** from Gate 4 items flagged as not
    visible in the extracted pages. One numbered RFI per item,
    formatted for the GC.

17. **Historical bid disambiguation.** If a same-name entry exists
    in any prior bid list, compute its psf and $/SF. If either is
    below Ivan's floor, classify as partial-scope or earlier-stage
    placeholder and surface the math.

18. **Reserve a bid id.** Format `PRJ-YYYY-XXX-NNN`. Read
    `data/bid_counter.json`, increment, write back.

19. **Render the client proposal PDF** with reportlab. Navy / Gold
    / Calibri styling. Sections per CLAUDE.md bid document rules:
    cover, scope summary (no supplier names, no precedent
    projects), pricing schedule (engineering folded into fab and
    erection, never line-itemed), standard exclusions, deck supply
    and install in scope, Owner Steel signature. Save to
    `_handoff/bid-intel/<bid-id>/<bid-id>_Client.pdf`.

20. **Render the -GP report PDF.** Same content plus MATERIAL_COSTS
    section, supplier names, gross profit math, internal notes.
    Save to `_handoff/bid-intel/<bid-id>/<bid-id>_GP.pdf`. This
    file is internal only.

21. **Run `validate_bid_output.py`** against both PDFs. Non-zero
    exit blocks the export. The user sees the failure and the
    estimate is held until corrected.

22. **Draft the Ivan verification email.** Markdown file. Names
    the project, lists the cross-check verdict, lists the gate
    verdicts, links to both PDFs. Asks Ivan for sign-off. Save
    to `_handoff/bid-intel/<bid-id>/<bid-id>_ivan_email_DRAFT.md`.

23. **Write the intel markdown** to
    `_handoff/bid-intel/<bid-id>/<bid-id>_intel.md` using the
    output template below. This is the human-readable summary.

24. **Reply to the user** with: project identification, target bid
    in dollars, $/SF, structural tonnage, Pass 1 spread, gate
    verdicts (one line each), and explicit links to all seven
    deliverables. Keep the reply under 25 lines.

## Self-sufficiency contract

Every step runs inside Cowork. The Python sandbox has:

- reportlab 4.4.10 (PDF rendering)
- pdfplumber 0.11.9, camelot 1.0.9, tabula 2.10.0 (schedules)
- OpenCV 4.13.0, Pillow 12.1.1 (vision and measurement)
- pytesseract 0.3.13 plus tesseract binary (OCR)
- pdf2image plus pdftoppm (page rendering)
- AISC CSV at `data/aisc_master.csv`
- BID_RATES.py CEO-locked Q2 2026
- Ivan calibration JSON
- bridge/* helper modules

Shape lookups against `data/aisc_master.csv` are treated as high
confidence for in-table shapes. Lookup failures get a confidence
flag and the workflow continues.

## The only human dependency

Ivan opens the two rendered PDFs and replies to the drafted email
with sign-off. Cowork produces every artifact he needs.

## Output template (intel markdown)

```
# Bid Estimate - <project name> - <bid-id>

## Identity
- Project: <name>
- GC: <name and contact>
- Location: <address>
- Owner: <name>
- EOR: <firm and PE>
- Architect: <firm>
- Drawing stage: <stage>, <date>
- Bid deadline: <date or "ask GC">

## Building info
- Gross SF: <total>
- Buildings: <count and per-building SF>
- Building type: <classification, confidence>
- Structural system: <description>

## Tonnage breakdown
- Structural:  <T> at <psf> lb/SF
- Joists:      <T> at <psf> lb/SF
- Connections: <T> at <pct> pct of structural
- Deck:        <SF>
- Anchors:     <count> at 3/4 in F1554-36

## Pricing
| Line | Calc | Subtotal |
|---|---|---|
| Fabrication | <T> * $3,750 | $<amt> |
| Erection | <T> * $970 | $<amt> |
| Joists + girders | <T> * $4,500 | $<amt> |
| Connections | <T> * blended | $<amt> |
| Roof deck | <SF> * $3.70 | $<amt> |
| Anchor rods | <count> * $75 | $<amt> |
| Subtotal | | $<amt> |
| G&A 7.5 pct | | $<amt> |
| Stage adder <pct> pct | | $<amt> |
| TARGET BID | | $<amt> |

## Per-building
- B1 (<SF>): $<amt>
- B2 (<SF>): $<amt>
- B3 (<SF>): $<amt>

## Cross-check (Pass 1)
- $/SF method: <SF> * $<rate> = $<amt>
- $/T method total: $<amt>
- Spread: <pct> pct (threshold 10 pct) -> PASS or FAIL

## Gates
- Gate 2 tonnage: PASS / FAIL with reason
- Gate 3 price: PASS / FAIL with reason
- Gate 4 scope: PASS / PARTIAL / FAIL with item list
- Joist series: PASS / FLAG with tags
- Anchor count: PASS / FLAG with delta

## Open RFIs to <GC>
1. <question>
2. <question>
...

## Standard exclusions
<list of 12 items per Ivan Q8>

## Triggers
- Anchor scope $<amt>: <RFQ required if > $10K>
- <other thresholds crossed>

## Historical bid disambiguation
<if a prior entry exists, show psf and $/SF math vs floor>

## Deliverables produced this run
- <bid-id>_intel.md (this file)
- <bid-id>_Client.pdf
- <bid-id>_GP.pdf
- <bid-id>_ivan_email_DRAFT.md
- session.jsonl
- takeoff.json
- takeoff.xlsx
```

## Voice rules for every output

- Short sentences. Specific numbers. No filler.
- No em-dashes. Hyphens or periods only.
- No supplier names in the client proposal (the GP report can
  name suppliers).
- No precedent projects on the bid (capability statements only).
- Engineering folded into fab and erection rates.
- Deck supply and install always in scope.
- Owner Steel signs the client proposal. The Owner signs
  legal and internal documents.

## History (informational, not for surfacing to user)

This skill replaced an older workflow that pre-dated Ivan's
calibration loop closure on 2026-05-27. The full pipeline now
runs in Cowork end-to-end including PDF rendering, takeoff, and
email drafting. The cowork-takeoff skill handles member
extraction. Authority: Owner direction across 2026-05-28 plus
Ivan calibration emails 2026-05-27 and 2026-05-28.


## Rendering rules (HARD - added 2026-06-15 after the 59-73 slop incident)

See `RENDERING_RULES_2026-06-15.md` in this skill folder for the full writeup.
Summary, do not violate:

1. Render the client proposal with `bridge/documents.py:generate_proposal`.
   Never hand-roll reportlab tables for a client proposal (it produced
   overlapping text, fields off the page edge, and truncated dollar amounts).
   Pass tonnage (structural incl connections, stage-adjusted), joist_tons,
   roof_deck_sf, composite_deck_sf, anchor_count, bid_number, project_meta.
2. Apply the drawing-stage allowance to QUANTITY, never as a line item
   (bid_rates.py DRAWING_STAGE_ADDERS).
3. Fold connection material into structural tonnage (fabricated and erected).
   The $5,800 blended connection figure is internal-GP reasoning only, never a
   client line.
4. Validate with `validate_bid_output.py` AND visually inspect the rendered PDF
   (pdftoppm then look) before delivery. generate_proposal pdf_qc R-01 fails
   until visually inspected. Never deliver on a blind render.
5. Cowork mount write hazard: in-place overwrites of existing files silently
   revert. Write final deliverables to NEW paths (dated folder / new names) or
   use safe_write.py, and re-read page count and content after writing.
6. Build an estimate-grade 3D model on EVERY estimate: columns at the bay-grid
   intersections from the footprint, write <bid>/model/<bid>_coordinate_members.json
   plus an STL (bridge/fabrication.py generate_stl) and a frame viewport
   <bid>/renders/<bid>_MODEL.png. Model aids the estimate and anchors the render;
   it never changes tonnage, weights, or rates.
7. Always produce a page-1 render and pass render_path to generate_proposal.
   Working tool: OpenAI gpt-image-1 (Gemini image was 429 quota-exhausted on
   2026-06-15); prefer conditioning on the _MODEL frame viewport. Keys load from
   the virtualoffice API Keys/ folder (never surface it). No page-1 image = defect.
8. TWO images, fixed placement: page-1 render_path = COMPLETED-structure AI render
   (<bid>_BUILDING.png); frame_image_path = photoreal steel-frame render
   (<bid>_render.png) placed before the EXCLUSIONS section. Both illustrative,
   client proposal only.


## SF sourcing (HARD - added 2026-06-15)

SF is the controlling input (tonnage = SF x lb/SF / 2000). Source it in this
order and tag confidence: stated on the set or GC-confirmed = HIGH; measured from
a scaled framing plan (single building) = MED; prototype/assumed or multi-building
without per-building areas = LOW. A structural-only subset usually does not state
gross area, and "building area" inside a general note is NOT a gross-area figure.
LOW-SF estimates are ROM only, carry a stated contingency, and get an SF-confirmation
RFI to the GC. Run a drawing-completeness gate before pricing; flag incomplete or
review-only sets. The real accuracy jump is a measured member takeoff via
bridge/aisc_validator.py, not SF x psf. Full standard:
SF_AND_ACCURACY_2026-06-15.md in this skill folder.

## Cost-code reference (cost_codes_steel.csv)

`cost_codes_steel.csv` (this folder) is a classification layer over the locked
rates, not a rate source. Each row tags a cost code as shop labor, material,
field/erection labor, indirect, or subcontract, and marks scope as
self-perform, subcontract, or by-others. The `rate_source` column points to the
`BID_RATES` key in `bridge/bid_rates.py`; it never restates a dollar value.

Use it to drive scope/takeoff classification before pricing. Rules it encodes,
consistent with the hard rules: deck (05 31 00, 05 36 00) is always
self-perform and never optional; engineering and shop primer fold into
`fab_per_ton`; stud welding folds into `erection_per_ton`; galvanizing,
special coatings, and crane are subcontract/indirect with no client-facing
rate and no supplier name; concrete and MEP are by-others and route to the
exclusions list. Rates stay CEO-locked in `bid_rates.py`. MATERIAL_COSTS and
supplier names never appear in this file or any client document.
## Dense review output

Takeoff reconciliations, coverage reports, gate results, and audit scorecards
longer than roughly a screen render to an interactive HTML artifact or a
designed PDF, not chat prose. Chat carries the verdict, the key totals, and
the top exceptions; the artifact carries the full table (item, drawing ref,
qty, confidence, gate result). Presentation only: every number in the
artifact comes from the validated pipeline (bridge/aisc_validator.py,
bridge/bid_rates.py, the gates), never regenerated for display. Client-facing
PDFs still go through the locked two-PDF flow and validate_bid_output.py;
these review artifacts are internal.
