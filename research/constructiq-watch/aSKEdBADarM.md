# AI for Estimating - What Works, What Doesn't (aSKEdBADarM)

- **URL:** https://www.youtube.com/watch?v=aSKEdBADarM
- **Uploader:** Tim Fairley (ConstructIQ / "Contractor OS")
- **Duration:** 27:37 (1657.4s)
- **Frames:** 80 @ 0.048 fps (512px), full mode
- **Transcript source:** captions (730 segments)

**Thesis (one sentence):** Across a full pre-construction bid workflow, AI is a reformatting, drafting, and cross-checking tool only. It should NEVER generate the system-of-record price, quantities, rates, or productivity data, because those come from structured business data and dedicated takeoff software, and a polished AI estimate is almost impossible to properly review (automation bias) and very likely to under-quote.

---

## Chronological walkthrough (with t=MM:SS anchors)

- **t=00:00 - The five mistakes (frames 1-2).** Fairley opens by naming five mistakes people make using AI for estimating. On-screen cards: "1 Using AI Over Existing Tools" (frame 1), "2 Automation" (frame 2).
  - **Mistake 1 (t=00:06):** Using AI when better, long-established tools already exist. Example given: using AI to turn a bill of quantities into direct cost, when assembly-based quantity-takeoff tools do this "almost automatically, much more accurately."
  - **Mistake 2 (t=00:27):** Automation bias. When AI hands you a finished, polished, good-looking estimate, it is "almost impossible to properly check it." You scan it, miss the big mistakes, and tell yourself you reviewed it. He calls this a well-studied cognitive bias.
  - **Mistake 3 (t=00:59):** Ignoring AI's technical limits. Long, complex tasks without check-ins or decomposition raise hallucination risk. Specifically: using AI to read/analyze construction drawings and do quantity takeoffs, "when the visual reasoning capabilities of these models just is not there yet."
  - **Mistake 4 (t=01:24):** Using AI without a foundation of structured data. You must give it activity templates, labor/plant/cost/material databases, subcontractor quotes, productivity libraries. Then AI is a "reformatting tool" turning that data into an estimate. If AI invents the productivity and cost numbers itself, "you are going to end up with terrible results."
  - **Mistake 5 (t=01:59):** Applying AI before you have a defined process. "AI without a defined workflow to follow is just going to lead to randomness."
- **t=01:22 (frame 4) - METR chart.** He shows the metr.org "Models are succeeding at increasingly long tasks" success-probability-vs-human-time chart to support Mistake 3 (model capability ceiling on long tasks).
- **t=02:32 - The workflow matrix (frames 8-11, 67, 80).** He drives an Excel "Pre-Construction Workflow" matrix that is the spine of the whole video. Columns: **Task | Project Input | Business Data | Output | Human Role | AI Role.** Stages: Initial Offer Assessment, Bid Management, Estimate - Direct Costs, Estimate - Indirect Costs, Finalisation, Bid Submission, Negotiation.
- **t=03:46 - Claude project setup (frames 13-20).** He creates a Claude project named "Construction Estimate" with the line "I want your help preparing a winning submission for this construction tender." Uploads drawings, scope of works, and background business data (scope-summary templates, lessons-learned, cost databases, benchmark rates, historic projects, go/no-go template, standard contract terms, indirect-cost templates). Explains Claude project parts: centralized file library, Instructions (system prompt), Memory file (self-updating).
- **t=05:33 - Stage 1, Initial Offer Assessment.** Steps: review bid docs and understand scope, raise clarifications, risk/opportunity assessment, conceptual estimate + schedule, go/no-go.
  - **t=06:09 - Document triage rule.** With 50-100 docs, "most of the important information is going to be in three to five documents and a handful of drawings." Human reads those key docs in "excruciating detail." AI reads the rest and extracts useful requirements.
  - **t=06:40 - project.md (frames 13-20).** AI builds a `project.md` synopsis so it does not re-tokenize PDFs/Excel/Word every query. He adds to system instructions: "before looking up any information in the project documents, refer to project.md for a synopsis" and "ask any clarifying questions when you are unsure" (frame 16 dialog: "Break down large tasks and ask clarifying questions when needed").
  - **t=07:11 - Where AI does NOT belong.** "If you have a two-page scope of works and 10 drawings, I do not see a role for AI in something like this." Human understands scope; do not let AI just summarize.
