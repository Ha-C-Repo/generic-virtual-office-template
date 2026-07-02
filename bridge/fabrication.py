"""
Your Company Virtual Office - Fabrication Module
3D Model Generation, CNC Programming, Hydraulic Ironworker Programs

Pipeline (same T1-1 hybrid logic):
  1. Gemini reads PDF/image → extracts members, dimensions, connections
  2. Local calculators compute weights, AISC cross-sections
  3. LOCAL Python generates files (STL, DXF, G-code) - no AI needed for geometry
  4. GPT-4o handles complex spatial reasoning if needed
  5. Claude validates against specs and rules

Output formats:
  STL  - 3D printable / viewer (binary STL via numpy)
  DXF  - AutoCAD compatible (via ezdxf)
  G-code - CNC plasma, drill, router
  PDF  - Ironworker setup sheets (via reportlab or text)
"""

import csv
import io
import struct
from datetime import datetime
from pathlib import Path

import numpy as np

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


# ═══════════════════════════════════════════════════════════════════════
# AISC EXTENDED CROSS-SECTION DATABASE
# ═══════════════════════════════════════════════════════════════════════

_SECTIONS: dict | None = None

def _load_sections() -> dict:
    """Load extended AISC cross-section data (d, bf, tf, tw, k)."""
    global _SECTIONS
    if _SECTIONS is not None:
        return _SECTIONS
    _SECTIONS = {}
    csv_path = _DATA_DIR / "aisc_sections.csv"
    if not csv_path.exists():
        return _SECTIONS
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Store BOTH original and uppercase keys for case-insensitive lookup
            key = row["shape"].strip()
            entry = {
                "lb_per_ft": float(row["lb_per_ft"]),
                "family": row["family"],
                "d": float(row["d"]),       # depth (inches)
                "bf": float(row["bf"]),     # flange width (inches)
                "tf": float(row["tf"]),     # flange thickness (inches)
                "tw": float(row["tw"]),     # web thickness (inches)
                "k": float(row["k"]),       # k-distance (inches)
                "W": float(row["lb_per_ft"]),  # alias for weight
                "weight_per_foot": float(row["lb_per_ft"]),
            }
            _SECTIONS[key] = entry
            _SECTIONS[key.upper()] = entry  # W14x82 → W14X82
    return _SECTIONS


def get_section(shape: str) -> dict | None:
    """Get cross-section properties for an AISC shape."""
    sections = _load_sections()
    return sections.get(shape)


def list_sections(family: str | None = None) -> list[str]:
    """List available sections, optionally filtered by family."""
    sections = _load_sections()
    if family:
        return [s for s, d in sections.items() if d["family"] == family]
    return list(sections.keys())


# ═══════════════════════════════════════════════════════════════════════
# 3D MODEL GENERATOR - Binary STL
# ═══════════════════════════════════════════════════════════════════════

def _box_triangles(x0, y0, z0, x1, y1, z1) -> list:
    """Generate 12 triangles for an axis-aligned box.
    Returns list of (normal, v1, v2, v3) tuples.
    """
    tris = []
    # 6 faces × 2 triangles each
    faces = [
        # Bottom (z = z0)
        ((0,0,-1), (x0,y0,z0), (x1,y0,z0), (x1,y1,z0)),
        ((0,0,-1), (x0,y0,z0), (x1,y1,z0), (x0,y1,z0)),
        # Top (z = z1)
        ((0,0,1), (x0,y0,z1), (x1,y1,z1), (x1,y0,z1)),
        ((0,0,1), (x0,y0,z1), (x0,y1,z1), (x1,y1,z1)),
        # Front (y = y0)
        ((0,-1,0), (x0,y0,z0), (x1,y0,z1), (x1,y0,z0)),
        ((0,-1,0), (x0,y0,z0), (x0,y0,z1), (x1,y0,z1)),
        # Back (y = y1)
        ((0,1,0), (x0,y1,z0), (x1,y1,z0), (x1,y1,z1)),
        ((0,1,0), (x0,y1,z0), (x1,y1,z1), (x0,y1,z1)),
        # Left (x = x0)
        ((-1,0,0), (x0,y0,z0), (x0,y1,z0), (x0,y1,z1)),
        ((-1,0,0), (x0,y0,z0), (x0,y1,z1), (x0,y0,z1)),
        # Right (x = x1)
        ((1,0,0), (x1,y0,z0), (x1,y1,z1), (x1,y1,z0)),
        ((1,0,0), (x1,y0,z0), (x1,y0,z1), (x1,y1,z1)),
    ]
    return faces


