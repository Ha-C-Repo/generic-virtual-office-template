"""
Stair Detector
==============
Phase 5 of the post-parity roadmap (v3.9.0).

Detects stair flights, stringers, treads, and landings from drawing text.
Output items follow this shape:

    {
        "mark": "STR-1",
        "flights": 1,
        "stringer_shape": "C12X20.7",
        "stringer_length_ft": 18.0,
        "tread_type": "checkered_plate",
        "tread_count": 14,
        "tread_sqft": 35.0,
        "landing_sqft": 16.0,
        "rise_in": 7.0,
        "run_in": 11.0,
        "stringer_weight_lbs": 745.2,
        "tread_weight_lbs": 446.0,
        "landing_weight_lbs": 203.5,
        "total_weight_lbs": 1394.7,
        "page_num": 5,
    }

Stringer weight is read from the AISC table via the calculators module.
Tread and landing weight use plate density (12.74 lb/sqft for 1/4 inch
checkered plate, 9.0 lb/sqft for typical bar grating) and 40.8 lb per
square foot per inch for solid plate landings.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import re
from typing import Iterable

log = logging.getLogger("stair_detector")


# ---- Pattern bank -----------------------------------------------------------

# Piece marks: STR-1, ST-12, STAIR 3.
_MARK_RE = re.compile(
    r"\b(?:STR|ST|STAIR)[-\s]?(\d+)\b",
    re.IGNORECASE,
)

# Stringer callout: "C12X20.7 STRINGER", "STRINGER C10X15.3"
_STRINGER_SHAPE_RE = re.compile(
    r"\b(C\d{1,2}\s*[X\u00d7]\s*\d{1,3}(?:\.\d+)?|"
    r"MC\d{1,2}\s*[X\u00d7]\s*\d{1,3}(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Rise/run patterns: "7/11", "7\" RISE 11\" RUN", "7 R / 11 T", "RISE=7"
_RISE_RUN_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\"|IN)?\s*[/]\s*"
    r"(\d+(?:\.\d+)?)\s*(?:\"|IN)?",
)
_RISE_RE = re.compile(
    r"\b(?:RISE|R)\s*(?:[=:]\s*)?(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_RUN_RE = re.compile(
    r"\b(?:RUN|TREAD|T)\s*(?:[=:]\s*)?(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Tread material
_CHECKERED_PLATE_RE = re.compile(
    r"\b(?:CHECKER(?:ED)?|DIAMOND)\s*(?:PL(?:ATE)?|PLT)\b",
    re.IGNORECASE,
)
_BAR_GRATING_RE = re.compile(
    r"\bBAR\s*GRAT(?:ING|E)?\b",
    re.IGNORECASE,
)

# Stringer length: "STRINGER 18 FT", "L = 18'-0\""
_LENGTH_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:FT|FEET|'|FT\.?\s*0?\")",
    re.IGNORECASE,
)

# Tread count: "14 TREADS", "(14) TREADS"
_TREAD_COUNT_RE = re.compile(
    r"\(?(\d+)\)?\s*TREADS?",
    re.IGNORECASE,
)

# Landing area: "LANDING 4'-0\" X 4'-0\"", "LANDING = 16 SF"
_LANDING_SF_RE = re.compile(
    r"LANDING.*?(\d+(?:\.\d+)?)\s*(?:SQ\s*FT|SF|SQFT)",
    re.IGNORECASE,
)
_LANDING_DIM_RE = re.compile(
    r"LANDING.*?(\d+(?:\.\d+)?)\s*(?:'|FT|FEET).*?[X\u00d7].*?"
    r"(\d+(?:\.\d+)?)\s*(?:'|FT|FEET)",
    re.IGNORECASE,
)


# ---- Material weight tables -------------------------------------------------

# 1/4 inch (0.250 in) checkered plate weighs 12.74 lb/sqft including the
# raised pattern. 3/8 inch checkered plate weighs 17.86 lb/sqft. Bar grating
# at 1-1/4 x 3/16 bearing bars weighs about 9.0 lb/sqft. Solid plate
# landings at 1/4 inch weigh 10.2 lb/sqft (smooth plate, no pattern).

CHECKERED_PLATE_LBS_PER_SF = {
    "1/4": 12.74,
    "3/8": 17.86,
    "1/2": 22.98,
}
BAR_GRATING_LBS_PER_SF = 9.0
SMOOTH_PLATE_LBS_PER_SF_PER_IN = 40.8   # also stored in calculators rates

DEFAULT_TREAD_DEPTH_IN = 11.0   # standard run
DEFAULT_TREAD_WIDTH_IN = 36.0   # standard 3 ft wide stair
DEFAULT_TREAD_PLATE_THICKNESS = "1/4"
DEFAULT_LANDING_THICKNESS_IN = 0.25
DEFAULT_LANDING_SF = 16.0       # 4 ft x 4 ft
DEFAULT_STRINGER_SHAPE = "C12X20.7"
DEFAULT_STRINGER_LENGTH_FT = 12.0
DEFAULT_RISE_IN = 7.0
DEFAULT_RUN_IN = 11.0


# ---- Helpers ----------------------------------------------------------------

def _normalize_shape(shape: str) -> str:
    """Normalize a stringer shape token: collapse whitespace, uppercase X."""
    s = shape.upper().replace("\u00d7", "X").strip()
    s = re.sub(r"\s+", "", s)
    return s


def _stringer_lbpf(shape: str) -> float:
    """Look up stringer weight per foot via the calculators shape table."""
    try:
        from bridge.calculators import shapes as _shapes
        db = _shapes()
        return float(db.get(shape, 0.0) or 0.0)
    except Exception:
        return 0.0


def _extract_rise_run(text: str) -> tuple[float, float]:
    """Extract rise and run in inches. Returns defaults if not found."""
    m = _RISE_RUN_RE.search(text)
    if m:
        try:
            rise = float(m.group(1))
            run = float(m.group(2))
            # Rise must be smaller than run for a real stair. Sanity check:
            # both must be in the residential or commercial range.
            if 4.0 <= rise <= 9.0 and 9.0 <= run <= 14.0:
                return rise, run
        except (ValueError, TypeError):
            pass

    rise = DEFAULT_RISE_IN
    run = DEFAULT_RUN_IN
    rm = _RISE_RE.search(text)
    if rm:
        try:
            v = float(rm.group(1))
            if 4.0 <= v <= 9.0:
                rise = v
        except (ValueError, TypeError):
            pass
    rn = _RUN_RE.search(text)
    if rn:
        try:
            v = float(rn.group(1))
            if 9.0 <= v <= 14.0:
                run = v
        except (ValueError, TypeError):
            pass
    return rise, run


def _extract_stringer_length(text: str) -> float:
    """Pull the largest reasonable stringer length in feet."""
    matches = _LENGTH_RE.findall(text)
    candidates = []
    for m in matches:
        try:
            v = float(m)
            # Stringers are realistically 4-30 feet long
            if 4.0 <= v <= 30.0:
                candidates.append(v)
        except (ValueError, TypeError):
            continue
    if candidates:
        return max(candidates)
    return DEFAULT_STRINGER_LENGTH_FT


def _extract_tread_count(text: str) -> int:
    """Find the tread count if explicitly stated, otherwise 0."""
    m = _TREAD_COUNT_RE.search(text)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            return 0
    return 0


def _extract_landing_sqft(text: str) -> float:
    """Find an explicit landing area in square feet."""
    m = _LANDING_SF_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            pass
    md = _LANDING_DIM_RE.search(text)
    if md:
        try:
            w = float(md.group(1))
            l = float(md.group(2))
            return round(w * l, 2)
        except (ValueError, TypeError):
            pass
    return 0.0


def _classify_tread(text: str) -> str:
    """Return checkered_plate or bar_grating based on keywords."""
    if _BAR_GRATING_RE.search(text):
        return "bar_grating"
    if _CHECKERED_PLATE_RE.search(text):
        return "checkered_plate"
    # Default for industrial stairs
    return "checkered_plate"


def _tread_weight(tread_count: int, tread_type: str,
                  tread_width_in: float = DEFAULT_TREAD_WIDTH_IN,
                  tread_depth_in: float = DEFAULT_TREAD_DEPTH_IN) -> float:
    """Calculate total tread weight."""
    sf_per_tread = (tread_width_in * tread_depth_in) / 144.0
    total_sf = sf_per_tread * max(tread_count, 0)
    if tread_type == "bar_grating":
        return round(total_sf * BAR_GRATING_LBS_PER_SF, 2)
    lbs_per_sf = CHECKERED_PLATE_LBS_PER_SF[DEFAULT_TREAD_PLATE_THICKNESS]
    return round(total_sf * lbs_per_sf, 2)


def _landing_weight(sqft: float,
                    thickness_in: float = DEFAULT_LANDING_THICKNESS_IN) -> float:
    """Calculate landing weight using smooth plate density."""
    return round(sqft * thickness_in * SMOOTH_PLATE_LBS_PER_SF_PER_IN, 2)


# ---- Public entry points ----------------------------------------------------

def detect_stairs(text: str | Iterable[dict],
                  page_num: int = 0) -> list[dict]:
    """Detect stair flights in drawing text.

    Args:
        text: Markdown string or iterable of preprocessor page dicts.
        page_num: Page reference applied when text is a single string.

    Returns:
        List of stair flight dicts.
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
        upper = body.upper()
        # Quick reject: must mention STAIR or a STR mark or a stringer shape
        has_stair_signal = (
            "STAIR" in upper
            or re.search(r"\bSTR[-\s]?\d", upper)
            or _STRINGER_SHAPE_RE.search(body)
        )
        if not has_stair_signal:
            continue

        # Walk by lines so each STAIR callout produces one detection
        seen_marks: set[str] = set()
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            line_upper = stripped.upper()
            if not (
                "STAIR" in line_upper
                or re.search(r"\bSTR[-\s]?\d", line_upper)
                or _STRINGER_SHAPE_RE.search(stripped)
            ):
                continue
            # Skip pure prose like "STAIRS SHALL CONFORM TO IBC"
            if "SHALL" in line_upper or "PER " in line_upper or \
               "CONFORM" in line_upper:
                continue

            mark_match = _MARK_RE.search(stripped)
            if mark_match:
                mark = f"STR-{mark_match.group(1)}"
            else:
                mark = f"STR-{len(detections) + 1:03d}"

            if mark in seen_marks:
                continue
            seen_marks.add(mark)

            # Stringer shape
            sh = _STRINGER_SHAPE_RE.search(stripped)
            stringer_shape = (
                _normalize_shape(sh.group(1)) if sh else DEFAULT_STRINGER_SHAPE
            )

            # Length, rise/run, tread count, landing
            length_ft = _extract_stringer_length(stripped)
            rise_in, run_in = _extract_rise_run(stripped)
            tread_count = _extract_tread_count(stripped)
            if tread_count <= 0 and rise_in > 0:
                # Estimate from rise total height. Default flight height
                # is 10 feet (120 inches) for one-story stairs.
                estimated_treads = int(round(120.0 / rise_in)) - 1
                tread_count = max(estimated_treads, 1)
            landing_sf = _extract_landing_sqft(stripped)
            if landing_sf <= 0:
                landing_sf = DEFAULT_LANDING_SF

            tread_type = _classify_tread(stripped)

            # Compute weights
            stringer_lbpf = _stringer_lbpf(stringer_shape)
            stringer_weight = round(
                stringer_lbpf * length_ft * 2.0, 2  # 2 stringers per flight
            )
            tread_weight = _tread_weight(tread_count, tread_type)
            landing_weight = _landing_weight(landing_sf)

            detection = {
                "mark": mark,
                "flights": 1,
                "stringer_shape": stringer_shape,
                "stringer_length_ft": length_ft,
                "stringer_count": 2,
                "tread_type": tread_type,
                "tread_count": tread_count,
                "tread_sqft": round(
                    tread_count * (DEFAULT_TREAD_WIDTH_IN
                                   * DEFAULT_TREAD_DEPTH_IN) / 144.0, 2
                ),
                "landing_sqft": round(landing_sf, 2),
                "rise_in": rise_in,
                "run_in": run_in,
                "stringer_weight_lbs": stringer_weight,
                "tread_weight_lbs": tread_weight,
                "landing_weight_lbs": landing_weight,
                "total_weight_lbs": round(
                    stringer_weight + tread_weight + landing_weight, 2
                ),
                "page_num": pn,
                "source_text": stripped[:140],
                "warnings": [],
            }

            # Stringer shape validation. If the shape is not in AISC, warn.
            if stringer_lbpf <= 0:
                detection["warnings"].append(
                    f"Stringer shape {stringer_shape} not found in AISC "
                    f"weight table. Verify and edit if needed."
                )

            detections.append(detection)

    return detections


def summarize_stairs(detections: list[dict]) -> dict:
    """Roll up stair detections into a single summary dict."""
    total_flights = sum(int(d.get("flights", 0) or 0) for d in detections)
    total_treads = sum(int(d.get("tread_count", 0) or 0) for d in detections)
    total_lbs = sum(
        float(d.get("total_weight_lbs", 0) or 0) for d in detections
    )
    total_landing_sf = sum(
        float(d.get("landing_sqft", 0) or 0) for d in detections
    )
    return {
        "flights": total_flights,
        "treads": total_treads,
        "landing_sqft": round(total_landing_sf, 2),
        "total_weight_lbs": round(total_lbs, 2),
        "count": len(detections),
    }
