# How to Get Claude to Read Construction Drawings (ItW-ielFvGg)

- **URL:** https://youtu.be/ItW-ielFvGg
- **Uploader:** Tim Fairley (ConstructIQ / "Contractor OS" community)
- **Duration:** 18:55 (1134.7s)
- **Frames analyzed:** 300 (three 1024px windows of 100 frames each, ~3.8s spacing; dense coverage, three parallel reader agents)
- **Transcript source:** captions (538 segments, complete and reliable)
- **Watched:** 2026-07-02 (via /watch)
- **Relationship to the existing KB:** direct follow-up and next iteration of `research/constructiq-watch/_k1jQBS4Nk8.md` ("Claude Code + Construction Drawings"). Same presenter, same warehouse example (Spencer Group Engineering, "Proposed Warehouse," Yatala QLD), same footing marks, same `drawings-analyser` skill. What is NEW here: (1) an object-keyed normalized SQLite database that groups by physical object instead of by sheet, with a per-discipline entity schema; (2) a Karpathy-style LLM concept-wiki for the notes/specs layer, with a standing conflict/RFI register; (3) a `validate_provenance.py` self-check step; and (4) a blind-judged accuracy + token benchmark across three methods. Note the surface also moved from Claude Code (prior video) to Claude Cowork here. Belongs in the ConstructIQ channel KB (`research/constructiq-watch/`); a `docs/CONSTRUCTIQ-KB.md` is referenced in CLAUDE.md but does not yet exist.

## Thesis

Construction-drawing PDFs are "quite possibly the worst possible input for AI": dense, symbol-heavy, huge, with meaning that lives in tiny features (a dashed line vs a thick line) and in cross-references across sheets (tag F6 on one page resolves only at the section view on another). Feeding raw drawings to an LLM burns tokens and returns inaccurate results because precise visual extraction is exactly where AI fails (his shorthand: the ClockBench analog-clock benchmark). The fix is a one-time indexing pass that reverse-engineers the drawings into a queryable structured database plus a concept wiki, the same shape a BIM model already has behind its geometry, packaged as a reusable Claude "drawings-analyser" skill. After the pass, every later query reads cheap structured text and drops back to the source PDF page only when it must. He reports the approach is roughly 50x fewer tokens per question and lifts accuracy to 100% on his own blind-judged test set, and stresses it composes into every downstream drawing workflow (RFIs, quantity takeoffs, error-checking).

## The architecture (the novel core of this video)

Two complementary layers sit under a `drawings.md` map file. The skill's own description on screen: "Turn a construction drawing set (PDF or folder of PDFs) into a queryable structured database plus per-sheet markdowns, a symbol library, a cross-reference graph, and a concept wiki of the notes/specs. Builds the building's components as instances with coordinates (IFC-style), tags every fact with a reliability score, validates its own sources, and flags conflicts/RFIs."

**1. The structured layer - a normalized SQLite database (grouped by object, not by sheet).** Four table shapes, each row carrying a `source` sheet and a `reliability` value:
- `schedules` (the catalogue, one row per type - "what a type is, straight from the schedule table"). Example row: `F10 | pad | 3200 x 3200 x 1200 mm | S101 | HIGH`. 19 rows for this set (F1-F13, DF1, SF1, GB1 warehouse + OF1-OF3 office).
- `instances` (one row per physical object, with a grid coordinate - "how many and where"). Example: `F10 | footing | grid w14/wD | S101 | HIGH`. 103 placed footings across the set.
- `slabs` (areas; "size comes from geometry, not a tag"). Example: warehouse fibre slab N40 area approx 3,656 m2 tagged `area MEDIUM - scaled`; office raft 120 mm N32 tagged HIGH (thickness/grade from the schedule).
- `relationships` (networks, stored as from -> to edges). Example: `PF2 portal frame | spans | grids w6-w12 | S301 | HIGH`; `DF1 footing | placed under | door columns`.

