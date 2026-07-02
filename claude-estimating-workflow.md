# Claude Estimating Workflow (Your Company Adaptation)

**Source:** Video transcript "How to Estimate a Construction Project with Claude,"
May 2026. Same author as the Claude routines videos.
**Use when:** Building or refining a Cowork-based estimating process for tender
review, takeoffs, and bid pricing.
**Relationship to existing files:** Extends `bidding-rules.md`,
`bid-pipeline.md`, `rates-and-pricing.md`, `change-order.md`. Pairs with
`claude-routines-construction.md` (autonomous routines run on top of this).

## Core thesis

Do not overuse Claude. AI has no common sense (no theory of mind), no memory
between sessions, and no understanding of your project. It is a next-token
predictor. The estimator does the thinking. Claude does the time-consuming
data moves: spreadsheet to spreadsheet, format to format, document to document.

Every AI step must follow this pattern:
1. Narrowly define the task
2. Give the background context
3. Define the process to follow
4. Specify the output template

You can only do that if you understand the project deeply yourself.

## The three-phase workflow

### Phase 1: Understand the scope

The estimator reads the tender package by hand. No AI summaries of drawings,
specs, or scope of works for multi-million-dollar work. A couple of hours of
careful reading saves the entire bid downstream.

Setup steps:
- Create a new Cowork PROJECT (not a standalone chat) pointed at the folder
  containing drawings, specs, and scope of works.
- Run the existing `.claude/skills/project-indexer/SKILL.md` skill. It
  writes a per-bid `_bid_context/` folder holding `project.md`,
  `drawings.md`, `memory.md`, and a per-bid loader. Naming note: the
  project-level `0.ai-context/` already exists at the Cowork project
  root and acts as the project loader. To avoid collision, per-bid
  context lives under `_bid_context/`, not `0.AI-context/`.
- The project-level `0.ai-context/CLAUDE.md` already pulls business
  context (rates, SOPs, production library, capability surface) into
  every chat. No new per-bid `CLAUDE.md` is required.

Estimator writes two documents by hand:
1. **Clarification register.** Every item in the docs that is unclear,
   contradictory, or missing. These become questions to the client.
2. **Pricing schedule (returnable schedule).** The line-item breakdown the bid
   will present to the client. This is the most important document in the
   workflow because it is how scope gets priced and presented.

Then run a `requirements-extraction` skill to CHECK that hand-written work.
Claude sweeps the tender package, lists every requirement the client is asking
to be priced, and flags anything missing from the clarification register or
pricing schedule. AI checks the human, not the reverse.

Status: `requirements-extraction` is TO BUILD. Priority: build before
the reconciliation skill since the requirements register it produces is
the input the reconciliation skill reads.

### Phase 2: Direct costs (takeoffs + assemblies + rates)

All estimating lives in an Excel workbook with: project summary, indirect cost
page, direct cost page, and linked libraries for labor, plant, material,
subcontract. A setup skill populates this template from the pricing schedule
and clears prior-project data.

**Assemblies before takeoffs.** The slow part of takeoffs is not measuring,
it is building the assembly list (slab depth, wall type, finish, rebar spec).
The author's `assemblies` skill takes a base/standard assembly library,
reads the `0.AI-context` folder for material tags and specs called out on the
drawings, and customizes the standard list for this specific project.
Example: turn "standard blockwork wall" into "wall type 3 per drawing A-201."
The estimator cross-checks the output. AI customizes, human verifies.

**Measurement tool ruling (Owner, 2026-05-29).** During the ZZ Takeoff
free trial week, ZZ Takeoff is the measurement tool for the trial bid.
Cowork remains the BOQ system of record: it extracts tabular schedules
(column schedule, beam schedule, joist schedule, anchor schedule) via
pdfplumber, camelot, and Claude Vision. PlanSwift drops to third-party
verification only, called when the user explicitly requests it. After
the trial week closes, revisit the tool choice before locking it in.

**Populate direct costs.** Export takeoffs to CSV. Import to Cowork. Run an
`estimating-workflow` skill: "using my assembly library, populate my Excel
estimate with this data." Claude moves data from CSV to direct cost sheet.
Any rate Claude does not know gets flagged for a subcontractor quote.

**Claude for Excel is separate.** It cannot read `CLAUDE.md` or the project
knowledge folder. It is the base model with spreadsheet awareness. Workaround:
add an `AI Instructions` TAB inside the workbook itself describing the
workbook layout. Then "update material rates from this attached quote" works.

### Phase 3: Indirect costs, letter of offer, reconciliation

**Indirect costs.** Key input is project duration. Self-performed work uses
total labor hours divided by crew size. Subcontract work needs a
`schedule-builder` skill that pulls historical durations and sequencing.
Recurring overhead (PM salary, supervision, site costs) gets allocated against
duration.

**Letter of offer.** AI populates a standard letter from the pricing schedule
with inclusions and exclusions. The non-negotiable rule: every requirement in
the client's tender package must be either priced inside the estimate OR
explicitly listed as an exclusion in the letter. Nothing in between. This is
how you close scope gaps.

