# How to Build an AI Quantity Take-Off Tool - Step-by-Step (IqfrXoiM4bE)

- **URL:** https://www.youtube.com/watch?v=IqfrXoiM4bE
- **Uploader:** Tim Fairley (ConstructIQ / "Contractor OS" community)
- **Duration:** 28:38 (1718.4s)
- **Frame count:** 80 frames @ 0.047 fps (512px wide), sparse coverage
- **Transcript source:** captions (793 segments), good quality with minor caption typos

**Thesis (one sentence):** Fairley builds a reusable Claude "skill" that runs a Python (PyMuPDF/`fitz`) script to extract the PDF vector-data layer (text, coordinates, line lengths, shapes) and then has Claude combine that structured data with the drawing image, so the AI counts and measures from exact vector data rather than from pixels, which he positions strictly as a check-your-work / budget-ROM tool, never the system-of-record takeoff on a real-money estimate.

---

## Chronological walkthrough (with t=MM:SS anchors)

- **t=00:00-00:45 (frame 1):** Intro. Quantity takeoffs follow a well-defined process with clear input/output, so they suit AI/automation, but the limitation is "how well AI processes image data." Pitch: build your own takeoff tool using "the Claude large language model and the Claude skills feature." Workflow preview: upload a drawing to a Claude project, give the instruction, tell it to run the skill.
- **t=00:48-01:09:** Why a skill beats raw LLM use. PDF drawings have two layers: the visible image and "a structured layer of data." The skill extracts that data layer using a Python script that "you can set up just by prompting." Claude builds a repeatable skill that extracts key quantities, tags, etc.
- **t=01:24-02:05:** Promises to show both how to build the skill and the "nerdy" PDF-internals theory. Nuances flagged: break drawings up and upload individually; structure the prompt so the model prioritizes the right data and focuses on primary big quantities rather than detailed reinforcement.
- **t=02:07-04:07 (frame 7 shows ChatGPT input bar):** The big qualification. Every LLM shows "AI isn't 100% reliable, check your answers" because models hallucinate. "If I was preparing an estimate for a $1M, $5M, $10M project, I would not be relying on an AI quantity takeoff tool." Better alternatives: (1) takeoffs are an intricate part of estimating, the AI tells you how many light fittings but not which need a ladder or an EWP; (2) hire quantity surveyors on Upwork in lower-wage countries, "more reliably for almost the same price"; (3) ask the designer to export quantities from Revit/BIM directly. "Missed quantities mean missed dollars." Good use case = first-cut understanding plus end-of-estimate check.
- **t=04:18-04:50 (frames 13-14):** Results of his pile test. Live takeoff in Claude shows BP1 = 30 piles, BP2 = 7 (he counted manually, both correct). On-screen "Pile takeoff" CSV: Mark BP1 "Bored Pier Type 1" Count 30 Diameter 1200mm Depth 9500mm; BP2 "Bored Pier Type 2" Count 7 Diameter 900mm Depth 9500mm; plus LP1 "Light Pole Pier." Claude's reasoning chain references finding a "Bored Pier Schedule" as the authoritative source and cross-referencing it. Worked because it extracted tags/symbols and compared with the image for layout context, not pure image processing.
- **t=04:51-08:14 (frames 15-24):** PDF internals explainer doc. Two layers: visual (screenshot-equivalent) and vector (coordinates, text positions, line lengths). Vector layer is why you can highlight text in Bluebeam. Format = "PDF reference," a database of objects: text operators (begin/end text), fonts, per-item coordinates, lines (from-point to-point), shapes (circle/rectangle with center + dimensions). Key operators shown on screen: BT/ET (begin/end text block), Tj (show text string), Td (move text position), Tm, m (move to point), l (line to point), re (rectangle), c (curve/Bezier). Darts-room example: a "7'-8"" text box decodes to BT, font size, Td move-to coordinate, Tj draw-text, ET. Python libraries read these operators and reconstruct the data as JSON (text + coordinates + font; lines with start/end/length; rectangles with coordinates + height/width + area). "Why PDF Data Matters": designers build in AutoCAD/Revit 3D models where every light fitting/outlet is a real object; the PDF drawing is an abstraction but all that source data still lives in the PDF. Extract it and you stop relying on AI vision (weak) and use AI's strength on structured data.
- **t=08:14-09:12 (frames 26-27):** The "clock benchmark" (clockbench.ai) leaderboard shown. Reading analog clocks is trivial for humans (baseline cited ~90.7% in narration; on-screen "Human Baseline" row ~38.4% in the visible column) but the best AI model ~39.4% accurate; congested clocks degrade further. Visible leaderboard rows: Human Baseline top, then GPT-5 (Chat) ~32.9% (OpenAI), Gemini 2.5 Pro ~28.8% (Google), and Claude Opus 4.1 far lower (~4-5%, Anthropic). Point: AI is weak at dense visual reasoning.
- **t=09:39-12:51 (frames 28-36):** "How AI Processes Images" explainer. Image is chopped into patches (a ~2000x500px image into a ~16x6 grid); each patch becomes a number (vector embedding); the model relates patches to your question via an attention mechanism; a slab rectangle may span 6-7 patches, so patches must relate to each other; more context grows complexity exponentially ("context rot") and raises hallucination risk. The "Willow Room" floor-plan illustration shows the L1/L2/L3 count failure: "What you want: count L1, L2, L3 = 47 / What the model does: approximately, around 50-60."
- **t=12:51-14:36 (frames 36-41):** "AI Image Processing - What it's Good/Bad at." GOOD AT: pattern recognition across whole image; symbol identification; spatial understanding ("is there a light fitting in the kitchen"); contextual reasoning; anomaly/error detection (unusual symbol). BAD AT: precise counting (a drawing with 47 GPO symbols would almost certainly be wrong, model says "approximately 45-50"); exact measurements (room "appears to be approximately 6m by 4m" vs actually 6.247m x 4.057m); small/dense/overlapping/congested text and symbols; distinguishing similar symbols; counting in cluttered areas.
- **t=14:36-15:36 (frames 42-44):** The three-query pile experiment in Bluebeam. Drawing with ~30 piles, manually counted 30. Image-only upload to the AI gave 27. PDF with vector data extracted via the skill's Python script gave the correct 30. On-screen panel: "Test image vs PDF: 30 x BP1 Piles / Actual: 30 / Image only: 27 piles / PDF with Python: 30 x BP1 Piles." A "BP1" tag is three text characters the model can extract reliably; it can see the legend instance and exclude it.
- **t=15:36-17:42 (frames 45-49):** "The Combined Approach" table and the four-step pipeline (captured below). Plus guidance: only extract quantities with explicit measurements; use vision for context; focus on primary quantities. Reinforcement shop drawings will give unreliable results because the reasoning is hard to replicate; but piles, slab dimensions, formwork areas work, and you can apply a conversion library (e.g., reinforcement ratio per cubic meter of concrete).
- **t=17:42-21:07 (frames 50-59):** How to build the skill in Claude. Settings > Capabilities shows Anthropic example skills: doc-coauthoring, internal-comms, mcp-builder, skill-creator, slack-gif-creator, theme-factory. His own skill is `construction-takeoff` with `SKILL.md`, `references/` (incl. `tags_and_symbols.md`), and `scripts/` (`extract.py`, `takeoff.py`). He cannot code Python; he just told Claude what he wanted it to do. Origin: he asked Claude whether you can run Python inside Claude, it said make a skill, then offered to create one; his request (frame 58): "yes, can you please create a generic script that extracts quantities for construction drawings, some drawings I will be counting tags ie light fitting L1, some drawings I will be measuring volumes ie concrete space, so it needs to be generic." Claude read the skill-creator guide and built it; then "Copy to your skills" (frame 59) installs it. He validated it by uploading drawings with known quantities and checking. A skill = a reusable set of instructions so the model does the least reasoning at call time (just call the skill).
- **t=21:07-24:42 (frames 60-71):** Live run on a real set. Drawings were ~7-8MB; uploading the whole set fails with an upload/network error and raises hallucination risk, so he compressed (7MB -> 5MB) and split into architectural / electrical / mechanical. The Claude Project "Quantity Take-off Tool" has a description, a Memory note, and custom Instructions (captured below). He types the full electrical-works prompt (captured below), turns on extended thinking, and runs it; takes ~2-3 minutes and "a lot of tokens" (recommends the tier above Pro, "like 160 bucks a month").
- **t=24:42-27:34 (frames 72-79):** Output. A "Century House" electrical takeoff. Primary equipment pulled straight from the Mechanical Equipment Schedule on Drawing E-0 (condensing units, air handling units, heat recovery ventilators, evaporator units, exhaust fan, force flow heaters, GFCI receptacles, main disconnect switches; Total Primary Equipment = 30). Secondary/derived quantities (disconnect switches, circuit breakers, raceway, TECK cable, feeder cables) inferred with stated derivation basis. Output written to a multi-tab Excel/`.XLSX` with primary, secondary, and derived quantities as separate tabs plus a Notes tab documenting sources and assumptions. He cautions he did NOT manually verify this set, "assuming it's correct."
- **t=27:34-28:38 (frame 80 blurred outro):** Closing. Works for electrical (tags/symbols) and concrete/structures (area measurement); does NOT work for detailed reinforcement takeoffs or for image-only PDFs with no vector layer. Repeats that relying on an AI takeoff to "save X hours" is the wrong frame; the value is understanding drawings, fast budget pricing (20-30% accurate), and checking your own work. Piles are ~$15-20k each installed, so saving a few minutes counting is not worth the hallucination risk. Plugs a fuller "AI in construction" course.

