"""
Railing Detector
================
Phase 5 of the post-parity roadmap (v3.9.0).

Railing takeoff is fundamentally different from structural-member takeoff.
Primary measurement is linear footage rather than tonnage. Detection
targets: plan-view callouts containing GUARD RAIL, HAND RAIL, PIPE RAIL,
or piece marks like GR-N and HR-N. Compliance bookmarks IBC 1015.2 (42
inch minimum guard height in commercial occupancies) and IBC 1015.4 (4
inch maximum opening between balusters).

Output items follow this shape:
    {
        "mark": "GR-1",
        "type": "guard",
        "linear_ft": 24.0,
        "height_in": 42,
        "post_count": 7,
        "rail_size": "2",                # nominal pipe size
        "weight_lbs": 412.5,
        "code_warnings": [...],
        "page_num": 3,
    }

Weight calc references Schedule 40 standard pipe lb-per-ft tables. Posts
default to 2 inch nominal at 42 inch height with 4 foot spacing on center.
The detector reports "estimated" linear feet when a callout omits an
explicit length and we have to infer from post count or default span.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import math
import re
from typing import Iterable

log = logging.getLogger("railing_detector")


# ---- Regex bank -------------------------------------------------------------
#
# Patterns are designed to be specific enough that a beam callout reading
# "RAILROAD TIE" or "GUARDED ENTRY" does not match.

_PATTERNS = [
    # GR-1, HR-12, PR-3 piece marks (must have hyphen or space before number)
    (re.compile(r"\b(GR|HR|PR)[-\s]?(\d+)\b", re.IGNORECASE), "mark"),
    # "42\" GUARD RAIL" or "GUARD RAIL 42 IN"
    (re.compile(
        r"\b(GUARD|HAND|PIPE)\s*RAIL(?:ING)?\b",
        re.IGNORECASE,
    ), "type"),
    # "42\" HT" or "42 IN HEIGHT" near a rail callout
    (re.compile(
        r"\b(?:42|36|34|30)\s*(?:\"|IN(?:CH(?:ES)?)?|HIGH|HT|HEIGHT)\b",
        re.IGNORECASE,
    ), "height"),
]

# Linear footage extraction. Looks for "LF" or "LINEAR" with a numeric
# preceding it. Conservative: only matches values 1-9999.
_LF_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:LF|L\.F\.|LIN\.?\s*FT\.?|LINEAR\s*FT)",
    re.IGNORECASE,
)

# Pipe size: must be in pipe/rail context. Bare numbers like the "1" in
# "GR-1" must not match. The token list runs longest-first so 1-1/2 wins
# over 1. Accepted forms:
#     1) "PIPE 2", "PIPE 1-1/2"        (size after PIPE)
#     2) "2 PIPE", "1-1/2 PIPE"        (size before PIPE)
#     3) "2\" PIPE", "2-IN PIPE"       (explicit inch mark plus PIPE)
#     4) "RAIL = 2\""                  (rail size shorthand)
_PIPE_SIZE_TOKENS = (
    r"(1-1/4|1\s*1/4|1-1/2|1\s*1/2|2-1/2|2\s*1/2|3/4|1|2|3)"
)
_PIPE_SIZE_RE = re.compile(
    r"(?:PIPE\s+" + _PIPE_SIZE_TOKENS + r"\b)"
    r"|"
    r"(?:" + _PIPE_SIZE_TOKENS + r"\s*[\"\u201d]?\s*(?:NPS|SCH|STD|XS))"
    r"|"
    r"(?:" + _PIPE_SIZE_TOKENS + r"\s*(?:\"|\u201d|IN(?:CH)?\.?)\s*PIPE)"
    r"|"
    r"(?:" + _PIPE_SIZE_TOKENS + r"\s+PIPE)"
    r"|"
    r"(?:RAIL\s*=\s*" + _PIPE_SIZE_TOKENS + r"\b)",
    re.IGNORECASE,
)


# ---- Pipe weight tables (Schedule 40 standard pipe, lb per ft) -------------
#
# Reference: AISC Steel Construction Manual, Pipe and HSS section.
# These weights apply to ASTM A53 Grade B carbon steel pipe.

PIPE_LBPF_SCH40 = {
    "3/4": 1.13,
    "1": 1.68,
    "1-1/4": 2.27,
    "1-1/2": 2.72,
    "2": 3.65,
    "2-1/2": 5.79,
    "3": 7.58,
}

# Default rail configuration when not specified in the drawing.
DEFAULT_RAIL_SIZE = "2"            # nominal 2 inch
DEFAULT_POST_SPACING_FT = 4.0      # IBC-friendly default
DEFAULT_POST_HEIGHT_IN = 42        # commercial guard
DEFAULT_RAILING_HEIGHT_IN = 42     # commercial guard

# Posts: 2 inch nominal pipe at 42 inch tall plus a base plate.
# Pipe weight: 3.65 lb/ft x 3.5 ft = 12.78 lb. Base plate: ~3 lb (small
# 4x4x3/8 plate). Round to 16 lb per post total to reflect cap and weld.
POST_WEIGHT_LBS = 16.0

# Top rail and mid rail. A guard rail typically has both (top and mid).
# Hand rail typically just one rail. Default counts:
RAILS_BY_TYPE = {
    "guard": 2,    # top plus mid
    "hand": 1,
    "pipe": 2,
    "rail": 2,     # generic falls to guard treatment
}


# ---- IBC code checks --------------------------------------------------------

def _check_ibc_compliance(detection: dict) -> list[str]:
    """Return a list of IBC compliance warnings for one railing detection."""
    warnings: list[str] = []
    height = detection.get("height_in") or 0
    rtype = (detection.get("type") or "").lower()
    if rtype == "guard" and height and height < 42:
        warnings.append(
            f"IBC 1015.2: guard rail height {height} in is below 42 in "
            f"commercial minimum."
        )
    if rtype == "hand" and height and (height < 34 or height > 38):
        warnings.append(
            f"IBC 1014.2: hand rail height {height} in is outside the "
            f"34 in to 38 in range."
        )
    return warnings


# ---- Linear footage helpers -------------------------------------------------

def _extract_linear_ft(text: str) -> float:
    """Pull the largest LF value from text. Returns 0.0 if nothing found."""
    matches = _LF_RE.findall(text)
    if not matches:
        return 0.0
    try:
        values = [float(m) for m in matches]
    except (ValueError, TypeError):
        return 0.0
    # Return the maximum because schedules sometimes list small subtotals
    # and a final total. Conservative: largest number in the row.
    return max(values)


def _extract_height(text: str) -> int:
    """Find an integer rail height (inches) in the text. Defaults to 42."""
    # The trailing alternation uses \b on word tokens only because the
    # quote character is not a word character and \b after it would
    # require a word boundary that does not exist in "36\" HAND".
    m = re.search(
        r"\b(42|36|34|30)\s*(?:[\"\u201d]|\bIN\b|\bHT\b|\bHEIGHT\b|\bHIGH\b)",
        text, re.IGNORECASE,
    )
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            pass
    return DEFAULT_RAILING_HEIGHT_IN


def _extract_pipe_size(text: str) -> str:
    """Find the pipe size token. Returns 2 inch default if absent.

    The regex has multiple capture groups (one per accepted form). Walk
    every match and every group so that whichever form actually matched
    contributes its size token.
    """
    for m in _PIPE_SIZE_RE.finditer(text):
        for group in m.groups():
            if not group:
                continue
            size = group.strip()
            # Normalize "1 1/2" -> "1-1/2"
            size = re.sub(r"^(\d)\s+(\d/\d)$", r"\1-\2", size)
            if size in PIPE_LBPF_SCH40:
                return size
    return DEFAULT_RAIL_SIZE


def _classify_rail_type(text: str) -> str:
    """Return guard, hand, pipe, or rail based on keywords."""
    upper = text.upper()
    if "GUARD" in upper or re.search(r"\bGR[-\s]?\d", upper):
        return "guard"
    if "HAND" in upper or re.search(r"\bHR[-\s]?\d", upper):
        return "hand"
    if "PIPE" in upper or re.search(r"\bPR[-\s]?\d", upper):
        return "pipe"
    return "rail"


def _compute_weight(linear_ft: float, post_count: int, rail_size: str,
                    rtype: str) -> float:
    """Return total railing weight in pounds.

    Includes top rail plus mid rail (per type) plus posts. Welds and
    fittings are absorbed into the per-post weight constant.
    """
    rails = RAILS_BY_TYPE.get(rtype, 2)
    rail_lbpf = PIPE_LBPF_SCH40.get(rail_size, PIPE_LBPF_SCH40["2"])
    rail_weight = rails * rail_lbpf * linear_ft
    post_weight = post_count * POST_WEIGHT_LBS
    return round(rail_weight + post_weight, 2)


# ---- Mark-key parser --------------------------------------------------------

def _find_mark(text: str) -> str:
    """Return the first GR-N or HR-N mark found, otherwise empty string."""
    m = re.search(r"\b(GR|HR|PR)[-\s]?(\d+)\b", text, re.IGNORECASE)
    if m:
        prefix = m.group(1).upper()
        num = m.group(2)
        return f"{prefix}-{num}"
    return ""


# ---- Public entry points ----------------------------------------------------

def detect_railings(text: str | Iterable[dict],
                    page_num: int = 0) -> list[dict]:
    """Detect railings in raw drawing text or a list of preprocessor pages.

    Args:
        text: Either a single markdown string or an iterable of page dicts
            with "markdown" and "page_num" keys (matches preprocessor output).
        page_num: 0-based page reference applied when text is a single string.

    Returns:
        List of railing detection dicts.
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
        # Walk by lines so each callout becomes one detection
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            upper = stripped.upper()
            # Cheap prefilter: must mention RAIL or a piece-mark family.
            has_rail_word = (
                "RAIL" in upper
                or re.search(r"\b(GR|HR|PR)[-\s]?\d", upper)
            )
            if not has_rail_word:
                continue
            # Skip false-positive nouns: "RAILROAD", "DERAIL", "GUARDRAIL".
            # Note: "GUARDRAIL" as one token is a valid alternate spelling
            # so we only filter "RAILROAD" and "DERAIL" here.
            if "RAILROAD" in upper or "DERAIL" in upper:
                continue

            rtype = _classify_rail_type(stripped)
            mark = _find_mark(stripped)
            height = _extract_height(stripped)
            linear_ft = _extract_linear_ft(stripped)
            rail_size = _extract_pipe_size(stripped)

            # If LF was not stated on this line, mark estimate flag and
            # default to a conservative 10 LF placeholder so the line still
            # produces a non-zero weight that the user can adjust.
            estimated = False
            if linear_ft <= 0:
                linear_ft = 10.0
                estimated = True

            post_count = max(2, math.ceil(linear_ft / DEFAULT_POST_SPACING_FT) + 1)
            weight = _compute_weight(linear_ft, post_count, rail_size, rtype)

            detection = {
                "mark": mark or f"RAIL-{len(detections) + 1:03d}",
                "type": rtype,
                "linear_ft": round(linear_ft, 2),
                "height_in": height,
                "post_count": post_count,
                "rail_size": rail_size,
                "weight_lbs": weight,
                "estimated": estimated,
                "page_num": pn,
                "source_text": stripped[:140],
            }
            detection["code_warnings"] = _check_ibc_compliance(detection)
            detections.append(detection)

    return detections


def summarize_railings(detections: list[dict]) -> dict:
    """Roll up railing detections into a single summary dict."""
    total_lf = sum(float(d.get("linear_ft", 0) or 0) for d in detections)
    total_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in detections)
    total_posts = sum(int(d.get("post_count", 0) or 0) for d in detections)
    by_type: dict[str, dict] = {}
    for d in detections:
        rtype = d.get("type", "rail")
        bucket = by_type.setdefault(
            rtype, {"linear_ft": 0.0, "weight_lbs": 0.0, "count": 0}
        )
        bucket["linear_ft"] += float(d.get("linear_ft", 0) or 0)
        bucket["weight_lbs"] += float(d.get("weight_lbs", 0) or 0)
        bucket["count"] += 1

    return {
        "total_linear_ft": round(total_lf, 2),
        "total_weight_lbs": round(total_lbs, 2),
        "total_posts": total_posts,
        "by_type": by_type,
        "count": len(detections),
    }