def _w_shape_triangles(sec: dict, length_in: float,
                       ox: float = 0, oy: float = 0, oz: float = 0) -> list:
    """Generate triangles for a W-shape (I-beam) extruded along X axis.
    Origin at bottom-left of bottom flange.
    """
    d = sec["d"]
    bf = sec["bf"]
    tf = sec["tf"]
    tw = sec["tw"]
    L = length_in

    tris = []
    # Bottom flange
    tris.extend(_box_triangles(
        ox, oy + (bf - bf)/2, oz,
        ox + L, oy + bf, oz + tf
    ))
    # Web
    web_x = (bf - tw) / 2
    tris.extend(_box_triangles(
        ox, oy + web_x, oz + tf,
        ox + L, oy + web_x + tw, oz + d - tf
    ))
    # Top flange
    tris.extend(_box_triangles(
        ox, oy, oz + d - tf,
        ox + L, oy + bf, oz + d
    ))
    return tris


def _hss_shape_triangles(sec: dict, length_in: float,
                          ox: float = 0, oy: float = 0, oz: float = 0) -> list:
    """Generate triangles for an HSS (hollow structural section) - outer box only."""
    d = sec["d"]
    bf = sec["bf"]
    t = sec["tw"]
    L = length_in
    tris = []
    # Outer box minus inner void = 4 walls
    # Bottom wall
    tris.extend(_box_triangles(ox, oy, oz, ox+L, oy+bf, oz+t))
    # Top wall
    tris.extend(_box_triangles(ox, oy, oz+d-t, ox+L, oy+bf, oz+d))
    # Left wall
    tris.extend(_box_triangles(ox, oy, oz+t, ox+L, oy+t, oz+d-t))
    # Right wall
    tris.extend(_box_triangles(ox, oy+bf-t, oz+t, ox+L, oy+bf, oz+d-t))
    return tris


def _angle_shape_triangles(sec: dict, length_in: float,
                            ox: float = 0, oy: float = 0, oz: float = 0) -> list:
    """Generate triangles for an L-shape (angle)."""
    d = sec["d"]
    bf = sec["bf"]
    t = sec["tw"]
    L = length_in
    tris = []
    # Vertical leg
    tris.extend(_box_triangles(ox, oy, oz, ox+L, oy+t, oz+d))
    # Horizontal leg (minus overlap at corner)
    tris.extend(_box_triangles(ox, oy+t, oz, ox+L, oy+bf, oz+t))
    return tris


# ═══════════════════════════════════════════════════════════════════════
# ENDPOINT MODE - extrude an AISC section between two 3D points
# ═══════════════════════════════════════════════════════════════════════
# Slice 1 of the 3D-coordinate-extraction plan
# (.specify/specs/bid-estimating/3d-coordinate-extraction-plan.md). The legacy
# builders above extrude a section along +X from an origin (shape + length_ft +
# x/y/z). Endpoint mode sweeps the section between a member's start and end
# points, so a column placed on a grid renders vertically and a beam renders
# along its span. Coordinates are ESTIMATE-GRADE and feed the in-house QC
# viewport only; Tekla Structures remains the fabrication system of record.

