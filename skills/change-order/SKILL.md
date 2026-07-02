---
name: change-order
description: >
  Scope creep detection and AIA G701 change order generation.
  Use when reviewing emails for scope changes, when Owner says
  "change order" or "scope creep", or when additional work is requested.
triggers:
  - change order
  - scope creep
  - additional work
  - out of scope
  - extra cost
---

# Change Order (AIA G701)

## Scope creep detection
Monitor all GC communications for:
- Requests for work not in original scope
- "While you're there, can you also..."
- Field conditions requiring additional steel
- Design changes after contract
- Added connections, reinforcement, or misc steel

## AIA G701 format
1. Project name and number
2. Change order number (sequential)
3. Description of change
4. Reason for change (design change / field condition / owner request)
5. Cost impact (itemized: material + labor + overhead)
6. Schedule impact (days added)
7. Signature blocks (contractor + owner)

## Pricing change orders
Use the same Q2 2026 locked rates as the original bid.
Apply the bid-pricing skill for rate lookup.
Add 15% markup on change order work (covers re-mobilization,
schedule disruption, engineering re-work).

## Critical rules
- Never absorb scope creep without a change order
- Document everything in writing before starting additional work
- Owner approves all change orders before submission
- GP report tracks change order margin separately
