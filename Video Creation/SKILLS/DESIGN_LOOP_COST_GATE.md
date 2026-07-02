# DESIGN LOOP + COST GATE + CRITIC PASS

Applies to VISUAL output only: renders, video clips, proposal and GP layout
polish, brand graphics, studio deliverables. Hard boundary: never bid
numbers, tonnage, connections, or rates. Those are deterministic
(bridge/aisc_validator.py, bridge/bid_rates.py) and are never "improved" by
iteration. Source pattern: research/fable5-use-cases/SUMMARY.md items 3 and 5.

## 1. Cost gate (mandatory before any PAID generation)

Before any Runway, gpt-image-1, Gemini image, or other paid API call:

1. Quote the plan: model, quantity of generations, resolution/duration, and
   a rough dollar cost.
2. Wait for an explicit go from Joseph or Owner. No go, no spend.
3. Batch the plan. One approval covers the stated batch, not open-ended
   regeneration. A changed plan means a new quote.

Exception: zero-cost local work (frame extraction, ffmpeg stitching, layout
passes) needs no gate.

## 2. Design loop (iterative self-scoring, visual only)

When polishing a visual across passes:

- Treat the previous accepted pass as a score of 100.
- The new pass must reach 120 against the brief: composition, brand
  compliance, artifact count, legibility. Keep the change only if it is
  obviously better, not merely different.
- Log each pass in the project folder (pass number, what changed, kept or
  reverted, one-line reason). Stop after 3 passes without a keep; escalate
  to Joseph instead of burning spend.

## 3. Critic pass (before output reaches a human)

Run a VirtualOwner-style critique against every candidate deliverable
before presenting it:

- Anti-AI laws from SKILLS/ANTI_AI.md: artifact scan, hands, text, physics.
- Brand: correct style system (Your Company Style 01 or Pinnacle Style 02,
  never blended), logo from approved masters only, no supplier names, no
  PEMB language, no em-dashes in any on-screen copy.
- Brief fit: does it do the one job the brief states?

Weak output gets one loop pass (section 2) or gets flagged, it does not get
presented as done. Owner signs off before any public release.