---

## On-screen tools and Claude skills (names EXACTLY as shown)

| Item | Type | Where shown |
|---|---|---|
| `construction-takeoff` | His custom Claude skill | frames 2, 53-57 (Settings > Capabilities / Memory) |
| `SKILL.md` | Skill instruction file inside the skill | frames 2, 53-57 |
| `references/` (folder) | Supporting docs folder | frames 2, 53 |
| `tags_and_symbols.md` | Reference file (tag legend) inside references/ | frames 2, 54 |
| `scripts/` (folder) | Python code folder | frames 2, 53 |
| `extract.py` | Vector-extraction Python script | frames 2, 53 |
| `takeoff.py` | CSV/Excel output + merge utility script | frames 2, 56-57 |
| `skill-creator` | Anthropic example skill (used to build the skill) | frame 52, 58 |
| `doc-coauthoring` | Anthropic example skill (listed) | frame 52 |
| `internal-comms` | Anthropic example skill (listed) | frame 52 |
| `mcp-builder` | Anthropic example skill (listed) | frame 52 |
| `slack-gif-creator` | Anthropic example skill (listed) | frame 52 |
| `theme-factory` | Anthropic example skill (listed) | frame 52 |
| "Quantity Take-off Tool" | His Claude Project (with Memory + Instructions) | frames 61-69 |
| PyMuPDF / `import fitz` | Python PDF library used by extract.py | frame 53 |
| Bluebeam | Manual-count PDF reader (ground truth) | frames 42-43 (also narration) |
| clockbench.ai | "Clock benchmark" leaderboard | frames 26-27 |
| Claude model "Opus 4.5" / "Opus 4.x" | Model selector in the chat UI | frames 3, 58-72 |
| ChatGPT | Shown only for the "AI isn't 100% reliable" disclaimer point | frame 7 |
| Excel `.XLSX` | Final multi-tab output format | frames 72-79 |

