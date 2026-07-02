"""
Your Company Virtual Office - Local STL Generator

Generates actual 3D STL files for structural steel shapes using AISC dimensions.
ZERO AI - pure parametric geometry from the AISC shape database.

W14x82 → real I-beam cross-section extruded to length → binary STL file.

Usage:
    from bridge.stl_generator import generate_stl
    result = generate_stl("W14x82", length_ft=20)
    # Returns {"path": "output/W14x82_20ft.stl", "triangles": 36, "size_bytes": ...}
"""

import struct, os, sys
from pathlib import Path
from datetime import datetime, timezone


def _get_stl_output_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "output"
    return Path(__file__).resolve().parent.parent / "output"

# ══════════════════════════════════════════════════════════════════
# AISC W-SHAPE DATABASE (common shapes - dimensions in inches)
# Source: AISC Steel Construction Manual, 16th Edition
# Fields: depth, flange_width, flange_thickness, web_thickness, weight_per_ft
# ══════════════════════════════════════════════════════════════════

AISC_W_SHAPES = {
    # Shape:      (depth,  bf,    tf,    tw,    wt/ft)
    "W4x13":      (4.16,   4.060, 0.345, 0.280, 13),
    "W6x9":       (5.90,   3.940, 0.215, 0.170, 9),
    "W6x15":      (5.99,   5.990, 0.260, 0.230, 15),
    "W6x25":      (6.38,   6.080, 0.455, 0.320, 25),
    "W8x10":      (7.89,   3.940, 0.205, 0.170, 10),
    "W8x18":      (8.14,   5.250, 0.330, 0.230, 18),
    "W8x24":      (7.93,   6.495, 0.400, 0.245, 24),
    "W8x31":      (8.00,   7.995, 0.435, 0.285, 31),
    "W8x40":      (8.25,   8.070, 0.560, 0.360, 40),
    "W8x48":      (8.50,   8.110, 0.685, 0.400, 48),
    "W8x67":      (9.00,   8.280, 0.935, 0.570, 67),
    "W10x12":     (9.87,   3.960, 0.210, 0.190, 12),
    "W10x22":     (10.17,  5.750, 0.360, 0.240, 22),
    "W10x33":     (9.73,   7.960, 0.435, 0.290, 33),
    "W10x49":     (9.98,   10.00, 0.560, 0.340, 49),
    "W10x68":     (10.40,  10.13, 0.770, 0.470, 68),
    "W10x100":    (11.10,  10.34, 1.120, 0.680, 100),
    "W12x14":     (11.91,  3.970, 0.225, 0.200, 14),
    "W12x22":     (12.31,  4.030, 0.425, 0.260, 22),
    "W12x26":     (12.22,  6.490, 0.380, 0.230, 26),
    "W12x35":     (12.50,  6.560, 0.520, 0.300, 35),
    "W12x50":     (12.19,  8.080, 0.640, 0.370, 50),
    "W12x65":     (12.12,  12.00, 0.605, 0.390, 65),
    "W12x87":     (12.53,  12.13, 0.810, 0.515, 87),
    "W12x106":    (12.89,  12.22, 0.990, 0.610, 106),
    "W12x152":    (13.71,  12.48, 1.400, 0.870, 152),
    "W14x22":     (13.74,  5.000, 0.335, 0.230, 22),
    "W14x30":     (13.84,  6.730, 0.385, 0.270, 30),
    "W14x38":     (14.10,  6.770, 0.515, 0.310, 38),
    "W14x48":     (13.79,  8.030, 0.595, 0.340, 48),
    "W14x53":     (13.92,  8.060, 0.660, 0.370, 53),
    "W14x61":     (13.89,  9.995, 0.645, 0.375, 61),
    "W14x68":     (14.04,  10.04, 0.720, 0.415, 68),
    "W14x74":     (14.17,  10.07, 0.785, 0.450, 74),
    "W14x82":     (14.31,  10.13, 0.855, 0.510, 82),
    "W14x90":     (14.02,  14.52, 0.710, 0.440, 90),
    "W14x99":     (14.16,  14.57, 0.780, 0.485, 99),
    "W14x109":    (14.32,  14.61, 0.860, 0.525, 109),
    "W14x120":    (14.48,  14.67, 0.940, 0.590, 120),
    "W14x132":    (14.66,  14.73, 1.030, 0.645, 132),
    "W14x145":    (14.78,  15.50, 1.090, 0.680, 145),
    "W14x159":    (14.98,  15.57, 1.190, 0.745, 159),
    "W14x176":    (15.22,  15.65, 1.310, 0.830, 176),
    "W14x193":    (15.48,  15.71, 1.440, 0.890, 193),
    "W14x211":    (15.72,  15.80, 1.560, 0.980, 211),
    "W14x233":    (16.04,  15.89, 1.720, 1.070, 233),
    "W14x257":    (16.38,  15.99, 1.890, 1.175, 257),
    "W14x283":    (16.74,  16.11, 2.070, 1.290, 283),
    "W14x311":    (17.12,  16.23, 2.260, 1.410, 311),
    "W14x342":    (17.54,  16.36, 2.470, 1.540, 342),
    "W14x370":    (17.92,  16.48, 2.660, 1.660, 370),
    "W14x398":    (18.29,  16.59, 2.845, 1.770, 398),
    "W14x426":    (18.67,  16.70, 3.035, 1.875, 426),
    "W14x455":    (19.02,  16.83, 3.210, 2.015, 455),
    "W14x500":    (19.60,  17.01, 3.500, 2.190, 500),
    "W16x26":     (15.69,  5.500, 0.345, 0.250, 26),
    "W16x36":     (15.86,  6.985, 0.430, 0.295, 36),
    "W16x40":     (16.01,  6.995, 0.505, 0.305, 40),
    "W16x50":     (16.26,  7.070, 0.630, 0.380, 50),
    "W16x57":     (16.43,  7.120, 0.715, 0.430, 57),
    "W16x67":     (16.33,  10.24, 0.665, 0.395, 67),
    "W16x77":     (16.52,  10.30, 0.760, 0.455, 77),
    "W16x89":     (16.75,  10.37, 0.875, 0.525, 89),
    "W16x100":    (16.97,  10.43, 0.985, 0.585, 100),
    "W18x35":     (17.70,  6.000, 0.425, 0.300, 35),
    "W18x40":     (17.90,  6.015, 0.525, 0.315, 40),
    "W18x46":     (18.06,  6.060, 0.605, 0.360, 46),
    "W18x50":     (17.99,  7.495, 0.570, 0.355, 50),
    "W18x55":     (18.11,  7.530, 0.630, 0.390, 55),
    "W18x60":     (18.24,  7.560, 0.695, 0.415, 60),
    "W18x65":     (18.35,  7.590, 0.750, 0.450, 65),
    "W18x71":     (18.47,  7.635, 0.810, 0.495, 71),
    "W18x76":     (18.21,  11.04, 0.680, 0.425, 76),
    "W18x86":     (18.39,  11.09, 0.770, 0.480, 86),
    "W18x97":     (18.59,  11.15, 0.870, 0.535, 97),
    "W21x44":     (20.66,  6.500, 0.450, 0.350, 44),
    "W21x50":     (20.83,  6.530, 0.535, 0.380, 50),
    "W21x57":     (21.06,  6.555, 0.650, 0.405, 57),
    "W21x62":     (20.99,  8.240, 0.615, 0.400, 62),
    "W21x68":     (21.13,  8.270, 0.685, 0.430, 68),
    "W21x73":     (21.24,  8.295, 0.740, 0.455, 73),
    "W21x83":     (21.43,  8.355, 0.835, 0.515, 83),
    "W21x101":    (21.36,  12.29, 0.800, 0.500, 101),
    "W21x111":    (21.51,  12.34, 0.875, 0.550, 111),
    "W24x55":     (23.57,  7.005, 0.505, 0.395, 55),
    "W24x62":     (23.74,  7.040, 0.590, 0.430, 62),
    "W24x68":     (23.73,  8.965, 0.585, 0.415, 68),
    "W24x76":     (23.92,  8.990, 0.680, 0.440, 76),
    "W24x84":     (24.10,  9.020, 0.770, 0.470, 84),
    "W24x94":     (24.31,  9.065, 0.875, 0.515, 94),
    "W24x104":    (24.06,  12.75, 0.750, 0.500, 104),
    "W24x117":    (24.26,  12.80, 0.850, 0.550, 117),
    "W24x131":    (24.48,  12.86, 0.960, 0.605, 131),
    "W24x146":    (24.74,  12.90, 1.090, 0.650, 146),
    "W24x162":    (25.00,  12.96, 1.220, 0.705, 162),
    "W27x84":     (26.71,  9.960, 0.640, 0.460, 84),
    "W27x94":     (26.92,  9.990, 0.745, 0.490, 94),
    "W27x102":    (27.09,  10.02, 0.830, 0.515, 102),
    "W30x90":     (29.53,  10.40, 0.610, 0.470, 90),
    "W30x99":     (29.65,  10.45, 0.670, 0.520, 99),
    "W30x108":    (29.83,  10.48, 0.760, 0.545, 108),
    "W30x116":    (30.01,  10.50, 0.850, 0.565, 116),
    "W30x124":    (30.17,  10.52, 0.930, 0.585, 124),
    "W33x118":    (32.86,  11.48, 0.740, 0.550, 118),
    "W33x130":    (33.09,  11.51, 0.855, 0.580, 130),
    "W33x141":    (33.30,  11.54, 0.960, 0.605, 141),
    "W33x152":    (33.49,  11.57, 1.055, 0.635, 152),
    "W36x135":    (35.55,  11.95, 0.790, 0.600, 135),
    "W36x150":    (35.85,  11.98, 0.940, 0.625, 150),
    "W36x160":    (36.01,  12.00, 1.020, 0.650, 160),
    "W36x170":    (36.17,  12.03, 1.100, 0.680, 170),
    "W36x182":    (36.33,  12.08, 1.180, 0.725, 182),
    "W36x194":    (36.49,  12.12, 1.260, 0.765, 194),
    "W36x210":    (36.69,  12.18, 1.360, 0.830, 210),
    "W36x232":    (37.12,  12.12, 1.570, 0.870, 232),
    "W36x256":    (37.43,  12.22, 1.730, 0.960, 256),
    "W36x300":    (36.74,  16.66, 1.680, 0.945, 300),
    "W40x149":    (38.20,  11.81, 0.830, 0.630, 149),
    "W40x167":    (38.59,  11.81, 1.030, 0.650, 167),
    "W40x183":    (38.98,  11.81, 1.220, 0.650, 183),
    "W40x199":    (38.67,  15.75, 1.070, 0.650, 199),
    "W40x211":    (38.84,  15.75, 1.190, 0.750, 211),
    "W40x235":    (39.69,  15.75, 1.360, 0.830, 235),
    "W40x264":    (40.00,  15.75, 1.570, 0.960, 264),
    "W40x277":    (39.69,  15.81, 1.580, 1.020, 277),
    "W40x297":    (39.84,  15.83, 1.650, 1.090, 297),
    "W40x324":    (40.16,  15.91, 1.810, 1.220, 324),
    "W40x362":    (40.55,  16.02, 2.010, 1.360, 362),
    "W40x392":    (41.57,  16.12, 2.520, 1.420, 392),
    "W40x431":    (41.26,  16.22, 2.360, 1.580, 431),
}