def _section_profile_rects(sec: dict) -> list[tuple]:
    """Cross-section as centered sub-rectangles (u0,v0,u1,v1) in inches, with the
    section centroid at (0,0). u runs across the flange width (bf), v through the
    depth (d). Reuses the same flange/web/wall decomposition as the legacy
    axis-aligned builders so both modes describe the same steel."""
    d = sec["d"]; bf = sec["bf"]; tf = sec["tf"]; tw = sec["tw"]
    fam = sec["family"]
    hd, hb = d / 2.0, bf / 2.0
    if fam in ("W", "C"):
        return [
            (-hb, -hd, hb, -hd + tf),                    # bottom flange
            (-hb, hd - tf, hb, hd),                      # top flange
            (-tw / 2.0, -hd + tf, tw / 2.0, hd - tf),    # web
        ]
    if fam == "HSS":
        t = tw
        return [
            (-hb, -hd, hb, -hd + t),                     # bottom wall
            (-hb, hd - t, hb, hd),                       # top wall
            (-hb, -hd + t, -hb + t, hd - t),             # left wall
            (hb - t, -hd + t, hb, hd - t),               # right wall
        ]
    if fam == "L":
        t = tw
        return [
            (-hb, -hd, -hb + t, hd),                     # vertical leg
            (-hb + t, -hd, hb, -hd + t),                 # horizontal leg
        ]
    return [(-hb, -hd, hb, hd)]                          # unknown: solid bbox


def _norm3(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def _quad_tris(a, b, c, d) -> list:
    """Two STL triangles for quad a-b-c-d with a shared computed normal."""
    n = _norm3(np.cross(b - a, c - a))
    nt = (float(n[0]), float(n[1]), float(n[2]))
    return [
        (nt, tuple(map(float, a)), tuple(map(float, b)), tuple(map(float, c))),
        (nt, tuple(map(float, a)), tuple(map(float, c)), tuple(map(float, d))),
    ]


def _endpoint_member_triangles(sec: dict, start_ft, end_ft) -> list:
    """Sweep the AISC section between two 3D points (in feet). Returns STL
    triangles. A near-vertical member (column) uses global X as the in-plane
    reference; everything else uses global Z."""
    S = np.array(start_ft, dtype=float) * 12.0
    E = np.array(end_ft, dtype=float) * 12.0
    axis = E - S
    L = float(np.linalg.norm(axis))
    if L < 1e-6:
        return []
    a = axis / L
    ref = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(a, ref))) > 0.9:          # member is (near) vertical
        ref = np.array([1.0, 0.0, 0.0])
    u_axis = _norm3(ref - float(np.dot(ref, a)) * a)
    v_axis = np.cross(a, u_axis)
    tris = []
    for (u0, v0, u1, v1) in _section_profile_rects(sec):
        corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        P0 = [S + u * u_axis + v * v_axis for (u, v) in corners]
        P1 = [p + axis for p in P0]
        tris += _quad_tris(P0[0], P0[1], P0[2], P0[3])   # start cap
        tris += _quad_tris(P1[3], P1[2], P1[1], P1[0])   # end cap
        for i in range(4):                                # side walls
            j = (i + 1) % 4
            tris += _quad_tris(P0[i], P0[j], P1[j], P1[i])
    return tris


def generate_stl(members: list[dict]) -> bytes:
    """Generate binary STL from a list of steel members.

    Two member shapes are accepted:
      - Endpoint mode (Slice 1 coordinate model): {shape, start:[x,y,z],
        end:[x,y,z]} in feet. The section is swept between the two points.
      - Legacy mode: {shape, length_ft, x_ft, y_ft, z_ft}. The section is
        extruded along +X from the origin. Preserved for backward compatibility.
    Returns: binary STL bytes ready to write to file.
    """
    all_tris = []
    sections = _load_sections()

    for m in members:
        shape = m.get("shape", "")
        sec = sections.get(shape) or sections.get(shape.upper())
        if not sec:
            continue  # skip unknown shapes

        # Endpoint mode: extrude between start/end if both are present.
        if m.get("start") is not None and m.get("end") is not None:
            all_tris.extend(_endpoint_member_triangles(sec, m["start"], m["end"]))
            continue

        L = m.get("length_ft", 10) * 12  # convert to inches
        ox = m.get("x_ft", 0) * 12
        oy = m.get("y_ft", 0) * 12
        oz = m.get("z_ft", 0) * 12

        family = sec["family"]
        if family == "W":
            all_tris.extend(_w_shape_triangles(sec, L, ox, oy, oz))
        elif family == "HSS":
            all_tris.extend(_hss_shape_triangles(sec, L, ox, oy, oz))
        elif family == "L":
            all_tris.extend(_angle_shape_triangles(sec, L, ox, oy, oz))
        elif family == "C":
            # Channel = half an I-beam (one flange + web + half flange)
            all_tris.extend(_w_shape_triangles(sec, L, ox, oy, oz))

    # Write binary STL
    buf = io.BytesIO()
    header = b"Your Company Steel Model" + b"\0" * (80 - 25)
    buf.write(header)
    buf.write(struct.pack("<I", len(all_tris)))

    for normal, v1, v2, v3 in all_tris:
        buf.write(struct.pack("<3f", *normal))
        buf.write(struct.pack("<3f", *v1))
        buf.write(struct.pack("<3f", *v2))
        buf.write(struct.pack("<3f", *v3))
        buf.write(struct.pack("<H", 0))  # attribute byte count

    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
