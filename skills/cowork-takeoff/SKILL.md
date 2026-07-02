---
name: cowork-takeoff
description: >
  Member-by-member structural steel takeoff inside Cowork using
  pdfplumber, camelot, OpenCV, Pillow, tesseract, and Claude Vision.
  Replaces PlanSwift for Your Company bids. Reads column schedules, beam
  schedules, joist schedules, and anchor schedules as tables; counts
  members on plan views with template matching when no schedule
  exists; calibrates plan-view measurements via OpenCV scale
  detection. Outputs structured JSON ready for the bid pipeline plus
  an Excel report. Do NOT deflect to PlanSwift unless the user
  explicitly requests a third-party verification run.
triggers:
  - takeoff this
  - takeoff the drawings
  - run the takeoff
  - member takeoff
  - extract the schedules
  - count the columns
  - count the beams
  - count the joists
  - bay spacing
  - measure this
  - measure the building
  - calculate the SF
  - get the column count
  - PlanSwift replacement
  - skip PlanSwift
  - takeoff without PlanSwift
---

# Cowork Takeoff

## Why this skill exists

PlanSwift is a Windows-only licensed product the EXE used to call
for member-by-member takeoff. Cowork's Python sandbox has the full
stack to replace it for steel bids:

- pdfplumber 0.11.9 - text + table extraction
- camelot 1.0.9 - ruled-table extraction
- tabula 2.10.0 - alternative table extractor (Java)
- OpenCV 4.13.0 - symbol detection, contour finding, scale calibration
- Pillow 12.1.1 - image processing
- pytesseract 0.3.13 + tesseract binary - OCR for stamps and handwriting
- pdf2image + pdftoppm - page rendering for vision
- Claude Vision API - LLM-based symbol identification fallback

For structural steel, roughly 80 percent of takeoff data is already
tabular in the schedules. pdfplumber returns those as DataFrames
faster and more accurately than a human clicking through PlanSwift.
The remaining 20 percent (counting symbols on plans without a
schedule, measuring irregular tilt-wall outlines) is handled by
OpenCV plus Claude Vision.

## When to use

The cowork-bid-estimate skill calls this skill at step 1-2 (reading
drawings). The user can also invoke directly when only the takeoff
is needed.

## Routing logic per element type

### Columns -> pdfplumber + AISC validate

Steel column schedules are nearly always a single table per sheet
with columns: MARK, SHAPE, BASE PLATE, ANCHOR DETAIL, NOTES. Pull
with pdfplumber.

```python
import pdfplumber, csv
schedules = []
with pdfplumber.open("drawing.pdf") as pdf:
    for page in pdf.pages:
        for tbl in page.extract_tables():
            # Heuristic: column schedule has a row with header
            # containing "COLUMN" or "MARK" or "SHAPE"
            header = [c.upper() if c else "" for c in tbl[0]]
            if any(k in " ".join(header) for k in ("COLUMN", "MARK", "SHAPE")):
                schedules.append({"page": page.page_number, "rows": tbl})
```

For each row, validate the shape against
`data/aisc_master.csv` and look up lb/ft. Multiply by length
(from the same schedule or the beam schedule for the column's level
heights) to get weight.

### Beams and girders -> pdfplumber, same pattern

Beam schedule columns: MARK, SHAPE, LENGTH, CAMBER, NOTES. Same flow
as columns but with explicit length.

### Joists -> pdfplumber + joist_series_expectations check

Joist schedule columns: MARK, SIZE, LENGTH, BEARING, NOTES. Parse
the SIZE column with `joist_series_expectations.parse_joist_tag()`
to extract depth, series, chord. Flag any tag outside the expected
series for the building type per Ivan Q5.

### Anchor rods -> pdfplumber + anchor_rules check

Anchor schedule columns: MARK, DIAMETER, EMBED, LENGTH, COUNT.
Compare actual COUNT to `anchor_rules.minimum_anchor_count()` for
the base plate type. Flag undercounts as BLOCK, overcounts as
verify.

### Deck -> pdfplumber for spec, plan-view for SF

