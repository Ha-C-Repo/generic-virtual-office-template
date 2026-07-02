# SF sourcing and estimate accuracy - standard (2026-06-15)

Gross SF is the controlling input on a calibration-band estimate:
`structural_tons = SF x lb_per_sf / 2000`, and the $/SF gate is `base / SF`.
A wrong SF scales the entire bid. Treat SF as the highest-risk number on the job.

## SF sourcing hierarchy (use the highest available, record which one)
1. STATED on the set - the architectural code-data / area-tabulation block or the
   G-series cover sheet states gross building area. CONFIDENCE: HIGH. Cite the sheet.
   NOTE: a structural-only subset (e.g. an "Extracted pages ... structural" PDF)
   usually does NOT carry this. "Building area" inside a general note (for example
   "field density tests per 3,000 SF of building area") is NOT a gross-area figure -
   do not harvest it. Verified false-positive source on the 2026-06-15 batch.
3. GC-confirmed - the GC states the gross SF in writing. CONFIDENCE: HIGH.
4. MEASURED from the framing plan - sum the overall gridline dimensions against the
   title-block scale (Bluebeam/PlanSwift, or a scale-calibrated read). Single clean
   rectangle only; do not eyeball a multi-wing or multi-building footprint.
   CONFIDENCE: MED.
5. PROTOTYPE / ASSUMED - national-brand prototype or a representative footprint.
   CONFIDENCE: LOW. Always paired with an SF-confirmation RFI to the GC.

Multi-building or multi-wing jobs (federal complexes, multi-school packages,
2-story schools): never collapse to one eyeballed footprint. Get the area per
building from the GC or the full set; until then it is LOW.

## Confidence rubric (tag every estimate)
- HIGH: SF stated on the set or GC-confirmed.
- MED: SF measured from a scaled plan (single building).
- LOW: SF prototype/assumed, or multi-building without per-building areas.
LOW-SF estimates are ROM only and carry a stated contingency band; surface to
Ivan/Owner for a contingency decision (Tier 2). Do not silently bury the risk.

## The real accuracy jump - measured member takeoff
SF x psf is a band, not a takeoff. To move from ROM to bid-grade, replace the
band tonnage with a measured member takeoff: extract the column, beam, and joist
schedules and the framing-plan marks (cowork-takeoff, ZZ Takeoff, PlanSwift, or
Tekla when a model exists), look up weights through `bridge/aisc_validator.py`
(2,299 shapes - never LLM math), and sum actual tonnage. This also makes the
connection allowance and joist tonnage real instead of typical. Confidence per
extracted item: high/medium/low; low items are flagged for human check, never
passed silently into a price.

## Pre-estimate drawing-completeness gate
Before pricing, confirm: a full structural set is present (all framing plans,
schedules, general notes), the title block stage is legible, and the set is not
stamped incomplete/review-only. If incomplete (e.g. 68 Lovett Fusion, stamped
DRAWINGS INCOMPLETE), the estimate is inherently unreliable - flag it, widen the
contingency, and do not submit until a complete set and a measured takeoff are in
hand.

## Calibration feedback loop
Feed real data back into `data/calibration/ivan_confirmed_2026Q2.json`: Ivan's
weekly bid-list XLSX, won/lost $/SF, and completed-job tonnages (ICD Church,
Elite Crossing, Topgolf, Carvana). Track estimate -> Ivan-verified -> awarded
deltas per building type to refine the psf bands over time.
