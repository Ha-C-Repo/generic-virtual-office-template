# Ivan Calibration Email - 2026-05-27

**Source:** Email exchange between Cowork-drafted questions (Claude, on
behalf of Joseph) and Ivan L. Martinez (Director of Engineering).
**Status:** Ivan confirmed values. Replaces placeholders previously
marked `TODO IVAN-CONFIRM` in `bridge/bid_sanity_gates.py` patch 04
(2026-05-25T14-09-00Z entry in `_handoff/changelog.md`).
**Authority:** Ivan is the verification gate before bids ship.
These numbers are the canonical estimating reference until Ivan
sends an explicit revision.

---

## 1. Steel Intensity Ranges (lbs/SF) by building type

Format: `low / mid / high`. Gate 2 BLOCKs below `low`, targets `mid`,
warns above `high`.

| Building type | Low | Mid | High | Notes |
|---|---|---|---|---|
| retail_small | 3.5 | 4.5 | 5.5 | |
| retail_big_box | 4.0 | 5.5 | 7.0 | |
| fitness | 5.0 | 6.5 | 8.0 | |
| warehouse | 4.0 | 5.0 | 6.5 | |
| office_multistory | 8.0 | 10.0 | 14.0 | varies w/ spans, mezzanines, cantilevers, architectural |
| dealership | 4.5 | 6.0 | 7.5 | |
| tilt_up | 3.0 | 4.5 | 6.0 | new this round |
| tilt_wall | 3.0 | 4.5 | 6.0 | new this round |
| medical | 5.5 | 7.5 | 10.0 | new this round |
| church | 6.0 | 8.0 | 12.0 | high variance from spans, geometry |
| fire_station | 5.0 | 7.0 | 9.0 | |
| restaurant | 4.0 | 5.5 | 7.0 | |
| gas_station | 3.0 | 4.5 | 6.0 | |
| school | 5.0 | 7.0 | 9.0 | |
| parking_garage | 12.0 | 16.0 | 22.0 | high variance from spans |
| hangar | 5.0 | 7.0 | 10.0 | very large clear spans, LH/DLH joists |
| hotel | 8.0 | 11.0 | 15.0 | |
| mixed_use | 8.0 | 12.0 | 16.0 | high variance from spans, mezzanines |

## 2. Bid Price Ranges ($/SF total) by building type

Format: `floor / mid / ceiling`. Gate floor BLOCKs export. Mid is the
target. Ceiling triggers upper sanity warning.

| Building type | Floor | Mid | Ceiling |
|---|---|---|---|
| retail_small | $14 | $18 | $24 |
| retail_big_box | $12 | $17 | $22 |
| fitness | $16 | $21 | $28 |
| warehouse | $11 | $16 | $22 |
| office_multistory | $28 | $38 | $52 |
| dealership | $18 | $24 | $32 |
| tilt_up | $12 | $18 | $26 | added 2026-05-28 |
| tilt_wall | $12 | $18 | $25 | |
| medical | $20 | $28 | $38 | |
| church | $24 | $35 | $50 | |
| fire_station | $20 | $28 | $40 | added 2026-05-28 |
| restaurant | $16 | $22 | $32 | added 2026-05-28 |
| gas_station | $14 | $20 | $30 | added 2026-05-28 |
| school | $18 | $26 | $36 | |
| parking_garage | $35 | $48 | $70 | |
| hangar | $18 | $28 | $42 | added 2026-05-28 |
| hotel | $30 | $42 | $58 | |
| mixed_use | $22 | $35 | $45 | added 2026-05-28 |

**Note for SP183 B1-type projects (tilt-wall + joist):** Ivan says
recent comparable jobs land $15-$22/SF depending on tonnage, joist
complexity, embeds, erection conditions, finish system.

**Ivan 2026-05-28 note on the six additions:** "These are general
commercial structural package ranges and can vary depending on
erection scope, finish, joists vs WF framing, architectural
exposure, and region."

**Gap status:** All 18 building types now have confirmed floor / mid
/ ceiling. PLACEHOLDER_BENCHMARKS is empty.

## 3. Connection Allowance Defaults (% of structural tonnage)

| Structural system | Default % | Notes |
|---|---|---|
| Tilt wall + bar joists + HSS framing | 8% | |
| Tilt wall + WF beams + bar joists | 10% | |
| Braced frame all-simple | 8% | |
| Moment frame perimeter, simple interior | 12% | |
| Full moment frame | 15% | |
| PEMB primary with conventional secondary | 6% | |
| Standard low-rise commercial | 10% | |

**Exception:** Highly architectural exposed steel or seismic-heavy
projects may exceed these values. Treat above ceiling as warning, not
block.

## 4. Anchor Rod Defaults and Exceptions

Confirmed by Ivan:

