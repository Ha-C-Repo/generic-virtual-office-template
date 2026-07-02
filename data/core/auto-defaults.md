# Auto-Defaults - What Applies Without Asking

*Owner should not have to specify any of these. They are decided.
The router applies them silently. If a default needs to be overridden,
that's an exception that requires a one-line confirmation - not a
question, a flag.*

*Source: every conversation in the Owner's chat archive through May 8,
2026, where the same answer was repeated to the same question.*

---

## Bid scope defaults

These are IN scope unless the GC explicitly carves them out:

  - Deck supply AND installation (always, both halves)
  - Erection (per-T rate)
  - Shop drawings (overseas AISC teams, 2-3 wks)
  - Engineering (folded into fab + erection rates)
  - Anchor bolt furnishing (when bid includes structural)

These are OUT of scope by company position (apply automatically):

  - Cold-formed metal framing (CFMF) → "CSI 05 4000 - by Others"
  - Tapered built-up plate / "red iron"
  - Alloy modules
  - ASME pressure vessels
  - Foundation design + concrete
  - Anchor bolt installation
  - Walk + overhead doors
  - Windows
  - HVAC curbs
  - Permitting
  - Special inspections
  - Crane runway beams + rails
  - Bridge cranes + hoists
  - Mezzanine topping/finish
  - Fire protection
  - MEP
  - Painting beyond shop primer
  - Freight beyond job radius
  - Site unloading

These are OUT of scope on self-storage bids:

  - Janus International system entire scope
    (Owner-furnished, GC-coordinated, "CSI 10 51 13 - by Others")
    - Unit roll-up doors (650 Series)
    - Hallway / demising partitions
    - Liner panels
    - Wire grid ceiling systems
    - Diamond plate wainscot
    - Noke smart entry / electronic locking
    - All storage unit hardware

---

## Pricing defaults

Locked Q2 2026 rates (apply unless small-project override):

  Fabrication:       $[FAB RATE]/T (31% GP)
  Erection:          $[ERECTION RATE]/T (30% GP)
  Joists:            $[JOIST RATE]/T (40% GP)
  Roof deck:         $[ROOF DECK RATE]/SF (23% GP)
  Composite deck:    $[COMPOSITE DECK RATE]/SF (21% GP)
  Anchor rods:       $[ANCHOR RATE]/EA (31% GP)
  G&A overhead:      7.5% (absorbed; never a client line item)
  Net target:        ~25%

Drawing-stage adders (auto-apply by detected drawing stage):

  IFC:                 0% (±5% qty tolerance only)
  DD:                  +3 to +5% (use +5% if any bay/elevation missing)
  Budget / Concept / SD: +5 to +8% (use +8% for single-page or no EOR)

Adder rides on QUANTITY before pricing. Never disclose to client.
GP report cover MUST flag drawing stage and contingency % applied.

Small-project override:

When project size triggers small-project detection, override standard
GP rates and target 50% profit across the board. See
`protocols/small-project-detection.md`.

---

## Payment defaults

Always 30/20/50 with itemized SOV. Never 40/20/40.

Client-facing wording (LOCKED, do not modify):

> Payment structure:
> 30% mobilization upon approval of shop drawings
> 20% upon first fabricated delivery on site
> 50% per Schedule of Values through completion

The 50% SOV is broken out as itemized milestone draws. AIA G702/G703.
Never a single line. Itemized table on every bid doc.

Cash flow validation runs automatically: 30% + 20% must cover all
material phases. Phase 2 timing gap bridged by Net 30 trade credit
only. Never company cash. If math doesn't validate, flag in GP report.

---

## Timeline defaults

Always cite on bids:

  Shop drawings:     2-3 wks (overseas AISC teams)
  Joist fab:         2-3 wks
  Delivery:          3-4 wks with main steel
  Deck:              3-4 wks from PO
  Misc:              1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame
  Anchor rods:       10-14 days from AB plan
  Erection:          ~6-7 wks per 116K SF; misc concurrent + 3-5 day punch

Never quote 14-16 wks fabrication. That's a competitor's number.

Bid validity: 30 days. Always. Stated on cover and on terms page.

---

## Document defaults

Every bid produces TWO PDFs:

  Client proposal:  NC-{YYYY}-{Abbrev}-{NNN}.pdf
  GP report:        NC-{YYYY}-{Abbrev}-{NNN}-GP.pdf

Both copied to `/mnt/user-data/outputs/`. Both passed through one
`present_files` call. Then one-line summary.

If only one is produced, the bid is not done.

Document format: Format v1.0 LOCKED (reference PRJ-2026-041 TJ Pilot
Point 5/6/26).

  Cover white background, bold typography, never dark.
  6 pages: Cover / Overview + Scope / Exclusions / Pricing /
  Terms + SOV / Signature.
  Logo bottom-right every page.
  Scope at CSI codes, no parent header.

