---
name: drawing-reading
description: >
  Structural drawing reading protocol. Use when PDF drawings are uploaded,
  when Owner says "take off this", "bid this", or "drawings attached."
  Prevents the #1 frustration: skipping the takeoff.
triggers:
  - drawings uploaded
  - take off this
  - bid this
  - structural drawings
  - plan set
  - s-sheets
---

# Drawing Reading Protocol

The most critical operational skill. Violating this protocol has caused
more CEO frustration than any other error.

## Rule 1: Claude owns 100% of takeoff
Claude runs the takeoff. Not Ivan, not Joseph, not "pending review."
Claude reads every sheet, extracts every member, computes every weight.

## Rule 2: Read general notes FIRST (S-001/S-002)
Before reading ANY plan sheet, find and read:
- S-001: General structural notes (steel grade, design loads, codes)
- S-002: Connection details, typical sections
These set the context for everything else.

## PRE-TAKEOFF QA CHECKLIST
Runs BEFORE any census or measurement. No member counting, no scaling,
no quantity extraction until all six items are answered. Each item
produces a yes/no plus a one-line finding. Low-confidence findings are
flagged for human check, never silently passed (the existing confidence
rule applies). The completed block sits at the top of the takeoff
record, and Ivan signs it as part of his verification gate.

The six items, in order:

1. Grid system identified. Lettered and numbered axes located, grid
   dimensions captured.
2. Levels and elevations identified from sections.
3. Section and detail callout map built. Every callout on the plans
   resolves to a drawn section; any callout that does not resolve is
   the finding.
4. GENERAL NOTES read IN FULL. Explicitly extract: deck gauge and type,
   camber requirements, paint and coating spec, special inspections,
   connection design responsibility, AESS requirements. These are the
   silent price changers.
5. Spec cross-references listed. Which CSI sections the drawings
   invoke.
6. Revision status confirmed. Latest issue, addenda incorporated,
   revision clouds checked (Rule 13 covers cloud detection).

Checklist block format, placed at the top of the takeoff record:

```
PRE-TAKEOFF QA CHECKLIST - <project> - <date>
1. Grid system identified:      YES/NO - <one-line finding>
2. Levels and elevations:       YES/NO - <one-line finding>
3. Callout map resolves:        YES/NO - <one-line finding>
4. General notes read in full:  YES/NO - <one-line finding>
   deck gauge/type: <...>  camber: <...>  paint/coating: <...>
   special inspections: <...>  connection design resp: <...>  AESS: <...>
5. Spec cross-references:       YES/NO - <CSI sections invoked>
6. Revision status confirmed:   YES/NO - <issue, addenda, clouds>
CONFIDENCE FLAGS: <every low-confidence item listed; never omitted>
IVAN SIGN-OFF: ____________ (verification gate)
```

A NO on any item is not a stop. It is a finding that rides with the
takeoff so the price carries the risk visibly. A NO on item 4 or item 6
is the exception: do not price until the general notes are read in full
and the revision status is known.

## Rule 3: Rasterize and VIEW every plan sheet
- Convert each PDF page to image (300 DPI minimum)
- Actually look at each image - do not rely on text extraction alone
- Text extraction is FORBIDDEN for quantity takeoff (pdfplumber misreads)
- Use Gemini vision for member identification from rasterized images

## Rule 4: Extract member-by-member
For each structural sheet, identify:
- Columns: shape, length, quantity, grid location
- Beams: shape, span, quantity, level
- Bracing: shape, length, quantity
- Joists: designation, span, spacing, quantity
- Deck: type (roof/composite), gauge, area in SF

## Rule 5: Cross-check SF vs tonnage
After takeoff, verify: total SF / total tons should land within:
- Conventional steel: 6-8 psf
- Tilt-up: 5-6 psf
If outside range, re-examine the takeoff before pricing.

## Rule 6: AISC database is the ONLY weight source
All weights come from bridge/calculators.py using aisc_shapes.csv.
Never estimate weights from memory. Never use LLM arithmetic.

## Rule 7: Drawing stage classification
Before pricing, classify:
- IFC (Issued for Construction): 0% adder
- DD (Design Development): +3-5% adder
- Budget/Concept/SD: +5-8% adder
Adder rides on QUANTITY, not price. Never disclose to client.

## What NOT to do
- Never skip the takeoff and go straight to pricing
- Never use placeholder tonnage ("approximately 50 tons")
- Never say "Ivan to verify" as a reason to skip your own takeoff
- Never use tilde (~) quantities in any document

## Rule 8: Multi-Pass Vision Strategy (from Gemini research)
Do NOT extract everything in a single pass. Use three passes:
- Pass 1: Identify grid intersections (A-1, B-2, etc.) and scale
- Pass 2: Extract member callouts anchored to grid locations
- Pass 3: Validate against AISC database (see Rule 9)

## Rule 9: AISC Validation Gate
Every extracted shape MUST pass through validate_shapes() before
entering the pipeline. This catches:
- Hallucinated shapes: "W14X81" does not exist (suggest W14X82)
- Reversed notation: "82-W14" normalized to "W14X82"
- Weight arithmetic: AI cannot multiply. Calculator does.
- Mass balance: if total tonnage doesn't match member sum, flag it

Call validate_shapes() after extraction. Call aisc_mass_balance()
after tonnage is computed. These are non-negotiable gates.

## Rule 10: Page Hash on Revisions
When revised drawings arrive, call compare_drawing_revisions()
BEFORE re-processing. Only changed pages go through vision AI.
This saves Gemini API costs and avoids re-introducing errors
in pages that haven't changed.

## Rule 11: 300 DPI for Analysis, 150 DPI for Classification
- Classification pass (routing S-sheets vs A-sheets): 150 DPI
- Analysis pass (reading member callouts): 300 DPI grayscale
- Higher DPI wastes tokens. Lower DPI loses weld symbols.

## Rule 12: CAD Layer Isolation (PyMuPDF OCG)
When available, use PyMuPDF OCG metadata to isolate:
- "Steel" layer: structural members (process this)
- "Notes" layer: text annotations (read for context)
- "Architecture" layer: walls, finishes (ignore)
This reduces visual noise before AI processing.

## Rule 13: Revision Cloud Detection (Gemini Suggestion #3)
When processing revised drawings, specifically prompt the vision AI to:
- Identify content inside cloud-shaped (revision cloud) polygons
- Label each cloud with its revision number
- Offer toggle: "Include Rev X only" or "Ignore cloud-marked members"
This prevents double-counting members that were moved/deleted.

Vision prompt addition for ROI pass:
"Identify any revision clouds on this sheet. For each cloud, list:
1. The revision number/letter
2. All member callouts inside the cloud boundary
3. Whether the cloud indicates ADDED, MODIFIED, or DELETED members"

## Rule 14: Connection Table Extraction (Gemini Suggestion #4)
Extract connection tables (typically on S-501/S-502 sheets).
For each connection type, validate against AISC Table 10-1:
- Count bolts specified in the connection
- Check if bolt count physically fits the beam web depth (d)
- Flag if more bolts are specified than the web can accommodate

This catches a class of errors LIFT completely ignores:
connection conflicts where the PE specified bolts that don't fit.

## Rule 15: Tesseract Bundling (Gemini Suggestion #5)
For PyInstaller distribution, consider bundling Tesseract binaries
in the /_internal folder to avoid a separate installation step.
Alternative: use pyocr as a lighter wrapper.
If Tesseract is not installed, pymupdf4llm still works for all
non-scanned PDFs (which covers 90%+ of structural drawing sets
since most are CAD-exported PDFs with selectable text).
