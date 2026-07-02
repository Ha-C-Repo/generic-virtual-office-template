"""DSTV (NC1) file writer for robotic beam lines.

DSTV (Deutscher Stahlbau-Verband) is the industry standard for CNC
beam processing lines from PythonX, Ficep, Voortman, Peddinghaus.
Future-proofs Your Company for equipment upgrades.

Format: fixed-width text. Header block (ST), then operation blocks
(BO for drill/punch, SI for cut, AK for layout mark). Pure text
output with no external dependencies.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from pathlib import Path

log = logging.getLogger(__name__)

# DSTV profile code mapping (subset covering common W-shapes)
PROFILE_CODES = {
    "W": "I",    # I-beam profile
    "HSS": "RO", # rectangular/round hollow
    "L": "L",    # angle
    "C": "U",    # channel
    "WT": "T",   # tee
}


def _profile_code(shape: str) -> str:
    """Map AISC shape prefix to DSTV profile code."""
    for prefix, code in PROFILE_CODES.items():
        if shape.upper().startswith(prefix):
            return code
    return "I"


def generate_dstv(
    member: dict,
    output_path: str | Path | None = None,
) -> dict:
    """Generate a DSTV/NC1 file for a single member.

    Args:
        member: Dict with mark, shape, size, length_ft, grade,
            bolt_count, member_depth_in (optional).
        output_path: Write .nc1 file here if provided.

    Returns:
        {"success": bool, "nc1_text": str, "output_path": str, ...}
    """
    mark = member.get("mark", "PART")
    shape = str(member.get("shape", "W") or "W")
    size = str(member.get("size", "") or "")
    grade = str(member.get("grade", "A992") or "A992")
    length_mm = float(member.get("length_ft", 0) or 0) * 304.8
    bolt_count = int(member.get("bolt_count", 0) or 0)

    depth_in = float(member.get("member_depth_in", 0) or 0)
    if depth_in <= 0:
        import re
        dm = re.search(r"(\d+(?:\.\d+)?)", shape + size)
        depth_in = float(dm.group(1)) if dm else 14.0
    depth_mm = depth_in * 25.4
    flange_mm = depth_mm * 0.6

    profile = _profile_code(shape)
    full_name = f"{shape}{size}"

    lines = []
    # ST block: header
    lines.append("ST")
    lines.append(f"  {mark}")
    lines.append(f"  {full_name}")
    lines.append(f"  {grade}")
    lines.append(f"  {profile}")
    lines.append(f"  {depth_mm:.1f}")        # profile height
    lines.append(f"  {flange_mm:.1f}")       # flange width
    lines.append(f"  0.0")                    # flange thickness (approx)
    lines.append(f"  0.0")                    # web thickness (approx)
    lines.append(f"  {length_mm:.1f}")       # member length
    lines.append("EN")

    # BO blocks: bolt holes
    if bolt_count > 0:
        gage_mm = 76.2      # 3 inches
        edge_mm = 63.5      # 2.5 inches
        spacing_mm = 76.2   # 3 inches
        dia_mm = 20.6       # 13/16 inch

        lines.append("BO")
        for i in range(bolt_count):
            x = round(gage_mm, 1)
            y = round(edge_mm + i * spacing_mm, 1)
            lines.append(f"  {x:.1f}  {y:.1f}  {dia_mm:.1f}")
        lines.append("EN")

    # End
    lines.append("EN")
    lines.append("")

    nc1_text = "\n".join(lines)

    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(nc1_text, encoding="utf-8")
        out_path = str(p)

    return {
        "success": True,
        "nc1_text": nc1_text,
        "output_path": out_path,
        "mark": mark,
        "profile_code": profile,
        "length_mm": round(length_mm, 1),
        "hole_count": bolt_count,
    }
