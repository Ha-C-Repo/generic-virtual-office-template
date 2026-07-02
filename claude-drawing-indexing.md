# Construction Drawing Indexing Workflow (Your Company Adaptation)

**Source:** Video transcript "How to Get AI to Read Construction Drawings,"
May 2026. Same author as the routines and estimating videos.
**Use when:** Building the drawing-indexing layer that feeds every other
workflow (estimating, takeoffs, RFIs, change orders).
**Relationship to existing files:** Foundation layer for
`claude-estimating-workflow.md`. The in-house substitutes for
ContractorOS already exist as `.claude/skills/project-indexer/SKILL.md`
and `.claude/skills/drawing-analyzer/SKILL.md`. This file EXTENDS those
skills with the Antigravity / NotebookLM / Gemini Vision pipeline. It
does not replace or rebuild them.
**Plan position:** This is the most important video of the three. Drawing
indexing is the bottleneck. Without it, none of the downstream estimating,
RFI, or change-order routines work reliably on real bid packages.

## Core thesis: why direct PDF upload fails

A 25-sheet structural drawing set is 15 to 20 MB. Three things break:

1. **Direct chat upload.** Hits Claude's effective upload limits even when
   the documented limit says 10 MB should work. Fails with "format not
   supported."
2. **Claude Projects RAG.** Same upload problem. The project-knowledge
   embedder cannot ingest the file in the first place.
3. **Cowork on the folder.** Works, but jams the entire PDF set into
   context per query. Burns roughly 30x the tokens needed. Pro usage
   caps out on one set of drawings. Accuracy drops as context fills.

The solution is to never make the model read the PDFs at query time.
Pre-process drawings into a structured database or per-drawing markdown
file. At query time, the model reads the index, not the original PDF.

Analogy from the video: it is the difference between handing someone 100
drawings and asking the height of a retaining wall, versus handing them the
one retaining-wall drawing with the height already labeled.

## The two architectures

### Architecture A: Antigravity + Database + MCP

