# Claude Cowork & Skills + Excel - AI Estimating Process (dhinW82s2DU)

- URL: https://www.youtube.com/watch?v=dhinW82s2DU
- Uploader: Tim Fairley (ConstructIQ / "Contractor OS")
- Duration: 12:12 (732.4s)
- Frame count: 80 frames @ 0.109 fps (full mode, 512px wide)
- Transcript source: captions (332 segments)

Thesis: Tim builds an end-to-end construction estimate by running a chain of narrow, single-purpose Claude Cowork skills against a desktop folder, where each skill only "takes data from one format and puts it into another" into pre-built Excel/Word templates, with a human verifying every intermediate output and a deliberately blind second session re-checking the final number.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:01 (frame 1) - Intro. End-to-end construction estimates from Claude Cowork plus Microsoft Excel. Cowork is the new Claude tool that runs in a desktop folder and can read, write, and edit documents. Estimating is framed as: take client bid documents, analyze, work out what to price, then build the estimate in Excel from sub quotes, activity costs, and labor/plant/material rates against quantities of work.
- t=00:46 to 01:33 (frames 6-10) - "Capabilities / skills" = pre-built workflows that can read, write, and run scripts. He shows the Cowork "Customize > Skills" panel. The orchestrator skill is the estimating-workflow skill: extract requirements from bid docs, build a pricing schedule, price each line item from input rates and sub quotes, then final verification and completeness check.
- t=01:33 to 02:07 (frames 11-14) - construction-takeoff skill explained. Splits a drawing set into individual PDFs, runs AI analysis on each PDF using vector data (the text/symbol/structure layer) combined with the image, extracts primary quantities (areas, tag counts), and explicitly does NOT do scaled measurements because AI is unreliable at that. Output goes into an Excel register.
- t=02:07 to 02:45 (frames 15-19) - Folder anatomy. The job folder is "141. Claude Cowork + Excel - AI Estimating > Example Estimate". The bid documents subfolder (2. Bid Documents) holds a Drawings PDF and a Scope of Works.docx. He notes Australia commonly issues a bill of quantities (BOQ) / pricing schedule with bid quantities already in it; this sample does, so the quantity takeoff is optional and AI can derive secondary quantities from the supplied primaries.
- t=02:45 to 03:44 (frames 19-24) - Step 1, requirements extraction. He treats a bid set (drawings, specs, scope) as "a massive list of things we have to price." Example: a schedule with 11 air-conditioning units means pricing 11 units; duct/condensate runs must be priced for supply and install. The Scope of Works header is "Century House Air Conditioning System Addition", 620 Eighth Street, New Westminster, BC; owner City of New Westminster. The SOW contains a Bill of Quantities by CSI-style division (02 Demolition & Site Prep, 03/09 Architectural & Finishing, 23 Mechanical/HVAC) with Item # / Description / Qty / Unit columns.
- t=03:44 to 04:46 (frames 25-31) - Output of the requirements extractor is a Requirements_Register.xlsx. He stresses intermediary verifiable steps: he can read the bid docs in parallel, cross-check the AI's register, delete/edit/add missing requirements, and add an "exclude from scope" flag column for later use in the proposal letter. Claude's chat reports "9 additional scope items were found in the drawing key notes that weren't in the BOQ" plus critical issues flagged as ISS-001 (wall penetration cost difference by cladding type), ISS-013 (no hazmat survey, provisional), and a few line items needing measurement.
- t=04:46 to 06:34 (frames 32-44) - Step 2, quantity takeoff skill. The skill carries a script that extracts vector data from the PDFs and compares it to the rendered image. Counting is done off text tags (AI is reliable at reading text) and verified against the image, not off symbols or scale. Claude reports "vector data extracted from all 31 pages... richest data is on the mechanical plans (M0.02 with 15 tags and 39 dimensions)." Result is a Quantity_Takeoff.xlsx. He repeats his strong opinion: he would NOT rely on AI for the primary takeoff (would not put a "$400,000 bet" on it at t=10:16), only use it to cross-check a human takeoff. Secondary quantities are derived from primary by conversion factors. Stated example (t=06:43 to 06:53): 5 condensing units x 15 m cable per unit = 75 m cable total.
- t=06:34 to 08:24 (frames 47-55) - Step 3, procurement scope-of-works per trade package. A procurement-scope skill edits his template scope-of-works documents (in 1. Templates > Scopes of Work) with the actual project scope and quantities. He generates Mechanical HVAC SOW, Electrical SOW, and Architectural/GC SOW, each with pulled-through quantities, drawing references, exclusions, and a pricing format for sub quotations. He muses (out of scope) about wiring it to an inbox or Airtable to auto-send packages.
- t=08:24 to 09:00 (frames 55-58) - For the demo he has Claude fabricate sample subcontractor quotes into a "3. Subcontractor Quotes" folder, using the docx skill format, with different inclusions/exclusions. Example quote: Fraser Valley Electric Inc. with subtotals for Demolition, Testing & commissioning, Electrical permit & inspections, Shop drawings & submittals, Other Costs, a TOTAL ELECTRICAL (excl. GST), and a QUALIFICATIONS & EXCLUSIONS block.
- t=09:00 to 10:00 (frames 59-66) - Step 4, compile the estimate. Inputs: subcontractor quotes, the quantities, and the activity templates (Activity_Templates.docx) with breakdowns and productivity rates. Claude reads Requirements_Register, Quantity_Takeoff, and Estimate_Template, then builds the priced workbook. He restates the governing principle: AI is only reformatting/repurposing data in small discrete verifiable steps, never doing heavy reasoning.
- t=10:00 to 10:32 (frames 64-70) - The estimate workbook is built. Claude reports "199 formulas, zero errors" and "The workbook has 7 sheets: Cover Sheet, Priced Schedule (all line items with formulas), Detailed Workings, Subcontractor Register, Requirements Register, Pricing Map (9 items flagged), and Assumptions Register (12 assumptions documented)." The estimate (Century_House_Estimate.xlsx) shows sections DEMOLITION & SITE PREP, CONCRETE & STRUCTURAL, ARCHITECTURAL & FINISHING, MECHANICAL/HVAC (SUBCONTRACT), ELECTRICAL (SUBCONTRACT), ARCHITECTURAL TRADES (SUBCONTRACT), TESTING & COMMISSIONING, ending in ESTIMATE TOTAL (Direct Costs). A visible formula is =SUM(G50:J50).
- t=10:32 to 11:41 (frames 71-77) - Step 5, blind verification. He starts a brand-new Cowork session pointed at the same folder and asks "In my folder are bid documents and a construction estimate, can you please prepare a comprehensive check that this estimate is correct." It launches the reconciliation-check skill. He explains the new session is deliberate: a fresh session has no memory of the prior working, so it checks the estimate against the original requirements from scratch instead of trusting its own earlier conclusions/mistakes. (The reconciliation chat at t=10:23 already noted a "double-count between Section 4 (architectural) and Section 7.01 (Pacific Rim subcontract)".)
- t=11:41 to 12:12 (frames 77-80) - Wrap. The whole point of the videos is to show what is possible. Big takeaway repeated: AI works best when each step only converts data from one format to another, and any reusable workflow should be captured as a skill, a template, or saved data in the folder.

