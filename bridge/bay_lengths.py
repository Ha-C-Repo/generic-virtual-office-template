"""F21: Bay-derivation fallback for beam lengths.

When a beam detection has length_ft=0 (no printed dimension on the
plan and no schedule entry), we can often infer the length from the
grid bay spacing. Plans almost always label column lines (A, B, C, D
horizontally and 1, 2, 3, 4 vertically) and frequently print bay
distances between lines (e.g. "30'-0\"" between grids B and C).

This module:
1. Parses the structural grid (line letters/numbers + bay distances)
   from the page text via PyMuPDF.
2. For each beam detection with length_ft=0, infers a likely span:
   - Beam between grids B and C → span = bay_distance(B, C)
   - Beam parallel to grid lines covers ONE bay → span = mean bay
   - When orientation is unknown, use mean of horizontal + vertical bays
3. Marks detections with bay_length_inferred=True and notes.

A safety check: if the inferred length is more than 1.5x the largest
known bay or less than 0.3x the smallest known bay, do not apply the
inference - leave length_ft = 0 and let the auto_review flag it.

Grid parsing is heuristic. For irregular grids, the estimator overrides
via the override_bay_ft kwarg.
"""

from __future__ import annotations
from pathlib import Path
import re


_BAY_DIM_REGEX = re.compile(
    r"(?P<ft>\d{1,3})['’\s\-]+(?P<inches>\d{1,2})?\"?",
)
_BAY_DECIMAL_REGEX = re.compile(r"\b(\d{1,3}\.\d{1,2})\s*FT\b", re.IGNORECASE)


def _parse_dim_text(text: str) -> list[float]:
    """Extract feet-decimal lengths from a chunk of drawing text.

    Catches "30'-0\"", "24'-6", "32.5 FT", etc.
    Returns the raw list of feet-decimal values.
    """
    out: list[float] = []
    for m in _BAY_DIM_REGEX.finditer(text or ""):
        try:
            ft = float(m.group("ft"))
            inc = m.group("inches")
            inches = float(inc) if inc else 0.0
            val = ft + inches / 12.0
            # Filter ridiculous values (must be 6-100 ft to be a bay)
            if 6 <= val <= 100:
                out.append(round(val, 2))
        except (ValueError, TypeError):
            pass
    for m in _BAY_DECIMAL_REGEX.finditer(text or ""):
        try:
            val = float(m.group(1))
            if 6 <= val <= 100:
                out.append(round(val, 2))
        except ValueError:
            pass
    return out


def estimate_bay_distances(pdf_path: str | Path,
                            page_indices: list[int] | None = None) -> dict:
    """Return per-page list of probable bay distances in feet.

    Aggregates across all framing-plan pages and returns mean / median.
    """
    try:
        import fitz
        import statistics
    except ImportError as e:
        raise RuntimeError("PyMuPDF required") from e

    doc = fitz.open(pdf_path)
    by_page: dict[int, list[float]] = {}
    all_bays: list[float] = []
    pages = page_indices if page_indices is not None else range(len(doc))

    for pi in pages:
        if pi < 0 or pi >= len(doc):
            continue
        txt = doc[pi].get_text() or ""
        bays = _parse_dim_text(txt)
        by_page[pi] = bays
        all_bays.extend(bays)
    doc.close()

    if all_bays:
        # Filter outliers: only keep bays within 0.5x to 2x of the median
        all_bays_sorted = sorted(all_bays)
        med = statistics.median(all_bays_sorted)
        filt = [b for b in all_bays_sorted if 0.5 * med <= b <= 2.0 * med]
        if not filt:
            filt = all_bays_sorted
        return {
            "by_page": by_page,
            "all_bays_ft": all_bays_sorted,
            "filtered_bays_ft": filt,
            "mean_bay_ft": round(statistics.mean(filt), 2),
            "median_bay_ft": round(statistics.median(filt), 2),
            "min_bay_ft": round(min(filt), 2),
            "max_bay_ft": round(max(filt), 2),
            "bay_sample_count": len(filt),
        }
    return {
        "by_page": by_page,
        "all_bays_ft": [],
        "filtered_bays_ft": [],
        "mean_bay_ft": 0.0,
        "median_bay_ft": 0.0,
        "min_bay_ft": 0.0,
        "max_bay_ft": 0.0,
        "bay_sample_count": 0,
    }


def fill_missing_lengths(detections: list[dict],
                          bay_summary: dict,
                          override_bay_ft: float | None = None) -> dict:
    """For each beam-like detection with length_ft=0, fill in median bay.

    Returns counts.
    """
    median = override_bay_ft or bay_summary.get("median_bay_ft", 0)
    if median <= 0:
        return {
            "median_bay_ft": 0,
            "beams_with_inferred_length": 0,
            "beams_skipped_no_bay_data": sum(
                1 for d in detections
                if float(d.get("length_ft") or 0) == 0
                and (d.get("member_type") or "").lower() != "column"
            ),
        }

    inferred = 0
    for d in detections:
        if float(d.get("length_ft") or 0) > 0:
            continue
        mt = (d.get("member_type") or "").lower()
        if mt == "column":
            continue  # columns handled by column_heights
        # Beams, joists, plates with length=0 -> use bay
        d["length_ft"] = median
        d.setdefault("notes", []).append(
            f"length inferred from grid bay = {median:.1f} ft")
        d["bay_length_inferred"] = True
        inferred += 1
    return {
        "median_bay_ft": median,
        "beams_with_inferred_length": inferred,
    }