- **t=11:00 - Conceptual estimate (frames 32, 35, 37, 38, 40).** New chat. Prompt: based on historic cost data and cost database, prepare a high-level order-of-magnitude conceptual estimate, give a range. The project is the "Century House Air Conditioning System Addition" (Owner: City of New Westminster; heat pumps, split-system condensing units, HRVs - frame 22). AI reads project.md then the benchmark library (frame 32/35: Work Item / Low / Mid / High $/unit / Unit / Notes-Basis; e.g. split system install $1,500/$3,800/$8,200 each; RTU replacement $8,000/$14,900/$22,000 each). Output (frame 37/38): a "CONCEPTUAL ESTIMATE - ORDER OF MAGNITUDE" with Direct Costs roughly $306,800 / $525,360 / $485,400 Low/Mid/High and a prose narrative landing ~$566k-$797k total; he says the project "should be anywhere from around 400 grand to 800 grand."
  - **t=12:34 - Self-criticism.** He notes the conceptual estimate was "way too much detail... should have been five to 10 lines max." But emphasizes AI "is not just coming up with its own data and rates" - it pulled his historic low/mid/high benchmark rates and restructured them.
- **t=13:54 - Go/no-go population (frames 43, 55).** New chat per task. AI populates the go/no-go template from the conceptual estimate + project.md. He calls this a low-risk "data transformation task" - and even if wrong, it is an internal form, not the price.
- **t=15:27 - Bid management (t=15:36-17:02).** Bid plan population (good for AI), project folder setup (NOT worth AI - just copy/paste a good folder), tracking correspondence via a project email address + a weekly Claude automation/connector that logs to a correspondence register (good for AI).
- **t=17:02 - Estimating (frames 53, 61, 63, 67, 73, 76, 78).**
  - **t=17:13 - Requirements register (frame 53).** New chat: "carefully analyse my bid documents... prepare a comprehensive list of all the requirements in the bid documents, drawings, that we must include in our construction estimate." Note: chat shows "Read the SKILL.md for PDF reading to properly extract drawing content" and "Copy files locally then read the Scope of Works." This register is the checklist used later for cross-check.
  - **t=18:43 - The core principle.** "The biggest risk with estimating... is that we underquote the job and stuff up. That is why you should be using AI as a tool to cross-check your work rather than as a tool to generate an estimate." Use AI as a risk-reduction tool, not an estimate generator.
  - **t=19:34 - Pricing schedule.** Human generates it (or client provides). AI only cross-checks against requirements register + project.md for anything missing.
  - **t=20:08 - Quantity takeoffs (frames 61, 63).** Two steps. AI can help with SETUP (recommend a list of items to count). "The physical counting you should do yourself." He shows a dedicated takeoff tool (ctakeoff.com) on an electrical drawing: B2 Light Fitting counted 21 ea, expanding via an ASSEMBLY into Light Fitting, Support Bracket, 2.5mm2 Electrical Cable, Electrician man-hours, Cable Tray quantities (frame 61). Frame 63 shows a concrete-footing assembly (Pad Footing -> Rebar labor, Rebar runs, SOG concrete, metal stake). He repeats: "There should be no AI in that... zero AI in this. There are tons of software tools that will do this for you."
  - **t=21:46 - Subcontractor quotes (good for AI).** AI is "a great tool at getting quotes from subcontractors": feed it the requirements register, template scopes of work, template trade structures, and have it generate the procurement package list and detailed trade scopes.
  - **t=22:53 - Direct-cost cross-check (good for AI).** After Excel build-up of self-perform + subcontract costs, get AI to sanity-check direct costs against benchmark low/medium/high per-unit rates from the cost database.
  - **t=23:35 - Indirect costs / schedule.** Indirect costs driven by project schedule. AI is good at estimating project duration from a historic project library - "probably going to be more accurate than... the man-hour method."
  - **t=24:31 - Markup/margin.** "Zero involvement of AI on that."