Note: the chat UI model picker reads "Opus 4.5" / "Opus 4.x" in several frames; caption text never names a model. Treat the exact model string as low confidence (small UI text).

---

## The workflow, step by step (reproducible how-to)

The on-screen four-step pipeline (frames 45-49):

1. **Upload PDF** (single discipline, compressed, split out of the full set).
2. **Extract vector data (Python script):** all text with coordinates; all lines with lengths; all shapes with dimensions; detected scale factor; pre-counted tags.
3. **Combine in Claude prompt:** JSON extraction data (primary source) + drawing image (interpretation layer).
4. **AI analyses both together:** uses extracted counts as truth; uses vision to identify unlabeled symbols; uses vision to verify and add context.

Build-the-skill procedure:
- Go to Claude Settings > Capabilities > skills.
- Use the `skill-creator` skill: ask Claude to create a generic script that extracts quantities from construction drawings (counts tags on some, measures volumes/areas on others; must be generic).
- Let Claude write `extract.py` (PyMuPDF/`fitz`) and `takeoff.py` (CSV/Excel I/O + merge), plus `SKILL.md` and `references/tags_and_symbols.md`.
- "Copy to your skills" to install. Optionally download the `.skill` file / `construction-takeoff` folder and place it in your skills directory.
- Validate against drawings with known quantities before trusting new work.

