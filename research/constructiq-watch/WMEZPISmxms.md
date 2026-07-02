# AI for Quantity Take-Offs - Step-by-Step (WMEZPISmxms)

- URL: https://www.youtube.com/watch?v=WMEZPISmxms
- Uploader: Tim Fairley (ConstructIQ / community "Contractor OS")
- Duration: 20:37 (1237s)
- Frame count: 80 frames @ 0.065 fps (full mode), 512px wide
- Transcript source: captions (595 segments, clean and complete)

Thesis: Fairley argues you should NOT let AI free-form measure drawings; instead you package a repeatable Claude skill that forces AI to count machine-readable text tags and explicit dimensions (high reliability), derive everything else by formula from those "primary" numbers, tag every line with a confidence score, and run sanity checks - keeping the human in the loop on scope and on low-confidence items.

---

## Chronological walkthrough (t=MM:SS anchors)

- t=00:02 (transcript) - Opens by restating his prior skepticism of AI takeoffs. Says recent advances (he names "Claude Opus 4.8" by ear; see Caveats) plus the models' ability to write and run their own code changed his mind: instead of counting a symbol by vision, AI "extracts the text tags from the PDFs and counts the text tags, which it can do programmatically 100% accurately."
- t=01:04 - States the core risk: ~80% of a construction estimate's direct costs are proportional to quantities, so a wrong takeoff under-quotes the job. For a real lump-sum bid ($1M/$5M/$10M) he would still do quantities himself and spend a couple hours checking.
- t=01:37 - Carves out where AI takeoff IS appropriate: quick conceptual / go-no-go estimates, or checking a takeoff you already did.
- t=02:06 (frames 1-8) - PDF viewer (Bluebeam-style) open on structural footing/foundation plan. Visible tags: footings F0/F6/F7, pile caps PC1/PC3, notes "FFL = 31.25", "TOP OF FOOTING R.L. = 30.95 U.N.O.", a "FOOTING & GROUND FLOOR PLAN" with a FOOTING SCHEDULE.
- t=02:11 (frame 9) - Introduces "Claude Cowork" (he pronounces it "Co-work"/"Cower"): Claude opened on a desktop folder it can read/write. Model selector shows "Opus 4.8 High". Folder (frame 10) holds sub-folders: 1. Structural Drawings, 2. Plumbing Drawings, 3. Architectural Drawings, 4. HVAC Drawings, 5. Civil Drawings, 6. Electrical Drawings.
- t=02:32 (frame 11) - The whole workflow is packaged as a Claude skill invoked by typing `/construction-takeoff`.
- t=02:58 - Skill contains Python scripts (split PDFs, extract sections) and per-trade checklists (architectural, civil, mechanical, electrical) and his primary-vs-secondary quantity strategy.
- t=03:18 - Pitches "Contractor OS" community (link in description) with pre-built skills, weekly AI workshops, 1-on-1 support.
- t=03:43 (frames 14-17, 24) - Prerequisite step: run the "drawing analyzer" / "drawings-analyser" skill FIRST. It splits the document set into individual PDFs and builds markdown files plus a structured (SQLite) database of every object on the drawings - "a map of where all the relevant information is." References his separate Project Indexer / Drawing Analyser videos.
- t=04:37 - Recommended phrasing: open Cowork on the folder and say "Can you please perform a quantity take-off on the architectural construction drawings in this folder?"
- t=04:54 (frames 21-23) - Demonstrates WHY Cowork and not Claude chat: uploading the drawing set to plain chat fails. The set was 11 MB (he also says 10 MB), under the stated upload limit, but "for some reason it never works." Error shown (frame 23): "Failed to upload 'DRAWINGS - Combined.pdf'. The file format may not be supported or the file may be corrupted." Conclusion: for big documents you must use Cowork in the desktop app.
- t=06:06 (frame 12) - Opens the `construction-takeoff` skill in the Cowork skills panel. File tree: SKILL.md, references/ (trade_checklists/, derivation_library.md), scripts/ (measure.py, split_extract.py). The skill encodes two things: the exact strategies to perform the takeoff and the output format to standardize on (so output is auditable and reusable).
- t=07:06 - The takeoff runs in three discrete steps: (1) analyze drawings and decide what to measure, (2) build assemblies, (3) measure.
- t=07:20 - Step 1: AI prompts you for the trade/perspective (e.g. you may only be pricing concrete, not steel) so it does not measure everything.
- t=07:44 - Step 2: build "assemblies." Introduces primary vs secondary quantities.
- t=08:49 (frame 36) - Worked example: warehouse P1 slab = 11,640 m2 is the PRIMARY quantity (measured). Concrete volume is SECONDARY = derived by formula (area x depth, depth read straight off the drawing), avoiding any complex volume/section reasoning.
- t=09:45 - Step 1 keeps a human in the loop: you review the plan and can tell it "don't measure cable to each power point - count power points, use 15 m of cable per point as the ratio." Constrains AI to what it does reliably (text tags) and away from scaled measurement.
- t=11:13 (frames 40-46) - Vector vs raster distinction. On the structural set he can highlight text (a vector-data layer exists). On the electrical set he cannot highlight a light fitting because that PDF is a compressed image; the takeoff returned LOW confidence because it had to use a vision count, not a vector count.
- t=12:40 (frames 50-52) - Shows `split_extract.py` source: splits the multi-page PDF into single-sheet PDFs, pulls the raw vector text layer with coordinates via PyMuPDF, optionally renders a PNG per sheet for vision passes. Storing the script in the skill saves tokens (AI pulls a template instead of writing its own).
- t=14:05 (frames 56-58) - Per-trade "coverage checklist" templates so every architectural / civil / mechanical / electrical job measures a consistent superset of items.
- t=14:58 (frame 59) - Back in the live run: skill asks "which architectural quantities should you take off?"; he answers "slab and floor area" and requests "an Excel BOQ plus a marked-up PDF."
- t=15:15 (frames 26-28, 68-70) - Confidence scoring: each quantity gets High/Med/Low so you know exactly which lines to re-check. Footings done by text count = very accurate.
- t=15:51 (frames 63-67, 72-77) - Self-audit by marking up the drawings (Bluebeam) with measured quantities. He spots one slab the AI wrongly extended into the office = a visible flag. Honest aside (t=16:42): the "look back at the markup" feedback loop has been hit-and-miss.
- t=16:47 - Summary of reliability: counting text tags "unbelievably accurate"; areas of slabs "not so accurate" UNLESS the slab has an explicit length x width on it (then 100%).
- t=17:21 - How to build your own: gather past takeoffs into a Cowork folder, tell Claude Code to build a takeoff skill, and use the Claude "goal" feature to iteratively self-improve / check / fix.
- t=18:06 (frames 78-80) - Final accuracy lever: a "sanity check" baked into the skill. For every measured quantity, AI re-derives a cross-check (e.g. cable tray runs the width of block C three times; if block C is 20 m, total should be ~60 m; if it computes 10 m or 100 m, something is wrong). Reduces gross hallucinations; does NOT improve precision.
- t=19:43 - Recap and a second Contractor OS pitch. Closes on the curriculum (frame 80): Estimating & Cost Management module - Cost Data Library, Estimating Suite, Quantity Takeoff, Payment Claims, Cashflow Forecaster, CVR Report, Cost Code Classifier.

