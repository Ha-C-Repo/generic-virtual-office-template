"""F19: Multi-sheet sweep + coverage tracker.

v14 hit Frutia on 2 of ~14 pages. The structural set commonly spans
S0.x (general notes), S1.x (foundation + roof framing), S2.x (mezzanine
+ second floor), S3.x (elevations + sections), S4.x (details), plus
auxiliary sheets (deck, joist, anchor schedules).

This module:
1. Reads page text via PyMuPDF
2. Classifies each page as one of:
       - cover / index
       - general_notes (S0)
       - foundation_plan (S1)
       - framing_plan (S1, S2)
       - elevation (S3)
       - section (S3)
       - details (S4)
       - schedule (anywhere)
       - architectural (A*)
       - mep / plumbing / civil (M*, P*, C*)
3. Returns the list of pages that need vision detection.
4. Reports coverage per sheet category so auto_review can flag
   gaps ("framing plan was scanned but elevations were not").

Cheap pure-text classifier. Does not call any LLM. Fast.
"""

from __future__ import annotations
from pathlib import Path
import re


_SHEET_REGEX = re.compile(
    r"\b([SADCMPE]\-?\d+(?:\.\d+)?[A-Z]?)\b",
    re.IGNORECASE,
)
_S_SHEET_REGEX = re.compile(r"\bS\-?\d", re.IGNORECASE)


_CATEGORY_KEYWORDS = {
    "general_notes":     ["GENERAL NOTES", "STRUCTURAL NOTES", "DESIGN CRITERIA"],
    "foundation_plan":   ["FOUNDATION PLAN", "FOOTING PLAN", "SLAB PLAN"],
    "framing_plan":      ["ROOF FRAMING PLAN", "FLOOR FRAMING", "FRAMING PLAN",
                          "MEZZANINE FRAMING"],
    "elevation":         ["FRAMING ELEVATION", "STRUCTURAL ELEVATION",
                          "COLUMN ELEVATION"],
    "section":           ["BUILDING SECTION", "WALL SECTION", "STRUCTURAL SECTION"],
    "details":           ["TYPICAL DETAIL", "CONNECTION DETAIL", "FRAMING DETAIL"],
    "schedule":          ["MEMBER SCHEDULE", "COLUMN SCHEDULE", "BEAM SCHEDULE",
                          "JOIST SCHEDULE", "FOOTING SCHEDULE", "MEMBER LIST",
                          "BASE PLATE SCHEDULE", "ANCHOR ROD SCHEDULE"],
    "deck_plan":         ["ROOF DECK PLAN", "DECK PLAN", "FLOOR DECK"],
    "architectural":     ["FLOOR PLAN", "ROOF PLAN", "ELEVATIONS",
                          "ARCHITECTURAL"],
    "mep":               ["MECHANICAL", "ELECTRICAL", "PLUMBING", "HVAC"],
    "civil":             ["CIVIL", "SITE PLAN", "GRADING", "PAVING"],
}

# Categories we send to vision for member detection.
_VISION_CATEGORIES = (
    "foundation_plan", "framing_plan", "elevation", "section", "details",
    "deck_plan",
)


def _detect_sheet_id(text: str) -> str:
    """Return the structural sheet identifier if present (S1.4, S2.1, etc.)."""
    matches = _SHEET_REGEX.findall(text or "")
    for m in matches:
        if _S_SHEET_REGEX.search(m):
            return m.upper().replace("-", "")
    return ""


def _classify_page_text(text: str) -> dict:
    upper = (text or "").upper()
    cat = "unknown"
    for c, keys in _CATEGORY_KEYWORDS.items():
        if any(k in upper for k in keys):
            cat = c
            break
    sheet_id = _detect_sheet_id(upper)
    return {
        "category": cat,
        "sheet_id": sheet_id,
        "is_structural": sheet_id.startswith("S") if sheet_id else False,
        "send_to_vision": cat in _VISION_CATEGORIES,
        "is_schedule": cat == "schedule",
    }


def sweep_pdf(pdf_path: str | Path) -> dict:
    """Classify every page of pdf_path.

    Returns:
        {
            pages: [
                {page_idx, sheet_id, category, is_structural,
                 send_to_vision, is_schedule}, ...
            ],
            vision_pages: [page_idx, ...],
            schedule_pages: [page_idx, ...],
            structural_pages: [page_idx, ...],
            coverage: {
                "framing_plan": int,
                "foundation_plan": int,
                ...
            },
        }
    """
    try:
        import fitz
    except ImportError as e:
        raise RuntimeError("PyMuPDF required") from e

    doc = fitz.open(pdf_path)
    pages_meta: list[dict] = []
    vision_pages: list[int] = []
    schedule_pages: list[int] = []
    structural_pages: list[int] = []
    coverage: dict[str, int] = {}

    for i in range(len(doc)):
        text = doc[i].get_text() or ""
        cls = _classify_page_text(text)
        cls["page_idx"] = i
        pages_meta.append(cls)
        if cls["is_structural"]:
            structural_pages.append(i)
        if cls["send_to_vision"]:
            vision_pages.append(i)
        if cls["is_schedule"]:
            schedule_pages.append(i)
        coverage[cls["category"]] = coverage.get(cls["category"], 0) + 1
    doc.close()

    return {
        "pages": pages_meta,
        "vision_pages": vision_pages,
        "schedule_pages": schedule_pages,
        "structural_pages": structural_pages,
        "coverage": coverage,
    }


def required_categories_for(building_type: str) -> list[str]:
    """Categories that should be present for a complete takeoff."""
    bt = (building_type or "retail_small").lower()
    base = ["framing_plan", "schedule"]
    if bt in ("retail_small", "retail_big_box", "fitness",
              "warehouse", "dealership"):
        base.extend(["foundation_plan"])
    if bt == "office_multistory":
        base.extend(["foundation_plan", "elevation"])
    return base


def coverage_gaps(sweep: dict, building_type: str) -> list[str]:
    """List required categories that have zero pages in sweep['coverage']."""
    needed = required_categories_for(building_type)
    cov = sweep.get("coverage") or {}
    return [c for c in needed if cov.get(c, 0) == 0]
