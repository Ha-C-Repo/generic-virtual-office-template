# Drawing Stage Classifier

## Triggers

Fire this skill when the user message contains any of:
- "drawing stage"
- "classify the drawings"
- "what stage are these"
- "ifc drawings"
- "dd drawings"
- "budget drawings"
- "schematic drawings"
- "cd drawings"
- "construction documents"
- "drawing classification"
- "stage of drawings"

## Purpose

Classify a set of structural drawings into the correct design stage.
The stage determines which pricing adder applies per the locked Q2 2026
bid rates.

## Stage Definitions and Adders

### IFC - Issued for Construction
- Definition: Final, signed, stamped drawings. Full structural details,
  connection schedules, anchor bolt plans, and member schedules are complete.
- Adder: 0% (baseline rate, no adder)
- Tell-tale signs: "ISSUED FOR CONSTRUCTION" or "IFC" in title block,
  engineer's seal and signature, revision cloud not present or resolved

### CD - Construction Documents (Near-IFC)
- Definition: 95%+ complete. May have minor open items but all primary
  structure is defined. Engineer of record signed but may not be final stamp.
- Adder: Same as IFC for bidding purposes. Flag if significant open items remain.
- Tell-tale signs: "FOR CONSTRUCTION" or "FOR BID" in title block

### DD - Design Development
- Definition: 50-75% complete. Major structure defined but connections,
  schedules, or secondary members may be incomplete or schematic.
- Adder: +8% on fabrication rate (risk adder for scope uncertainty)
- Tell-tale signs: "DESIGN DEVELOPMENT" or "DD" in title block, member
  sizes shown but connection details absent, "TBD" on schedules

### SD / Schematic
- Definition: 20-40% complete. Framing layout only. Member sizes may
  be preliminary or absent.
- Adder: +15% on fabrication rate. Flag for Owner before bidding.
- Tell-tale signs: "SCHEMATIC" or "SD" or "PRELIMINARY" in title block

### Budget / Conceptual
- Definition: Less than 20% complete. No member sizes or placeholder only.
  Bidding not recommended.
- Adder: N/A - do not price. Provide budget range only with heavy caveat.
- Tell-tale signs: "BUDGET" or "CONCEPTUAL" or "FOR PLANNING" in title block,
  no member designations, building outline only

## Output Format

| Drawing Set | Classified Stage | Adder | Confidence | Notes |
|-------------|-----------------|-------|------------|-------|
| [sheet ref] | [stage]         | [%]   | High/Med/Low | [notes] |

Then:
**Recommended action:** [proceed at baseline / apply adder / flag for Owner / do not price]

## Rules

- If the title block is not visible or legible, classify as Unknown and
  request a clearer image. Do not guess.
- If member sizes are absent, default to DD or Budget - do not assume IFC.
- Flag Budget/SD drawings to Owner before any pricing.
- No em-dashes. Hyphens or periods only.
- Do not fabricate a stage if the evidence is ambiguous. State: "Classification
  uncertain - confirm title block with Joseph or Owner before pricing."
