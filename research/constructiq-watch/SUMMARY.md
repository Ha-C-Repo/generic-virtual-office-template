# ConstructIQ / Tim Fairley - AI Construction Estimating: Consolidated Findings

Source: 15 YouTube videos from the ConstructIQ channel (presenter Tim Fairley, community "Contractor OS"), watched at full depth (download, frame extraction, full caption transcript, every frame read). Per-video reports live beside this file as `<videoid>.md`. Lens: what transfers to Your Company, a structural steel fabricator (AISC member takeoff, tonnage, fab/erection rates, Claude Cowork bid pipeline, project-indexer and drawing-analyzer skills, MCP server, Python Bridge).

Date compiled: 2026-06-24.

## 1. The one doctrine repeated in every video

Across all 15 videos there is a single, consistent estimating doctrine. It is, almost word for word, Your Company's own "verify, do not generate" governance posture:

- AI is a reformatter, drafter, and cross-checker. It must never produce the system-of-record number (price, quantity, rate, or productivity). Said most bluntly in aSKEdBADarM ("never generate the price; under-quote risk is incredibly high") and BfNGeJuFfGI (blast-radius triage: estimates and takeoffs are AI-CHECK-only).
- Scripts do the cheap deterministic work; AI does only the judgement. "AI classifies sheets, scripts never pattern-match" (_k1jQBS4Nk8). PyMuPDF splits/extracts; the model interprets.
- Count from the drawing TEXT/vector layer and from client schedules, never from scaled measurement. This is the technical core of the whole channel (WMEZPISmxms, IqfrXoiM4bE, jCedUrbENnY, rrUqIdAMzbU, dhinW82s2DU).
- Every line carries a Confidence tier and a Method. High = vector/text tag match; Medium = schedule read; Low = vision or inferred-with-assumption. Low-confidence items get human review.
- Measure primary quantities, derive secondary by formula (Source Qty x Conversion Factor + percent Waste + Basis).
- The estimator must own deep understanding of the project; AI is for the time-consuming plumbing while the human steers.
- A final reconciliation pass diffs the finished estimate against the original requirements/exclusions register so nothing is missed and nothing is double-counted. Best run in a fresh, memoryless session so it checks against source, not its own prior working (dhinW82s2DU).

This is independent, external validation that Your Company's architecture (verify-don't-generate, aisc_validator-only weights, CEO-locked BID_RATES, SF/accuracy standard, project-indexer, drawing-analyzer) is the correct design. The channel arrives at our rules from the general-construction direction.

## 2. The unified takeoff method (most relevant to our count-gap branch)

The channel converges on one takeoff architecture, shown built in several videos:

1. Split the PDF set to one file per sheet (PyMuPDF / `import fitz`).
2. Render a high-DPI image per sheet AND extract the vector text layer.
3. Classify sheets with the AI (not regex), build durable indexes once: `drawings.md`, `sheet_classification.json`, `cross_references.json`, `coordination_issues.json`, `symbol_library.json`.
4. Count tagged items from the text layer (HIGH), read client schedules (HIGH); use vision only to identify legends/symbols/context, never to count or scale (LOW).
5. Derive secondary quantities by formula from primaries; attach a written assumption string to every inferred line.
6. Score each line High/Med/Low; run a blind independent recount and an order-of-magnitude sanity check ($/unit vs benchmark).
7. Output an Excel BOQ plus a marked-up PDF.

Named scripts seen: `extract.py`, `takeoff.py`, `build_sheet_index.py`, `crop_region.py`, `process_drawing.py`, `query_drawing.py`. The skill is variously `construction-takeoff` / `drawings-analyser` / a `qto-workflow.md` system prompt.

Evidence the method matters:
- Image-only pile count 27 vs vector-extracted 30 (correct) - IqfrXoiM4bE.
- Naive Cowork over-counted footings (141) and refused an 11 MB upload - _k1jQBS4Nk8.
- Naive Cowork drawing path measured at 60,211 tokens / 26 tool calls vs about 5 KB of indexed text - _k1jQBS4Nk8.
- AI polygon slab footprint about 13,250 m2 vs 13,600 m2 in Bluebeam - _k1jQBS4Nk8.
- Vision accuracy is the binding constraint. ClockBench numbers cited aloud (rrUqIdAMzbU): human 90.7 percent; best GPT about 50 percent; Gemini 3.1 Pro 32.2 percent; Claude Opus 4.6 under 10 percent. Hence "vision is backup, not default."