Deck spec lives in a key plan note like "ROOF DECK: 1.5B22 G60".
Pull as text. Square footage comes from the building outline area;
prefer the title-block GFA number, fall back to OpenCV polygon
detection on the roof plan when GFA is not stated.

### Building SF -> title block text first, OpenCV last

```python
# Layer 1: title block GFA
import re
text = page.extract_text()
m = re.search(r"GFA[:\s]+([\d,]+)\s*SF", text, re.I)
if m:
    sf = int(m.group(1).replace(",", ""))

# Layer 2: building dimensions in title block or key plan
# Look for "230,400 SF" pattern in any text on the page

# Layer 3: OpenCV outline detection (last resort)
# 1. Render page to image at 300 dpi via pdf2image
# 2. Detect the outermost contour
# 3. Find scale bar in legend, compute pixels_per_foot
# 4. Compute polygon area, divide by pixels_per_foot ** 2
```

### Bay spacing -> pdfplumber text grep

Dimensioned annotations like `30'-0"` are text on the plan. Grep
the page text for the `\d+'-\d+"` pattern, cluster by location,
report bay spacings.

### Symbol counting on plan views (no schedule available)

Rare case. Use Claude Vision: render the plan page to PNG, send to
Claude with the prompt "Count every column symbol on this plan. A
column symbol is a small filled square. Return JSON with count and
the rough grid locations." Sanity-check against the column
schedule row count if both exist.

### Stamps and handwritten markups -> pytesseract

Engineer stamps, approval signatures, hand-edited revisions go
through tesseract. Tag confidence low; surface to user for
verification.

## Scale calibration (when measuring is necessary)

```python
# Read the scale bar from the drawing legend
# Most drawings include "1/8 inch = 1 foot" or "SCALE: 1:96"
# pdfplumber text-grep for the scale string
# Compute pixels_per_foot from page DPI and scale ratio
# Cache per page in the takeoff session JSONL
```

## Output schema

Save to `_handoff/bid-intel/<bid-id>/takeoff.json`:

```json
{
  "bid_id": "PRJ-2026-SOU-XXX",
  "drawing_sources": ["B1.pdf", "B2.pdf", "B3.pdf"],
  "takeoff_method": "pdfplumber + camelot + Claude Vision",
  "schedules_extracted": {
    "column": [{"mark": "C1", "shape": "HSS10X10X1/2", "base_plate": "BP-1", "qty": 12, "page": 7}],
    "beam":   [{"mark": "B1", "shape": "W18X35", "length_ft": 30, "qty": 24}],
    "joist":  [{"mark": "J1", "size": "32LH07", "length_ft": 60, "qty": 18, "series": "LH", "depth": 32}],
    "anchor": [{"mark": "A1", "diameter_in": 0.75, "embed_in": 12, "count": 48}]
  },
  "computed": {
    "structural_tonnage": 463.2,
    "joist_tonnage": 280.1,
    "deck_sf": 231400,
    "anchor_total_count": 512,
    "bay_spacing_typ_ft": [30, 50]
  },
  "confidence": {
    "schedules": "high",
    "deck_sf": "high",
    "bay_spacing": "high",
    "stamps": "medium"
  },
  "flags": [
    {"type": "joist_series", "tag": "32LH07", "verdict": "PASS"},
    {"type": "anchor_count", "B3_moment_columns": "FLAG", "expected_per_column": 8, "actual_per_column": 4}
  ],
  "audit_trail_path": "_handoff/bid-intel/PRJ-2026-SOU-XXX/takeoff.jsonl"
}
```

The session JSONL has one line per extraction step so the audit
trail shows exactly which page, which method, which library
version produced each number. Ivan can verify any line.

## When to deflect to PlanSwift

Only when the user explicitly says "verify in PlanSwift" or "send
to PlanSwift" or asks for "third-party verification". Cowork's
takeoff is the default.

For bids over `$`2M where the cross-check spread is between 5 and
10 percent (in-tolerance but tight), offer a PlanSwift verification
run as an optional safety check. Do not force it.

## Excel report (for Ivan's review)

Use openpyxl to render `_handoff/bid-intel/<bid-id>/takeoff.xlsx`
with one sheet per schedule type plus a summary sheet. Match the
EXE-side template Ivan is used to. Save next to the JSON.
