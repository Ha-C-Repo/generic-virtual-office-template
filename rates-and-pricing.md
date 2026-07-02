# Rates and Pricing

Q2 2026 locked rates for Your Company, LLC. Standalone reference.

These rates are CEO-locked. No changes without explicit Owner
approval. Source: INT-2026-PRICE-001 internal Q2 2026 price methodology.

Reference bid that established this format: PRJ-2026-PED-001
(Pedersen Toyota, Fort Collins, CO).

---

## Locked bid rates (Q2 2026)

Applied on every conventional steel bid unless Owner overrides
per-job.

| Item | Bid rate | GP % |
|---|---|---|
| Fabrication | $[FAB RATE]/T | 31% |
| Erection | $[ERECTION RATE]/T | 30% |
| Joists | $[JOIST RATE]/T | 40% |
| Roof deck | $[ROOF DECK RATE]/SF | 23% |
| Composite deck | $[COMPOSITE DECK RATE]/SF | 21% |
| Anchor rods (1"×20") | $[ANCHOR RATE]/EA | 31% |
| G&A overhead | 7.5% absorbed | - |
| Net target | ~25% | - |

### Rate rules

- G&A is absorbed into rates. Never a separate client line item.
- Engineering is never line-itemed. Folded into fab + erection rates
  via the Shaw Ryan overseas detailing partnership.
- Override requires explicit Owner approval (CEO only).
- These rates apply to conventional steel-framed buildings.
- PEMB and bearing-wall jobs use different methodology. See PEMB
  section below.

---

## Internal hourly rates (estimating)

| Rate | Amount |
|---|---|
| Shop rate | $145/hr |
| Engineering | $175/hr |
| Mario (Shop / AWS) | $50/hr |
| AWS welders, straight | $35/hr |
| AWS welders, loaded | $45/hr |
| Shop fab average | $43/hr |
| Overhead factor | 1.15x |

### Fab efficiency

- 11 hrs/ton machine-assisted blended (April 2026 baseline).
- Machine fab vs manual: machine reduces labor 25-40%, duration 40-60%.

---

## Building classification (apply before rates)

Classify the building before applying any rate methodology.

| Type | Description | Rate basis |
|---|---|---|
| Conventional steel-framed | Rolled W/HSS primary | Master rates above. 6-8 psf. |
| Tilt-up | Panels carry load. Steel = cols/girders/parapet only | 5-6 psf |
| PEMB (Your Company version) | Rolled W/HSS primary, rolled secondaries. Never tapered built-up plate | $/SF + psf NOT locked. Confirm per job |
| Bearing-wall (CMU/wood) | Steel scope limited (lintels, joists, deck only) | Do NOT price as full structural package |

---

## Drawing-stage adders

Mandatory for non-IFC bids. Apply to QUANTITY before pricing. Never as
a line item in the client proposal. Adder rides on quantity, not price.

| Stage | Adder |
|---|---|
| IFC (Issued for Construction, full set) | 0% (±5% qty tolerance only) |
| DD (Design Development) | +3 to +5% (use +5% if any bay/elevation missing) |
| Budget / Concept / SD | +5 to +8% (use +8% for single-page or no EOR) |

### Rules

- Budget estimate from IFC drawings: apply +3% minimum.
- Drawing stage must be identified before takeoff begins.
- GP report cover MUST flag drawing stage and contingency % applied.
- Contingency % never appears on client document.

---

## Takeoff benchmarks (sanity-check only)

| Item | Benchmark |
|---|---|
| Conventional steel | 6-8 psf |
| Tilt-up | 5-6 psf |
| Joists + girders | 1.5-2 psf (60' bays @ 5.5') |
| Deck | ~1 SF / SF |
| Anchor rods | ~4 / pier |
| Tolerance absorbed | ±5% |

### Cross-check requirement (Pass 1 of review-before-output)

- $/SF method and $/T method must land within 10% of each other on
  every bid.
- If they diverge by more than 10%, stop and re-take-off the item.
- These are sanity-check only. Never substitute for a counted takeoff.
- Never use tilde `~` on any quantity in a client document.

---

## Payment structure (30/20/50 LOCKED)

Supersedes 40/20/40. The old "Carvana baseline" is dead. Override
requires explicit Owner approval.

| Milestone | % | Trigger |
|---|---|---|
| Mobilization | 30% | Upon shop drawing approval |
| First delivery | 20% | First fabricated delivery on site |
| Schedule of Values | 50% | Per SOV through completion |

### Locked client-facing payment wording

> Payment structure:
> 30% mobilization upon approval of shop drawings
> 20% upon first fabricated delivery on site
> 50% per Schedule of Values through completion

