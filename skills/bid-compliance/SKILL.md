---
name: bid-compliance
description: >
  26 immutable Tier 1 rules and 18+ compliance scanner patterns.
  Use when generating any client-facing document, reviewing bids,
  or checking content for forbidden items.
triggers:
  - check compliance
  - review against rules
  - scan for violations
  - forbidden items
---

# Bid Compliance (Tier 1 Immutable Rules)

## Forbidden in ALL client-facing documents

### Supplier names (NEVER)
Vulcraft, Nucor, Peyton, J.H. Botts, A&M Nut & Bolt, Service Steel,
Triple-S, Brown Strauss, Atlanta Rod, Canam, Ayamsa, Schuff, Herrick,
Cives. Use generic: "qualified steel suppliers."

### Team names (NEVER)
Ivan, Mario, Paul, Amber, Joseph - no individual names on bids.
Exception: The Owner (CEO signature block only).

### PE names (NEVER)
No specific Professional Engineer names. Use "PE-stamped per
Texas registration" or "Engineer of Record."

### Internal data (NEVER)
- Headcount (12 employees, team size)
- Margin/GP percentages
- Cost-per-ton internal rates
- Cash flow rationale ("deposit covers Phase 1 steel")
- Supplier relationships or pricing

### Dead items (NEVER)
- 40/20/40 payment terms (use 30/20/50)
- Alamo Heights address (use Houston)
- "Est. 2017" without confirmation
- [FORBIDDEN PROJECT] (NOT a Your Company project)
- Red Dot Buildings / PEMB manufacturer language
- "14-16 week" fab lead time (competitor number)

### Format rules (ALWAYS)
- Two PDFs per bid: client proposal + GP report (-GP)
- Engineering folded into rates, never line-itemed
- Deck always in scope (supply + install)
- PDF only output, never .docx
- Literal & never &amp;

## Scanner patterns (automated)
The compliance scanner checks for 30+ regex patterns covering all
forbidden items above. Run check_bid_compliance() on every document
before output.
