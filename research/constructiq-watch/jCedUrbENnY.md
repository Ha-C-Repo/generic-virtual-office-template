# Build Your Own AI Construction Estimator - Step-by-Step (jCedUrbENnY)

- URL: https://www.youtube.com/watch?v=jCedUrbENnY
- Uploader: Tim Fairley (ConstructIQ / community "Contractor OS")
- Duration: 14:24 (864.1s)
- Frames analyzed: 80 @ 0.093 fps (full mode, 512px wide)
- Transcript source: captions (405 segments, clean)

Thesis: AI can do the number-crunching half of estimating well (apply rates to quantities) for budget/conceptual-grade estimates, but only if you feed it a structured cost library via an MCP connector and a tightly scripted "skill" workflow that takes off quantities from the drawing TEXT/vector layer (high confidence) rather than measuring scaled geometry (low confidence), and that flags its own confidence and assumptions for human audit.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:00 (frame 1): Opens on the Airtable "Production Rate Library" base. Thesis stated: AI prices badly with no context; give it location, lane count, design features, AND your full cost library + bill of quantities + exact process, and "it will probably do its job as good as any estimator," because "the actual number crunching part of estimating is just applying rates to quantities." Accuracy depends entirely on data quality.
- t=00:35: Defines the build. Input = a set of drawings + a scope of works. Output = an Excel estimate. "One simple workflow that you run end to end." Two foundations: (1) the data behind it, (2) the workflow itself. Mechanics reduce to getting correct quantities and applying correct rates (rates depend on your database).
- t=01:17: Scope caveat. This is for budget and conceptual estimates, NOT lump-sum hard-dollar projects. He has a separate video for integrating AI into a +/- 5% lump-sum estimate.
- t=01:48: The commercial caveat. Estimating is also a commercial decision, not just calculation: risk, where to strategically drop price, smart inclusions/exclusions, what the client cares about. AI excels when given a good accurate cost library, a clearly defined scope, and a clear bill of quantities.
- t=02:30: The drawings problem. There is a "lag" between AI's ability to read text and how badly it reads/interprets construction drawings. "Construction drawings are quite possibly the worst input for AI" (visual, dense, layered symbols). Measuring a pipe run length is very hard for AI. Cites the "clock benchmark" for AI struggling with precise measurement.
- t=03:29: The exception he found "very recently": extract the TEXT layer from the drawings. He built this into a quantity-takeoff skill that counts individual text call-outs very accurately. Area/linear measurements off a scale are still not accurate.
- t=03:52: Use-case framing. Quick budget price before a detailed estimate; high-level dollar figure for a bid-to-bid situation (contract not yet secured, loose scope, you will not be held to it); developer feasibility study.
- t=04:30: AACE class mapping. He puts this at "tender budget estimate" accuracy of roughly minus 20% to plus 30%.
- t=04:42 (frame 29): TOOL 1 - Claude Cowork. The desktop version of Claude opened on a folder containing the drawings; Claude reads/writes files directly so you do not paste into chat. Reason: a ~10 MB drawing set cannot be uploaded to chat without overwhelming the context window.
- t=05:23 (frame 32): TOOL 2 - Claude Skills. Pre-package a workflow; call it from chat by name. His "estimating workflow" skill stores all instructions: exact process, output format, how to make assumptions, how to read from the cost library.
- t=06:05 (frame 36): Plug for Contractor OS - a library of pre-built construction skills plus one-on-one text support. The estimating and drawing-analysis skills shown live in Contractor OS.
- t=06:35 (frames 38/39): TOOL 3 - the output is Excel ("the greatest construction software ever invented"), easier to audit than a chat report. The estimating skill defines the structure: price schedule, workings with direct cost (with references to where rates were pulled), build-up of indirect cost, and inclusions/exclusions. Same output format every run, so it is easy to audit.
- t=07:30 (frames 1/14/44): TOOL 4 - the cost database, stored in Airtable ("Excel online" for structured construction data). Stresses Airtable is just his choice; you could use Excel, Notion, SharePoint, Google Drive, Supabase. He likes Airtable because it has a good MCP into Claude.
- t=08:04 (frame 50): MCP explanation. Customize > Connectors. An MCP lets Claude read/write to external software directly. You need the cost DB in a cloud platform the MCP can reach, rather than copying the DB into every project folder.
- t=09:03: Token-cost warning per connector. Airtable and Supabase do NOT use a lot of tokens; Notion uses "a ton"; Microsoft 365 is slow and uses a ton.
- t=09:18: The drawing-analyzer behavior. It splits the drawing set into individual PDF drawings and creates a markdown representation of each, so instead of ingesting the whole 10 MB PDF every read, Claude finds the specific drawing and the exact bit of information.
- t=09:35 (frame 55): Runs the conceptual estimator skill. It takes whatever the client provided (drawings, scope, maybe a bill of quantities), determines what scope is missing, makes assumptions where required, derives a bill of quantities using a SEPARATE skill (the construction takeoff skill), then turns it into an Excel estimate, flagging confidence level throughout.
- t=10:25 (frame 70): Confidence breakdown for the sample estimate: 30% high, 5% medium, 65% low confidence. It shows the workings (derived bill of quantities); against each item it flags whether the cost-library info and the source info are useful/relevant, and whether it counted items (accurate) versus measured area (not accurate).
- t=11:03 (frames 26/66): The takeoff output. The skill counted all the floor drains by converting drawings to vector data and counting individual tags, and marks up the tags on the drawing as a reference. It did NOT count lengths.
- t=11:30 (frames 66/68): The takeoff sheet. Items where it counts items = HIGH confidence. Trench drain = HIGH because the client gave a schedule with lengths. Sanitary waste/vent and domestic water pipe used the "polyline method" off scaled measurements = LOW confidence. This tender package had no bill of quantities, so it had to do its own takeoff.
- t=12:20 (frames 58/60): The data feeds the conceptual estimator, which judges (1) confidence in the RATE (good match = high accuracy, poor match = low) and (2) confidence in the QUANTITY (easily derived = high, not derived properly = low). It calculates direct costs and matches them to activities in the cost library, then builds up overheads per the instructions, which requires estimating the project DURATION.
- t=13:05 (frame 74): Everything is documented as inclusions and exclusions. Any missing/inaccessible info is explicitly forced into inclusions/exclusions so the estimate makes no hidden assumptions. "An estimate is only as good as the assumptions behind it."
- t=13:40: He notes one missed step: the skill also looks at the benchmark rates and fact-checks them as a reasonableness test at the end (the parametric sanity check seen in frames 5/70).
- t=13:50: Close. Quality depends on (1) quality of your cost data and (2) quality of the bid-package info. With a bill of quantities + good data it is very accurate; without, it is not. "What really matters is how to have a really good construction cost library."