# HSS (Hollow Structural Sections) - common rectangular tubes
AISC_HSS_SHAPES = {
    # Shape:           (width, height, wall_thickness, wt/ft)
    "HSS4x4x1/4":     (4.0,  4.0,  0.233, 12.21),
    "HSS4x4x3/8":     (4.0,  4.0,  0.349, 17.27),
    "HSS4x4x1/2":     (4.0,  4.0,  0.465, 21.63),
    "HSS6x4x1/4":     (6.0,  4.0,  0.233, 15.62),
    "HSS6x4x3/8":     (6.0,  4.0,  0.349, 22.37),
    "HSS6x6x1/4":     (6.0,  6.0,  0.233, 19.02),
    "HSS6x6x3/8":     (6.0,  6.0,  0.349, 27.48),
    "HSS6x6x1/2":     (6.0,  6.0,  0.465, 35.24),
    "HSS8x4x1/4":     (8.0,  4.0,  0.233, 19.02),
    "HSS8x4x3/8":     (8.0,  4.0,  0.349, 27.48),
    "HSS8x6x1/4":     (8.0,  6.0,  0.233, 22.42),
    "HSS8x8x1/4":     (8.0,  8.0,  0.233, 25.82),
    "HSS8x8x3/8":     (8.0,  8.0,  0.349, 37.69),
    "HSS8x8x1/2":     (8.0,  8.0,  0.465, 48.85),
    "HSS10x6x1/4":    (10.0, 6.0,  0.233, 25.82),
    "HSS10x10x1/4":   (10.0, 10.0, 0.233, 32.63),
    "HSS10x10x3/8":   (10.0, 10.0, 0.349, 47.90),
    "HSS10x10x1/2":   (10.0, 10.0, 0.465, 62.46),
    "HSS12x8x1/4":    (12.0, 8.0,  0.233, 32.63),
    "HSS12x12x1/4":   (12.0, 12.0, 0.233, 39.43),
    "HSS12x12x3/8":   (12.0, 12.0, 0.349, 58.10),
    "HSS12x12x1/2":   (12.0, 12.0, 0.465, 76.07),
    "HSS16x16x1/2":   (16.0, 16.0, 0.465, 103.3),
}