---

## On-screen tools and Claude skills (names exactly as shown)

| Item | Type | Where seen | Notes |
|---|---|---|---|
| Claude Cowork ("Co-work") | App | frames 9, 19-20, 23, 59, 71 | Claude opened on a desktop folder; model picker "Opus 4.8 High". Spoken as Cowork/Cower; UI label "Cowork". |
| `/construction-takeoff` (skill title "Construction quantity takeoff") | Claude skill | frames 11-13, 19-20, 25, 29, 50-58 | Trigger: Slash command + auto. Files: SKILL.md, references/trade_checklists/, references/derivation_library.md, scripts/measure.py, scripts/split_extract.py. |
| `drawings-analyser` / "Drawing Analyser" (skill + course page) | Claude skill (prerequisite) | frames 14-17 | Builds prose layer (per-sheet markdown, symbol library, cross-reference graph) + structured layer (normalized SQLite DB). |
| `project-indexer` / "Project Indexer" | Claude skill | frame 24 | Turns a project folder into CLAUDE.md, project.md, drawings.md context files. |
| `construction-site-diary-setup`, `construction-cashflow-forecast`, `notion-construction-setup` | Other Claude skills (listed) | frames 24, 50 | Visible in the skills sidebar, not demonstrated. |
| Claude "goal" feature | Claude Code feature | t=17:54, frame 59 sidebar ("Claude Goal feature") | Set an objective; Claude iteratively improves/checks/fixes. Used to build the skill. |
| Bluebeam Revu (PDF viewer) | 3rd-party app | frames 1-8, 18, 33-34, 47-49, 63-67, 72-77 | Used to view drawings and the AI-marked-up PDF output. "BLUEBEAM" tab also appears in Excel ribbon. |
| Microsoft Excel (+ Claude and Bluebeam add-ins) | 3rd-party app | frames 26-32, 35-39, 43-46, 54, 60-62, 68-70, 78-79 | Holds the output BOQ and the primary/secondary quantity sheets. |
| PyMuPDF | Python library | split_extract.py docstring, frames 50-52 | "reads every selectable character with exact coordinates at 100% accuracy." Vector text extraction engine. |
| Contractor OS (community on Skool) | Paid community | frames 14-15, 80 | Curriculum: Project Set-Up (Project Indexer, Drawing Analyser), Bidding & Procurement, Estimating & Cost Management (Cost Data Library, Estimating Suite, Quantity Takeoff, Payment Claims, Cashflow Forecaster, CVR Report, Cost Code Classifier), Project Controls & Scheduling. |