## On-screen tools and Claude skills (table; names EXACTLY as shown)

| Item | Type | Where seen |
|---|---|---|
| Cowork | Claude desktop app (tabs: Chat / Cowork / Code) | frames 1-80 |
| document-controller | skill (My skills) | frame 7 |
| procurement-packaging | skill | frame 7 |
| construction-takeoff | skill | frames 7, 11-14 |
| gantt-chart | skill | frame 7 |
| reconciliation-check | skill | frames 7, 77 |
| line-item-pricing | skill | frame 7 |
| schedule-builder | skill | frame 7 |
| requirements-extraction | skill | frame 7 |
| estimating-workflow | skill (orchestrator) | frames 8-10 |
| mcp-builder, skill-creator, algorithmic-art, brand-guidelines, canvas-design, doc-coauthoring, internal-comms, slack-gif-creative | example/library skills (not used) | frames 7-13 |
| Microsoft Word | scope-of-works + trade SOW + sub quote editing | frames 17-18, 23-24, 51, 57-58 |
| Microsoft Excel | registers + takeoff + estimate workbook | frames 27-33, 42-47, 65-70, 78-80 |
| Bluebeam Revu | manual PDF drawing review | frames 21-22, 35-41 |
| Airtable | mentioned only (out of scope) | t=08:02 |
| Opus 4.6 | model shown in composer | frames 9-14, 71-77 |