import re as _re


def _get_w_shape_data(key: str):
    """Return (depth, bf, tf, tw, wt_per_ft) from AISC validator (Hard Rule #5).

    Tries the validator first (2,299 shapes). Falls back to local dict for
    shapes the validator can't locate, so frozen-mode stays usable.
    """
    try:
        from bridge.aisc_validator import validate_shape as _vs
        norm_key = key.upper().replace("x", "X")
        vr = _vs(norm_key)
        if vr.get("valid"):
            d = vr["data"]
            depth = d.get("d_in")
            bf    = d.get("bf_in")
            tf    = d.get("tf_in")
            tw    = d.get("tw_in")
            wt    = d.get("lb_per_ft")
            if all(v is not None and v == v for v in (depth, bf, tf, tw, wt)):
                return (float(depth), float(bf), float(tf), float(tw), float(wt))
    except Exception:
        pass
    # Fallback: local 157-shape dict
    norm = key.strip().replace("×", "x").replace(" ", "")
    if norm[:1].isalpha():
        norm = norm[0].upper() + norm[1:]
    norm = norm.replace("X", "x")
    return AISC_W_SHAPES.get(norm)


def _get_hss_shape_data(key: str):
    """Return (width, height, wall_t, wt_per_ft) for an HSS shape.

    Dimensions are parsed from the shape name (they encode the geometry).
    lb_per_ft comes from the AISC validator.
    Falls back to local dict if validator lookup fails.
    """
    m = _re.match(
        r"HSS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:/\d+)?(?:\.\d+)?)",
        key.upper().strip(),
    )
    if m:
        w = float(m.group(1))
        h = float(m.group(2))
        t_str = m.group(3)
        if "/" in t_str:
            num, den = t_str.split("/")
            t = float(num) / float(den)
        else:
            t = float(t_str)
        try:
            from bridge.aisc_validator import validate_shape as _vs
            vr = _vs(key.upper().strip())
            if vr.get("valid"):
                wt = vr["data"].get("lb_per_ft")
                if wt is not None and wt == wt:
                    return (w, h, t, float(wt))
        except Exception:
            pass
    # Fallback: local dict
    norm = key.strip().replace("×", "x").replace(" ", "")
    return AISC_HSS_SHAPES.get(norm)