---

## The workflow, step by step (reproducible how-to)

1. Pre-process the set once with the drawing-analyzer skill: split the merged PDF into single sheets, render a PNG per sheet, extract the vector text layer with coordinates, and build a structured database + per-sheet markdown so AI can reference where everything is cheaply. (His Project Indexer does the project-level CLAUDE.md/project.md/drawings.md layer.)
2. Open Claude Cowork on the project folder (desktop app) - NOT plain Claude chat, because large drawing sets fail to upload to chat.
3. Invoke the packaged skill: `/construction-takeoff`, or ask in plain language "perform a quantity take-off on the [trade] drawings in this folder."
4. Step 1 - Scope. AI reads the set, reads the title block / legend / schedules, reports what it found, and asks which trade and which quantities to take off (e.g. "slabs and floor areas only"). Human narrows scope here.
5. Step 2 - Build assemblies (primary vs secondary). AI lists the PRIMARY quantities it will measure directly (counts of text tags, explicit dimensions, scheduled values) and the SECONDARY quantities it will DERIVE by formula from the primaries (e.g. concrete volume = slab area x depth x waste factor; cable length = power-point count x 15 m ratio). Human approves the plan and can delete/override lines before any measuring.
6. Step 3 - Measure by the most reliable method available for the PDF type: vector text-tag count and explicit dimensions for vector PDFs; vision count for raster/compressed-image PDFs (flagged Low). Pull existing schedule quantities when present.
7. Confidence score every line (High/Med/Low) so the human knows which lines to re-check.
8. Sanity check every quantity against an independent cross-check derived from a different figure on the drawings (catches order-of-magnitude hallucinations).
9. Output in a fixed format: an Excel BOQ plus a marked-up PDF (drawings annotated with counts/dimensions for visual QC).
10. To build your own skill: drop past completed takeoffs into a Cowork folder, have Claude Code build the skill following this architecture (primary/secondary breakdown, confidence scoring, prefer vector over vision), and use the goal feature to self-test and auto-improve.

---

## What works / what does NOT (where he trusts AI vs refuses it)

Trusts (high reliability):
- Counting text tags extracted from the PDF vector layer ("100% accurately", "unbelievably accurate"). Footing counts, fixture counts, light-fitting counts.
- Reading explicit dimensions printed on the drawing (e.g. slab L x W noted on plan = 100% accurate area).
- Pulling quantities straight from a schedule already in the drawings.
- Deriving secondary quantities by simple formula from a reliable primary.

Refuses / distrusts (low reliability):
- Scaled measurements off the image (measuring geometry by pixel). "It struggles with this." Slab areas without printed dimensions = not accurate.
- Vision counting on compressed-image / raster PDFs (no vector layer) = returns Low confidence by design.
- Letting AI free-form decide what to measure across a whole set - he constrains scope to one trade and a discrete list.
- Free-form measuring on a real lump-sum bid - he says he would still do those quantities himself and spend hours checking.