# DXF GENERATOR - AutoCAD Compatible
# ═══════════════════════════════════════════════════════════════════════

def _ensure_ezdxf():
    try:
        import ezdxf
        return ezdxf
    except ImportError:
        return None


def generate_dxf_cross_section(shape: str) -> dict:
    """Generate DXF of a single cross-section profile."""
    ezdxf = _ensure_ezdxf()
    if not ezdxf:
        return {"error": "ezdxf not installed. Run: pip install ezdxf", "path": None}

    sec = get_section(shape)
    if not sec:
        return {"error": f"Shape '{shape}' not found in AISC database", "path": None}

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    d, bf, tf, tw = sec["d"], sec["bf"], sec["tf"], sec["tw"]
    family = sec["family"]

    if family == "W":
        # Draw I-beam cross-section as polyline
        web_left = (bf - tw) / 2
        web_right = web_left + tw
        points = [
            (0, 0), (bf, 0), (bf, tf),                    # bottom flange
            (web_right, tf), (web_right, d - tf),          # right side of web
            (bf, d - tf), (bf, d), (0, d),                 # top flange
            (0, d - tf), (web_left, d - tf),               # left of top flange
            (web_left, tf), (0, tf),                       # left side of web
            (0, 0),                                        # close
        ]
        msp.add_lwpolyline(points, close=True,
                           dxfattribs={"layer": "CROSS_SECTION"})
    elif family == "HSS":
        t = tw
        # Outer rectangle
        msp.add_lwpolyline(
            [(0,0), (bf,0), (bf,d), (0,d), (0,0)],
            close=True, dxfattribs={"layer": "CROSS_SECTION"})
        # Inner rectangle (void)
        msp.add_lwpolyline(
            [(t,t), (bf-t,t), (bf-t,d-t), (t,d-t), (t,t)],
            close=True, dxfattribs={"layer": "CROSS_SECTION"})
    elif family == "L":
        t = tw
        points = [
            (0,0), (bf,0), (bf,t), (t,t),
            (t,d), (0,d), (0,0),
        ]
        msp.add_lwpolyline(points, close=True,
                           dxfattribs={"layer": "CROSS_SECTION"})
    elif family == "C":
        web_right = tw
        points = [
            (0,0), (bf,0), (bf,tf), (web_right,tf),
            (web_right,d-tf), (bf,d-tf), (bf,d), (0,d), (0,0),
        ]
        msp.add_lwpolyline(points, close=True,
                           dxfattribs={"layer": "CROSS_SECTION"})

    # Add label
    msp.add_text(shape, dxfattribs={"layer": "LABELS", "height": 0.5,
                                     "insert": (bf/2, -1.0)})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def generate_dxf_plan(members: list[dict]) -> bytes | None:
    """Generate DXF plan view of a steel layout.
    Each member: {shape, length_ft, x_ft, y_ft, rotation_deg}
    """
    ezdxf = _ensure_ezdxf()
    if not ezdxf:
        return None

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()
    sections = _load_sections()

    for m in members:
        sec = sections.get(m.get("shape", ""))
        if not sec:
            continue
        x = m.get("x_ft", 0) * 12
        y = m.get("y_ft", 0) * 12
        L = m.get("length_ft", 10) * 12
        bf = sec["bf"]
        rot = m.get("rotation_deg", 0)

        # Plan view: rectangle (length × flange width)
        points = [(x, y), (x+L, y), (x+L, y+bf), (x, y+bf), (x, y)]
        msp.add_lwpolyline(points, close=True,
                           dxfattribs={"layer": "STEEL"})
        # Member mark
        label = f"{m.get('mark', m['shape'])} ({m.get('length_ft','')}'-0\")"
        msp.add_text(label, dxfattribs={
            "layer": "LABELS", "height": 3.0,
            "insert": (x + L/2, y + bf/2),
        })

    # Title block
    msp.add_text("YOUR COMPANY - STEEL PLAN", dxfattribs={
        "layer": "TITLE", "height": 6.0, "insert": (0, -36)})
    msp.add_text(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",  # vj: local-display-ok
                 dxfattribs={"layer": "TITLE", "height": 3.0, "insert": (0, -48)})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def generate_dxf_hole_pattern(holes: list[dict],
                               plate_w: float = 0, plate_h: float = 0) -> bytes | None:
    """Generate DXF hole pattern for CNC drilling.
    Each hole: {x, y, diameter, note}
    plate_w, plate_h in inches (0 = no plate outline).
    """
    ezdxf = _ensure_ezdxf()
    if not ezdxf:
        return None

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # Plate outline
    if plate_w > 0 and plate_h > 0:
        msp.add_lwpolyline(
            [(0,0), (plate_w,0), (plate_w,plate_h), (0,plate_h), (0,0)],
            close=True, dxfattribs={"layer": "PLATE"})

    # Holes
    for h in holes:
        cx, cy = h["x"], h["y"]
        r = h.get("diameter", 0.8125) / 2  # default 13/16" std hole
        msp.add_circle((cx, cy), r, dxfattribs={"layer": "HOLES"})
        # Center mark
        msp.add_line((cx-0.25, cy), (cx+0.25, cy), dxfattribs={"layer": "CENTER"})
        msp.add_line((cx, cy-0.25), (cx, cy+0.25), dxfattribs={"layer": "CENTER"})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


