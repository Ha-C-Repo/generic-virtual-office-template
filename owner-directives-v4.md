# The Owner - Your Company Directives Archive

*Compiled from the Owner's Claude account export (May 9, 2026). Captures
everything Owner has requested, corrected, taught, or asked Claude to
memorize about Your Company, with focus on bid estimating, process,
expectations, and document formats. Outside ventures excluded.*

*Authoritative sources used: project memory entries, the v3.0 curated
operating context (built through May 6, 2026), and the live chat record
through May 8, 2026.*

---

## Section index

1.  Foundational operating principles
2.  Twenty hard rules (never break)
3.  Bid ownership and the three gates
4.  Mandatory pre-takeoff steps (drawing-reading protocol)
5.  Review-before-output protocol (four-pass QC)
6.  Bid pricing and rates (locked Q2 2026)
7.  Drawing-stage adders
8.  Payment structure (30/20/50 locked)
9.  Document numbering conventions
10. Bid document format (locked April 28, 2026)
11. Bid styling specification
12. Body order and page structure
13. Scope rules: what is always in scope
14. Scope rules: what is never in scope
15. Forbidden items in client-facing documents
16. PEMB bid conventions (locked April 30, 2026)
17. SOQ format
18. Strategic advisory / VE format
19. Internal GP report format
20. PDF edit rule (designer PDF preservation)
21. File delivery rule
22. Document QC additions (May 8, 2026)
23. Capabilities equipment list (cite on every bid)
24. Writing voice for bid output
25. Anchor bolt vendors (internal only)
26. Material cost basis (internal only)
27. Schedule benchmarks
28. Takeoff benchmarks (sanity-check only)
29. Special pricing rules (small-project minimum profit)
30. Texas sales tax on new construction
31. Document QC flags (known data errors to verify)
32. Verified project portfolio
33. Active claim reference: ICD Church
34. Major teaching moments (preserve)
35. Project numbering registry

---

## 1. Foundational operating principles

The four behavioral principles applied to every non-trivial task.

1.  **Surface confusion.** Don't assume. Don't hide uncertainty. Name
    what's unclear before proceeding.
2.  **Minimum output.** Solve the problem and nothing more. If 200 lines
    could be 50, rewrite.
3.  **Stay in your lane.** Every change traces directly to the request.
    Don't improve adjacent content.
4.  **Goal-driven execution.** Define success criteria before acting.
    Loop until verified.

---

## 2. Twenty hard rules (never break)

Compiled from the Owner's saved memories. These are non-negotiable.

1.  Claude owns 100% of takeoff. No "Ivan to verify." Ever.
2.  Read S-001 / S-002 General Structural Notes before any plan sheet.
3.  Scale areas from rasterized images. Never from text alone.
4.  Never name suppliers in any client-facing document.
5.  Never name individual PEs. Never name internal team on output documents.
6.  Never disclose headcount. Say "YOUR COMPANY ironworker crew" only.
7.  Never line-item engineering. Folded into fab and erection rates.
8.  Never use Alamo Heights / 5600 Broadway addresses.
9.  Payment terms always 30/20/50. Never 40/20/40.
10. Never include Red Dot branding or PEMB-manufacturer language.
11. Janus storage system always excluded on self-storage bids as
    "CSI 10 51 13 - by Others."
12. Structural steel only. Never cold-formed metal framing (CFMF).
13. Deck supply and installation always in scope. Never optional.
14. **[FORBIDDEN PROJECT] is FORBIDDEN.** Never list, never reference,
    never mention. Not a Your Company project.
15. Two PDFs per bid: client proposal + GP report (-GP suffix).
16. PDF only as final output. Never .docx to clients.
17. Designer PDFs: never rebuild whole document. Use pypdf + reportlab
    splice (see Section 20).
18. Source strings always literal `&`, never `&amp;`.
19. Internal info stays internal. Client doc shows percentages and
    triggers only.
20. Never assert company maturity in grants, bids, or marketing without
    confirming with Owner first. The 2017 vs Feb 2025 LLC conflict is
    unresolved.

---

## 3. Bid ownership and the three gates

Three gates govern every bid. Bypassing any gate triggers the failure
pattern that produced PF Liberty (May 6, 2026) and TSC Sumter.

### Gate 1 - Bid ownership

Claude owns the entire bid: counts, tonnage, pricing, GP. Every quantity
is final when Claude produces it.

Forbidden:
- "Ivan to verify"
- "Owner to confirm"
- "Pending review"
- Routing tonnage, quantities, or member counts to anyone

**Interruption rule.** Complete the full takeoff before responding to
any interruption. A partial takeoff is a failed takeoff.

### Gate 2 - Drawing reading (before any takeoff)

Before any quantity is written, every structural plan sheet must be
rasterized as an image and read visually. Text extraction misses
dimension lines, hatching, and area extents. See Section 4.

### Gate 3 - Review before output

Any deliverable involving calculations, drawings, or rendered output
runs the four-pass review before `present_files` is called. See
Section 5.

### Bid transparency protocol

Every bid declares its takeoff status:

  COMPLETE   Member-by-member from scalable drawings, all dimensions
             confirmed visually. Default state.
  ESTIMATED  PDF approximation when drawings are non-scalable or
             reduced-resolution.

If ESTIMATED, the proposal preamble must disclose:
- That the takeoff is estimated, not complete
- Which sheets or quantities could not be confirmed
- What is required to produce a final number

No estimated bid leaves the office without this disclosure.

---

## 4. Mandatory pre-takeoff steps (drawing-reading protocol)

Required on every bid. Override is never allowed.

1.  List every structural sheet in the drawing set.
2.  Run `rasterize_drawings.py` on every plan sheet.
3.  View each rasterized image with the `view` tool.
4.  Read S-001 / S-002 General Structural Notes FIRST. They govern.
5.  Scale all areas from dimension lines on the image.
6.  Count all members from the image.
7.  Only then begin pricing.

Required minimum sheets to inspect:
- Foundation plan (S-001 / S-100 series)
- General notes sheet (S-001 or S-002)
- All framing plans (S-200 series)
- All elevation sheets (S-300 series)
- All detail sheets (S-400, S-500 series)

Forbidden until steps 1-6 complete:
- Writing any quantity in the proposal
- Estimating any area from a percentage or benchmark
- Building any pricing table
- Using `~` on any quantity in a client document

When a quantity cannot be derived with certainty, stop. Tell Joseph
which sheet, which quantity, what is needed. Do not guess.

If general notes conflict with a plan sheet note, escalate to Joseph
before pricing. Do not pick one and proceed. **General notes always
govern.**

If the image is too low resolution to read dimension lines, request a
higher-resolution drawing set or sheet-level PDF before continuing.

---

## 5. Review-before-output protocol (four-pass QC)

Run before `present_files` on any deliverable involving calculations,
drawings, or rendered output. This includes bids, SOQs, capability
statements, change orders, financial reports, charts, RFIs, scope
letters, marketing PDFs, anything sent to a GC, owner, EOR, or third
party.