Tools used: Google Antigravity (free), Airtable (the video's choice),
Gemini 2.5 Pro for vision, PyMuPDF for vector extraction.

Pipeline (Phase 1 - Phase 2 - Phase 3, with confirmation between each):

1. **Find** the source PDF folder.
2. **Create** `/indexed/` working folder.
3. **Split** the merged PDF into single-sheet PDFs in `/indexed/pdfs/`.
   Name by drawing number if detectable, else `{source}_page_{n}.pdf`.
4. **Render** each single-sheet PDF to PNG at 300 DPI (400 DPI for A1 or
   larger sheets). Save to `/indexed/images/`.
5. **Extract** vector text data (positions, orientations) via PyMuPDF.
   Store whether vector data is present per sheet.
6. **Write** a reusable Python script (`prepare.py`) so future projects
   can re-run the pipeline.
7. **Send** each rendered PNG plus its vector text to Gemini Vision with a
   strict estimator-focused prompt covering scope of work, elements and
   dimensions, material specs, connections, coordination notes.
8. **Push** the structured output to the database (Airtable in the video).

Output schema (the 11 fields shown in screenshot 5):
- Drawing Number (single line, primary key)
- Drawing Title (single line)
- Discipline (single select: Architectural, Structural, Civil, Mechanical, Electrical, Hydraulic, Fire, Other)
- Revision (single line)
- Scale (single line)
- Source File (single line)
- Estimator Summary (long text)
- What's Shown (long text)
- Extracted Quantities (long text)
- Specifications (long text)
- (one more field, partially obscured)

At query time, Claude connects to the same database via MCP and reads rows,
not PDFs.

### Architecture B: NotebookLM + Claude Code -> drawing.md files

Tools used: NotebookLM (included in Google AI Ultra), Claude Code, OneDrive.

Pipeline:
1. Upload the drawing set to a NotebookLM notebook. Google's multimodal
   embedder handles drawings well.
2. Connect NotebookLM to Claude Code via the integration (finicky but
   documented).
3. Claude Code queries NotebookLM per drawing, writes one `drawing.md` per
   sheet into the project folder. Each file is a complete text
   representation of one drawing: contents, structure, dimensions, material
   specs, what's shown.
4. Downstream Cowork sessions read the `.md` files instead of the PDF.
   Per-query token cost drops roughly 30x.

The video author considers Architecture B simpler and faster to set up.
He also notes Architecture B is still being refined; the exact prompt for
generating the per-drawing markdown is a work in progress.

## What the screenshots add beyond the transcript

Screenshot 1 shows the actual implementation plan Antigravity drafted before
executing. Comprehensive estimator summaries via Gemini Vision parsing.
Real generated script name: `indexed/generate_summaries.py`. Iterates 25
drawing images, sends each to Gemini Vision with an estimator-focused
prompt covering Scope of Work, Elements and Dimensions, Material Specs,
Connections.

Screenshot 12 shows the NotebookLM output narrative quality. Example pulled
quotes worth noting for structural steel:
- "Connections (S711, S720): lots of varied cleats, end plates, cast-in
  plates, fabrication complexity, coordination with precast"
- "Portal frames (S401): precambers mandatory, fabricator-driven"
- "Galvanising required for all exposed steel including outdoor office
  framing, and flagged on S301 for future solar allowance"

That kind of output is exactly what Your Company's bid review needs surfaced
before pricing.

Screenshots 6-9 confirm the final folder structure on OneDrive:
```
Antigravity Demo/
  indexed/
    pdfs/        (split single-sheet PDFs, 25 files)
    images/      (PNG render of each sheet)
    prepare.py
    extract.py
    compile_data.py
    compiled_data.json
    dump_records.py
    vector_quantities.json
    vector_status.json
  [original merged PDF]
  Bill_of_Quantities.md
  antigravity_talking_points.md
  records_dump.json
```

## Stack additions (Google AI Ultra)

Adding to Your Company's paid stack per the user's confirmation:

| Tool | Role | Status |
|---|---|---|
| Google Antigravity | Desktop agent for the splitting/extraction pipeline | Free with Google account, install at antigravity.google |
| NotebookLM | Drawing database, narrative summaries | Included in Google AI Ultra |
| Gemini 2.5 Pro / 3 Pro Vision | Vision API for drawing analysis | Included in Google AI Ultra |
| Gemini in Workspace | In-app drafting inside Sheets/Docs | Included in Google AI Ultra |

This expands the stack constraint in the system prompt. The hard rule was
Claude Max, Google Premium, M365, Runway. With Google AI Ultra the
Google tier covers Antigravity, NotebookLM, and Gemini Pro Vision at high
quota. No new paid tools required for either architecture.

Airtable from the video is NOT being added. Your Company has two zero-cost
substitutes already in stack:
- Google Sheets (Drive-accessible, queryable via Claude with Drive MCP)
- SharePoint List (M365-native, queryable via M365 MCP)

## Recommended Your Company path: hybrid

Run both architectures because they produce complementary outputs.

1. **NotebookLM-first for narrative.** Upload each bid package to a
   NotebookLM notebook. Use it to produce one drawing.md per sheet plus a
   bid-level summary. Stored in OneDrive next to the bid. Cheap, fast,
   leverages the Ultra plan already paid for.
2. **Antigravity-driven for structured rows.** Run the splitting + vision
   pipeline. Output to a Google Sheet with the 11-field schema (modified
   for structural steel, see below). The Sheet is queryable, sortable,
   exportable to CSV for the ZZ Takeoff import step.

NotebookLM gives the writeup. The Sheet gives the queryable data. Both
read by Cowork at estimating time.

## Structural-steel schema adjustments

The video's 11 fields are general construction. For Your Company, modify:

| Field | Video version | Your Company version |
|---|---|---|
| Drawing Number | Single line | Same |
| Drawing Title | Single line | Same |
| Discipline | Multi-discipline select | Drop. All Your Company drawings are Structural. Replace with "Sheet Type" (Plan, Elevation, Section, Detail, Schedule, Anchor Bolt Plan) |
| Revision | Single line | Same |
| Scale | Single line | Same |
| Source File | Single line | Same |
| Estimator Summary | Long text | Same |
| What's Shown | Long text | Same |
| Extracted Quantities | Long text | Replace with "Members on Sheet" (W-shapes, HSS, plate, anchor rods) and "Tons Estimated" |
| Specifications | Long text | Same, plus "Connection Types" (moment, shear, gusset, splice, base plate) |
| (11th field) | Unknown | "Coordination Flags" (links to architectural, MEP, concrete, precast) |

Add one Your-Company-specific field: "Engineering Required" (Yes/No, with
note). This catches sheets where shop drawing engineering scope is implied
but not stated.

## What this changes about the existing Your Company plan

1. The Project Indexer and Drawing Analyser skills are already built
   in-house at `.claude/skills/project-indexer/SKILL.md` and
   `.claude/skills/drawing-analyzer/SKILL.md`. The Antigravity /
   NotebookLM architectures in this file EXTEND those skills with the
   pre-processing pipeline (split, render, vector extract, vision
   summary). The skills stay as the entry points; the pipeline is
   the implementation layer they call.
2. The project-level `0.ai-context/` folder is the Cowork project
   loader (one per Cowork project, not per bid). To avoid name
   collision, the per-bid context folder introduced by the estimating
   workflow is `_bid_context/` (was provisionally called `0.AI-context`
   in the source video). Companion per-bid folder: `indexed/` for the
   split PDFs, images, scripts, and compiled data. Two folders side by
   side per bid: `_bid_context/` and `indexed/`.
3. The ZZ Takeoff trial test plan gets a precondition: run the indexing
   pipeline on the trial bid package first. The takeoff measurements then
   get cross-referenced against the indexed sheet schedule.

## Open questions

1. Which database, Google Sheets or SharePoint List? Sheets is faster to
   set up and Gemini integration is native. SharePoint keeps everything in
   M365 with the existing Joseph and Owner permissions. Recommend Sheets
   first for speed; migrate to SharePoint later if access becomes an issue.
2. Antigravity prompt template. The video author's prompt is shown in
   screenshots 1, 2, 4, 5. It needs to be saved verbatim as a reusable
   Your Company template before the first real bid runs through the pipeline.
3. NotebookLM integration with Claude Code. The video author calls this
   "a tiny bit finicky." Joseph should plan a one-hour spike to verify the
   Claude Code <-> NotebookLM bridge actually works on Joseph's machine
   before relying on it for a live bid.
4. Trial bid selection. The ZZ Takeoff trial bid (from the previous file)
   should ideally also be the trial subject for this indexing pipeline.
   One bid, all three workflows tested at once.
