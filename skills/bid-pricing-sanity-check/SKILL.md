---
name: bid-pricing-sanity-check
description: >
  Validates a generated bid against the locked Q2 2026 rate baseline.
  Flags any line-item rate that diverges more than 3% without an explicit note.
  Run before every bid ships. Live gate between pricing and output.
triggers:
  - sanity check this bid
  - check bid rates
  - validate pricing
  - rate check
  - bid sanity
  - pricing check
  - check the rates
  - does this bid look right
---

# Bid Pricing Sanity Check

## Locked Baseline (Q2 2026, CEO-locked)

| Line Item | Locked Rate | Target GP | Trigger on drift |
|-----------|------------|-----------|-----------------|
| Fabrication | $3,750/ton | 31% | >3% drift |
| Erection | $970/ton | 30% | >3% drift |
| Joists | $4,500/ton | 40% | >3% drift |
| Roof Deck | $[ROOF DECK RATE]/SF | 23% | >3% drift |
| Composite Deck | $[COMPOSITE DECK RATE]/SF | 21% | >3% drift |
| Anchor Rods | $[ANCHOR RATE]/EA | 31% | >3% drift |
| G&A | 7.5% | - | Any change |

## What to check

Given a bid dict or bid JSON, for each line item:

1. Compute effective rate: `total_line_cost / quantity`
2. Compare to locked rate above.
3. If deviation > 3%: FLAG. Do not pass.
4. If deviation <= 3%: PASS.
5. If line item has an explicit note explaining the deviation: PASS with NOTE.

## Output format

```
BID PRICING SANITY CHECK
Bid: [bid name]
Date: [date]

Line Item         Rate Used    Baseline    Deviation   Status
Fabrication       $X,XXX/ton   $3,750/ton  +X.X%       PASS / FLAG
Erection          $XXX/ton     $970/ton    +X.X%       PASS / FLAG
Joists            $X,XXX/ton   $4,500/ton  +X.X%       PASS / FLAG
Roof Deck         $X.XX/SF     $[ROOF DECK RATE]/SF    +X.X%       PASS / FLAG
Composite Deck    $X.XX/SF     $[COMPOSITE DECK RATE]/SF    +X.X%       PASS / FLAG
Anchor Rods       $XX/EA       $[ANCHOR RATE]/EA      +X.X%       PASS / FLAG
G&A               X.X%         7.5%        0.0%        PASS / FLAG

OVERALL: PASS / HOLD FOR REVIEW

[If HOLD: list each flagged item and ask Owner to confirm before proceeding]
```

## Rules

- Never adjust rates to pass the check. Flag and surface.
- A deviation with an approved note (documented in the bid dict) passes.
- Any G&A change, regardless of direction, is flagged. G&A is not adjusted per-bid.
- If a line item is missing from the bid entirely, flag it as MISSING.
- Deck is never optional. If deck is missing, HOLD immediately regardless of notes.
- Do not email or send a bid that has any HOLD items without Owner review.

## Small project override

Projects under $200K: 50% profit override is allowed on all line items.
The sanity check still runs but PASS threshold becomes 50% GP rather than
the line-item targets above. Flag on GP report cover.
