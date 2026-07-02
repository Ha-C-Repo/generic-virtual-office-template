"""Stop list CSV generator for ironworker back gauges.

Highest immediate shop value. Mario's crew currently measures bolt hole
locations by hand with a tape measure. This is the number one source of
measurement errors in the shop.

The operator loads the CSV onto the Geka touchscreen via USB. The back
gauge positions automatically. Zero tape measure.

Output columns: MemberMark, HoleNum, X_inches, Y_inches, Dia, Operation

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import csv
import io
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _default_bolt_layout(bolt_count: int, member_depth_in: float,
                         bolt_dia_in: float = 0.8125,
                         edge_dist_in: float = 2.5,
                         gage_in: float = 3.0) -> list[dict]:
    """Generate a standard bolt pattern for a shear tab connection.

    Bolts are laid out in a single vertical line at the gage distance
    from the member edge, evenly spaced starting from edge_dist_in.
    """
    if bolt_count <= 0:
        return []
    spacing = 3.0  # standard 3-inch spacing
    holes = []
    for i in range(bolt_count):
        holes.append({
            "hole_num": i + 1,
            "x_in": round(gage_in, 4),
            "y_in": round(edge_dist_in + i * spacing, 4),
            "dia_in": bolt_dia_in,
            "operation": "PUNCH",
        })
    return holes


def generate_stop_list(
    members: list[dict],
    output_path: str | Path | None = None,
) -> dict:
    """Generate a stop-list CSV from takeoff member + connection data.

    Args:
        members: Takeoff member dicts. Each should have:
            mark, shape, size, bolt_count (from Phase 2 detail_vision),
            member_depth_in (optional, derived from shape if absent).
        output_path: If provided, write CSV here.

    Returns:
        {
            "success": bool,
            "csv_string": str,
            "output_path": str,
            "hole_count": int,
            "member_count": int,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["MemberMark", "HoleNum", "X_inches", "Y_inches",
                      "Dia", "Operation"])

    total_holes = 0
    members_with_holes = 0

    for m in members:
        mark = m.get("mark", "UNMARKED")
        bolt_count = int(m.get("bolt_count", 0) or 0)
        if bolt_count <= 0:
            continue

        depth = float(m.get("member_depth_in", 0) or 0)
        if depth <= 0:
            # Derive from shape name (e.g., W14X22 -> 14 inches)
            shape = str(m.get("shape", "") or "") + str(m.get("size", "") or "")
            try:
                import re
                dm = re.search(r"(\d+(?:\.\d+)?)", shape)
                depth = float(dm.group(1)) if dm else 14.0
            except Exception:
                depth = 14.0

        bolt_dia = float(m.get("bolt_dia_in", 0.8125) or 0.8125)
        holes = _default_bolt_layout(bolt_count, depth, bolt_dia)

        for h in holes:
            writer.writerow([
                mark,
                h["hole_num"],
                h["x_in"],
                h["y_in"],
                h["dia_in"],
                h["operation"],
            ])
            total_holes += 1
        members_with_holes += 1

    csv_str = buf.getvalue()

    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(csv_str, encoding="utf-8")
        out_path = str(p)

    return {
        "success": True,
        "csv_string": csv_str,
        "output_path": out_path,
        "hole_count": total_holes,
        "member_count": members_with_holes,
        "warnings": warnings,
    }
