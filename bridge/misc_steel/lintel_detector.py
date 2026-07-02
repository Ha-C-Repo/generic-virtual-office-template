"""
Lintel Detector
===============
Phase 5 of the post-parity roadmap (v3.9.0).

Detects lintels (horizontal members spanning door, window, or other wall
openings) from drawing text. Typical lintel shapes are L-angles, double
angles, WT cuts, and small W-shapes. Each detected lintel goes through
the AISC validator the same way structural members do, so any shape that
makes it into the bid is real.

Output items follow this shape:

    {
        "mark": "L-1",
        "shape": "L4X4X1/4",
        "qty": 4,
        "span_ft": 6.5,
        "weight_lbs": 165.1,
        "lb_per_ft": 6.6,
        "page_num": 4,
        "aisc_valid": true,
        "warnings": [...],
    }

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import re
from typing import Iterable

log = logging.getLogger("lintel_detector")


# ---- Pattern bank -----------------------------------------------------------
#
# Lintel piece marks: L-1, LTL-2, LIN-3.

_MARK_RE = re.compile(
    r"\b(?:LTL|LIN|LNTL|L)\s*-\s*(\d+)\b",
    re.IGNORECASE,
)

# Lintel callout phrases. Must say LINTEL or HEADER explicitly.
_LINTEL_KEYWORDS = re.compile(
    r"\b(?:LINTEL|HEADER|LTL)\b",
    re.IGNORECASE,
)

# Shape patterns for lintels: angles (L4X4X1/4), double angles (2L3X3X1/4),
# WT cuts (WT5X11), and small W-shapes (W6X9).
_SHAPE_RE = re.compile(
    r"\b(?:"
    r"(?:2L|L)\s*\d{1,2}\s*[X\u00d7]\s*\d{1,2}\s*[X\u00d7]\s*"
    r"(?:\d{1,3}/\d{1,3}|\d+(?:\.\d+)?)"
    r"|"
    r"WT\s*\d{1,2}\s*[X\u00d7]\s*\d{1,3}(?:\.\d+)?"
    r"|"
    r"W\s*\d{1,2}\s*[X\u00d7]\s*\d{1,3}(?:\.\d+)?"
    r"|"
    r"C\s*\d{1,2}\s*[X\u00d7]\s*\d{1,3}(?:\.\d+)?"
    r")\b",
    re.IGNORECASE,
)

# Span: "6'-6\"", "6.5 FT", "SPAN = 6'-6\""
_SPAN_RE = re.compile(
    r"(\d+)\s*[\u2019']\s*-?\s*(\d+(?:\.\d+)?)?\s*[\"\u201d]?",
)
_SPAN_FT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:FT|FEET|F\.)",
    re.IGNORECASE,
)

# Quantity: "(4) L4X4X1/4", "QTY 4", "4 EA"
_QTY_PAREN_RE = re.compile(r"\((\d+)\)")
_QTY_EA_RE = re.compile(
    r"(\d+)\s*(?:EA|EACH|QTY|TOTAL)",
    re.IGNORECASE,
)

DEFAULT_LINTEL_SHAPE = "L4X4X1/4"
DEFAULT_LINTEL_SPAN_FT = 6.0
DEFAULT_LINTEL_QTY = 1


# ---- Helpers ----------------------------------------------------------------

def _normalize_shape(shape: str) -> str:
    """Normalize a lintel shape token: collapse whitespace, uppercase X."""
    s = shape.upper().replace("\u00d7", "X").strip()
    s = re.sub(r"\s+", "", s)
    return s


def _validate_shape(shape: str) -> tuple[bool, float]:
    """Return (is_valid, lb_per_ft) using AISC validator + calculator."""
    try:
        from bridge.aisc_validator import validate_shape
        vr = validate_shape(shape)
        is_valid = bool(vr.get("valid", False))
    except Exception:
        is_valid = False
    try:
        from bridge.calculators import shapes as _shapes
        db = _shapes()
        lbpf = float(db.get(shape, 0.0) or 0.0)
    except Exception:
        lbpf = 0.0
    return is_valid, lbpf


def _extract_span_ft(text: str) -> float:
    """Extract a lintel span in feet. Returns default if unfound."""
    # Try foot-inch notation first
    m = _SPAN_RE.search(text)
    if m:
        try:
            ft = int(m.group(1))
            inches_raw = m.group(2)
            inches = float(inches_raw) if inches_raw else 0.0
            if 1 <= ft <= 30:
                return round(ft + inches / 12.0, 2)
        except (ValueError, TypeError):
            pass
    # Decimal feet fallback
    m2 = _SPAN_FT_RE.search(text)
    if m2:
        try:
            v = float(m2.group(1))
            if 1.0 <= v <= 30.0:
                return v
        except (ValueError, TypeError):
            pass
    return DEFAULT_LINTEL_SPAN_FT


def _extract_qty(text: str) -> int:
    """Extract quantity. Looks for (N), N EA, N TOTAL, etc."""
    m = _QTY_PAREN_RE.search(text)
    if m:
        try:
            return max(int(m.group(1)), 1)
        except (ValueError, TypeError):
            pass
    m2 = _QTY_EA_RE.search(text)
    if m2:
        try:
            return max(int(m2.group(1)), 1)
        except (ValueError, TypeError):
            pass
    return DEFAULT_LINTEL_QTY


# ---- Public entry points ----------------------------------------------------

def detect_lintels(text: str | Iterable[dict],
                   page_num: int = 0) -> list[dict]:
    """Detect lintels in drawing text.

    Args:
        text: Markdown string or iterable of preprocessor page dicts.
        page_num: Page reference applied when text is a single string.

    Returns:
        List of lintel detection dicts.
    """
    detections: list[dict] = []

    pages: list[tuple[int, str]] = []
    if isinstance(text, str):
        pages.append((page_num, text))
    else:
        for p in text:
            if not isinstance(p, dict):
                continue
            md = p.get("markdown", "") or p.get("text", "") or ""
            pn = int(p.get("page_num", 0) or 0)
            pages.append((pn, md))

    for pn, body in pages:
        if not body:
            continue
        if not _LINTEL_KEYWORDS.search(body):
            continue

        seen_marks: set[str] = set()
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if not _LINTEL_KEYWORDS.search(stripped):
                continue
            # Skip generic specification text
            line_upper = stripped.upper()
            if "SHALL" in line_upper or "TYPICAL" in line_upper:
                # Allow if a shape AND a span are present (a real callout),
                # otherwise it is prose.
                if not (_SHAPE_RE.search(stripped) and _SPAN_RE.search(stripped)):
                    continue

            mark_match = _MARK_RE.search(stripped)
            if mark_match:
                mark = f"L-{mark_match.group(1)}"
            else:
                mark = f"L-{len(detections) + 1:03d}"
            if mark in seen_marks:
                continue
            seen_marks.add(mark)

            sh = _SHAPE_RE.search(stripped)
            shape = _normalize_shape(sh.group(0)) if sh else DEFAULT_LINTEL_SHAPE
            span = _extract_span_ft(stripped)
            qty = _extract_qty(stripped)

            is_valid, lbpf = _validate_shape(shape)
            weight = round(lbpf * span * qty, 2) if lbpf > 0 else 0.0

            warnings: list[str] = []
            if not is_valid:
                warnings.append(
                    f"Lintel shape {shape} not in AISC v16.0. "
                    f"Verify and edit if needed."
                )
            if lbpf <= 0 and is_valid:
                warnings.append(
                    f"Lintel shape {shape} has no lb/ft entry. Weight set "
                    f"to 0. Update aisc_master.csv or correct the shape."
                )

            detections.append({
                "mark": mark,
                "shape": shape,
                "qty": qty,
                "span_ft": span,
                "lb_per_ft": round(lbpf, 3),
                "weight_lbs": weight,
                "page_num": pn,
                "aisc_valid": is_valid,
                "source_text": stripped[:140],
                "warnings": warnings,
            })

    return detections


def summarize_lintels(detections: list[dict]) -> dict:
    """Roll up lintel detections."""
    total_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in detections)
    total_qty = sum(int(d.get("qty", 0) or 0) for d in detections)
    valid_count = sum(1 for d in detections if d.get("aisc_valid"))
    return {
        "count": len(detections),
        "total_qty": total_qty,
        "valid_count": valid_count,
        "total_weight_lbs": round(total_lbs, 2),
    }