def _write_stl_triangle(f, v1, v2, v3, normal=(0,0,1)):
    """Write one triangle to a binary STL file."""
    f.write(struct.pack('<3f', *normal))
    f.write(struct.pack('<3f', *v1))
    f.write(struct.pack('<3f', *v2))
    f.write(struct.pack('<3f', *v3))
    f.write(struct.pack('<H', 0))  # attribute byte count


def _i_beam_cross_section(d, bf, tf, tw):
    """Generate 2D cross-section points for a W-shape (I-beam).
    Returns list of (x, y) points forming the cross-section outline.
    Origin at centroid.
    """
    hd = d / 2.0    # half depth
    hbf = bf / 2.0  # half flange width
    htw = tw / 2.0  # half web thickness

    # 12-point cross section (clockwise from top-left of top flange)
    return [
        (-hbf,  hd),           # top-left of top flange
        ( hbf,  hd),           # top-right of top flange
        ( hbf,  hd - tf),      # bottom-right of top flange
        ( htw,  hd - tf),      # top-right of web
        ( htw, -hd + tf),      # bottom-right of web
        ( hbf, -hd + tf),      # top-right of bottom flange
        ( hbf, -hd),           # bottom-right of bottom flange
        (-hbf, -hd),           # bottom-left of bottom flange
        (-hbf, -hd + tf),      # top-left of bottom flange
        (-htw, -hd + tf),      # bottom-left of web
        (-htw,  hd - tf),      # top-left of web
        (-hbf,  hd - tf),      # bottom-left of top flange
    ]


def _hss_cross_section(w, h, t):
    """Generate 2D cross-section for an HSS (rectangular tube).
    Returns outer and inner rectangles.
    """
    hw, hh = w/2.0, h/2.0
    outer = [(-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh)]
    inner = [(-hw+t, hh-t), (hw-t, hh-t), (hw-t, -hh+t), (-hw+t, -hh+t)]
    return outer, inner


def _triangulate_polygon(points, z):
    """Fan triangulation of a convex-ish polygon at height z.
    Returns list of triangles as ((x,y,z), (x,y,z), (x,y,z)).
    """
    tris = []
    n = len(points)
    for i in range(1, n - 1):
        v0 = (points[0][0], points[0][1], z)
        v1 = (points[i][0], points[i][1], z)
        v2 = (points[i+1][0], points[i+1][1], z)
        tris.append((v0, v1, v2))
    return tris


