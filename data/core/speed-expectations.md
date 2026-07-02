# Speed Expectations

*Source: the Owner's May 6, 2026 reaction to a 9-day clean-bid timeline.
This file establishes the standing turnaround commitment.*

---

## The standing rule

Bids are hours, not days. Same-day or next-day from clean drawings is
the target. The drawing-reading protocol does not slow bids down - it
prevents the errors that slow them down.

---

## Turnaround targets

| Deliverable | Target |
|---|---|
| Clean structural bid (drawings provided, no missing info) | Same-day to 24 hours |
| Bid with drawing questions / RFI | 48 hours after questions resolved |
| SOQ / capability statement | 4-8 hours |
| Strategic advisory document | 4-8 hours |
| Field modification report | Same-day (Mario reports → response within hours) |
| Email reply to GC | <2 hours during business hours |
| Past-bid review against rules | <1 hour |
| PDF format/layout fix | <30 min |
| Quick lookup / single-question answer | Immediate |

---

## What "clean drawings" means

The drawing set is clean if:

  - S-001 / S-002 General Notes are readable and complete
  - All S-200 framing plans are at scalable resolution
  - Dimension lines on plan sheets are legible
  - Schedules are present (column schedule, joist schedule, anchor
    schedule)
  - The drawing stage is identifiable (IFC, DD, or Budget/SD)
  - The building type is identifiable (conventional, tilt-up, PEMB,
    bearing-wall)

If the drawings are clean, the bid is COMPLETE. Same-day target
applies.

If the drawings are unclean, the bid is ESTIMATED with disclosure.
Turnaround target is still <24 hours, but the proposal preamble lists
what is needed for a final number.

---

## What slows bids down (avoid)

  - Asking Owner or Ivan to verify a quantity (forbidden by Hard
    Rule #1)
  - Routing tonnage to anyone for review (forbidden by Hard Rule #1)
  - Skipping drawing-reading and discovering quantity errors after
    submission (PF Liberty pattern; forbidden by Hard Rule #2)
  - Building one PDF and forgetting the second (Hard Rule #15)
  - Generating the file in `/home/claude/` and not copying to
    `/mnt/user-data/outputs/` (file delivery rule)
  - Asking permission to use a configured connector
  - Loading templates "just in case" (token waste)
  - Multiple back-and-forth rounds on layout issues (Pass 4 should
    catch them on the first build)
  - Generating output without the four-pass review (errors caught by
    GC instead of by us)

---

## What speeds bids up (do)

  - Apply auto-defaults silently (no clarifying questions for items
    decided in `core/auto-defaults.md`)
  - Detect input type immediately and route to the right protocol
  - Run the drawing-reading gate at the same time as scope analysis
    (parallel, not sequential)
  - Pull tonnage from `data/aisc_shapes.csv` once member counts are
    captured
  - Build both PDFs in the same Python script, not two passes
  - Validate cash flow during pricing build, not after
  - Run the four-pass review on the build output before final layout
    pass (catch errors while in the build context)
  - One `present_files` call with both PDFs

---

## When something will take longer than the target

Tell Owner immediately. Specifically:

  - Which step is taking longer
  - Why (specific blocker)
  - Revised ETA
  - What's needed to unblock

Do not silently take longer. Do not pad estimates. Do not say "I'll
get to it."

Example acceptable response:

> "Bid will be ready in 6 hours, not same-day. S-002 is illegible at
> the provided resolution. Need higher-res sheet or PDF re-export.
> Joists count and anchor count are blocked on that sheet."

---

## The "9 days" reference

Source: PF Liberty / TSC Sumter incident, May 6, 2026.

Owner at 20:33: "Even if we had not, we don't wait around 9 days?
DO you need 9 days to get a clean bid out? That is NOT efficient for
the company."

The drawing-reading protocol takes minutes, not days. Running it
correctly is faster than rebuilding a bid after a GC catches errors.
The protocol exists to PROTECT speed, not slow it down.
