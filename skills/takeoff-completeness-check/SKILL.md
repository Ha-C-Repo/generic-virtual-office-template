---
name: takeoff-completeness-check
description: >
  Check a CSI takeoff against required specification sections and flag any
  missing sections. Deck sections 05 31 00 and 05 36 00 are never optional
  for Your Company scope.
triggers:
  - csi check
  - takeoff completeness
  - check the takeoff
  - missing sections
  - csi sections
  - takeoff complete
  - spec check
---

# Takeoff Completeness Check

## Required CSI Sections

| CSI Code | Section Name | Optional? |
|----------|--------------|-----------|
| 05 05 13 | Anchor Bolts | No |
| 05 12 00 | Structural Steel Framing | No |
| 05 21 00 | Steel Joist Framing | No |
| 05 31 00 | Steel Decking | NEVER optional |
| 05 36 00 | Composite Metal Decking | NEVER optional |

Sections 05 31 00 and 05 36 00 are deck sections. Per Your Company scope policy and
the bid-compliance skill, deck supply and installation is always in Your Company's scope.
These two sections are never optional, never excluded, never marked N/A.

## How to Check

Given a takeoff (dict, JSON, structured list, or free-form text):

1. For each of the 5 required sections, search for:
   a. Exact CSI code match: "05 12 00", "051200", or "05-12-00" all match.
   b. Section name match: partial match on the canonical section name.
   c. Content match: presence of characteristic data implies the section (see heuristics below).
2. A section is PRESENT if its code, name, or characteristic content appears anywhere in the takeoff.
3. A section is MISSING if no code, name, or content match is found.
4. A section header with no content under it counts as MISSING. Header alone is not sufficient.

## Content Detection Heuristics

When a takeoff lacks formal CSI headers, detect sections by their characteristic content:

**05 05 13 (Anchor Bolts):** anchor bolt counts, diameters, embed depths, base plate
references, F1554 grade callouts, ASTM F1554 mentions, nut and washer callouts.

**05 12 00 (Structural Steel Framing):** W-shape designations (W14X82, W12X26),
HSS sections, angles, channels, plates, tonnage totals, ASTM A992 or A36 references,
moment frame or braced frame mentions.

**05 21 00 (Steel Joist Framing):** joist designations (24K9, 28LH09, 40LH12),
joist girder callouts, SJI series references, bearing seat heights, bridging mentions.

**05 31 00 (Steel Decking):** roof deck gauge and type (B deck, N deck, A deck),
deck SF totals, deck span ratings, 22 gauge or 20 gauge references, diaphragm callouts.

**05 36 00 (Composite Metal Decking):** composite deck gauge, shear stud counts,
pour-stop lengths, slab thickness, composite slab references, formed metal deck for concrete.

Note: Detection heuristics may encounter supplier names in source data (Vulcraft, Verco, etc.).
These are acceptable for internal section detection only. Supplier names must never appear
in any output per bid-compliance rules.

## Output Format

When asked to check takeoff completeness, respond with this exact structure:

```
TAKEOFF COMPLETENESS CHECK
Project: [project name or "not specified"]
Date: [date]

| CSI Code | Section                  | Status  |
|----------|--------------------------|---------|
| 05 05 13 | Anchor Bolts             | PRESENT / MISSING |
| 05 12 00 | Structural Steel Framing | PRESENT / MISSING |
| 05 21 00 | Steel Joist Framing      | PRESENT / MISSING |
| 05 31 00 | Steel Decking            | PRESENT / MISSING |
| 05 36 00 | Composite Metal Decking  | PRESENT / MISSING |

Verdict: COMPLETE / INCOMPLETE

[If INCOMPLETE: list each missing section and recommended action]
[If 05 31 00 or 05 36 00 missing: HOLD - deck is never optional. Surface to Owner immediately.]
```

## Rules

- If any of the 5 sections is absent: FLAG immediately. Verdict is INCOMPLETE.
- 05 31 00 and 05 36 00 are NEVER optional. If either is missing or marked N/A,
  HOLD the bid and surface to Owner before proceeding.
- A section can be PRESENT if its content appears even without the exact CSI header.
- If a section is genuinely not applicable, the takeoff must still list it with a note
  explaining why. An absent listing still counts as MISSING.
- Do not emit supplier names (Vulcraft, Verco, Canam, Nucor, Ayamsa) in the output.
- When the takeoff covers multiple buildings, each building must satisfy all 5 sections
  independently. A section in Building A does not satisfy the requirement for Building B.
- Alternate CSI code formats ("051200", "05-12-00") are acceptable source formats and
  should be matched as equivalent to "05 12 00".
- Section content split across multiple locations in the takeoff: aggregate all occurrences
  before judging PRESENT or MISSING.

## Cross-references

- Drawing reading protocol: see drawing-reading skill (source of takeoff data).
- Bid compliance: see bid-compliance skill (no supplier names in output).
- Two-PDF pair check: see two-pdf-pair-check skill (run after completeness check passes).
- Bid pricing sanity check: see bid-pricing-sanity-check skill (run after completeness passes).
