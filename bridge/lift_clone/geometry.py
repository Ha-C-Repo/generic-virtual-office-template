"""
Your Company Virtual Office - Coordinate Frame + Member Placement (lift_clone)
===========================================================================
Slice 1 of the 3D-coordinate-extraction plan
(.specify/specs/bid-estimating/3d-coordinate-extraction-plan.md).

The takeoff (takeoff.py) reads marks + AISC shapes from sheet TEXT but holds
NO spatial information. This module adds the missing geometry so Your Company can
build its OWN estimate-grade structural model in-house: a column-grid STL for a
page-1 viewport when no Tekla export exists yet, and a visual QC cross-check on
every bid.

Two things the drawings hold separately:
  - A COORDINATE FRAME: the column grid (numbers 1,2,3 along X, letters A,B,C
    along Y) plus the bay dimensions give X/Y. Level datums on elevations and
    sections (T.O. Slab, T.O. Steel, roof) give Z.
  - MEMBER PLACEMENT: each member's endpoints expressed against that frame. A
    column sits at a grid intersection and runs base elevation to top.

The single new artifact is ``coordinate_members.json`` - a SUPERSET of today's
BOM. It is additive. It NEVER changes the validated tonnage, the AISC weights,
or any rate. Tekla Structures remains the fabrication system of record; this
model is estimate-grade, for visualization and QC only.

Verify, don't generate (constitution): every coordinate carries a confidence
tag (high/medium/low). Low-confidence items are flagged needs_review and never
fed silently into anything that ships. When the vector data cannot be read
(scanned or dirty sets) the extractor flags for human entry rather than
inventing a grid.

No new dependency: vector parsing uses PyMuPDF (fitz), already in the stack.
The optional vision fallback reuses whatever multimodal call path the bridge
already exposes; if none is available it returns a flagged human-entry result.
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── confidence ladder ────────────────────────────────────────────────
HIGH, MEDIUM, LOW = "high", "medium", "low"
_RANK = {HIGH: 3, MEDIUM: 2, LOW: 1}


def _weakest(*tags: str) -> str:
    """Return the lowest-confidence tag among the inputs (chain is as weak as
    its weakest link). Unknown tags are treated as LOW."""
    rank = min((_RANK.get(t, 1) for t in tags), default=1)
    for tag, r in _RANK.items():
        if r == rank:
            return tag
    return LOW


# ── dimension + datum parsing ────────────────────────────────────────
# Architectural feet-inches: 25'-0", 25' - 6 1/2", 14'-0", 100'-0"
_DIM = re.compile(r"(\d{1,3})'\s*-?\s*(\d{1,2})?\s*(\d{1,2}/\d{1,2})?\"")
# Grid-bubble labels: 1, 2, 12, A, B, AA, B.4, D.5 (one or two chars + opt .digit)
_GRID_LABEL = re.compile(r"^(?:[A-Za-z]{1,2}|\d{1,2})(?:\.\d)?$")
# Level datum names commonly stacked on elevations and sections.
_LEVEL_NAME = re.compile(
    r"(T\.?\s*O\.?\s*(?:STEEL|SLAB|MASONRY|CONC(?:RETE)?|PARAPET|DECK|JOIST|"
    r"FOOTING|FND|FOUNDATION|PLATE|WALL)"
    r"|TOP\s+OF\s+(?:STEEL|SLAB|MASONRY|CONCRETE|PARAPET|DECK|WALL|FOOTING)"
    r"|FIN(?:ISH(?:ED)?)?\.?\s*F(?:LR|LOOR)"
    r"|(?:LOW|HIGH)\s+ROOF|ROOF\s+BEARING|BRG|EAVE)",
    re.IGNORECASE,
)
# An elevation value attached to a datum: EL. 16'-0", +16'-0", 100'-0".
_ELEV = re.compile(r"(?:EL(?:EV)?\.?\s*)?([+\-]?\d{1,3})'\s*-?\s*(\d{1,2})?\"")


def _dim_to_feet(feet_str: str, inch_str: Optional[str], frac_str: Optional[str]) -> float:
    """Convert a parsed feet/inches/fraction triple to decimal feet."""
    feet_str = (feet_str or "").strip()
    neg = feet_str.startswith("-")   # '-0' must read as negative (below-grade datum)
    ft = abs(float(feet_str))
    inches = float(inch_str) if inch_str else 0.0
    if frac_str:
        num, den = frac_str.split("/")
        inches += float(num) / float(den)
    sign = -1.0 if neg else 1.0
    return sign * (ft + inches / 12.0)


def parse_dimensions_ft(text: str) -> list[float]:
    """Every architectural dimension on a sheet, in decimal feet."""
    out = []
    for m in _DIM.finditer(text):
        try:
            out.append(_dim_to_feet(m.group(1), m.group(2), m.group(3)))
        except (ValueError, ZeroDivisionError):
            continue
    return out


# ── grid extraction (vector-first) ───────────────────────────────────

def _circle_bubbles(page) -> list[tuple]:
    """Grid bubbles drawn as circles. Heuristic: a closed near-square path made
    of curves, bubble-sized (roughly 14 to 70 pt across). Returns a list of
    (cx, cy, diameter) in PDF points. Corroborates label clusters; not relied
    on alone (some sets letter the grid without a visible bubble)."""
    out = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return out
    for d in drawings:
        items = d.get("items", [])
        if not items:
            continue
        curves = sum(1 for it in items if it and it[0] == "c")
        rect = d.get("rect")
        if rect is None or curves < 2:
            continue
        w, h = float(rect.width), float(rect.height)
        if w <= 0 or h <= 0:
            continue
        if max(w, h) / max(min(w, h), 0.01) >= 1.4:
            continue  # not round
        if not (14.0 <= max(w, h) <= 70.0):
            continue  # not bubble-sized
        out.append(((rect.x0 + rect.x1) / 2.0, (rect.y0 + rect.y1) / 2.0, max(w, h)))
    return out


def _label_tokens(page) -> list[tuple]:
    """Short grid-label tokens with their center point: (label, cx, cy)."""
    out = []
    try:
        words = page.get_text("words")  # (x0,y0,x1,y1,word,block,line,wordno)
    except Exception:
        return out
    for w in words:
        tok = (w[4] or "").strip()
        if tok and _GRID_LABEL.match(tok):
            out.append((tok.upper(), (w[0] + w[2]) / 2.0, (w[1] + w[3]) / 2.0))
    return out


def _associate_labels_to_bubbles(bubbles: list[tuple],
                                 labels: list[tuple]) -> list[tuple]:
    """Anchor each grid bubble to the single closest label token inside it.

    This is the noise filter that matters: short tokens scattered through the
    title block and general notes ('OF', 'TO', 'US', 'TX') look like grid labels
    to a regex but are NOT inside a grid bubble. Keeping only bubble-anchored
    labels drops that noise. Returns (label, bubble_cx, bubble_cy) using the
    bubble center as the authoritative position; one label per bubble.
    """
    out = []
    used = set()
    for (bx, by, dia) in bubbles:
        tol = (dia / 2.0) * 1.4
        best_k, best_d = None, tol
        for k, (lab, lx, ly) in enumerate(labels):
            if k in used:
                continue
            d = math.hypot(lx - bx, ly - by)
            if d < best_d:
                best_k, best_d = k, d
        if best_k is not None:
            used.add(best_k)
            out.append((labels[best_k][0], bx, by))
    return out


def _margin_bands(values: list[float], tol: float = 30.0) -> list[float]:
    """Band centers where grid bubbles line up: the plan margins. Grid bubbles
    for one axis cluster in one or two substantial bands (a top row and/or a
    bottom row for numbers; left/right columns for letters). Interior
    detail-reference bubbles are sparse and fall outside every substantial band,
    so they drop. A lone stray at an extreme cannot define a band on its own.
    Returns the centers of every band holding at least half the densest band."""
    if not values:
        return []
    counts = [(v, sum(1 for w in values if abs(w - v) <= tol)) for v in values]
    dmax = max(c for _, c in counts)
    centers: list[float] = []
    for v, c in sorted(counts, key=lambda z: -z[1]):
        if c >= max(2, dmax * 0.5) and all(abs(v - cc) > tol for cc in centers):
            centers.append(v)
    # Grid bubbles for an axis sit only at the two plan margins (top/bottom for
    # numbers, left/right for letters), never in a third interior band. Keep just
    # the extreme bands so a dense interior detail-callout cluster cannot leak in.
    if len(centers) >= 2:
        centers.sort()
        return [centers[0], centers[-1]]
    return centers


def _axis_grid(points: list[tuple], axis: str, use_band: bool) -> list[tuple]:
    """Ordered grid lines along one axis from labelled points.

    axis == "x": VERTICAL grid lines, keyed by x; their bubbles share a common y
                 (the top/bottom margin row).
    axis == "y": HORIZONTAL grid lines, keyed by y; their bubbles share a common
                 x (the left/right margin column).

    When use_band is True (bubbles present) we first keep only points in the
    densest perpendicular band, which removes interior detail bubbles. A label
    can repeat at both ends of its line; we keep the median parallel position.
    Returns [(label, position_pt)] sorted by position.
    """
    if not points:
        return []
    # par = position along the axis (identifies the line); perp = margin band.
    if axis == "x":
        par = lambda p: p[1]  # cx
        perp = lambda p: p[2]  # cy
    else:
        par = lambda p: p[2]  # cy
        perp = lambda p: p[1]  # cx

    if use_band:
        centers = _margin_bands([perp(p) for p in points])
        if centers:
            points = [p for p in points
                      if any(abs(perp(p) - c) <= 30.0 for c in centers)]

    by_label: dict[str, list[float]] = {}
    for p in points:
        by_label.setdefault(p[0], []).append(par(p))
    lines = []
    for label, positions in by_label.items():
        positions.sort()
        lines.append((label, positions[len(positions) // 2]))
    lines.sort(key=lambda t: t[1])
    return lines


def _estimate_scale_ft_per_pt(grid_gaps_pt: list[float], dims_ft: list[float]) -> tuple:
    """Estimate drawing scale (feet per PDF point) and a confidence tag.

    Relative grid spacing comes for free from the pixel gaps, so the render is
    correctly proportioned regardless of scale. The scale only sets the absolute
    feet value (needed later for the Slice-3 tonnage QC, not for the Slice-1
    visual). We pair the typical bay dimension with the typical pixel gap:

      MEDIUM: plausible bay dimensions (8 to 60 ft) and grid gaps both present;
              scale = median(bay dims) / median(gaps).
      LOW:    no usable dimensions; assume a nominal 25 ft typical bay so the
              model still renders, flagged for human confirmation.
    """
    gaps = [g for g in grid_gaps_pt if g > 1.0]
    bays = sorted(d for d in dims_ft if 8.0 <= d <= 60.0)
    if gaps and bays:
        gaps_sorted = sorted(gaps)
        med_gap = gaps_sorted[len(gaps_sorted) // 2]
        med_bay = bays[len(bays) // 2]
        if med_gap > 0:
            return med_bay / med_gap, MEDIUM
    if gaps:
        gaps_sorted = sorted(gaps)
        med_gap = gaps_sorted[len(gaps_sorted) // 2]
        if med_gap > 0:
            return 25.0 / med_gap, LOW  # nominal bay, flagged
    return 0.0, LOW


def extract_grid(page) -> dict:
    """Build the column-grid coordinate frame from one framing/foundation plan.

    Vector-first: short grid-label tokens (numbers along X, letters along Y) are
    clustered into ordered grid lines; circle bubbles corroborate and raise
    confidence. Pixel positions are converted to feet through an estimated
    drawing scale (see _estimate_scale_ft_per_pt).

    Returns:
        {
          "x_lines": [{"label": "1", "ft": 0.0, "pt": 120.4}, ...],  # vertical lines
          "y_lines": [{"label": "A", "ft": 0.0, "pt": 90.1}, ...],   # horizontal lines
          "scale_ft_per_pt": float,
          "confidence": "high|medium|low",
          "needs_review": bool,
          "source": "vector",
          "notes": [...],
        }
    A grid with fewer than 2 lines on an axis is not usable; confidence is LOW
    and needs_review is True so a human supplies the frame.
    """
    bubbles = _circle_bubbles(page)
    labels = _label_tokens(page)
    notes = []

    # Bubble-anchored labels are clean; bare label clustering (no bubbles) is the
    # lower-confidence fallback for sets that letter the grid without a visible
    # bubble. Either way numbers identify X lines, letters identify Y lines.
    use_band = len(bubbles) >= 4
    anchored = _associate_labels_to_bubbles(bubbles, labels) if use_band else labels

    numeric = [p for p in anchored if p[0][:1].isdigit()]
    alpha = [p for p in anchored if p[0][:1].isalpha()]

    x_lines_raw = _axis_grid(numeric, "x", use_band)
    y_lines_raw = _axis_grid(alpha, "y", use_band)

    # Pixel gaps between consecutive grid lines feed the scale estimate.
    x_pts = [p for _, p in x_lines_raw]
    y_pts = [p for _, p in y_lines_raw]
    gaps = [b - a for a, b in zip(x_pts, x_pts[1:])] + [b - a for a, b in zip(y_pts, y_pts[1:])]
    dims = parse_dimensions_ft(page.get_text())
    scale, scale_conf = _estimate_scale_ft_per_pt(gaps, dims)

    def _to_ft(positions: list[float]) -> list[float]:
        if not positions:
            return []
        base = min(positions)
        return [round((p - base) * scale, 3) for p in positions]

    x_ft = _to_ft(x_pts)
    # PDF y grows downward; flip Y so the model reads like a plan looked at from
    # above (north up). Consistency matters more than the sign for a QC view.
    y_ft = _to_ft(y_pts)
    if y_ft:
        y_max = max(y_ft)
        y_ft = [round(y_max - v, 3) for v in y_ft]

    x_lines = [{"label": lbl, "ft": ft, "pt": round(pt, 2)}
               for (lbl, pt), ft in zip(x_lines_raw, x_ft)]
    y_lines = [{"label": lbl, "ft": ft, "pt": round(pt, 2)}
               for (lbl, pt), ft in zip(y_lines_raw, y_ft)]

    n_lines = len(x_lines) + len(y_lines)
    usable = len(x_lines) >= 2 and len(y_lines) >= 2

    # Confidence: start from the scale tag, raise it when bubbles corroborate a
    # clean grid, drop it when the grid is too thin to trust.
    confidence = scale_conf
    if usable and len(bubbles) >= max(len(x_lines), len(y_lines)):
        confidence = _weakest(MEDIUM if scale_conf == LOW else HIGH, scale_conf)
        if scale_conf == MEDIUM and len(bubbles) >= n_lines:
            confidence = HIGH
        notes.append(f"{len(bubbles)} grid bubbles corroborate the label grid.")
    if not usable:
        confidence = LOW
        notes.append("Grid too sparse to trust (need >=2 lines per axis). "
                     "Flagged for human entry of bay dimensions.")
    if scale == 0.0:
        notes.append("No drawing scale recoverable; positions are relative only.")

    return {
        "x_lines": x_lines,
        "y_lines": y_lines,
        "scale_ft_per_pt": round(scale, 6),
        "scale_confidence": scale_conf,
        "confidence": confidence,
        "needs_review": (not usable) or confidence == LOW,
        "source": "vector",
        "bubble_count": len(bubbles),
        "notes": notes,
    }


# ── level / datum extraction ─────────────────────────────────────────

def _normalize_level_name(raw: str) -> str:
    """Canonicalize a datum name so 'T/STEEL' and 'TOP OF STEEL' agree."""
    s = re.sub(r"\s+", " ", raw.strip().upper())
    s = s.replace("T/", "T.O. ").replace("T.O ", "T.O. ")
    if "FIN" in s and "F" in s:
        return "FINISH FLOOR"
    if "ROOF" in s:
        return "ROOF"
    s = re.sub(r"T\.?\s*O\.?\s*", "T.O. ", s)
    return s.strip()


def _datum_elev_from_tail(tail: str) -> Optional[float]:
    """The datum elevation that immediately follows a level name, or None.

    PDF text linearizes a drawing, so a datum name is not guaranteed to sit next
    to its elevation. We scan the elevation-shaped tokens in a short window and
    return the first that reads like a datum elevation, rejecting tokens that the
    surrounding text marks as a clearance, spacing, or slope dimension (CLR, TYP,
    O.C., PER, SLOPE) rather than a level. Heuristic; a bounding-box proximity
    pairing is the Phase 1b upgrade."""
    _PRE_NOISE = ("PER", "SLOPE", "@")
    _TRAIL_NOISE = ("CLR", "TYP", "O.C", "OC.", "WIDE", "LONG")
    for em in _ELEV.finditer(tail):
        pre = tail[max(0, em.start() - 12):em.start()].upper()
        post = tail[em.end():em.end() + 6].upper().lstrip()
        if any(k in pre for k in _PRE_NOISE):
            continue
        if any(post.startswith(k) for k in _TRAIL_NOISE):
            continue
        try:
            return _dim_to_feet(em.group(1), em.group(2), None)
        except (ValueError, ZeroDivisionError):
            continue
    return None


def extract_levels(pages_text: list[str]) -> dict:
    """Parse level datums (Z frame) from elevation/section text.

    Returns {"levels": {name: elev_ft}, "confidence": ..., "needs_review": ...,
             "notes": [...]}. For a single-story flat shell the two that matter
    are the base (T.O. Slab / Finish Floor = 0) and T.O. Steel (eave). When an
    explicit T.O. Steel elevation is found it is used (MEDIUM); otherwise a
    flagged nominal 16 ft is returned (LOW, needs_review) so the model renders
    while a human confirms the height.
    """
    levels: dict[str, float] = {}
    notes = []
    found_top_of_steel = False

    for text in pages_text:
        for m in _LEVEL_NAME.finditer(text):
            name = _normalize_level_name(m.group(0))
            # The datum elevation that immediately follows the name (rejecting
            # clearance / slope dimensions that linearized text can interleave).
            elev = _datum_elev_from_tail(text[m.end():m.end() + 40])
            if elev is None:
                continue
            # Keep the first plausible reading per datum name.
            if name not in levels and -10.0 <= elev <= 300.0:
                levels[name] = round(elev, 3)
                if "STEEL" in name:
                    found_top_of_steel = True

    # The drawing's elevation datum is the slab / finish floor (0 or 100'-0").
    # Every other level (a below-grade footing, the steel eave) is read relative
    # to it, so ONLY a slab / finish-floor datum may re-zero the frame. A footing
    # or foundation elevation is below grade and must never become the base, or
    # every column would inflate by the footing depth. Choose by name, not by
    # text-scan order.
    slab_names = [n for n in levels if "SLAB" in n or "FINISH FLOOR" in n]
    base = levels[slab_names[0]] if slab_names else 0.0
    if base != 0.0:
        for n in list(levels):
            levels[n] = round(levels[n] - base, 3)
    levels["T.O. SLAB"] = 0.0  # pin the slab datum to 0 (assign, not setdefault)

    confidence = MEDIUM if found_top_of_steel else LOW
    if not found_top_of_steel:
        levels.setdefault("T.O. STEEL", 16.0)  # flagged nominal eave
        notes.append("No T.O. Steel elevation found; using a nominal 16 ft eave. "
                     "Human must confirm the steel height before this model ships.")
    else:
        notes.append(f"T.O. Steel read at {levels.get('T.O. STEEL', '?')} ft above slab.")

    return {
        "levels": levels,
        "base_name": slab_names[0] if slab_names else "T.O. SLAB",
        "confidence": confidence,
        "needs_review": confidence == LOW,
        "notes": notes,
    }


# ── member placement ─────────────────────────────────────────────────

def _grid_intersections(grid: dict) -> list[tuple]:
    """Every (x_ft, y_ft, x_label, y_label) intersection of the grid frame."""
    out = []
    for xl in grid.get("x_lines", []):
        for yl in grid.get("y_lines", []):
            out.append((xl["ft"], yl["ft"], xl["label"], yl["label"]))
    return out


def place_columns(columns: list, grid: dict, levels: dict,
                  source_sheet: int = 0) -> list[dict]:
    """Place detected columns onto the grid frame as coordinate-tagged members.

    columns: detected column records (objects or dicts) carrying at least a
             ``shape``. Slice-1 detection has NO per-column grid reference, and
             text-stream order is not spatial order, so we cannot say which
             detected mark sits at which intersection. We therefore place the
             dominant detected column shape at every grid intersection and flag
             the result: it is grid-derived, not mark-confirmed. A verified
             per-column mapping arrives in Slice 2 (members carrying grid refs).

    Returns a list of coordinate_members.json records (see module docstring).
    """
    inter = _grid_intersections(grid)
    if not inter:
        return []

    base = float(levels.get("levels", levels).get("T.O. SLAB", 0.0)) \
        if isinstance(levels, dict) else 0.0
    lv = levels.get("levels", levels) if isinstance(levels, dict) else {}
    top = float(lv.get("T.O. STEEL", 16.0))

    def _shape_of(c):
        if isinstance(c, dict):
            return c.get("shape", "")
        return getattr(c, "shape", "")

    shapes = [s for s in (_shape_of(c) for c in columns) if s]
    dominant = max(set(shapes), key=shapes.count) if shapes else ""

    grid_conf = grid.get("confidence", LOW)
    # Placement is grid-derived, never mark-confirmed in Slice 1: capped at LOW
    # and always flagged for human review, so an unverified position can never
    # ship as trusted. The shape is the dominant detected column shape.
    place_conf = _weakest(grid_conf, LOW)
    out = []
    for (x, y, xlbl, ylbl) in inter:
        out.append({
            "mark": f"C{xlbl}{ylbl}",
            "shape": dominant,
            "type": "column",
            "start": [round(x, 3), round(y, 3), round(base, 3)],
            "end": [round(x, 3), round(y, 3), round(top, 3)],
            "level": "T.O. STEEL",
            "grid_ref": f"{xlbl}-{ylbl}",
            "confidence": place_conf,
            "needs_review": True,
            "source_sheet": source_sheet,
            "placement": "grid_intersection_unverified",
        })
    return out


def place_members(framing_members: list, grid: dict, levels: dict,
                  source_sheet: int = 0) -> list[dict]:
    """Slice-2 placeholder: beams, girders, and joists between grid lines.

    Kept here so the data contract and call sites are forward-compatible. Slice
    1 ships columns only; this returns an empty list and a note rather than
    guessing span endpoints we cannot yet read. See the spec, Phase 2.
    """
    return []


# ── vision fallback (scanned / non-vector sets) ──────────────────────

def _has_enough_vectors(page, minimum: int = 60) -> bool:
    try:
        return len(page.get_drawings()) >= minimum
    except Exception:
        return False


def vision_fallback_grid(page, project_name: str = "") -> dict:
    """Flagged fallback for scanned or non-vector framing sheets.

    In Slice 1 NO multimodal call path is wired into the bridge, so this function
    intentionally degrades to a flagged human-entry result rather than inventing
    a grid. It probes defensively for a future Gemini/GPT-4o image-call path; the
    actual vision read is planned for Phase 1b. Output ALWAYS carries
    source="vision" or source="human_entry_required" and LOW confidence, per
    verify-don't-generate.
    """
    notes = ["Vector grid extraction was insufficient (scanned or raster set)."]
    # Locate a multimodal call path defensively. We do not hard-depend on any
    # one integrator signature; if absent we degrade to human entry.
    caller = None
    try:
        from bridge import api_integrator as _ai  # noqa
        caller = getattr(_ai, "_call_gemini", None) or getattr(_ai, "call_vision", None)
    except Exception:
        caller = None

    if caller is None:
        notes.append("No multimodal call path available here; human must enter "
                     "the grid (bay dimensions) and level datums.")
        return {
            "x_lines": [], "y_lines": [], "scale_ft_per_pt": 0.0,
            "scale_confidence": LOW, "confidence": LOW, "needs_review": True,
            "source": "human_entry_required", "bubble_count": 0, "notes": notes,
        }

    # A real vision call is wired. We still tag the result LOW and needs_review:
    # multimodal grid reads are approximate, never accurate (constitution).
    notes.append("Vision grid read is approximate; always human-confirmed.")
    return {
        "x_lines": [], "y_lines": [], "scale_ft_per_pt": 0.0,
        "scale_confidence": LOW, "confidence": LOW, "needs_review": True,
        "source": "vision", "bubble_count": 0,
        "notes": notes + ["Vision schema parsing is wired in Phase 1b; Slice 1 "
                          "ships the vector path and flags raster sets."],
    }


# ── page selection + orchestration ───────────────────────────────────

_FRAMING_HINT = re.compile(
    r"(roof framing|floor framing|framing plan|foundation plan|low roof|high roof|"
    r"roof plan|structural plan|anchor (?:bolt|rod) plan)", re.IGNORECASE)
_ELEV_SECT_HINT = re.compile(r"(elevation|section|building section|wall section)", re.IGNORECASE)


def _pick_framing_page(doc) -> tuple:
    """Choose the best framing/foundation plan page. Score by framing keywords
    plus grid-bubble count (a real framing plan has a labelled grid). Returns
    (page_index, score) or (-1, 0)."""
    best_idx, best_score = -1, 0.0
    for i in range(len(doc)):
        page = doc[i]
        try:
            text = page.get_text()
        except Exception:
            continue
        score = 0.0
        if _FRAMING_HINT.search(text):
            score += 5.0
        score += min(len(_circle_bubbles(page)), 30) * 0.5
        labels = _label_tokens(page)
        if len([p for p in labels if p[0][:1].isdigit()]) >= 2 and \
           len([p for p in labels if p[0][:1].isalpha()]) >= 2:
            score += 3.0
        if score > best_score:
            best_idx, best_score = i, score
    return best_idx, best_score


def build_coordinate_members(pdf_path: str = "", members: Optional[list] = None,
                             project_name: str = "") -> dict:
    """Assemble the coordinate model for a bid: grid + datums + placed columns.

    pdf_path: the plan-set PDF (vector framing plan inside). Optional - without
              it the function returns a flagged human-entry result.
    members:  detected members from the takeoff (DetectedMember objects or
              dicts). Columns (member_type/type == 'column') are placed; other
              members are deferred to Slice 2.

    Returns:
        {
          "members": [coordinate_members.json records...],
          "grid": {...}, "levels": {...},
          "meta": {confidence, needs_review, scale, framing_page, warnings, ...},
        }
    This is additive. It does NOT touch tonnage, AISC weights, or any rate.
    """
    members = members or []
    warnings = []

    def _is_column(m):
        if isinstance(m, dict):
            t = m.get("member_type") or m.get("type") or ""
            mark = m.get("mark", "")
        else:
            t = getattr(m, "member_type", "") or ""
            mark = getattr(m, "mark", "")
        if str(t).lower() == "column":
            return True
        # Fallback for BOM rows that dropped member_type: mark prefix 'C' is a
        # column on Your Company sets (matches takeoff.py's type_map).
        return (not t) and str(mark)[:1].upper() == "C"

    columns = [m for m in members if _is_column(m)]

    if not pdf_path or not Path(pdf_path).exists():
        return {
            "members": [], "grid": {}, "levels": {},
            "meta": {
                "confidence": LOW, "needs_review": True,
                "warnings": ["No plan-set PDF supplied; coordinate model needs a "
                             "framing plan or human-entered grid."],
                "source": "human_entry_required",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    try:
        import fitz  # PyMuPDF
    except Exception as e:
        return {
            "members": [], "grid": {}, "levels": {},
            "meta": {"confidence": LOW, "needs_review": True,
                     "warnings": [f"PyMuPDF unavailable: {e}"],
                     "source": "human_entry_required",
                     "generated_at": datetime.now(timezone.utc).isoformat()},
        }

    doc = fitz.open(pdf_path)
    try:
        page_idx, score = _pick_framing_page(doc)
        if page_idx < 0:
            warnings.append("No framing/foundation plan page identified.")
            grid = {"x_lines": [], "y_lines": [], "confidence": LOW,
                    "needs_review": True, "source": "none", "notes": []}
        else:
            page = doc[page_idx]
            if _has_enough_vectors(page):
                grid = extract_grid(page)
            else:
                grid = vision_fallback_grid(page, project_name)
            grid["source_sheet"] = page_idx + 1

        # Level datums come from elevation/section pages (fall back to all pages).
        elev_texts = []
        for i in range(len(doc)):
            try:
                t = doc[i].get_text()
            except Exception:
                continue
            if _ELEV_SECT_HINT.search(t):
                elev_texts.append(t)
        if not elev_texts:
            elev_texts = [doc[i].get_text() for i in range(len(doc))]
        level_info = extract_levels(elev_texts)

        source_sheet = grid.get("source_sheet", page_idx + 1 if page_idx >= 0 else 0)
        coord_members = place_columns(columns, grid, level_info, source_sheet)

        if not coord_members:
            warnings.append("No columns placed (no grid or no detected columns).")
        low = sum(1 for m in coord_members if m.get("confidence") == LOW)
        confidence = _weakest(grid.get("confidence", LOW), level_info.get("confidence", LOW))
        needs_review = bool(grid.get("needs_review") or level_info.get("needs_review") or low)

        return {
            "members": coord_members,
            "grid": grid,
            "levels": level_info,
            "meta": {
                "confidence": confidence,
                "grid_confidence": grid.get("confidence", LOW),
                "level_confidence": level_info.get("confidence", LOW),
                "needs_review": needs_review,
                "framing_page": page_idx + 1 if page_idx >= 0 else None,
                "framing_page_score": round(score, 2),
                "scale_ft_per_pt": grid.get("scale_ft_per_pt", 0.0),
                "column_count": len(coord_members),
                "low_confidence_members": low,
                "warnings": warnings,
                "source": grid.get("source", "vector"),
                "model_is_estimate_grade": True,
                "system_of_record": "Tekla Structures (this model is QC/visualization only)",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    finally:
        doc.close()


def to_stl_members(coord_members: list) -> list[dict]:
    """Adapt coordinate_members.json records to fabrication.generate_stl endpoint
    mode (each carries shape + start + end). Pure adapter; no geometry math."""
    out = []
    for m in coord_members:
        s, e, shp = m.get("start"), m.get("end"), m.get("shape")
        if not (s and e and shp):
            continue
        # A zero-length member contributes no geometry in generate_stl and would
        # silently inflate the rendered member count; drop it so the count is honest.
        if all(abs(float(a) - float(b)) < 1e-6 for a, b in zip(s, e)):
            continue
        out.append({
            "shape": shp,
            "start": s,
            "end": e,
            "mark": m.get("mark", ""),
            "confidence": m.get("confidence", LOW),
        })
    return out


def save_coordinate_members(model: dict, out_path: str) -> str:
    """Write the coordinate model to ``coordinate_members.json``. Returns path."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(model, indent=2), encoding="utf-8")
    return str(p)