Skill metadata visible (frame 7, construction-takeoff): "Extract quantities from construction drawings using vector data extraction combined with AI vision. Handles tag counting (light fittings, power outlets, fixtures), area/volume measurement (concrete, flooring), and linear measurement (cable trays, pipes)... Automatically splits multi-page PDFs into individual drawings and needs quantity takeoffs... Extracts vector data programmatically first, then uses AI vision on each page individually to verify and supplement. Produces a professional Excel register of all quantities with confidence ratings, methods, and notes." Core Principles (frames 11-13): "Split first", "Vector data is the foundation", "Vision verifies and supplements", "Primary > Secondary quantities" (measure what can be reliably extracted, then infer secondary from primary), "Excel register output". estimating-workflow Workflow Overview (frames 8-10): 1 REQUIREMENTS EXTRACTION, 2 SCHEDULE BUILDER (create WBS and pricing schedule structure), 3 LINE ITEM PRICING (price each item with workings), 4 RECONCILIATION CHECK (verify completeness, prepare tender letter), each gated by "User confirms".

## The workflow, step by step (reproducible how-to)

1. Create a desktop folder per job and point a Cowork session at it. Subfolders used: `1. Templates`, `2. Bid Documents`, `3. Subcontractor Quotes`, plus output files at the root (frames 50, 61, 63).
2. Drop the client bid set into `2. Bid Documents` (Drawings.pdf + Scope of Works.docx; a supplied BOQ/pricing schedule if you have one) (frame 16).
3. Run the requirements-extraction skill: AI reads scope, specs, and drawing key notes and writes `Requirements_Register.xlsx` (frames 25-33). Human cross-checks in parallel, edits, and adds an "exclude from scope" column.
4. Run the construction-takeoff skill: it splits the PDF into per-sheet PDFs, extracts vector data per page, counts off text tags, verifies counts against the rendered image, and writes `Quantity_Takeoff.xlsx`. A second sheet derives secondary quantities from primaries via conversion factors (frames 42-47).
5. Run the procurement-scope skill: it edits the template trade SOWs in `1. Templates` with the project's actual scope, quantities, drawing refs, and exclusions, producing per-trade SOW docs ready for sub quotation (frames 49-57).
6. Collect (here, fabricate for the demo) subcontractor quotes as docx into `3. Subcontractor Quotes` with inclusions/exclusions (frame 58).
7. Run the compile/line-item-pricing step: AI reads `Requirements_Register`, `Quantity_Takeoff`, `Activity_Templates` (breakdowns + productivity rates), and sub quotes, then builds `Estimate_Template.xlsx` into the priced estimate workbook with live formulas (frames 64-70).
8. Open a NEW Cowork session on the same folder and run reconciliation-check to compare the estimate to the bid requirements with no memory of the prior working (frames 71-77).

## What works / what does NOT

Works: the discrete-step pattern (each skill does one narrow data-shape conversion with a human-verifiable artifact between steps); tag-count takeoff verified against the image rather than scaled measurement; secondary-from-primary derivation via conversion factors for cheap, low-proportion items; templated trade SOWs and a templated estimate workbook so the AI only fills, never invents structure; the deliberately blind second session for reconciliation; requirements register catching scope items in drawing key notes that the BOQ missed (9 found here) and flagging double-counts.

Does NOT work / he refuses: relying on AI for the system-of-record primary quantity takeoff ("would I put a $400,000 bet that AI has done a quantity takeoff? No" - t=10:16); scaled/dimensional measurement off the image (AI unreliable); reading symbols rather than text tags for counting. The takeoff is the one step he says is not safely verifiable and should be done by a human, with AI used only as a cross-check.

## Concrete numbers, rates, file names, Excel structure, examples shown

