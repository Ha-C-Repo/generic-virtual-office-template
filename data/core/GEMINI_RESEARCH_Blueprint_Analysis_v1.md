# GEMINI DEEP RESEARCH PROMPT
# Blueprint Analysis System - Outperforming Sketchdeck LIFT
# For: Joseph Hasse, Director of I.T., Your Company LLC
# Context: Building into a Python desktop app (pywebview + Bridge API)
# Date: May 2026

---

## MISSION

I am building a structural steel blueprint analysis system inside a
Python desktop application. The system must extract member data (shapes,
quantities, dimensions, connections) from construction PDFs/drawings and
produce accurate material takeoffs.

Our competitor, Sketchdeck.ai, built their LIFT product by training on
over a million hours of construction documents. We cannot replicate that
training investment. Instead, we need to build a system that achieves
HIGHER accuracy through a fundamentally different architecture:

**Our approach: Vision AI + local tool chain + ground-truth validation
+ self-healing + self-learning feedback loops.**

The thesis is simple: a system that reads a drawing with AI vision,
validates every extracted value against AISC shape databases and
engineering tables, and automatically builds new parsing capabilities
when it encounters unknown formats will eventually surpass a system
that relies purely on pattern-matched training data.

I need you to research and provide IMPLEMENTATION-READY findings for
each section below. Not theory. Not overviews. Actual Python code
patterns, library versions, API calls, and architecture decisions I
can build into production this week.

---

## SECTION 1: PDF PRE-PROCESSING PIPELINE

### What I need to know:

1. **Best Python libraries for structural drawing PDF extraction in 2026.**
   Compare: PyMuPDF (fitz), pdfplumber, pdf2image, pikepdf, borb,
   camelot-py, tabula-py. For each, give me:
   - Can it extract vector paths (lines, arcs, polylines)?
   - Can it extract text with position coordinates (x, y, font size)?
   - Can it rasterize pages at specific DPI for vision AI input?
   - Memory usage on a 200-page structural drawing set
   - License compatibility with commercial desktop distribution

2. **Optimal DPI for rasterizing structural drawings for AI vision.**
   Construction drawings have fine dimension lines, small text callouts
   (like "W14X82" or "3/8" plate), and hatching patterns. What DPI
   balances readability vs. file size vs. API token cost? Test at 150,
   200, 300, and 400 DPI. What's the sweet spot?

3. **Page classification before analysis.** A structural drawing set
   contains: cover sheets, general notes (S-001), foundation plans,
   framing plans, elevations, sections, details, schedules. I need to
   auto-classify each page type BEFORE running expensive vision analysis.
   What features distinguish each page type? (Title block position,
   drawing number prefix, content density, presence of grid lines, etc.)

4. **Multi-page cross-referencing.** Structural drawings reference each
   other constantly: "SEE DETAIL 3/S-501" or "TYP. AT ALL COLS (SEE
   S-200)". How do I build a cross-reference graph so the system knows
   which detail page to look at when a framing plan references it?

### Specific questions:

- Is there a way to extract CAD layer information from PDFs that were
  exported from AutoCAD/Revit? Some PDFs retain layer metadata.
- Can I detect drawing scale from the scale bar or title block and use
  it to compute real-world dimensions from pixel measurements?