def generate_dxf_cope(d: float, bf: float, cope_depth: float,
                       cope_length: float, cope_type: str = "top") -> bytes | None:
    """Generate DXF cope/notch profile for a W-shape beam end.
    cope_type: 'top', 'bottom', 'both'
    """
    ezdxf = _ensure_ezdxf()
    if not ezdxf:
        return None

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # Full beam cross-section outline
    view_length = cope_length * 2.5
    msp.add_lwpolyline(
        [(0,0), (view_length,0), (view_length,d), (0,d), (0,0)],
        close=True, dxfattribs={"layer": "BEAM"})

    # Cope cut lines
    if cope_type in ("top", "both"):
        msp.add_lwpolyline(
            [(0, d), (0, d - cope_depth), (cope_length, d - cope_depth), (cope_length, d)],
            dxfattribs={"layer": "COPE", "color": 1})  # red
        msp.add_text(f"COPE TOP: {cope_depth}\" x {cope_length}\"",
                     dxfattribs={"layer": "DIMS", "height": 0.25, "insert": (0.5, d+0.5)})

    if cope_type in ("bottom", "both"):
        msp.add_lwpolyline(
            [(0, 0), (0, cope_depth), (cope_length, cope_depth), (cope_length, 0)],
            dxfattribs={"layer": "COPE", "color": 1})
        msp.add_text(f"COPE BTM: {cope_depth}\" x {cope_length}\"",
                     dxfattribs={"layer": "DIMS", "height": 0.25, "insert": (0.5, -1.0)})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════
# CNC G-CODE GENERATOR
# ═══════════════════════════════════════════════════════════════════════