def _triangulate_i_beam(d, bf, tf, tw, z):
    """Decompose I-beam cross-section into 3 convex rectangles, 2 triangles each.

    Replaces fan triangulation which fails on the non-convex 12-point I-beam
    polygon. Three-rectangle decomposition always produces correct normals.
    Returns 6 triangles per face (top flange + web + bottom flange).
    """
    hd, hbf, htw = d / 2.0, bf / 2.0, tw / 2.0

    def _rect_tris(x0, y0, x1, y1):
        a = (x0, y0, z); b = (x1, y0, z); c = (x1, y1, z); e = (x0, y1, z)
        return [(a, b, c), (a, c, e)]

    tris = []
    tris += _rect_tris(-hbf, hd - tf, hbf, hd)       # top flange
    tris += _rect_tris(-htw, -hd + tf, htw, hd - tf)  # web
    tris += _rect_tris(-hbf, -hd, hbf, -hd + tf)      # bottom flange
    return tris


def _extrude_edge(p1_2d, p2_2d, z0, z1):
    """Create two triangles for one extruded edge (side face)."""
    a = (p1_2d[0], p1_2d[1], z0)
    b = (p2_2d[0], p2_2d[1], z0)
    c = (p2_2d[0], p2_2d[1], z1)
    d = (p1_2d[0], p1_2d[1], z1)
    return [(a, b, c), (a, c, d)]


def generate_w_shape_stl(shape_name: str, length_ft: float = 20.0) -> dict:
    """Generate a binary STL file for a W-shape (I-beam) member.

    Args:
        shape_name: AISC designation like "W14x82"
        length_ft: Member length in feet

    Returns:
        dict with path, shape_data, triangles, size_bytes
    """
    key = shape_name.strip().replace("×", "x").replace(" ", "")
    if key[:1].isalpha():
        key = key[0].upper() + key[1:]
    key = key.replace("X", "x")

    # Fix 11: query AISC validator first (2,299 shapes), local dict fallback
    dims = _get_w_shape_data(key)
    if dims is None:
        # Try case-insensitive partial match against local dict
        matches = [k for k in AISC_W_SHAPES if key.lower() in k.lower()]
        if matches:
            dims = AISC_W_SHAPES[matches[0]]
            key = matches[0]
        else:
            return {"error": f"Shape '{shape_name}' not found in AISC v16.0 database."}

    d, bf, tf, tw, wt = dims
    length_in = length_ft * 12.0

    # Cross-section outline (12 points) - used for side face extrusion
    cs = _i_beam_cross_section(d, bf, tf, tw)

    triangles = []

    # Fix 13: 3-rectangle decomposition - correct for non-convex I-beam polygon
    front_tris = _triangulate_i_beam(d, bf, tf, tw, 0)
    triangles.extend(front_tris)

    back_tris = _triangulate_i_beam(d, bf, tf, tw, length_in)
    triangles.extend([(t[0], t[2], t[1]) for t in back_tris])

    # Side faces - extrude each edge
    n = len(cs)
    for i in range(n):
        p1 = cs[i]
        p2 = cs[(i + 1) % n]
        side_tris = _extrude_edge(p1, p2, 0, length_in)
        triangles.extend(side_tris)

    # Write binary STL
    out_dir = _get_stl_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{key}_{int(length_ft)}ft.stl"
    stl_path = out_dir / filename

    with open(str(stl_path), 'wb') as f:
        # Header (80 bytes)
        header = f"YourCo STL - {key} {length_ft}ft - {datetime.now(timezone.utc).isoformat()}"
        f.write(header.encode('ascii').ljust(80, b'\0')[:80])
        # Number of triangles
        f.write(struct.pack('<I', len(triangles)))
        # Write each triangle
        for tri in triangles:
            # Calculate normal (cross product)
            v0, v1, v2 = tri
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            nx = e1[1]*e2[2] - e1[2]*e2[1]
            ny = e1[2]*e2[0] - e1[0]*e2[2]
            nz = e1[0]*e2[1] - e1[1]*e2[0]
            mag = (nx*nx + ny*ny + nz*nz) ** 0.5
            if mag > 0:
                nx, ny, nz = nx/mag, ny/mag, nz/mag
            _write_stl_triangle(f, v0, v1, v2, (nx, ny, nz))

    size = stl_path.stat().st_size
    weight_total = wt * length_ft

    return {
        "path": str(stl_path),
        "filename": filename,
        "shape": key,
        "dimensions": {
            "depth_in": d, "flange_width_in": bf,
            "flange_thickness_in": tf, "web_thickness_in": tw,
            "length_ft": length_ft, "length_in": length_in,
        },
        "weight": {
            "per_foot_lbs": wt,
            "total_lbs": round(weight_total, 1),
            "total_tons": round(weight_total / 2000, 3),
        },
        "stl_info": {
            "triangles": len(triangles),
            "size_bytes": size,
            "format": "binary STL",
        },
        "message": f"Generated {key} column. {length_ft}ft long, {round(weight_total)}lbs ({round(weight_total/2000, 3)} tons). STL saved to output/{filename}",
    }


