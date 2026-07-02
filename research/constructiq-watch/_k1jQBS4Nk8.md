# Claude Code + Construction Drawings (_k1jQBS4Nk8)

- **URL:** https://www.youtube.com/watch?v=_k1jQBS4Nk8
- **Uploader:** Tim Fairley (ConstructIQ / "Contractor OS" community)
- **Duration:** 18:24 (1104.3s)
- **Frames analyzed:** 80 (0.072 fps, 512px wide, sparse coverage for an 18-min video)
- **Transcript source:** captions (522 segments, complete)

**Thesis:** Construction-drawing PDFs are the worst possible input for an LLM because meaning lives in tiny features and cross-references that vision tiling destroys, so Tim builds a Claude Code "drawings-analyser" skill that uses Python scripts for the cheap deterministic work (split PDF, extract vector text, render images, crop regions) and reserves the LLM for judgement (classifying sheets, resolving cross-references), pre-computing durable markdown/JSON indexes once so every later query is faster, cheaper, and more accurate than re-feeding the raw PDF.

## Chronological walkthrough (with t=MM:SS anchors)

- **t=00:02** Opening claim: construction drawings are "quite possibly the worst input into AI." Dense, large PDFs full of symbols and cross-references between multiple sheets.
- **t=00:37** Why AI struggles: when AI sees an image it breaks it into tiles (16x16 pixel patches), converts each to tokens, processes like text. A sample image becomes "roughly 4,000 tokens." Fine for a cat photo, terrible for drawings (frames 1-3 show the chat where this is narrated).
- **t=01:24** Meaning lives in tiny features. Examples given: a semi-dash line is a cold-water line, a line with two dashes is a hot-water line (visually similar, mean opposite things); code "TD7" on the sanitary waste drawings means nothing until you cross-reference the schedule to a specific trench drain; footing "F6" only makes sense if you reference the section drawings. Frames 7-8 show these exact symbols in Bluebeam Revu (plumbing sheets, TD-6/TD-7/KD-1, FS-1/FD-2 tags).
- **t=02:09 (frames 10-12)** Demo of the naive path: tries to upload an 11 MB (he also says 10 MB) "Plumbing Drawings.pdf" directly into the Claude desktop app ("Happy Sunday, Tim", model selector shows **Opus 4.7**). After ~1 minute it fails: "Failed to upload Plumbing Drawings.pdf. The file format may not be supported or the file may be corrupted" (frame 12).
- **t=02:46 (frame 13)** Opens Claude support docs in a browser confirming the **30 MB per-file** upload limit, so the failure is not a size issue. He notes drawing PDFs just refuse to upload for unknown reasons.
- **t=02:58 (frames 14-18)** Claude **Cowork** path: opens Cowork inside the folder holding the drawings. It can read them, but two problems: (1) usage cost, every query re-reads the full 10 MB set (~60-70k tokens per prompt); (2) it does nothing to fix Claude's drawing limitations. Demo prompt: "How many footings are shown on the foundation drawings?" Cowork answers **141** (frame 14 shows the working count: pad/isolated footings 109 = 75 warehouse + 34 office; with door pad footings DF1 ~32, total 141). He states the true answer is lower; Cowork over-counted.
- **t=04:03 (frames 19-21)** Contrast: the pre-processed drawing-analyzer path in **Claude Code** runs a quantity takeoff and returns the *correct* foundation count, a breakdown by type, a **confidence** rating per item (HIGH/MEDIUM/LOW), and **cites which drawings** it used. Frame 20 shows the footing schedule table (F1-F24 with counts, sizes, types, confidence; SF1/GB1 marked LOW (linear)). Right panel shows sheet 5120-S101 Footing and Ground Floor Plan with title-block metadata extracted.
- **t=04:51** Names the mechanism: a "drawing analyzer workflow or drawing analyzer skill." It splits drawings into individual files, gives a text representation + image of each, and builds a register of drawings, summaries, cross-references, coordination indexes, and an overall package summary. Reading those markdown indexes is far cheaper than re-reading 10 MB every query.
- **t=05:39** Offers the skill, code, and scripts via a link in the video description. Notes Claude lets you upload pre-built skills.
- **t=05:53** Camera-failure aside; he restarts the explanation.
- **t=06:13 (frames 27-31, 33)** Sourcing the "why." Source 1: Anthropic's own Claude API docs, "Images and vision -> Limitations" page (frames 27-31). Lists four relevant drawbacks: **Accuracy** (may hallucinate on low-quality/rotated/small images), **Spatial reasoning** (limited; struggles with precise localization or layout; their own examples are reading an analog clock or exact chess-piece positions), **Counting** (gives approximate, not accurate, counts), plus people-identification and AI-generated-image caveats.
- **t=07:12 (frames 33-34)** Source 2: an academic paper, **"CEQuest: Benchmarking Large Language Models for Construction Estimation"** by Yanzhao Wu, Lufan Wang, Rui Liu (Florida International University / University of Florida, dated 22 Aug 2025 in the margin). Four issues found, paraphrased: general-purpose models trained on the whole internet (1) poorly identify drawing elements (scale, title block, whether a sheet is a layout vs section vs schedule); (2) miss the set organization (general notes, layouts, sections) and the cross-referencing; (3) poor spatial reasoning; (4) only Google-level general construction knowledge, no real understanding of construction process.
- **t=08:50 (frames 40-44)** "Most obvious thing to do" tangent: skip PDFs, get the **BIM model**, a 3D structured database that already holds quantities and volumes. Shows the **buildingSMART Industry Foundation Classes (IFC)** page (frames 40-44) and the Autodesk Platform Services "Talk to your BIM" blog with an architecture diagram **User -> Claude Desktop -> MCP Server -> Authentication / AEC Data Model** (frame 43), i.e., Autodesk MCP connections to extract directly. Caveat: in Australia (and bidding generally) you usually never get the BIM model, so the PDF pipeline is still needed.
- **t=10:05 (frames 22-26, 45-52)** The drawing-analyzer skill in detail. Core principle (t=10:31): "use scripts to do the cheap, easy stuff" (splitting PDFs, extracting vector data via Python) but "the actual categorization and understanding the drawings, it uses AI for." Frame 26 / 48-50 show the skill open in Claude Code's Skills panel: skill name **drawings-analyser**, trigger "Slash command + auto", with `SKILL.md`, a `references/` folder (`drawing_types.md`, `output_schemas.md`), and a `scripts/` folder (`build_sheet_index.py`, `crop_region.py`, `process_drawing.py`, `query_drawing.py`), plus `wrapup` and `om-manual` entries.
- **t=11:17** Key warning: Claude Code "always wants to write scripts to do these tasks" (classifying sheets). You must stop it. A script that pattern-matches title text ("if title says electrical, it's an electrical drawing") fails because of the huge variety and minute formatting differences across drawing sets. Classification must be done by the AI, not a regex script.
- **t=11:55 (frames 22-25, 53-60)** The output artifacts it creates for the 11 MB compiled set (frames 22-23, 53, 75-76 show the folder `drawings_analysis/`): `drawings.md` (overall summary, ingested on every task), `sheet_classification.json` (per-sheet type + detail, ~5 KB text files), `cross_references.json` (which drawing references which and why), `coordination_issues.md`, `sheet_index.json`, and a `drawings_split/` folder with per-sheet `.pdf` + `.png` (image) + `.json` (vector text) (frames 24, 59, 70). First read text, then image, then only if needed the PDF.
- **t=13:31 (frames 47, 61-66)** Worked example in Claude Code: "What is the area of the warehouse slab?" The agent offers two methods and he says "run both to cross-check": (1) **polygon extraction** of vector data from the specific drawing via `query_drawing.py polygons`; (2) overall warehouse perimeter dimensions multiplied. Result (t=14:35): gross building footprint **13,250 m squared**, best-estimate warehouse slab **~12,500 m squared**. He measured the same slab in **Bluebeam** and got **13,600 m squared** (measuring the entire slab including external slabs the AI excluded), so the AI estimate was very close. Frames 61-66 show the full agent reasoning, including that Method 1 (polygon) partially failed (the slab outline was not a closed polygon, returned 4,348 m squared from open line segments), Method 2 derived the grid from bubble positions, and dimensions live in the vector text layer (5101 parses as ~3,138 strokes, not characters, no OCR available, so it suggests installing **pytesseract**).
- **t=15:11** Step-by-step recap of the pipeline (see how-to below), including the **maximum rendering** image step (frame stated "Opus 4.7, Claude's most recent visual model" maximum DPI).
- **t=17:03** A later addition not in the recorded steps: a **symbol library** step that extracts symbols across all drawings and builds a referenceable legend text file.
- **t=17:28** Builds a **detailed cross-references library** so the model understands how the whole set fits together.
- **t=17:50 (frames 67-69, 79-80)** Token accounting. Asked Cowork "how many tokens did you use?" Answer (frame 67): **60,211 tokens across 26 tool calls**, about 5 minutes of runtime, all the heavy lifting (rendering PDF pages to images, reading them, cross-referencing) inside the ~60k window. Then he runs the same warehouse-slab query in Cowork live (frames 68-69, 79-80) to compare accuracy; it runs 27 steps generating temp crops (`_tmp_s101_*.png`).
- **t=17:50** Admits he did not run the Cowork comparison before recording; it has "been going for 10 minutes"; he will post the Cowork result in the comments. Closing claim: this pipeline guarantees higher accuracy, fewer tokens, for takeoffs or other purposes.