## On-screen tools and Claude skills (table; names exactly as shown on screen)

| Item | Type | Where seen | Notes |
|---|---|---|---|
| Claude Cowork | Desktop app | t=04:46, frames 29/32 | Opens Claude on a folder; reads/writes files directly. (He spells it "CoWork" in speech; UI is the Claude desktop app.) |
| `estimating-workflow` | Skill (slash command) | frames 33/34/37 | Typed `/estimating-workflow`; master orchestration, "Slash command + auto" trigger, "Added by You, Last updated Jan 15, 2026." |
| `conceptual-estimate` | Skill (slash command) | frame 55 | Typed `/conceptual-estimate`; the main estimate-builder skill. |
| Construction Estimating Workflow | Skill body title | frame 32 | "Orchestrate the full tender-to-estimate process through four steps with human confirmation between each." 4 numbered steps visible: 1 REQUIREMENTS EXTRACT..., 2 SCHEDULE BUILDER..., 3 LINE ITEM PRICING..., 4 RECONCILIATION CHECK..., each with "User confirmation". "Step 1: Gather Information." |
| quantity takeoff skill / "construction takeoff skill" | Skill | t=03:37, t=10:12, frames 66/68 | Counts text call-outs / tags from vector data; produces the takeoff sheet. |
| Quantity Takeoff | Contractor OS module | frame 36 | Listed in Contractor OS Classroom sidebar. |
| Project Indexer | Contractor OS module | frame 36 | Sidebar under "Estimating & Cost Management" / project set-up. |
| Drawing Analyser | Contractor OS module | frame 36 | Splits drawings into per-sheet PDFs + markdown. |
| Cost Data Library | Contractor OS module | frame 36 | Sidebar. |
| Estimating Suite | Contractor OS module | frame 36 | Sidebar. |
| Payment Claim - Client | Contractor OS module | frame 36 | Sidebar. |
| Cashflow Forecaster | Contractor OS template | frame 36 | "AI Workflows & Templates" classroom item. |
| Personal-plugin skills list | Claude Skills panel | frame 32 | Visible skill files: subcontract-review, progress-report, payment-claim, variation, correspondence-review, contract-notices, contract-obligations-register, departures-register, contract-review, construction-takeoff, construction-site-diary-sweep, site-diary-daily-setup, site-diary-daily-report, requirements-clarifications-register, business-cash-position, project-cash-reconciliation, construction-cashflow-forecast, longform-script-builder, pdf-markup. |
| "Contractor os skills" | Claude personal plugin | frames 32/46 | The plugin bundling all the above skills. |
| Airtable | Cost DB + MCP connector | frames 1/14/44/50/79 | Base named "Production Rate Library". |
| Airtable MCP (read-only tools) | Connector | frame 50 | Tools shown: `get_record_for_page`, `get_table_schema`, `list_bases`, `list_pages_for_base`, `list_record_comments`, `list_records_for_page`, `list_records_for_table`, `list_tables_for_base`. |
| Other connectors present | Connectors panel | frame 50 | Airtable, Canva, GitHub Integration, GitHub MCP, Gmail, Google Drive, Microsoft 365, Bluebeam (LOCAL DEV), Claude in Chrome, googleDrive. |
| Bluebeam Revu | PDF markup tool | frames 26/64/66 | Where the marked-up plumbing drawings are viewed (file "P100_Waste_Vent_MARKED"). |
| Excel | Output format | frames 5/38/39/58/74 | Estimate workbook with multiple sheets. |