def generate_hss_stl(shape_name: str, length_ft: float = 20.0) -> dict:
    """Generate STL for an HSS hollow rectangular tube member.

    Fix 12: renders as proper hollow tube (outer sides + inner sides +
    ring end caps). Previous version was a solid prism.
    Fix 11: dimensions from shape name, lb/ft from AISC validator.
    """
    key = shape_name.strip().replace("×", "x").replace(" ", "")

    # Fix 11: get dims from validator-assisted lookup
    dims = _get_hss_shape_data(key)
    if dims is None:
        # Case-insensitive fallback against local dict
        matches = [k for k in AISC_HSS_SHAPES if key.upper() == k.upper()]
        if matches:
            dims = AISC_HSS_SHAPES[matches[0]]
            key = matches[0]
        else:
            return {"error": f"HSS shape '{shape_name}' not found in AISC v16.0 database."}

    w, h, t, wt = dims
    length_in = length_ft * 12.0
    outer, inner = _hss_cross_section(w, h, t)
    n = len(outer)

    triangles = []

    # Outer side faces (4 edges)
    for i in range(n):
        triangles.extend(_extrude_edge(outer[i], outer[(i+1)%n], 0, length_in))

    # Inner side faces - reversed winding so normals point inward (toward hollow)
    for i in range(n):
        raw = _extrude_edge(inner[i], inner[(i+1)%n], 0, length_in)
        triangles.extend([(t[0], t[2], t[1]) for t in raw])

    # End cap helper: ring of 4 quads at height z, normal sign controls winding
    def _end_cap(z, reverse=False):
        for i in range(n):
            o1 = (outer[i][0], outer[i][1], z)
            o2 = (outer[(i+1)%n][0], outer[(i+1)%n][1], z)
            i1 = (inner[i][0], inner[i][1], z)
            i2 = (inner[(i+1)%n][0], inner[(i+1)%n][1], z)
            if not reverse:
                triangles.append((o1, i1, i2))
                triangles.append((o1, i2, o2))
            else:
                triangles.append((o1, i2, i1))
                triangles.append((o1, o2, i2))

    _end_cap(0.0, reverse=False)       # front (z=0)
    _end_cap(length_in, reverse=True)  # back (z=length)

    out_dir = _get_stl_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{key.replace('/', '_')}_{int(length_ft)}ft.stl"
    stl_path = out_dir / filename

    with open(str(stl_path), 'wb') as f:
        header = f"YourCo STL - {key} {length_ft}ft"
        f.write(header.encode('ascii').ljust(80, b'\0')[:80])
        f.write(struct.pack('<I', len(triangles)))
        for tri in triangles:
            v0, v1, v2 = tri
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            nx = e1[1]*e2[2] - e1[2]*e2[1]
            ny = e1[2]*e2[0] - e1[0]*e2[2]
            nz = e1[0]*e2[1] - e1[1]*e2[0]
            mag = (nx*nx + ny*ny + nz*nz) ** 0.5
            if mag > 0:
                nx, ny, nz = nx/mag, ny/mag, nz/mag
            _write_stl_triangle(f, v0, v1, v2, (nx, ny, nz))

    size = stl_path.stat().st_size
    weight_total = wt * length_ft
    return {
        "path": str(stl_path), "filename": filename, "shape": key,
        "weight": {"per_foot_lbs": wt, "total_lbs": round(weight_total, 1)},
        "stl_info": {"triangles": len(triangles), "size_bytes": size},
        "message": f"Generated {key}. {length_ft}ft, {round(weight_total)}lbs. STL saved to output/{filename}",
    }


def _write_stl_body(stl_path, header_str: str, triangles: list):
    """Shared binary STL writer - reduces duplication across shape generators."""
    with open(str(stl_path), 'wb') as f:
        f.write(header_str.encode('ascii').ljust(80, b'\0')[:80])
        f.write(struct.pack('<I', len(triangles)))
        for tri in triangles:
            v0, v1, v2 = tri
            e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            nx = e1[1]*e2[2] - e1[2]*e2[1]
            ny = e1[2]*e2[0] - e1[0]*e2[2]
            nz = e1[0]*e2[1] - e1[1]*e2[0]
            mag = (nx*nx + ny*ny + nz*nz) ** 0.5
            if mag > 0:
                nx, ny, nz = nx/mag, ny/mag, nz/mag
            _write_stl_triangle(f, v0, v1, v2, (nx, ny, nz))


