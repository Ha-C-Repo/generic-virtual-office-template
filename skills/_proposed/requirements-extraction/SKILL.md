---
name: requirements-extraction
description: >
  Check, do not generate. After the estimator has read the tender package by
  hand and written the clarification register and the returnable pricing
  schedule, this skill sweeps the same package, lists every requirement the
  client asks to be priced, and flags anything the human missed. AI checks the
  human; the human stays the source of truth. Use during Phase 1 of the
  estimating workflow, before takeoff and before any pricing.
status: PROPOSED (staging). Promote to skills/ only after one live-bid test.
triggers:
  - requirements extraction
  - check my clarification register
  - check the returnable schedule
  - what did I miss in the tender
  - sweep the tender package
  - missing requirements
---

# Requirements Extraction (human-gated check)

## Why this exists

`claude-estimating-workflow.md` Phase 1 and `skills/ROADMAP.md` both list this
as a planned build. The report's framing is the spec: the estimator reads the
tender by hand and writes two documents first. This skill then audits that
hand work. It never replaces the estimator's reading. It catches omissions.

This is a CHECK skill. It pairs with, and does not duplicate:
- `skills/bid/requirement-register.skill.md` builds the four-bucket register
  from scratch (the system of record). Run that for the structured register.
- `skills/takeoff-completeness-check/SKILL.md` checks CSI section coverage.
- This skill reconciles the human's clarification register and returnable
  schedule against the tender, and surfaces gaps for the human to resolve.

## Required inputs (all human-supplied)

1. The tender package (drawings excluded here; specs, scope, head contract,
   addenda, instructions to bidders).
2. The estimator's hand-written **clarification register** (unclear,
   contradictory, or missing items).
3. The estimator's hand-written **returnable / pricing schedule** (the
   line-item breakdown that will be priced).

If any of the three is missing, stop and ask for it. Do not proceed on two of
three. Do not invent the human documents.

## Procedure

1. Sweep the tender package page by page. Extract every distinct priced
   requirement as a verbatim sentence with a page-level citation. No
   paraphrasing of contract language.
2. Build a working list of requirements found in the package.
3. Diff against the returnable schedule: for each requirement, is there a
   matching line? Output one of: Covered, Missing-from-schedule,
   Ambiguous-match.
4. Diff against the clarification register: for each item that is unclear,
   contradictory, or absent from the docs, is it already logged as a
   clarification? Output: Logged, Not-logged.
5. Flag conflicts the human should resolve before costing (for example a
   quantity stated two ways on two sheets, the open 64-vs-160 anchor type of
   discrepancy, or scope that two trades both claim).
6. Assign confidence 0.0-1.0 per finding. Anything below 0.7 is marked for
   human review, never asserted.
7. Output a short gap report. The estimator resolves each gap. The skill does
   not edit the human documents.

## Output

`requirements-extraction-gaps.md` in the bid's `_bid_context/` folder:
- Missing-from-schedule list (requirement, verbatim quote, page).
- Not-logged clarifications (issue, page, why it needs a question to the GC).
- Conflicts to resolve (the two readings, both citations).
- Confidence column; sub-0.7 rows grouped under "verify by hand".

## Hard rules respected

- Verify, do not generate. The human-written documents are inputs, never
  outputs of this skill.
- Deck supply AND install are always Your Company scope; never flag them as
  exclusion candidates.
- Engineering is folded into fab/erection, never a standalone priced line.
- No supplier names surfaced.
- SF is sourced, not assumed. If gross SF is needed and not stated on the set,
  flag an SF-confirmation RFI per `skills/cowork-bid-estimate/SF_AND_ACCURACY_2026-06-15.md`.
- Verbatim quoting only.

## Realistic accuracy

- Tabulated/clear specs: ~95% recall of priced requirements.
- Prose-only specs: ~70-80%. The gap report is a safety net, not a guarantee.
- This skill reduces missed-scope risk. It does not certify completeness.

## Promotion criteria

Run alongside the current manual Phase 1 on one live tender. If it catches a
real gap the estimator missed, and produces no false "missing" on items that
were in fact scheduled, promote from `skills/_proposed/` to `skills/`. Until
then it is advisory only.