Run procedure:
- Put it in a Claude Project with an Instructions block making the model an "expert construction quantity take-off specialist" that always uses the skill.
- Compress and split the set by discipline (architectural / electrical / mechanical) to avoid upload failures and context rot.
- Prompt it to use the skill, prefer explicit schedules over counting, prefer explicit dimensions over scaling, and infer secondary from primary quantities.
- Turn on extended thinking. Expect 2-3 min and heavy token use.
- Output to a multi-tab Excel with primary, secondary/derived, and a notes/sources tab.

---

## What works / what does NOT (where he trusts AI vs refuses it, and why)

He refuses to trust AI for:
- The system-of-record takeoff on any real-money estimate ($1M-$10M). Explicit. Hallucination + missed-quantity-equals-missed-dollars risk.
- Detailed reinforcement (rebar) takeoffs - too much human reasoning to replicate.
- Image-only PDFs with no vector text layer - the method simply cannot work.
- Precise counting from pixels; exact measurement by scaling off the drawing; dense/congested/overlapping symbols; distinguishing similar symbols.

He trusts AI (with verification) for:
- Counting text-tagged items (BP1, L1, GPO) via vector extraction - exact.
- Reading explicit schedules/legends (the authoritative source) and pulling counts from them.
- Using explicit listed dimensions/lengths (e.g., a conduit run that states its length).
- Vision for context: which room a fitting is in, excluding the legend instance, identifying unlabeled symbols, spotting anomalies/errors.
- First-cut drawing comprehension and fast 20-30% budget pricing.
- A second-set-of-eyes check at the end of a human estimate.

The reasoning is the "combined approach" division of labor: vector extraction is exact but context-blind; AI vision is context-rich but imprecise. Use each only for its strength.

---

## Concrete numbers, rates, file names, examples shown

