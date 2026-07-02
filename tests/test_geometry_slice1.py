"""
Slice 1 unit coverage: endpoint-mode STL + coordinate geometry.
Run from the project root:  py -3.13 tests/test_geometry_slice1.py

No pytest dependency (the repo has none). Plain asserts; exits non-zero on the
first failure. Covers the deterministic, dependency-free pieces: endpoint STL
geometry, dimension/datum parsing, column placement, adapters, and confidence.
Live vector grid extraction is exercised by output/_scratch_grid_probe.py and
the proof run against a real framing set.
"""
import struct
import sys
from pathlib import Path

# Ensure the project root is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge.fabrication import generate_stl, list_sections, _section_profile_rects, get_section
from bridge.lift_clone import geometry as geo

_PASS = 0


def check(cond, label):
    global _PASS
    if not cond:
        raise AssertionError(f"FAIL: {label}")
    _PASS += 1
    print(f"  ok: {label}")


def parse_stl(b: bytes):
    """Return (n_tris, list[(v0,v1,v2)]) from binary STL bytes."""
    assert len(b) >= 84, "STL too short"
    n = struct.unpack("<I", b[80:84])[0]
    tris = []
    off = 84
    for _ in range(n):
        vals = struct.unpack("<12f", b[off:off + 48])
        tris.append((vals[3:6], vals[6:9], vals[9:12]))
        off += 50
    return n, tris


def bbox(tris):
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def test_endpoint_vertical_column():
    w = next(s for s in list_sections("W"))          # guaranteed present shape
    rects = _section_profile_rects(get_section(w))
    member = {"shape": w, "start": [10.0, 5.0, 0.0], "end": [10.0, 5.0, 16.0]}
    stl = generate_stl([member])
    n, tris = parse_stl(stl)
    check(len(stl) > 100, "endpoint STL is non-empty")
    check(n == 12 * len(rects), f"W column triangle count == 12*{len(rects)} (got {n})")
    x0, x1, y0, y1, z0, z1 = bbox(tris)
    # Column is vertical: Z spans the 16 ft (192 in) height; X/Y are section-sized.
    check(abs((z1 - z0) - 192.0) < 0.5, f"column height == 192 in (got {z1 - z0:.1f})")
    check((x1 - x0) < 40 and (y1 - y0) < 40, "column footprint is section-sized, not stretched")
    # Centered on the grid point (10ft,5ft) -> (120in, 60in).
    check(abs((x0 + x1) / 2 - 120.0) < 1.0, "column centered on grid X")
    check(abs((y0 + y1) / 2 - 60.0) < 1.0, "column centered on grid Y")


def test_endpoint_horizontal_beam():
    w = next(s for s in list_sections("W"))
    member = {"shape": w, "start": [0.0, 0.0, 16.0], "end": [30.0, 0.0, 16.0]}
    n, tris = parse_stl(generate_stl([member]))
    x0, x1, *_ , z0, z1 = bbox(tris)
    check(abs((x1 - x0) - 360.0) < 0.5, f"beam length == 360 in (got {x1 - x0:.1f})")


def test_legacy_mode_unchanged():
    w = next(s for s in list_sections("W"))
    legacy = {"shape": w, "length_ft": 10, "x_ft": 0, "y_ft": 0, "z_ft": 0}
    stl = generate_stl([legacy])
    n, tris = parse_stl(stl)
    x0, x1, *_ = bbox(tris)
    check(len(stl) > 100, "legacy-mode STL still non-empty")
    check(abs((x1 - x0) - 120.0) < 0.5, "legacy mode extrudes 10 ft along X (120 in)")


def test_unknown_shape_skipped():
    stl = generate_stl([{"shape": "NOTASHAPE", "start": [0, 0, 0], "end": [0, 0, 10]}])
    n, _ = parse_stl(stl)
    check(n == 0, "unknown shape yields zero triangles, no crash")


def test_dimension_parsing():
    ft = geo.parse_dimensions_ft('25\'-0" and 26\'-6" plus 14\' - 0" and 100\'-0"')
    check(25.0 in ft, "parses 25'-0\" == 25.0")
    check(26.5 in ft, "parses 26'-6\" == 26.5")
    check(14.0 in ft, "parses 14' - 0\" == 14.0")
    check(100.0 in ft, "parses 100'-0\" == 100.0")
    half = geo.parse_dimensions_ft('5\'-6 1/2"')
    check(abs(half[0] - 5.541666) < 1e-3, "parses fraction 5'-6 1/2\"")


def test_extract_levels():
    text = ["ROOF PLAN", "T.O. STEEL EL. 18'-0\"  T.O. SLAB EL. 0'-0\""]
    info = geo.extract_levels(text)
    lv = info["levels"]
    check(abs(lv.get("T.O. STEEL", 0) - 18.0) < 0.01, "T.O. Steel read at 18 ft")
    check(lv.get("T.O. SLAB", None) == 0.0, "T.O. Slab is the 0 datum")
    check(info["confidence"] in ("medium", "high"), "found steel -> medium+ confidence")


def test_extract_levels_fallback():
    info = geo.extract_levels(["no datums here at all"])
    check(info["levels"].get("T.O. STEEL") == 16.0, "nominal 16 ft eave when none found")
    check(info["needs_review"] is True, "missing datum is flagged needs_review")
    check(info["confidence"] == "low", "missing datum -> low confidence")