For our `feature/count-gap-sf-a1` branch: his schedule-QTY-vs-plan-mark-count reconciliation, the method-linked confidence tiers, and the explicit per-line assumption string are all directly adoptable. The fence-post counting rule from the rebar video (below) is a concrete formula to encode.

## 3. Consolidated skill catalog (slugs seen on screen across the set)

| Skill slug | Purpose | Seen in |
|---|---|---|
| project-indexer | Build `0.ai-context` per-sheet drawing markdown + summaries + JSON indexes | VrSs8, fjodH, 5iImq, _k1jQ |
| drawing-analyser / drawings-analyser | Per-sheet split, vector-text extraction, sheet classification, durable indexes | WMEZP, _k1jQ, iCNSq |
| construction-takeoff | Count tags from text layer; Excel BOQ + marked-up PDF | WMEZP, IqfrX, dhinW |
| requirements-extraction | Tender docs to structured BOQ + clarification/RFI register | VrSs8, BfNGe, dhinW, 5iImq |
| assemblies | Customize generic assemblies to project from drawing tags | VrSs8 |
| estimating-workflow | Orchestrator chaining the sub-skills with human-confirm gates | VrSs8, BfNGe, iCNSq, dhinW, jCedU |
| conceptual-estimate | ROM / budget estimate from your benchmark data | jCedU |
| line-item-pricing | Per-line pricing (sub-agent spun up per item) | BfNGe, iCNSq, dhinW |
| schedule-builder / gantt-chart | Estimate duration; build Gantt artifact | VrSs8, 5iImq, BfNGe |
| reconciliation-check | Diff estimate vs requirements; flag gaps/double-counts; benchmark $/t, $/SF | VrSs8, BfNGe, 5iImq, dhinW, aSKEd |
| procurement-packaging | Build subcontractor RFQ packages | 5iImq, dhinW |
| contract-review (+ departures-register) | Review contract vs standard terms | 5iImq |
| go-no-go-review | Bid/no-bid screen | 5iImq |
| document-controller | Document register / transmittals | 5iImq, BfNGe |
| om-manual | O&M manual assembly | 5iImq |
| subcontractor-quote-analysis | Compare/normalize sub quotes | VrSs8 |
| mcp-builder, skill-creator, setup-cowork | Build skills/MCP, set up Cowork | VrSs8 |

Skill file structure (BfNGe, IqfrX): `SKILL.md` + `references/` + `scripts/`, trigger-phrase auto-invocation. ContractorOS ships as a Claude plugin (v0.1.2, "27 construction skills") distributed via a GitHub-backed marketplace (iCNSq).

## 4. Tools, connectors, models seen

- Claude surfaces: Cowork (desktop, folder-scoped projects, Memory, scheduled tasks), Claude for Excel (basic model, no CLAUDE.md access, driven by a workbook "AI instructions tab"), Chat, Code.
- Other tools: Excel, Word, Notion (business-context store), Airtable (cost DB via low-token MCP), Bluebeam Revu, Openspace / ZZ Takeoff, ctakeoff.com, Google Antigravity (Gemini), Operum (cost data).
- MCP packages named (zDt-k3AC_LE): `@modelcontextprotocol/server-filesystem`, `@modelcontextprotocol/gdrive`, `mcp-google-sheets`, `gmail-mcp`, `ms-365-mcp-server`, `pdf-reader-mcp`, plus a beta "Bluebeam MCP" (unverified).
- Model tiering matches ours: Haiku for extraction, Sonnet default, Opus only for hard work (fjodH). On-screen model labels across videos: Opus 4.7, 4.6, 4.5, and one read as 4.8 (some labels are low-confidence OCR at 512px).
- Chat vs Cowork vs Code routing (k3Bj31): Chat = few inputs to one output (about 90 percent of use); Cowork = many inputs/outputs over a desktop folder it can read/write/delete; Code = connect to software with no pre-built connector via APIs/MCP that Claude scripts itself.

