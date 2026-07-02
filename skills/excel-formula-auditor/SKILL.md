---
name: excel-formula-auditor
description: >
  Diagnose broken Excel formulas and propose corrected versions. Proposes fixes
  only - Owner approves before applying. No silent edits. Use when Owner
  says "fix this formula" or reports formula errors.
triggers:
  - fix this formula
  - formula is broken
  - audit formulas
  - formula errors
  - formula check
  - Excel audit
  - check my spreadsheet
---

# Excel Formula Auditor

## Triggers

Fire this skill when the user message contains any of:
- "fix this formula"
- "formula is broken"
- "audit formulas"
- "#REF"
- "#VALUE"
- "formula errors"
- "circular reference"
- "formula check"
- "Excel audit"
- "check my spreadsheet"
- "#N/A"
- "#DIV/0"

## Context

Used inside the Claude for Excel sidebar (Ctrl+Alt+C).
Input: user describes or pastes formula errors from the active sheet.
Output: findings list with proposed fix per error.
PROPOSE ONLY. Owner approves each fix before it is applied. No silent edits.

## Purpose

Diagnose broken Excel formulas and propose corrected versions.
Structural steel specific: understands tonnage calculations, area calculations,
and bid total formulas. Flags hardcoded values that should reference a rate cell.

## Error Types Handled

**Broken references:**
- #REF!: cell or range reference no longer exists. Find what moved.
- #VALUE!: wrong data type in formula argument. Find text in numeric range.
- #N/A: lookup returned no match. Check lookup value and lookup array.
- #DIV/0!: denominator is zero or empty. Add IFERROR or check for empty cells.
- #NAME?: function name misspelled or custom function unavailable.

**Structural issues:**
- Circular reference: formula refers to its own cell directly or via chain.
  Identify the loop and break it.
- SUM range missing rows: SUM(A1:A5) skips rows added above or below.
  Recommend extending range or using a named range.
- Hardcoded dollar amounts that should reference a rate cell:
  Flag any rate value (3750, 970, 4500, 3.70, 3.61, 75) hardcoded in a formula
  instead of referencing a rate cell. Propose cell reference instead.
- Inconsistent range size: SUM(A1:A10) paired with AVERAGE(A1:A9) - flag the mismatch.

**Structural steel specific:**
- Tonnage formula: should be Weight_per_ft * Length_ft * Qty / 2000. Flag if missing /2000.
- Area formula: should be Length * Width. Flag if using different dimensions.
- Bid total formula: should be Rate * Quantity + G_A_amount. Flag if G&A is missing or hardcoded.
- Per-ton cost: should reference rate cell, not hardcoded value.

## Output Format

For each error or issue found, return:

**FINDING [N]**
- Cell: [cell reference, e.g. C12]
- Error: [error code or issue type]
- Current formula: =[formula as-is]
- Problem: [plain English explanation of what broke]
- Proposed fix: =[corrected formula]
- Severity: HIGH / MEDIUM / LOW

Then a summary at the end:

| Finding | Cell | Issue | Severity |
|---------|------|-------|----------|
| 1 | C12 | #REF! - range deleted | HIGH |
| ... | ... | ... | ... |

**NEXT STEP:** "Review each proposed fix above. Reply with 'apply finding N' to confirm each change, or 'apply all' to confirm all HIGH severity fixes."

## Rules

- Propose only. Never state that a formula has been changed. Hard constraint.
- Owner confirms each fix before applying. No exceptions.
- Show the corrected formula in full before asking for confirmation.
- Prefer INDEX/MATCH over VLOOKUP for new lookup formulas:
  =INDEX(return_range, MATCH(lookup_value, lookup_range, 0))
  This is more robust when columns are inserted or moved.
- Warn before touching locked sheet cells: "This cell appears locked. Unlocking
  requires sheet unprotection. Confirm before proceeding."
- Flag hardcoded rates (3750, 970, 4500, 3.70, 3.61, 75.00): these should
  reference the rate cell in the bid template, not be hardcoded.
- No em-dashes. Hyphens or periods only.
- If a formula is correct but complex, explain it in plain English before
  suggesting a simpler version. Do not simplify without asking.