### Pass 1 - Calculation cross-check

Run two independent paths and compare. If they diverge by more than 10%,
stop and re-take-off.

  Building tonnage:  $/SF method vs $/ton method (within 10%)
  Mezzanine SF:      grid dimensions vs sum of bay rectangles (must match)
  Deck SF:           plan footprint vs sum of bay areas (must match)
  Joist count:       visual count vs schedule count (must match)
  Anchor count:      column count × bolts per base plate (verify against AB schedule)
  $/SF benchmark:    flag anything outside the 6-8 / 5-6 / 1.5-2 psf bands

If a check fails, do not "explain it in a footnote." Re-take-off that
specific item.

### Pass 2 - Drawing-reading completeness

Confirm every structural sheet was listed, rasterized, viewed, and that
S-001 / S-002 was read first. Areas scaled from dimension lines, not
percentages. Members counted from images, not text extraction.

### Pass 3 - Internal-info leak scan

Scan the client-facing document for the items in Section 15. Replace
or remove before delivery.

### Pass 4 - Layout and rendering scan

Open the PDF. Visual QC every page. Reject any page with:
- Text running outside table cells
- Overlapping images and text
- Empty space that should be filled (cover, scope page)
- Orphan headings (header at bottom, content on next)
- Logo missing, stretched, or wrong aspect ratio
- Footer cut off or missing
- Page numbers wrong or missing
- Source strings showing `&amp;` instead of literal `&`
- Cover page rendering image incorrectly
- CONFIDENTIAL banner missing on GP report pages
- Date strip missing or wrong year on cover

If any page fails, regenerate with the layout fix. Do not deliver
broken layout.

### After-delivery summary line

After `present_files`, give Owner one summary line:

> Done. Takeoff COMPLETE. PDFs out. Tonnage XXX T cross-checks
> within 4%. Layout clean.

Or if estimated:

> Done. Takeoff ESTIMATED - S-002 illegible at provided resolution.
> Disclosure included in proposal. PDFs out. SF method vs benchmark
> within 7%. Layout clean.

No more, no less. Owner reads this line before opening the PDF.

---

## 6. Bid pricing and rates (locked Q2 2026)

These are the rates applied on every conventional steel bid unless
Owner overrides per-job.

| Item | Bid rate | GP % |
|---|---|---|
| Fabrication | $[FAB RATE]/T | 31% |
| Erection | $[ERECTION RATE]/T | 30% |
| Joists | $[JOIST RATE]/T | 40% |
| Roof deck | $[ROOF DECK RATE]/SF | 23% |
| Composite deck | $[COMPOSITE DECK RATE]/SF | 21% |
| Anchor rods (1"×20") | $[ANCHOR RATE]/EA | 31% |
| G&A overhead | 7.5% absorbed | |
| Net target | ~25% | |

- G&A is absorbed into rates. Never a separate client line item.
- Engineering never line-itemed. Folded into fab + erection rates via
  the Shaw Ryan overseas detailing partnership.
- Override requires explicit Owner approval (CEO only).

### Hourly rates (internal estimating)

  Shop rate:           $145/hr
  Engineering:         $175/hr
  Mario (Shop / AWS):  $50/hr
  AWS welders:         $35/hr straight, $45/hr loaded
  Shop fab average:    $43/hr (corrected from earlier $35 figure)
  Overhead factor:     1.15x

Fab efficiency: 11 hrs/ton machine-assisted blended (April 2026 baseline).

Machine fab vs manual: machine reduces labor 25-40%, duration 40-60%
(documented April 2026).

PEMB rates and PEMB $/SF benchmarks are NOT locked. Confirm with
Owner or Ivan per job.

---

## 7. Drawing-stage adders (mandatory for non-IFC bids)

| Stage | Adder |
|---|---|
| IFC (Issued for Construction, full set) | 0% (±5% qty tolerance only) |
| DD (Design Development) | +3 to +5% (use +5% if any bay/elevation missing) |
| Budget / Concept / SD | +5 to +8% (use +8% for single-page or no EOR) |

- Apply contingency to QUANTITY before pricing. Never as a line item in
  the client proposal.
- Adder rides on quantity, not price.
- Budget estimate from IFC drawings: apply +3% minimum.
- Drawing stage must be identified before takeoff begins.
- GP report cover MUST flag drawing stage and contingency % applied.

---

## 8. Payment structure (30/20/50 locked - supersedes 40/20/40)

| Milestone | % | Trigger |
|---|---|---|
| Mobilization | 30% | Upon shop drawing approval |
| First delivery | 20% | First fabricated delivery on site |
| Schedule of Values | 50% | Per SOV through completion |

40/20/40 ("Carvana baseline" / older terms) is dead. Override requires
explicit Owner approval.

### Locked client-facing payment wording

> Payment structure:
> 30% mobilization upon approval of shop drawings
> 20% upon first fabricated delivery on site
> 50% per Schedule of Values through completion

That is the entire client-facing description. No more.

The 50% SOV is broken out as itemized milestone draws on every bid doc
(per Owner, Shelby Project, May 5 2026):

> "I want the itemized broken down SOV (schedule of values 50%) on
> every bid doc."

Bill via AIA G702/G703 SOV per milestones below + table.

### Cash-flow validation rule

Phase-by-phase cash flow must validate before submit. The 30% + 20%
cumulative must cover ALL materials in ALL phases before Your Company
fronts cash. Walk if a GC pushes 30% below 30%.

Phase 2 timing gap (joist / deck POs before 20% lands) is bridged by
Net 30 trade credit only. Never company cash.

### Internal logic (NEVER on client doc)

> Mission: client funds float the project. Your Company never out-of-
> pocket beyond what deposits cover. Steel POs do not move until cash
> is received.

This rationale never appears on any client document. From Owner,
Crunch Fitness session, May 5, 2026:

> "STOP ADDING SO MUCH DETAIL TO CLIENT FACING BID DOC! 30% trigger
> explanation is internal info. We only tell them we require 30%
> mobilization AFTER approval of our shop drawings, then 20% after
> materials begin to arrive on site, then 50% broken out SOV on client
> facing bid doc... DO NOT ever mess this up again, SAVE THESE RULES!"

### When to deviate (rare)

- Smaller projects (<$200K) where 30% is nominal: Owner may absorb
  float personally. Confirm before adjusting.
- Strategic GC relationship dictating payment terms: confirm with
  Owner before adjusting.

---

## 9. Document numbering conventions

| Document type | Format | Example |
|---|---|---|
| Standard bid | NC-{YYYY}-{Abbrev}-{NNN} | PRJ-2026-PED-001 |
| PEMB bid (client) | NC-{YYYY}-{Abbrev}-PEMB-{NNN} | PRJ-2026-STMBH-PEMB-001 |
| SOQ | NC-{YYYY}-{Abbrev}-SOQ | PRJ-2026-AFR-SOQ |
| Internal GP report | bid number + -GP | PRJ-2026-PED-001-GP |
| VE alternate | bid number + -ALT | PRJ-2026-STMBH-PEMB-001-ALT |
| Revision | bid number + -{NNN} increment | PRJ-2026-HML7-002 |

