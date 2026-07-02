---
name: bid-orchestrator
description: >
  State-aware orchestration workflow for YourCo bid composition.
  Refactored from the linear bid composition chain into Command/Agent/Skill
  graph nodes. Entry point for all structural takeoff and bid generation
  sessions. Implements the C/A/S primitive architecture with 90-turn
  budget containment. Triggered by Owner or Joseph from the dashboard.
triggers:
  - /bid-orchestrator
  - start a bid
  - new bid
  - takeoff for
  - generate bid
  - bid for project
---

# Bid Orchestrator - YourCo Virtual Office

**Replaces:** The old linear bid composition chain.
**Architecture:** Command -> Agent -> Skill primitives per the YourCo Phase 8 C/A/S design.
**Budget:** 90-turn hard cap per session. At turn 85, summarize and yield.

---

## The C/A/S primitives

### Command (C) - Entry point
Owner or Joseph triggers `/bid-orchestrator` from the dashboard. The Command collects project context and provisions the appropriate Agent.

### Agent (A) - Isolated executor
Each Agent is provisioned for one task and has access only to the Skills it needs. Two primary agents in the bid workflow:

- **Scout Agent:** Processes drawing tiles. Runs tiled inference. Outputs verified shape list.
- **Bid Composer Agent:** Takes the verified shape list and compiles the bid document.

Agents do not share state. Scout Agent output is handed to Bid Composer Agent as a structured JSON payload, not as a running context.

### Skill (S) - Reusable tool
Skills are the atomic units. Agents call Skills. Skills do not call each other directly.

---

## Full orchestration flow

```
COMMAND: /bid-orchestrator
Triggered by: The Owner or Joseph Hasse via dashboard

-----------------------------------------------------
STEP 1: AskUser (Conditional Gate)
-----------------------------------------------------
Prompt for project context if not provided:
  -> Project name (for file naming)
  -> Drawing version and scale (e.g., "1/8" = 1'-0"")
  -> Drawing stage (IFC / DD / Budget-SD)
  -> Scope confirmation (fab only / fab+erection / full package)

If all context present in the trigger: skip gate, proceed immediately.
If any context missing: pause and prompt. Do not assume.

-----------------------------------------------------
STEP 2: Scout Agent provisioning
-----------------------------------------------------
Provisions a short-lived, isolated Scout Agent with access to:
  -> Skill: tiled-inference (drawing tile processing)
  -> Skill: drawing-stage-classifier (classify IFC/DD/SD)
  -> Skill: takeoff-completeness-check (CSI section completeness)
  -> Read access: AISC master CSV
  -> Write access: None (Scout Agent is read-only)

Scout Agent is isolated. It cannot write to the bid pipeline database.
It cannot access bid rates or GP data.

-----------------------------------------------------
STEP 3: Scout Agent execution (Skill chain)
-----------------------------------------------------
3a. Skill: drawing-stage-classifier
    -> Input: drawing metadata, scale, version
    -> Output: stage (IFC / DD / Budget-SD), contingency %
    -> If stage UNKNOWN: block and request manual classification from Joseph

3b. Skill: tiled-inference
    -> Input: drawing files (PDF or image)
    -> Strips empty blueprint regions (whitespace > 40% of tile area)
    -> Passes high-density tiles to cloud inference endpoint
    -> Output: raw shape list with quantities

3c. Skill: AISC shape verifier
    -> Input: raw shape list from tiled-inference
    -> For each shape: verify against AISC 2,299 master CSV
    -> Flag: any shape NOT in master CSV -> block that line item
    -> Apply stage contingency to all quantities
    -> Output: verified shape list (JSON)

3d. Skill: takeoff-completeness-check
    -> Input: verified shape list
    -> Check CSI section coverage: Div 05 framing, connections, misc metals
    -> Flag: any standard section missing from the scope
    -> Output: completeness report + verified shape list

3e. Scout Agent yields to Bid Composer Agent
    -> Payload: { verifiedShapes, stage, contingency, completenessReport, projectContext }

-----------------------------------------------------
STEP 4: Bid Composer Agent provisioning
-----------------------------------------------------
Provisions Bid Composer Agent with access to:
  -> Skill: bid-pricing (apply CEO-locked rates to shape list)
  -> Skill: bid-pricing-sanity-check (validate GP% against targets)
  -> Skill: bid-compliance (26 Tier 1 immutable rules)
  -> Skill: bid-output-scrubber (6 client-doc content rules)
  -> Skill: proposal-format (PDF generation)
  -> Skill: owner-voice-check (BLOCKING gate)
  -> Read access: bid rates config, payment terms config
  -> Write access: bid_pipeline.db (bid record), PDF output directory

-----------------------------------------------------
STEP 5: Bid Composer Agent execution (Skill chain)
-----------------------------------------------------
5a. Skill: bid-pricing
    -> Apply CEO-locked rates to verified shape list
    -> Fab: $3,750/ton, Erection: $970/ton, Joists: $4,500/ton, etc.
    -> Apply G&A at 7.5%
    -> Output: priced line item matrix

5b. Skill: bid-pricing-sanity-check
    -> Verify GP% per line item against targets
    -> Flag: any line item below target GP
    -> Flag: any line item with GP > 50% (likely error)
    -> Reject and re-prompt if overall GP below 20% or above 45%

5c. Skill: bid-compliance (26 Tier 1 rules)
    -> Hard-check: no invented shapes, no modified rates, correct payment terms (30/20/50)
    -> Hard-check: deck in scope if structural steel in scope
    -> Hard-check: engineering folded into rates (not line-itemed)
    -> Block: any violation. No partial compliance.

5d. Skill: bid-output-scrubber (6 client-doc rules)
    -> Strip supplier names (per bridge/virtual_owner.py YOUR_COMPANY_SUPPLIERS)
    -> Strip team member names (Ivan, Mario, Paul)
    -> Strip internal rate notes or GP% from client content
    -> Confirm signatory: Owner Steel (not The Owner)
    -> Confirm no em-dashes in output text
    -> Output: scrubbed client content

5e. Skill: proposal-format
    -> Generate Client PDF: scope, quantities, pricing, payment terms
    -> Generate GP PDF: full cost breakdown, GP% per line, actual material costs
    -> File naming: [ProjectName].pdf and [ProjectName]-GP.pdf
    -> Verify: two PDFs produced, not one

5f. Skill: owner-voice-check (BLOCKING gate)
    -> Check both PDFs for voice violations
    -> PASS: proceed silently
    -> AUTO-FIX: em-dashes, hedging openers
    -> BLOCK: unresolved placeholders, supplier names, invented certifications
    -> If BLOCK: return to 5d for resolution. Do not deliver blocked PDFs.

-----------------------------------------------------
STEP 6: Command resolution
-----------------------------------------------------
All gates PASS:
  -> Write bid record to bid_pipeline.db
  -> Deliver paired PDFs to output directory
  -> Log: { projectName, stage, totalPrice, GP%, shapesCount, bidId, timestamp }
  -> Notify Owner via SMS gateway if bid > $500K (configured threshold)

Any gate BLOCKED:
  -> Log the block reason
  -> Surface to Joseph for manual resolution
  -> Do NOT write to bid_pipeline.db until all blocks resolved
  -> Do NOT deliver PDFs until all blocks resolved
```