## On-screen tools and Claude skills/commands (table; names EXACTLY as shown)

| Item (verbatim) | Type | Frame(s) / time |
|---|---|---|
| Claude Code | App (terminal-style agent UI, dark) | frames 1, 19-21, 47-52, 61-66 |
| Claude Cowork ("Cowork") | App (folder-scoped agent UI) | frames 14-18, 67-69, 79-80 |
| Claude desktop app ("Happy Sunday, Tim") | App | frames 10-12 |
| Opus 4.7 | Model (selector, also "Claude's most recent visual model") | frames 12, 17, 67-69 |
| `drawings-analyser` | Skill name in Skills panel | frames 26, 48-52 |
| Trigger: "Slash command + auto" | Skill trigger config | frames 26, 48 |
| `SKILL.md` | Skill body file | frames 26, 49-50 |
| `references/` -> `drawing_types.md`, `output_schemas.md` | Skill reference files | frames 26, 48, 51-52 |
| `scripts/` -> `build_sheet_index.py`, `crop_region.py`, `process_drawing.py`, `query_drawing.py` | Skill Python scripts | frames 26, 48, 50 |
| `drawings_analysis/` | Output folder | frames 22-23, 53, 75-76 |
| `drawings.md` | Output (overall summary, MD) | frames 23, 53-54, 75 |
| `sheet_classification.json` | Output (per-sheet classification) | frames 23, 53, 55-56, 73 |
| `cross_references.json` | Output (cross-ref matrix) | frames 23, 53, 57, 77-78 |
| `coordination_issues.md` | Output (coordination index) | frames 23, 53, 75 |
| `sheet_index.json` | Output | frames 23, 53, 75 |
| `drawings_split/` | Output (per-sheet pdf+png+json) | frames 24, 45, 59, 70-71 |
| `takeoff_output` | Output folder | frame 22 |
| `.claude` | Claude Code config folder | frame 22 |
| `query_drawing.py polygons` | Command shown in agent reasoning | frames 47, 61-66 |
| Bluebeam Revu | Third-party PDF/takeoff tool (manual ground-truth) | frames 7-9, 32, 35-39, 65 |
| Claude API Docs "Images and vision" / "Limitations" | Source doc | frames 27-31 |
| CEQuest paper (Wu, Wang, Liu; FIU/UF) | Source doc | frames 33-34 |
| buildingSMART "Industry Foundation Classes (IFC)" | Source doc | frames 40-42, 44 |
| Autodesk Platform Services "Talk to your BIM" + MCP architecture diagram | Source doc | frame 43 |
| pytesseract | Suggested OCR dependency | frame 66 (reasoning text) |