The skill's `schema_guidance.md` defines universal tables always present: `sheets(sheet_id, title, drawing_type, scale, discipline, rev, source_type)`, `notes(topic, rule_value, source_sheet)` (one rule per row, verbatim value), `relationships(from_entity, relation, to_entity, source_sheet, confidence)` (connective facts stated in text), and `placeholders(entity_or_topic, what_is_missing, why, suggested_sheet)` (for facts that need vision: counts off plans, traced runs, raster sheets). Then one entity table per discipline, with the rule "keep EVERY listed item even if attributes are null" (entity-completeness). The Structural entity table is `footing_schedule, members(mark, category, section, span_or_location, source_sheet, confidence), slabs, grids, levels`. Plumbing, Electrical, and HVAC each have their own entity tables (fixtures/connections/waste_routing; boards/circuits/luminaires; equipment/connections).

**2. The prose / concept-wiki layer - the Karpathy LLM-Wiki.** The notes and specs from all sheets are regrouped by IDEA rather than by sheet, with `[[wikilinks]]`, a source-sheet citation on every fact, and a standing conflict/RFI register. On-screen title: "The concept wiki - the notes/requirements layer (Karpathy's LLM-wiki idea)." Three operations: Ingest / Query / Lint. Pages for this set: Structural - `concrete-grades, reinforcement-and-mesh, cover-and-durability, slabs, footings, joints, subgrade-and-pavement`; Services - `systems, materials, fixings-and-supports, testing-and-commissioning, fire-rating, penetrations, controls`; plus `index.md` which carries a first-class conflicts/RFI register. Standing rule on screen: "Don't invent; cite every fact's source sheet; use [[wikilinks]]. The conflict/lint register is an output, not a side-note."

**3. `drawings.md` - the map / register.** Sits above both layers. A per-sheet index table (number, sheet, title, drawing_type, scale, rev, link) plus "the building in one paragraph" summary and query instructions. Claude is instructed to pull `drawings.md` first on every drawing task for overall context before touching anything else.

**Two data types in every PDF drawing.** A PDF holds (a) the visual representation and (b) a text/vector layer behind it. A footing tag "F6" is a text tag in the vector layer that can be referenced and counted directly. The skill embeds scripts that extract the vector layer, so the model works the visual and the vector data in parallel. Counting instances of a tag from the vector layer is reported as roughly 100% accurate; counting from a rendered image is not.

**Where accuracy breaks: scaled measurement.** Counting tags is reliable; measuring a length or area is not (extract scale, crop region, assume scale, measure - each step adds error). Mitigation is an order-of-magnitude sanity check against cross-referenced facts (a cable-tray run measured at 7 m against a 35 m building length is obviously wrong) and a reliability tag on every value: scaled area = MEDIUM ("hedged, not stated as fact"), counted quantity or schedule-stated value = HIGH.

## Chronological walkthrough (t=MM:SS anchors)