def generate_gcode_plasma(contours: list[list[tuple]], feed: int = 80,
                          kerf: float = 0.0625) -> str:
    """Generate G-code for CNC plasma table.
    contours: list of polyline paths [(x,y), (x,y), ...]
    feed: cutting feed rate IPM
    kerf: plasma kerf width (inches)
    Returns: G-code string
    """
    lines = [
        f"( Your Company - CNC Plasma Program )",
        f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",  # vj: local-display-ok
        f"( Feed: {feed} IPM  Kerf: {kerf}\" )",
        "G90 G20",  # absolute, inches
        "G28",      # home
    ]
    for i, contour in enumerate(contours):
        if not contour:
            continue
        x0, y0 = contour[0]
        lines.append(f"( Contour {i+1} )")
        lines.append(f"G00 X{x0:.4f} Y{y0:.4f}")  # rapid to start
        lines.append("M03")  # torch on
        lines.append(f"G04 P0.5")  # pierce delay
        for x, y in contour[1:]:
            lines.append(f"G01 X{x:.4f} Y{y:.4f} F{feed}")
        # Close contour
        if contour[-1] != contour[0]:
            lines.append(f"G01 X{x0:.4f} Y{y0:.4f} F{feed}")
        lines.append("M05")  # torch off

    lines.extend(["G28", "M30"])  # home, end
    return "\n".join(lines)


def generate_gcode_drill(holes: list[dict], peck: float = 0.25,
                          retract: float = 0.1, feed: int = 5) -> str:
    """Generate G-code for CNC drill.
    holes: [{x, y, diameter, depth}]
    peck: peck increment (inches)
    retract: retract height above work
    feed: drill feed IPM
    """
    lines = [
        f"( Your Company - CNC Drill Program )",
        f"( Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} )",  # vj: local-display-ok
        f"( {len(holes)} holes  Peck: {peck}\"  Feed: {feed} IPM )",
        "G90 G20",
        f"G43 H01",  # tool length comp
        f"G00 Z{retract:.4f}",
    ]
    for i, h in enumerate(holes):
        x, y = h["x"], h["y"]
        depth = h.get("depth", 1.0)
        dia = h.get("diameter", 0.8125)
        lines.append(f"( Hole {i+1}: {dia}\" dia x {depth}\" deep )")
        lines.append(f"G00 X{x:.4f} Y{y:.4f}")
        lines.append(f"G83 Z-{depth:.4f} Q{peck:.4f} R{retract:.4f} F{feed}")
        lines.append(f"G80")  # cancel canned cycle

    lines.extend(["G00 Z1.0", "G28", "M30"])
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# HYDRAULIC IRONWORKER PROGRAMS
# ═══════════════════════════════════════════════════════════════════════

# Standard punch sizes (die clearance = material thickness + 1/16")
PUNCH_SIZES = {
    "13/16": 0.8125,   # standard bolt hole for 3/4" bolt
    "15/16": 0.9375,   # standard for 7/8" bolt
    "1-1/16": 1.0625,  # standard for 1" bolt
    "1-3/16": 1.1875,  # standard for 1-1/8" bolt
    "3/4": 0.750,      # common misc
    "7/8": 0.875,
    "1": 1.000,
}

# Ironworker capacity (typical 120-ton hydraulic, e.g., Edwards, Piranha, Geka)
IRONWORKER_CAPACITY = {
    "punch_max_dia": 1.1875,    # max hole diameter (inches)
    "punch_max_thick": 1.0,     # max material thickness (inches)
    "shear_angle_max": "6x6x1/2",  # max angle size
    "shear_flat_max_w": 14.0,   # max flat bar width (inches)
    "shear_flat_max_t": 1.0,    # max flat bar thickness
    "shear_plate_max_w": 14.0,
    "shear_plate_max_t": 0.75,
    "notch_max_depth": 6.0,     # max notch depth
    "notch_max_width": 6.0,     # max notch width
    "cope_max_depth": 6.0,
}