- Simple base plate = **4 anchor rods minimum**
- Moment connection base plate = **typically 8 anchor rods**
- Default diameter = **3/4 inch UNO**

**Exceptions Ivan added:**

- Braced-frame columns: **6 to 8 anchor rods** depending on overturning
  and base-plate size. Heavy braced frames and moment frames should
  never default to only 4.
- Large HSS columns, high-seismic zones, crane columns, and
  cantilevered conditions may exceed standard counts.

## 5. Joist Series Expected by Building Type

| Building type | Expected joist tags |
|---|---|
| retail_small | K-series, 18K through 30K depths |
| retail_big_box / warehouse / tilt-wall | K-series + joist girders (48G, 54G, etc.). LH-series on larger spans. |
| medical | WF framing mostly. Joists possible in roof areas and mechanical penthouses. |
| office_multistory | WF + composite deck. Joists uncommon except mechanical roofs. |
| dealership | K-series + joist girders. Long-span showroom framing common. |
| church | LH/DLH joists due to long clear spans + high roof geometry. |
| hangar | LH or DLH series. Very large clear spans. |

If extracted tags don't match expected series for the building type,
the pipeline will FLAG for verification.

## 6. Drawing Stage Adders

| Drawing stage | Adder |
|---|---|
| Schematic / DD | +18% |
| 50% CD | +12% |
| 90% CD | +5% |
| 100% IFC | 0% (baseline) |
| IFB / Bid Set | +3% |

Adder applied to base bid to cover risk of quantities shifting before
construction.

## 7. Standard Scope Checklist by Building Type

Items added on top of the existing default (columns, beams, girders,
bar joists, joist girders, roof deck, base plates, anchors, bracing,
misc angles and plates).

**Tilt-wall projects must auto-flag if missing:**
- Embed plates
- Joist embeds
- Caged ladders
- Roof hatches and surrounds
- Deck closures
- Canopy framing
- Lintels
- Sill angles
- Base plate templates
- Leveling nuts

**Multistory and mezzanine projects must also include:**
- Floor deck
- Stairs and handrails
- Mezzanine framing

**PEMB projects must flag:**
- Secondary framing
- Miscellaneous steel
- Canopies
- Roof screen framing

## 8. Standard Exclusions (canned into client proposal)

These go on every client proposal under "Not in our scope":

- Concrete foundations and anchor setting
- Rebar and embeds by others unless specifically noted
- Field welding inspections and special inspections
- Fireproofing
- Touch-up beyond standard erection touch-up
- Roofing and waterproofing
- Masonry embeds unless shown on structural drawings
- Mechanical, electrical, and plumbing supports unless specifically detailed
- Surveying and layout by others
- Permits and testing unless noted
- Temporary shoring by others
- Deck attachment to PEMB unless specifically included

## 9. Calibration Reference Projects (partial)

Ivan provided one data point this round.

**Genius Kids (PEMB):**
- $35/SF material + fabrication (rate at time of build)
- $7/SF erection (rate at time of build)
- Rate may differ now: at time of build, Your Company did not have in-house
  facilities. Now we do, so this data point is a CEILING reference, not
  a directly applicable rate.

**Ivan 2026-05-28 status update on calibration anchors:**

- Tilt-wall or tilt-up built and paid: **NOT AVAILABLE** in records.
  Do not block waiting on this.
- Medical built and paid: **NOT AVAILABLE** in records.
  Do not block waiting on this.
- Recent WON bids with details: **NOT AVAILABLE** in records.
- Recent LOST bids with reasons: **NOT AVAILABLE**. Historical lost-bid
  feedback is informal and undocumented. Ivan: most informal feedback
  cites pricing competitiveness, relationship, schedule, or scope coverage.
- Weekly bid list xlsx: **INCOMING.** Ivan committed to sharing the
  updated XLSX by 2026-05-29 for live opportunity calibration.
- ICD Church: still under design phase, not usable yet.
- Elite Crossing Retail: mentioned previously, no figures provided.

The pipeline cannot backtest against historical built/paid/won/lost data
because that data does not exist in records. The Ivan-confirmed
floor/mid/ceiling values are the only calibration anchor available
until live opportunity data arrives from the weekly bid list.

---

## Closing comment from Ivan (2026-05-27)

> "I do think the direction here is strong. The biggest improvement
> already visible is moving the system away from generic placeholder
> assumptions and toward actual structural-system-driven logic. The
> anchor rod rules, joist extraction checks, and connection allowance
> automation will eliminate many of the unrealistic outputs immediately."

## Closing comment from Ivan (2026-05-28)

> "The current direction of the pipeline looks very strong. The
> system-based logic additions already appear much more realistic
> than generic placeholder estimating assumptions."

Together these are the verification-gate signal Joseph protocol requires
before any calibration-affecting change reaches production.