- Project: Century House Air Conditioning System Addition, 620 Eighth Street, New Westminster, BC; owner City of New Westminster (frame 23).
- Drawing set: 31 pages / "all 31 pages" (transcript + frame 34); the file is `Drawings_(Arch_Elec_Mech).pdf` (frames 16, 61). Richest data on mechanical plan M0.02 (15 tags, 39 dimensions) (frame 34).
- Requirements register found 9 extra scope items in drawing key notes not in the BOQ; flagged issues ISS-001, ISS-013, etc. (frame 26).
- Secondary-quantity example: 5 condensing units x 15 m cable each = 75 m total (t=06:43-06:53).
- Estimate workbook: 199 formulas, zero errors; 7 sheets (frame 70).
- Visible Excel formula: `=SUM(G50:J50)` (frames 69, 78-80).

Template/library files (frame 50, `1. Templates`): `Scopes of Work` (folder), `Activity_Templates.docx`, `Estimate_Template.xlsx`, `Quantity_Matrix.xlsx`, `Quantity_Takeoff.xlsx`, `Requirements_Register.xlsx` (each with a ~lock file).

Requirements_Register.xlsx columns (frames 27-33): Item # / Type (REQ-001...), Description, Qty, Unit, Source Doc (Scope of Works / SOW / Drawings / SOW BOQ), Dwg/Section (e.g. M0.02, A102), Pricing Impact, Notes. Grouped sections "A - SCOPE OF WORKS" (REQ-xxx), then BOQ-xxx, "B - SITE CONDITIONS & CONSTRAINTS", "B - SPECIFICATIONS & STANDARDS" (SPEC-xxx).

Quantity_Takeoff.xlsx, sheet 1 "MECHANICAL EQUIPMENT" (frames 42-43, 45): Ref (PG-M01...), Item (CU-1, AC-1, HV-1, HRV-1...), Description, Qty, Unit (EA), Drawing Ref (M0.02, A102), Confidence (High/Medium), Method (text_extraction vs vision_count), Notes. Equipment counted by text_extraction = High confidence; "DUCTWORK & DISTRIBUTION" counted by vision_count = Medium. Sheet 2 secondary quantities (frames 44, 46-47): Ref, Item, Description, Source Qty, Conversion Factor, Calculated Qty, Unit, Qty Incl. Waste, % Waste, Confidence, Basis. Sections: REFRIGERANT PIPING, CONDENSATE PIPING, ELECTRICAL CABLING, CONDUIT, DUCTWORK, CONCRETE, ARCHITECTURAL FINISHES.

Trade SOW docx structure (frames 51, 57): numbered divisions (e.g. "4. CONDUIT & RACEWAY", "5. DEVICES & FITTINGS") each a table of Ref / Description / Qty / Unit / Notes.

Sample sub quote (frame 58, Fraser Valley Electric Inc.): subtotal rows for Demolition, Testing & commissioning, Electrical permit & inspections, Shop drawings & submittals, Other Costs; TOTAL ELECTRICAL (excl. GST); plus QUALIFICATIONS & EXCLUSIONS.

Final estimate workbook sections (frames 65-69): DEMOLITION & SITE PREP, CONCRETE & STRUCTURAL, ARCHITECTURAL & FINISHING, MECHANICAL/HVAC (SUBCONTRACT), ELECTRICAL (SUBCONTRACT), ARCHITECTURAL TRADES (SUBCONTRACT), TESTING & COMMISSIONING, ESTIMATE TOTAL (Direct Costs). Self-perform lines have material/labour/plant columns; subcontract lines roll up the quote totals. No "AI instructions tab" was visible inside any workbook - the AI instructions live in the skill SKILL.md files (frames 8-13), not in an Excel sheet.

## Applicability to a structural steel fabricator (Your Company)

How Cowork + skills drive Excel here, and what maps to our pipeline:

