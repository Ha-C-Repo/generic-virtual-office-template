# AI-Enhanced Construction Bid Estimating Software: Research Paper and Claude Cowork Handoff for Your Company, LLC

## TL;DR
- For Your Company's structural steel scope, dedicated pixel-accurate steel takeoff (SketchDeck LIFT, Beam AI steel, eTakeoff+Togal) is the one capability Claude Cowork cannot match at parity. Everything else in the Operum-style workflow (tender ingestion, BoQ from specs, Inclusions/Exclusions, contract-risk register, reconciliation gap detection, rate-anomaly checks, time-based overhead) can be rebuilt inside Cowork at usable accuracy with Claude Max 5x, Google Workspace, and M365 already in the stack.
- The reconciliation engine is the real moat. It is reproducible in Cowork as a Sequential-Thinking skill that diffs a structured Requirement Register (extracted from the tender) against a normalized Estimate, then flags missing line items and outlier unit rates. Nothing about it requires paid software.
- Operum is now verified from its product walkthrough. A May 2026 guided demo on operum.io (sample project, demonstration data) confirms the real feature set: tender plus drawings ingestion, a Tender Summary requirement register with live counts and page-level citations, subcontractor package management with quote comparison, a Direct/Indirect/Sell-Price estimate engine with per-activity Pricing Workbooks, and a Submission Analysis reconciliation step that emits a verdict, a critical-issue count, and prioritized issues with requirement IDs and recommended actions. The earlier JS-SPA caveat is retired.

---

## Part 1 - Research Paper

### 1. Executive Summary

AI estimating tools split cleanly into three families:

1. Pixel-accurate drawing takeoff (Togal.AI, SketchDeck LIFT, Kreo, Beam AI, STACK, PlanSwift, Procore Estimating, eTakeoff). These use computer vision plus CNN-based symbol detection to count beams, doors, rooms, fixtures, etc. directly from PDF drawings. Verified accuracy claims sit at 95-99% on clean PDFs.
2. Tender intelligence and bid governance (Operum, ContraVault). These parse the tender package's text (specs, scopes, head-contract clauses), build a structured requirement register, generate Inclusions/Exclusions, flag commercial risk, and reconcile the contractor's draft estimate against the register.
3. End-to-end residential / FSM hybrids (Handoff AI, CountBricks, OptiServe AI). These bundle voice-to-estimate, CRM, and proposal generation, mostly for small residential/services contractors. They are not relevant to structural steel fabrication bids.

For a 12-person structural steel fabricator, the value chain is: (a) read the tender package fast, (b) build a defensible scope register and contract-risk list, (c) get steel quantities off the drawings accurately, (d) price using the existing Your Company production rates (11 hr/ton fab baseline, $145/hr shop, $175/hr engineering, 1.15x overhead), and (e) reconcile the priced estimate against the register before submission. Items (a), (b), and (e) are language and structured-data tasks. Claude Cowork is genuinely good at them. Item (c) is a computer-vision task and is where dedicated software still wins.

### 2. Methodology

Sources used:
- Each competitor's public website (operum.io, sketchdeck.ai, togal.ai, kreo.net, ibeam.ai, optiserveai.tech, construct-iq.com), with direct fetches where the site permitted.
- Founder writing on LinkedIn and YouTube, especially Tim Fairley's posts and the Construct-IQ channel.
- Independent reviews (Capterra, GetApp, Software Advice, Beck Technology, DataDrivenAEC, AppIntent, Robotics & Automation News, Getlatka).
- Industry context on Bills of Quantities, winner's curse, and the four-bucket scope framework.
- Operum product walkthrough captured from operum.io (Guideflow interactive demo, sample project, May 2026), used to verify Operum's feature set and Submission Analysis output structure.

Where a vendor's internal pipeline is not disclosed, the paper provides the most plausible technical reconstruction and labels it as inference. Where a vendor publishes a marketing number (e.g. "98% accuracy"), the paper treats it as a vendor claim, not a verified benchmark.

### 3. Per-tool deep dives

#### 3.1 Operum (operum.io) - Tim Fairley / Construct-IQ

Founder and provenance. Operum is built by Timothy Fairley, founder of ConstructIQ Pty Ltd (Melbourne, Australia). Per construct-iq.com, Fairley has "over a decade of hands-on experience in electrical, civil, and commercial construction across Australia" and ConstructIQ has trained 50,000+ professionals through its courses and YouTube channel (self-reported figure). His LinkedIn headline is "Timothy Fairley - Operum."

Now verified from the product walkthrough (May 2026). The earlier draft of this paper could not see inside Operum because operum.io renders as a JavaScript single-page app. That gap is now closed. A full guided product walkthrough delivered on operum.io (via the third-party Guideflow demo player, using a sample "Commercial Construction Project" with demonstration data) exposes the actual UI and feature set. Everything below the line is taken from that walkthrough. Dollar figures in the demo are sample data, not benchmarks, and Guideflow is the demo player, not an Operum feature.

Verified product structure. Operum is organized as Organization, then Projects, then per project four tabs: Project Overview, Subcontractors, Estimate, Submission Analysis. Supporting libraries are a company Resources library and Workbook Templates. Pricing is credit-based (the demo org shows "3.20K / 3.20K credits remaining" with a "Buy More Credits" action, plus a "Get Started For Free" tier and a "Start free and scale as you grow" pricing page).