- What's the best approach for detecting and reading dimension strings
  (like "30'-0"" or "7.62m") from rasterized images?

---

## SECTION 2: VISION AI FOR BLUEPRINT READING

### What I need to know:

1. **Best vision model for structural drawing interpretation in 2026.**
   Compare: Gemini 2.5 Pro vision, Claude Sonnet 4 vision, GPT-4o
   vision, Qwen-VL, and any open-source alternatives (Florence-2,
   LLaVA, etc.). For each:
   - Accuracy on reading steel shape designations (W14X82, HSS6X6X3/8)
   - Accuracy on reading dimension strings (30'-0", 25'-6")
   - Ability to understand structural framing layouts (column grids,
     beam spans, bracing configurations)
   - Ability to read connection details (bolt patterns, weld symbols)
   - Cost per page at 300 DPI
   - Token limit and whether a full structural sheet fits in one call

2. **Prompting strategies for structural drawing extraction.**
   What system prompts and few-shot examples maximize extraction
   accuracy? Specifically:
   - How to prompt for member schedule extraction (shape, qty, length)
   - How to prompt for connection detail reading
   - How to prompt for general notes extraction (weld requirements,
     coating specs, inspection requirements)
   - How to handle drawings with revision clouds (ignore old content)

3. **Multi-pass extraction strategy.** A single vision call may miss
   details. Research the optimal multi-pass approach:
   - Pass 1: Full page overview (what type of drawing, grid layout,
     general content)
   - Pass 2: Quadrant-by-quadrant zoom for member callouts
   - Pass 3: Detail/section callout extraction
   - Pass 4: Title block and general notes
   Should passes use the same model or different models?

4. **Confidence scoring on extracted values.** When the vision AI reads
   "W14X82" from a drawing, how confident is it? Research approaches to
   generate per-value confidence scores:
   - Multiple model consensus (Gemini + Claude agree = high confidence)
   - OCR cross-validation (vision AI + Tesseract/EasyOCR agree?)
   - AISC database validation (is "W14X82" a real shape?)
   - Contextual validation (is W14X82 reasonable for a column in a
     single-story warehouse?)

### Specific questions:

- Can I use Gemini's grounding feature to have it point to specific
  regions of the drawing where it found each member callout?
- Is there a way to fine-tune an open-source vision model on structural
  drawings without needing millions of examples? (Few-shot tuning,
  LoRA adapters, etc.)
- What's the state of the art for reading AWS weld symbols from drawings?
  These are highly standardized graphical symbols.

---

## SECTION 3: LOCAL TOOL CHAIN FOR GROUND-TRUTH VALIDATION

### What I need to know:

This is our key advantage over LIFT. We don't just extract data. We
validate every value against ground truth. LIFT trusts its training.
We trust math.

1. **AISC Shapes Database integration.** I already have AISC v16.0
   loaded as a CSV (2,299 rows, 84 columns). When the vision AI
   extracts "W14X82", we validate:
   - Does W14X82 exist in the AISC database? (It does: 82 lb/ft)
   - Is the weight-per-foot consistent with the tonnage calculation?
   - Are the section properties (d, bf, tw, tf, Ix, Sx, Zx) consistent
     with what a structural engineer would specify for this application?
   
   Research: What additional validation rules can we derive from the
   AISC database? For example:
   - Column slenderness ratio checks (L/r)
   - Beam span-to-depth ratio checks
   - Connection capacity checks based on section properties
   - Composite section checks for composite beams

2. **Dimensional validation.** When the system extracts a building
   dimension of 300'-0" x 150'-0", it should validate:
   - Total SF = 45,000 SF
   - PSF (lbs/SF) should be 5-8 for conventional steel
   - Estimated tonnage = SF * PSF / 2000
   - Does the vision-extracted tonnage match the calculated tonnage?

3. **Connection validation.** Research what rules exist for validating
   structural connections:
   - AISC Steel Construction Manual, Table 10-1 through 10-12
   - Bolt group capacity calculations
   - Weld size validation (fillet weld effective throat)
   - Are there open-source tools that compute connection capacity?

4. **Local calculators that replace AI arithmetic.** List every
   calculation that should NEVER be done by the LLM and must be done
   by a local Python calculator:
   - Weight calculations (shape weight * length * qty)
   - Tonnage totals (sum of all member weights / 2000)
   - Cost calculations (tonnage * rate)
   - Area calculations (length * width)
   - PSF calculations (weight / area)
   - Bolt count estimates
   - Weld consumable estimates
   - Paint/coating area estimates

---

## SECTION 4: SELF-LEARNING FEEDBACK LOOP

### What I need to know:

Every bid we process makes the system smarter. Research how to build
this without a massive training pipeline.

1. **Extraction accuracy tracking.** After each takeoff, Owner reviews
   and corrects the extracted data. Research how to store:
   - Original AI extraction vs. human-corrected value
   - Which model produced the extraction
   - Which drawing type (framing plan, elevation, schedule, detail)
   - Confidence score at time of extraction
   - Error type (misread shape, missed member, wrong quantity, wrong
     dimension, hallucinated member)

2. **Pattern library from corrections.** Over time, the correction data
   reveals patterns:
   - "When the drawing has grid lines at 30' spacing, the AI
     consistently misreads '30'-0"' as '3'-0"' - add a
     post-processing rule"
   - "W-shape callouts on elevation views have 40% lower accuracy
     than on plan views - use higher DPI on elevations"
   - "This specific PE firm always uses a non-standard callout format
     - store a firm-specific prompt override"
   
   Research: What's the minimum number of corrections needed before
   a pattern is statistically significant? How do I auto-generate
   parsing rules from correction data?

3. **Prompt evolution.** Research how to automatically improve extraction
   prompts based on error patterns:
   - If W-shape misreads cluster on elevation views, auto-modify the
     elevation extraction prompt
   - If dimension misreads cluster on drawings with heavy hatching,
     auto-add "ignore hatching patterns" to the prompt
   - If a specific drawing format consistently fails, auto-flag it
     for manual review while building a specialized prompt

4. **Benchmark tracking.** Research metrics for tracking improvement:
   - Extraction accuracy rate (% of members correctly identified)
   - Tonnage accuracy (extracted vs. final verified tonnage)
   - Time to takeoff (minutes from PDF drop to verified BOM)
   - Cost per takeoff (API calls * cost per call)
   - False positive rate (hallucinated members)
   - False negative rate (missed members)

---

## SECTION 5: SELF-HEALING ARCHITECTURE

### What I need to know:

This is the breakthrough concept. When the system encounters a document
format it cannot read, it should NOT fail silently. It should:

1. Detect that it failed (low confidence, missing data, inconsistencies)
2. Diagnose WHY it failed (unknown format, poor scan quality, non-standard
   callout convention, unfamiliar drawing type)
3. Research how to solve the problem (query Gemini for solutions)
4. Generate new parsing code or prompt modifications
5. Test the new approach on the failed document
6. If successful, add the new capability permanently

### Research these specific scenarios:

1. **Unknown drawing format.** The system receives a PDF from a PE firm
   it's never seen. The callout format is non-standard (e.g., "82W14"
   instead of "W14X82"). How does the system:
   - Detect the non-standard format
   - Map it to standard AISC notation
   - Store the mapping for future use with this firm

2. **Scanned drawings (not digital PDFs).** Many drawings arrive as
   scanned images with no text layer. Research:
   - Best OCR approach for construction drawings (Tesseract, EasyOCR,
     PaddleOCR, or cloud OCR)
   - How to handle skewed/rotated scans
   - How to handle drawings with coffee stains, fold marks, or stamps
   - Minimum scan quality (DPI, bit depth) for reliable extraction

3. **3D model generation from 2D drawings.** Research:
   - Can we generate a basic 3D wireframe model from extracted member
     data (columns at grid intersections, beams spanning between columns)?
   - What Python libraries support 3D structural modeling?
     (trimesh, cadquery, Open3D, pythreejs, FreeCAD scripting)
   - Can a 3D model be used to VALIDATE the extraction? (If the model
     shows overlapping members or unsupported beams, the extraction
     has errors)
   - Can we export to IFC (Industry Foundation Classes) format for
     Tekla/Revit interop?

4. **Mixed document formats.** Research handling of:
   - DWG files (AutoCAD native) - is there a Python reader?
   - DXF files - ezdxf library capabilities
   - Revit exports (IFC, PDF, DWG)
   - Hand-drawn sketches with dimensions
   - Napkin sketches photographed on a phone
   - Spreadsheet-based BOMs (Excel member schedules)

5. **Self-healing code generation.** When the system encounters a format
   it can't handle, research how to:
   - Use Gemini/Claude to generate a specialized parser
   - Sandbox and test the generated parser
   - If it works, integrate it into the pipeline
   - Version-control the generated parsers for rollback
   - What safety guardrails prevent the self-generated code from
     breaking existing functionality?

---

## SECTION 6: COMPETITIVE ANALYSIS - SKETCHDECK LIFT

### What I need to know:

1. **What does LIFT actually do?** Research their public documentation,
   case studies, blog posts, and demos. Specifically:
   - What document types does LIFT support?
   - What data does LIFT extract? (Quantities, dimensions, materials,
     connections, or just high-level counts?)
   - What accuracy rates do they claim?
   - What's their pricing model?
   - What are their known limitations? (User complaints, forum posts,
     Reddit threads, G2 reviews)

2. **Where does LIFT fail?** Research common complaints:
   - Does it handle revision clouds correctly?
   - Does it handle multi-sheet cross-references?
   - Does it validate extracted data against engineering standards?
   - Does it learn from corrections?
   - Can it handle scanned drawings?
   - Does it support structural steel specifically, or is it generalist?

3. **What's our unfair advantage?** Given that we have:
   - AISC v16.0 database (2,299 shapes)
   - Locked Q2 2026 Houston market rates
   - 9+ years of structural steel domain expertise
   - Real project history (ICD Church, Elite Crossing, Topgolf, Carvana)
   - Local Python calculators that never hallucinate math
   - Multi-model consensus (Gemini + Claude + local validation)
   
   How do we position these advantages against LIFT's training data
   advantage?

---

## SECTION 7: IMPLEMENTATION ARCHITECTURE

### What I need to know:

Give me the complete Python architecture for this system. It must fit
into an existing pywebview desktop app with a Bridge API pattern.

1. **Pipeline stages.** Define the exact sequence:
   ```
   PDF Input → Pre-process → Classify → Extract → Validate → 
   Correct → Learn → Output BOM
   ```
   For each stage, specify:
   - Input format
   - Output format
   - Which tool/model handles it
   - Error handling and fallback
   - Performance target (seconds per page)

2. **Module structure.** Map to Python files:
   ```
   bridge/
     drawing_intel/
       __init__.py
       preprocessor.py     # PDF → rasterized images
       classifier.py       # Page type classification
       extractor.py         # Vision AI member extraction
       validator.py         # AISC + dimensional validation
       cross_ref.py         # Multi-page reference resolution
       self_healer.py       # Unknown format detection + fix
       learning_store.py    # Correction tracking + pattern mining
       model_3d.py          # 3D wireframe generation + validation
       benchmark.py         # Accuracy tracking over time
   ```

3. **API cost optimization.** A 200-page structural set could cost
   $50+ in vision API calls at 300 DPI. Research:
   - Which pages can be skipped entirely? (Cover sheets, general notes
     that are text-only, blank pages)
   - Can we use a cheap/fast model for classification and an expensive
     model only for extraction?
   - Can we cache extracted data and skip re-processing when the same
     drawing is uploaded again? (Hash-based dedup)
   - What's the cost comparison: process all pages at 200 DPI vs.
     classify at 150 DPI then extract at 300 DPI?

4. **Offline capability.** The desktop app may need to work without
   internet. Research:
   - Can any open-source vision models run locally on a Windows machine
     with 16GB RAM and no GPU?
   - What's the accuracy tradeoff vs. cloud models?
   - Can we pre-cache the most common extraction patterns so the system
     works for "typical" drawings offline?

---

## SECTION 8: IMMEDIATE NEXT STEPS

### What I can build THIS WEEK:

Given the current codebase (Python 3.13, pywebview, Bridge API pattern,
Gemini + Claude + OpenAI keys available), what's the fastest path to a
working prototype that demonstrates superiority over LIFT?

1. What's the minimum viable pipeline? (Fewest libraries, fewest API
   calls, maximum accuracy)