- **Pile test:** 30 piles actual (BP1), image-only = 27, PDF + Python = 30. BP2 = 7. (frames 13-14, 42-44; t=04:24, 14:44.)
- **Pile schedule data:** BP1 Bored Pier Type 1, dia 1200mm, depth 9500mm; BP2 Bored Pier Type 2, dia 900mm, depth 9500mm. (frame 14.)
- **Clock benchmark:** human ~90.7% (narration) / ~38.4% on visible leaderboard column; best AI ~39.4%; GPT-5 Chat ~32.9%; Gemini 2.5 Pro ~28.8%; Claude Opus 4.1 ~4-5%. (frames 26-27, t=08:57.)
- **GPO example:** 47 GPO symbols -> model says "approximately 45-50." (frame 37, t=13:36.)
- **Measurement example:** room reported "approximately 6m by 4m," actually 6.247m x 4.057m. (frame 40, t=13:58.)
- **Cable inference rule of thumb:** "if you count 10 light fittings... each light fitting will need 8 m of cable." (t=24:28, frame 69.)
- **File sizes:** full set ~7MB (one mention 8MB); compressed to 5MB; Explorer shows Drawings-Architecture-Compressed 1,420KB, Drawings-Electrical-Compressed 1,957KB, Drawings-Mechanical-Compressed 1,957KB, Drawings (Arch_Elec_Mech) 7,747KB. (frame 64, t=22:33.) ~7MB estimated as ~100,000 tokens (his rough guess).
- **Cost:** the tier above Pro "like 160 bucks a month"; run took 2-3 minutes and "a lot of tokens." (t=24:55.)
- **Output project:** "Century House" electrical takeoff, project no 39028, issued 25 Mar 2019; Total Primary Equipment = 30 (Condensing Units 5, AHU 1, Heat Recovery Ventilators 3, Evaporator Units 11, Exhaust Fans 1, Force Flow Heaters 1, GFCI Receptacles 2, Main Disconnect Switches 1). (frames 72-79.)
- **`extract.py` internals (frame 53):** `import fitz`; `except ImportError: print("ERROR: PyMuPDF required. Install with: pip install pymupdf")`; a `TAG_PATTERNS` dict of regex -> (description, discipline), e.g. light fitting `L\d+`, LED downlight, fluorescent `F\d+`, pendant, general power outlet `GPO\d+`, double power outlet, distribution board `DB\d+`, switch, exit light, smoke detector `SD\d+`. (Exact regex strings are partly low confidence; small text.)
- **`tags_and_symbols.md` (frame 54):** plumbing legend table - WC water closet/toilet (EA), WHB wall hung basin, VB vanity basin, SHR shower, SK sink, FL/FD floor drain, FW floor waste, HW/HWS hot water system, TAP tap/faucet, BIB bib tap, PRV pressure reducing valve, TMV thermostatic mixing valve.
- **`SKILL.md` data-source table (frame 55):** Tag counts -> Text extraction / Vision check for missed items; Dimensions -> Extracted text / Vision confirms placement; Scale -> Title block text / Dimension-to-line matching; Room areas -> Vector rectangles / Vision verifies; Linear runs -> Vector polylines / Vision traces cable routes; Symbol types -> Vision recognition / Legend cross-reference. Output command: `python /mnt/skills/user/construction-takeoff/scripts/takeoff.py`.
- **`takeoff.py` usage header (frame 57):** "Construction Takeoff Output Utilities. Handles CSV/Excel output and merging of takeoff results." Commands: `python takeoff.py template output.csv` (blank template), `python takeoff.py merge file1.csv file2.csv -o combined.csv`, `python takeoff.py from-json extracted.json -o takeoff.csv`. Functions seen: `create_template`, `merge_takeoff`.
- **Combined-approach table (frames 45-46):** Counting text tags (L1, GPO) Vector=Exact / AI=Estimates; Counting symbols without text Vector=Can't identify / AI=Recognises; Precise measurements Vector=Exact coordinates / AI=Guesses; Understanding context Vector=Just data / AI=Interprets; Reading legends Vector=Just text / AI=Understands meaning; Scale detection Vector=From title block / AI=Can verify.
- **Project Instructions (frames 61-69):** "You are an expert construction quantity take-off specialist. Always use the Claude skill to extract vector data from drawings..." (text partly truncated on screen). Memory note: "Tim is working in construction quantity surveying and estimating, focusing on developing AI-powered tools..."
- **Full electrical prompt (assembled from frames 65-69):** "Using the construction quantity take-off skill, perform a quantity takeoff of the electrical works. Use the PDF vector data for detailed analysis, use the image of the PDF to understand context. Focus on extracting known quantities that you can clearly see in the drawings, use any explicit schedules rather than counting where available. For example if there is a schedule with light fitting quantities, use that rather than counting the fittings. Focus on explicit dimensions rather than scales. For example if a conduit run lists the length, use that length rather than trying to measure from the scale. Infer secondary quantities from the primary quantities. For example if you count 10 light fittings, then you can infer [each needs 8m of cable]."

---

## Applicability to a structural steel fabricator (Your Company)

**What transfers well:**

- **The two-layer insight matches our `drawing-analyzer` skill exactly.** Fairley's whole thesis ("extract the PDF vector text layer with PyMuPDF, count from text not pixels") is precisely what our `drawing-analyzer` already does (split per sheet, render high-res image, extract the PDF vector-data text layer, count tagged items from text, never measure scaled quantities from the image). This video is independent third-party validation of our existing architecture and the "approximate, not accurate" disclaimer in our skill description. We are already on the right path; he is one external data point that the vector-extraction approach is the correct one.
- **Schedule-first, count-second is directly our doctrine.** "Use explicit schedules rather than counting where available" maps onto our Engine A1 schedule-QTY reader (the count-gap branch, feature/count-gap-sf-a1) and onto CLAUDE.md's "measured member takeoff (schedules plus framing-plan marks)" standard. His electrical run pulled primary equipment straight from the Drawing E-0 equipment schedule; for steel, the analogous authoritative sources are the column schedule, beam schedule, and member marks - read those, do not pixel-count.
- **Tag-counting is exact for marked members.** For structural steel, member marks (e.g., C1, B12, J-series joist marks) are text tags. Counting tag occurrences from vector text is the reliable operation, same as his BP1=30 pile count. This is the count-gap engine's core premise.
- **The primary-then-secondary inference pattern maps to tonnage build-up.** His "count primary, infer secondary via a ratio library" (concrete -> reinforcement per m3; light fittings -> 8m cable each) is structurally identical to: count/measure members -> get weight per member from `aisc_validator.py` -> roll up tonnage -> apply fab/erection rates. We must keep the AISC-weight step in our validator, never an LLM ratio, but the inference architecture is the same shape.
- **The "check, don't generate" stance is identical to our governance.** His core rule ("never the system-of-record number on a real estimate; use it as a second set of eyes and for ROM budget pricing") is verbatim our "verify, do not generate" Operating Rule and our SF/accuracy ROM-vs-bid-grade distinction. He independently arrived at our governance posture.
- **Split-by-discipline and compress to beat context rot** transfers to our pipeline: index/process structural, then misc/secondary steel separately rather than dumping a full multi-discipline set into one context. Reinforces our `project-indexer` per-project approach.
- **Skill packaging.** His `construction-takeoff` skill (SKILL.md + scripts/ + references/tags_and_symbols.md) is the same shape as our skills directory. A `references/tags_and_symbols.md` analog for steel (a marks/section legend: W/HSS/L/C/PL/joist/girt/purlin abbreviations) could improve our drawing-analyzer's tag recognition.

