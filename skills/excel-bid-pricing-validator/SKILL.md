---
name: excel-bid-pricing-validator
description: >
  Read-only validation of bid pricing in Excel against locked Q2 2026 rates.
  Flags rate divergences over 3%, wrong payment terms, supplier name leaks,
  and scope issues. Use when Owner says "validate pricing" or "rate check".
triggers:
  - validate pricing
  - check bid rates
  - sanity check this sheet
  - rate check
  - pricing check
  - validate this bid
  - check pricing
  - bid sanity
---

# Excel Bid Pricing Validator

## Triggers

Fire this skill when the user message contains any of:
- "validate pricing"
- "check bid rates"
- "sanity check this sheet"
- "rate check"
- "pricing check"
- "validate this bid"
- "check pricing"
- "bid sanity"

## Context

Used inside the Claude for Excel sidebar (Ctrl+Alt+C).
Input: user describes or pastes pricing rows from the active workbook.
Output: validation report with PASS/WARN/FAIL per check.
READ-ONLY. This skill never modifies cells. No exceptions.

## Purpose

Compare active workbook pricing against the locked Q2 2026 rate baseline.
Flag divergences above 3% without an explanatory note. Confirm payment terms,
GP margins, drawing-stage adders, and scope completeness.

## Locked Rate Baseline

These are the only rates this skill validates against:

| Item | Rate | Unit |
|------|------|------|
| Structural steel fabrication | $3,750 | per ton |
| Steel erection | $970 | per ton |
| Steel joists | $4,500 | per ton |
| Roof deck | $3.70 | per SF |
| Composite deck | $3.61 | per SF |
| Anchor rods (1" x 20") | $75 | each |
| G&A overhead | 7.5% | absorbed |

## Validation Checks

Run all checks. Report each with PASS / WARN / FAIL:

**Check 1 - Rate Accuracy**
For each pricing line item: compare the stated rate to the locked baseline.
- Within 3%: PASS
- 3%-10% divergence with an adjacent explanatory note: PASS (auto-pass rule)
- 3%-10% divergence without a note: WARN - state cell reference, expected rate, actual rate, delta %
- More than 10% divergence: FAIL regardless of notes

**Check 2 - Drawing-Stage Adder**
If a drawing-stage adder is applied, verify it matches the correct stage:
- IFC: 0% adder
- DD: 5% adder
- Budget/SD/Concept: 8% adder
Adder applied to quantity, not price (internal use only - should not appear on client line items).

**Check 3 - Payment Terms**
Confirm payment terms match 30% / 20% / 50%.
Any reference to 40/20/40: FAIL immediately. Flag as "superseded payment structure."

**Check 4 - GP Margins**
If GP margin per line is visible, compare to targets:
- Fab: 31%, Erection: 30%, Joists: 40%, Roof deck: 23%, Composite: 21%, Anchors: 31%
- Blended target: 25%
- Below target with no note: WARN

**Check 5 - Supplier Name Leak**
Scan any visible text in the pricing rows.
If any supplier name appears: FAIL. Names to flag: Vulcraft, Canam, Nucor, Ayamsa.
Replace with "supplier" or "manufacturer" in client-facing context.

**Check 6 - Engineering Line Item**
Engineering must NOT appear as a separate line item.
Engineering costs are folded into fab and erection rates.
If an "engineering" or "E.O.R." line item exists: WARN. Flag for removal before client delivery.

**Check 7 - Deck in Scope**
Metal deck (roof deck or composite deck) must be present in the pricing.
If deck is missing or marked "NIC" (not in contract) or "by GC": FAIL.
Deck supply and installation is always Your Company's scope.

**Check 8 - Small Project Rate**
If the total bid is under $200,000 and GP target is not at 50%: WARN.
Flag for Owner to confirm if small project override applies.

## Output Format

Return a validation report:

**BID PRICING VALIDATION REPORT**

| Check | Result | Detail |
|-------|--------|--------|
| Rate Accuracy | PASS/WARN/FAIL | [cell ref, expected, actual, delta] |
| Drawing-Stage Adder | PASS/WARN/FAIL | [stage detected, adder applied] |
| Payment Terms | PASS/WARN/FAIL | [terms found] |
| GP Margins | PASS/WARN/FAIL | [margin vs target per line] |
| Supplier Name Leak | PASS/FAIL | [names found if any] |
| Engineering Line Item | PASS/WARN | [line items found if any] |
| Deck in Scope | PASS/FAIL | [deck status] |
| Small Project Rate | PASS/WARN | [total vs threshold] |

**VERDICT:** CLEAN / REVIEW REQUIRED / HOLD

- CLEAN: all checks PASS
- REVIEW REQUIRED: one or more WARN items need the Owner's attention before delivery
- HOLD: any FAIL item. Do not deliver bid until FAIL is resolved.

## Rules

- Read-only. Never modify any cell, formula, or value. Hard constraint.
- Only compare against the locked Q2 2026 baseline above. Never suggest alternative rates.
- If a rate is not in the baseline (e.g., misc steel): WARN that it is outside the locked baseline.
- No em-dashes. Hyphens or periods only.
- Adjacent explanatory note for a divergence: the note must be in the same row or immediately adjacent cell.
  Notes in a different section do not qualify as adjacent.