- **t=24:47 - Final cross-check, the payoff (frames 76, 78).** "The final step, which I think is a very good step for AI to lead, is the actual cross-checking of your estimate." Prompt (new chat): "I have finished my estimate... Can you please carefully check my construction estimate against my requirements register to flag if I am missing anything and there are any gaps, errors, or omissions. Please carefully check as I am worried about under-quoting." AI produces an "ESTIMATE RECONCILIATION REPORT" (frames 76/78): Total Requirements 132, Items Covered ~110, Coverage Rate ~75%, Critical Gaps flagged HIGH risk; it found 17 unpriced items including concrete pads (priced 3 but need 4, CU-5 at Maple Room missing ~$3,500), EF-1 exhaust ductwork, fire dampers at rated walls, firestop professional engineer, existing BMS examination, furred-out exterior walls, 5 control items. Arithmetic check returned "ALL CORRECT."
- **t=26:48 - Bid submission / negotiation (frame 80).** AI helps draft methodology document from templates and review the contract (he calls contract review "a fantastic use case" - comparing a requirements list to contract terms). Letter of offer and negotiation close the workflow. Human leads; AI assists.

---

## What WORKS vs what does NOT (his explicit verdicts - the centerpiece)

His unifying rule: **AI is for reformatting, drafting, and cross-checking. AI is NOT for generating the number that costs you money.** "Data transformation" tasks = low risk. "Come up with the number" tasks = high risk of under-quote.

| Estimating task | His AI verdict | Reasoning (his words / paraphrase) | t= |
|---|---|---|---|
| Quantity takeoff: reading drawings + counting items | **NO - do it yourself** | Visual reasoning of current models "just is not there yet"; dedicated takeoff software is more accurate. Physical counting is human. | 01:17, 20:25 |
| Turning a takeoff/BoQ into direct cost via assemblies (labor/plant/material build-up) | **NO AI - "zero AI in this"** | Assembly-based takeoff tools "do this almost automatically, much more accurately." Tons of cheap software exists. | 00:19, 21:46-22:15 |
| Generating productivity and unit-cost/rate data | **NO - never** | If AI invents rates/productivity "you are going to end up with terrible results." Must come from your structured databases. | 01:53 |
| Generating the actual estimate / the price | **NO - cross-check only** | Under-quoting is the biggest risk; chance AI "stuffs up and underquotes or prices way too high" is "incredibly high." | 18:43-19:24 |
| Pricing schedule creation | **NO (human generates), AI cross-checks** | You generate from scope or client provides; AI only checks for missing items. | 19:34 |
| Markup / margin application | **NO AI - "zero involvement"** | Business decision, not a data task. | 24:43 |
| Building the final estimate / risk+opportunity | **Mostly human, AI supports** | "Really this should be something you've come up with." | 24:31 |
| Project folder / template set-up | **NOT worth AI** | "If you have a good project folder, you can literally just copy and paste it." Not the end of the world to do manually. | 15:58 |
| Reviewing/checking a polished AI estimate | **Caution - automation bias** | A finished good-looking answer is "almost impossible to properly check"; you scan, miss the big errors. | 00:30-00:57 |
| Reading the KEY 3-5 bid documents | **NO - human, "excruciating detail"** | Human must know the controlling docs "like the back of your hand." | 06:21 |
| Small jobs (2-page scope, 10 drawings) | **NO role for AI at all** | At that size you should understand scope yourself; AI summary adds nothing. | 07:14 |
| --- | --- | --- | --- |
| Extracting requirements from the REST of the docs (50-100 docs) -> project.md synopsis | **YES** | Supplements the human; reduces re-tokenizing PDFs every query. | 06:31, 06:54 |
| Drafting clarification questions to client | **YES (as a check)** | You identify the key ones; AI checks for any others you missed. | 09:52 |
| First-draft risk & opportunity register | **YES (first cut)** | You describe your concerns; AI drafts the register. | 10:18 |
| Conceptual / order-of-magnitude estimate from YOUR historic data | **YES - "good use case"** | "Doesn't have to be accurate," ROM only; AI pulls your benchmark low/mid/high rates and restructures, not invents. | 11:24 |
| Populating go/no-go template | **YES - low risk** | Pure "data transformation task, very low risk of hallucination"; it is an internal form, errors do not hit the price. | 14:44 |
| Populating bid-plan template | **YES** | Just fills a template from background info. | 15:36 |
| Tracking correspondence / RFIs (weekly automation, connector) | **YES** | Generic/project email + a once-a-week Claude automation logs to a register. | 16:13 |
| Quantity-takeoff SETUP (recommend list of items to count) | **YES (setup only)** | Suggesting what to count is fine; the count is not. | 20:10 |
| Generating subcontractor procurement packages + trade scopes | **YES - "a great tool"** | Feed requirements register + template scopes; AI structures the packages. | 21:46 |
| Cross-checking direct costs vs benchmark low/med/high rates | **YES - "a good check"** | Sanity check, not generation. | 22:53 |
| Estimating project duration from historic project library | **YES - likely more accurate** | Better than man-hour method when you have a similar-project library; drives indirects. | 24:02 |
| FINAL cross-check of the estimate vs requirements register | **YES - "a very good step for AI to lead"** | The reconciliation that catches gaps/omissions before submission (found 17 unpriced items). | 24:47 |
| Methodology document drafting from templates | **YES** | Template-driven drafting. | 26:53 |
| Contract review (requirements list vs contract terms) | **YES - "a fantastic use case"** | Comparing two lists is exactly what AI is good at. | 27:00 |

