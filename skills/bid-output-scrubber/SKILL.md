---
name: bid-output-scrubber
description: >
  Final scrub of any client-facing bid document, proposal PDF, or
  scope narrative before delivery. Enforces six rules in one pass:
  no supplier names, no precedent projects, no engineering line item,
  deck always in scope, no PEMB-manufacturer language, no 40/20/40
  payment terms. Run on every bid PDF after generation, before
  saving the final copy.
triggers:
  - finalize bid
  - scrub bid
  - pre-flight bid
  - bid ready
  - check this proposal
  - scrub proposal
  - check before send
  - is this bid clean
---

# Bid Output Scrubber

A single skill that runs all six Owner bid-content rules in one
pass. Each rule has a violation pattern, a severity, and a fix.

## Rule 1 — No supplier names (CRITICAL)

Pattern: any of the following literal strings in the document body
(case-insensitive):
```
Peyton, J.H. Botts, A&M Nut & Bolt, A&M Nut and Bolt,
Service Steel, Service Steel Warehouse, Triple-S, Triple-S Steel,
Brown Strauss, Atlanta Rod, Vulcraft, Nucor, Canam,
Ayamsa, Schuff, Herrick, Cives, Steel Dynamics, SDI
```

Auto-fix: replace with `qualified steel suppliers` (plural) or
`supplier quotes` depending on context. Verify the sentence still
reads naturally.

Exception: equipment brands are allowed. `Arc Pro Automation` and
`Squickmons` (the CNC plasma cutter and hydraulic ironworker we
own) may be named.

## Rule 2 — No precedent projects (CRITICAL)

Pattern: any of the following on a bid PDF:
```
ICD Church, Elite Crossing, Topgolf New Braunfels, Carvana Mobile,
Fulshear Central, [FORBIDDEN PROJECT]
```

NOTE: [FORBIDDEN PROJECT] is NOT a Your Company project. If it appears
anywhere, BLOCK the document entirely and surface a critical alert.
This is a brand-integrity rule per system prompt.

Auto-fix: delete the line or sentence that names the project.
Don't try to substitute another project. If the paragraph becomes
empty, delete it. If the paragraph was citing "completed projects
include," replace with capability language: "10+ tons fabricated
weekly across commercial, industrial, and retail clients" with the
adjective rule enforced (rephrase to two adjectives).

## Rule 3 — No engineering line item (HIGH)

Pattern: a row in a pricing table or scope list whose label exactly
matches or contains:
```
Engineering, Detailing, Engineering & Detailing, Shop Drawings (priced),
PE Stamp Fee, Design Services
```

Where the label is in a row that has its own dollar amount column.

Auto-fix: remove the row. Fold its dollar value into the Fabrication
or Erection row above it (allocate per the project's blend). If the
row was zero-priced, just delete it. Note in a comment that
engineering is included in fab+erect rates.

Exception: an internal GP report (filename suffix `-GP`) may show
engineering separately for cost tracking. Apply this rule ONLY when
the document is the client-facing proposal.

## Rule 4 — Deck always in scope (HIGH)

Pattern: a scope of work that omits deck supply and installation, OR
lists deck as "optional," "by others," "alternate," or "GC-supplied."

Auto-fix: add a line under section 05 31 00 (Steel Decking) that
reads "Galvanized 3" deck supply and installation included. See
Pricing Schedule for rate."

If the omission is intentional (e.g., bearing-wall building where
the GC specifically said deck is separate), flag and ask Owner to
confirm before suppressing this rule.

## Rule 5 — No PEMB-manufacturer language (MEDIUM)

Pattern: the document references or implies we are supplying a
pre-engineered metal building system. Trigger phrases:
```
Red Dot Buildings, Mueller, Varco Pruden, Butler, Nucor Building
Systems, Metallic Building, PEMB system, pre-engineered package,
turnkey building, design-build building
```

Auto-fix: remove the phrase. Replace with the appropriate descriptor:
- "Conventional structural steel frame" if the project IS conventional
- "Structural steel for the manufacturer-supplied PEMB" if the project
  has a separately-procured PEMB and we're only doing the conventional
  steel scope (mezzanines, embedded angles, secondary framing)

## Rule 6 — Payment terms 30/20/50 (MEDIUM)

Pattern: any of the following payment splits in the Terms section:
```
40/20/40, 50/25/25, 30/30/40
```

Auto-fix: replace with `30/20/50` (mobilization 30%, mid-fab 20%,
final on substantial completion 50%). Update the dollar amounts in
the payment table to match.

Exception: if Owner explicitly set different terms for a specific
client (Marathon, refinery TICs sometimes require different splits),
leave alone but flag for review.

## Execution order

Run rules in this exact order so auto-fixes don't conflict:

1. Rule 1 (supplier names) — string substitution
2. Rule 2 (precedent projects) — paragraph deletion
3. Rule 5 (PEMB language) — phrase substitution
4. Rule 3 (engineering line item) — table row removal
5. Rule 4 (deck scope) — scope-section addition
6. Rule 6 (payment terms) — terms-section substitution

Then re-render the PDF if any fixes applied. Diff old vs new and
attach the diff to the report under `--- scrubber applied ---`.

## Output contract

Three response shapes. Identical to the owner-voice-check contract
for consistency.

1. **PASS** — return input unchanged, no commentary
2. **AUTO-FIX** — apply fixes, return corrected document, append a
   block listing what changed with rule number and severity
3. **BLOCK** — for [FORBIDDEN PROJECT] references or for cases where
   auto-fix can't safely resolve (e.g., the engineering line item
   has a custom amount that needs Owner to redistribute manually)

## Two-PDF rule reminder

Per the Owner's standing rule: every bid produces TWO PDFs. The
client proposal AND the internal GP report (filename suffix `-GP`).
If only one PDF has been generated when this skill runs, surface
a warning to also generate the GP report before delivery.

## Why this skill exists

Six separate Owner corrections combined into one pass. Each rule
was learned the hard way from a bid he had to manually clean up.
Running them as one skill prevents the "you fixed rule 1 but rule
3 leaked through" failure mode. Apply on every bid. No exceptions.
