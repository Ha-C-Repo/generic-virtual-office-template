# How to Estimate a Construction Project with Claude AI - Take-Off to Priced Bid (VrSs8mGI8ss)

- URL: https://www.youtube.com/watch?v=VrSs8mGI8ss | Uploader: Tim Fairley (ConstructIQ / Contractor OS) | Duration: 24:53 | Frames: 80 @ 512px | Transcript: captions (691 segments)
- Thesis: Use Claude across the whole estimate (scope, takeoff, price, letter of offer) but only for the time-consuming data-moving and the cross-checking. The estimator owns the judgement, because the biggest trap in AI estimating is over-relying on a model that has no common sense and cannot be the system-of-record number.

NOTE: this report was authored in the main session (the video was watched in-chat) so the rest of the 14-video corpus could be batch-processed in isolated subagents. Same full-depth method: all 80 frames read, full caption transcript reviewed.

## Chronological walkthrough (with t=MM:SS anchors)

- 00:00 to 04:12 - Thesis and warning. The workflow combines Excel, Claude for Excel, Claude Cowork, and pre-built Claude skills. The biggest trap is overusing Claude for estimating. Models are next-token predictors with no common sense, "amnesia," and no theory of mind. The viral "my car is dirty, the car wash is a 5-minute walk away, drive or walk?" example is shown (1:33 to 2:48 in a Word doc and a Claude chat) where the model told people to walk. His own example: on a battery project he asked Claude to check a commissioning estimate for gaps and got 50 recommendations already covered in the construction cost or overhead. Takeaway: narrowly define the task, give background, define the process, specify the output template; only possible if you deeply understand the project yourself.
- 04:12 to 11:10 - Phase 1, Understand the scope. Read the tender package, drawings, and scope yourself (a couple of hours); do not trust an AI summary. Set up a Cowork project pointed at the folder of drawings/specs/scope with the instruction "Help me prepare an estimate" (Cowork "Use an existing folder" dialog, 5:17 to 6:13). Run a project-indexer skill that builds a `0.AI Context` folder with a markdown representation and summaries of every drawing (6:32 to 7:47; files include `drawings_split`, `coordination_issues.json`, `cross_references.json`, `drawings.md`, `sheet_classification.json`, `symbol_library.json`, and a `CLAUDE.md`/`project.md`/`drawings.md` context set). Business context is managed in Notion (a "Bradman Construction" page with a "Production Rate Library" of concrete and partition rates, shown 7:47 and 21:28). He creates two files himself first: a clarification register and a returnable pricing schedule (1.Understand folder, 7:28 to 9:39). Then he has Claude check his work with "can you review the clarification register using requirements-extraction" (skill definition visible at 9:57: "Extract all pricing requirements from tender documents as a structured BOQ, and generate a clarification/RFI register").
- 11:10 to 18:09 - Phase 2, Pricing schedule, assemblies, takeoff. Estimating happens in an Excel workbook (project summary, indirect-costs page, direct-cost structure, links to labour/plant/material/subcontract libraries; "Project Summary / Key Quantities" and "Total Cost Breakdown" sheet at 12:45, self price about $156,235). A skill populates the template and clears prior-project costs. Strong opinion: the slow part of takeoff is setting up and customizing assemblies, not measuring. Fix: a base assembly library + an "assemblies" skill that reads the `0.ai` context and the material specs/text tags in the drawings and customizes generic assemblies to the project (generic wall to "wall type 3", slab to its specified mesh/reinforcement). AI extracts specifications and tags; it does NOT count. ZZ Takeoff (browser-based, "Ask Gemini" button) cannot yet import assemblies from Excel, so he pastes the list in (with formulas and wastage) and measures manually (13:04 to 16:11; 200mm hollow blocks 105,326; GARAGE and TOOLS rooms labelled). Export takeoff as CSV BOM + labour hours, import into Cowork: "using my assembly library populate my excel estimate with this data using my estimating-workflow" (17:25 to 17:44). The estimating-workflow skill enters everything into direct cost and flags any rate it does not know (example: a hoarding plywood panel, 12 units at $35) so he can chase a quote or document an assumption (subcontractor/material libraries with rate-status tags Standard/Trade rate/Assumed/Mid-range commercial at 18:03 to 19:17).
- 18:09 to 24:50 - Phase 3, Indirect costs and outputs. For subcontractor quotes he switches to Claude for Excel (not Cowork) because Claude for Excel is the basic model that knows spreadsheets but not construction and cannot see CLAUDE.md, so he keeps an "AI instructions tab" inside the workbook describing its structure. Indirect costs hinge on duration: self-performed = total labour hours / assumed crew (indirect sheet at 20:13: Total Labour Hours 420, Duration 13.1 days / 3 weeks); subcontract = a schedule-building/gantt-chart skill reading a business data library of standard task durations. Final deliverable: a Letter of Offer from a standard template (22:43 to 23:57: "USD $ [TOTAL - TO BE INSERTED FROM ESTIMATE]", What's included, Exclusions, Assumptions priced). Key principle: every client requirement is either priced in the estimate or explicitly excluded in the letter of offer, so there are no scope gaps. Closes by running a reconciliation skill that cross-checks the letter of offer against the original requirements register and the estimate (23:01).

## On-screen tools and Claude skills

| Tools on screen | Claude skills referenced |
|---|---|
| Excel (with Claude + Bluebeam add-ins), Claude for Excel, Claude Cowork (model selector showing Opus 4.7), Notion, Bluebeam Revu, Openspace / ZZ Takeoff (browser, "Ask Gemini"), Word, ContractorOS (skool.com) | project-indexer, requirements-extraction, assemblies, estimating-workflow, schedule-builder / gantt-chart, reconciliation-check, contract-review, subcontractor-quote-analysis, document-controller, line-item-pricing, drawing-analyser, mcp-builder, skill-creator, setup-cowork |

## The workflow, step by step

1. Read the tender set yourself; build personal understanding of scope.
2. Create a Cowork project on the drawings/specs/scope folder; turn on Memory.
3. Run project-indexer to build the `0.AI Context` folder (per-sheet drawing markdown + summaries + JSON indexes).
4. Hand-write a clarification register and a returnable pricing schedule (first cut).
5. Run requirements-extraction to cross-check the register and schedule against the indexed scope.
6. Populate the Excel estimating template via a skill (clears old direct costs).
7. Build/customize assemblies via the assemblies skill (AI customizes generic assemblies from drawing tags; no counting).
8. Measure quantities manually in takeoff software; export CSV BOM + labour hours.
9. Import the CSV into Cowork; estimating-workflow populates direct costs and flags unknown rates.
10. Get subcontractor quotes via Claude for Excel using the workbook AI-instructions tab.
11. Estimate duration (labour-hours method or schedule-builder skill) and allocate recurring indirect costs.
12. Generate the Letter of Offer from a template (inclusions/exclusions).
13. Run reconciliation-check to confirm every requirement is priced or excluded.

## What works / what does NOT

- Trusts AI for: per-sheet drawing indexing/summaries, requirements extraction as a cross-check, customizing assemblies from text tags, moving takeoff data into the estimate, flagging unknown rates, drafting the letter of offer, final reconciliation.
- Refuses AI for: reading the set in place of his own review, COUNTING quantities off drawings ("AI is not reliable at this step, so do it manually"), supplying the system-of-record price or rates.
- The core discipline: AI does the time-consuming plumbing while the estimator steers and owns the numbers.

## Concrete numbers, rates, file names, examples shown

- Worked example: an industrial garage building (drawings "INDUSTRIAL GARAGE"; schedule headed "Garage / E-Learning / Australia"). Self price about $156,235 (13:41). An office-fitout workbook ("Office Fitout - Suite 4, 18 King Street") also appears in the opening frames.
- 200mm hollow blocks quantity 105,326 in the takeoff tool (13:04 to 16:11).
- Indirect sheet: Total Labour Hours 420; Duration 13.1 days / 3 weeks (20:13).
- Rate-flag example: hoarding plywood panel, 12 units at $35 (18:21).
- Files: `Clarification Register.xlsx`, `Returnable Schedule.xlsx`, `0.AI Context` folder (`CLAUDE.md`, `project.md`, `drawings.md`), `drawings_analysis` folder JSON indexes.

## Applicability to a structural steel fabricator (Your Company)

- Transfers strongly: the Cowork-project-on-the-bid-folder pattern, project-indexer to a `0.ai-context` folder, requirements-extraction as a cross-check, the rate-flagging behaviour (flag any unknown rate rather than inventing one), the letter-of-offer inclusions/exclusions discipline, and the final reconciliation pass. These mirror Your Company's existing 0.ai-context/project-indexer/governance design and the verify-don't-generate rule.
- Transfers with adaptation: "assemblies" customized from drawing tags maps onto building member assemblies from schedule marks, but our member weights and tonnage must come from aisc_validator, not an LLM-customized assembly.
- Does NOT transfer: his cloud-Notion cost/rate store (Tier 1 confidentiality breach for us - MATERIAL_COSTS, supplier names, BID_RATES never leave the repo); general/civil/fitout assembly content; any reliance on the takeoff tool's "Ask Gemini".
- Steel-specific gap he does not cover: AISC member takeoff and tonnage. Our pipeline must keep the member takeoff (schedules + framing-plan marks through aisc_validator) as the bid-grade spine; his SF-times-rate and assembly approach is conceptual-grade at best.

## Caveats

- Frame coverage is sparse at 24 minutes (about one frame every 18 seconds), so a single fast screen (an exact formula or a specific rate cell) can fall between frames. The full transcript is intact, so the spoken method is solid.
- The model selector reads "Opus 4.7" in the Cowork panes; the transcript also references "Opus 4.7."