2. What single improvement would have the biggest accuracy impact?
3. What's the cheapest way to build a test suite? (10 real structural
   PDFs from past Your Company projects)
4. How do I measure accuracy without labeled training data?

---

## OUTPUT FORMAT

For each section, provide:
1. **Finding**: One-paragraph summary
2. **Recommendation**: What to build and why
3. **Code pattern**: Python code I can use directly
4. **Libraries**: Exact pip install commands with versions
5. **Cost estimate**: API costs, compute costs, development time
6. **Risk**: What could go wrong and how to mitigate

Do NOT provide generic overviews. I need implementation-ready findings
that a senior Python developer can turn into production code in a
desktop application this week. Every recommendation must work within
these constraints:
- Python 3.13 on Windows 11
- No GPU required (must work on a standard office laptop)
- API keys available: Gemini, Claude, OpenAI
- Existing libraries: pdfplumber, httpx, numpy, reportlab, Pillow
- Budget: $0 for new paid tools. API costs only.
- EXE distribution via PyInstaller (no Docker, no cloud deployment)

---

## CONTEXT FILES AVAILABLE

The system already has:
- AISC Shapes Database v16.0 (2,299 rows, 84 columns, US customary)
- Bid rates locked for Q2 2026 ($[FAB RATE]/T fab, $[ERECTION RATE]/T erection)
- 26 Tier 1 governance rules (compliance scanner)
- 10 voice calibration rules (the Owner's output preferences)
- Intent router with 31 intent families
- 7 operational skills (drawing-reading, bid-pricing, etc.)
- Self-test harness (84/84 passing)
- Bid history database (win/loss tracking)
- VE suggestion engine (lighter shape alternatives)
- Drawing revision diff engine (scope change detection)

The goal is to make the drawing extraction layer so accurate that the
downstream pricing, narrative, and proposal generation are all grounded
in verified structural data - not AI guesses.