Honest caveats he volunteers:
- The "look back at the marked-up drawing and re-validate" feedback loop has been hit-and-miss; he is not sure how much value it adds and needs more tests.
- The sanity check avoids big hallucinations but does nothing for precision.

The one-line principle on screen (frame 12/29/80): "The principle that makes it work on any trade: AI does judgement, scripts do plumbing." And (frame 80): "Drawings are the worst input you can hand an AI... The fix is to stop making it read the drawing and turn the drawing into data."

---

## Concrete numbers, rates, file names, examples shown

- Drawing set size that failed chat upload: 11 MB (also stated 10 MB); file "DRAWINGS - Combined.pdf", 30 pages = 15 unique sheets each printed twice (frame 71).
- Demo building: a small garage (bathroom, storage, work areas, tools room) for "Julio Mendoza, Caracas, Venezuela; drawn by E-Learning Australia, 2022"; title-block Scale field blank (so AI calibrates off printed dims) (frame 71).
- Structural worked example (frames 36-38): P1 - Warehouse SFRS slab 160mm N40 = 11,640 m2 (sheet S101); concrete formula basis "area x 0.160 x 1.025" (includes 2.5% waste). Other primaries: P2+P3 Office rafts 130mm N32 = 3,876 m2 (S102); P4 Sprinkler tank slab 275mm N32 = 100 m2; P5 Pump room slab 150mm N32 = 46 m2. Materials: concrete N40/N32, Dramix SD 65/60-BG steel fibre, HDPE membrane 0.2mm, crusher fines screed, mesh reinforcement.
- Structural BOQ columns (frames 26-31, 53, 68-70): Ref | Element | Tag | Qty | Unit | Sheet | Scale | Method | Confidence | Anchor check (blind agent) | Notes/basis. Method values: vector_extr, plan_extr, text_count, between_pad_faces, pattern_count, perimeter_calc, schedule, estimate. Pad footings F1-F15 in sizes 2100x2100x600, 2500x2500x600, 3000x3000x600, etc.; pile caps; office raft; despatch office raft; sprinkler tank slab; pump room slab.
- "Anchor check (blind agent)" column = a second blind sub-agent independently re-counts/re-derives as a cross-check (referenced in the construction-takeoff SKILL.md description: "Marks up every measured sheet and produces an Excel BOQ ... independently double-checked ... by a blind subagent").
- Electrical takeoff (raster PDF), "PRIMARY QUANTITIES - measured directly off the drawings | Umalusi Electrical (19034)" (frames 46, 78-79): LIGHT FITTINGS by vision count off Dwg 100/101 - A2 LED linear vapour-proof = 7, B1 LED panel = 74, B2/B2e 600x600 LED panel = 62, C1 Downlighter 10-12W = 61, C2/C2e Downlighter 20-25W = 22, total = 216, ALL Low confidence. CIRCUITS off single-line diagram (SLD count) = Medium. WIRING traced off plans (vector length @1:100, raw): Lighting wiring = 1360.8 m, Power wiring = 2944.9 m, method "Vector trace Dwg 100/101 / 200/201", Medium.
- Skill files: SKILL.md, references/trade_checklists/{architectural.md, civil.md, electrical.md, hvac.md, plumbing.md, structural.md, README.md}, references/derivation_library.md, scripts/measure.py, scripts/split_extract.py. Output files: Structural_Takeoff_BOQ_2101-0101...xlsx; S101-S105_takeoff_marked.pdf; p01.png-p07.png, probe.py in the session context.
- Cable derivation ratio example: 15 m of cable per power point (t=10:24).
- Sanity-check example: block C cable tray = 3 x block length; if block = 20 m, expect ~60 m (t=18:44).

---

## Applicability to a structural steel fabricator (Your Company)

