"""T3 scale check: title-block scale string vs measured grid spacing.

Reads every scale string on a sheet, then cross-checks the governing
plan scale by measuring the grid bubble span in vector coordinates
against the printed overall grid dimension. Mismatch beyond 2 percent
is a FLAG, recorded on every affected sheet (the measured sheet plus
any sheet carrying the same scale string with no passing check of its
own, marked inherited).

Why this matters: a set plotted at half or double size silently halves
or doubles every measured length. The check is mechanical: bubble span
in points / 72 = inches on paper; inches x scale = feet; compare to the
printed dimension.

Sheets where no check is possible return NO_CHECK with the reason,
never a silent pass. Standalone: no bridge/ imports, no pricing (P25).
"""

import re
from pathlib import Path

from takeoff_pipeline import sheet_router

TOLERANCE_PCT = 2.0

# 1" = 20'-0"  /  3/4" = 1'-0"  /  1 1/2" = 1'-0"
_SCALE = re.compile(
    r"(\d+(?:\s+\d+/\d+)?|\d+/\d+)\s?\"\s*=\s*(\d+)'(?:\s*-\s*(\d+)\s?\")?")
_NTS = re.compile(r"\bN\.?T\.?S\.?\b|NOT\s+TO\s+SCALE", re.I)
# Feet token with optional inches: 413', 45'-10", 22'-2 1/2".
_FEET_TOKEN = re.compile(
    r"^(\d{1,4})'(?:-(\d{1,2})(?:\s?\d{1,2}/\d{1,2})?\s?\")?$")
_BUBBLE = re.compile(r"^(?:[A-Z]{1,2}|\d{1,2})$")


def parse_feet_token(text: str):
    """Decimal feet from a dimension word, or None."""
    m = _FEET_TOKEN.match((text or "").strip())
    if not m:
        return None
    return float(m.group(1)) + (float(m.group(2) or 0) / 12.0)


def _frac_to_float(text: str) -> float:
    text = text.strip()
    total = 0.0
    for part in text.split():
        if "/" in part:
            num, den = part.split("/")
            total += float(num) / float(den)
        else:
            total += float(part)
    return total


def parse_scale(text: str):
    """Feet of real distance per inch of paper, or None."""
    m = _SCALE.search(text or "")
    if not m:
        return None
    paper_in = _frac_to_float(m.group(1))
    real_ft = float(m.group(2)) + (float(m.group(3) or 0) / 12.0)
    if paper_in <= 0 or real_ft <= 0:
        return None
    return real_ft / paper_in


def scale_strings(page) -> list:
    """Every scale string on the page, with NTS entries preserved."""
    out = []
    for line in page.get_text().splitlines():
        if _NTS.search(line):
            out.append({"text": line.strip()[:80], "ft_per_in": None})
            continue
        m = _SCALE.search(line)
        if m:
            out.append({"text": m.group(0),
                        "ft_per_in": parse_scale(m.group(0))})
    return out


def _sequence_like(tokens) -> bool:
    """True when the left-to-right tokens read like grid bubbles: all
    numeric and strictly increasing (01, 02, 03...), or all alphabetic
    and strictly increasing (A, B, C...). Random aligned short tokens
    (keynotes, bar marks) do not pass this."""
    if all(t.isdigit() for t in tokens):
        vals = [int(t) for t in tokens]
        return all(b > a for a, b in zip(vals, vals[1:]))
    if all(t.isalpha() for t in tokens):
        return all(b > a for a, b in zip(tokens, tokens[1:]))
    return False


def _bubble_row(words):
    """The horizontal grid bubble row: at least four short tokens,
    aligned within 8 pt vertically, forming a strictly increasing
    sequence. Topmost qualifying row wins (the grid line bubbles sit
    above the dimension strings)."""
    cands = [w for w in words if _BUBBLE.match(w[4])]
    rows = []
    used = set()
    for w in sorted(cands, key=lambda v: v[1]):
        if id(w) in used:
            continue
        row = [v for v in cands if abs(v[1] - w[1]) <= 8]
        for v in row:
            used.add(id(v))
        row.sort(key=lambda v: v[0])
        dedup = []
        for v in row:
            if not dedup or v[0] - dedup[-1][0] > 12:
                dedup.append(v)
        if len(dedup) >= 4 and _sequence_like([v[4] for v in dedup]):
            rows.append(dedup)
    return rows[0] if rows else None