def generate_punch_schedule(connections: list[dict]) -> dict:
    """Generate punch schedule for hydraulic ironworker.

    Each connection: {
        mark: str,          # piece mark (e.g., "B1", "C3")
        material: str,      # shape or plate (e.g., "L4x4x3/8", "PL 3/8")
        thickness: float,   # material thickness (inches)
        holes: [{x, y, diameter, bolt_size}]
    }

    Returns: {schedule: [...], setup_notes: [...], warnings: [...]}
    """
    schedule = []
    setup_notes = set()
    warnings = []
    cap = IRONWORKER_CAPACITY

    for conn in connections:
        mark = conn.get("mark", "?")
        mat = conn.get("material", "?")
        thick = conn.get("thickness", 0.375)

        for h in conn.get("holes", []):
            dia = h.get("diameter", 0.8125)
            bolt = h.get("bolt_size", "3/4")

            # Capacity check
            if dia > cap["punch_max_dia"]:
                warnings.append(
                    f"{mark}: {dia}\" hole exceeds ironworker capacity "
                    f"({cap['punch_max_dia']}\"). Use drill press or CNC.")
                continue
            if thick > cap["punch_max_thick"]:
                warnings.append(
                    f"{mark}: {thick}\" material exceeds punch capacity "
                    f"({cap['punch_max_thick']}\"). Use CNC drill.")
                continue

            # Die clearance: hole = bolt + 1/16" (AISC standard)
            std_hole = round(float(_frac(bolt)) + 0.0625, 4)
            die_size = _closest_punch(dia)

            schedule.append({
                "mark": mark,
                "material": mat,
                "thickness": thick,
                "x": h.get("x", 0),
                "y": h.get("y", 0),
                "bolt_size": bolt,
                "hole_dia": dia,
                "punch_die": die_size,
                "tonnage_est": _punch_tonnage(dia, thick),
            })
            setup_notes.add(f"Die: {die_size}\" punch + {die_size + 1/16:.4f}\" die")

    return {
        "schedule": schedule,
        "total_holes": len(schedule),
        "setup_notes": sorted(setup_notes),
        "warnings": warnings,
        "machine": "Hydraulic Ironworker (120-ton)",
    }


def generate_shear_schedule(items: list[dict]) -> dict:
    """Generate shear schedule for hydraulic ironworker.

    Each item: {mark, material, length_in, qty, thickness, width}
    Returns: {schedule: [...], setup_notes: [...], warnings: [...]}
    """
    schedule = []
    warnings = []
    cap = IRONWORKER_CAPACITY

    for item in items:
        mark = item.get("mark", "?")
        mat = item.get("material", "flat bar")
        length = item.get("length_in", 0)
        qty = item.get("qty", 1)
        thick = item.get("thickness", 0.375)
        width = item.get("width", 3.0)

        # Capacity check
        if width > cap["shear_flat_max_w"]:
            warnings.append(f"{mark}: {width}\" wide exceeds shear capacity. Use saw.")
            continue
        if thick > cap["shear_flat_max_t"]:
            warnings.append(f"{mark}: {thick}\" thick exceeds shear capacity. Use saw.")
            continue

        schedule.append({
            "mark": mark,
            "material": mat,
            "length_in": length,
            "qty": qty,
            "thickness": thick,
            "width": width,
            "total_cuts": qty,  # each piece = 1 cut
        })

    total_cuts = sum(s["total_cuts"] for s in schedule)
    return {
        "schedule": schedule,
        "total_pieces": sum(s["qty"] for s in schedule),
        "total_cuts": total_cuts,
        "est_time_min": round(total_cuts * 0.5, 1),  # ~30 sec per cut
        "warnings": warnings,
        "machine": "Hydraulic Ironworker - Shear Station",
    }