## 5. Security findings (zDt-k3AC_LE, BfNGe)

- Live prompt-injection demo (a LinkedIn payload made a cold-email agent reply with a flan recipe), over-privileged access, supply-chain risk (a fake Postmark MCP BCCing emails), and tool poisoning. Connectors are powerful and dangerous.
- Cowork is desktop-only, can "go rogue" over a folder, and asks for a per-folder Allow gate. He keeps cost/rate data in cloud Notion, which for us is a Tier-1 violation.

## 6. The rebar video is the only steel-specific method (jrmaDOIESjY)

No AI is used; it is pure manual methodology, but the math is directly encodable for our secondary-steel/rebar count-gap work:

- Decompose each element into bar groups (straight X, straight Y, U/L bars, starters, ligatures, mesh), one row per group.
- Count from spacing with the fence-post rule: `bars = ROUNDUP(span / spacing) + 1` (a 1 m run at 200 mm spacing = 6 bars, not 5).
- Length per bar = element dimension plus developed bent-leg length; add a lap only when the run exceeds the 3 m or 6 m stock bar (lap from the general-note table, or 40 to 50 x diameter).
- Weight = total length x weight-per-metre, doubled for top+bottom layers, summed to tons, then plus 3 to 5 percent waste.
- The ratio method (kg/m3 x concrete volume) is ROM only; it under-read the worked slab by about 50 percent.

Caution: all his weight/lap/cover figures are metric N-convention (for example N16 = 1.65 kg/m). For Your Company these must come from our own validated US-convention sources, never his numbers.

## 7. What transfers to Your Company, prioritized

Adopt (high value, low risk, fits our governance):

1. Reconciliation pass as an advisory gate. A stored skill that diffs the finished steel estimate against an AI-extracted requirements/exclusions register and reports coverage rate plus named gaps. Wire it alongside `run_gates()`; generation stays off, cross-check stays on. His results: 17 unpriced items found, about 75 percent coverage; a double-count and 9 scope gaps caught. Best run in a fresh memoryless session.
2. Enrich our drawing-analyzer / project-indexer outputs with `cross_references.json` and a `coordination_issues.json`, matching his durable-index pattern. Keep "AI classifies, scripts never pattern-match."
3. Fold his explicit takeoff prompt clauses into the count-gap engine: "use explicit schedules rather than counting, use explicit dimensions rather than scaling, infer secondary from primary," plus a written assumption string per inferred line and method-linked confidence tiers.
4. Encode the fence-post count rule `ROUNDUP(span/spacing)+1` and schedule-mark reading for rebar/secondary steel in the A1 schedule reader and Engine B grid geometry.
5. Row-level schema for our takeoff: Tag / Description / System / Qty / Unit / Drawing / Method / Confidence / Basis / Notes (from jCedU, dhinW).
6. Distribute our `skills/` as a GitHub-backed "YourCo-OS" plugin marketplace so Owner and Joseph pull synced, version-controlled skills without an EXE rebuild (iCNSq).
7. Explicit dollar-threshold escalation table for human review (fjodH), and the conceptual ROM clearly labelled budget-only (-20 percent / +30 percent), never lump-sum (jCedU).

Reject or guard (Tier-1 / accuracy risks):

- Do NOT put MATERIAL_COSTS, supplier names, or BID_RATES in any cloud connector (Notion, Airtable, etc.). His cloud cost-library pattern is a Tier-1 confidentiality breach for us.
- Do NOT let AI count members or scale lengths for bid-grade tonnage. Keep member takeoff (schedules + framing-plan marks) flowing through `aisc_validator.py`; LLM ratios must never set tonnage or rates.
- Do NOT treat his ROM/conceptual output as bid-grade. The accuracy jump to bid-grade is a measured member takeoff, exactly our SF/accuracy standard.
- His fuzzy rate-matching must stay off our deterministic, CEO-locked steel rates.
- Commercial AI QTO tools: his verdict is not worth it (overpriced, never 100 percent, slower than outsourcing). A self-built, validator-backed agent is the only version worth running.

Does not apply: his concrete/MEP/HVAC/fitout assembly content and coverage checklists; we need AISC-keyed equivalents.

## 8. Per-video index