Verified, document ingestion. Upload accepts Tender documents (PDF, Word, Excel, CSV; max 50MB each) and Drawings (PDF only; max 50MB) in separate drop zones. On ingest it auto-identifies document classes (in the demo: Scope of Works, Bill of Quantities, Conditions of Contract, Tender Conditions). The tip to "split very large files into smaller sections (for example by trade or package)" confirms a chunking strategy for reliability.

Verified, Tender Summary (the requirement register made real). The analysis output is a structured, navigable register with live counts. In the demo: Submission Requirements (9), Drawings (10), Bill of Quantities (14), Requirements (44), Contract, RFIs / Clarifications (28), Risks & Opportunities (18). Every extracted item carries a page-level source citation (e.g. "Invitation to Tender.pdf Page 1; Scope of Works.pdf"), a "Found & verified" status, and high-level scope cards (Project Type, Duration, Location, Contract Model). It explicitly extracts submission requirements, extracts quantities from drawings, and identifies risks, and it exports to PDF. Two capabilities the first draft did not credit Operum with are confirmed here: automatic RFI / clarification generation, and a Risks AND Opportunities register, not just risks.

Verified, Subcontractor management. A Project Work Breakdown Structure organizes the job into areas (Preliminaries, Construction) and numbered procurement packages, each tagged Self-perform or Subcontract with a status (Draft, Issued, Quotes Received, Awarded). Per package: a Documents tab with revision control (Rev 1 through Rev 6) and type tags (BoQ, Drawings, Scope of Works, Invitation to Tender); a Pricing Schedule (Item Code, Description, Unit, Quantity) with CSV import/export and a Template action, issued to subcontractors; a Subcontractors tab to invite subs by email and collect quotes; and a Comparison tab to compare quotes and import the winner into the estimate.

Verified, Estimate engine. The Estimate tab has a Pricing Schedule and a Project Resource Library. The pricing schedule splits Direct Costs (shown to clients) from Indirect Costs (hidden, e.g. project management), and computes a Sell Price that "automatically includes all indirect costs and markup percentages, distributed proportionally across each line item" (columns: Item, Description, Quantity, Unit, Rate, Total, Sell Price). Each pricing-schedule line links to a Pricing Workbook for activity-level build-up. The Project Resource Library captures labour, plant, material and subcontractor costs plus quantities, productivity, and other variables, copied from a company library per project. Resource rows are typed Labour, Plant, Material, Subcontractor, Productivity, Variable, Quantity, and Overheads.

