"""F11: Clash / double-count detector.

Catches the case where the same physical member is tagged twice
(once on plan sheet, once on schedule, or twice across overlapping
sheets). Flags by (shape, mark, sheet) collisions.
"""

from __future__ import annotations
from collections import defaultdict


def detect_clashes(members: list[dict]) -> dict:
    """Return clash report.

    Definition of clash:
    - Same shape + same piece mark on two different sheets (the mark
      is the identity, so this is almost always a true double-count).
    - Same shape + same gridline + same length on same sheet (possible
      double-count from estimator running two markup passes).
    """
    by_mark = defaultdict(list)
    by_sig = defaultdict(list)
    for m in members:
        s = (m.get("shape") or "").upper().strip()
        mark = (m.get("mark") or m.get("piece_mark") or "").upper().strip()
        sheet = (m.get("sheet") or m.get("page") or m.get("page_num") or "").upper().strip()
        gridline = (m.get("gridline") or m.get("location") or "").upper().strip()
        length = round(float(m.get("length_ft", 0) or 0), 2)
        qty = int(m.get("qty", 1) or 1)
        if mark and s:
            by_mark[(s, mark)].append({"sheet": sheet, "qty": qty})
        if sheet and gridline and s and length:
            by_sig[(s, gridline, length, sheet)].append(qty)

    mark_clashes = []
    for (s, mark), occ in by_mark.items():
        sheets = {o["sheet"] for o in occ}
        if len(sheets) > 1:
            mark_clashes.append({
                "shape": s, "mark": mark,
                "sheets": sorted(sheets),
                "total_qty": sum(o["qty"] for o in occ),
            })

    grid_clashes = []
    for (s, g, l, sh), qtys in by_sig.items():
        if len(qtys) > 1:
            grid_clashes.append({
                "shape": s, "gridline": g, "length_ft": l, "sheet": sh,
                "occurrences": len(qtys), "total_qty": sum(qtys),
            })

    return {
        "mark_clash_count": len(mark_clashes),
        "grid_clash_count": len(grid_clashes),
        "mark_clashes": mark_clashes,
        "grid_clashes": grid_clashes,
        "any_clashes": bool(mark_clashes or grid_clashes),
    }