## The workflow, step by step (reproducible how-to)

This is the "drawings-analyser" skill, run once per new drawing set, then queried many times. Naming and the script set are from frames 26 and 48-66; behavior from t=10:05 to t=17:45.

1. **Split the merged PDF** into one PDF per sheet (deterministic Python; `process_drawing.py` / the split scripts). Output to `drawings_split/`.
2. **Render an image per sheet** at the maximum DPI the vision model (he says Opus 4.7) can ingest, so the AI reads the finest detail possible. Output a `.png` per sheet.
3. **Extract the vector text layer** per sheet to a `.json` (relevant text strings with bounding boxes; not OCR, the actual PDF vector text). This is the cheap, fast representation read first.
4. **Build the sheet classification index** (`build_sheet_index.py` orchestrates, but the *classification itself is done by the AI*, not a regex). For each sheet the AI reads the rendered image + text, reads the title block, and classifies discipline + drawing_type per the taxonomy in `references/drawing_types.md`, returning JSON: `sheet_id`, `title`, `discipline`, `drawing_type`, `confidence` (high/medium/low), `justification` (one sentence). Aggregate into `sheet_classification.json` (frames 51-52, 55-56).
5. **(Added later) Build a symbol library / legend** by extracting symbols across all sheets into a referenceable text legend (t=17:03).
6. **Build the cross-reference library** (`cross_references.json`): per sheet, what it references and why, with `source_sheet`, `source_type` (section_marker, detail_bubble, text_reference, general_arrangement, elevation, etc.), `source_label`, `target_sheet`, `target_type`, `resolved` (true/false), `reason` (frames 57, 77-78). Also `coordination_issues.md`.
7. **Write `drawings.md`** as the overall package summary (project, source file, sheet count, what is on each sheet, plus instructions on how to query the drawings and when to fall back to vector data or the raw PDF). This file is ingested on every later task (frames 53-54).
8. **Querying (every later request):** the agent reads `drawings.md` first, then the relevant `sheet_classification.json` / `cross_references.json`, locates the specific sheet, reads its text `.json`, then its `.png` image, and only if necessary opens the per-sheet PDF. For a takeoff it can run `query_drawing.py polygons` to pull vector polygons for area. He recommends pairing a **precise method with an order-of-magnitude sanity check** ("run both to cross-check") for any takeoff.

