---
name: spec-driven-development
description: >
  The 6-stage spec-driven engineering lifecycle for the YourCo virtual
  office. Eliminates vibe coding on the bid engineering codebase by
  requiring every structural change to pass through constitution -> specify
  -> clarify -> plan -> tasks -> implement before any Python file is written.
  Adapted from github/spec-kit. Read .specify/constitution.md first.
triggers:
  - spec
  - new feature
  - build this
  - add this
  - change the
  - fix the architecture
  - engineering task
---

# Spec-Driven Development - YourCo Virtual Office

**The problem:** Vibe coding on a large Python bridge causes silent regressions in the bid pipeline. A change to the takeoff engine that breaks the AISC shape lookup does not announce itself. The spec discipline exists to make regressions impossible to miss.

**Stack context:** Python 3.13, pywebview, Flask (webhooks only), SQLite WAL, PyInstaller. Bridge methods in `bridge/api.py`. Skills under `skills/`. Claude Sonnet/Opus for reasoning, Haiku for triage, Gemini for multimodal, GPT-4o for structured output.

---

## The 6-stage lifecycle

```
/constitution -> /specify -> /clarify -> /plan -> /tasks -> /implement
```

---

## Operating postures

The lifecycle is the same every task. The hat you wear inside it changes with
the work. Pick the posture, then run the stages. Scale framing is always this
project's scale; defer infrastructure calls to the five gates in
`.specify/governance-delta.md`. Never change product behavior under a refactor.

- Technical lead (Mode 8). Any non-trivial decision before code. Lives in
  /clarify. Ask the questions, challenge a bad ask, name scaling risks,
  recommend the simplest approach. Output: decision, trade-offs, plan.
- Greenfield architect (Mode 1) and Backend architect (Mode 6). New system or
  backend. Live in /plan. Design the full shape first, then build the minimal
  version that can grow. Output: architecture, data flow, file structure,
  schema, Bridge method impact, then code. Monolith-first and Premature-scaling
  gates apply.
- Clean-architecture refactorer (Mode 5). Working but messy code. Lives in
  /plan. Separate concerns, cut coupling, behavior stays identical. Output: new
  structure, what improved, regression list.
- Frontend engineer (Mode 7). UI work in frontend/. Honor Hard Rule 9: the
  frontend calls the Bridge via window.pywebview.api, never DOM-to-Python.
  Handle loading, empty, and error states. Output: component shape, states,
  usage note.
- Production debugger (Mode 3). Live bug or crash. Do not guess. State what the
  code actually does, then root cause, then why it fails, then edge cases, then
  the smallest robust fix. Reproduce before you fix. Fatal log path is in
  CLAUDE.md and CLAUDE.local.md.

Deeper review postures (auditor, performance, security) live in vj-scan.
Pre-build thinking uses pre-mortem.md.

---

## Stage 1: /constitution

Read `.specify/constitution.md` in full before anything else.

Gate questions:
- Does this task touch bid rates? (CEO-locked - requires Owner approval)
- Does this task touch AISC shape lookup? (Non-negotiable accuracy boundary)
- Does this task produce client-facing output? (Voice firewall and two-PDF standard apply)
- Does this task modify the SQLite schema? (Backup required before any migration)
- Does this task affect ISNetworld compliance data? (Hardcoded values - no AI interpolation)
- Does this task ask the LLM to do arithmetic? (Banned - route through calculator)
- Does this task touch a protected file outside its marked extension point? (Banned - quarantine and request human merge)

If any answer is yes: note the constraint and proceed with it as a hard boundary, not a guideline.

**Output:** One-line check: "Constitution reviewed. Constraints noted: [list]" or "No constitution violations identified."

---

## Stage 2: /specify

Write the specification. Three sections. One document.

```
FEATURE: [name]
DATE: [date]
AUTHOR: [Joseph / Claude Code / both]

WHAT IT IS:
[2-3 sentences in bid operations terms, not Python terms]

WHAT IT IS NOT:
[Explicit exclusions - what this change intentionally does not do]

SUCCESS CRITERIA:
[3-5 measurable outcomes. What can Owner or Joseph do that they cannot do today?
 Include accuracy assertions where relevant: "AISC shape lookup returns correct section
 properties for 100% of the synthetic test shapes."]
```

Example - Upgrading the AISC shape verifier:
```
FEATURE: AISC shape verifier - tolerance mode
DATE: 2026-05-20

WHAT IT IS:
Adds a +/-5% quantity tolerance mode to the shape verifier for IFC-stage drawings.
When a drawing is classified as IFC, the verifier flags quantities outside +/-5%
of the reference takeoff instead of hard-blocking them.

WHAT IT IS NOT:
Not a change to bid rates. Not a change to the AISC master CSV.
Does not affect DD or Budget/SD stage behavior.

SUCCESS CRITERIA:
1. IFC drawings with quantities within +/-5% pass without a warning.
2. IFC drawings with quantities outside +/-5% produce a yellow warning, not a red block.
3. DD and Budget/SD drawings are unaffected by this change.
4. The GP PDF correctly marks IFC-flagged quantities as "within tolerance."
5. No regression in the existing bid test cases.
```

