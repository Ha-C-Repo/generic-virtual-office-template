---
name: contract-notice
description: >
  Draft contractual notices for delay, changed conditions, constructive
  changes, and variations. Use when the user says draft a notice, the GC
  caused a delay, we need to put them on notice, or when the correspondence
  register tags an item NOTICE-CANDIDATE or project controls flag a
  client-caused variance. Handoff 1 item A6, built 2026-06-11.
  DRAFT ONLY: Owner approves before anything is sent.
---

# Contract Notice

## Inputs (all referenced, never embedded, per P10)
1. The signed contract notice clause from `<project>/01 Contract` and the
   matching row in `obligations_register.xlsx` (notice period, required
   form, required recipient).
2. The triggering event: correspondence register rows tagged
   NOTICE-CANDIDATE, field reports, or PC3/PC4 variance data where the
   cause is client-side.
3. The frozen baseline (P14): a notice without a baseline comparison has
   no teeth. If PC1 baselines do not exist yet, say so and state what the
   notice can and cannot claim.

## Process
1. Confirm the notice period has not lapsed. If it has, lead with that:
   state the lapse, the clause, and the residual options. Do not hide it.
2. Draft the notice: event, date noticed vs date occurred, clause cited
   verbatim, factual impact (schedule and cost stated as preliminary
   unless PC data supports a number), records attached or referenced,
   reservation of rights, and the specific relief or instruction
   requested.
3. Voice: the Owner's. Short sentences, specific dates, zero hedging,
   no apology. Facts and clause citations only; no characterizations of
   the GC's motives.
4. Attach the evidence list: register row IDs, field report dates, photo
   references. Every factual claim has a pointer.
5. Hand to Owner for approval with band label [WAIT]. Amber reviews if
   the notice touches indemnity, LDs, or termination. Nothing sends
   without the Owner's explicit go.

## Rules
This skill never sends anything. Quantification of entitlement is D2
(variation quantification) and waits for PC1-PC3 data; this skill
preserves rights, it does not price claims. Log the issued notice in
the correspondence register as OUT with Reference NOTICE-NNN.

## Template types (coverage check 2026-06-11, intake v2 item A6)

| Type | Trigger | Notes |
|--|--|--|
| Delay notice | Client-caused schedule impact | Original scope of this skill |
| Variation notice | Scope change directed or constructive | Original scope |
| Changed conditions | Latent or differing site conditions | Original scope |
| EOT request | Delay notice matured into a time claim | ADDED: cites the prior delay NOTICE-NNN, states days claimed against the frozen baseline (P14), and the contractual EOT clause. Days are preliminary until PC schedule data supports them |
| Practical completion notice | Work complete per contract definition | ADDED: states the PC definition clause verbatim, the completion date claimed, outstanding punch items if any, and starts the defects-liability and retention-release clocks. Triggers the closeout obligations in obligations_register.xlsx |

Same process and rules apply to all five: draft only, Owner approves,
Amber reviews anything touching indemnity, LDs, or termination.