---

## On-screen tools and Claude skills (names EXACTLY as shown)

| Item | What it is | Frame / t= |
|---|---|---|
| Claude project "Construction Estimate" | Claude.ai project with file library, Instructions, Memory; tabs Chat / Cowork / Code; "Start a task in Cowork" button | frames 13-20, t=03:46 |
| **Opus 4.6** | Model shown in the Claude composer model selector | frames 15, 20, 43, 53, 73, 78 |
| "Cowork" tab / "Start a task in Cowork" | Claude UI surface (named in the app top bar) | frames 13, 15, 18, 20 |
| Project Instructions dialog "Set project instructions" | Text shown: "Break down large tasks and ask clarifying questions when needed" | frame 16, t=08:55 |
| `project.md` | Markdown synopsis file the AI builds and refers to before reading raw docs | t=06:40-08:42 |
| Memory file | Self-updating Claude project memory | t=05:18 |
| `SKILL.md` (PDF reading) | Chat step: "Read the SKILL.md for PDF reading to properly extract drawing content" | frame 53, t=17:13 |
| "Copy files locally then read..." | A tool/command step shown in the chat trace | frames 40, 53 |
| Excel "Pre-Construction Workflow" matrix | Task / Project Input / Business Data / Output / Human Role / AI Role | frames 8-11, 67, 80 |
| Benchmark cost database (Century_House_Business_Data.xlsx) | Work Item / Low / Mid / High $-unit / Unit / Notes-Basis | frames 32, 35 |
| Conceptual estimate output (Century house conceptual estimate.xlsx) | "CONCEPTUAL ESTIMATE - ORDER OF MAGNITUDE", Division 23 line items | frames 37, 38, 40 |
| Estimate Reconciliation Report (Century house estimate reconciliation.xlsx) | Total Requirements / Items Covered / Coverage Rate / Critical Gaps / arithmetic check | frames 76, 78 |
| **ctakeoff.com** (Stack/"On-Screen Takeoff"-style) | Browser takeoff tool with Plans/Takeoff/Reports/Community; assemblies expand counts into labor/plant/material | frames 61, 63, t=20:50 |
| Bluebeam | Add-in tab visible in his Excel ribbon (BLUEBEAM) | frames 8-11, 73, 80 |
| METR long-task chart | metr.org "Models are succeeding at increasingly long tasks" | frame 4, t=01:22 |

