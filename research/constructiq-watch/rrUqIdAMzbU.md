# AI Quantity Take-offs - Actually Worth Using? (rrUqIdAMzbU)

- URL: https://www.youtube.com/watch?v=rrUqIdAMzbU
- Uploader: Tim Fairley (ConstructIQ / Contractor OS)
- Duration: 15:54 (953.6s)
- Frames analyzed: 80 (0.084 fps, full mode, 512px wide)
- Transcript source: captions (425 segments)

Thesis: Off-the-shelf AI quantity-takeoff products are not worth it (too expensive, never 100% accurate, slower than a human or a Philippines outsourcer once you actually have the drawings), but a self-built agent that uses code as deterministic "hands" and the LLM only as a "brain" - counting tags from PDF vector text, never AI vision, with per-item confidence and mandatory human sign-off - is genuinely useful for three narrow jobs: conceptual/ROM estimating, building the list of items to measure, and cross-checking a finished takeoff.

## Chronological walkthrough (with t=MM:SS anchors)

- t=00:03 (frame 1-2): Opens with the ClockBench benchmark (clockbench.ai). Premise: reading an analog clock is trivial for humans but very hard for current AI vision, and measuring ductwork off a drawing is harder still. Human baseline 90.7%; top AI model ~50%.
- t=00:35 to 01:06 (frames 2-7): Walks the ClockBench leaderboard. GPT 5.4 high tops at ~50% (called an outlier). Most recent models including Claude Opus 4.6 score under 10%. Gemini 3.1 Pro (his stated working model for drawings) scores 32.2%. Point: LLMs are strong at math/reasoning/language but weak at "simple" visual tasks.
- t=01:31 to 02:00 (frame 7): Draws the key distinction - classifying a drawing ("this is an architectural layout") is easy; taking a precise scaled measurement from a specific region of a drawing is a fundamentally different and hard task because of how models process visual data.
- t=02:00 to 03:09 (frames 8-18): "Is AI useless for QTO? Not necessarily." Splits the video into two parts. Editorial verdict on commercial AI QTO tools: pricing is "astronomically high," none claim 100% accuracy, and if your goal is drawings-in / bill-of-quantities-out in your format, outsourcing to the Philippines via Fiverr or Upwork is cheaper and more accurate. Shows a real residential drawing set in Bluebeam Revu (file "Drawings_(Arch_Elec_Mech)", 31 pages, Iredale Architecture title block; rooms named Cedar/Birch/Arbutus/Maple/Willow/Spruce, Darts Room, Billiards).
- t=03:22 to 03:53 (frames 19-20): Recommends Gemini for best visual reasoning. Searches "visual reasoning benchmark"; shows a second benchmark, AIMultiple's "Visual reasoning benchmark" bar chart, to back the Gemini claim.
- t=04:02 to 06:00 (frames 21-32): Explains how a model ingests a PDF. Two layers: (1) vector data - the encoded text, lines, symbols and their coordinates (he uses Bluebeam Revu; demonstrates text-search highlighting tags); (2) the rendered image. Models extract the vector data AND, in parallel, rasterize the PDF to images. Because a model cannot process a whole large drawing at once, it breaks it into overlapping tiles and usually compresses, so you lose pixels versus a real PDF reader.
- t=06:00 to 07:05 (frames 33-39): Part one build. Picks Gemini (chat shown), then says the chat interface is too limited (you can only upload + prompt). Moves to Google Antigravity - a downloadable agentic IDE ("next-generation IDE") that runs Gemini against a desktop folder. Opens an "Example" folder containing the drawing set; left file explorer shows the project files.
- t=07:21 to 08:30 (frames 36-46): The leverage idea: let Gemini WRITE code once, then RUN that code deterministically. Tasks like splitting a 40-page PDF into individual files are code jobs, not AI jobs. He prompted Gemini to write utility scripts. On screen the `utils` folder holds Python files: `split_pdf.py`, `extract_vector_text.py`, `write_excel.py`, `contact_sheet.py`, `write_pdf.py`, plus a `split_and_index.py` entrypoint. Code visibly imports `fitz` (PyMuPDF), `pandas`, `openpyxl`, and PIL. He gave it three jobs: split PDF page-by-page (smaller context = more accurate per page), increase tile resolution (shrink physical tile size, raise DPI - more tokens but more accurate), and extract the vector-data text layer.
- t=09:50 to 10:18 (frame 50 area, narration): The counting principle by example. To count split-system units, find the tag (e.g. CU5) on the layout; once vector data is extracted, every "CU5" is just text in a big blob, so AI counts the text occurrences very accurately - no vision needed.
- t=10:20 to 11:02 (frames 53-57): Shows the system prompt file `qto-workflow.md` (full text below). Core rule: never use AI vision when you can count tags or read vector data; primary quantities first then derived secondary; one drawing at a time; state a confidence level per item; the user verifies.
- t=11:02 to 12:11 (frames 57-61): Runs the workflow ("you have access to a set of construction drawings, please complete a quantity take-off using my workflow"). The agent returns an implementation plan (proposed items, pages, methods, open questions), the user approves, it executes, and writes `Master_BoQ.xlsx` - 46 tabulated items. Excel shown (frame 61) with columns Trade / Tag / Description / Quantity / Unit / Confidence / Method / Assumptions. Example: AC-1 "Air Conditioning Unit" = 4 Nos, High confidence, method "Counted from explicitly tagged references on plans"; derived rows (refrigerant pipe, condensate drain, etc.) carry Low/Medium confidence and an explicit assumption string.
- t=12:11 to 13:07 (frames 62-66): "These tools are not good on first use; you iterate and get it to fix itself." Re-runs with refinement (group derived quantities under their primary; restructure the JSON / Excel).
- t=13:09 to 14:08 (frames 67-72): The skeptic's core argument, demonstrated in a browser takeoff tool (Cztakeoff / cztakeoff.com, "Electrical Example" project). He manually clicks count points on light fittings; the right-hand assembly panel auto-derives support brackets, 2.5mm2 cable, electrician hours, cable tray from the count (fittings climb 21 -> 33 -> 50 -> 54; cable updates 270 -> 287). Point: once you know what to measure, manually counting and measuring "genuinely isn't that long." He doubts the time-saving people expect from AI QTO. If it is a huge task, outsource it.
- t=14:08 to 14:38 (frames 72-78): The one clearly safe automation is deterministic assemblies - once items are measured, simple assemblies derive all secondary quantities with no AI and no risk. (Tool warns "Page Not Scaled - you must scale the page before doing takeoff measurements" at frame 78, underlining that measurement needs a real scale, not vision.)
- t=14:10 to 15:52 (frames 73-80): The three legitimate AI use cases (the real verdict, below). Closes on AI as an error-checking second pass, "we're not relying on AI."

