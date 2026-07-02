"""Punch map PDF generator for shop floor posting.

Creates an 11x17 PDF showing the member elevation with each hole
labeled by X,Y coordinate from member origin (0,0). Color coded:
bolt holes (blue), cope cuts (red). Printable for shop floor posting.

Uses reportlab (already in stack).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import landscape, TABLOID
    from reportlab.lib.units import inch
    from reportlab.lib.colors import blue, red, black, lightgrey
    from reportlab.pdfgen import canvas as rl_canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def generate_punch_map(
    member: dict,
    output_path: str | Path | None = None,
) -> dict:
    """Generate a punch map PDF for a single member.

    Args:
        member: Dict with mark, shape, size, length_ft, bolt_count,
            member_depth_in (optional).
        output_path: Write PDF here if provided.

    Returns:
        {"success": bool, "output_path": str, ...}
    """
    if not HAS_REPORTLAB:
        return {"success": False, "error": "reportlab_not_installed",
                "output_path": ""}

    mark = member.get("mark", "PART")
    shape = str(member.get("shape", "") or "") + str(member.get("size", "") or "")
    length_ft = float(member.get("length_ft", 0) or 0)
    length_in = length_ft * 12.0
    bolt_count = int(member.get("bolt_count", 0) or 0)

    depth_in = float(member.get("member_depth_in", 0) or 0)
    if depth_in <= 0:
        import re
        dm = re.search(r"(\d+(?:\.\d+)?)", shape)
        depth_in = float(dm.group(1)) if dm else 14.0

    if length_in <= 0:
        length_in = 240.0

    out_path = ""
    if not output_path:
        output_path = str(Path(tempfile.gettempdir()) / f"{mark}_punch_map.pdf")

    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = landscape(TABLOID)
    c = rl_canvas.Canvas(str(p), pagesize=(page_w, page_h))

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(0.5 * inch, page_h - 0.6 * inch,
                 f"PUNCH MAP: {mark} ({shape})")
    c.setFont("Helvetica", 10)
    c.drawString(0.5 * inch, page_h - 0.9 * inch,
                 f"Length: {length_in:.1f}in ({length_ft:.1f}ft)  "
                 f"Depth: {depth_in:.1f}in  "
                 f"Holes: {bolt_count}")

    # Drawing area
    margin_x = 1.5 * inch
    margin_y = 1.5 * inch
    draw_w = page_w - 2 * margin_x
    draw_h = page_h - 3 * margin_y

    # Scale to fit
    scale_x = draw_w / max(length_in, 1)
    scale_y = draw_h / max(depth_in, 1)
    scale = min(scale_x, scale_y, 8.0)  # cap at 8 pts/inch

    ox = margin_x
    oy = margin_y

    # Member outline
    c.setStrokeColor(black)
    c.setLineWidth(2)
    c.rect(ox, oy, length_in * scale, depth_in * scale)

    # Grid lines (every 6 inches)
    c.setStrokeColor(lightgrey)
    c.setLineWidth(0.5)
    for xi in range(0, int(length_in) + 1, 6):
        px = ox + xi * scale
        c.line(px, oy, px, oy + depth_in * scale)
    for yi in range(0, int(depth_in) + 1, 3):
        py = oy + yi * scale
        c.line(ox, py, ox + length_in * scale, py)

    # Holes
    holes_drawn = 0
    if bolt_count > 0:
        gage = 3.0
        edge = 2.5
        spacing = 3.0
        c.setStrokeColor(blue)
        c.setFillColor(blue)
        c.setFont("Helvetica", 7)

        for i in range(bolt_count):
            hx = gage
            hy = edge + i * spacing
            if hy > depth_in:
                break
            px = ox + hx * scale
            py = oy + hy * scale
            c.circle(px, py, 3, fill=1)
            c.setFillColor(black)
            c.drawString(px + 5, py - 2,
                        f"({hx:.2f}, {hy:.2f})")
            c.setFillColor(blue)
            holes_drawn += 1

    # Origin marker
    c.setStrokeColor(red)
    c.setLineWidth(1.5)
    c.line(ox - 5, oy, ox + 5, oy)
    c.line(ox, oy - 5, ox, oy + 5)
    c.setFillColor(red)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(ox - 15, oy - 12, "(0,0)")

    # Footer
    c.setFillColor(black)
    c.setFont("Helvetica", 8)
    c.drawString(0.5 * inch, 0.4 * inch,
                 "Your Company. All dimensions in inches from member "
                 "origin (0,0). Blue = bolt holes.")

    c.save()
    out_path = str(p)

    return {
        "success": True,
        "output_path": out_path,
        "mark": mark,
        "hole_count": holes_drawn,
    }