## The workflow, step by step (reproducible how-to)

1. Set up a structured cost database in a cloud tool with a low-token MCP (he uses Airtable; Supabase is the equally-endorsed alternative). Base = "Production Rate Library" with tabs: Production Rates, Projects, Resource Rates, Benchmarks, Overheads Library.
2. Connect that database to Claude as an MCP connector (Customize > Connectors), with read-only tools at minimum (`get_table_schema`, `list_records_for_table`, etc.).
3. Put the client's drawings + scope of works in a desktop folder. Open Claude Cowork on that folder so Claude reads files directly (no chat upload; avoids context-window blowup on a ~10 MB set).
4. Pre-index the project: a drawing-analyzer/project-indexer step splits the merged PDF into per-sheet PDFs and writes a markdown representation per sheet, so Claude later fetches only the relevant sheet, not the whole file.
5. Invoke the master skill in chat by slash command (`/estimating-workflow` or `/conceptual-estimate`). The skill is a 4-step orchestration with human confirmation between each step: Requirements Extraction, Schedule Builder, Line-Item Pricing, Reconciliation Check.
6. The conceptual-estimate skill ingests whatever was provided, determines missing scope, makes flagged assumptions, and calls a SEPARATE construction-takeoff skill to derive the bill of quantities.
7. Takeoff method per item is recorded: `text_count` (count tags from the vector/text layer = HIGH confidence), `schedule` (client-provided schedule = HIGH), `polyline_length` (measure off scale = LOW). The skill marks up counted tags on the drawing as a visual audit reference.
8. The estimator matches each item to a cost-library activity ("Direct activity match"), records base rate, escalation, contract factor, final rate, source table, and source item; it judges rate-match confidence and quantity confidence independently.
9. It builds up indirect/overhead costs per instruction, which requires estimating project DURATION.
10. It runs a parametric sanity check: compares the bottom-line $/unit against benchmark rates (industry + first-principles + database) and reports "Priced" if reasonable.
11. It writes everything to a fixed Excel structure (cover/exec summary, build-up, takeoff, workings/direct-cost with rate sources, confidence breakdown, inclusions/exclusions) plus a `priced_data.json` source file. Same layout every run for auditability.

## What works / what does NOT (where he trusts AI vs refuses it, and why)

- TRUSTS: counting tagged items from the extracted drawing TEXT/vector layer ("very accurately"); client-provided schedules; applying rates to known quantities. He says once it is counting items it is "quite accurate."
- TRUSTS PARTIALLY (flags LOW): area and linear measurements taken off a scaled drawing via the "polyline method." He explicitly will not stand behind these and tags them low confidence. Cites the "clock benchmark" for AI's poor precise-measurement reading.
- REFUSES: lump-sum hard-dollar bids (+/- 5%). This whole system is positioned only for budget/conceptual/feasibility/bid-to-bid pricing at roughly minus 20% to plus 30%.
- DESIGN PRINCIPLE: never let AI make hidden assumptions. Every gap is forced into written inclusions/exclusions; every line carries a confidence flag and a cited rate source. Excel is chosen specifically because it is auditable.
- COMMERCIAL JUDGMENT stays human: risk posture, strategic price drops, what the client values, smart inclusions/exclusions.

