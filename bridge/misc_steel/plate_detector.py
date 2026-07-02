"""
Plate Detector
==============
Phase 5 of the post-parity roadmap (v3.9.0).

Detects connection and base plates from drawing text. Plates are not in
the AISC shape database (PL is generic, not a fixed cross section), so
weight is computed from physical dimensions and steel density.

Output items follow this shape:

    {
        "mark": "BP-1",
        "type": "base_plate",
        "thickness_in": 0.75,
        "width_in": 12.0,
        "length_in": 18.0,
        "qty": 4,
        "weight_lbs": 220.7,
        "page_num": 6,
        "warnings": [...],
    }

Thickness can arrive as a fraction (3/4), a decimal (.75), or a mixed
fraction (1-1/2). All three forms are normalized.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import re
from typing import Iterable

log = logging.getLogger("plate_detector")


# ---- Pattern bank -----------------------------------------------------------
#
# Plate callout: PL 3/4 X 12 X 18, PL 3/4" X 12" X 18", PL .500 X 12 X 18
#
# Capture groups: (1) thickness, (2) width, (3) length.
# Three dimension forms accepted:
#   * mixed fraction: 1-1/2, 1 1/2, 3/4
#   * leading-decimal: .500, .25
#   * decimal or whole: 0.75, 12, 18, 1.25

_DIM = (
    r"(\d+\s*-\s*\d+/\d+"          # 1-1/2
    r"|\d+\s+\d+/\d+"              # 1 1/2
    r"|\d+/\d+"                    # 3/4
    r"|\.\d+"                      # .500
    r"|\d+\.\d+"                   # 0.75
    r"|\d+)"                       # 12
)
_PLATE_RE = re.compile(
    r"\bPL\s*"
    + _DIM + r"\s*[\"\u201d]?\s*[X\u00d7]\s*"
    + _DIM + r"\s*[\"\u201d]?\s*[X\u00d7]\s*"
    + _DIM + r"\s*[\"\u201d]?",
    re.IGNORECASE,
)

# Piece marks: BP-1 (base plate), GP-1 (gusset), SP-1 (stiffener), ST-1
_MARK_RE = re.compile(
    r"\b(BP|GP|SP|SHP|CP|TP)\s*-?\s*(\d+)\b",
    re.IGNORECASE,
)

# Type indicators
_BASE_PLATE_RE = re.compile(r"\bBASE\s*(?:PL(?:ATE)?|PLT)\b", re.IGNORECASE)
_GUSSET_RE = re.compile(r"\bGUSSET\s*(?:PL(?:ATE)?|PLT)?\b", re.IGNORECASE)
_STIFFENER_RE = re.compile(r"\bSTIFF(?:ENER)?\s*(?:PL(?:ATE)?|PLT)?\b", re.IGNORECASE)
_SHEAR_TAB_RE = re.compile(
    r"\b(?:SHEAR\s*TAB|SHEAR\s*PL(?:ATE)?|S\.?T\.?)\b",
    re.IGNORECASE,
)
_CAP_PLATE_RE = re.compile(r"\bCAP\s*(?:PL(?:ATE)?|PLT)\b", re.IGNORECASE)

# Quantity
_QTY_PAREN_RE = re.compile(r"\((\d+)\)\s*PL", re.IGNORECASE)
_QTY_EA_RE = re.compile(
    r"(\d+)\s*(?:EA|EACH|TOTAL|REQD)",
    re.IGNORECASE,
)


# Plate density: 0.283 lb/in3 for ASTM A36 carbon steel.
STEEL_DENSITY_LBS_PER_IN3 = 0.283


# ---- Helpers ----------------------------------------------------------------

def _parse_dim(token: str) -> float:
    """Convert a dimension token into inches.

    Accepts:
        - decimals: ".500", "0.75", "12", "1.25"
        - simple fractions: "3/4", "1/2", "3/8"
        - mixed fractions: "1-1/2", "1 1/2", "2-3/4"
        - feet markers are NOT supported here (callers must strip them)
    """
    if token is None:
        return 0.0
    t = re.sub(r"\s+", "", token).strip()
    if not t:
        return 0.0
    # Mixed fraction with hyphen: 1-1/2
    m = re.match(r"^(\d+)-(\d+)/(\d+)$", t)
    if m:
        try:
            whole = int(m.group(1))
            num = int(m.group(2))
            den = int(m.group(3))
            if den == 0:
                return 0.0
            return whole + (num / den)
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0
    # Simple fraction: 3/4
    m = re.match(r"^(\d+)/(\d+)$", t)
    if m:
        try:
            num = int(m.group(1))
            den = int(m.group(2))
            if den == 0:
                return 0.0
            return num / den
        except (ValueError, TypeError, ZeroDivisionError):
            return 0.0
    # Decimal or whole number
    try:
        return float(t)
    except (ValueError, TypeError):
        return 0.0


def _classify_plate_type(text: str, mark_prefix: str = "") -> str:
    """Return base_plate, gusset, stiffener, shear_tab, cap_plate, or plate."""
    if _BASE_PLATE_RE.search(text) or mark_prefix == "BP":
        return "base_plate"
    if _GUSSET_RE.search(text) or mark_prefix == "GP":
        return "gusset"
    if _STIFFENER_RE.search(text) or mark_prefix == "SP":
        return "stiffener"
    if _SHEAR_TAB_RE.search(text) or mark_prefix in ("SHP", "TP"):
        return "shear_tab"
    if _CAP_PLATE_RE.search(text) or mark_prefix == "CP":
        return "cap_plate"
    return "plate"


def _extract_qty(text: str) -> int:
    """Extract plate quantity."""
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
    return 1


def _plate_weight(thickness_in: float, width_in: float,
                  length_in: float, qty: int = 1) -> float:
    """Plate weight in pounds. thickness * width * length * density * qty."""
    if thickness_in <= 0 or width_in <= 0 or length_in <= 0:
        return 0.0
    volume_in3 = thickness_in * width_in * length_in
    return round(volume_in3 * STEEL_DENSITY_LBS_PER_IN3 * qty, 2)


# ---- Public entry points ----------------------------------------------------

def detect_plates(text: str | Iterable[dict],
                  page_num: int = 0) -> list[dict]:
    """Detect plates in drawing text.

    Args:
        text: Markdown string or iterable of preprocessor page dicts.
        page_num: Page reference applied when text is a single string.

    Returns:
        List of plate detection dicts.
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
        # Cheap prefilter
        if "PL" not in body.upper():
            continue

        # Collect all plate dimension matches with their position for context
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Quick reject: avoid lines about "PLAN", "PLATFORM" without PL dim
            for m in _PLATE_RE.finditer(stripped):
                t_token = m.group(1)
                w_token = m.group(2)
                l_token = m.group(3)

                thickness = _parse_dim(t_token)
                width = _parse_dim(w_token)
                length = _parse_dim(l_token)

                # Sanity check: reject obviously wrong dimensions.
                # Thickness 0.125-4 in, width 1-72 in, length 1-240 in.
                if not (0.0625 <= thickness <= 4.0):
                    continue
                if not (1.0 <= width <= 72.0):
                    continue
                if not (1.0 <= length <= 240.0):
                    continue

                mark_match = _MARK_RE.search(stripped)
                if mark_match:
                    mark_prefix = mark_match.group(1).upper()
                    mark_num = mark_match.group(2)
                    mark = f"{mark_prefix}-{mark_num}"
                else:
                    mark_prefix = ""
                    mark = f"PL-{len(detections) + 1:03d}"

                ptype = _classify_plate_type(stripped, mark_prefix)
                qty = _extract_qty(stripped)
                weight = _plate_weight(thickness, width, length, qty)

                warnings: list[str] = []
                if weight <= 0:
                    warnings.append(
                        "Plate weight computed as zero. Verify dimensions."
                    )

                detections.append({
                    "mark": mark,
                    "type": ptype,
                    "thickness_in": round(thickness, 4),
                    "width_in": round(width, 2),
                    "length_in": round(length, 2),
                    "qty": qty,
                    "weight_lbs": weight,
                    "page_num": pn,
                    "source_text": stripped[:140],
                    "warnings": warnings,
                })

    return detections


def summarize_plates(detections: list[dict]) -> dict:
    """Roll up plate detections."""
    total_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in detections)
    total_qty = sum(int(d.get("qty", 0) or 0) for d in detections)
    by_type: dict[str, dict] = {}
    for d in detections:
        ptype = d.get("type", "plate")
        bucket = by_type.setdefault(
            ptype, {"count": 0, "weight_lbs": 0.0, "qty": 0}
        )
        bucket["count"] += 1
        bucket["weight_lbs"] += float(d.get("weight_lbs", 0) or 0)
        bucket["qty"] += int(d.get("qty", 0) or 0)
    return {
        "count": len(detections),
        "total_qty": total_qty,
        "total_weight_lbs": round(total_lbs, 2),
        "by_type": by_type,
    }