| # | Video ID | Title | Duration | One-line takeaway | Report |
|---|---|---|---|---|---|
| 1 | VrSs8mGI8ss | How to Estimate a Construction Project with Claude AI | 24:53 | Full scope-to-letter-of-offer workflow; AI does plumbing, human owns numbers | VrSs8mGI8ss.md |
| 2 | WMEZPISmxms | AI for Quantity Take-Offs - Step-by-Step | 20:37 | Split per sheet, PyMuPDF text layer, count tags not pixels, confidence + blind recount | WMEZPISmxms.md |
| 3 | IqfrXoiM4bE | How to Build an AI Quantity Take-Off Tool | 28:38 | The tool is a `construction-takeoff` skill (extract.py/takeoff.py); pile count 27 vs 30 | IqfrXoiM4bE.md |
| 4 | jCedUrbENnY | Build Your Own AI Construction Estimator | 14:24 | Cowork + skills + Airtable cost DB via MCP + fixed Excel; conceptual only | jCedUrbENnY.md |
| 5 | fjodH7eGwg0 | How to Set Up Claude Cowork for Construction | 19:12 | 3-layer setup: Notion context, Cowork project + Memory, project-indexer 0.AI Context | fjodH7eGwg0.md |
| 6 | BfNGeJuFfGI | How Claude Cowork Actually Works | 21:49 | Cowork mechanics; compounding-error math; blast-radius triage (estimates AI-check only) | BfNGeJuFfGI.md |
| 7 | iCNSq4FLboE | Claude Plugins for Construction | 11:17 | Plugin = bundle of skills/connectors/agents; GitHub marketplace distribution | iCNSq4FLboE.md |
| 8 | 5iImqMMGjkI | 8 Claude Skills for Construction | 23:35 | 8 named skills incl reconciliation-check, project-indexer, go-no-go-review | 5iImqMMGjkI.md |
| 9 | _k1jQBS4Nk8 | Claude Code + Construction Drawings | 18:24 | Claude Code drawings-analyser; durable MD/JSON indexes; AI classifies, scripts never pattern-match | _k1jQBS4Nk8.md |
| 10 | dhinW82s2DU | Claude Cowork & Skills + Excel | 12:12 | Skill chain into Excel templates; blind separate-session reconciliation caught 9 gaps | dhinW82s2DU.md |
| 11 | k3Bj31-pXOc | Claude Chat vs Cowork vs Code - Explained | 04:18 | Routing rule for the three surfaces; folder-scoped Cowork bid pipeline analog | k3Bj31-pXOc.md |
| 12 | aSKEdBADarM | AI for Estimating - What Works, What Doesn't | 27:37 | Verdict centerpiece; reconciliation found 17 unpriced items, ~75% coverage | aSKEdBADarM.md |
| 13 | rrUqIdAMzbU | AI Quantity Take-offs - Actually Worth Using? | 15:54 | Commercial tools not worth it; self-built agent for 3 narrow jobs; ClockBench numbers | rrUqIdAMzbU.md |
| 14 | jrmaDOIESjY | Steel Reinforcement Takeoffs Made EASY | 21:49 | Manual rebar method; fence-post count rule; ratio method under-reads ~50% | jrmaDOIESjY.md |
| 15 | zDt-k3AC_LE | Connect AI to your Construction Tools | 08:37 | MCP connectors for drawings/sheets/email; named packages; serious security risks | zDt-k3AC_LE.md |

## 9. Caveats on this research

- All videos were sampled at about 80 frames (roughly one frame every 8 to 18 seconds) at 512px, so fast on-screen detail (exact Excel cells, small JSON values, regex bodies, leaderboard sub-decimals) is approximate where noted in each per-video report. Spoken content is from complete caption transcripts and is reliable.
- A few model-name and connector OCR reads are low-confidence (for example "Opus 4.8", "Operum/Opryum", "Gov 4.1/Clove 4.5" almost certainly GPT 4.1 / Claude 4.5) and are flagged in the individual reports.
- Two videos needed download fallbacks (fjodH7eGwg0 stream 403, recovered via tv-client format 18); all 15 completed.
- Accuracy figures quoted by the presenter (ClockBench percentages, token counts, coverage rates) are his stated numbers, not independently verified.