def generate_cope_schedule(members: list[dict]) -> dict:
    """Generate cope/notch schedule.

    Each member: {mark, shape, cope_type, cope_depth, cope_length, end}
    cope_type: 'top', 'bottom', 'both'
    end: 'left', 'right', 'both'
    """
    schedule = []
    warnings = []
    sections = _load_sections()
    cap = IRONWORKER_CAPACITY

    for m in members:
        shape = m.get("shape", "")
        sec = sections.get(shape)
        if not sec:
            warnings.append(f"Unknown shape: {shape}")
            continue

        cope_depth = m.get("cope_depth", sec["d"] / 3)  # default 1/3 depth
        cope_length = m.get("cope_length", sec["bf"] * 1.5)  # default 1.5 × bf
        cope_type = m.get("cope_type", "top")

        if cope_depth > cap["cope_max_depth"]:
            warnings.append(
                f"{m.get('mark','?')}: {cope_depth}\" cope depth exceeds "
                f"ironworker capacity. Use band saw + torch.")

        ends = ["left", "right"] if m.get("end") == "both" else [m.get("end", "left")]

        for end in ends:
            schedule.append({
                "mark": m.get("mark", "?"),
                "shape": shape,
                "beam_depth": sec["d"],
                "flange_width": sec["bf"],
                "web_thick": sec["tw"],
                "cope_type": cope_type,
                "cope_depth": round(cope_depth, 3),
                "cope_length": round(cope_length, 3),
                "end": end,
            })

    return {
        "schedule": schedule,
        "total_copes": len(schedule),
        "warnings": warnings,
        "machine": "Ironworker Notcher / Band Saw + Torch",
    }


# ── Helpers ────────────────────────────────────────────────────────────

def _frac(s: str) -> float:
    """Convert fraction string to float: '3/4' → 0.75"""
    if "/" in str(s):
        parts = str(s).split("/")
        return float(parts[0]) / float(parts[1])
    return float(s)


def _closest_punch(dia: float) -> float:
    """Find the closest standard punch die size."""
    sizes = sorted(PUNCH_SIZES.values())
    closest = min(sizes, key=lambda s: abs(s - dia))
    return closest


def _punch_tonnage(dia: float, thick: float) -> float:
    """Estimate punch tonnage: T = dia × thick × 80 (for A36 steel)."""
    return round(dia * thick * 80, 1)


# ═══════════════════════════════════════════════════════════════════════
# FILE OUTPUT HELPERS
# ═══════════════════════════════════════════════════════════════════════

def save_output(data: bytes | str, filename: str) -> str:
    """Save generated file to output directory. Returns the full path."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _OUTPUT_DIR / filename
    mode = "wb" if isinstance(data, bytes) else "w"
    if mode == "wb":
        with open(path, mode) as f:
            f.write(data)
    else:
        with open(path, mode, encoding="utf-8") as f:
            f.write(data)
    return str(path)


# ═══════════════════════════════════════════════════════════════════════
# REGISTRY - Available fabrication tools
# ═══════════════════════════════════════════════════════════════════════

FAB_REGISTRY = {
    "stl_model": {
        "fn": generate_stl,
        "desc": "3D STL model from member list (shape, length, position)",
        "output": ".stl",
    },
    "dxf_cross_section": {
        "fn": generate_dxf_cross_section,
        "desc": "DXF cross-section profile for a single AISC shape",
        "output": ".dxf",
    },
    "dxf_plan": {
        "fn": generate_dxf_plan,
        "desc": "DXF plan view of steel layout",
        "output": ".dxf",
    },
    "dxf_holes": {
        "fn": generate_dxf_hole_pattern,
        "desc": "DXF hole pattern for CNC drilling",
        "output": ".dxf",
    },
    "dxf_cope": {
        "fn": generate_dxf_cope,
        "desc": "DXF cope/notch detail for beam end",
        "output": ".dxf",
    },
    "gcode_plasma": {
        "fn": generate_gcode_plasma,
        "desc": "G-code for CNC plasma cutting",
        "output": ".nc",
    },
    "gcode_drill": {
        "fn": generate_gcode_drill,
        "desc": "G-code for CNC drill program",
        "output": ".nc",
    },
    "punch_schedule": {
        "fn": generate_punch_schedule,
        "desc": "Ironworker punch schedule (holes, dies, tonnage)",
        "output": ".json",
    },
    "shear_schedule": {
        "fn": generate_shear_schedule,
        "desc": "Ironworker shear schedule (cuts, lengths)",
        "output": ".json",
    },
    "cope_schedule": {
        "fn": generate_cope_schedule,
        "desc": "Cope/notch schedule with DXF details",
        "output": ".json",
    },
}
