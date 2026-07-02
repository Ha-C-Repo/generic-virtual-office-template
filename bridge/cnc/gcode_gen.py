"""G-code generator for Piranha A-series plasma tables.

Pure text output. No external dependencies. G0 = rapid move (between
holes), G1 = cut/punch. Feed rate configurable per material thickness.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Feed rates by material thickness (in/min)
FEED_RATES = {
    0.25: 120,
    0.375: 90,
    0.5: 70,
    0.625: 55,
    0.75: 45,
    1.0: 30,
}


def _pick_feed_rate(thickness_in: float) -> int:
    """Select feed rate for given thickness. Rounds up to next bracket."""
    for t in sorted(FEED_RATES.keys()):
        if thickness_in <= t:
            return FEED_RATES[t]
    return FEED_RATES[max(FEED_RATES.keys())]


def generate_gcode(
    member: dict,
    output_path: str | Path | None = None,
    thickness_in: float = 0.5,
) -> dict:
    """Generate G-code (.nc) for a single member's hole pattern.

    Args:
        member: Dict with mark, bolt_count, bolt_dia_in (optional).
        output_path: Write .nc file here if provided.
        thickness_in: Material thickness for feed rate selection.

    Returns:
        {"success": bool, "gcode": str, "output_path": str, ...}
    """
    mark = member.get("mark", "PART")
    bolt_count = int(member.get("bolt_count", 0) or 0)
    bolt_dia = float(member.get("bolt_dia_in", 0.8125) or 0.8125)
    feed = _pick_feed_rate(thickness_in)

    lines = []
    lines.append(f"( Your Company CNC - {mark} )")
    lines.append(f"( Holes: {bolt_count}, Dia: {bolt_dia}in )")
    lines.append(f"( Feed: {feed} in/min @ {thickness_in}in thick )")
    lines.append("G90 G20")          # absolute, inches
    lines.append("G0 Z1.000")        # safe height
    lines.append(f"F{feed}")

    gage = 3.0
    edge = 2.5
    spacing = 3.0
    holes_written = 0

    for i in range(bolt_count):
        x = round(gage, 4)
        y = round(edge + i * spacing, 4)
        lines.append(f"G0 X{x:.4f} Y{y:.4f}")    # rapid to hole center
        lines.append("G1 Z-0.100")                 # plunge
        lines.append("G0 Z1.000")                  # retract
        holes_written += 1

    lines.append("G0 X0.0000 Y0.0000")  # return to origin
    lines.append("M30")                  # program end
    lines.append("")

    gcode = "\n".join(lines)

    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(gcode, encoding="utf-8")
        out_path = str(p)

    return {
        "success": True,
        "gcode": gcode,
        "output_path": out_path,
        "mark": mark,
        "hole_count": holes_written,
        "feed_rate": feed,
    }