- **t=00:02** Opening claim: construction drawings are "quite possibly the worst possible input for AI." Dense, symbol-heavy, huge files, cross-references across sheets. Dashed vs thick line; tag F6 resolves only at the section view.
- **t=00:38** His workflow "reduces the amount of tokens you take to read PDF drawings by almost 50 times and drastically increases the accuracy," and composes into other workflows (RFIs, takeoffs, error-checking).
- **t=01:05** Demo prompt (on screen in Cowork): "How many foundations are there in the warehouse structural site?" Prepackaged skill linked in the description.
- **t=01:26** Core idea: we do NOT want AI to read drawings; extracting precise bits of images is where AI fails. Cites the clock benchmark (ClockBench).
- **t=01:56** Second problem: a typical PDF set ("I think it's 12 megabytes... a relatively standard set") with cross-references (footing on page 4, section on page 10).
- **t=03:04** Solution: an initial indexing pass that turns drawings into a structured relational database, keyed by OBJECT not page.
- **t=04:20** Text info (general notes, specs, schedules) handled differently: extract all text into a structured Wikipedia-style wiki, "based on the Andre Karpathy LLM Wiki approach."
- **t=05:01** `drawings.md`: register of all drawings + one-page summary; pulled in before reading drawings; includes query instructions. Concrete-spec queries route to the wiki; fall back to the source PDF only when needed (each page has an image + a text representation; only the needed page is pulled).
- **t=05:56** First run costs a lot of tokens, so it is packaged as a Claude skill: "run my drawing analyzer workflow on this set." (On screen: typing `/drawings-analyser` in Cowork.)
- **t=06:28** A skill embeds the concept database structure, the Python split script, the schema, and output-schema examples for different drawing types.
- **t=07:05** Origin: BIM models. AI does quantities from BIM accurately because a structured database (Revit/Autodesk) sits behind the geometry. He reverse-engineers that from PDFs.
- **t=08:07** Industry critique: redundant if people passed BIM models, but you always get drawings, never the BIM model. A 3D model of the warehouse exists somewhere and already holds every footing and all the structural steel; the workflow just restructures it out of the PDF.
- **t=09:37** Two data types per drawing: visual + text/vector layer. F6 is a text tag; the skill embeds scripts that extract the vector layer; visual and vector worked in parallel.
- **t=10:18** Quantity takeoff: pull vector data, write a script to count instances of the F6 tag. "Counting from PDF drawings which has vector data on them is 100% accurate."
- **t=10:47** Where you do NOT get 100%: measuring a length (cable tray) - extract scale, crop, assume, measure.
- **t=11:07** Built-in mitigation: overall dimensions/footprints + a sanity check after any measurement (cable tray vs building length), cross-reference check catches gross errors.
- **t=11:58** Reliability per measurement in the DB: scaled/area = MEDIUM; counted or schedule-stated (slab 200 mm) = HIGH.
- **t=12:28** Testing: he wrote his own Q&A set and had Claude test reliability across the three approaches (raw images, prose text, database).
- **t=13:05** ACCURACY chart on screen (see figures below): raw images 86%, prose notes 98%, database 96%->100%, over 44 questions.
- **t=13:57** TOKEN chart on screen ("probably craziest result"): 104,552 / 66,219 / 1,446 tokens per question; database 46-72x cheaper.
- **t=14:52** Structure recap: keep `drawings.md` (the map), split and process sheets individually, build the object-keyed DB (slab/footings/counted + reliability), text -> the Karpathy LLM Wiki (nested by concrete/electrical/QA).
- **t=16:24** Rules: indexing phase + query phase (progressive ingest, refer to DB, low-confidence -> check original, routed queries -> the specific wiki page), plus the sanity-checking process across drawings.
- **t=17:51** "One of the 40 different construction workflows in Contractor OS," added to weekly.
- **t=18:00** Roadmap: break drawings by trade with template databases (electrical/structural/mechanical); integrate sub-agents (Claude Haiku for cheap tasks, "Claude Opus 4.8 for example doing the visual interpretation"); benchmark models and harnesses ("Claude Cowork versus Claude Code").
- **t=18:45** CTA: everything goes into Contractor OS; unlimited one-on-one setup calls.

## Benchmark figures (read at HIGH legibility from on-screen charts; the CLAIMS are the presenter's own self-reported results, so LOW confidence for us until independently verified)

Governance note: these were legible on screen (so the transcription is reliable), but they are Tim's own results on his own test set and blind grader. Per "verify, do not generate," treat every number as an unverified claim. None may set a system-of-record value.

The test, verbatim from the on-screen "Test Results" page: a real 25-sheet warehouse structural set plus a plumbing set; three fresh AIs each given ONE version (raw images / prose notes / the database); a separate AI blind-graded every answer without knowing which system produced it; ground truth = the drawing's own text layer + a verified takeoff; 44 questions (28 + 16 harder ones, weighted to counts, connections, and traps with no answer); instance counts matched the human takeoff 14 of 14.

Accuracy (blind-judged):

| Method | Accuracy | Fabrications |
|---|---|---|
| Raw images (reads the picture like a person) | 86% | 3 made-up answers |
| Prose notes (drawings turned into structured text) | 98% | 0 made-up answers |
| The database (after the provenance check) | 96% -> 100% | 1 -> 0 made-up |