**What does NOT transfer / cautions:**

- **He explicitly excludes reinforcement takeoffs** because the reasoning is too complex; the closest structural-steel analog is **connection and detailing takeoff** (bolt counts, weld lengths, gusset/stiffener/baseplate plate work, misc/secondary steel from details). Expect the same unreliability there - those need a human or a measured detail takeoff, never an AI count. Treat AI counts on detail sheets as low confidence.
- **His tool tops out at ROM (20-30%) accuracy.** That is below our bid-grade bar. For Your Company this method is a screening/QC layer feeding the SF-confirmation and completeness gates, not a replacement for the member takeoff through `aisc_validator.py`.
- **AISC weights and BID_RATES stay locked.** Nothing in his approach (he uses LLM ratios and "typical building runs" allowances) should leak into our weight or rate path. Tier 1 / Hard Rules 5 and 6 hold. His secondary-quantity allowances are explicitly "estimates based on typical building runs" - not acceptable as our priced numbers.
- **Image-only / scanned PDFs are dead ends** for this method - same limitation our drawing-analyzer faces; gate for the vector text layer first.
- **He generates Excel as the deliverable.** Our deliverable path is the locked two-PDF bid format with governance gates; an Excel QC worksheet is fine internally but is not a client artifact.

**Concrete reuse ideas:**
- Extend our count-gap A1 reader with his explicit "schedule beats counting / explicit dimension beats scaling" prompt clauses; they are clean, copyable instruction text.
- Add a steel `tags_and_symbols.md` reference (member-mark and section legend) to the drawing-analyzer skill.
- Borrow his `takeoff.py` merge/template/from-json CSV utilities pattern for assembling per-sheet counts into one combined takeoff CSV before it goes through our validator.
- Adopt his confidence framing (primary = extracted/exact, secondary = derived/assumed, with a Notes tab documenting source per line) - it aligns with our high/medium/low confidence tagging and our "be explicit about data source" rule.

---

## Caveats

- **Frame sparsity:** 80 frames over 28:38 = one frame every ~21s. Multi-step UI animations (e.g., the skill's live reasoning chain, the Excel tab-switching) are sampled, not fully captured. Several code/prompt frames are mid-scroll, so a few lines are cut off.
- **Small-text reads are partly inferred:** the `extract.py` `TAG_PATTERNS` regex strings, the exact `SKILL.md`/`takeoff.py` wording, and the chat model string ("Opus 4.5"/"Opus 4.x") are read from small UI text and should be treated as medium-to-low confidence. The four-step pipeline, the combined-approach table, the tags legend, and the assembled electrical prompt are high confidence (clearly legible across multiple frames).
- **Caption typos:** the transcript is auto-captions ("Jibbt" = ChatGPT, "clog skill" = Claude skill, "condute" = conduit, "GPO"/"EWP" correct). Numbers were cross-checked against frames where possible.
- **Clock-benchmark percentages:** narration says human 90.7% / best AI 39.4%; the on-screen leaderboard's visible accuracy column shows lower figures (human row ~38.4%), likely a different/secondary column. Reported both; do not over-rely on the exact percentages.
- No supplier names, rates, or material costs appear in the video; nothing here conflicts with Tier 1 brand rules.