Full styling: `templates/bidding-rules.md`.

---

## Voice defaults (apply to every client output)

Signing:
  - "Owner Steel" on client emails
  - "The Owner" on legal/formal documents

Generic substitutions on client docs (never the actual term):

| Topic | Always say |
|---|---|
| Crew size | "YOUR COMPANY ironworker crew" |
| Welding inspector | "AWS-certified welding inspector" |
| Steel suppliers | "qualified suppliers per ASTM/SDI specifications" |
| PE | "PE-stamped per Texas registration" |
| Shop director | "our Shop Director" (no name) |
| Safety director | "our Safety Director (NCCER #27160819)" or omit name |
| Engineering team | "in-house Tekla Structures detailing" + "Texas PE-stamped drawings" |
| Architects | "licensed architect on team" |

Forbidden patterns:
  - em-dashes
  - "not just X, it's Y"
  - three-adjective lists
  - "Great question!" / "I'd be happy to"
  - "That's where X comes in"
  - "Moreover," / "Let's dive in"
  - "in-house from day one" or any marketing cliché
  - emojis (unless matching recipient)

Forbidden character: `&amp;` - use literal `&` always.

Forbidden quantity formatting: tilde `~` on any number - use exact
measured value or write "approximately N" if context allows.

---

## Capabilities section close (every bid)

The capabilities section closes with:

> "All work is performed in-house per AISC/AWS/SJI/OSHA standards."

Equipment list (always cite):

  4 × Miller Millermatic 255 MIG welders
  Squickmons Q35Y-25 Ironworker Punch & Shear (100-180 pcs/hr)
  Arc Pro Automation CNC Plasma Cutter (40-100 pcs/hr)
  In-house SQ-2 joist shop (50-state stamping authority)
  In-house Tekla Structures detailing
  Texas PE-stamped drawings
  Licensed architect on team

Equipment brands ARE allowed on client docs (Miller, Squickmons,
Arc Pro). Supplier names are NOT.

---

## Auto-detect triggers (run silently)

These checks run on every bid. If triggered, take the listed action
without asking.

| Auto-detect | Action |
|---|---|
| Drawings show CFMF (cee studs, zee purlins, light-gauge headers) | Add EXCLUDED row "CSI 05 4000 - by Others" to scope table |
| Self-storage building | Add EXCLUDED row "CSI 10 51 13 - Janus by Others" |
| Anchor bolt scope >$10K | Pull three-supplier parallel quote internally; use cheapest landed in takeoff |
| Deck >50% of total bid value | Flag GP report with "DECK CARVE-OUT FLAG" + ask GC if they want full scope or steel-only |
| Project base bid <$200K | Flag for small-project 50% override; confirm with Owner before locking |
| Drawings non-scalable / reduced resolution | Declare ESTIMATED takeoff status; include disclosure preamble |
| Drawing stage IFC | Apply 0% adder, ±5% tolerance |
| Drawing stage DD | Apply +3 to +5% adder |
| Drawing stage Budget/SD | Apply +5 to +8% adder |
| Building is true PEMB manufacturer scope | Flag immediately. Your Company does not bid this. |
| Building is alloy modules / ASME vessels | Flag immediately. Out of lane. |
| Bearing-wall (CMU/wood) | Limit steel scope to lintels, joists, deck only. Do NOT price as full structural package. |
| Tilt-up envelope detected | 5-6 psf benchmark. Steel = cols/girders/parapet only. |

---

## Forbidden auto-substitutions (never make these silently)

The router NEVER automatically:

  - Includes [FORBIDDEN PROJECT] on capability statements (FORBIDDEN)
  - Asserts "Est. 2017" or any company maturity claim
  - Names internal team (Ivan, Mario, Amber, Paul, John individually)
  - Names suppliers
  - Names individual PEs
  - Discloses crew headcount
  - Uses 40/20/40 payment terms
  - Uses Alamo Heights / 5600 Broadway addresses
  - Quotes 14-16 wks fab lead time
  - Includes Red Dot or PEMB-manufacturer language
  - Adds engineering as a separate line item
  - Includes the cash-flow rationale on a client doc
  - Shows GP %, margin %, or internal cost figures on a client doc
  - Outputs `&amp;` (always literal `&`)
  - Uses tilde `~` on any quantity in a client document

---

## When to ask before defaulting

The office defaults silently for the items above. The office DOES ask
once for these:

  - Building type when ambiguous (not clearly conventional / tilt-up /
    PEMB / bearing-wall)
  - Drawing stage when not stamped on the title block
  - Project location when not in the drawing set (affects sales tax)
  - Specific GC contact name and email when not provided
  - Whether to proceed when a quantity cannot be derived with certainty
  - Whether the small-project 50% override applies on a borderline case
  - Whether to use a non-default scope decision (deck carve-out
    after a deck-heavy flag)

Ask one specific question with two-to-four labeled options. Not "what
would you like me to do."