## What works / what does NOT (where he trusts AI vs refuses it on drawings, and why)

**Trusts AI for:**
- **Sheet classification and understanding** (discipline, drawing type, what is on each sheet). Reason: too many drawing formats and minute formatting differences for a script to pattern-match reliably (t=11:17). This is the one place he explicitly forbids letting Claude write a script.
- **Cross-reference resolution and summarization** into durable indexes.
- **Reading the rendered high-DPI image + vector text** to answer scoped questions, *after* pre-processing.

**Refuses / distrusts AI for:**
- **Direct upload of raw drawing PDFs** to the chat app (fails outright) or relying on raw vision counting. Counting is "approximate, not accurate" (Anthropic's own docs). Cowork over-counted footings (141, true count lower) precisely because it counted from rendered images (t=03:46, t=04:00).
- **Spatial / localization tasks** done by vision alone (analog-clock / chess-piece analogy).
- **Writing pattern-matching classification scripts** (will look right, fail silently across sets).

**Trusts deterministic Python (not AI) for:**
- Splitting PDFs, extracting vector text/data, rendering images, cropping regions, polygon extraction. "Use scripts for the cheap, deterministic work" (t=10:31).

**Honesty / open issues he flags:**
- Polygon extraction *partially failed* on the warehouse slab because the slab outline was not a closed polygon (returned 4,348 m squared of open segments); he fell back to grid-from-bubbles and dimension strings (frames 63-66).
- No OCR in the box; suggests installing `pytesseract` (frame 66).
- He did not validate the Cowork-vs-pipeline accuracy comparison before recording (t=17:50); promises results in comments. Treat the headline accuracy claim as anecdotal on one slab, not benchmarked.

## Concrete numbers, rates, file names, examples, code/scripts shown

- Image tokenization: 16x16 pixel patches; sample image "roughly 4,000 tokens" (t=00:53).
- Drawing set size: 10-11 MB compiled PDF; Claude file-upload limit is 30 MB/file (t=02:46).
- Cowork per-query cost: "60 or 70,000 tokens" estimated (t=03:31); measured **60,211 tokens across 26 tool calls, ~5 min** for the footing count (frame 67).
- Footing count: Cowork answered **141** (109 pad/isolated = 75 warehouse + 34 office, plus ~32 door pad footings DF1); pipeline returned the lower correct count with per-type confidence (frames 14, 20).
- Warehouse slab area: pipeline gross footprint **13,250 m squared**, best-estimate slab **~12,500 m squared**; Method-1 open-segment polygon **4,348 m squared** (failed); Bluebeam manual ground truth **13,600 m squared** (frames 63-66, t=14:35-15:07).
- Index file sizes: classification/cross-ref text files "like 5 KB" (t=12:43); `drawings.md` ~11 KB, `coordination_issues.md` ~8 KB, `sheet_index.json` ~20-25 KB, `cross_references.json` ~21 KB (frame 23).
- Project on screen: "5128 Proposed Warehouse, Yatala QLD," engineer **Spencer Group Engineering Pty Ltd**, sheet IDs like `5120-S101`, `5120-S201`, file `40318320S-D-3-2-Structural-Dwgs-T2-25-No.pdf`, sheets `..._sheet1.pdf/.png/.json` etc. (frames 20, 24, 35, 54). Footing marks F1-F24, SF1, GB1, DF1; plumbing tags TD-6/TD-7, KD-1, FS-1, FD-2, SK101.
- Scripts (verbatim names): `build_sheet_index.py`, `crop_region.py`, `process_drawing.py`, `query_drawing.py`. References: `drawing_types.md`, `output_schemas.md`. Skill body: `SKILL.md`.
- Classification JSON schema (frame 51, verbatim keys): `sheet_id`, `title`, `discipline`, `drawing_type`, `confidence`, `justification`, aggregated into `sheet_classification.json` with a top-level `classified_at` and `sheets[]`.
- Cross-ref JSON keys (frames 57, 77-78): `source_sheet`, `source_type`, `source_label`, `target_sheet`, `target_type`, `resolved`, `reason`.
- BIM route: Autodesk Platform Services MCP, diagram User -> Claude Desktop -> MCP Server -> Authentication / AEC Data Model; IFC = ISO 16739 (frames 40-44).

## Applicability to a structural steel fabricator (Your Company)

This video is squarely on-target for our bid pipeline. The architecture he reverse-engineers is almost identical in spirit to our `drawing-analyzer` and `project-indexer` skills, and validates several of our existing rules.

**What transfers directly:**
- **Use Claude Code, not Cowork/chat, for drawing-heavy takeoff work.** His core finding is exactly our Hard Rule mindset and the `drawing-analyzer` skill description: "Never measure scaled quantities from the image; the model gives approximate, not accurate, counts." He demonstrates the failure (141 footings, over-counted) and the fix. Our `drawing-analyzer` already splits the merged PDF into one file per sheet, renders a high-res image per sheet, and extracts the PDF vector-text layer to count from text not pixels. His pipeline is the same three moves. We should treat his result as external confirmation of our design.
- **Pre-compute durable indexes once, query cheaply.** His `drawings.md` + `sheet_classification.json` + `cross_references.json` map onto our `project-indexer` output (`0.ai-context/CLAUDE.md`, `project.md`, `drawings.md`, `memory.md`) that "cuts query token use roughly 20 to 40 times." His measured 60k tokens/query for the naive Cowork path is the number our indexer avoids. Worth adding his cross-reference matrix and a coordination-issues file to our `drawings.md` output if we do not already emit them.
- **Vector text + bounding boxes, not OCR, as the cheap first read.** His per-sheet `.json` text layer is exactly what feeds our member-mark counting (AISC marks, footing marks, joist tags). For us, a `query_drawing.py polygons` equivalent over PyMuPDF (we already ship PyMuPDF for drawing parsing) could pull slab/roof-deck areas and bay-grid geometry. This is directly relevant to our open `feature/count-gap-sf-a1` work (grid-geometry SF / Engine B and the A1 schedule-QTY reader): his "grid extent from bubble positions" method is the same idea as our grid-geometry SF engine, and his honest failure mode (open polygon -> wrong area) is a caution our SF gate should encode.
- **AI classifies, scripts never pattern-match.** His strongest reusable lesson: do not let Claude Code write regex/title-string classifiers for sheet type or discipline. Use the model with a fixed taxonomy + JSON schema + confidence + one-line justification. Our drawing-analyzer should classify structural vs section vs schedule vs general-notes via the model, which also reinforces our "drawing-completeness gate" and "SF is controlling, source it" rules (a sheet classified as a structural-only subset should not have gross area harvested).
- **Confidence tagging + cite the source sheet.** His output returns HIGH/MEDIUM/LOW per line and names the drawings used. This is identical to our Operating Rule "Confidence tagging" and "Be explicit about data source." His footing schedule (F1-F24 with confidence, SF1/GB1 marked LOW (linear)) is a model for how our AISC member takeoff should present counts.
- **Precise method + order-of-magnitude sanity check.** His "run both to cross-check" maps onto our `run_gates()` 4-gate sanity check and the $/SF gate. Adopt his pattern: polygon/vector takeoff as the precise number, grid-extent or footprint-times-psf as the sanity check, flag divergence.

**How it slots into our stack:**
- **Bridge / drawing-analyzer:** add (or confirm) a per-sheet vector-text extractor and a polygon/area extractor in the `bridge/` modules behind the `drawing-analyzer` skill; emit a `cross_references.json` and `coordination_issues.md` alongside the existing per-sheet outputs. Keep AISC weights from `bridge/aisc_validator.py` only; his pipeline never claims member weights, so no conflict.
- **MCP server:** his BIM tangent (Autodesk APS MCP: User -> Claude Desktop -> MCP Server -> AEC Data Model) is a real pattern we could mirror. We already run an MCP server sharing the Bridge class. If a client ever provides a Tekla/IFC model, an MCP route that extracts tonnage/areas directly from the model (analogous to his Autodesk MCP) would beat PDF inference, and our Tekla viewport pipeline already touches the model side. Out of scope for the common case (no model provided), same as his Australian-bidding caveat.
- **Sub-agents:** his per-sheet classification is embarrassingly parallel; our `vj-scan` async/background-thread pattern and sub-agent fan-out fit it well.

**What does NOT transfer / cautions:**
- His units are metric (m squared) and his example is a warehouse slab for a general-contractor estimator, not a steel-fab member takeoff. We do not price by slab area; SF feeds tonnage and the $/SF gate, then a *measured member takeoff* (schedules + framing-plan marks through `aisc_validator.py`) is what makes it bid-grade. Do not let his slab-area accuracy claim leak into a belief that AI vision can size members.
- His accuracy headline is anecdotal (one slab, Cowork comparison not finished on camera). Treat as directional, not benchmarked. Our governance "Verify, do not generate" still rules: counts and tonnages get a verification step.
- `pytesseract`/OCR: we already avoid trusting LLM math and OCR for system-of-record numbers. If we add OCR it is for locating text, never for the priced quantity.
- His skill is a downloadable third-party artifact (link in video description). Do not import his code into our repo under our governance without a Dependency-tax review; the *method* transfers, the *binary* does not.

## Caveats

- **Frame sparsity:** 80 frames over 18:24 (one every ~13.8 s, 512px wide). Fine-grained code in the script files (e.g., the full body of `build_sheet_index.py` past line ~30, frame 50) and small JSON values are partly unreadable at this resolution; key file/skill/script names, the JSON schemas, the folder tree, and the numbers above were legible across multiple frames and are reliable. For exact script source, the video description link would be needed (not followed here).
- Transcript is from captions (522 segments), auto-generated, so a few words are garbled (e.g., "F-type" near t=02:18, "[snorts]" artifacts); meaning is clear from context.
- The naive-upload model selector reads **Opus 4.7** (frames 12, 17, 67); he also calls it "Claude's most recent visual model." This is a model id shown in his build, not necessarily current.
- I did not follow external links (video description, the CEQuest paper, Autodesk blog); citations above are to what is on screen.