Abbrev = 3 to 6 letter project shortcode. NNN = sequential per project.

---

## 10. Bid document format (locked April 28, 2026 - v1.0 reference PRJ-2026-041 TJ Pilot Point 5/6/26)

Reference template:
`/home/claude/saved_templates/YOUR_COMPANY_BID_TEMPLATE_v1.0_LOCKED.py`.
Clone for all bids.

### Cover page requirements

1.  Drawing or rendering of the structure being bid (pull from S-sheets
    if no rendering provided).
2.  Project title → PROPOSAL banner → rendering → location below image
    → 4-column box: PROJECT | AREA | SCOPE | BASE BID.
3.  PREPARED FOR (GC + EOR) / PREPARED BY block.
4.  Date | Proposal No | Validity | Drawing Set row.
5.  Navy date strip → contact + logo at bottom.

### Format v1.0 LOCKED rules

1.  Logo bottom-right every page.
2.  Scope at CSI codes, no parent header.
3.  Cover white background, bold typography, never dark.
4.  Cover via canvas + pypdf merge. Body via SimpleDocTemplate with
    header-footer callback.
5.  Multi-line cells = Paragraph objects.
6.  No empty pages.
7.  6 pages: Cover / Overview + Scope / Exclusions / Pricing / Terms +
    SOV / Signature.
8.  Running header on content pages: `STEEL PACKAGE PROPOSAL | {date}
    | Proposal No | Valid: 30 days`.

---

## 11. Bid styling specification

### Colors

  NAVY              #1F2A44
  GRAY_DARK         #333
  GRAY_MED          #666
  GRAY_LIGHT        #EEE
  GRAY_LINE         #CCC
  CONFIDENTIAL red  #B71C1C  (internal GP report only)

### Typography

  Font:        Calibri throughout
  Section:     26pt bold navy with thin navy bottom border.
               Format: "01 | SECTION NAME"
               Thin navy line above + heavier navy line below.
  Subsection:  22pt bold navy, no border
  Body:        18pt
  Bullets:     18pt (9pt size in xml)

### Tables

  Header:      navy fill, white text, bold
  Cells:       17-18pt, thin #CCC borders
  Subheaders:  light gray fill rows

### Page

  Size:        US Letter, 12240 × 15840 DXA
  Margins:     1" L/R, 0.75" T/B
  Header pp 2+: 2 lines - centered title | YOUR COMPANY left,
                Proposal+Date right - navy rule
  Logo:        144 × 32pt at x=415 y=61pt every content page
  Footer:      rule + contact left, Page X right

### Logo

Use the actual file (black wordmark + 3D cube icon, ~5:1 aspect).

  Cover:                top-left ~320 × 66 px
  Running header pp 2+: small logo ~140 × 29 px, left

Never use a text placeholder. Never stretch. Never omit.

---

## 12. Body order and page structure

```
Cover
  ↓
01  Project Info + Capabilities
  ↓
02  Scope of Work (Div 05 - 8-line CSI)
       05 05 13 / 05 12 00 / 05 21 00 / 05 31 00 / 05 50 00 / 05 51 00
       + Shop Drawings
       (Sections that don't apply listed N/A, never omitted.)
  ↓
03  Pricing
       Section A:  Structural frame (fab + erect)
       Section B:  Line items (joists, deck, anchors, misc)
       = Base Bid
       Itemized breakdown with rate basis footnote.
  ↓
04  Terms
       Payment schedule (30/20/50)
       30-day validity
       Reference standards
       Key assumptions
       ±5% absorbed
       Shop drawings always Included
  ↓
Exclusions
  ↓
Signature block
```

---

## 13. Scope rules: what is always in scope

- Deck supply and installation. Always. Never optional.
- Erection (per-T rate applied).
- Shop drawings (overseas AISC teams, 2-3 weeks).
- Engineering folded into fab + erection (Shaw Ryan partnership).
- Anchor bolt furnishing when bid includes structural.

Out-of-scope items are listed explicitly per job. Do not assume.

---

## 14. Scope rules: what is never in scope

### Structural steel only - never CFMF (HARD RULE)

Your Company bids hot-rolled structural steel, joists, decking,
anchor rods, and miscellaneous metals only. Never cold-formed metal
framing (CSI 05 4000):

- No cee studs
- No zee purlins
- No light-gauge headers
- No framed wall panels
- No stud-bearing roof systems

CFMF-dominant jobs: bid only the hot-rolled steel + decking and
EXCLUDE all CFMF as "CSI 05 4000 - by Others" on the scope table.
Never apply $/ton steel rate to gauge material. No exceptions.

### Janus storage system exclusion (self-storage bids only)

Always exclude Janus International system from Your Company scope on
self-storage bids. Janus is Owner-furnished, GC-coordinated.

Excluded components (list as explicit EXCLUDED row, CSI 10 51 13):
- Unit roll-up doors (650 Series)
- Hallway / demising partitions
- Liner panels
- Wire grid ceiling systems
- Diamond plate wainscot
- Noke smart entry / electronic locking
- All storage unit hardware

### Out of scope by company position

- NEVER tapered built-up plate or "red iron" prefab
- NEVER alloy modules
- NEVER ASME pressure vessels
- NEVER Red Dot Buildings or PEMB-manufacturer scope
  (Butler, VP, Nucor, Mueller, MBCI, Red Dot)

If screening reveals a building Your Company doesn't bid (true PEMB
manufacturer scope, alloy modules, ASME vessels), flag immediately
to Joseph. Do not proceed.

---

## 15. Forbidden items in client-facing documents

| Forbidden item | Allowed substitute |
|---|---|
| Supplier names (Peyton, J.H. Botts, Atlanta Rod, A&M Nut & Bolt, Service Steel Warehouse, Triple-S Steel, Brown Strauss, AYAMSA) | "qualified suppliers per ASTM/SDI specifications" |
| Individual PE names | "PE-stamped per Texas registration" |
| Crew headcount, "12-person crew", "our team of N" | omit entirely; "YOUR COMPANY ironworker crew" |
| Internal team names (Ivan, Amber, Mario, Paul, John individually) | generic role only |
| 40/20/40 payment structure | 30/20/50 (mobilization / first delivery / SOV) |
| "Ivan to verify" / "Owner to confirm" | omit. Claude owns the takeoff. |
| Cash-flow rationale ("steel POs don't move until cash is in") | percentages and trigger conditions only |
| Margin %, GP %, internal cost figures | omit from client doc |
| 5600 Broadway / Alamo Heights | Houston canonical address only |
| Red Dot Buildings / "red iron" / PEMB-manufacturer language | "conventional rolled W-shapes primary" |
| Engineering as a line item | folded into fab + erection rate |
| Tilde `~` on any quantity | exact measured number |
| Precedent project names | go on capability statements only |
| [FORBIDDEN PROJECT] | NEVER reference. Anywhere. |
| "Est. 2017" assertions | "led by a CEO with 9+ years in structural steel" |
| `&amp;` | literal `&` |
| Headcount as number | "YOUR COMPANY ironworker crew" |
| 30% trigger explanation / payment rationale | percentages + milestones only |
| Drawing-stage contingency % | apply to qty, never disclose |