Note: "ctakeoff.com" is the literal URL visible in frames 61/63. The phrase "On-Screen Takeoff" is not shown; do not attribute a specific vendor beyond the visible URL.

---

## Concrete numbers, accuracy claims, rates, examples shown

- **Example project:** "Century House Air Conditioning System Addition," Owner City of New Westminster. Mechanical/HVAC: heat pumps, split-system condensing units, HRVs, RTUs, ductwork, fire dampers, controls/BMS (frames 22, 38).
- **Benchmark rate examples (frames 32/35):** split system install $1,500 / $3,800 / $8,200 each (low/mid/high); condensing unit install ~$1,200-$4,500 each; RTU replacement on existing curb $8,000 / $14,900 / $22,000 each; refrigerant piping per linear metre; HRV unit install (Lossnay); concrete pad; panel breaker; disconnect switch.
- **Conceptual estimate output (frames 37/38):** Direct Costs roughly $306,800 / $525,360 / $485,400; total narrative ~$566k-$797k; his stated expected band "around 400 grand to 800 grand." He flags the AI over-detailed it ("should have been five to 10 lines max").
- **Takeoff example (frame 61):** B2 light fittings counted = 21 ea; assembly expands to light fittings, support brackets, 2.5mm2 cable, electrician man-hours, cable tray (large quantity).
- **Final reconciliation (frames 76/78):** Total Requirements 132; Items Covered ~110; Coverage Rate ~75%; 17 unpriced items found; named critical gaps: concrete pads (priced 3, need 4; CU-5 Maple Room missing ~$3,500), EF-1 exhaust ductwork, fire dampers at rated walls, firestop PE check, existing BMS examination, furred-out exterior walls, 5 control items; arithmetic = "ALL CORRECT."
- **Indirect cost approaches (t=23:35):** flat markup "30% or 40%" on direct costs, or a detailed build-up driven by schedule.
- **Document triage claim (t=06:12):** of 50-100 bid docs, the important info is in "three to five documents and a handful of drawings."
- No claim of a measured AI takeoff accuracy percentage; his accuracy stance is qualitative ("not there yet," "incredibly high" chance of under/over-quote).

---

## Applicability to a structural steel fabricator (Your Company)

Fairley is a generalist GC/sub estimator (HVAC/electrical/civil examples), not steel. But his works/does-not map lands almost exactly on our governance, with a few non-transfers.

**Strongly transfers - already aligned with our rules:**
- **"Verify, do not generate" is literally his thesis.** His "use AI to cross-check, not to generate the price" equals our Operating Rule "AI checks work that costs money if wrong; it does not produce the system-of-record number unguarded." His final reconciliation step (estimate vs requirements register) is the spiritual twin of our `bridge/bid_sanity_gates.py:run_gates()` + `VirtualOwner` 15-rule review and `validate_bid_output.py`. Worth adding an explicit "missing-items / coverage-rate" reconciliation pass against an extracted requirements register, scoped to structural+misc steel.
- **Tonnage/weights stay off-limits to AI.** His "never let AI invent rates/productivity" hardens our Hard Rule 5/6: AISC member weights come ONLY from `bridge/aisc_validator.py`, and BID_RATES are CEO-locked. AI never produces a tonnage or a $/T - it reformats validated numbers. His video is external support for that posture.
- **Member takeoff = human + dedicated tooling, not AI vision.** His "visual reasoning just is not there yet, physical counting is human, assembly tools have zero AI" maps directly to our SF/accuracy standard: the jump from ROM to bid-grade is a MEASURED member takeoff (schedules + framing-plan marks through `aisc_validator`), not AI reading pixels. Our `drawing-analyzer` skill already self-limits to text-layer counts and explicitly says the model gives approximate, not accurate, counts - same caution he voices. Reinforces: do not let AI scale tonnage off a drawing image.
- **project.md synopsis = our `project-indexer` / `0.ai-context`.** His project.md is exactly our per-project `0.ai-context` layer (CLAUDE.md, project.md, drawings.md, memory.md) that cuts token use 20-40x. His "refer to project.md before reading raw docs" instruction is our loader pattern. Direct validation of the indexer design.
- **Conceptual/ROM estimate from historic benchmark low/mid/high = our ROM lane.** He prices ROM only from a benchmark library with a stated range - matches our "LOW-SF estimates are ROM only, carry a stated contingency, SF-confirmation RFI." His "give a range" is our confidence/contingency discipline.
- **Good-for-AI tasks we can adopt for steel:** requirements/exclusions register from the spec set; clarification-RFI drafting; risk & opportunity first draft; go/no-go template population; subcontractor/vendor RFQ package generation (galv, paint, deck, bolts); methodology/narrative drafting; contract review; correspondence/RFI tracking. All "data transformation," all consistent with our pipeline.
- **Automation-bias warning** is a useful addition to our review gates: a polished AI bid PDF should trigger MORE scrutiny, not less - argues for keeping the human-in-the-loop GP-report review and not auto-accepting AI-formatted numbers.