- The whole architecture is the same shape as ours: a per-job folder, narrow skills, human-in-the-loop gates, and verify-don't-generate. His estimating-workflow orchestrator (extract requirements -> build schedule -> price line items -> reconcile) is a direct analog of our `bid_chain`, and his "AI only converts data formats, never does heavy reasoning" maxim is our verify-don't-generate principle stated almost verbatim. His refusal to bet a real number on an AI takeoff matches our rule that AISC weights come only from `aisc_validator.py` and that a measured member takeoff (not SF x psf) is what moves ROM to bid-grade.
- The Excel data flow worth copying: takeoff CSV/sheet -> requirements register -> priced estimate, with every quantity carrying a Confidence and a Method (text_extraction = High vs vision_count = Medium) and every secondary quantity carrying a Source Qty + Conversion Factor + % Waste + Basis. This confidence/method/basis tagging per row is exactly our confidence-tagging operating rule, and his "Basis" column is a clean pattern for our calc audit trail. We could adopt the Source Qty / Conversion Factor / Qty Incl. Waste columns for our derived items (e.g. connection bolts per ton, weld inches per ton, paint SF per ton from member tonnage).
- The templated workbook approach (Estimate_Template.xlsx with structure pre-built, AI only fills cells and writes 199 formulas) is the safe way to let Cowork touch our GP report and pricing sheets without it inventing layout. Our BID_RATES would live in an activity-template equivalent that the skill reads but never edits, analogous to his Activity_Templates.docx productivity rates.
- The blind reconciliation session (new Cowork session, no prior memory, reconciliation-check skill, compares estimate to original requirements) is a cheap, high-value addition to our flow and is stronger than re-checking inside the same chat. It also caught a double-count and provided-vs-required scope gaps - directly relevant to our count-gap work on the current branch.
- The drawing-side overlaps our `drawing-analyzer` and `project-indexer`: split the merged PDF per sheet, extract the vector text layer, count off text tags, never measure by scale. He confirms the same accuracy boundary our skills already encode.

What does NOT transfer:
- His job is MEP/HVAC fit-out (condensing units, evaporators, HRVs, refrigerant/condensate piping, GFCI receptacles, cladding) with a supplied BOQ; he has no structural-steel member takeoff, no AISC shape database, no per-member weight validation, no tonnage-driven rate gate. None of his quantity logic touches steel weights.
- He uses a supplied bill of quantities to skip the takeoff; our structural-only subsets usually do NOT state gross area or a member BOQ, so we cannot lean on a client schedule the way he does.
- No SF-as-controlling-input discipline, no Tekla model / render / STL mandate, no governance gate on supplier names or precedent projects, no $/SF or $/ton sanity gates. His "exclude from scope" column and proposal-letter step are lighter than our two-PDF (proposal + -GP) and `validate_bid_output.py` requirements.
- His rates are generic activity/productivity rates in a Word doc; ours are CEO-locked Q2 2026 rates in `bid_rates.py` and cannot be a free-form template the AI edits.

Net for us: adopt the row-level Confidence/Method/Basis tagging, the Source-Qty + Conversion-Factor + %-Waste secondary-derivation columns, the template-only estimate workbook pattern, and the separate blind reconciliation session. Keep our structural-specific spine (AISC validator, tonnage, locked rates, SF discipline, Tekla/render, governance gates) untouched.

## Caveats (frame sparsity; anything unreadable)

- The watch tool warned that a 12-minute video is sparsely sampled (80 frames, ~1 every 9 s); fast UI actions between frames (menu clicks, exact cell values) are not all captured.
- Excel cell numbers in frames 27-33, 42-47, 65-70 are mostly too small to read at 512px; column headers and section labels are legible but individual dollar values and most quantities are not. Reported numbers (199 formulas, 7 sheets, 9 extra items, M0.02 with 15 tags/39 dimensions, 5 units x 15 m = 75 m) come from Claude's chat text and the transcript, which are legible, not from reading the cells.
- The "7 sheets" list and the "double-count between Section 4 and Section 7.01" come from Claude's on-screen chat (frames 70, 76) and are quoted as such; I did not independently see all 7 tabs.
- Transcript is auto-captions: minor garbles ("coowwork", "rellying", "Lutos/Lunos") are transcription noise, not product names. The dollar figure cited is a rhetorical "$400,000 bet," not this project's bid total; the actual estimate total was not legibly readable.
- No supplier-name or rate concerns for us here; this is a third-party MEP demo and contains no Your Company data.