**Reconciliation skill.** Final check. Reads the letter of offer, the original
requirements register, and the estimate. Flags any client requirement that is
neither included in the price nor excluded in the letter.

## Skills inventory from the video

| Skill | Purpose | Phase | Status |
|---|---|---|---|
| project-indexer | Builds per-bid `_bid_context/` from drawings/specs | 1 | BUILT - `.claude/skills/project-indexer/SKILL.md` |
| drawing-analyzer | Splits PDF, extracts text layer, counts tagged items | 1 | BUILT - `.claude/skills/drawing-analyzer/SKILL.md` |
| requirements-extraction | Cross-checks clarifications and pricing schedule | 1 | TO BUILD - priority 2 |
| contract-review | Reviews contract terms (mentioned, not detailed) | 1 | TO BUILD - priority 5 |
| assemblies | Customizes standard assembly library to this project | 2 | TO BUILD - priority 3 |
| estimating-workflow | Populates Excel direct costs from takeoff CSV | 2 | TO BUILD - priority 4 |
| schedule-builder | Estimates project duration from historical data | 3 | TO BUILD - priority 6 |
| reconciliation | Checks scope coverage across estimate/letter/requirements | 3 | TO BUILD - priority 1 (highest leverage; catches missed scope) |

Build priority confirmed by Owner 2026-05-29: reconciliation first
(catches scope gaps before submit), then requirements-extraction (feeds
reconciliation), then assemblies, then estimating-workflow,
then contract-review, then schedule-builder.

When the reconciliation skill is built it must consume Ivan's
calibration data at `data/calibration/ivan_confirmed_2026Q2.json` and
the bid recon rules logged 2026-05-27 (anchor count, joist gate, anchor
diameter, connection allowance, building SF). Without those inputs the
skill misses the failure modes Ivan already flagged.

## Mapping to Your Company reality

This video is general construction. Your Company is structural steel fab. Direct
translation needs five adjustments.

1. **Assemblies = connection details + member families.** Instead of "wall
   type 3" the assemblies map to "moment connection type A," "shear tab to
   W12x26," etc. The AISC v16.0 database (already processed to
   `aisc-shapes-v160-US.csv`) is the equivalent of the standard library.
2. **Takeoff method (resolved 2026-05-29).** Your Company does steel
   takeoffs by member count and tons, not by area. The Excel workbook
   structure stays. For the next week ZZ Takeoff (free trial) is the
   measurement tool on the trial bid. Cowork remains the BOQ system of
   record and extracts tabular schedules. PlanSwift is third-party
   verification only. After the trial week the tool choice gets
   revisited before being locked in. CSV import step is unchanged.
3. **Rates already exist.** Shop $145/hr, Engineering $175/hr, Overhead 1.15x,
   11 hrs/ton blended baseline. The `estimating-workflow` skill should
   reference `rates-and-pricing.md`, not external libraries.
4. **Letter of offer = the bid proposal.** Your Company already produces two
   PDFs per bid (client proposal + GP report). The "explicit inclusions and
   exclusions" principle should be enforced on the client proposal PDF.
5. **Engineering line item conflict.** Existing rule: engineering folded into
   fab + erection rates, never line-itemed. The video says every requirement
   must be in the estimate or excluded in the letter. These do not conflict.
   Engineering is in the price (rate-loaded), so it lives in the estimate.
   The exclusions list just needs to be clear about what engineering scope
   is and is not provided.

## Where this changes the existing Your Company workflow

1. Add a per-bid `_bid_context/` folder generation step per bid via the
   existing `project-indexer` skill. The project-level `0.ai-context/`
   stays as the Cowork project loader (unchanged). Currently bids start
   without a structured drawing index at the per-bid scope.
2. Formalize the clarification register as a deliverable on every bid before
   pricing begins. Tracks unanswered questions in one place.
3. Build the requirements extraction skill specifically for Marathon
   Petroleum-style RFPs first (those are the bids that matter most).
4. Add an `AI Instructions` tab to the standard bid workbook so Claude for
   Excel can update rates from emailed quotes without breaking formulas.
5. The reconciliation skill is the highest-leverage net new item. It catches
   missed scope before submission, which is exactly the failure mode
   `bidding-rules.md` exists to prevent.

## Open questions for Owner or Joseph

1. Where does the business context live? Notion is what the video uses. Nano
   Cube uses Cowork project knowledge plus `CLAUDE_v3_owner_voice_calibrated`.
   Confirm that the Cowork project root is the single source for business
   context, then point any future `CLAUDE.md` at it.
2. Takeoff software decision. RESOLVED 2026-05-29: ZZ Takeoff for the
   trial week, Cowork stays BOQ system of record, PlanSwift drops to
   third-party verification. Revisit at end of trial week.
3. Priority order for building the seven skills above. RESOLVED
   2026-05-29: reconciliation (1), requirements-extraction (2),
   assemblies (3), estimating-workflow (4), contract-review (5),
   schedule-builder (6). project-indexer and drawing-analyzer are
   already built.