**Does NOT transfer / needs adaptation:**
- **His assembly-takeoff tool (ctakeoff.com) is generic-trade, not steel.** Our equivalent is the AISC validator + the estimate-grade coordinate model / STL pipeline (`bridge/fabrication.py`, `tekla_viewport.py`), not a light-fitting/footing assembly library. The principle (assemblies = zero AI, pull from a structured library) transfers; the specific tool does not.
- **His "five to ten line conceptual estimate" granularity** is fine for HVAC trade pricing but steel ROM still needs the SF-driven tonnage gate and per-building SF sourcing - we cannot collapse to a few lines without losing the SF-controlling-input discipline (multi-building/multi-wing jobs go LOW-confidence). His simplicity advice must not override our SF sourcing rule.
- **He treats AI duration/schedule estimation as "more accurate than man-hour method."** For us, schedule/erection-duration is tied to crew and sequence, not a generic historic library; treat any AI duration estimate as advisory only, never a committed erection program.
- **No structural-specific content** (no AISC shapes, no fab/erection rate logic, no deck/joist scope rules). His framework is process-level; the steel-specific numerics remain ours.
- **Brand/Tier-1 governance** (no supplier names, no PEMB language, render/logo rules) is entirely absent from his video - those stay our own layer.

**Net for Your Company:** This video is strong external validation of our verify-don't-generate posture and the project-indexer design. The one concrete enhancement worth piloting: a dedicated AI "estimate reconciliation" pass that diffs the finished steel estimate against an AI-extracted requirements/exclusions register and reports a coverage rate + named gaps (his frames 76/78), wired as an advisory check alongside `run_gates()` - generation stays off, cross-check stays on.

---

## Caveats

- **Frame sparsity:** 80 frames over 27:37 (~1 every 21s), and the warning header notes accuracy degrades on videos over 10 minutes. Fast on-screen actions (clicking through chats, mid-scroll Excel states) are partially captured; some exact dollar cells in the benchmark and conceptual sheets are read at 512px and may be off by a digit (e.g., the conceptual Direct Cost low/mid/high read as ~$306,800 / $525,360 / $485,400, where mid > high suggests a column/label nuance not fully legible). Treat all transcribed dollar figures as approximate.
- **Transcript artifacts:** captions double lines and garble a few numbers (e.g., "25,200 to 4 34 25,000... to 46,000" around t=12:55); I reconstructed intent, not exact cents.
- **Tool naming:** the takeoff tool is identified only by the visible URL "ctakeoff.com" (frames 61/63). I did not attribute a brand name beyond that. Bluebeam appears only as an Excel ribbon add-in, not demonstrated.
- **"Opus 4.6"** is the model string shown in his composer; it is his environment, not a recommendation, and not a model we are bound to.
- No accuracy percentage for AI takeoff is claimed in the video; his accuracy position is qualitative.