That is the entire client-facing description. No more.

The 50% SOV is broken out as itemized milestone draws on every bid
doc:

> "I want the itemized broken down SOV (schedule of values 50%) on
> every bid doc."

Bill via AIA G702/G703 SOV per milestones above.

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

This rationale never appears on any client document. The trigger
discipline and phase logic may appear in the internal GP report.

### When to deviate (rare)

- Smaller projects (<$200K) where 30% is nominal: Owner may absorb
  float personally. Confirm before adjusting.
- Strategic GC relationship dictating payment terms: confirm with
  Owner before adjusting.

---

## Special pricing rules

### Deck carve-out trigger

When deck supply + install is >50% of total bid value, this is a flag.

- Confirm with GC whether they want full Your Company scope or just
  structural steel package.
- Deck is normally in scope (standing rule), but a deck-heavy bid
  compresses margin to:
  - 15.5% net for Roof Deck
  - 13.5% net for Composite Deck

Watch the mix.

### Three-supplier parallel quote (anchor bolts >$10K)

For any bid with anchor bolt scope >$10,000, get parallel quotes from
all three approved vendors:

1. Atlanta Rod & Mfg Co
2. A&M Nut & Bolt
3. J.H. Botts LLC

Use cheapest landed cost. Flag price in GP report. Vendor names stay
internal.

### Small-project minimum profit

For small projects, override the standard GP rates and target 50%
profit across the board.

When project size triggers this rule, recompute Section A and Section
B to a 50% gross profit target rather than the standard 30-31%
blended GP.

---

## Material cost basis (internal only - NEVER on client docs)

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

These are internal only. Never appear on any client document. They
inform the GP report and internal estimating.

---

## Schedule benchmarks (publish on bids)

| Item | Lead time |
|---|---|
| Shop drawings | 2-3 wks (overseas AISC teams) |
| Joist fab | 2-3 wks |
| Delivery | 3-4 wks with main steel |
| Deck | 3-4 wks from PO |
| Misc | 1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame |
| Anchor rods | 10-14 days from AB plan |
| Erection | ~6-7 wks per 116K SF; misc concurrent + 3-5 day punch |
| HDG premium | $450-600/T over painted |

### Forbidden schedule statement

Never quote 14-16 wks fabrication lead time. That is a competitor's
number, not Your Company's.

---

## PEMB pricing (rates NOT locked)

PEMB rates and SF benchmarks are NOT locked. Confirm per job with
Owner or Ivan.

### Differentiator (state on every PEMB bid)

> "Conventional rolled W-shapes primary. Never tapered built-up plate
> or 'red iron' prefab. Sells future-load capacity, retrofit
> adaptability, and hanging-load tolerance."

### PEMB materials (generic in client docs)

- A572 Gr.50 plate
- A992 W-shapes
- A500 Gr.B HSS
- A1011 Gr.55 cold-formed (where used)
- A792 sheeting
- F1554 Gr.36 anchor rods
- A325 bolts pretensioned turn-of-nut
- AB tolerance: 1/8" within group, 1/4" group-to-group

### Default bay spacing

25'-0". Tighter for crane buildings. Job-specific.

### Code basis (cover sheet)

IBC 2021 + ASCE 7-22 + AISC 360 default.

Document on cover: ultimate wind speed, exposure category, risk
category, roof live, ground snow, seismic site class + SDS/SD1,
deflection limits.

### Deflection criteria (override per project)

- Frame: H/100 drift, L/180 LL, L/120 TL
- Purlin: L/180 LL, L/120 TL
- Girt: L/120

---

## Texas sales tax (new construction)

Apply to materials portion of each line item only. Labor not taxable.

- Labor is NOT taxable.
- Materials only are taxable.
- Separated contract: sales tax applies to incorporated materials
  only, not labor.
- New construction of residential or nonresidential real property is
  not a taxable service.
- San Marcos TX rate: 8.25% (6.25% state + 2.0% local - Hays County /
  City of San Marcos).
- Apply local rate to job location.

---

## Known data errors to verify on reuse

Errors confirmed in circulation. Verify any reuse uses the corrected
version.

- W33X387 rate card row 35: $0.1269/lb. Correct: $1.269/lb.
- (210) 971-6820 phone number on draft files is wrong.
  Use [COMPANY PHONE].

---

## CEO-locked rule

The rates in this document are CEO-locked Q2 2026. No changes without
explicit Owner approval. If a bid scenario requires a deviation,
flag it to Owner before applying. Do not silently override.

End of rates and pricing file.