**Output:** Spec saved to `.specify/specs/[feature-name]-[date].md`.

---

## Stage 3: /clarify

Auto-generate targeted questions to isolate edge cases before touching any file.

**Required clarification areas for YourCo tasks:**

- **Bridge method impact:** Which Bridge methods in `bridge/api.py` does this touch? Are any methods affected that are not obvious from the spec?
- **Skill interactions:** Does this change affect any of the skills under `skills/`? Which ones must be regression-tested?
- **Drawing stage logic:** If the task involves takeoff or pricing - which drawing stages are affected?
- **Database schema:** Does this require a schema change? What is the migration path?
- **PDF output:** Does this change the structure of either the client PDF or the GP PDF?
- **Voice compliance:** Does this produce new text output? If yes, the owner-voice-check skill runs on it.
- **Compliance data:** Does this touch ISNetworld, EMR, or compliance program data? If yes, Paul Guerrero or Owner must review.

**Seeded edge cases for the YourCo domain (always ask):**
- Drawing version-scale mismatch (e.g., a scale change without a version bump)
- Shape absent from the AISC master set
- Rate not present in `bridge/bid_rates.py` :: `BID_RATES`
- Em-dash present in any string this task will emit
- The task wants arithmetic from an LLM (constitution NC-11)

Format:
```
CLARIFICATION QUESTIONS - [feature name]
1. [Question] -> [Answer or UNKNOWN]
...
```

Do not proceed until all UNKNOWN items are resolved. Unresolved edge cases in a bid engine become incorrect bids.

---

## Stage 4: /plan

Technical approach based on spec and clarifications.

```
TECHNICAL PLAN - [feature name]

PYTHON CHANGES:
[Files to be modified. Function signatures. No code yet - describe intent.]

DATABASE CHANGES:
[Schema changes. Migration script approach. Backup required: yes/no]

BRIDGE METHOD IMPACT:
[Which methods are affected. Any new methods to add.]

SKILL IMPACT:
[Which skills need updating. Regression test list.]

PDF OUTPUT CHANGES:
[Client PDF: what changes. GP PDF: what changes.]

CONSTITUTION COMPLIANCE:
[List the clause IDs (NC-1.1 etc.) this task touches and whether each is preserved.]
[AISC shape data: confirmed unchanged / [note]]
[Bid rates: confirmed unchanged / [note - requires Owner if changed]]
[Voice firewall: applies / N/A]
[Two-PDF standard: maintained / [note]]
[Payment terms: confirmed unchanged]

RISKS:
[What could break. What must be regression-tested.]

ESTIMATED EFFORT: [Hours or days]
```

---

## Stage 5: /tasks

Ordered checklist. One task = one discrete action. Each task names the constitution clause ID it inherits from (e.g., `[NC-2.3]`).

Rules:
- Database migrations first (before any code that depends on the new schema)
- Bridge methods before skills (skills call Bridge methods)
- Skills before PDF output (PDF uses skill outputs)
- Tests before marking complete

Example task list for an AISC-adjacent change:
```
TASK CHECKLIST - [feature name]

[ ] 1. [NC-7.3] Back up bid_pipeline.db before making any schema changes
[ ] 2. [NC-7.2] Write and validate SQLite migration script (if schema change)
[ ] 3. [NC-2.2] Update the affected function in bridge/api.py
[ ] 4. [NC-2.1] Verify AISC master CSV lookup still returns correct properties for 10 test shapes
[ ] 5. Update the affected skill SKILL.md if skill behavior changes
[ ] 6. Run regression test against existing bid test cases
[ ] 7. [NC-6.1] Generate one test bid with both client PDF and GP PDF - verify two-PDF standard
[ ] 8. [NC-5.3] Run owner-voice-check on any new text output
[ ] 9. Compile test build via PyInstaller - confirm no import errors
[ ] 10. Test on Staging (offline mirror DB with synthetic blueprints)
[ ] 11. Owner reviews output on his home desktop - confirm GP figures are correct
```

---

## Stage 6: /implement

Execute tasks in order. Reference spec and task list throughout.

**YourCo-specific implementation rules:**
- Every function that reads from SQLite uses parameterized queries
- Every new Bridge method is documented in `BRIDGE_METHOD_MANIFEST.md`
- Every new skill has a SKILL.md with YAML frontmatter before the Python implementation
- Test builds via PyInstaller before marking any task "complete" - runtime import errors are common and caught only at compile time
- `bridge/api.py` changes require a Bridge method count audit after - confirm method count did not accidentally drop
- Any proposed change to a file in constitution clause NC-13 (protected files) goes through the R4 self-healer human-merge gate (`bridge/self_build_gate.py`). Do not bypass.

**Anti-patterns:**
- Writing a Bridge method before the database migration is validated
- Updating a skill without checking which Bridge methods it calls
- Generating a client PDF without running it through owner-voice-check
- Marking a task complete without testing the compiled `.exe` (not just running `python main.py`)
- Asking an LLM to compute weight, tonnage, or GP percentages

---

## Spec archive

`.specify/specs/[feature-name]-[YYYY-MM-DD].md`
Running index: `.specify/specs/INDEX.md`