What transfers directly:
- Primary-vs-secondary decomposition maps cleanly onto steel. Make the PRIMARY quantity the thing AI counts reliably: member marks / piece marks counted from the schedule text and the framing-plan tags (beam marks, column marks, joist marks, brace marks). Derive SECONDARY quantities (tonnage) by formula: count x length x weight-per-foot. This is EXACTLY the CLAUDE.md operating rule "the accuracy jump from ROM to bid-grade is a measured member takeoff (schedules plus framing-plan marks)" - Fairley's text-tag-count method IS that, mechanized. Tonnage must still route weight-per-foot through bridge/aisc_validator.py, never LLM math (Hard Rule 5).
- Vector-text-first extraction is a real upgrade to our drawing-analyzer skill. Our skill description says the model gives "approximate, not accurate, counts" off the rendered image. Fairley's split_extract.py (PyMuPDF, per-sheet, coordinates, raster-flag) shows how to make member-mark and schedule-QTY counts exact off the text layer instead of vision. We already have PyMuPDF in the stack. This is the same idea as our count-gap engines branch (A1 schedule-QTY reader, grid-geometry SF) - his approach validates that direction.
- Confidence tagging (High/Med/Low per line) is already our Operating Rule. His Method column + Confidence column + "always land a quantity, never leave blank, see SKILL.md Honesty about confidence" is a clean output schema we could mirror in bid takeoff outputs.
- The vector-vs-raster gate maps onto our drawing-completeness gate. If a steel set is a scanned/raster PDF with no selectable text, member counts are vision-only = LOW = ROM-only with an SF/scope RFI, exactly our SF-sourcing discipline.
- The "blind agent" cross-check is a verify-don't-generate pattern we already believe in (VirtualOwner review rules, bid_sanity_gates run_gates). A second independent sub-agent re-counting marks before a tonnage is priced is a concrete way to harden the count step.
- Fixed output format = our locked two-PDF + GP discipline. His standardized Excel BOQ schema is the same instinct; ours just has extra governance (no supplier names, rates from bid_rates.py).
- Sanity check (order-of-magnitude cross-derivation) transfers to steel: e.g. total tonnage / gross SF should land in a sane psf band for the building type; column count should roughly equal grid intersections; if it is 10x off, flag it. Cheap guard against a gross miscount feeding a price.

What does NOT transfer / needs caution:
- His domain is general/civil/fit-out (concrete slabs, footings, cable, light fittings, HVAC plant). His checklists are architectural/civil/mechanical/electrical, NOT structural-steel member takeoff. We need our own coverage checklist keyed to AISC shapes, connections, base plates, anchor rods, deck, joists, misc/secondary steel - not his concrete/MEP lists.
- Steel tonnage is unforgiving in a way slab concrete waste-factors are not. His "derive secondary by simple formula" is fine for concrete volume; for steel, weight must come from the AISC validator per mark, not a blanket formula. Do not let AI multiply a guessed weight.
- He explicitly does NOT trust AI for a real lump-sum bid and re-does quantities himself. For us that means: AI member-count is a verification/ROM aid and a check against a human takeoff, never the unguarded system-of-record number (matches our governance).
- Deck/composite area is the one "scaled area" case - his weakest case unless dimensions are printed. Source roof-deck/composite SF from stated areas or framing-plan dims, not pixel-scaling, consistent with "SF is the controlling input - source it, do not assume it."
- He uses Bluebeam for markup; we generate our own marked outputs and PDFs through the bridge. Adopt the marked-up-drawing QC idea, not his toolchain.

Net: the highest-value, lowest-risk import is the vector-text-tag count of member marks and schedule QTY (via PyMuPDF, per sheet) as the PRIMARY input, with a blind second-agent recount and per-line confidence, feeding tonnage only through aisc_validator.py. That is our count-gap work, with his confidence/sanity-check schema layered on top.

---

## Caveats

- Frame sparsity: 80 frames over 20:37 = roughly one frame every 15.5 s. Fast scrolls through Excel and the skill body are sampled, not exhaustive. Some cell values in the BOQ are at the edge of legibility at 512px; QTYs and headers I cite were readable, but a few mid-table Method/Notes cells were partially obscured by the presenter's webcam overlay (bottom-right) and are reported only where clearly legible.
- "Opus 4.8" is taken from the captions and the on-screen model picker label ("Opus 4.8 High", frames 9, 21). The model menu text is small; the exact build string was not separately verifiable, though both audio and UI agree on "4.8".
- The "blind agent" / "Anchor check (blind agent)" column wording is read from the BOQ header and the skill description text; the sub-agent mechanism itself was not shown executing on screen.
- Captions render m2/m3 oddly (e.g. "11,640 m" then corrected); units confirmed against the Excel frames (m2, m3, LM, No).
- This is partly a funnel for his paid Contractor OS community; the skill files shown are real but the full SKILL.md/derivation_library.md contents were only partially visible.