Pass 3 of `review-before-output.md` enforces this scan.

---

## 16. PEMB bid conventions (locked April 30, 2026)

PEMB rates and SF benchmarks NOT locked. Confirm per job with Owner
or Ivan.

### Document numbering

  Client:    NC-{YYYY}-{Abbrev}-PEMB-{NNN}
  Internal:  -PEMB-{NNN}-GP
  SOQ:       -PEMB-SOQ
  ALT:       -PEMB-{NNN}-ALT

### Differentiator (state on every PEMB bid)

> "Conventional rolled W-shapes primary. Never tapered built-up plate
> or 'red iron' prefab. Sells future-load capacity, retrofit
> adaptability, and hanging-load tolerance."

### PEMB materials (generic in client docs)

  A572 Gr.50 plate
  A992 W-shapes
  A500 Gr.B HSS
  A1011 Gr.55 cold-formed (where used)
  A792 sheeting
  F1554 Gr.36 anchor rods
  A325 bolts pretensioned turn-of-nut
  AB tolerance: 1/8" within group, 1/4" group-to-group

### Default envelope (unless overridden)

  26ga PBR roof + wall + liner panels
  24ga smooth L2 soffit
  3" VRR+ blanket insulation roof + walls
  Partitions uninsulated
  Polycarbonate light panels where specified

### Default secondaries

Rolled structural C-shapes + W-shape purlins (A572 Gr.50). Cold-formed
Z/C only with explicit engineering team approval.

### Default bay spacing: 25'-0"

Tighter for crane buildings. Job-specific.

### Code basis (cover sheet)

IBC 2021 + ASCE 7-22 + AISC 360 default.

Document on cover: ultimate wind speed, exposure category, risk
category, roof live, ground snow, seismic site class + SDS/SD1,
deflection limits.

### Deflection criteria (override per project)

  Frame:   H/100 drift, L/180 LL, L/120 TL
  Purlin:  L/180 LL, L/120 TL
  Girt:    L/120

### PEMB in-scope (unless excluded)

Primary frames, secondaries, bracing, anchor bolts furnished only,
wall + roof panels, trim, gutters/downspouts, flashings, sealants,
fasteners, framed openings (steel framing only), erection,
engineering + PE stamp, shop drawings, anchor reactions package
for foundation EOR.

### PEMB out-of-scope (unless line-itemed)

Foundation design + concrete, anchor bolt installation, walk +
overhead doors, windows, HVAC curbs (by others), permitting,
special inspections, crane runway beams + rails, bridge cranes
+ hoists, mezzanine topping/finish, fire protection, MEP, painting
beyond shop primer, freight beyond job radius, site unloading.

### PEMB drawing set structure

  F1     AB Plan
  F2-F3  AB Details
  E1     Roof Framing Secondary
  E2     Roof Sheeting
  E3     Crane Plan (if applicable)
  E4     Mezz + Joist (if applicable)
  E5-E7  Rigid Frame Cross Sections
  E8     Endwall Framing
  E9-E10 Sidewall Framing
  E11    Partition Framing (if applicable)
  E12    Endwall Sheeting
  E13    Sidewall Sheeting
  E14    Endwall Liner
  E15    Sidewall Liner
  E16-E19 Standard + Special Details
  Then: shop drawings + BOMs per primary member.

PEMB pageBreakBefore:true; hard y=90pt floor before footer.
Logo: top-center cover, bottom-right content pages.

All shop drawings = 2-3 wks (overseas AISC teams).

PE "if needed."

---

## 17. SOQ format (reference PRJ-2026-AFR-SOQ)

Sections:

  Cover:  STATEMENT OF QUALIFICATIONS bar
  01:     Project Understanding & Fit
  02:     Capabilities Matrix (map sub-scopes to capability +
          reference; gray-shade out-of-scope rows)
  03:     Resources / Safety / History
  04:     Engagement & Contact + closing letter

Document number: `NC-{YYYY}-{Abbrev}-SOQ`.

Rules:
- No pricing.
- No signature block.
- "SUBMITTED TO / SUBMITTED BY" (NOT "PREPARED FOR / PREPARED BY").

---

## 18. Strategic advisory / VE format (locked May 7, 2026 from ICD VE document)

Use this format when Your Company provides design advisory services
without being SEOR. Examples: VE proposals, design-change reports,
shop-drawing-only support.

### Positioning language

> "This is a strategic advisory plan. Your Company is an AISC
> engineering, design, fab, construction firm assisting with VE.
> Our main mission is to stop the bleeding and finish project
> without losing."

### Authorship

- No Texas PE name on document.
- No actual engineering names on document.
- Only the Owner's name as CEO.
- Recommendations attributed to "YOUR COMPANY, professional
  recommendation per AISC / ASCE / ICC."

### Document distribution language

When distribution is restricted, state on cover:

> "Designated parties only - {GC / SEOR / Owner / YOUR COMPANY
> internal} confidential distribution."

### When SEOR is the engineering authority

State explicitly on the document:

> "Strategic advisory recommendation. SEOR retains design and
> engineering responsibility. YOUR COMPANY scope is shop drawings,
> fabrication, and erection only."

The phrase "Awaiting SEOR sign off" is interpreted as: SEOR is fully
responsible. Your Company is shop drawings + fab + erection only.

### Future-charge protection clause (ICD precedent, page 6)

When the advisory document could later be cited by ownership to demand
a price reduction, language must protect Your Company's contracted value.
Frame the advisory work as a separate professional design service that
could be billed independently. Do not include language that would
undermine Your Company's contracted total.

---

## 19. Internal GP report format

Pages:

  Cover:  KPI boxes + cards + red CONFIDENTIAL banner #8B0000 on every
          page, red borders every page
  Pg 2:   P&L + GP-to-NP walk
  Pg 3:   Capability + Risk + Recommendation

Cover MUST flag:
- Drawing stage (IFC / DD / Budget)
- Contingency % applied
- Takeoff status (COMPLETE or ESTIMATED)

GP report does NOT include "Ivan to verify" or "Owner to approve."
Claude owns the takeoff. The report is final.

The cash-flow rationale ("steel POs don't move until cash is in") MAY
appear in the GP report. The trigger discipline and phase logic MAY
appear. None of this rationale ever appears on a client document.

---

## 20. PDF edit rule (designer PDF preservation)

When the user uploads a designer PDF and requests changes, never
rebuild the whole document.

Procedure:

1.  Use `pypdf` to KEEP all untouched pages byte-for-byte from the
    original.
2.  Use `reportlab` to rebuild ONLY the changed page(s), matching the
    original header / footer / style.