## The verdict (is AI takeoff worth it?)

His answer: commercial AI QTO software is NOT worth it; a self-built, code-backed agent IS worth it for three narrow tasks; AI must never be the system-of-record counter.

Where it FAILS / he rejects it:
- Commercial AI QTO tools: "astronomically high" pricing, none claim 100% accuracy, and slower/less accurate than outsourcing (Fiverr/Upwork, Philippines) for a full formatted BoQ.
- AI vision for measuring or counting off the rendered image. Vision is the backup, never the default. Anything tagged in the PDF must be counted from vector text, not pixels.
- The premise that AI saves meaningful time on the actual count once you know what to measure. He argues manual counting "doesn't take that long."

Where it SUCCEEDS / he endorses it (three use cases, t=14:10 to 15:52):
1. Conceptual / order-of-magnitude estimating, where a missed quantity here or there is acceptable for an initial budget price.
2. Generating the list of items to measure - one of the most time-consuming parts of a takeoff is working out WHAT to measure across many drawings. Let AI read the set and return that list (and even pre-build the secondary assemblies), then a human does the actual measurement in the takeoff tool.
3. Cross-checking / error-checking a human-measured BoQ - feed your outputs plus the drawings to AI to catch errors. "We're not relying on AI, we're just using it as an error-checking tool."

Accuracy claims (all from ClockBench, t=00:26 to 01:06): human baseline 90.7%; top model GPT 5.4 high ~50% (50.6% shown on the site, frame 2); most recent models incl. Claude Opus 4.6 under 10% (8.0% range, frame 5); Gemini 3.1 Pro 32.2%. He never claims a numeric accuracy for his own workflow; the workflow output is explicitly "not final without user sign-off."

## On-screen tools and Claude skills (names EXACTLY as shown)

