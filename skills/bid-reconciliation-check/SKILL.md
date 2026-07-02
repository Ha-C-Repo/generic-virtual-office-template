---
name: bid-reconciliation-check
description: >
  Advisory cross-check. Diff a finished steel estimate against the
  requirements-and-exclusions register and report a coverage rate plus named
  gaps (unpriced items, double-counts, excluded-but-priced, orphan lines).
  Cross-check only, generation off. It never sets or changes a price,
  quantity, weight, or rate. Best run as a fresh, memoryless pass.
triggers:
  - reconciliation check
  - reconcile the estimate
  - recon check
  - coverage check
  - what did the estimate miss
  - unpriced items
  - double count check
  - estimate vs requirements
---

# Bid Reconciliation Check (advisory cross-check)

## What this is, and what it is not

This is a verify-do-not-generate gate. It reads a finished estimate and the
requirements-and-exclusions register for the same bid, and it reports where the
estimate covers the register and where it does not. It is a cross-check.
Generation is off.

It cannot and must not produce, set, or change any price, quantity, weight, or
rate. Member weights come from `bridge/aisc_validator.py`. Rates come from
`bridge/bid_rates.py`. The only numbers this gate emits are diagnostic counts
and a coverage ratio over the inputs you give it. It returns no go/no-go
verdict on price. Every finding is reviewed by a human before bid submission.

Run it as a fresh, memoryless pass. It checks the estimate against the source
register, not against its own prior working. ConstructIQ reached this same
posture from the general-construction side: a final reconciliation pass, run in
a separate session, caught 17 unpriced items, a double-count, and 9 scope gaps
at about 75 percent coverage. That validates the design. It does not loosen the
rule that the human owns the number.

## Inputs

1. The finished estimate or BOQ: a list of priced line items. Canonical fields
   per `planswift_import.py` / `bluebeam_boq_adapter.py`: `line_id`,
   `description`, `category`, `discipline`, `unit`, `qty`, `unit_rate`,
   `extended`, and `requirement_refs` (the list of `req_id` values that line
   satisfies). This gate reads only `line_id`, `description`, `category`,
   `unit`, and `requirement_refs`. It ignores `unit_rate` and `extended` on
   purpose. It does not touch money.

2. The requirements-and-exclusions register: a list of requirement rows. The
   skill-doc shape is `req_id`, `requirement_text`, `category`, `status`,
   `priced_line_ref`, `source_doc`, `source_page`. The
   `bridge/requirements_register.py` emitter shape (`id`, `description`,
   `category`, `confidence`, `source_citations`) is also accepted. Exclusions
   are register rows with `category` "Excluded" (or `status`
   "ExcludedByDesign"). An inclusions-and-exclusions list may be passed as
   `{"inclusions": [...], "exclusions": [...]}` and is merged for you.

If either input is missing, stop and ask for it. Do not invent an estimate or a
register. Do not reconstruct numbers from memory.

## Method: deterministic first, judgment only on the remainder

Scripts do the cheap, exact matching. The model judges only the ambiguous
remainder. The script never keyword-guesses whether a line covers a
requirement; that semantic call is the model's job, item by item. This is the
"AI classifies, scripts never pattern-match" rule.

The deterministic engine is `bridge.bid_sanity_gates.reconcile_advisory`,
surfaced to the GUI and the MCP server as the Bridge method
`bid_reconciliation_check`. It matches on identity only:

- An estimate line's `requirement_refs` listing a `req_id`.
- A register row's `priced_line_ref` naming a `line_id`.

From those links it computes:

- Coverage rate. Priceable requirements (every category except Subcontractor
  and Excluded) that carry an explicit link, divided by all priceable
  requirements. Reported as a ratio of counts, never a dollar figure.
- UNPRICED_REQUIREMENT. A priceable requirement with no linked line. The named
  gap. Tagged needs_judgment so the model confirms no unlinked line covers it.
- EXCLUDED_BUT_PRICED. A register row marked excluded that a line still links
  to. A scope contradiction to resolve before submitting.
- DOUBLE_LINK and DUPLICATE_LINE. Double-count candidates: one requirement
  claimed by two or more lines, or two lines identical in description, unit,
  and category.
- ORPHAN_LINE. A priced line that traces to no requirement. Possible scope
  creep, or a requirement the register missed.

Everything the script cannot link is routed to a needs_judgment bucket. That
bucket is the model's work: read each unlinked requirement and each orphan line
against the source and decide, item by item, whether the scope is genuinely
covered. Quote the source. Do not assert a match the script did not make
without naming the evidence.

## Method-linked confidence on every finding

Each finding carries a confidence tag tied to how it was found, matching the
house confidence doctrine:

- high. A deterministic, unambiguous identity result. Example:
  EXCLUDED_BUT_PRICED, where an excluded requirement is explicitly linked to a
  priced line.
- medium. A deterministic structural signal that usually indicates a problem
  but can be benign. Examples: an unlinked priceable requirement, a duplicate
  line, a requirement linked by two lines that may be a legitimate split.
- low. The script could not decide. These are the needs_judgment items handed
  to the model or a human. They are never asserted as fact.

A medium or low finding is a prompt for review, not a conclusion. Do not
upgrade a finding's confidence without new evidence from the source.

## Output

The Bridge method returns the standard envelope `{"ok": true, "data": {...}}`.
The data payload carries `advisory: true`, `generates_numbers: false`,
`coverage` (priceable_total, linked_matched, coverage_rate, basis),
`findings` (each with type, confidence, needs_judgment, method, source, note),
`summary` (the counts), `verdict: null`, and a `disclaimer`. Present the
coverage rate, then the named gaps grouped by type, then the needs_judgment
list for the human to work top to bottom. Use prose, not a wall of bullets.

## Hard rules respected

- Advisory and read-only. No price, quantity, weight, or rate is produced, set,
  or changed. No go/no-go verdict on price.
- Member weights cite `bridge/aisc_validator.py`. Rates cite
  `bridge/bid_rates.py`. This gate cites neither because it sources neither.
- Deck supply and install are always Your Company scope. Never flag deck as an
  exclusion candidate.
- Engineering is folded into fab and erection, never a standalone priced line.
- No supplier names surfaced. No em-dashes. No filler language.
- Verify, do not generate. The estimate and the register are inputs, never
  outputs of this gate.

## Cross-references

- `skills/bid/reconciliation.skill.md` is the heavier engine spec (rate bands,
  arithmetic checks, the Ivan rules A through F, an HTML dashboard). This gate
  is the lighter, advisory coverage-and-gaps cross-check that wires alongside
  `run_gates()`. Run the full engine when you need rate-band and arithmetic
  checks; run this gate for a fast fresh-pass coverage read.
- `skills/bid/requirement-register.skill.md` and
  `skills/bid/inclusions-exclusions.skill.md` build the register this gate
  reads.
- `skills/takeoff-completeness-check/SKILL.md` checks CSI section coverage and
  pairs with this gate.

## Needs Ivan sign-off before a live bid

By design nothing here sets a number, so the gate itself is safe to run on any
bid as a read-only check. The one item for Ivan before its output informs a
live bid is confirming that the estimate-line and register field mapping
matches the BOQ system of record, the same gate the plan attaches to the
row-level takeoff schema (item 1.3).