---

## 90-turn budget containment

The bid orchestration session has a hard cap of 90 turns.

Turn 30: Confirm Scout Agent has a complete verified shape list before proceeding to Bid Composer.
Turn 60: Confirm all compliance gates have passed before triggering PDF generation.
Turn 85: TURN 85/90 - summarize current state, yield to Joseph if incomplete.
Turn 90: Session must stop. Joseph reviews and restarts if incomplete work remains.

Why: A runaway tiled-inference session against a large drawing set can consume hundreds of turns if not capped. The 90-turn limit forces a checkpoint that catches inference failures early.

---

## Error states

| Error | Cause | Action |
|---|---|---|
| Shape not in AISC master | AI hallucinated a shape | Block that line item. Flag to Joseph. Do not deliver. |
| GP% below 20% | Rate error or scope undercount | Block. Re-run bid-pricing. Alert Owner if persistent. |
| Missing CSI section | Incomplete drawing set | Flag completeness gap. Joseph decides whether to proceed with caveat or request more drawings. |
| owner-voice-check BLOCK | Unresolved placeholder or compliance text in output | Return to bid-output-scrubber. Resolve before delivery. |
| Scout Agent > 45 turns | Large or complex drawing set | Checkpoint at 45 turns. Resume with verified shapes collected so far. |

---

## Skill turn-cost estimates

| Skill | Typical turns | Notes |
|---|---|---|
| drawing-stage-classifier | 2-3 | Fast lookup |
| tiled-inference (per drawing) | 5-15 | Depends on drawing density |
| AISC shape verifier | 2-4 | CSV lookup |
| takeoff-completeness-check | 2-3 | CSI section audit |
| bid-pricing | 2-3 | Rate application |
| bid-pricing-sanity-check | 1-2 | Arithmetic check |
| bid-compliance | 3-5 | 26-rule audit |
| bid-output-scrubber | 2-3 | Text scrub |
| proposal-format | 5-10 | PDF generation |
| owner-voice-check | 1-3 | Gate check |
| **Total typical session** | **25-55 turns** | Well within 90-turn budget |
