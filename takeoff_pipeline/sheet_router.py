"""T1 sheet router: PyMuPDF title-block parse and sheet classification.

Classifies sheets by sheet-number prefix per the spike prompt:
  S0.x  GENERAL_NOTES
  S1.x  FOUNDATION
  S2.x  FRAMING
  S3.x and up  DETAILS

The numeric scheme is the rule; real sets sometimes number differently
(South Park 183 puts general notes on S1.00), so the router also records
a title_hint derived from the sheet title. Consumers that need the
drawing's actual content category (census primary_source strings) use
the title; the numeric category is reported alongside, never silently
overridden.

Scanned (non-vector) sheets are detected by text-object count and routed
to a SCANNED list. Census work STOPS for those sheets here. The locked
4x rasterization procedure handles scanned sets and is NOT reimplemented
in this package.

No pricing anywhere (P25). Standalone: no bridge/ imports.
"""

import re
from pathlib import Path

# Below this many text words a sheet is treated as scanned/non-vector.
# Vector CAD exports carry hundreds of text objects; a scanned raster
# page carries none (or a handful of OCR artifacts). The leanest real
# vector sheet observed on the SP183 B1 set carries 116 words.
SCANNED_TEXT_THRESHOLD = 25

CATEGORY_GENERAL_NOTES = "GENERAL_NOTES"
CATEGORY_FOUNDATION = "FOUNDATION"
CATEGORY_FRAMING = "FRAMING"
CATEGORY_DETAILS = "DETAILS"
CATEGORY_UNKNOWN = "UNKNOWN"

_SHEET_ID = re.compile(r"^[A-Z]{1,2}\d{1,2}\.\d{1,2}[A-Z]?$")
_S_PREFIX = re.compile(r"^S(\d{1,2})\.", re.IGNORECASE)

_STAGE_PATTERNS = (
    "ISSUE FOR PRICING",
    "ISSUED FOR PRICING",
    "ISSUED FOR CONSTRUCTION",
    "ISSUE FOR CONSTRUCTION",
    "ISSUED FOR PERMIT",
    "ISSUE FOR PERMIT",
    "DESIGN DEVELOPMENT",
    "SCHEMATIC DESIGN",
    "FOR REVIEW",
    "NOT FOR CONSTRUCTION",
)


def classify_sheet_number(sheet_number: str) -> str:
    """Numeric classification per the spike prompt scheme."""
    if not sheet_number:
        return CATEGORY_UNKNOWN
    m = _S_PREFIX.match(sheet_number.strip())
    if not m:
        return CATEGORY_UNKNOWN
    major = int(m.group(1))
    if major == 0:
        return CATEGORY_GENERAL_NOTES
    if major == 1:
        return CATEGORY_FOUNDATION
    if major == 2:
        return CATEGORY_FRAMING
    return CATEGORY_DETAILS


def title_category_hint(title: str) -> str:
    """Category suggested by the sheet TITLE text. Recorded beside the
    numeric category, never silently substituted for it."""
    t = (title or "").upper()
    if not t:
        return CATEGORY_UNKNOWN
    if "GENERAL" in t and "NOTE" in t:
        return CATEGORY_GENERAL_NOTES
    if "FOUNDATION" in t and "PLAN" in t:
        return CATEGORY_FOUNDATION
    if "FRAMING" in t and "PLAN" in t:
        return CATEGORY_FRAMING
    if "DETAIL" in t or "SECTION" in t or "SCHEDULE" in t \
            or "ELEVATION" in t:
        return CATEGORY_DETAILS
    return CATEGORY_UNKNOWN


def is_scanned(word_count: int) -> bool:
    return word_count < SCANNED_TEXT_THRESHOLD


def _label_position(words, first: str, second: str):
    """Locate a two-word label like SHEET NUMBER / SHEET NAME. Returns
    the (x0, y0) of the first word, or None."""
    for w in words:
        if w[4].upper() != first:
            continue
        for v in words:
            if v[4].upper() != second:
                continue
            if abs(v[1] - w[1]) <= 4 and 0 < v[0] - w[0] <= 90:
                return (w[0], w[1])
    return None


def parse_title_block(page) -> dict:
    """Parse sheet number, sheet title, and issue stage from one page.

    Strategy: the value sits just below its label in the title block
    (SHEET NUMBER label, then the id; SHEET NAME label, then the title).
    Fallback for the number: the bottom-most sheet-id token in the right
    strip of the page. All coordinates are PyMuPDF points, top origin.
    """
    words = page.get_text("words")
    rect = page.rect
    ids = [w for w in words if _SHEET_ID.match(w[4].upper())]

    sheet_number = ""
    num_label = _label_position(words, "SHEET", "NUMBER")
    if num_label:
        lx, ly = num_label
        below = [w for w in ids
                 if 0 < w[1] - ly <= 150 and abs(w[0] - lx) <= 200]
        if below:
            below.sort(key=lambda w: w[1] - ly)
            sheet_number = below[0][4].upper()
    if not sheet_number:
        strip = [w for w in ids
                 if w[0] > rect.width * 0.82 and w[1] > rect.height * 0.5]
        if strip:
            strip.sort(key=lambda w: (-w[1], -w[0]))
            sheet_number = strip[0][4].upper()

    sheet_title = ""
    name_label = _label_position(words, "SHEET", "NAME")
    if name_label:
        lx, ly = name_label
        band = [w for w in words
                if 6 < w[1] - ly <= 60 and lx - 40 <= w[0] <= lx + 460
                and not _SHEET_ID.match(w[4].upper())]
        band.sort(key=lambda w: (round(w[1]), w[0]))
        sheet_title = " ".join(w[4] for w in band).strip()

    # Revision tables list the full issue history, so a sheet can carry
    # SEVERAL stage strings (this set carries ISSUE FOR PERMIT and
    # ISSUE FOR PRICING on every content sheet). All matches are
    # returned; "stage" is the first in pattern order, NOT necessarily
    # the current issue. Consumers that care about currency must look
    # at the full list.
    upper_text = page.get_text().upper()
    stages = [pat for pat in _STAGE_PATTERNS if pat in upper_text]

    return {
        "sheet_number": sheet_number,
        "sheet_title": sheet_title,
        "stage": stages[0] if stages else "",
        "stages": stages,
        "word_count": len(words),
    }


def route(pdf_path) -> dict:
    """Route every page of a drawing set.

    Returns {"pdf": str, "sheets": [...], "scanned": [...]} where each
    sheet dict carries page_index, sheet_number, sheet_title, category
    (numeric scheme), title_hint, stage, word_count, is_scanned.
    Scanned pages appear in both lists; census and scale work must skip
    them (the locked 4x rasterization procedure owns scanned sets).
    """
    import fitz

    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    sheets = []
    scanned = []
    try:
        for i, page in enumerate(doc):
            tb = parse_title_block(page)
            entry = {
                "page_index": i,
                "sheet_number": tb["sheet_number"],
                "sheet_title": tb["sheet_title"],
                "category": classify_sheet_number(tb["sheet_number"]),
                "title_hint": title_category_hint(tb["sheet_title"]),
                "stage": tb["stage"],
                "stages": tb["stages"],
                "word_count": tb["word_count"],
                "is_scanned": is_scanned(tb["word_count"]),
            }
            sheets.append(entry)
            if entry["is_scanned"]:
                scanned.append(entry)
    finally:
        doc.close()
    return {"pdf": str(pdf_path), "sheets": sheets, "scanned": scanned}