def _stated_candidates(words, row, band_top):
    """Plausible printed values for the bubble-row span, target-blind.

    Two candidate kinds, both built only from dimension words inside
    the row's x-extent (a margin tolerates label offsets):
    - any single token of 60 ft or more (an overall dimension)
    - the sum of a y-aligned dimension row whose tokens tile at least
      80 percent of the span (a bay-dimension chain)
    The x-bound matters: a full-building overall dimension printed on a
    partial plan (one half of a long building split across two sheets)
    must not masquerade as the span's value."""
    first, last = row[0], row[-1]
    x_lo = ((first[0] + first[2]) / 2.0) - 40
    x_hi = ((last[0] + last[2]) / 2.0) + 40
    band = []
    for w in words:
        if band_top < w[1] <= band_top + 130:
            cx = (w[0] + w[2]) / 2.0
            if x_lo <= cx <= x_hi:
                ft = parse_feet_token(w[4])
                if ft is not None:
                    band.append((w[0], w[1], w[2], ft))
    if not band:
        return []
    candidates = [ft for _, _, _, ft in band if ft >= 60]
    used = set()
    span = x_hi - x_lo - 80
    for x0, y, x1, _ in band:
        key = round(y)
        if key in used:
            continue
        used.add(key)
        cluster = [b for b in band if abs(b[1] - y) <= 6]
        if len(cluster) < 3:
            continue
        extent = max(b[2] for b in cluster) - min(b[0] for b in cluster)
        if span > 0 and extent / span >= 0.8:
            candidates.append(sum(b[3] for b in cluster))
    return sorted(set(round(c, 2) for c in candidates))


def measure_grid(page, ft_per_in: float):
    """Compare the bubble-row span against the printed dimensions.

    The verdict asks: is ANY plausible printed value (overall token or
    bay-dimension chain) consistent with the measured span at the
    labeled scale? A wrong plot scale throws every candidate off by
    the same factor, so nothing agrees and the sheet flags. Returns a
    dict, or None when the page offers no measurable grid."""
    words = page.get_text("words")
    rect = page.rect
    row = _bubble_row([w for w in words if w[1] < rect.height * 0.25])
    if not row:
        return None
    first, last = row[0], row[-1]
    span_pt = ((last[0] + last[2]) / 2.0) - ((first[0] + first[2]) / 2.0)
    if span_pt < rect.width * 0.33:
        return None
    band_top = max(w[1] for w in row)
    candidates = _stated_candidates(words, row, band_top)
    if not candidates:
        return None
    measured_ft = span_pt / 72.0 * ft_per_in
    stated_ft = min(candidates, key=lambda c: abs(measured_ft - c))
    diff_pct = abs(measured_ft - stated_ft) / stated_ft * 100.0
    return {
        "bubbles": len(row),
        "span_pt": round(span_pt, 1),
        "stated_ft": stated_ft,
        "stated_candidates": candidates,
        "measured_ft": round(measured_ft, 1),
        "diff_pct": round(diff_pct, 2),
    }


def check_pdf(pdf_path, router_result=None) -> list:
    """Scale check for every sheet. Status per sheet: OK, FLAG, or
    NO_CHECK with the reason. Inherited flags are marked as such."""
    import fitz

    pdf_path = str(Path(pdf_path))
    router_result = router_result or sheet_router.route(pdf_path)
    results = []
    flagged_scales = set()

    doc = fitz.open(pdf_path)
    try:
        for entry in router_result["sheets"]:
            sheet = entry["sheet_number"] or f"PAGE-{entry['page_index']}"
            if entry["is_scanned"]:
                results.append({
                    "sheet": sheet, "status": "NO_CHECK",
                    "reason": "scanned sheet; 4x rasterization procedure "
                              "owns it", "scales": [], "measure": None})
                continue
            page = doc[entry["page_index"]]
            scales = scale_strings(page)
            plan_scales = [s for s in scales
                           if s["ft_per_in"] and s["ft_per_in"] >= 4]
            if not plan_scales:
                results.append({
                    "sheet": sheet, "status": "NO_CHECK",
                    "reason": "no plan-magnitude scale string on sheet",
                    "scales": scales, "measure": None})
                continue
            governing = max(s["ft_per_in"] for s in plan_scales)
            measure = measure_grid(page, governing)
            if measure is None:
                results.append({
                    "sheet": sheet, "status": "NO_CHECK",
                    "reason": "no measurable grid bubble row plus overall "
                              "dimension", "scales": scales,
                    "governing_ft_per_in": governing, "measure": None})
                continue
            status = "FLAG" if measure["diff_pct"] > TOLERANCE_PCT \
                else "OK"
            if status == "FLAG":
                flagged_scales.add(governing)
            results.append({
                "sheet": sheet, "status": status,
                "scales": scales, "governing_ft_per_in": governing,
                "measure": measure})
    finally:
        doc.close()

    # A flagged scale taints every sheet that carries the same scale
    # value and could not prove itself: the mismatch is recorded on
    # every affected sheet, not just where it was measured.
    for r in results:
        if r["status"] == "NO_CHECK" and flagged_scales:
            carried = {s["ft_per_in"] for s in r.get("scales", [])
                       if s.get("ft_per_in")}
            if carried & flagged_scales:
                r["status"] = "FLAG"
                r["reason"] = (r.get("reason", "") +
                               " ; inherited: shares a scale that failed "
                               "measurement on another sheet").strip(" ;")
    return results