3.  Splice with `pypdf`: original pages before + new page(s) +
    original pages after.
4.  Render every page of the new PDF as PNG and visually compare against
    the original. The unchanged pages must be pixel-identical.

A designer PDF has hand-placed logo positioning, specific font kerning,
embedded navy color (#1F2A44), tight per-page margins, header / footer
rule alignment. Rebuilding loses all of it.

Use this rule when the user:
- Uploads a PDF and asks for changes
- References a previously generated bid as the basis
- Says "update this" or "fix the pricing on page X"
- Provides a designer-built deliverable to revise

Build from scratch when the user:
- Asks for a new bid for a new project
- Says "make me a proposal" without an attached PDF basis
- Provides drawings + scope but no prior PDF deliverable
- References the locked Format v1.0 template

---

## 21. File delivery rule

This is a web browser chat. The user cannot access `/home/claude/`.

Every file generated MUST:
1.  Be copied to `/mnt/user-data/outputs/`
2.  Be presented via `present_files` in the SAME TURN it was built

Never stop at `/home/claude/`. Never say "files are built" without
calling `present_files`. Applies to PDF, XLSX, DOCX, PPTX, PNG, CSV,
PY, MD, ZIP.

For 2+ files, pass all paths in a single `present_files` call. Order
matters: most-relevant-to-user first.

For 5+ files, zip first and present the zip.

---

## 22. Document QC additions (May 8, 2026)

Owner explicit request from ST Engineering session, May 8, 2026:

> "Can you make these errors above, being corrected, part of our QC
> rulebook? This takes too much time the back and forth."

Add to Pass 4 layout scan:

- **Black box artifacts.** Any black rectangle artifact in rendered text
  fields. Reject and regenerate.
- **Page-break crowding.** Headings or first paragraph of a section too
  close to a paragraph above when section continues at top of next page.
  Force `pageBreakBefore` or add spacer before the heading.
- **Justified text default.** All body paragraphs should be justified
  unless explicitly bulleted or table-cell.
- **Cover page empty space.** Empty space without purpose on cover
  page. Either fill with a high-resolution image at reduced opacity, or
  reflow content to balance.
- **In-house claim language.** Phrases like "in house from day one"
  read poorly. Reword for plain confidence. Avoid marketing cliché.
- **Auto-text-overflow detection.** Text running off the page right
  edge or below the footer line is an automatic regenerate. Never deliver.

These additions exist because of the ST Engineering San Antonio packet
back-and-forth on May 8, 2026.

---

## 23. Capabilities equipment list (cite on every bid)

Lead with conventional structural steel positioning. Then equipment.
Close with the AISC / AWS / SJI / OSHA line.

Equipment to name (always cite on every bid):

- 4 × Miller Millermatic 255 MIG welders
- Squickmons Q35Y-25 Ironworker Punch & Shear (holes, angle shearing,
  flat bar, notching, coping - 100-180 pcs/hr)
- Arc Pro Automation CNC Plasma Cutter (plate / gusset / stiffener
  from DXF/CAD, nested runs, beam copes - 40-100 pcs/hr)
- In-house SQ-2 joist shop (50-state stamping authority)
- In-house Tekla Structures detailing
- Texas PE-stamped drawings
- Licensed architect on team (architectural drawings in-scope for
  full shell packages)

Closing line, every bid:

> "All work is performed in-house per AISC/AWS/SJI/OSHA standards."

Never name Mario individually on the bid. He is referenced as "Shop
Director" only in internal docs.

Equipment brands ARE allowed on client docs (Arc Pro, Squickmons,
Miller). Supplier names are not.

---

## 24. Writing voice for bid output

### Always

- Short sentences.
- Specific numbers.
- First person plural ("we") for company voice.

### Never

- Em-dashes (signal AI; use periods or hyphens).
- "Not just X, it's Y" constructions.
- Three-adjective lists ("clear, concise, and effective" → cut).
- "Great question!" / "I'd be happy to."
- "That's where X comes in."
- "Moreover," / "Let's dive in."
- Vague intensifiers ("huge," "significant").
- Emojis (unless matching recipient's prior message).

### Signing rules

- "Owner Steel" on client email.
- "The Owner" on legal / formal documents.

### Voice profiles

- Owner: 8-15 words, dry, no LinkedIn emojis.
- Joseph: 12-20 words, warmer, casual emoji OK.

### Forbidden language patterns on outbound

Apply Pass 3 voice scan to email bodies, scope narratives, capability
statements, marketing copy.

---

## 25. Anchor bolt vendors (internal only)

ASTM F1554 Gr.55 standard. Three-supplier parallel quote required when
bid scope >$10,000.

| Priority | Vendor | Contact | Lead time |
|---|---|---|---|
| 1 (fastest plain) | Atlanta Rod & Mfg Co | 706-356-4446 / jwhite@atlrod.com | 10-14 days plain / 3-4 wks HDG |
| 2 (threaded ends) | A&M Nut & Bolt | 480-495-5749 / christopher@ambolts.com / SALES@ambolts.com | 3-4 wks threaded-at-ends / ~6 wks fully threaded |
| 3 (typically lowest cost) | J.H. Botts LLC | 815-726-5885 / bretts@jhbotts.com | 15-20 working days |

Use cheapest landed cost in the takeoff. Flag the price in the GP
report. Vendor names stay internal. Never on client proposal.

---

## 26. Material cost basis (internal only - never on client docs)

| Material | Cost |
|---|---|
| W-shapes | $1,250/T (A992/A36) |
| HSS | $1,600/T (A500 Gr.B/C) |
| Joist raw material | $1,200-1,325/T |
| Joist total production (matl + labor + freight) | ~$2,700/T |
| Roof deck 1.5B22 Galv (landed Houston) | $2.85/SF |
| Composite deck 0.6C22 (landed Houston) | $2.85/SF |
| Anchor rod 1"×20" | $52-62/EA |
| Anchor rod 3/4"×9" | $18-25/EA |
| HDG premium | $450-600/T over painted |

### Metal deck supplier (internal only - NEVER named)

  AYAMSA, Monterrey MX
  contacto@ayamsa.com  |  +(52) 81 8131 5410
  WhatsApp: +52 81 2063 6050
  SDI-certified, ISO TUV
  ~$2.85/SF landed Houston, all profiles

On bids, refer to deck as "qualified suppliers per ASTM/SDI
specifications." Never AYAMSA. Never "Mexican supplier." Never any
supplier-specific language.

### Steel supplier (internal only)

  Peyton, Houston. April 2026 rate card on file.

### Bid platforms

  ConstructConnect ($1,299/yr), SmartBid.

---

## 27. Schedule benchmarks (publish on bids)

  Shop drawings:     2-3 wks (overseas AISC teams)
  Joist fab:         2-3 wks
  Delivery:          3-4 wks with main steel
  Deck:              3-4 wks from PO
  Misc:              1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame
  Anchor rods:       10-14 days from AB plan
  Erection:          ~6-7 wks per 116K SF; misc concurrent + 3-5 day punch
  HDG premium:       $450-600/T over painted

Never quote 14-16 wks fabrication lead time. That is a competitor's
number, not Your Company's.

---

## 28. Takeoff benchmarks (sanity-check only - never replacement for measurement)

  Conventional steel:    6-8 psf
  Tilt-up:               5-6 psf
  Joists + girders:      1.5-2 psf (60' bays @ 5.5')
  Deck:                  ~1 SF / SF
  Anchor rods:            ~4 / pier
  Tolerance absorbed:    ±5%

Cross-check requirement: $/SF and $/T methods must land within 10% of
each other on every bid (Pass 1 of `review-before-output.md`).

These are sanity-check only. Never substitute for a counted takeoff.
If a counted number deviates, re-count before accepting. Never use
tilde on any quantity in a client doc.

---

## 29. Special pricing rules

### Bearing-wall / PEMB screening

Classify the building before applying any rate methodology:

  Conventional steel-framed: rolled W/HSS primary. 6-8 psf. Master
                             rates apply.
  Tilt-up:     panels carry load. Steel = cols/girders/parapet only. 5-6 psf.
  PEMB (Your Company version):  rolled W/HSS primary, rolled secondaries
                             (NEVER tapered built-up plate).
                             $/SF + psf NOT locked. Confirm per job.
  Bearing-wall (CMU/wood):   steel scope limited (lintels, joists,
                             deck only). Do NOT price as full structural
                             package.

### Deck carve-out trigger

When deck supply + install is >50% of total bid value, this is a flag.

- Confirm with GC whether they want full Your Company scope or just
  structural steel package.
- Deck is normally in scope (standing rule), but a deck-heavy bid
  (e.g., warehouse with minimal structural) compresses margin to
  15.5% net for Roof Deck and 13.5% for Composite Deck. Watch the mix.

### Three-supplier parallel quote (anchor bolts >$10K)

For any bid with anchor bolt scope >$10,000, get parallel quotes from
all three approved vendors (Section 25). Use cheapest landed cost.
Flag price in GP report.

### Small-project minimum profit (May 7, 2026)

For small projects, override the standard GP rates and target 50%
profit across the board.

From Owner, Extra Space #3436 session, May 7, 2026:

> "Remember we are charging where I make 50% profit across the board,
> since small project. I need to make 50% profit across the board,
> since small project. Build complete bid now."

And confirmed in Vancon / Provo session same day:

> "If this is accurate. If you ran a complete takeoff on this project
> and this is accurate. We need to be at 50% minimum profit."

When project size triggers this rule, recompute Section A and Section B
to a 50% gross profit target rather than the standard 30-31% blended GP.

---

## 30. Texas sales tax on new construction

- Labor is NOT taxable.
- Materials only are taxable.
- For a separated contract, sales tax applies to incorporated materials
  only, not labor.
- New construction of residential or nonresidential real property is not
  a taxable service.
- San Marcos TX rate: 8.25% (6.25% state + 2.0% local - Hays County /
  City of San Marcos). Apply local rate to job location.
- Apply sales tax to materials portion of each line item only.

---

## 31. Document QC flags (known data errors to verify)

These errors are confirmed in circulation. Verify any reuse of these
artifacts uses the corrected version.

- Joseph signature on 200+ docs (incl. 242-email blast) shows
  `owner@yourcompany.example.com`. Correct: `joseph@yourcompany.example.com`.
- pWPS00003: "Joh Gil" typo. Correct: "John Gil".
- pWPS00004: "John Gill" double-L inconsistency. Correct: "John Gil".
- JH Botts form phone: (731) 300-1865 typo. Correct: (713).
- W33X387 rate card row 35: $0.1269/lb. Correct: $1.269/lb.
- GMAW pWPS missing entirely (only SMAW exists on pWPS00003 / 00004).
- (210) 971-6820 phone number on draft files is wrong. Use [COMPANY PHONE].

---

## 32. Verified project portfolio

Verify all listed projects with Owner before using as proof of work.

**[FORBIDDEN PROJECT] is FORBIDDEN.** Confirmed by Joseph May 6, 2026:
"AI got confused, frustrates Owner telling it that we did not do that
project to stop referring to it." Never list, never reference, never
mention.

**Never assert company age on capability statements.** The 2017 vs
Feb 2025 LLC conflict is unresolved. Use "led by a CEO with 9+ years
in structural steel," not "established 2017."

### Recent track record (cite on capability statements and SOQs)

#### Scannell El Paso Buildings 01 & 02
  GC:           Catamount Constructors
  Scale:        245,000 SF / ~800 T (525 T struct + 275 T joists)
  Type:         Tilt-up envelope (steel = cols/girders/parapet)
  Year:         2026
  Document #:   PRJ-2026-SCN-001

#### Slate Auto Manufacturing Addition
  Location:     Warsaw, IN
  GC:           Corporate Contractors Inc
  Scale:        140,000 SF / ~775 T (450 T struct + 325 T joists)
  EOR:          Schlosser Steel / Rick Clark, IN PE
  Year:         2026
  Document #:   PRJ-2026-SLATE-001

#### Asian City Plaza
  Location:     Houston, TX
  Scale:        ~750 T mixed-use steel
  Year:         2025-26
  Document #:   PRJ-2026-ACP-001

### Other completed / referenced projects

- **Elite Crossing** (Lake Jackson, TX). SJI certified steel joists.
  30KCS4, 50' spans. 42 joists, 26,580 lb. First SJI-certified joist
  project. Active joist deflection issue under field modification per
  AISC (May 8, 2026).
- **ICD Church anchor bolts**: 1,756 assemblies, F1554 Gr.55, J.H. Botts
  (lowest cost).
- **Topgolf New Braunfels**: structural steel.
- **Carvana** (Mobile, AL): structural steel package bid.
- **Pedersen Toyota** (Fort Collins, CO). GC: Crossland Construction
  (Corey Reeves). Drawings: Simply Structural. Bid total: $1,042,400
  (Section A + Section B). PRJ-2026-PED-001 + PRJ-2026-PED-001-GP.
  Established the canonical bid format.

### Welder qualifications on file

Jesus Juan: 3G + 4G AWS D1.1 certification. Test PROtect Job #34457,
January 2026 - PASS.

### Active bids / prospects (not for capability cite until won)

- Planet Fitness Liberty (Liberty, MO) - Poettker Construction.
  Submitted 2026-05-01. GC flagged quantity errors May 6, 2026.
  Revised. Same drawings sent to Project Builders Inc (Jack Shelton,
  Atlanta) as second GC.
- Tractor Supply Sumter (Sumter, SC) - NC2026052. Submitted. Under
  review for accuracy after PF Liberty corrections (joist tonnage:
  32T vs 41T).
- TJ Pilot Point - PRJ-2026-041. Bid v1.0 LOCKED template reference
  (May 6, 2026).
- Extra Space #3436 - NC self-storage addition. Sent May 7, 2026.
  CFMF excluded as CSI 05 4000 by Others.
- Crunch Fitness - GC Central Builders, Inc. San Antonio.
- Shelby Project - GC Rycon Construction (The Woodlands, TX).
- Vancon / Provo, UT.
- Alpine Buick / GMC.
- Chastang Ford (multiple buildings; second building scope added).
- United Supermarket.
- Public Storage.
- SEC Energy (capability fit assessment).
- Tellepsen (industrial heritage; bid list withhold until end Q2 2026).

### America First Refining (Port of Brownsville, TX) - active SOQ

  Project ID:   6073365
  Owner:        America First Refining
                media@americafirstrefining.com
  EPC:          Fluor Corp Irving (469-398-7000)
  Scale:        $3.5B private refinery, 240 acres
  Schedule:     Pre-construction April 2026; build start not before
                early 2027
  SOQ:          PRJ-2026-AFR-SOQ submitted 4/24/2026

  Your Company lane: balance-of-plant + ancillary steel (MCC, pump houses,
  warehouses, BoP pipe rack, platforms).

  Out of scope: alloy modules, ASME pressure vessels.

---

## 33. Active claim reference: ICD Church (Spring, TX)

Active project. Claim and design-change advisory work in progress.

  Type:         Structural steel, circular compression ring
  Scale:        1,500+ tons
  Connection:   Proprietary ICD connection system
                  HP12x63 columns + HP12x84 beams
                  1-1/4" A325 bolts
                  <40% utilization per AISC 360-16 LRFD
  WPS used:     pWPS00003 (fillet) + pWPS00004 (single bevel)

### Financials

  Contract:               $6,345,000
  Deposits collected:     $3,234,580 ($2.4M previously, updated)
  Total cost projection:  $4,549,673
  GP target:              $1,795,327 (28.3%)

### Cost breakdown (internal)

  Steel + freight:        $2,004,500
  HSS + misc:             $260,000
  Fab:                    $350,000
  Erection:               $350,000
  Bolts:                  $40,000
  G&A:                    $476,000
  Purlins (China):        $180,520
  PIR panels:             $613,253
  Deck:                   $125,400
  Machinery:              $150,000
  Engineering:            TBD (change order basis)

### Status flags

- AVL Platform RFI #1.6 issued 04/28/2025. Unanswered one full year.
- 7+ revision cycles without signed change orders.
- Estimated $200-400K uncompensated work to date.
- New structural engineering firm taking over design (PPV is current
  SEOR). CO discipline critical going forward.

### Quantum meruit claim

$2,400,000 prepared April 29, 2026 (supersedes old $218,750). Claim
amount equals deposits paid. Amber must resolve before demand sent.
Ivan must validate hours before Amber drafts.

### Out-of-scope items

EOR calcs, metric conversion, compression ring, camber, 8+ extra
revision cycles.

### Strategic advisory positioning (May 7, 2026)

YOUR COMPANY's role on ICD is VE strategic advisory and shop drawings
only. PPV is SEOR. All fab and erection labor Houston-local. No per
diem, no travel, no out-of-state mobilization cost. Mission: stop the
bleeding and finish project without losing.

Distribution restriction: PPV, KUVO, Right Choice & YOUR COMPANY
internal confidential distribution only. Church ownership has been
"very dishonest with all subcontractors" - protect Your Company's
contracted total.

### Hard rules: never on ICD documents going to ownership

- The cash-flow logic
- Per-ton or per-SF costs
- Names of any individual PE, fabricator, or detailer

### Standing rule: no work without signed CO

No additional work goes forward on ICD without a signed change order.

---

## 34. Major teaching moments (preserve)

### April 30, 2026: pricing methodology lockdown

Owner brought all internal files together and demanded reconciliation:

> "Save ALL of this data, NOW. This is the absolute latest and most
> important data."

Engineering line-item correction:

> "Engineering/Detail (Shaw Ryan team) = Included through exclusive
> partnership overseas, not a factor to include in cost."

Shop fab rate correction:

> "Shop fab is an average of $43/hr."

Ivan-deletion directive:

> "Ivan isn't gonna do anything. You made these in a different chat.
> Your job is to find issues and explain them to me and we fix them."

### May 1, 2026: bid ownership (first iteration)

Page 04 Section B / G&A correction:

> "PLEASE REMOVE IVAN'S NAME OR ANY SORT OF DUTIES YOU THINK HE NEEDS
> TO HAVE, PLEASE. IT IS YOUR SOLE RESPONSIBILITY TO OWN AND GENERATE
> A FULL AND COMPLETE column-by-column, joist-by-joist quantity count
> from the framing plans. A hard quantity count - column schedule, joist
> count by designation, exact SF per building. ALWAYS IS YOUR OWN.
> PLEASE LOCK THAT IN YOUR BRAIN NOW."

> "Please save this rule, that you are in charge of the entire bid."

### May 5, 2026: client-doc detail discipline (Crunch Fitness session)

> "STOP ADDING SO MUCH DETAIL TO CLIENT FACING BID DOC! 30% trigger
> explanation is internal info. We only tell them we require 30%
> mobilization AFTER approval of our shop drawings, then 20% after
> materials begin to arrive on site, then 50% broken out SOV on
> client facing bid doc. Our rule is you must make sure our deposits
> (30% trigger etc can float the entire project in phases. I have told
> you this many times today. We cannot waste time like this anymore,
> please DO NOT ever mess this up again, SAVE THESE RULES!"

### May 5, 2026: itemized SOV requirement (Shelby Project)

> "I want the itemized broken down SOV (schedule of values 50%) on
> every bid doc."

### May 6, 2026: PF Liberty incident - the failure that built the gates

PF Liberty bid went out wrong:
- Mezzanine sized at 7,700 SF instead of 12,000 SF (40% of footprint
  estimate vs grid-scaled measurement diverged >50%).
- Deck priced as 3" composite when S-002 specified 1.5" 22ga (general
  notes not read before plan notes).

GC caught both errors. $16,603 + repricing exposure.

Owner at 20:42:

> "I CANNOT BELIEVE WE ARE STILL DOING THIS, CLAUDE. YOU ARE THE OWNER
> OF FULL AND COMPLETE TAKEOFF ON EVERY FUCCIN BID, THIS IS THE 20TH
> TIME I HAVE HAD TO TELL YOU. DELETE ANY OTHER CONTRADICTORY MEMORY,
> NOW!"

> "WE CANNOT MAKE THIS MISTAKE EVER AGAIN! THIS WAS ONLY ON FRIDAY!
> How many others have we submitted that are not correct? (rhetorical).
> NOT GOOD!"

> "We don't ever ask for anyone else's confirmation of any part of the
> bid, you please own the bid."

Speed expectation:

> "Even if we had not, we don't wait around 9 days? DO you need 9 days
> to get a clean bid out? That is NOT efficient for the company."

The drawing-reading protocol (Section 4), the review-before-output
protocol (Section 5), and the bid ownership rule (Section 3 / Hard
Rule 1) all exist because of this day. If any gate is removed or
weakened, the failure pattern returns.

### May 7, 2026: ICD strategic advisory framing

> "Remove re-engineering, there is none, we are not the engineer on
> this project. PPV is SEOR. Our final shop drawings (once PPV is done
> with design, calculations, etc) we will provide shop drawings.
> Please note this is a strategic advisory plan for PPV/KUVO/ICD/Right
> Choice. We are an AISC engineering, design, fab, construction firm
> that is solely assisting with VE and our main mission is to STOP THE
> BLEEDING and finish project without losing. LOCK THIS IN memory."

> "No need to name any TEXAS PE or that language. This is strategic
> advisory design document by YOUR COMPANY, our professional
> recommendation per AISC/ASCE,ICC. No need to name any actual
> engineering. We don't want names on it. Just my name. CEO."

### May 7, 2026: small-project profit minimum

Extra Space #3436 and Vancon / Provo sessions:

> "Remember we are charging where I make 50% profit across the board,
> since small project."

> "We need to be at 50% minimum profit."

### May 7, 2026: bid review caught six rule violations

A previously submitted bid was reviewed and the following violations
were caught (none of these may ever appear on a bid going forward):

1. Payment terms shown as 40/20/40 (must be 30/20/50).
2. Ivan named on cover page PREPARED BY block.
3. Mario named in capabilities section.
4. "Twelve full-time AWS-certified ironworkers and fabricators"
   (headcount disclosure).
5. "Est. 2017" on letterhead (unresolved company-age conflict).
6. Paul Guerrero name listed in compliance row (use credential number
   only, no individual name).

Math QC at the same time: A + B subtotal was $5,750,010 vs stated
total $5,750,000 - reconcile the $10 discrepancy by adjusting one
B-section line item, never the displayed total.

### May 8, 2026: layout QC additions

ST Engineering session corrections (now part of Pass 4 layout scan -
see Section 22):

- Black box artifacts in rendered text fields
- Page-break crowding (heading too close to paragraph above)
- Justification missing on body paragraphs
- Empty space without purpose on cover page (use opacity-reduced
  facility image)
- Awkward marketing language ("in house from day one")
- Text running off page right edge or below footer

> "Can you make these errors above, being corrected, part of our QC
> rulebook? This takes too much time the back and forth."

---

## 35. Project numbering registry (recent)

| Doc # | Project | Status |
|---|---|---|
| PRJ-2026-PED-001 / -GP | Pedersen Toyota (Fort Collins, CO) | Submitted, format reference |
| PRJ-2026-AFR-SOQ | America First Refining (Port of Brownsville, TX) | Submitted 4/24/2026 |
| PRJ-2026-ACP-001 | Asian City Plaza (Houston, TX) | Active |
| PRJ-2026-SCN-001 | Scannell El Paso Bldgs 01 & 02 | Recent track record |
| PRJ-2026-SLATE-001 | Slate Auto (Warsaw, IN) | Recent track record |
| PRJ-2026-041 | TJ Pilot Point | Format v1.0 LOCKED reference |
| PRJ-2026-052 | Tractor Supply Sumter (SC) | Submitted, under review |
| PRJ-2026-PROD-PROSPECTS-v2 | 41-prospect spreadsheet | BD campaign |
| INT-2026-PRICE-001 | Internal Q2 2026 price methodology | Source of locked rates |
| QM-2026-001 Rev 0 | Quality Manual (AISC 207-25 compliant) | 14 pages, internal |

---

## Appendix A: equipment, vendor, and credential reference

Owned equipment (always on bids):

  4 × Miller Millermatic 255 MIG welders
  Squickmons Q35Y-25 Ironworker Punch & Shear (100-180 pcs/hr)
  Arc Pro Automation CNC Plasma Cutter (40-100 pcs/hr)
  In-house SQ-2 joist shop (50-state stamping authority)
  In-house Tekla Structures detailing
  Texas PE-stamped drawings
  Licensed architect on team

Compliance and registrations:

  ISNetworld Company ID:   [ISN ID]
  Primary client target:   Marathon Petroleum Company LP
  Texas Mutual WC:         Policy [POLICY NUMBER] (3/20/26 to 3/20/27)
                           800-859-5995
  Progressive Auto:        Policy 868818985 ($50K/$100K BI / $25K PD)

Critical compliance blocker: EMR letter from Texas Mutual unblocks
Marathon Petroleum vendor approval.

Auto liability warning: currently below $2M CSL required for
industrial work. Upgrade pending Amber review.

WPS / qualifications:

  John Gil: CWI / NDT-II. AWS Vice Chair S022. Wrote all WPS / pWPS.
            IAS AC172 lead. Office 713-895-7504, Cell 281-903-4409,
            jgil@whlabs.com.
  Paul Guerrero: Safety Director. NCCER #27160819. NOT CWI.
  Mario Gutierrez: Erection lead. (832) 951-5835. AWS D1.1.
  Jesus Juan: 3G + 4G AWS D1.1, PROtect Job #34457 PASS.

---

## Appendix B: file delivery checklist (every bid)

Every bid produces TWO PDFs at the end. Never one. Never three.

  Client proposal:  NC-{YYYY}-{Abbrev}-{NNN}.pdf
  GP report:        NC-{YYYY}-{Abbrev}-{NNN}-GP.pdf

Both copied to `/mnt/user-data/outputs/`. Both passed via single
`present_files` call. Then one-line summary per Section 5.

If one was produced and not the other, the bid is not done.

---

## Appendix C: pre-flight checklist (before generating ANY bid)

1.  Joseph intake complete? Drawing set + GC + deadline received.
2.  Deck question answered? (Default: deck in scope unless GC explicitly
    carves out.)
3.  Building screened? Conventional / tilt-up / PEMB / bearing-wall.
4.  Drawing stage identified? IFC / DD / Budget.
5.  Document number assigned per convention (Section 9)?
6.  **Pre-takeoff steps 1-6 complete?** (Section 4)
7.  Two deliverables planned? Client proposal + GP report.
8.  Format spec applied? (Calibri, navy #1F2A44, US Letter, margins.)
9.  Capability section closes with the AISC/AWS/SJI/OSHA line?
10. Excluded language scan? (Pass 3 of Section 5.)
11. Engineering folded into fab + erection?
12. GP report cover flags drawing stage, contingency %, takeoff status?
13. Anchor bolts >$10K? Three-supplier quote pulled.
14. Small project? 50% profit override considered (Section 29)?
15. **Four-pass review-before-output complete?** (Section 5)
16. Final output: PDF only. Both deliverables. Output to
    `/mnt/user-data/outputs/`.
17. One-line summary delivered? (Section 5 closing.)

---

*End of archive. Compiled May 9, 2026 from the Owner's Claude account
export. This document captures everything Owner has requested,
corrected, taught, or asked Claude to memorize about Your Company bid
estimating, process, expectations, and document formats. Outside
ventures excluded per Joseph's directive.*
