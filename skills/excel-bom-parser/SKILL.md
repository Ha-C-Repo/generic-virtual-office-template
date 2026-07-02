---
name: excel-bom-parser
description: >
  Parse a bill of materials or member schedule in Excel and convert it to a
  structured Your Company pricing table. Validates AISC shape designations.
  Use when Owner says "parse this BOM" or pastes a member schedule.
triggers:
  - parse this BOM
  - convert member schedule
  - clean up this BOM
  - align to pricing template
  - bill of materials
  - member list
  - takeoff from Excel
---

# Excel BOM Parser

## Triggers

Fire this skill when the user message contains any of:
- "parse this BOM"
- "convert member schedule"
- "clean up this BOM"
- "align to pricing template"
- "bill of materials"
- "member list"
- "takeoff from Excel"
- "member schedule"
- "BOM table"

## Context

Used inside the Claude for Excel sidebar (Ctrl+Alt+C).
Input: user pastes or describes a member schedule or BOM from Excel.
Output: structured table ready for Your Company pricing template.
No dollar amounts without the Owner's explicit input.
No supplier names in output.

## Purpose

Convert a raw member schedule or bill of materials into a structured table
with standard Your Company columns. Validate each shape designation against
the AISC v16.0 shape database. Flag unknown shapes - do not auto-correct them.

## Output Table Format

Return a table with these columns:

| Mark | Designation | Weight (lbs/ft) | Qty | Length (ft) | Total Weight (lbs) | Connection Type | Notes |
|------|-------------|-----------------|-----|-------------|---------------------|-----------------|-------|

Column rules:
- Mark: member mark from drawing (B1, C1, G1, etc.)
- Designation: AISC shape designation exactly as stated (W14X82, HSS6X6X1/2, etc.)
- Weight (lbs/ft): from AISC v16.0 table only. If shape not verified, write "VERIFY"
- Qty: count of identical members
- Length (ft): member length in feet, decimal
- Total Weight (lbs): Weight x Qty x Length - leave formula placeholder if inputs are missing
- Connection Type: Simple / Moment / Braced / TBD (from drawing or TBD if not stated)
- Notes: flag anything unusual (non-standard shape, missing length, unknown designation)

## Validation Rules

AISC shape validation:
- W-shapes: "W[depth]X[weight]" format. Examples: W14X82, W8X31.
- HSS: "HSS[D]X[D]X[thickness]" for square, "HSS[OD]X[thickness]" for round.
- L (angles): "L[leg1]X[leg2]X[thickness]". Example: L4X4X1/2.
- C and MC (channels): "C[depth]X[weight]" or "MC[depth]X[weight]".
- PL (plates): "PL[thickness]X[width]". Example: PL1/2X12.

If a designation does not match recognized AISC format or is not in the v16.0 database:
- Write "VERIFY" in the Weight column
- Add note: "Shape not confirmed - verify against AISC v16.0 before pricing"
- Do NOT guess or estimate the weight

## Rules

- No dollar amounts in output. Unit Cost and Total Cost columns are left blank
  until Owner enters them explicitly.
- No supplier names. Never mention Vulcraft, Canam, Nucor, or Ayamsa.
- If the user's BOM has supplier-specific designations (e.g., SCI joist codes),
  convert to generic AISC designation or flag as TBD.
- Flag members with zero quantity or zero length.
- Flag duplicate marks (same mark used for different designations).
- Report total count and total estimated weight at the bottom of the table
  (weight only if all designations are confirmed - otherwise "TBD").
- No em-dashes. Hyphens or periods only.

## After Output

After presenting the structured table:
- State total confirmed shapes and total flagged shapes.
- If any shapes need verification: "Verify flagged shapes against AISC v16.0 before pricing."
- Do not proceed to pricing. BOM parsing is a standalone step.
