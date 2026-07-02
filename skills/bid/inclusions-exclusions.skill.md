---
name: inclusions-exclusions
version: 1.0.0
inputs:
  - requirement-register.json
outputs:
  - inclusions-exclusions.json
mcp_connectors:
  - filesystem
voice: owner
schema: data/schemas/inclusions-exclusions.schema.json
---

# inclusions-exclusions

## Purpose

Derive the client-facing Inclusions and Exclusions list from the
Requirement Register. Strict scrubbing for Your Company voice and hard rules.

## Inputs

`requirement-register.json`.

## Procedure (Sequential Thinking)

1. Filter requirements by category:
   - `Inclusion` = category=Direct or category=ContingencyPrelim
   - `Exclusion` = category=Excluded
   - Subcontractor rows skipped (not Your Company scope, not Your Company
     exclusion either).
2. Rewrite each requirement as a clean client-facing sentence. Strip:
   - Supplier names (Vulcraft, Canam, Nucor, Ayamsa, and any caught by
     bid-output-scrubber).
   - Internal cost language ($/ton, hr/ton, markup notes).
   - Precedent project names.
   - Em-dashes. Use periods or hyphens.
   - "Great question" or any filler-opener language.
   - Three-adjective lists.
3. Enforce required Inclusions even if not derived from tender:
   - "Deck supply and installation."
   - "Engineering and detailing folded into fabrication and erection rates."
4. Group by discipline. Structural first.
5. Assign `list_id` as `IE-NNNN` zero-padded sequential.
6. Write `inclusions-exclusions.json` conforming to schema.

## Output structure

```
{
  "inclusions": [
    { "list_id": "IE-0001", "category": "Inclusion", "discipline": "Structural",
      "text": "Deck supply and installation.", "derived_from_req_ids": [] }
  ],
  "exclusions": [
    { "list_id": "IE-0050", "category": "Exclusion", "discipline": "MEP",
      "text": "Electrical conduit and wiring.", "derived_from_req_ids": ["REQ-0123"] }
  ]
}
```

## Hard rules respected

- Deck supply and install always in Inclusions.
- Engineering never line-itemed.
- No supplier names.
- No precedent project names.
- No em-dashes.
