---
name: contract-risk
version: 1.0.0
inputs:
  - tender-index.json (head_contract documents)
outputs:
  - contract-risk-register.json
mcp_connectors:
  - filesystem
voice: owner
schema: data/schemas/contract-risk-register.schema.json
---

# contract-risk

## Purpose

Scan the head contract and tender T&Cs. Identify commercial and legal
risk clauses. For each hit, write a row with severity, recommendation,
and a draft qualification sentence Your Company can include in the bid
letter.

## Inputs

Documents classified as `head_contract` in `tender-index.json`.

## Procedure (Sequential Thinking)

1. For each head_contract document, sweep for the eleven risk types:
   - LiquidatedDamages (LDs, "$X per day", "delay damages")
   - PaymentTerms (Net 60/90, pay-when-paid, pay-if-paid)
   - RetentionTerms (% withheld, release schedule)
   - Indemnity (broad-form, mutual, defend-and-hold-harmless)
   - Insurance (limits, AI endorsement, waiver of subrogation)
   - ProgramRisk (acceleration, no-damages-for-delay, sole remedy)
   - ScopeAmbiguity ("to the satisfaction of", "as directed", "implied")
   - HiddenPenalty (chargebacks, backcharges, unilateral deductions)
   - TerminationRights (for convenience, fee on termination, IP on term)
   - IPOwnership (drawings, models, shop drawings)
   - DisputeResolution (venue, arbitration, governing law, waiver of jury)
2. For each hit, capture the verbatim clause and a clause reference
   (document name + section).
3. Score severity:
   - Critical: uncapped LDs, broad-form indemnity, pay-if-paid, IP
     transfer on default, sole-remedy clauses.
   - High: capped LDs >$5k/day, retention >10%, no-damages-for-delay.
   - Medium: standard LDs, retention 5-10%, mutual indemnity.
   - Low: boilerplate that aligns with industry standard.
4. Draft a qualification sentence in the Owner's voice for each Critical
   and High row. Short sentences, no filler.
5. Write `contract-risk-register.json` conforming to schema.

## Output schema

See `data/schemas/contract-risk-register.schema.json`.

## Realistic accuracy

- Standard risk language: ~90% recall.
- Novel or jurisdiction-specific language: lower. Surface uncertainty,
  do not guess.

## Hard rules respected

- Verbatim clause quotes only.
- No legal advice. The register flags risks. Amber (COO) reviews and
  approves all qualifications before they go on a bid letter.