Caption: "Any structure approx 96-98%. Reading the picture: 86%, and it fabricated. The database's single miss was a wrong source sheet; the provenance check caught it -> 100%, zero made-up answers." (The captions had garbled these as "raster / split-to-markdown / skill"; the real on-screen labels are Raw images / Prose notes / The database.)

Token bill (measured on the 25-sheet set, tokens to answer ONE question):

| Method | Tokens / question |
|---|---|
| Read the images | 104,552 |
| Read the text | 66,219 |
| Query the database | 1,446 |

Session scaling (read once, query many): 1 question 46x cheaper, 5 questions 201x, 10 questions 348x. Plus roughly 10x fewer tool calls (about 16 vs 157 to work through the set). Headline: "the database is 46-72x cheaper, and it's read once, not every time." (Caption's rounded 104k / 66k / 1,400 are corrected to 104,552 / 66,219 / 1,446.)

Where reading the picture fell over (on-screen failure list, structural set): asked for the F10 footings, the image-reader "invented two F10s that aren't there"; asked total F10 concrete volume, it "made up 24.576 m3" off the invented footings; asked which grids PF2 spans, "wrong axis"; asked how many footings 600+ deep, "miscounted, missed the 28 DF1s." "Every fabrication came from the image-reader. The structured arms said 'I can't' instead of guessing."

## On-screen tools, skills, scripts, and files (names EXACTLY as shown)

| Item (verbatim) | Type | Where |
|---|---|---|
| Claude Cowork | Surface (desktop, folder projects; New task / Projects / Live artifacts / Scheduled / Dispatch (Beta) / Customize) | throughout |
| Opus 4.8 (High) | Model badge in the Cowork chat selector | throughout |
| `claude-opus-4-7` | Model field inside the `sheet_classification.json` example | W3 ~15:30 |
| `drawings-analyser` | The Cowork skill (Added by You, Last updated Jun 11 2026, Trigger: "Slash command + auto") | W1/W2/W3 |
| `/drawings-analyser` / `/anthropic-skills:drawings-analyser` | Slash-command invocation | W1 ~6:09, W2 ~6:43 |
| `SKILL.md` | Skill body | W2/W3 |
| `references/` -> `concept_wiki.md`, `drawing_types.md`, `eval_protocol.md`, `instance_model_template.md`, `output_schemas.md`, `schema_guidance.md` | Skill reference files | W2 ~6:31-7:59 |
| `scripts/` -> `build_db.py`, `build_sheet_index.py`, `crop_region.py`, `extract_and_split.py`, `extract_instances.py`, `process_drawing.py`, `query_drawing.py`, `validate_provenance.py` | Skill Python scripts | W2 ~10:08, W3 ~16:29 |
| `drawings.md` | Output map/register (sheet index + one-paragraph building summary) | W1/W2 ~5:08-11:58 |
| `sheet_index.json` | Output (built by `build_sheet_index.py`; "pure file I/O, no judgement"; `total_sheets`, `sheets[]`) | W2/W3 |
| `sheet_classification.json` | Output (AI classification: `sheet_id`, `title`, `discipline`, `drawing_type`, `confidence`, `justification`) | W3 ~15:00 |
| `drawings_split/structural/` | Per-sheet output triplets `*_sheet<N>.json` (vector text) + `.pdf` + `.png` | W1 ~5:38 |
| SQLite `db/` + `SCHEMA` | The structured database folder (glimpsed under the electrical example) | W2 ~12:10 |
| Bluebeam Revu | Third-party PDF viewer used to show the set | throughout |
| Obsidian vault "221. AI for construction drawings" | Where the example markdown (Database, Concept Wiki, drawings.md) is shown | W1/W2 |
| Chrome "Test Results.html" | The local HTML page with the accuracy + token charts | W3 ~12:55 |
| ContractorOS (Skool classroom) | The commercial workflow library (Project Indexer, Drawing Analyser, Quantity Takeoff, Estimating Suite, ...) | W3 ~17:51 |
| project-indexer, construction-takeoff | Sibling skills; drawings-analyser is explicitly "not for full-set takeoffs (use construction-takeoff) or project onboarding (use project-indexer)" | W2/W3 |
| Bid Doc Designer | Sibling skill (Cowork + Claude Code editions, Nano Banana / Gemini; produces an editable .docx) | W3 ~17:51 |

## The 8-step pipeline (from the Cowork Progress rail, verbatim)

1. Splitting and extracting sheets.
2. Classify every sheet (type + discipline).
3. Build symbol library.
4. Per-sheet analysis markdowns.
5. Instances + vision context notes.
6. Build structured DB + validate provenance.
7. Concept wiki + cross-refs + coordination.
8. Combined `drawings.md` index + final summary.

Query phase (later requests): read `drawings.md` first, query the DB/wiki progressively, drop to the specific source PDF page only when the DB is low-confidence or lacks detail. Every answer carries a confidence tag; any scaled measurement gets an order-of-magnitude sanity check.

## The "eight learnings" the skill is built on (from SKILL.md, "evidence, not assertion", measured across structural + plumbing + electrical sets, 80+ blind-judged questions)

1. **Structure beats images.** Never make the model count symbols; extract to structure, query that. "Vision is approx 40-55% on symbol counting; the vector text layer is approx 100% on text."
2. **Hybrid beats either alone.** Keep the prose layer AND the database.
3. **Validate provenance at build time.** The DB's one failure mode is silent extraction errors; `validate_provenance.py` relocates mis-sourced rows and took a test DB from 96.4% to 100%, zero hallucinations. "Always run it."
4. **Entity-completeness.** Aggregate counts over the entity table, never the relationship table, and store `count` as an explicit integer, never inline notation like "F10 x2" (that ambiguity caused a real miscount).
5. **The vector/raster fork decides feasibility.** Vector PDF with a real text layer extracts near-losslessly; a scanned or outlined-text sheet needs vision. `process_drawing.py` reports text density per sheet; for sheets with no text layer, "flag a placeholder, never fabricate."
6. **Schedule = catalogue; tags = instances. Capture both.** (Points 7-8 were only partially legible.)

A separate SKILL.md line: "Keep BOTH. They were A/B-validated against each other and against raw images: structure beats images on cost (approx 20x) and hallucination resistance; the prose layer is self-correcting and caught DB extraction errors; reliability + context notes lifted answer accuracy 9.5 -> 14/16 and calibration 9 -> 15/16 with zero added hallucination."

## The drawing set on screen (what it is)

A real Australian job used as the running example: Spencer Group Engineering, "PROPOSED WAREHOUSE," Lot 412 Arthur Dixon Court, Yatala QLD, watermarked "TENDER 9/5/18." A single-storey portal-frame structural-steel warehouse. The structural file in Bluebeam is `403183205-D-3-2-Structural-Dwgs-T2-25-No.pdf` (25 pages); a separate electrical set is `Electrical-Drawings` (42 pages). Sheet register (from `drawings.md`): S101/S102/S103 footing and slab plans, S201-S204 footing details, S301 Warehouse Roof Framing Plan, S401 Portal Frame Elevations, S402 Warehouse Wall Elevations, S501 Office Roof Framing Plans, S601 Office Elevations, S701-S724 structural/typical details, and S801 "Warehouse Steel Erection Sequence Plan." Structural-steel markers throughout: general-notes columns "STRUCTURAL STEELWORK NOTES" and "SHOP DRAWINGS"; portal frames PF1 (w2-w5), PF2 (w6-w12), PF3 (w13-w14); braced end walls w1/w15; Z/C purlins and girts; member schedules on S301/S501. Footings F1-F13, DF1, SF1 strip, GB1 ground beam, OF1-OF3 office; grids w1-w15 x wA-wD. Datum notes "FFL = 31.25 / TOP OF FOOTING R.L. = 30.95 U.N.O." Key on-screen honesty note in the building summary: "No overall dimensions are printed on any GA - all plan geometry rides on scale calibration (bay regularity at 1:250 is the check)," and "S103's raster underlay is not vector-queryable; its structural overlay (joint tags, notes) is."

Observed inconsistency worth flagging: one demo shows the skill finding "CIVIL STRUCTURAL ENGINEERS DRAWINGS.pdf (13 sheets)" while the Bluebeam file and the benchmark both say a 25-sheet structural set. The two are different PDFs in the same folder; the benchmark figures are stated against the 25-sheet set.

## What Tim trusts AI for vs refuses (on drawings)

- **Counts from the vector/text layer: trusts (calls it approx 100%).** Pull vector tags, write a script to count instances. Same "count from text, not pixels" principle our `drawing-analyzer` is built on.
- **Schedule-stated values: trusts (HIGH).** A value written on a schedule (slab 200 mm) is read, not inferred.
- **Scaled length/area measurement: distrusts (MEDIUM at best).** Only used with a cross-reference sanity check and a confidence tag; the on-screen slab area is explicitly hedged.
- **Raw-image vision counting: refuses as the method.** The whole design exists to avoid it; the failure list (invented F10s, made-up 24.576 m3, wrong PF2 axis, missed 28 DF1s) is the argument.
- **Deterministic Python for the cheap work.** Splitting, vector extraction, provenance validation, counting scripts. AI is reserved for judgement (classification, cross-reference, interpretation).

## Applicability to Your Company (structural steel fabricator)

This is squarely on-target and is strong external validation of our architecture, with concrete new patterns for the count-gap branch. Unusually, his running example is itself a portal-frame structural-steel warehouse with a footing schedule and an erection-sequence sheet, so the domain matches ours directly.

**Direct confirmations of our design:**
- **Count from the vector/text layer, never from pixels.** Identical to our `drawing-analyzer` (split merged PDF -> one file per sheet, render image, extract PDF vector-text, count tags from text). His measured "vision approx 40-55% on symbol counting; vector text approx 100%" is the reason our skill exists, now with a number attached to it.
- **Verify, do not generate + per-line confidence tiers.** His per-row `reliability` (scaled = MEDIUM, counted/schedule = HIGH) is our Operating Rule "Confidence tagging" almost verbatim, and "the structured arms said 'I can't' instead of guessing" is verify-don't-generate in the wild. His order-of-magnitude sanity check maps onto our `run_gates()` and the $/SF gate.
- **SF is controlling, source it, do not assume it.** His building summary flags "no overall dimensions printed on any GA, all plan geometry rides on scale calibration" and marks the scaled slab area MEDIUM. That is our SF/accuracy standard stated from the other side: a scaled area is a hedged, low/medium-confidence input, never a stated fact.
- **Pre-compute durable indexes once, query cheaply.** His `drawings.md` + SQLite DB + wiki is our `project-indexer` output that "cuts query token use roughly 20 to 40 times." His 1,446-token query figure (vs 66k-104k for the naive paths) is the payoff our indexer targets. He even ships a `project-indexer` skill with the same "20 to 40 times" claim, and keeps it distinct from the drawing analyzer, which mirrors our skill separation.
- **AI classifies, scripts never pattern-match.** His `sheet_classification.json` is produced by the model reading each sheet's PNG + vector JSON, returning `discipline`, `drawing_type`, `confidence`, `justification`. Same posture as our indexer and the prior video.

**New patterns worth evaluating for the count-gap branch:**
- **Object-keyed / mark-keyed store (group by physical object, not by sheet).** This is the genuinely new idea versus his earlier sheet-keyed indexes, and it maps cleanly onto our takeoff. His `members(mark, category, section, span_or_location, source_sheet, confidence)` and `footing_schedule` are a near-mirror of our canonical takeoff row in `bridge/takeoff_row.py` (Tag / Description / System / Qty / Unit / Drawing / Method / Confidence / Basis / Notes). His design argues for persisting that as a queryable object index, and his `schedules` (catalogue, one row per type) vs `instances` (one row per placed object with a grid coordinate) split is exactly the schedule-QTY-vs-plan-mark-count distinction our A1 reader and Engine B grid geometry already work with.
- **Count validated against the takeoff (14/14).** His "instance counts matched the human takeoff 14 of 14" is literally a count-reconciliation gate. Our reconciliation advisory gate (`reconcile_advisory()`) does the same shape of check; his framing ("count validated N/N against the takeoff") is a clean way to report it.
- **Provenance validation as a build-time gate.** `validate_provenance.py` relocates mis-sourced rows and is credited with 96.4% -> 100%. For us this is a cheap, high-value addition: after a takeoff, re-verify that every counted mark actually appears on the sheet it claims, and flag rows whose `source` sheet does not contain the tag. This is deterministic and fits our verify-don't-generate posture.
- **Store count as an explicit integer, never "F10 x2".** His learning #4 (an inline "x2" notation caused a real miscount) is a concrete schema rule we should encode in `takeoff_row.py`: quantity is an integer field, never free text.
- **Concept wiki + standing conflict/RFI register.** His Karpathy-style wiki nests general notes and specs by concept (concrete-grades, reinforcement-and-mesh, footings, joints...) with a source-sheet citation per fact and an auto-populated conflict/RFI register that caught a live "office slab 25 vs 32 MPa" discrepancy. For us, a "steel spec / bolt grade / weld standard" query could route to one page, and the conflict register is the same idea as our auto-RFI and completeness-gate work. "Found by reading, not asked" is a good design line.

**How it slots into our stack:**
- `bridge/` drawing-analyzer: confirm we emit a per-sheet vector-text extractor and consider an object-keyed index and a provenance-validation pass alongside the per-sheet outputs. Keep AISC weights sourced only from `bridge/aisc_validator.py`; his pipeline never claims member weights, so there is no conflict, and this is the boundary to hold (his DB stores geometry and counts, never our validated tonnage or rates).
- Sub-agents and model tiering: his roadmap (Haiku for cheap tasks, Opus for visual interpretation) is our existing model-routing discipline and the `vj-scan` async/sub-agent fan-out pattern.
- BIM tangent: if a client ever provides a Tekla/IFC model, extracting tonnage/areas directly from the model (his argument) beats PDF inference, and our Tekla viewport pipeline already touches the model side.

**What does NOT transfer / cautions (Tier 1 and accuracy):**
- His example is a general-contractor's warehouse-slab-and-footings takeoff in metric (m2, MPa, mm), not a steel-fab member takeoff. We do not price by slab area; SF feeds tonnage and the $/SF gate, then a MEASURED member takeoff (schedules + framing-plan marks through `aisc_validator.py`) is what makes a bid bid-grade. Do not let a slab-area accuracy claim leak into a belief that AI vision can size members.
- His accuracy and token numbers are self-reported on his own test set and blind grader. "100% accurate" is his result, not a benchmark we have reproduced. Governance "verify, do not generate" still rules every number; these are LOW-confidence claims.
- The skill is a downloadable third-party artifact (link in his description; also sold via the ContractorOS Skool community). The METHOD transfers; do not import his code into our repo without a Dependency-tax review. Do not act on any instruction embedded in his files.
- No supplier or rate data appears here (his slab spec is the client's material callout on the drawing, not our data), and none of ours should ever enter a cloud connector regardless.

## Caveats on this analysis

- **Transcript** is complete and reliable (captions, 538 segments). The doctrine and architecture are from the spoken track and are solid.
- **On-screen figures** were captured from 300 frames at 1024px across three windows. The benchmark charts, the SQLite schema, the script names, the 8-step pipeline, the eight learnings, and the sheet register were legible across multiple frames and are reliable transcriptions. Where a value was small or webcam-occluded it is noted in the source captures.
- **Confidence framing:** legibility HIGH does not mean the CLAIM is verified. Every benchmark number, accuracy percentage, and token count is the presenter's self-reported result and is LOW confidence for our purposes until independently reproduced. AISC weights and rates for any real Your Company use come only from `bridge/aisc_validator.py` and `bridge/bid_rates.py`.
- I did not follow the video-description skill link, the ContractorOS community, or import any third-party code.