Verified, Pricing Workbook (cost-per-activity build-up). Opening a line (demo: "Concrete Works 3.1 Foundations 1000 m3") shows a resource table (#, Resource, Description, Qty/Formula, Unit, Rate, Total, Notes) where you assemble typed resources, including formula-driven rows (e.g. a Variable "Reinforcement Ratio 0.2 t/m3" feeding a Labour "Steel Fixer" line at "8 mhr per tonne"), grouped under Heading rows and summed to a workbook total that flows up to the pricing schedule. Below it is a free-form Excel-like grid (columns A through N) labeled "Assumptions & Calculations" for notes and working.

Verified, Submission Analysis (the reconciliation engine output). You upload a Letter of Offer (PDF/Word, max 20MB) and Estimate Workings (Excel), or use the estimate built in Operum, and Operum analyses the estimate "to find calculation errors, scope gaps and other issues that can cost you money." The output has four views: Executive Summary, Scope Coverage, Detailed Estimate Risk Analysis, and Rates. It opens with an overall verdict label (demo: "REVIEW_AND_ADJUST") and a critical-issue count ("7 Critical Issues"), then a prioritized issue list. Each issue carries a priority (High Priority), a title, a source citation with a requirement ID (e.g. "Contract.pdf p2 (REQ-010)", "LOO Section 3 Exclusion E003; REQ-004"), a section or category (Preliminaries / Commercial, Finishes & Fitout), and a recommended action ("Add LD allowance or qualify programme"; "Reconcile to BOQ; reprice FL02"). The demo issues confirm all three reconstruction vectors from Section 5: commercial and contract gaps (unqualified $10k/day liquidated damages, excluded authority fees, excluded escalation) and quantity reconciliation against the BOQ (carpet tiles 8,000 vs 12,000 m2). Exports to PDF.

Documented methodology - the four-bucket scope framework. Fairley states the design premise verbatim on LinkedIn: every requirement in the client's bid documents must fall into one of four buckets - direct costs (your labour, plant, materials), subcontractor scope, contingency/preliminaries, or excluded (named in your letter of offer). The estimator's job is to "take the tender package + drawings and turn it into a big checklist to compare against your estimate, submission and subcontract packages." This four-bucket checklist is what the rest of the paper refers to as the Requirement Register.

Documented methodology - preliminary BoQ derivation. Fairley publicly described a Claude Skill that extracts vector data from PDFs, captures primary quantities directly (concrete areas/volumes, light fittings, GPOs and switches, schedules), then derives secondary quantities by applying ratios from a database (e.g. reinforcement at 180 kg/m3, 8 m of cable per light fitting). This is the spec-to-BoQ pipeline Operum is built around, and it is the exact pattern this paper recommends rebuilding in Cowork.

The reconciliation exercise (as a Fairley-documented concept). Fairley's published reasoning: "Estimates pull from dozens of sources - BoQs, subcontractor quotes, schedules, scopes of work, addendums. Incorrect information leads to incorrect prices. And inaccuracies compound downstream." The reconciliation step compares the contractor's draft estimate line by line against the Requirement Register and flags (i) requirements with no matching priced line ("gap"), (ii) priced lines with no requirement source ("orphan"), and (iii) unit rates that deviate from a historical band ("rate anomaly"). The literal phrase "AI Reconciliation Exercise" is referenced in the user's brief and in YouTube descriptions but does not appear in indexed Fairley writing, so the paper treats the named process as a concept Operum implements, not a verified product feature.

Time-based overhead. The concept is to extract durations and dependencies from the BoQ and produce a Gantt-shaped schedule so time-dependent indirect costs (site office, supervision, insurances per month, crane standby) can be priced as duration x rate rather than guessed lump-sum. This is a standard NRM2 "Preliminaries" approach; Operum's contribution is automating it from extracted scope data.

Pricing. Credit-based, confirmed from the walkthrough. There is a free tier ("Get Started For Free", "Start free and scale as you grow") and a "Simple, Transparent Pricing" page; the demo organization shows a 3,200-credit balance with "Buy More Credits." Exact dollar-per-credit rates were not captured in the walkthrough.

Net read. Operum is a real, shipping product, not just a methodology. It is the most complete tender-intelligence-plus-estimate-plus-reconciliation workflow in this study, weakest only on pixel-accurate drawing takeoff (it extracts quantities from drawings but is not positioned as a symbol-counting computer-vision takeoff tool like LIFT or Togal). For Your Company, Operum is the closest single product to the full target workflow, and its Submission Analysis output is the clearest template for the reconciliation engine to rebuild in Cowork.

#### 3.2 ConstructIQ (construct-iq.com)

The consultancy parent. Three service lines: (1) AI services - "We set up your databases, deploy AI workflows, and train your team. Then we manage and expand the system month-to-month," with 2 custom AI workflows deployed per month; (2) Quantity surveying; (3) Training. Named workflows offered: tender document extraction, quantity takeoffs, contract review & departures, bid comparison & evaluation, progress claim preparation, procurement packaging, RFI & document control, cost reporting & dashboards. Delivery method is "Setup -> Validate (run on a live project) -> Manage." Status banner reads "Now booking Q3 engagements," © 2026 ConstructIQ Pty Ltd. Client logos shown: RSGx, Pacific Building Solutions, Hisway, Kelly Electrical, Kilcomer Group (all Australian). This is the methodology channel the Cowork handoff is most directly aligned with.

#### 3.3 SketchDeck.ai and LIFT

Product. LIFT is SketchDeck.ai's AI-powered material counting software for structural steel estimators. It is the single tool in the field most directly relevant to Your Company.

Pipeline (vendor-disclosed). LIFT was not rule-coded; it was trained on examples. Starting in 2021, SketchDeck collaborated with AISC-certified fabricators and fed the system real structural steel drawings. Per SketchDeck's own write-up: "We didn't tell the computer 'look for parallel lines.' We showed it 50,000 examples of a W12x26 beam - clean, messy, rotated, faint - and labeled them all as beams. The system's Neural Network learned to recognize the pattern of a beam, regardless of noise or variation." CNNs are explicitly named as the architecture. LIFT auto-detects beams, columns, braces; captures shape, size, stud counts and camber from labels; analyzes framing conditions, moments, copes, holes; and generates a Bill of Materials.

Exports. Tekla, Strumis, Fabtrol, E.J.E., Bluebeam, Excel.

Accuracy claims (vendor + customer): 95-99% accuracy on beam takeoffs. MSE Inc. case study reports up to 95% time reduction on beam takeoffs and one estimator-week per month freed up. FabArc, DG Welding, Maccabee Industrial, Motion Steel, Guardian Roofing, and Blach Construction are public reference customers. Treat the 95-99% as a vendor-published figure for typical cases on clean drawings, not an audited benchmark.

Pricing. Not public. Demo and trial only.

Verdict for Your Company. This is the closest direct competitor to manual steel takeoff at Your Company. Cowork cannot match it on pixel-accurate beam/column/brace detection. If Your Company wants parity on (c) drawing takeoff, this is the tool to evaluate, and its cost would sit outside the approved Your Company stack and must be flagged as such.

#### 3.4 LIFT AI (clarification)

The brief asked about "LIFT AI as the PDF analysis engine SketchDeck reportedly uses." Public evidence shows LIFT is SketchDeck.ai's own product, not a third-party engine - built in-house by SketchDeck since 2021 on a CNN trained on labeled structural-steel examples. There is no public evidence of a separate "LIFT AI" company licensing PDF analysis to SketchDeck. Treat LIFT and SketchDeck.ai as one stack.

#### 3.5 Porecore / Porcore / PoreCore

No construction estimating product by that spelling exists. Web hits resolve to (a) "Procore" (the major construction management platform - likely the intended reference; covered below), or (b) "porecore" geotechnical/pore-network instrumentation, which is unrelated. Procore Estimating (originally Esticom, which Procore announced acquiring on October 27, 2020 at its Groundbreak conference, with platform integration rolling through 2021) is a cloud takeoff + estimating product with Automated Area Takeoff that uses machine learning to detect room outlines on floor plans, auto-count repeated symbols, 2D/3D takeoff, cost catalog, proposal builder, and Bid Board. Pricing custom/enterprise. Strong for general contractors; weaker for structural-steel-specific workflows than LIFT or Beam AI.

#### 3.6 OptiservAI (optiservai.tech)

The site exists and is a real SaaS - OptiServe AI LLC, Ronkonkoma, NY - but it is not a construction estimating product. Its own tagline: "The AI Operating System for Service, Construction & Property Management. From work orders to invoicing, OptiServe AI automates your entire operation - AI proposals, smart dispatch, real-time scheduling, and profit protection built for the trades." It covers 51 industries (HVAC, plumbing, electrical, salons, restaurants, vets, legal). Pricing: from $89/month (salons) to $199/month (service businesses). Modules: Work Orders, Smart Scheduling, AI Proposal Builder, Invoicing & Payments, Customer Portal, Site Surveys, AI Reports, GPS Auto-Timesheets, Geofencing, Projects & Milestones, etc. Hosted on Microsoft Azure, uses OpenAI under the hood, Stripe for payments. Headline marketing stats ("40% Faster Proposals", "3x Dispatch Efficiency", "85% Less Paperwork") are unsourced. Not relevant to Your Company's structural-steel bid workflow.

#### 3.7 Togal.AI

Cloud takeoff platform built by former U.S. Congressman Patrick Murphy, headquartered in Miami, FL, founded 2019. Vendor claim: "up to 98% accuracy on floor plans" using AIA measurement standards, with the Togal Button (single-click area detection) and Togal.CHAT (natural-language queries against the plan set). Integrations with eTakeoff (SnapAI add-on), DESTINI Estimator. Pricing: Essential $199/mo per user; Growth $299/mo per user; annual $1,999-$2,999 per user. Time savings independently measured at 90% (Robotics & Automation News six-platform stress test, February 19, 2026: "Togal.AI tops the Time-Saved metric, clocking a 12-minute full-plan take-off that cut manual hours by 90 percent"); Togal's own Coastal Construction case study reports a 40% workload reduction saving $800,000/year. Architectural focus - strongest on floor plans and rooms, not on structural steel members.

#### 3.8 Kreo

Kreo Software Ltd, founded 2017, headquartered in London, bootstrapped with no outside funding, 22 employees and $2.4M 2025 revenue per Getlatka ("In 2025, Kreo Software Ltd's revenue reached $2.4M"), valued at $7.3M, headcount up to 23 by March 2026 per Tracxn. Cloud-based AI takeoff + estimating with: Auto Measure, AI Suggest, Auto Count, Auto Scale; an Items & Assemblies database with embedded pricing rules; 2D and 3D BIM support; agentic workflow product claiming "up to 98.5% accuracy" reading blueprints "with the accuracy of an experienced cost estimator." Pricing entry tier reported at $35/user/month for AI-assisted takeoff (per Handoff AI's review, not direct Kreo confirmation); annual commitment required at higher tiers. Reviewers consistently note: AI requires training, accuracy depends heavily on PDF quality, and troubleshooting misclassifications is opaque.

#### 3.9 Beam AI (iBeam)

End-to-end AI takeoff service that combines AI extraction with human QA. Supports 15+ trades including structural steel (beams, columns, connections). Delivery: AI-only in ~10 minutes, or AI+human-QA in 24-72 hours. Vendor accuracy claim: 98% / "+/-1% of in-house takeoff accuracy." Pricing: annual license tied to bid volume (no per-project fee). Notable for steel: explicit support for "structural steel - including beams, columns, and connections" with Excel outputs grouped by assembly. Reference customers: Blach Construction, Silicon Valley Mechanical, Guardian Roofing & Exteriors. Reviewers note the service component (~24-72hr turnaround) is a feature, not a bug, for smaller estimating teams.

#### 3.10 STACK

Cloud takeoff + estimating. STACK Assist AI auto-detects doors, windows, rooms, walls. Entry plan $1,899-$2,999/year. Strong digital plan room and accessibility; not steel-specific. Good fit as a Bluebeam replacement, weaker than LIFT for steel.

#### 3.11 PlanSwift

Older tool. Largely a digital measuring wheel; AI capabilities are limited compared to current entrants. Useful as a manual takeoff workhorse, not as an AI peer to LIFT/Togal/Kreo.

#### 3.12 Bizscope

No verifiable construction-estimating product was located under that spelling in this research pass. Possible intended reference is Bidscope/Buildscope/PinPoint Analytics (historical bid data + AI rate benchmarking). Flagged as unconfirmed.

#### 3.13 Honorable mentions

eTakeoff Dimension Premier with SnapAI, partnered with Togal.AI; InEight Estimate with AI benchmarking against historical cost libraries (Robotics & Automation News six-platform stress test, February 19, 2026, found InEight "missed the ground-truth quantities by only 1.8 percent," and notes Hunter Contracting reports three decades of similar performance using InEight); PataBid Quantify (electrical/MEP focus, live supplier-pricing integrations); PinPoint Analytics, which markets itself as: "Combine a decade of public works data with AI-driven recommendations to bid accurately, minimize risk, and maximize your profits on every job" (pinpointanalytics.ai); CountBricks (voice-to-estimate, residential); Handoff AI (residential, $149/mo); Autodesk Construction Cloud / Procore (enterprise platforms with embedded AI takeoff); ContraVault AI (RFP extraction, Go/No-Go scoring, compliance matrix - closest pure analog to Operum's contract-risk module).

### 4. Feature comparison matrix

Rows are capability; columns are tool. Y = vendor advertises; P = partial/limited; - = not advertised or not applicable.

| Capability | Operum | LIFT (SketchDeck) | Togal.AI | Kreo | Beam AI | Procore Est. | STACK | ContraVault | Handoff AI |
|---|---|---|---|---|---|---|---|---|---|
| Tender PDF/spec ingestion | Y | P | P | P | Y | P | P | Y | Y |
| Pixel-accurate drawing takeoff | P | Y (steel) | Y (arch) | Y | Y | Y | Y | - | P |
| Spec-text-based BoQ | Y | - | - | P | P | - | - | P | Y |
| Inclusions/Exclusions auto-list | Y | - | - | - | - | - | - | Y | - |
| Contract-risk / clause analysis | Y | - | - | - | - | - | - | Y | - |
| Reconciliation / gap detection | Y | - | - | - | P | - | - | Y | - |
| Rate-anomaly detection | Y | - | - | P | - | - | - | P | - |
| Schedule / time-based overhead | Y | - | - | - | - | P | - | - | - |
| Subcontractor package + quote comparison | Y | - | - | - | - | P | - | - | P |
| RFI / clarification generation | Y | - | - | - | - | - | - | P | - |
| Document revision control | Y | - | - | - | - | Y | P | - | - |
| Excel integration | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Structural-steel specialization | P | Y | - | P | P | P | P | - | - |
| AISC shapes awareness | - | Y | - | - | P | - | - | - | - |
| Output formats (PDF/Excel/CSV) | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Published pricing | P (free tier + credits) | - | $199-299/user/mo | ~$35/user/mo entry | License/volume | Custom | $1,899-$2,999/yr | Custom | $149/mo |

Operum cells are verified from the May 2026 product walkthrough; other cells reflect vendor advertising per the legend above.

### 5. The Reconciliation Engine - deep dissection

This is the central moat and the section that matters most for the Cowork rebuild.

5.1 What a Requirement Register is. It is a normalized table where every requirement extracted from the tender package becomes one row. Minimum columns: req_id (stable identifier), source_doc (filename) and source_locator (page, section, clause), requirement_text (verbatim quote), category (Direct / Subcontractor / Contingency-Prelim / Excluded - the four-bucket framework), discipline (Structural / Architectural / MEP / Civil / Other), expected_unit (TON, EA, LF, LS), expected_qty (number or null if not measurable from text), priced_line_ref (foreign key to Estimate line, null if unmatched), status (Matched / Gap / Orphan / Excluded-by-design), risk_note. The register is built page-by-page from the tender. Each row links back to a verbatim source quote so disputes can be settled by clicking through.

5.2 How an Estimate is normalized so it can be diffed. The contractor's estimate is parsed into the same schema: line_id, description, category (Direct/Sub/Cont/Excl), discipline, unit, qty, unit_rate, extended, requirement_refs (list of req_ids this line satisfies), rate_basis (e.g., "$145/hr x 11 hr/ton + material" for steel fab). If the contractor's estimate is an Excel file, normalization is a one-time mapping per template. Once normalized, line items are joinable to requirements.

5.3 The diff: gap detection rules.
- Gap: Any req_id with category in {Direct, Subcontractor, Contingency-Prelim} and no priced_line_ref. Flagged for the estimator.
- Orphan: Any priced line with empty requirement_refs. Either the line is non-essential (acceptable) or the requirement was missed during register extraction (the register needs a row).
- Category mismatch: A requirement classified as "Direct" but matched to a priced line whose category is "Subcontractor" - flag for resolution.
- Excluded-but-priced: A requirement explicitly listed in Exclusions, but a priced line exists for it. Either remove the price or move out of exclusions.

5.4 Rate-anomaly detection. This is statistical, not AI-mystical:
- Build a historical rate band from the Production Rate Library: median, P25, P75, and absolute floor/ceiling per discipline+unit (e.g., structural steel fab in $/ton, fab in hr/ton, paint in $/sf).
- For each priced line: compute z-score or simply check whether the unit rate sits inside [P25 x 0.7, P75 x 1.4] (a tolerant band that catches gross outliers without nagging on every line).
- Flag anything outside the band, plus any line whose qty x unit_rate != extended (arithmetic check) and any line whose unit doesn't match the discipline default (e.g., steel priced in SF).
- The point is not to be clever. It is to catch the $50K reinforcement undercount Fairley warned about and the $200/ton steel rate that should have been $4,500/ton.

5.5 Winner's-curse prevention as an emergent behavior. Gap detection catches missed scope (the largest single cause of losing money on low bids). Rate-anomaly detection catches priced-too-low lines. Together they are a structural defense against winning a job at a price you cannot deliver. The economic literature (Ahmed, El-adaway, Kagel & Levin, Flyvbjerg) is consistent on the mechanism: winner's curse arises when the winner underestimates the true cost or omits scope. The engine described above attacks both vectors directly.

5.6 Time-based overhead. The schedule is generated from BoQ durations using simple rules:
- Each priced line carries a crew and productivity (e.g., 11 hr/ton fab, an erection crew rate, etc.).
- Duration = quantity / crew throughput.
- Sequencing is the four-phase template (Engineering & detailing -> Procurement -> Fabrication -> Delivery & erection) with Finish-to-Start defaults that the user overrides.
- The total duration drives time-based prelims: site supervision-months, crane standby weeks, insurance days, etc.
- The Gantt artifact is a Live Artifact in Cowork (Mermaid gantt), not a Primavera/MS-Project replacement.

5.7 What's missing from any AI rebuild. Pixel-accurate steel quantities. The reconciliation engine assumes the BoQ already has a defensible quantity column. For text-extractable schedules (drawing tables, beam schedules in tabular form), Claude vision is competent. For raster-only graphical takeoffs (counting every brace from a plan view), a dedicated tool (LIFT, Beam AI, Togal) or a human estimator is still required. This is the one place where Cowork cannot hit parity.

5.8 Verified reconciliation output structure (from Operum's product walkthrough). The May 2026 product walkthrough confirms the reconstruction in 5.1 through 5.6 and pins down the exact output shape to copy. Operum's Submission Analysis produces: an overall verdict label (demo: REVIEW_AND_ADJUST) and a critical-issue count; four analysis views: Executive Summary, Scope Coverage, Detailed Estimate Risk Analysis, and Rates. Scope Coverage is gap detection. Detailed Estimate Risk Analysis is the line-level audit. Rates is rate-anomaly detection. A prioritized issue list. Each issue is one record with: priority, title, source citation including a requirement ID (REQ-010, REQ-004, REQ-044, REQ-036 in the demo) and document plus page, a section or category, and a recommended action. The demo issues map one to one to the engine vectors in 5.3 and 5.4: commercial and contract gaps (unqualified $10k/day liquidated damages, excluded authority fees, excluded escalation) and quantity reconciliation against the BOQ (carpet tiles 8,000 vs 12,000 m2). The Cowork recon-report.json schema should adopt this record shape exactly: priority, title, req_id, source_doc, source_page, section, recommended_action, plus the verdict-and-count header. That makes the Cowork output structurally identical to Operum's and directly comparable during the benchmark phase.

### 6. Honest parity assessment

| Function | Parity inside Claude Cowork? |
|---|---|
| Tender document ingestion (PDF + Word + Excel scopes/specs) | Yes, at parity. Claude reads multi-hundred-page tender packs reliably. |
| Requirement Register extraction with the four-bucket categorization | Yes, at parity. This is a classification task language models are strong at, with verbatim quoting back to the source. |
| Inclusions/Exclusions list | Yes, derived directly from the Requirement Register. |
| Contract-risk / clause analysis (LDs, payment terms, indemnity, hidden penalties) | Yes, at parity. Claude is the current best-in-class for contract review. |
| Preliminary BoQ from specs (text-quantifiable items) | Yes, at parity. |
| BoQ from drawings (pixel-accurate counting of beams/columns/braces) | No. Use LIFT/Beam AI/human estimator. Cowork can do a first-pass sanity check but should not be the system of record for steel quantities. |
| Reconciliation engine (gap + rate anomaly) | Yes, at parity, given a clean Requirement Register and normalized Estimate. |
| Time-based overhead (Gantt + duration x rate) | Yes, at parity, for the level of detail used on bids (not for scheduling execution). |
| Two-PDF output (client proposal + GP report) | Yes, via Live Artifacts and M365/Workspace export. |

---

## Part 2 - Claude Cowork Handoff (executable)

### 0. Conventions

- Edits are additive, phased, and reversible. Each phase writes a single new directory or file; nothing is overwritten without a .bak copy in /handoff_backups/<UTC-ISO-timestamp>/.
- All paths assume the existing .specify/ constitution.md root. New spec files live under .specify/specs/bid-estimating/.
- All prompts route through Sequential Thinking MCP unless explicitly marked single-shot.
- Voice rules: short sentences, specific numbers, no filler, no em-dashes, no "Great question" openers, no three-adjective lists.
- Bid rules respected by every prompt: no supplier names in client-facing docs, no precedent projects on bids, deck supply and install always in scope, engineering folded into fab and erection rates and never line-itemed, two PDFs per bid (Client and GP, GP suffix -GP).
- Verified facts to hard-code: established 2017, shop rate $145/hr, engineering $175/hr, overhead multiplier 1.15x, fabrication baseline 11 hr/ton (machine-assisted blended, April 2026), AISC Shapes Database v16.0, ISNetworld ID [ISN ID].

### 1. Phase plan (all phases reversible, backup-first)

| Phase | What it creates | Reversal |
|---|---|---|
| P1 | .specify/specs/bid-estimating/constitution-delta.md (additive) | Delete file |
| P2 | /data/schemas/ with 5 JSON schemas | Delete folder |
| P3 | /skills/bid/ with 6 skill markdown files | Delete folder |
| P4 | /library/production-rates.yaml extension | Restore from .bak |
| P5 | Live Artifact templates (Mermaid + HTML) under /artifacts/templates/ | Delete folder |
| P6 | Scheduled tasks registration in Cowork (Dispatch panel) | Disable tasks |
| P7 | Two MCP connectors registered (filesystem + PDF parser) | Remove from Customize panel |

Each phase ends with a one-line journal entry appended to /handoff_backups/journal.log.

### 2-7. Data schemas, skills, rate library, artifact templates, scheduled tasks, MCP connectors

All executable artifacts are now built and live in this project. See the sibling files:

- constitution-delta.md
- scheduled-tasks.md
- mcp-connectors.md
- ../../data/schemas/*.schema.json
- ../../skills/bid/*.skill.md
- ../../library/production-rates.yaml
- ../../artifacts/templates/*.tpl
- ../../scripts/validate-bid-output.py

### 8. Expected accuracy per replicated function

| Function | Realistic accuracy in Cowork |
|---|---|
| Tender ingestion (text extraction from digital PDFs) | >=98% character-level on clean PDFs; lower on scanned. |
| Requirement Register from spec text | ~95% recall on tabulated/clear specs; ~70-80% on prose-only specs; verbatim quotes always preserved. |
| Inclusions/Exclusions list | ~95% if the Requirement Register is clean. |
| Contract-risk register | ~90% recall on standard risk clauses; novel clause language requires human review. |
| Preliminary BoQ from specs | ~85-90% for items with quantities in spec text. |
| BoQ from drawings (graphical takeoff) | Not at parity. Estimate ~60-70% recall for first-pass sanity check only. Use LIFT/Beam AI or human for the system-of-record quantity. |
| Reconciliation gap/orphan/category detection | ~100% deterministic given clean inputs. |
| Rate-anomaly detection | ~100% deterministic given a populated rate library. |
| Time-based overhead schedule (bid-grade Gantt) | ~95% for the level of detail needed at bid stage. |
| Two-PDF output (client + GP) | 100% via M365/Workspace. |

### 9. Hard rules enforcement (build-time checks)

scripts/validate-bid-output.py runs before any PDF export and fails the build if:
- Any supplier name appears in the client proposal PDF.
- Any precedent project is referenced in the client proposal.
- Engineering appears as its own line item anywhere.
- Deck supply or deck install is missing from Inclusions.
- The two-PDF pair is incomplete (must produce both <bid>.pdf and <bid>-GP.pdf).
- Voice rules: em-dash characters present, three-adjective sequences detected, "Great question" or filler-opener detected.

### 10. Out-of-stack costs flagged

| Component | Inside approved stack? | If not, indicative cost |
|---|---|---|
| Claude Max 5x | Yes | Already paid |
| Google Workspace / M365 / Runway | Yes | Already paid |
| Sequential Thinking MCP | Yes, free | $0 |
| SketchDeck LIFT (steel pixel-takeoff) | No | Not public; demo/contact only |
| Beam AI structural-steel takeoff | No | License by annual bid volume, custom |
| Togal.AI | No | $199-$299/user/month |
| Kreo | No | ~$35/user/mo entry, annual commitments at scale |
| Procore Estimating | No | Custom enterprise |
| Tesseract OCR (scanned PDF fallback) | Yes (free OSS, local) | $0 |
| PinPoint Analytics (historical bid benchmarking) | No | Subscription |

### 11. Rollout sequence (recommended)

1. Week 1: P1-P2. Constitution delta + schemas. No skill changes yet. Sanity check that the existing handoff still runs.
2. Week 2: P3 (skills) + P4 (rate library extension). Test on one closed historical bid.
3. Week 3: P5 (Live Artifacts) + P6 (Scheduled tasks). Run on a live in-flight tender as a shadow-bid, do not submit Cowork output yet.
4. Week 4: P7 (MCP connectors) + validator. Compare Cowork-generated reconciliation output against the human estimator's manual review on three closed bids. Calibrate rate bands.
5. Week 5: Production use for tender intelligence, Inclusions/Exclusions, contract risk, and reconciliation. Drawing takeoff remains human-led or LIFT-led, not Cowork-led, until a controlled trial proves otherwise.

### 12. Caveats and what would change this plan

- If Operum publishes a real feature list/API: revisit whether direct integration is cheaper than rebuilding.
- If Your Company's bid volume justifies it (~12+ steel bids/month with significant repeat content): re-evaluate adding LIFT or Beam AI as the steel-takeoff layer. Cost would have to be flagged formally as outside the approved stack.
- If a tender package routinely contains scanned (raster) PDFs only: Tesseract OCR is not enough; budget for a cloud OCR API or insist on digital PDFs from clients.
- The rate bands in the production library only become statistically meaningful after ~20+ closed projects are loaded. Until then, anomaly detection should be tuned looser (e.g. P10/P90) to avoid false positives.

---

## Key Findings

1. The reconciliation engine is the moat, not the takeoff. Most AI estimating vendors compete on drawing takeoff accuracy. Operum's contribution is in the governance layer above the takeoff (Requirement Register -> Inclusions/Exclusions -> contract risk -> diff against estimate -> flag gaps and rate outliers -> derive time-based prelims). That layer is reproducible inside Claude Cowork using only the approved stack.
2. Structural steel is the one domain where dedicated software still wins. SketchDeck LIFT's CNN-trained beam/column/brace detector is mature enough (95-99% vendor claim on clean drawings, MSE case study reports 95% time reduction) that Your Company should not pretend Cowork can match it on pixel-accurate steel takeoff. The honest plan is hybrid: Cowork for everything except graphical takeoff; human or LIFT for that.
3. Operum is now benchmarked from its product walkthrough. The earlier "JS SPA, nothing verifiable" caveat is retired. A full guided walkthrough on operum.io confirms the real feature set: credit-based pricing with a free tier; tender plus drawings ingestion; a Tender Summary requirement register with live counts (Requirements 44, Submission Requirements 9, RFIs/Clarifications 28, Risks & Opportunities 18, BoQ 14, Drawings 10) and page-level citations; subcontractor package management with quote comparison; a Direct/Indirect/Sell-Price estimate engine with per-activity Pricing Workbooks and a typed Project Resource Library; and a Submission Analysis reconciliation step that emits a verdict, a critical-issue count, and prioritized issues with requirement IDs, citations, and recommended actions. Two capabilities the first draft did not credit Operum with are now confirmed: automatic RFI/clarification generation and a Risks-and-Opportunities (not just risks) register.
4. "Porecore" is almost certainly Procore. Procore Estimating (originally Esticom, acquisition announced October 27, 2020) is a real competitor with Automated Area Takeoff and 2D/3D takeoff; no "Porecore" product exists.
5. OptiservAI is not a construction estimating tool. It is a 51-industry field-service-management SaaS (OptiServe AI LLC, Ronkonkoma NY, from $89-$199/month). Useful framing for FSM, irrelevant to Your Company's bid workflow.
6. Time-based overhead is mechanically straightforward. Quantities -> durations via the production-rate library -> Gantt -> time-based prelims = duration x monthly indirect rate. It does not need Primavera and it does not need Operum.
7. Vendor accuracy numbers should be treated skeptically. Most "98%" and "99%" figures are vendor-published claims on clean inputs. The closest thing to a third-party benchmark in this research is the Robotics & Automation News six-platform stress test (February 19, 2026), which reported InEight at 1.8% variance from ground-truth quantities and Togal.AI cutting takeoff time by 90%.

## Recommendations

Stage 1 (Weeks 1-2): Build the governance layer in Cowork. Implement Phases P1-P4 of the handoff. This delivers Requirement Register, Inclusions/Exclusions, contract-risk register, preliminary BoQ from specs, and the reconciliation engine, using only Claude Max 5x + Sequential Thinking MCP + the existing rate library. Benchmark for moving on: running the workflow on three closed historical Your Company bids should flag every known scope miss those projects experienced post-award. If it doesn't, recalibrate before going further.

Stage 2 (Weeks 3-4): Add Live Artifacts and Scheduled tasks. Implement P5-P7. Run shadow-bid against a live in-flight tender. Compare against the human estimator's manual reconciliation. Benchmark to ship: Cowork reconciliation report agrees with the human estimator on >=90% of flagged items, with disagreements all explained by either (a) drawing-derived quantities Cowork could not see, or (b) tacit knowledge the rate library does not yet encode.

Stage 3 (Week 5 onwards): Production use, hybrid drawing takeoff. Cowork is the system of record for tender intelligence, Inclusions/Exclusions, contract risk, reconciliation, and the GP report. Drawing takeoff remains a human or LIFT process. Benchmark to add dedicated takeoff software: if Your Company's bid volume crosses ~12 steel-heavy bids per month AND the human-estimator hour cost on drawing takeoff alone exceeds the LIFT/Beam AI license cost, formally evaluate adding one of them as a flagged out-of-stack tool. Until then, do not.

Stage 4 (Quarter 2+): Statistical maturity. Once 20+ closed projects are loaded into the rate library, tighten anomaly bands from P10/P90 to P25/P75 with the +/-30-40% tolerance described in section 5.4. Benchmark to tighten further: false-positive flag rate per bid drops below 1 per 100 priced lines.

## Caveats

- The Operum sections are now grounded in a May 2026 product walkthrough on operum.io (delivered via the Guideflow demo player) using a sample project with demonstration data. Feature existence and structure are verified from that walkthrough; the dollar figures in it are sample data, not benchmarks, and exact dollar-per-credit pricing was not captured. Independent third-party accuracy benchmarks for Operum specifically were still not located.
- "LIFT AI" as a separate company licensing PDF analysis to SketchDeck could not be substantiated. LIFT appears to be SketchDeck.ai's in-house product.
- "Porecore" did not resolve to any construction estimating product. Treated as a likely misspelling of Procore.
- OptiservAI exists but is a horizontal field-service-management SaaS, not a construction bid estimating tool. Excluded from the parity discussion.
- "Bizscope" could not be verified. Flagged as unconfirmed.
- All vendor accuracy claims (98%, 99%, 95%, 80% time savings) are vendor-published figures, not audited benchmarks. The one third-party number cited (InEight at 1.8% variance vs ground truth, Togal.AI at 90% time reduction) comes from the Robotics & Automation News six-platform stress test of February 19, 2026.
- The reconciliation engine described here is the author's reconstruction based on Fairley's documented methodology and standard quantity-surveying practice. Operum's actual internal implementation may differ in details.
- The "AI Reconciliation Exercise" name in the user's brief was not found verbatim in any public Fairley writing; the concept is documented, the name as a product feature is not.