| Name (as shown) | What it is | Frame / time |
|---|---|---|
| ClockBench / clockbench.ai | Analog-clock visual-reasoning benchmark (36 clock faces, 180 clocks, 720 questions) | frames 2-7, t=00:03 |
| Visual reasoning benchmark (AIMultiple, aimultiple.com/visual-reasoning) | Second bar-chart benchmark used to argue Gemini is best | frame 20, t=03:45 |
| Bluebeam Revu | PDF takeoff tool he uses to view drawings and search tags | frames 1, 8-32, t=04:33 |
| Google Gemini (gemini.google.com/app) | The LLM he recommends; "best visual reasoning" | frames 33-34, t=06:09 |
| Google Antigravity (antigravity.google) | Downloadable agentic IDE running Gemini against a desktop folder; "the brain, the tools are the hands" | frames 35-66, t=06:49 |
| Cztakeoff (cztakeoff.com) | Browser takeoff app; manual count points + auto-deriving assemblies | frames 67-80, t=13:07 |
| GPT 5.4 high | Top ClockBench model, ~50% | frame 4, t=00:40 |
| Gemini 3.1 Pro | His drawing model, 32.2% ClockBench | frame 3, t=00:58 |
| Claude Opus 4.6 | Cited as <10% on ClockBench | frame 5, t=00:51 |

His own project files (Antigravity "Example" folder): `.agents`, `qto_working`, `tmp`, `utils`, `Drawings_(Arch_Elec_Mech).pdf`, `Master_BoQ.xlsx`. Utility scripts: `split_pdf.py`, `split_and_index.py`, `extract_vector_text.py`, `extract_vector_test.py`, `write_excel.py`, `write_pdf.py`, `contact_sheet.py`. Workflow/system-prompt file: `.agents/workflows/qto-workflow.md`. No Claude Code "skills" appear; this is a Gemini-in-Antigravity build. Notably his architecture mirrors our own drawing-analyzer skill (split per sheet, render hi-res image, extract vector text, count from text not pixels).

## Concrete numbers, accuracy comparisons, examples shown

- ClockBench (frame 2): 36 clock faces, 180 clocks, 720 questions, human accuracy 90.7%, top model accuracy 50.6%.
- Leaderboard (frames 4-6): GPT 5.4 high 50.6%; Qwen 3-VL 235B Instruct ~26.4%; Gemini 3.1 Pro 32.2%; Gemini 3 Pro ~28.9%; Gemini 2.5 Pro ~18.9%; GPT 5.2 high ~15%; Claude Opus 4.6 ~8.0%; Claude Opus 4.1 ~8.3%; Claude Sonnet 4.5 ~7.2%; (values read from a 512px frame, treat the lower digits as approximate).
- His BoQ output: 46 tabulated items in `Master_BoQ.xlsx` (frame 41 narration "46 tabulated items"; frame 61 Excel).
- Worked example (frame 61): AC-1 "Air Conditioning Unit" = 4 Nos, confidence High, method "Counted from explicitly tagged references on plans"; derived rows (DER-AC-*) for refrigerant pipe, condensate drain (PVC), supply/return air grilles, isolators, controls wiring - each Low/Medium confidence with an explicit assumption (e.g. "Assumes XX run per unit").
- Cztakeoff manual count (frames 67-80): B3 Light Fittings counted live 21 -> 33 -> 50 -> 54; 2.5mm2 Electrical Cable derived 270.00 -> 287.00; Cable Tray linear measure 100 -> 108 -> 135 m; tool warning "Page Not Scaled" when measuring before scaling.

## Applicability to a structural steel fabricator (Your Company)

His architecture is close to ours and validates the count-gap branch direction, with important caveats for steel.

