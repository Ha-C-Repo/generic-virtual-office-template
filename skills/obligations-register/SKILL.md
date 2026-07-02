---
name: obligations-register
description: >
  Maintain the per-project contractual obligations register. Use when a
  contract is signed, when the user says track obligations, what do we owe
  the GC, what are our deadlines, or at each pay-app cycle. Extracts
  obligations from the signed contract into the live register xlsx and keeps
  status current. Handoff 1 item, built 2026-06-11. Pilot: PRJ-2026-ACP-001.
---

# Obligations Register

## Source of record
`<project>/08 Registers/obligations_register.xlsx`. This is a LIVE register
per P13: never mirror it to markdown, always read and write the xlsx.

## Input
The signed contract and subcontract exhibits in `<project>/01 Contract`.
If the contract is not in the folder, stop and say so. Do not invent
obligations from memory.

## Process
1. Read the contract. Extract every obligation with a clause citation:
   deliverables (COI, SOV, submittals, schedules), signature gates
   (approvals that gate progress), money moments (payment triggers,
   retainage, lien waivers), and notice requirements (delay, changed
   conditions, variations, with their notice periods).
2. One row per obligation: ID, Source clause, Obligation, Type
   (Deliverable | Signature gate | Money moment | Notice), Owner, Due or
   trigger, Status, Evidence link, Notes.
3. Rows seeded before contract receipt are marked TEMPLATE. On contract
   receipt, confirm each TEMPLATE row against the real clause, update the
   Source column, and clear the TEMPLATE flag. Flag any contract clause
   with no matching row.
4. Status values: TEMPLATE, OPEN, IN PROGRESS, DONE, AT RISK, MISSED.
   AT RISK and MISSED rows surface to Owner immediately.
5. Separate signature gates from money moments per P18. A money moment
   with no preceding signature gate row is a cash flow risk; flag it.

## Rules
Confidence tag on every extracted obligation. Low confidence = flag for
Amber's legal read, never silently recorded as fact. Notice periods feed
the contract-notice skill; record them exactly as written. No rates or
contract sums embedded in this skill (P10); they live in the register and
the contract. Back up the xlsx to `_handoff/backups/` before structural
changes to the sheet.
