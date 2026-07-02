# 8 Claude Skills for Construction - Estimating, Contracts, Scheduling and More (5iImqMMGjkI)

- URL: https://www.youtube.com/watch?v=5iImqMMGjkI
- Uploader: Tim Fairley (community: Contractor OS / ConstructIQ)
- Duration: 23:35 (1414.9s)
- Frames analyzed: 80 (0.057 fps, full mode, 512px) plus all 80 read visually
- Transcript source: captions (638 segments, complete)

Thesis: Fairley packages eight repeatable construction back-office workflows (contract review, project indexing, go/no-go, procurement packaging, estimate reconciliation, scheduling, document control, O&M manuals) as named Claude "Skills" run inside Claude Cowork, treating AI as a structured workflow engine with human checkpoints rather than a number generator, and he sells the skill pack through his Contractor OS community.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:02 Hook: AI gives inconsistent results and forgets between chats. Skills fix that by storing repeatable workflows in your Claude account.
- t=00:27 Defines a skill as a "nested set of instructions": overall workflow plus examples plus an output format. Lists his own skills (O&M manual, departures/takeoffs, document control, Gantt charts, estimate review).
- t=00:38 Walks the contract-review skill structure: workflow, library of accepted contract terms, output format. Usage: upload contract, say "review my contract using my contract review skill."
- t=01:38 Skill 1: Contract reviews. AI extracts clauses from the head contract, compares to your library of acceptable terms (example: 10% cap on liquidated damages, rise and fall, no consequential loss, set delay-notice period), and formats a departures register. Frames 6-8 show a numbered departures list (clauses 1-29) with GREEN/YELLOW/RED color coding.
- t=02:17 Skill 2: project-indexer (a "meta skill" run at the start of a project). Run in Cowork on a desktop folder: "Using my project indexer, prepare a summary of this project."
- t=02:57 It reads every file, writes a concise per-file summary, and produces a CLAUDE.md "roadmap" telling AI how to read and analyze files. Rationale: without it, Cowork re-reads ~15 PDFs and burns tokens on every simple question.
- t=04:08 Special drawing handling: drawings are hard for AI (visual analysis weaker than text). The indexer splits drawings, analyzes each sheet, and writes a text summary per drawing to reduce hallucination. Note: he reran it in an already-indexed folder, so it got confused (honest failure shown).
- t=04:56 Output: a folder of markdown summaries describing every file/folder, where to find things, and project status. Acts like a per-folder system prompt; extensible with project-specific rules.
- t=05:44 Skill 3: go-no-go skill. On a new bid package, summarize in-scope/out-of-scope, project type, key risks, to support the bid/no-bid decision. Invoked in Cowork: "@go-no-go-review run this workflow and provide a bid summary."
- t=06:36 Aside on the pain of recording: Cowork workflows often take 10 minutes, so he kicks off long runs and jumps between skills.
- t=07:05 Extension demo: Google Antigravity (Google's Cowork equivalent) plus Airtable. He sent his entire drawing set into an Airtable database with per-drawing descriptions, extracted quantities, and raw vector data. Admits it over-summarizes and is "hit and miss," still iterating.
- t=08:48 Back to Cowork: go/no-go produces a go-no-go Excel sheet and a 5-slide PowerPoint of scope in/out.
- t=09:32 Reads the output: "Horizon Business Park Commercial Office Development," 8-story, 12,500 sqm, conceptual estimate required, key inclusions/exclusions (fit-out, loose furniture), commercial terms, risks.
- t=09:59 Plug: skills are hosted in Contractor OS under Classrooms > AI Workflows and Templates; download and install into Claude. ChatGPT/Gemini/Copilot ports in progress.
- t=10:24 Skill 4: procurement-packaging ("data transformation tool"). "@procurement-packaging run this skill and help me develop my procurement strategy."
- t=10:52 Concept: take head contract / client scope / specs / drawings, break into procurement packages, then per package draft a scope of works and specifications. Three steps with a human-in-the-loop checkpoint between each.
- t=11:25 It asks clarifying questions (which trades you self-perform: answer "none"). Stresses customizing with your historic package-breakdown registers so it splits packages your way (utilities, comms/electrical, free-issue items, etc.).
- t=13:00 Step 1 output: scope summary plus extracted requirements. Step 2: suggested package list. Step 3: draft scopes of work when happy.
- t=13:26 More clarifying questions: how to handle provisional sum items (answer: separate nominated package), how many packages (fewer = faster; more = more competition, more interfaces), critical undocumented assumptions (none).
- t=14:33 Skill 5: reconciliation-check (an estimate review skill; he says the name should be better). "Please use my reconciliation-check skill to carefully review my estimate and find gaps/errors."
- t=15:23 What it does: re-reads bid documents and client scope, runs a line-by-line scope check of the estimate, finds calculation errors and implied scope gaps (example: concrete works priced but concrete supply omitted). Purpose: stop under-quoting. He deliberately runs it on a mismatched estimate to show it catching errors.
- t=16:19 Procurement register result shown: preliminaries/site establishment, demolition, earthworks, concrete, structural steel, structures, internal fit-out, mechanical services, electrical services, in an Excel register. He approves and asks for one sample package (building envelope) to keep the run short.
- t=17:16 Skill 6: gantt-chart skill (project schedule from bid documents). "Using my gantt chart skill, please build a project schedule for this project. Assume the list of trades developed in my procurement register." Argues scheduling is lower risk than estimating because a wrong Gantt does not commit you to liquidated damages.
- t=18:33 Shows skill outputs chaining: the procurement package register becomes context for the Gantt chart. The package list becomes the Gantt structure.
- t=18:56 Last two skills shown only in the Claude library (concepts, not full runs).
- t=19:13 Skill 7: document-controller. Runs on a schedule/routine. Scans project registers and the project Gmail address, cross-references new correspondence to registers, updates the correspondence register and project registers. Settable to run daily/weekly via Claude routines.
- t=20:08 Skill 8: om-manual (O&M manual). At project end, compiles technical specs, products used, and outputs a templated Operations and Maintenance manual; missing info flagged in yellow to populate. Customizable with previous examples.
- t=20:50 Returns to procurement output: building-envelope scope of works (project overview, inclusions/exclusions, package scope: material supply, design development and shop drawings, curtain wall manufacture and install, roofing/waterproofing/skylights, external wall), with gaps highlighted yellow.
- t=21:43 Building-envelope pricing schedule: pulls relevant items from the client bill of quantities for that subcontractor.
- t=22:02 Reconciliation report review: executive summary, calculation errors, scope gaps, double counts. Mentions you could link a database of historic project costs for a benchmarking check.
- t=22:51 Gantt output: package-by-package schedule listing key trades. Caveat: with little context given, much of the schedule was AI-generated, so it depends on input data quality.
- t=23:20 Close: skills capture a process once and turn it into a repeatable AI workflow; you must tell it what data to use and what steps to take.

## The 8 skills

### 1. contract-review (shown in sidebar as `contract-review`; departures output as `departures-register`)
- What it does: extracts clauses from a head contract, compares each to a stored library of acceptable positions, and produces a departures register with each clause flagged GREEN/YELLOW/RED.
- Inputs: the contract document (uploaded), plus the skill's embedded library of standard accepted terms and an output format.
- Outputs: structured review of critical findings and a Subcontractor Departures Register (one row per departure, amendment language, pre-populated counter-position). Written as a markdown file (frame 8: "Write the full contract review as a markdown file").
- How invoked: upload contract, then "review my contract using contract-review" (frames 4-5, slash-style "/contract-review" reference).
- Trusts AI for: locating/extracting clauses, matching to terms, drafting amendment language and formatting. Does NOT trust AI to invent acceptable positions; those come from the user-built term library. Frame 8 shows it self-flagging an uncertain drawings reference yellow ("That's a Yellow flag on its own").

### 2. project-indexer (sidebar: `project-indexer`)
- What it does: indexes a project folder; writes per-file concise summaries and a CLAUDE.md navigation roadmap so future queries hit text, not raw PDFs. Splits and text-summarizes drawings per sheet.
- Inputs: a project folder of PDFs, docs, drawings, registers (Cowork "Working folder").
- Outputs: a "0. AI Context" folder with CLAUDE.md (navigation guide + project-specific rules), project.md synthesis, and drawings.md per-sheet breakdown. Progress steps seen (frames 13-17): 1 Check for existing AI Context folder, 2 Discover project folder inventory, 3 Classify PDFs as drawings vs documents, 4 Generate CLAUDE.md navigation guide, 5 Generate project.md synthesis, 6 Generate drawings.md per-sheet breakdown, 7 Write outputs to 0. AI Context folder and summaries.
- How invoked: "use project-indexer on this folder" (frame 14).
- Trusts AI for: classification and summarization. Frame 17 shows a deterministic Python helper (`project-indexer/scripts/read_pdf.py`) doing PDF text extraction rather than relying on the model to read pixels. It asks a scoping question (project-specific only vs include org-level reference material) before proceeding (human checkpoint).

### 3. go-no-go-review (sidebar: `go-no-go-review`)
- What it does: reads a bid/tender package and produces a fast bid/no-bid decision support pack.
- Inputs: bid documents and drawings in a Cowork folder. Per the SKILL.md description (frame 66): "Takes uploaded bid/tender documents (ITT, RFP, specs, drawings, contracts, addenda) and produces a concise Go/No-Go decision pack... 18 key fields and yellow placeholders for conceptual estimate, duration and recommendation."
- Outputs: a one-page Go/No-Go Excel summary sheet (scope, key inclusions/exclusions, unusual requirements, key contract terms, contract form, payment penalties) and a 5-slide PowerPoint. Progress steps (frame 22): 1 Reading bid documents, 2 Build Go/No-Go Excel sheet, 3 Build 5-slide PowerPoint deck, 4 Save outputs and present to user. Outputs named `Horizon_Business_Park_Go_No.pptx` and the Go/No-Go xlsx.
- How invoked: "@go-no-go-review run this workflow and provide a bid summary" (frames 21-23).
- Trusts AI for: summarization and extraction of scope and terms. Conceptual estimate, duration, and recommendation are left as yellow placeholders for a human review panel (does NOT trust AI to set the price or the go decision).

### 4. procurement-packaging (sidebar: `procurement-packaging`)
- What it does: a 3-step procurement strategy builder. Step 1 extracts all project requirements (requirements register). Step 2 breaks requirements into suggested procurement packages plus an allocation matrix. Step 3 drafts scope of works and a pricing schedule per package.
- Inputs: head contract, client scope, specs, drawings/BoQ, plus (optionally) the user's historic package-breakdown registers for customization. Uses prior skill outputs as context (requirements register feeds packaging).
- Outputs: Requirements Register, Package Register and Allocation Matrix (xlsx, `Horizon_Business_Park_Package_Register.xlsx`), per-package Scope of Works (DOCX) and Pricing Schedule (XLSX). Progress steps (frames 41-57): Step 1 Scope extraction and document inventory, Step 1 checkpoint Confirm scope with user, Step 2 Build package register and allocation matrix, Step 2 checkpoint Confirm package strategy, Step 3 Produce package outputs (Scope of Works + Pricing Schedule per package), Verification Quality check all outputs.
- How invoked: "@procurement-packaging run this skill and help me develop my procurement strategy" (frame 39).
- Trusts AI for: requirement extraction, package suggestion, scope drafting. Human-in-the-loop checkpoints at each step; multiple clarifying questions (self-perform trades, scope mode, package count, provisional-sum treatment, undocumented assumptions). Pricing schedule items are pulled from the client bill of quantities, not invented.

### 5. reconciliation-check (sidebar: `reconciliation-check`; he calls it an estimate review / estimate error checker)
- What it does: reviews a completed estimate against the client scope; runs a line-by-line scope check, finds calculation errors and implied scope gaps, and checks double counts.
- Inputs: the prepared estimate (xlsx, e.g. `Construction_Estimate_Green_Project.xlsx`) plus the bid documents and client scope of works.
- Outputs: a Reconciliation Report (xlsx) with an overall verdict (frame 76 shows "DO NOT SUBMIT in current form"), headline findings table (finding / $ impact / severity / action), calculation errors, scope gaps, double counts, and a Reasonableness / Benchmarking tab (metrics vs industry benchmark with verdict and comment, including a steel rate $/t row - frame 77).
- How invoked: "I have gone and prepared an estimate for this project, please use my reconciliation-check skill to carefully review my estimate and find gaps/errors" (frames 52-54).
- Trusts AI for: scope comparison, error detection, benchmarking commentary. Purpose is verification to prevent under-quoting; he notes you can link a database of historic project costs for the benchmark. The AI checks the human-prepared number rather than producing it.

### 6. gantt-chart (sidebar: not separately confirmed by name; invoked via "gantt chart skill")
- What it does: builds an interactive project schedule (Gantt) from bid documents, structured around the procurement package list. Tooltip (frame 62): "Create interactive Gantt chart schedules with editable activities, dates, durations and dependencies... outputs to a React (.jsx) artifact with an interactive UI where activities can be edited inline and exported to CSV."
- Inputs: bid documents plus the procurement register (package list as the schedule structure).
- Outputs: a programme (frames 78-80, "HORIZON BUSINESS PARK - PROGRAMME") with WBS, ~43 activities across 11 phases, predecessors, an interactive editable grid and bar chart, and Export CSV. Includes a STRUCTURAL STEEL (PKG-04) activity line. Shown rendered inside Google Antigravity.
- How invoked: "Using my gantt chart skill, please build a project schedule for this project. Assume the list of trades developed in my procurement register" (frame 63).
- Trusts AI for: structuring durations and dependencies. He explicitly flags this as lower-stakes than estimating and warns the result is heavily AI-generated when little context is provided ("completely dependent on how well you structure the input data").

### 7. document-controller (sidebar: `document-controller`)
- What it does: a scheduled document-control workflow. SKILL.md (frames 67-71): "reads Gmail, cross-references against Excel registers (Correspondence Log, RFI Variation, Submittal, Transmittal), logs new items, updates statuses, and flags overdue/unanswered/incomplete entries." Three-step workflow including Step 3 "Cross-reference" matching emails to register entries.
- Inputs: project registers in the folder, the project Gmail inbox (demo set up with Gmail), client correspondence.
- Outputs: updated correspondence register and project registers; a status update logging new items, updating existing entries, and flagging items needing attention.
- How invoked: set to run on a Claude routine (daily/weekly), not a manual chat command. He corrects "trigger" to "routine."
- Trusts AI for: matching correspondence to register entries (reference similarity, date+sender+topic, thread relationships) and status updates. Simple, low-stakes register hygiene; humans still own the registers.

### 8. om-manual (sidebar: `om-manual`)
- What it does: at project end, compiles technical specs, products used, contacts, and maintenance info into a templated Operations and Maintenance manual. SKILL.md (frames 70-74): drafts an O&M / Owner's Handover Manual using a professional Word template, organized by section, populating known info and flagging missing info in yellow.
- Inputs: project technical specifications, product data, contacts; optionally previous O&M examples for a custom structure.
- Outputs: a templated O&M manual document with sections (building services: electrical, heating/cooling, hydraulic, fire safety, security/access, solar/renewable, gas, underfloor heating; appliances/equipment; external works and landscaping), missing items highlighted yellow for human population.
- How invoked: run the om-manual skill (shown as a library concept, not a full live run).
- Trusts AI for: assembling and templating handover content. Does NOT trust it to fabricate missing product/spec data; gaps are flagged yellow rather than guessed. For residential, commercial, industrial and civil projects.

## On-screen tools and Claude skills (names EXACTLY as shown)

| Item | Where shown | Type |
|---|---|---|
| Claude Cowork ("co-work") | Main app, Opus 4.7 model selector | Anthropic agentic desktop app |
| Google Antigravity ("anti-gravity") | Drawing-to-Airtable + Gantt render | Google's Cowork-equivalent agent IDE |
| Airtable ("Warehouse Drawings - Index" base) | Drawing index database | Database, MCP connector ("Airtable MCP Server" in Cowork Connectors panel, frame 1) |
| Contractor OS / ContractorOS | aiosi.com/contractor-os, Classrooms tab | Community hosting the skill pack |
| `contract-review` | Skills sidebar | Claude Skill |
| `project-indexer` | Skills sidebar | Claude Skill |
| `go-no-go-review` | Skills sidebar | Claude Skill |
| `procurement-packaging` | Skills sidebar | Claude Skill |
| `reconciliation-check` | Skills sidebar | Claude Skill |
| `gantt-chart` ("gantt chart skill") | Invoked via @ tag | Claude Skill |
| `document-controller` | Skills sidebar | Claude Skill |
| `om-manual` | Skills sidebar | Claude Skill |
| `departures-register` | Skills sidebar | Claude Skill (contract-review companion) |
| `subcontractor-quote-analysis` | Skills sidebar (frame 2) | Claude Skill (not one of the 8) |
| `notebooklm` / `notebooklm` | Skills sidebar | Claude Skill (not one of the 8) |
| `wrapup` | Skills sidebar | Claude Skill (not one of the 8) |
| `youtube-packaging` | Skills sidebar | Claude Skill (his own, not construction) |
| `construction-takeoff` | Skills sidebar (frame 3, 65) | Claude Skill (named, not demoed) |
| `pba-1bid-review` / `requirements-extraction` | Skills sidebar | Claude Skill (not demoed) |
| `estimating-workflow` | Skills sidebar | Claude Skill (used in frame 1 cost-estimate task) |
| `schedule-builder` | Skills sidebar | Claude Skill |
| `mcp-builder` | Skills sidebar | Claude Skill |
| `skill-creator` | Skills sidebar | Claude Skill |
| `Cost Data Structurer Skill` | ContractorOS Cost Data Library page (frame 35) | Claude Skill (resource link) |
| CLAUDE.md / project.md / drawings.md / memory.md | Cowork "0. AI Context" / Knowledge Base folders | Context files |

Note: the sidebar shows ~20 skills total; only 8 are the focus of this video. The model selector reads "Opus 4.7" throughout (this is the uploader's UI, not authoritative for our routing). Frame 17 shows a path `claude/skills/project-indexer/scripts/read_pdf.py`.

## What works / what does NOT

Works:
- The skill-as-stored-workflow concept is sound: workflow + examples library + locked output format gives consistency and removes prompt drift between chats.
- project-indexer's core idea (pre-process documents and drawings into text/markdown once, query the index after) is the strongest transferable idea and matches our own project-indexer.
- Human-in-the-loop checkpoints in procurement-packaging (confirm scope, confirm packages, then produce) are a good governance pattern.
- reconciliation-check as an estimate verifier (check the human number, flag gaps and double counts, benchmark) aligns with verify-don't-generate.
- Skills chaining: one skill's output (package register) becomes the next skill's input (Gantt structure).
- Outputs land as real artifacts (xlsx, docx, pptx, jsx) in the project folder, not just chat text.

Does NOT work well (his own admissions):
- Cowork runs are slow: 5-10, sometimes 15 minutes per skill; he constantly context-switches while waiting.
- Re-running project-indexer in an already-indexed folder confused it (no idempotency handling shown).
- The Antigravity-to-Airtable drawing extraction is "hit and miss," over-summarizes, and drops detail; still being iterated.
- The Gantt was largely AI-generated because he gave little context; he warns schedule quality depends entirely on input structuring.
- He concedes some skill names are poor (reconciliation-check is really an estimate review).
- No accuracy/validation layer is shown for quantities or rates; quantity extraction from drawings is acknowledged as unreliable.

## Concrete numbers, rates, file names, examples shown

- Demo projects: "Horizon Business Park - Commercial Office Development" (8-story, 12,500 sqm GFA, 3-level basement, ground-floor retail, Levels 1-7 office, Sydney NSW, ~160 car spaces, ~$52.5M commercial target, 18-month programme, contract form AS4000-1997 amended, Practical Completion 30 Sep 2026, 5.5-star NABERS, 5-star Green Star). A separate "Green Precinct Commercial Office Building" estimate (~$1.5M variance error flagged) used for the reconciliation demo.
- Contract terms example: 10% cap on liquidated damages, rise and fall, no consequential loss, limited liability, set delay-notice period; departures list ran clauses 1-29.
- Folder structure (Cowork project): 1. Project Docs, 2. Contract, 3. Estimate, 4. Correspondence, 5. Registers, 6. Programme, 7. Site; plus Knowledge Base, memory, Project OS, CLAUDE.md (frames 11-19).
- File names: `Drawings_Arch_Elec_Mech.pdf` (drawing set, 31 landscape pages, ~53k vectors/pg), `BILL OF QUANTITIES.pdf` (14 pp), `SCOPE OF WORKS.pdf` (17 pp), `Horizon_Business_Park_Go_No.pptx`, `Horizon_Business_Park_Package_Register.xlsx`, `01 Requirements Register.xlsx`, `03 MEH Pricing Schedule - Rev 02 REVIEWED with Gaps.pdf`, `Construction_Estimate_Green_Project.xlsx`, `Scope of Works.docx`.
- Procurement packages (PKG-01 to ~PKG-11): Preliminaries/Site Establishment, Demolition/Shoring/Piling (Earthworks), Concrete Structure (basement+superstructure), Structural Steel & Metal Decking (PKG-04), Building Envelope (Curtain Wall, Roof, Waterproofing, PKG-05), Internal Linings & Painting, Floor & Wall Finishes, Joinery/Doors & Operable Walls, Mechanical Services, Electrical Services, Hydraulic & Fire Services.
- Airtable "Warehouse Drawings - Index" columns: Drawing Number, Source File, Estimator Summary, What's Shown, Extracted Quantities, Specifications, Risk & Unusual Items, Raw Vector Data, Drawing Image. Sample sheet ranges S120-S001 to S120-S601. Steel detail visible: members/marks (B9, C1, C2, etc.), connections (CFW, cap plate, stiffener), "N12 CONTINUOUS BAR TOP."
- Reconciliation benchmarking tab metrics: Direct $/m2, Total ex GST $/m2, Preliminaries %, Design % of direct, Structure cost $/m2, Margin %, Contract value $/m2 vs industry benchmark, plus a steel rate row.
- Gantt: 43 activities across 11 phases, project lands ~Fri 25 Sep 2026 (~3 working days ahead of the 30 Sep target), Export CSV available.

## Applicability to a structural steel fabricator (Your Company)

Map of the 8 skills to our pipeline:

- contract-review: TRANSFERS. We already enforce contract/terms positions; a stored library of our accepted subcontract terms (LD caps, retention, pay-when-paid, back-charge clauses) compared to a head contract is directly useful for Amber's legal review queue. Caveat: keep our acceptable positions in a versioned, human-owned file, not model memory; flag uncertain clauses, never auto-accept. Low risk, high value.
- project-indexer: TRANSFERS DIRECTLY and overlaps our existing `project-indexer` and `drawing-analyzer` skills. His CLAUDE.md/project.md/drawings.md pattern is the same idea as our 0.ai-context loader. Takeaway: his "split drawings, text-summarize per sheet, query the index" is exactly our pre-process-so-counts-run-against-text-not-pixels rule. Confirms our direction; nothing new to adopt structurally, but the per-sheet "Estimator Summary / Extracted Quantities / Specs / Risk" column schema (from his Airtable index) is a clean template for our drawings.md.
- go-no-go-review: TRANSFERS as a bid-screening front end. We screen bids and identify framing type internally; a one-page go/no-go pack (scope in/out, unusual requirements, contract form, an SF-confirmation flag) fits before our estimate pipeline. Key fit with our rules: leave conceptual estimate as a placeholder for human review, exactly as he does. We would add our SF-sourcing gate and drawing-completeness gate here.
- procurement-packaging: PARTIALLY TRANSFERS. As a fabricator we are usually a single trade (the structural steel + misc/secondary package), not a head contractor splitting the whole job into 11 packages. The whole-of-project package breakdown does NOT transfer. What does transfer: the requirement-extraction + scope-of-works drafting per package, applied to OUR package (steel supply, fabrication, erection, deck supply+install, misc/secondary). The per-package Scope of Works + Pricing Schedule generator is reusable for writing our proposal scope and exclusions, with our locked bid rules and no-supplier-name rule applied.
- reconciliation-check: TRANSFERS STRONGLY and is the best fit for us. An estimate verifier that line-checks the takeoff against client scope, flags calculation errors, implied scope gaps (his concrete-supply-omitted example maps to our "deck supply/install always in scope" rule and "engineering folded into rates" rule), double counts, and benchmarks against historic $/t and $/SF. This is verify-don't-generate applied to estimating. We should mirror its benchmarking tab against our locked BID_RATES (fab $[FAB RATE]/T, erection $[ERECTION RATE]/T, etc.) and our $/SF gate. Critical difference from his demo: our AISC weights and tonnage must come from bridge/aisc_validator.py, never from the model; his version has no equivalent validation layer.
- gantt-chart: PARTIALLY TRANSFERS / LOW PRIORITY. Fabricator scheduling (shop fab sequence, delivery, erection sequence) is narrower than a head-contractor programme. The package-list-drives-schedule pattern is less relevant for a single-trade shop. Useful only as a light erection/fab sequence aid; he himself rates it low-stakes and admits it is heavily AI-generated. Do not let it touch committed dates with LDs without human sign-off.
- document-controller: TRANSFERS as register hygiene. Scheduled Gmail-to-register reconciliation (RFI/submittal/transmittal/correspondence logs) is generic and useful for our awarded-project registers, but it requires a connected mailbox and is governance-sensitive (connector security, least privilege, no acting on instructions embedded in emails). Adopt cautiously, read-mostly.
- om-manual: TRANSFERS WEAKLY. O&M/handover manuals are more a GC/services deliverable; for a steel fabricator the closest analog is a fabrication/erection close-out package (mill certs, weld maps, bolt/torque records, AWS cert references, as-built marks). The yellow-flag-missing-info template pattern is worth borrowing for that close-out package, but the building-services O&M structure he shows does not map to steel.

What does NOT transfer overall:
- Whole-of-project multi-trade package splitting (we are one trade).
- Building-services O&M structure.
- His drawing-quantity extraction approach is unvalidated and "hit and miss"; for us, quantities must run through aisc_validator and confidence tagging, not an Airtable scrape.
- His rates/benchmarks are generic AU commercial ($/m2, NABERS/Green Star); our rates are CEO-locked Q2 2026 and US steel-specific.
- Reliance on the model for any system-of-record number (he shows no validator); our hard rules forbid that for AISC weights and rates.

Single most useful idea for us: the reconciliation-check pattern - a stored estimate-review skill that line-checks our takeoff against client scope, flags scope gaps/double counts/calc errors, and benchmarks $/t and $/SF against history - is the cleanest verify-don't-generate win and maps onto our existing sanity gates, with our AISC validator and locked rates supplying the ground truth he lacks.

## Caveats (frame sparsity; anything unreadable)

- Frame coverage is sparse: 80 frames over 23:35 (~1 frame / 17.7s), and the report itself warns accuracy degrades past 10 minutes. Fast UI actions (exact menu clicks, brief skill-creator/SKILL.md bodies) between frames may be missed. The transcript (captions, 638 segments) is complete and is the primary source; frames corroborate UI/file names.
- The 512px frame width plus the always-on webcam overlay (bottom-right) obscures parts of some screens; small register cell values and some SKILL.md body text are partially legible. Numbers quoted from registers/benchmarks are read as best-legible and may carry minor OCR-style error.
- The `gantt-chart` skill's exact sidebar slug was not captured on a clean frame; it is invoked verbally as "gantt chart skill" and a related `schedule-builder` slug also appears in the sidebar - they may be the same or distinct.
- The Antigravity/Airtable drawing-index demo is an experimental extension the author says is unfinished; treat its capabilities as aspirational, not proven.
- Model label "Opus 4.7" is the uploader's UI string; do not treat as a routing recommendation for our project.