# ── L-ANGLE RENDERER ────────────────────────────────────────────────────────

def _l_angle_cross_section(leg_a: float, leg_b: float, t: float) -> list:
    """6-point cross-section for an L-angle.

    Origin at outer bottom-left corner.
    leg_a: height of vertical leg (y-axis)
    leg_b: width of horizontal leg (x-axis)
    t: thickness (both legs assumed equal)
    """
    return [
        (0.0,   0.0),    # outer bottom-left
        (leg_b, 0.0),    # outer bottom-right
        (leg_b, t),      # top of horizontal leg, right
        (t,     t),      # inner corner
        (t,     leg_a),  # top of vertical leg, inner
        (0.0,   leg_a),  # top of vertical leg, outer
    ]


def generate_l_angle_stl(shape_name: str, length_ft: float = 20.0) -> dict:
    """Generate STL for an L-angle. Shape format: L4X4X1/2 or L4x4x0.5."""
    name = shape_name.strip().upper().replace(" ", "")
    m = _re.match(r"L(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)X(\d+(?:/\d+)?(?:\.\d+)?)", name)
    if not m:
        return {"error": f"Cannot parse L-angle '{shape_name}'. Expected format: L4X4X1/2"}

    leg_a = float(m.group(1))
    leg_b = float(m.group(2))
    t_str = m.group(3)
    t = float(t_str.split("/")[0]) / float(t_str.split("/")[1]) if "/" in t_str else float(t_str)

    # lb/ft from validator
    wt = 0.0
    try:
        from bridge.aisc_validator import validate_shape as _vs
        vr = _vs(name)
        if vr.get("valid"):
            wt = float(vr["data"].get("lb_per_ft") or 0)
    except Exception:
        pass

    cs = _l_angle_cross_section(leg_a, leg_b, t)
    length_in = length_ft * 12.0
    triangles = []

    # Front face: fan triangulate the 6-point convex(ish) section
    front = _triangulate_polygon(cs, 0.0)
    triangles.extend(front)
    back = _triangulate_polygon(cs, length_in)
    triangles.extend([(x[0], x[2], x[1]) for x in back])

    # Side faces
    n = len(cs)
    for i in range(n):
        triangles.extend(_extrude_edge(cs[i], cs[(i+1)%n], 0.0, length_in))

    out_dir = _get_stl_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace("/", "_")
    filename = f"{safe_name}_{int(length_ft)}ft.stl"
    stl_path = out_dir / filename
    _write_stl_body(stl_path, f"YourCo STL - {name} {length_ft}ft", triangles)

    size = stl_path.stat().st_size
    weight_total = wt * length_ft
    return {
        "path": str(stl_path), "filename": filename, "shape": name,
        "weight": {"per_foot_lbs": wt, "total_lbs": round(weight_total, 1)},
        "stl_info": {"triangles": len(triangles), "size_bytes": size},
        "message": f"Generated {name}. {length_ft}ft. STL saved to output/{filename}",
    }


# ── PLATE RENDERER ──────────────────────────────────────────────────────────

def generate_plate_stl(shape_name: str, length_ft: float = 20.0) -> dict:
    """Generate STL for a flat plate. Shape format: PL1/2X8 (thickness x width)."""
    name = shape_name.strip().upper().replace(" ", "")
    m = _re.match(r"PL(\d+(?:/\d+)?(?:\.\d+)?)X(\d+(?:\.\d+)?)", name)
    if not m:
        return {"error": f"Cannot parse plate '{shape_name}'. Expected format: PL1/2X8 (thicknessXwidth)"}

    t_str = m.group(1)
    t = float(t_str.split("/")[0]) / float(t_str.split("/")[1]) if "/" in t_str else float(t_str)
    w = float(m.group(2))
    length_in = length_ft * 12.0

    # Rectangular cross-section (4 points)
    cs = [(-w/2, 0.0), (w/2, 0.0), (w/2, t), (-w/2, t)]
    triangles = []

    front = _triangulate_polygon(cs, 0.0)
    triangles.extend(front)
    back = _triangulate_polygon(cs, length_in)
    triangles.extend([(x[0], x[2], x[1]) for x in back])
    n = len(cs)
    for i in range(n):
        triangles.extend(_extrude_edge(cs[i], cs[(i+1)%n], 0.0, length_in))

    # A36 plate weight: A (in2) x 0.2833 lbs/in3 x 12 in/ft
    wt_per_ft = t * w * 0.2833 * 12.0

    out_dir = _get_stl_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace("/", "_")
    filename = f"{safe_name}_{int(length_ft)}ft.stl"
    stl_path = out_dir / filename
    _write_stl_body(stl_path, f"YourCo STL - {name} {length_ft}ft", triangles)

    size = stl_path.stat().st_size
    weight_total = wt_per_ft * length_ft
    return {
        "path": str(stl_path), "filename": filename, "shape": name,
        "weight": {"per_foot_lbs": round(wt_per_ft, 2), "total_lbs": round(weight_total, 1)},
        "stl_info": {"triangles": len(triangles), "size_bytes": size},
        "message": f"Generated {name}. {length_ft}ft. STL saved to output/{filename}",
    }