## Concrete numbers, rates, file names, examples shown

- Sample project: "Whole Foods Market - Kennesaw, GA (Plumbing Package)", ~9,210 m2 (45,300 sq ft), Commercial Floor, ~$210/m2 GFA, dated 2026-06-08 (frames 5/38/39).
- Headline band on the Excel cover: "BUDGET PRICE - ACCURACY +/-30% | basis: drawings_no_boq / quantities: takeoff | NOT A LUMP-SUM BID" (frames 38/39).
- Build-up figures (frames 5/23): Direct costs 408,541; Project overheads (prelim) 68,002; Contingency (7.5%) 35,808; OH&P (12.0%) 61,590; TOTAL (excl. tax) 574,842; Sales tax (on material rates) 0; TOTAL (incl. tax) 574,842; Per-m2 GFA 137 (also seen as range 402,389 to 747,295 at 100%).
- Confidence breakdown (frames 5/70): HIGH 121,917 (29.8% / ~30%); MEDIUM 20,436 (5.0%); LOW 266,188 (65.2% / ~65%).
- Parametric sanity check text (frame 5): "Supermarket plumbing $/m2 (industry, first principles) ... not in database) benchmark mid $368,350 vs priced $574,842 (+1%) - Priced." (A second frame shows benchmark mid 384,850.)
- Takeoff sheet title (frames 66/68): "WHOLE FOODS MARKET - KENNESAW, GA | PLUMBING TAKEOFF (SAMPLE FOR REVIEW)". Columns: Tag, Description, System, Qty, Unit, Drawing, Method, Confidence, Notes. Method values: text_count, polyline_length, schedule. Example notes: "Verified on marked PDF: 1 per case branch"; "Lengths from P001 schedule (linear trench run)"; "Counted on plan, NOT risers (avoids double-count)"; "Diagrammatic routing; scaled by linewght; range." Items: Floor Drain heavy-duty cast iron + grate (FD-1), acid-resistant Sani-Ceptor (FD-2), in-round nickel bronze (FD-3), wall hydrant, trench drain channel, domestic water pipe, etc.
- Workings/direct-cost sheet (frames 58/60) columns: Ref, Description, Base rate, Escalation, Contract factor, Final rate, Source table, Source item, Method ("Direct activity match"), Assumptions. Source table = "Production Rates" for most lines.
- Output folder "Estimate Output" (frame 48) files: `priced_data.json` (JSON Source File) and `Whole_Foods_Plumbing_Conceptual_Estimate.xlsx`.
- Airtable base "Production Rate Library" tabs: Production Rates, Projects, Resource Rates, Benchmarks, Overheads Library.
  - Production Rates columns (frames 14/44): Activity Name, Work Category (Civil/Electrical/Structural/Formwork...), Quantity, Unit (m, no, m2, m3, t), Crew Size, Plant Used (e.g., "20t Excavator + Truck", "Electricians + Cable Winch", "Steel fixers + Mobile Crane", "Excavator + Pipe Layer"), Duration. Sample activities: Trenching, Slab Formwork, Cable Pulling, Rebar Installation, Pipe Laying, Conduit Installation, Column Installation, Steel Erection, Switchboard Install, Wall Formwork, Concrete Pouring, Kerb & Gutter, Lighting Installation, Deck Formwork, Precast Panel Erection.
  - Benchmarks columns (frames 10/79): Benchmark name, Project Type, Unit, Low, Mid, High, Basis & Caveats, Source Projects. Rows: Warehouse shell construction (Industrial / Warehouse, $/m2 GFA, $900-$1,200, source "Industrial Logistics Esta..."); High-rise residential constr. ($/m2 GFA, $1,600-$4,100, "CBD Residential Tower"); Data centre electrical fitout ($/m2, $5,500-$6,800, "Data Centre Project"); Dual carriageway road construction ($/lane-km, $3,800,000-$4,550,000, "Western Bypass Stage 2"); Structure as % of total project cost (% of construction cost, $28-$33, "Concrete structure incl. fou..."); Live environment works premium (Airport / Aviation, % uplift on project, "Airport Terminal Upgrade").

## Applicability to a structural steel fabricator (Your Company)