What to ADOPT:
- Vector-text-first counting over vision. His Principle 1 ("Never use AI vision for something the vector data already captured ... Count it programmatically. Vision is the backup, not the default") is exactly the count-gap thesis. For us this maps directly to reading member marks and piece marks (e.g. a beam tagged W18x35 [B-12], a column tag C-3) from the PDF text layer rather than from the rasterized image. Our AISC member counts should come from counting tag occurrences in extracted text, and only fall back to vision on dense or untagged drawings.
- Per-item confidence tiering tied to METHOD, not a vibe. His three tiers - High = vector data, Medium = schedule reading or vision on a clear drawing, Low = vision on dense drawings or inferred-with-assumptions - are a cleaner, more defensible scheme than a generic high/med/low and align with our CLAUDE.md confidence-tagging rule. Worth mirroring in the count-gap output: tag-text match = High, schedule-row read = Medium, vision/inferred = Low. Each Low item also carries an explicit assumption string in his Excel; we should do the same so a human knows precisely what to verify.
- Schedule reading as a distinct, higher-confidence path. He treats a door schedule as "high confidence" reading. For us the analog is the steel member schedule / column schedule / joist schedule - read the schedule rows for the authoritative size and count, and reconcile against the framing-plan tag count. That reconciliation (schedule QTY vs plan-mark count) is precisely the gap our A1 schedule reader and Engine B target. His workflow's "primary then derived" ordering also matches: count members first, then derive tonnage via aisc_validator, never the other way.
- Code-as-hands, LLM-as-brain split. Deterministic Python (split per sheet, hi-res tile, extract text, write Excel) does the mechanical work; the model only decides what to count and judges results. This is already our posture (drawing-analyzer + project-indexer are deterministic pre-processing) and reinforces keeping tonnage/weights out of the LLM. His "split one drawing per page, smaller context = more accurate" matches drawing-analyzer's per-sheet split.
- Two of his three endorsed use cases transfer cleanly: (a) AI builds the list of items to measure (for us: enumerate the distinct shapes/marks/connection types present so an estimator does not miss a member type), and (b) AI cross-checks a finished human takeoff for errors. Both are "verify, do not generate" uses that fit our governance.

What to REJECT or treat carefully:
- His use case 1 (conceptual/ROM estimating where a missed quantity is acceptable) collides with our hard rule: accuracy errors cost real money, and our jump from ROM to bid-grade requires a measured member takeoff through aisc_validator, not SF x psf. We can use his ROM workflow only behind our existing LOW-SF / ROM-only flagging and SF-confirmation RFI gate - never as a priced bid.
- His scaled-measurement skepticism is even MORE true for steel than for his electrical/architectural example. He counts tagged fittings; structural tonnage is not a count, it is count x validated unit weight x length. We must never let the model take a scaled length off a frame (the "Page Not Scaled" warning at frame 78 is the lesson). Lengths come from the schedule, the dimension text, or a member takeoff - not vision.
- Gemini-in-Antigravity is his stack, not ours. The transferable idea is the agentic file-folder workflow and the vector-first method, not the specific tool. Our equivalent is Cowork + drawing-analyzer/project-indexer with Claude routing per model_routing.json; do not adopt Gemini as the counter, but his point that Gemini leads visual benchmarks is a data point for our multimodal-drawing fallback (which already routes drawing analysis to Gemini per CLAUDE.md).
- "Manual counting doesn't take long, AI saves little time" is true for a small residential electrical set. It does not transfer to a large multi-building steel job where the count-gap (members present on plans but missing from schedules, or vice versa) is the actual error source. Our value is not raw speed; it is catching the discrepancy between schedule QTY and plan-mark count that a human flying through would miss. That is the part his video does not address and where our branch adds something he doesn't.

Net: his vector-first-with-confidence-and-sign-off method is strong external validation for the count-gap branch's core design. Adopt the method-linked confidence tiers, the schedule-vs-plan reconciliation framing, and the explicit per-item assumption string. Reject his ROM-as-deliverable framing and any scaled measurement by vision for tonnage.

## Caveats

- Frame sparsity: 80 frames over 15:54 = one frame every ~12s; the watch tool itself warns accuracy degrades over 10 minutes. Fast UI actions (individual count clicks, exact prompt text typed) between frames are inferred from the transcript, not directly seen.
- Frames are 512px wide. The ClockBench leaderboard percentages and the Excel cell text were read from low-res frames; the second-decimal digits (e.g. Claude Opus 4.6 "8.0%", Qwen "26.4%") are approximate. The headline numbers stated aloud (90.7%, ~50%, 32.2%, <10%, "46 items") are from the transcript and reliable.
- The `qto-workflow.md` principles and the Excel columns were legible enough to quote in substance; minor wording may differ by a word. No frame was fully unreadable.
- Model version names (GPT 5.4, Gemini 3.1 Pro, Claude Opus 4.6) are as the video presents them on a benchmark site and are not validated against any release we track.