# ── K-JOIST RENDERER ────────────────────────────────────────────────────────

def generate_k_joist_stl(shape_name: str, span_ft: float = 20.0) -> dict:
    """Generate STL rectangular envelope for a K-series steel joist.

    Rendered as a rectangular box the depth of the joist. More accurate
    joist geometry (chord + diagonals) requires the SJI shape database.

    Shape format: K12 or 18K5 or K-series designation.
    """
    name = shape_name.strip().upper().replace(" ", "")
    # Try to extract joist depth from designation
    # Formats: "K12", "18K5", "16K9", etc.
    dm = _re.search(r"(\d+)K", name)
    if dm:
        joist_depth_in = float(dm.group(1))
    else:
        m2 = _re.match(r"K(\d+)", name)
        joist_depth_in = float(m2.group(1)) if m2 else 12.0

    chord_height_in = 1.5   # typical top/bottom chord depth
    span_in = span_ft * 12.0

    # Rectangular envelope: joist_depth tall, chord_height wide
    # Model as the bounding envelope (top chord + approximate body)
    cs = [(-joist_depth_in/2, 0.0),
          (joist_depth_in/2, 0.0),
          (joist_depth_in/2, chord_height_in),
          (-joist_depth_in/2, chord_height_in)]

    triangles = []
    front = _triangulate_polygon(cs, 0.0)
    triangles.extend(front)
    back = _triangulate_polygon(cs, span_in)
    triangles.extend([(x[0], x[2], x[1]) for x in back])
    n = len(cs)
    for i in range(n):
        triangles.extend(_extrude_edge(cs[i], cs[(i+1)%n], 0.0, span_in))

    out_dir = _get_stl_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}_{int(span_ft)}ft.stl"
    stl_path = out_dir / filename
    _write_stl_body(stl_path, f"YourCo STL - {name} {span_ft}ft span [K-joist envelope]", triangles)

    size = stl_path.stat().st_size
    return {
        "path": str(stl_path), "filename": filename, "shape": name,
        "stl_info": {"triangles": len(triangles), "size_bytes": size},
        "message": (
            f"Generated {name} joist envelope. {span_ft}ft span, {joist_depth_in}in deep. "
            f"Envelope model - for full truss geometry contact SJI. "
            f"STL saved to output/{filename}"
        ),
    }


# ── DISPATCH ────────────────────────────────────────────────────────────────

def generate_stl(shape_name: str, length_ft: float = 20.0) -> dict:
    """Auto-detect shape type and generate STL. Fix 14: adds L, PL, K dispatch."""
    name = shape_name.strip().upper().replace(" ", "")
    if name.startswith("HSS"):
        return generate_hss_stl(shape_name, length_ft)
    elif name.startswith("W"):
        return generate_w_shape_stl(shape_name, length_ft)
    elif name.startswith("L") and _re.match(r"L\d", name):
        return generate_l_angle_stl(shape_name, length_ft)
    elif name.startswith("PL"):
        return generate_plate_stl(shape_name, length_ft)
    elif _re.search(r"\dK\d|^K\d", name):
        return generate_k_joist_stl(shape_name, length_ft)
    else:
        return {"error": (
            f"Unsupported shape type '{shape_name}'. "
            f"Supported: W-shapes (W14x82), HSS (HSS8x8x1/2), "
            f"L-angles (L4x4x1/2), Plates (PL1/2x8), K-joists (18K5)."
        )}


def list_shapes() -> dict:
    """List all available shapes in the database."""
    return {
        "w_shapes": sorted(AISC_W_SHAPES.keys()),
        "w_count": len(AISC_W_SHAPES),
        "hss_shapes": sorted(AISC_HSS_SHAPES.keys()),
        "hss_count": len(AISC_HSS_SHAPES),
        "total": len(AISC_W_SHAPES) + len(AISC_HSS_SHAPES),
        "also_supported": ["L-angles (L4X4X1/2)", "Plates (PL1/2X8)", "K-joists (18K5)"],
    }