WHAT TRANSFERS DIRECTLY:
- The architecture maps almost 1:1 onto our existing Cowork pipeline. His "Production Rate Library" Airtable base is our `bridge/bid_rates.py` BID_RATES + production data; his cost-DB-over-MCP idea is an alternative to our hardcoded rates if we ever want CEO-editable rates in one place (but our rates are CEO-locked Q2 2026, so keep them in code; do not move locked rates into an editable Airtable without the Owner's approval).
- The confidence-tagging discipline (HIGH/MEDIUM/LOW per line, with method and source recorded) is exactly our Operating Rule on confidence tagging and our SF-source HIGH/MED/LOW model. His method labels (text_count = HIGH, schedule = HIGH, polyline_length/scaled = LOW) are a clean vocabulary we can adopt verbatim in our takeoff output. Our drawing-analyzer skill already extracts the PDF vector text layer and counts tagged items, and explicitly refuses scaled measurement - identical to his core insight.
- "Count tags, never measure off scale" validates our drawing-analyzer's stated rule ("Never measure scaled quantities from the image; approximate, not accurate"). For steel, the count-from-tags approach transfers to: counting columns/beams/joists/connections from member tags and schedules, and reading member marks from the schedule TEXT layer - which is precisely what our count-gap engines (A1 schedule-QTY reader) and project-indexer do.
- The Excel output anatomy (cover/exec summary with accuracy band + basis line, build-up, takeoff sheet, workings sheet with cited rate sources, confidence breakdown, inclusions/exclusions, parametric sanity check) is a strong template to benchmark our two-PDF + GP-report structure and our `bid_sanity_gates.run_gates()` against. His parametric "$/m2 vs benchmark" check is our $/SF gate; his benchmark table with Source Projects is our precedent list (note: we keep precedents off client bids per Tier 1, so a benchmarks table stays internal/GP-only).
- The "force every gap into written inclusions/exclusions, no hidden assumptions" rule matches our verify-don't-generate posture and the RFI/contingency flow for LOW-SF jobs.

WHAT TRANSFERS WITH ADAPTATION:
- His "structure as % of total project cost" benchmark (frame 79) is exactly the kind of ROM cross-check we could add for structural steel tonnage sanity (steel $/SF or tonnes/SF bands), feeding the same low-confidence ROM caveat we already attach.
- His crew/plant/duration model in the Production Rates table (Crew Size, Plant Used, Duration) is more granular than our fab/erection $/T model. For erection sequencing or schedule estimates it is a useful pattern, but our rates are tonnage-based and CEO-locked, so this would be additive (schedule/duration estimation), not a replacement for BID_RATES.

WHAT DOES NOT TRANSFER:
- He is explicit this is budget/conceptual only (minus 20% to plus 30%), and that AI should NOT do lump-sum hard-dollar bids. Our bid-grade estimates require a measured member takeoff through `bridge/aisc_validator.py` (the 2,299-shape DB), not $/SF or scaled approximation. His "derive a bill of quantities and trust the count" is fine for fixture counts; for steel tonnage we must run validated AISC weights, never LLM math (Hard Rule 5). His system has no equivalent of our AISC validator.
- His rate-matching is "best-match an activity to a cost-library row." For steel that is too loose: our tonnages and AISC weights are deterministic, not fuzzy-matched. Use his fuzzy-match pattern only for soft/secondary items, never for primary structural members.
- He measures plumbing (pipe runs, drains). Direct steel analogue is member length, which he himself flags LOW when scaled - reinforcing that we should drive length from schedules/marks, not from scaled plans.

## Caveats

- Frame sparsity: 80 frames over 14:24 (~one every 11s). Fast UI actions between frames are not captured, so some skill-list entries and Excel cell values are read from partial views and may be slightly imprecise (exact decimal cents on a few rates were not legible).
- The "Construction Estimating Workflow" skill body (frame 32) was only partially on screen; I captured the 4 step headers and the overview line but not the full prompt text of each step.
- The Airtable record values (rate dollar figures, durations) are read from a zoomed-out grid partly occluded by the presenter webcam overlay; treat specific cell numbers as indicative, not exact. The build-up and confidence dollar figures (frames 5/23/70) were clearly legible and are reported as shown.
- Title em-dash in the source metadata was rendered by the pipeline; this report uses hyphens throughout per our output rules.
- Two benchmark "mid" values appeared across frames ($368,350 and $384,850) in the sanity-check line; both are noted rather than reconciled, as the view changed between frames.