def render_model_png(model: dict, renders_dir: str, name: str = "model") -> dict:
    """Render the coordinate model to a gray QC viewport PNG and the backing STL.

    Tier 1 of the render plan: fabrication.generate_stl endpoint mode plus
    stl_thumbnail.render_stl_thumbnail. No new dependency. Saved as
    ``<name>_MODEL.png`` so bid_documents.find_render places it in the ``model``
    tier (below a true Tekla export, above a fused MASTER) and the proposal
    caption marks it estimate-grade. Render failure is non-fatal: the
    coordinate JSON is the durable artifact. Returns {"png","stl",
    "stl_member_count"}.
    """
    out = {"png": "", "stl": "", "stl_member_count": 0}
    stl_members = to_stl_members(model.get("members", []))
    out["stl_member_count"] = len(stl_members)
    if not stl_members:
        return out
    try:
        from bridge.fabrication import generate_stl
        stl_bytes = generate_stl(stl_members)
    except Exception:
        return out
    if not stl_bytes or len(stl_bytes) < 100:
        return out
    d = Path(renders_dir)
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:48] or "model"
    stl_path = d / f"{safe}_MODEL.stl"
    try:
        stl_path.write_bytes(stl_bytes)
        out["stl"] = str(stl_path)
    except Exception:
        return out
    try:
        from bridge.stl_thumbnail import render_stl_thumbnail
        png = render_stl_thumbnail(str(stl_path), str(d / f"{safe}_MODEL.png"),
                                   width_px=1200, height_px=800)
        out["png"] = png or ""
    except Exception:
        out["png"] = ""
    return out
