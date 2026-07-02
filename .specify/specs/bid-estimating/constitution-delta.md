# Bid Estimating - Constitution Delta

Additive specification. Layers on top of the existing Your Company CLAUDE.md
and any future `.specify/constitution.md`. Nothing here overrides Tier 1
Immutable Rules. Where this delta conflicts with the project CLAUDE.md,
the project CLAUDE.md wins.

Generated: 2026-05-23
Source: AI-Enhanced Construction Bid Estimating handoff (Part 2)
Owner: The Owner / Joseph Hasse
Status: Phase 1 of 7 (additive, reversible)

---

## 1. Scope of this delta

Defines the data, skills, artifacts, and validators required to operate
the AI-augmented bid estimating workflow inside Cowork using only the
approved stack (Claude Max 5x, Google Workspace, M365, Sequential
Thinking MCP, filesystem MCP).

This delta does not replace Your Company's existing bid pipeline. It adds
a governance layer above the existing skills (bid-compliance,
bid-orchestrator, bid-pricing, bid-pricing-sanity-check,
bid-output-scrubber, takeoff-completeness-check, two-pdf-pair-check,
scope-creep-detector). Those existing skills remain authoritative for
their stated functions. The new skills under `skills/bid/` add:

- Requirement Register extraction (the four-bucket scope checklist)
- Contract risk register
- Inclusions/Exclusions auto-derivation
- Spec-to-BoQ preliminary estimate
- Reconciliation engine (gap + orphan + rate anomaly)

## 2. Verified facts hard-coded across the workflow

- Company: Your Company, LLC
- Established: 2017
- Address: [COMPANY ADDRESS]
- Office: [COMPANY PHONE]
- ISNetworld ID: [ISN ID]
- Current build: v3.3.16
- Shop labor rate: $145/hr
- Engineering rate: $175/hr (folded into fab and erection; never line-itemed)
- Overhead multiplier: 1.15x
- Fabrication baseline: 11 hr/ton (machine-assisted blended, April 2026)
- AISC reference: Shapes Database v16.0
- BID_RATES (Q2 2026, CEO-locked): fab $[FAB RATE]/T, erection $[ERECTION RATE]/T,
  joists $[JOIST RATE]/T, roof deck $[ROOF DECK RATE]/SF, composite $[COMPOSITE DECK RATE]/SF, anchors $[ANCHOR RATE]/ea,
  G&A 7.5%

## 3. Hard rules enforced by validator

`scripts/validate-bid-output.py` runs before any PDF export. Failure
modes:

1. Supplier name present in client proposal (Vulcraft, Canam, Nucor,
   Ayamsa, others). Tier 1 violation.
2. Precedent project named on a bid proposal. Capability statements only.
3. Engineering shown as a separate line item.
4. Deck supply or deck install missing from Inclusions.
5. Two-PDF pair incomplete. Both `<bid>.pdf` and `<bid>-GP.pdf` must exist.
6. Em-dash characters present in output.
7. Three-adjective sequences, "Great question", or filler-opener language.
8. [FORBIDDEN PROJECT] referenced anywhere on a bid or capability sheet.

## 4. Files created by this delta

```
.specify/specs/bid-estimating/
    constitution-delta.md            (this file)
data/schemas/
    requirement-register.schema.json
    estimate-line.schema.json
    contract-risk-register.schema.json
    inclusions-exclusions.schema.json
    production-rate-library.schema.json
skills/bid/
    tender-ingest.skill.md
    requirement-register.skill.md
    inclusions-exclusions.skill.md
    contract-risk.skill.md
    spec-boq.skill.md
    reconciliation.skill.md
library/
    production-rates.yaml
artifacts/templates/
    reconciliation-dashboard.html.tpl
    bid-gantt.mmd.tpl
    requirement-register.html.tpl
    client-proposal.html.tpl
    gp-report.html.tpl
scripts/
    validate-bid-output.py
handoff_backups/
    journal.log
```

## 5. Reversal

Each phase is reversible by deleting the directory or file it created.
No existing project file is overwritten by this delta. Phase 4
(production-rates.yaml) creates a new file. If a production-rates file
already exists in the project, the delta version is named
`production-rates.yaml` and the existing file is backed up to
`handoff_backups/<UTC-ISO-timestamp>/production-rates.yaml.bak` before
the new file is written.

## 6. Voice rules in effect

Short sentences. Specific numbers. No filler. No em-dashes. No "Great
question". No three-adjective lists. No "it's not just X, it's Y".
the Owner's voice or Joseph's. Ask before drafting outbound content.

## 7. Out-of-stack components flagged

The following are referenced by the research paper but are NOT installed
or operated by this delta. They sit outside the approved stack and any
adoption requires CEO approval.

- SketchDeck LIFT (pixel-accurate steel takeoff)
- Beam AI structural-steel takeoff
- Togal.AI
- Kreo
- Procore Estimating
- Operum.io
- PinPoint Analytics

This delta delivers parity on tender intelligence, scope register,
contract risk, inclusions/exclusions, reconciliation, and time-based
overhead. It does not deliver parity on graphical drawing takeoff.
Drawing takeoff remains human-led until a controlled trial proves
otherwise.

## 8. Rollout sequence (from research paper §11)

- Week 1: P1-P2 (this file + schemas)
- Week 2: P3-P4 (skills + rate library)
- Week 3: P5-P6 (artifacts + scheduled tasks)
- Week 4: P7 (MCP connectors + validator). Calibrate on three closed bids.
- Week 5: Production use for governance layer. Drawing takeoff remains
  human-led.