def test_place_columns():
    grid = {
        "x_lines": [{"label": "1", "ft": 0.0}, {"label": "2", "ft": 25.0}],
        "y_lines": [{"label": "A", "ft": 0.0}, {"label": "B", "ft": 30.0}],
        "confidence": "medium",
    }
    levels = {"levels": {"T.O. SLAB": 0.0, "T.O. STEEL": 16.0}, "confidence": "medium"}
    w = next(s for s in list_sections("W"))
    cols = [{"mark": f"C{i}", "shape": w, "member_type": "column"} for i in range(4)]
    placed = geo.place_columns(cols, grid, levels, source_sheet=5)
    check(len(placed) == 4, "2x2 grid yields 4 placed columns")
    m = placed[0]
    check(m["type"] == "column", "placed member type is column")
    check(len(m["start"]) == 3 and len(m["end"]) == 3, "each column carries 3D start/end")
    check(m["start"][2] == 0.0 and m["end"][2] == 16.0, "column runs base 0 to T.O. Steel 16")
    check(m["confidence"] == "low", "Slice-1 grid-derived placement is capped at low confidence")
    check(m["needs_review"] is True, "grid-derived column is flagged for human review")
    check(m["placement"] == "grid_intersection_unverified", "placement marked unverified, not mark-confirmed")
    check(m["source_sheet"] == 5, "source_sheet threaded through")
    check("-" in m["grid_ref"], "column records its grid intersection")
    stl_members = geo.to_stl_members(placed)
    check(len(stl_members) == 4, "adapter maps all placed columns to endpoint members")
    check(all("start" in s and "end" in s and "shape" in s for s in stl_members),
          "adapter output carries shape + endpoints")


def test_place_columns_low_confidence_propagates():
    grid = {"x_lines": [{"label": "1", "ft": 0.0}, {"label": "2", "ft": 25.0}],
            "y_lines": [{"label": "A", "ft": 0.0}, {"label": "B", "ft": 30.0}],
            "confidence": "low"}
    levels = {"levels": {"T.O. SLAB": 0.0, "T.O. STEEL": 16.0}}
    placed = geo.place_columns([{"mark": "C1", "shape": "W14X82"}], grid, levels)
    check(all(m["confidence"] == "low" for m in placed), "low-confidence grid -> low columns")
    check(all(m["needs_review"] for m in placed), "low-confidence columns flagged needs_review")


def test_confidence_helper():
    check(geo._weakest("high", "low") == "low", "_weakest(high, low) == low")
    check(geo._weakest("high", "medium") == "medium", "_weakest(high, medium) == medium")
    check(geo._weakest("high", "high") == "high", "_weakest(high, high) == high")


def test_no_pdf_is_flagged_not_guessed():
    model = geo.build_coordinate_members(pdf_path="", members=[], project_name="X")
    check(model["members"] == [], "no PDF -> no invented members")
    check(model["meta"]["needs_review"] is True, "no PDF -> needs_review")
    check(model["meta"]["source"] == "human_entry_required", "no PDF -> human entry flagged")


def test_dim_sign_subfoot_negative():
    check(abs(geo._dim_to_feet("-0", "6", None) - (-0.5)) < 1e-6, "-0'-6\" reads as -0.5 ft (sign not lost)")
    check(abs(geo._dim_to_feet("-4", "0", None) - (-4.0)) < 1e-6, "-4'-0\" reads as -4.0 ft")
    check(abs(geo._dim_to_feet("16", "0", None) - 16.0) < 1e-6, "16'-0\" reads as 16.0 ft")


def test_levels_footing_does_not_inflate_steel():
    # A below-grade footing read BEFORE the slab must not become the base datum.
    text = ["FOUNDATION PLAN", "T.O. FND EL. -4'-0\"  T.O. SLAB EL. 0'-0\"  T.O. STEEL EL. 16'-0\""]
    lv = geo.extract_levels(text)["levels"]
    check(lv.get("T.O. SLAB") == 0.0, "slab pinned to 0 even when footing seen first")
    check(abs(lv.get("T.O. STEEL", 0) - 16.0) < 0.01, "steel eave stays 16 ft, not inflated by footing depth")


def test_levels_reject_clearance_dim():
    # A clearance dim immediately after the datum must not be read as the elevation.
    text = ["ROOF PLAN", "T.O. STEEL  5'-4\" CLR  EL. 16'-0\""]
    lv = geo.extract_levels(text)["levels"]
    check(abs(lv.get("T.O. STEEL", 0) - 16.0) < 0.01, "skips 5'-4\" CLR, takes the real EL 16'-0\"")


def test_zero_length_member_dropped():
    degenerate = [{"shape": "W14X82", "type": "column", "start": [0, 0, 0], "end": [0, 0, 0]}]
    check(geo.to_stl_members(degenerate) == [], "zero-length member excluded so the rendered count stays honest")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    print(f"Running {len(tests)} Slice-1 geometry tests...\n")
    for t in tests:
        print(f"{t.__name__}:")
        t()
    print(f"\nALL GREEN: {_PASS} assertions across {len(tests)} tests.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\n{e}")
        sys.exit(1)
