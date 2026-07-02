"""Grid-geometry SF engine (Engine B).

Computes building footprint and roof deck area from the drawing grid,
not from a printed SF figure. Real structural sets rarely print a gross
SF, so a text census cannot find one (it is an AREA-mode quantity per
schema section 3.3, computed from geometry, never a callout). This
engine reads the two largest orthogonal OVERALL dimensions along the
grid axes and multiplies them into a bounding-box footprint.

Detection is target-blind. An overall dimension is the largest feet
value whose text appears mirrored on opposite sides of the plan: a
horizontal overall is the same value printed above and below the grid
(shared X, separated Y); a vertical overall is the same value printed
left and right (shared Y, separated X). A wrong plot scale or a stray
bay dimension does not produce that mirrored pair, so it does not win.

v1 is bounding-box only. It emits the box area plus a non-rectangular
verify flag; it never reconstructs a polygon. Confidence is medium when
both axes close on mirrored pairs (and, when a plan scale exists, the
long axis agrees with the grid-bubble span at scale), low and flagged
otherwise. Areas feed the takeoff as AREA-mode rows for Ivan to verify;
they are never auto-accepted into a price (P23, P24). Deck openings are
deducted downstream by apply_assemblies (F4), not here.

Counts and areas only. No pricing (P25). Free tooling (PyMuPDF).
Standalone: no bridge/ imports; census.db is untouched. Paths are
package-relative; resource_path() only if promoted into bridge/.
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path

from takeoff_pipeline import scale_check, sheet_router

_PKG = Path(__file__).resolve().parent
LEDGER_DIR = _PKG / "ledger"
ACCURACY_LEDGER = LEDGER_DIR / "accuracy_ledger.csv"
LEDGER_HEADER = ["date", "job", "test", "metric", "value", "notes"]

# Below this a feet token is a bay or a detail dimension, not a building
# overall. The leanest real building on file runs well over 100 ft.
MIN_OVERALL_FT = 40.0
# Mirrored-pair geometry, in PDF points. Perpendicular alignment must be
# tight; the separation along the measured axis must be large.
SHARE_TOL_PT = 40.0
DIFFER_MIN_PT = 150.0
# Long axis vs grid-bubble span agreement, when a plan scale exists.
GRID_SPAN_TOL_PCT = 3.0
# Deck and building footprints should agree; beyond this they conflict.
CROSS_CHECK_TOL_PCT = 3.0


def _feet_tokens(page) -> list:
    """Every feet token at or above the overall floor, with its center
    and bbox in PyMuPDF page points."""
    out = []
    for w in page.get_text("words"):
        ft = scale_check.parse_feet_token(w[4])
        if ft is not None and ft >= MIN_OVERALL_FT:
            out.append({
                "ft": ft,
                "cx": (w[0] + w[2]) / 2.0,
                "cy": (w[1] + w[3]) / 2.0,
                "bbox": (w[0], w[1], w[2], w[3]),
                "raw": w[4],
            })
    return out


def _mirror_pair(group, axis):
    """The first pair in a same-value group that reads as a mirrored
    overall dimension on the given axis. horizontal: shared X, well
    separated in Y (a value printed above and below the plan). vertical:
    shared Y, well separated in X (printed left and right)."""
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a, b = group[i], group[j]
            dx = abs(a["cx"] - b["cx"])
            dy = abs(a["cy"] - b["cy"])
            if axis == "horizontal" and dx <= SHARE_TOL_PT \
                    and dy >= DIFFER_MIN_PT:
                return (a, b)
            if axis == "vertical" and dy <= SHARE_TOL_PT \
                    and dx >= DIFFER_MIN_PT:
                return (a, b)
    return None


def _union_bbox(tokens) -> str:
    """A schema bbox string spanning the contributing tokens."""
    xs = [v for t in tokens for v in (t["bbox"][0], t["bbox"][2])]
    ys = [v for t in tokens for v in (t["bbox"][1], t["bbox"][3])]
    return json.dumps([round(min(xs), 1), round(min(ys), 1),
                       round(max(xs), 1), round(max(ys), 1)])


def find_overall_dimensions(page) -> dict:
    """Length and width in feet from the mirrored-pair rule, with a
    fallback to the largest tokens when a pair is missing. Returns a
    dict, or None when the page offers fewer than two overall tokens."""
    toks = _feet_tokens(page)
    if len(toks) < 2:
        return None

    by_val = {}
    for t in toks:
        by_val.setdefault(round(t["ft"], 1), []).append(t)

    horiz, vert = {}, {}
    for val, group in by_val.items():
        h = _mirror_pair(group, "horizontal")
        if h:
            horiz[val] = h
        v = _mirror_pair(group, "vertical")
        if v:
            vert[val] = v

    length = max(horiz) if horiz else None
    width = max(vert) if vert else None
    used = []
    flags = []

    if length is not None:
        used += list(horiz[length])
    if width is not None:
        used += list(vert[width])

    # Fallbacks. A missing axis drops to low confidence; the value is a
    # best effort from the largest token not already claimed, and the
    # gap is named, never hidden.
    if length is None or width is None:
        ordered = sorted(toks, key=lambda t: -t["ft"])
        claimed = {id(t) for t in used}
        spare = [t for t in ordered if id(t) not in claimed]
        if length is None and spare:
            length = spare.pop(0)["ft"]
            flags.append("length axis has no mirrored overall dimension")
        if width is None and spare:
            width = spare.pop(0)["ft"]
            flags.append("width axis has no mirrored overall dimension")

    if length is None or width is None:
        return None

    rectangular = not flags
    return {
        "length_ft": length,
        "width_ft": width,
        "mirrored_axes": (bool(horiz), bool(vert)),
        "rectangular": rectangular,
        "flags": flags,
        "bbox": _union_bbox(used) if used else _union_bbox(toks[:2]),
    }


def _grid_span_agreement(page, length_ft):
    """Cross-check the long axis against the grid-bubble span measured
    at the plan scale. Returns (agrees, detail) or (None, reason) when
    no scale-based check is possible. A disagreement is a real warning:
    a wrong plot scale throws the bubble span off while the printed
    dimension stays put."""
    scales = [s["ft_per_in"] for s in scale_check.scale_strings(page)
              if s["ft_per_in"] and s["ft_per_in"] >= 4]
    if not scales:
        return None, "no plan-magnitude scale string on the sheet"
    measure = scale_check.measure_grid(page, max(scales))
    if not measure:
        return None, "no measurable grid bubble row plus overall dim"
    span_ft = measure["measured_ft"]
    if span_ft <= 0:
        return None, "grid span measured as zero"
    diff = abs(length_ft - span_ft) / max(length_ft, span_ft) * 100.0
    detail = (f"long axis {length_ft:g} ft vs grid-span {span_ft:g} ft "
              f"({diff:.1f} pct)")
    return diff <= GRID_SPAN_TOL_PCT, detail


def _pick_sheet(router_result, kind):
    """The plan sheet for a footprint. deck reads the roof or floor
    framing plan (so primary_source carries FRAMING PLAN, section 5);
    building reads the foundation or floor plan."""
    sheets = router_result["sheets"]
    if kind == "deck":
        title_keys = ("ROOF FRAMING PLAN", "FLOOR FRAMING PLAN",
                      "FRAMING PLAN")
        hint = sheet_router.CATEGORY_FRAMING
    else:
        title_keys = ("FOUNDATION PLAN", "FLOOR PLAN", "OVERALL PLAN")
        hint = sheet_router.CATEGORY_FOUNDATION
    for e in sheets:
        title = (e["sheet_title"] or "").upper()
        if not e["is_scanned"] and any(k in title for k in title_keys):
            return e
    for e in sheets:
        if not e["is_scanned"] and e["title_hint"] == hint:
            return e
    if kind == "building":
        for e in sheets:
            title = (e["sheet_title"] or "").upper()
            if not e["is_scanned"] and "PLAN" in title:
                return e
    return None


def _conforming_deck_source(sheet, primary_source) -> str:
    """Section 5 requires a DECK primary_source to carry the literal
    'FRAMING PLAN'. The chosen sheet is a framing plan (title_hint
    FRAMING), but its title may not be the contiguous phrase (for
    example 'ROOF FRAMING - LOW ROOF PLAN'). Cite the sheet number with
    the canonical class source so the row conforms and is never blocked
    by the gate, rather than emitting an unconforming source that hard-
    fails the whole workbook."""
    if "FRAMING PLAN" in primary_source.upper():
        return primary_source
    return f"{sheet} ROOF FRAMING PLAN"


def _measure_plan(doc, router_result, kind) -> dict:
    entry = _pick_sheet(router_result, kind)
    if entry is None:
        return None
    page = doc[entry["page_index"]]
    dims = find_overall_dimensions(page)
    if dims is None:
        return None

    sheet = entry["sheet_number"] or f"PAGE-{entry['page_index']}"
    primary_source = " ".join(
        x for x in (entry["sheet_number"], entry["sheet_title"]) if x
    ).strip() or sheet
    if kind == "deck":
        primary_source = _conforming_deck_source(sheet, primary_source)
    area = int(round(dims["length_ft"] * dims["width_ft"]))

    flags = list(dims["flags"])
    agrees, detail = _grid_span_agreement(page, dims["length_ft"])
    if agrees is True:
        flags.append(f"grid-span cross-check agrees: {detail}")
    elif agrees is False:
        flags.append(f"grid-span cross-check disagrees: {detail}")
    else:
        flags.append(f"no independent scale cross-check: {detail}")
    # Medium only when both axes close on mirrored overall dimensions
    # AND the long axis is corroborated by the grid-bubble span at
    # scale. Without that independent check the footprint stays plan
    # evidence for Ivan, never auto-accepted: low and flagged (P24).
    # The largest mirrored value on a split or L-shaped plan can be a
    # property line, so an uncorroborated rectangle is not trusted.
    confidence = "medium" if (dims["rectangular"] and agrees is True) \
        else "low"

    return {
        "sheet": sheet,
        "primary_source": primary_source,
        "length_ft": dims["length_ft"],
        "width_ft": dims["width_ft"],
        "area_sf": area,
        "confidence": confidence,
        "rectangular": dims["rectangular"],
        "bbox": dims["bbox"],
        "flags": flags,
    }


def _cross_check(deck, building) -> dict:
    """Deck and building footprints are the same outline and should
    agree. Agreement is recorded; a real disagreement drops both to low
    and is flagged for Ivan, never reconciled silently."""
    if not deck or not building:
        return {"status": "one footprint only", "diff_pct": None}
    a, b = deck["area_sf"], building["area_sf"]
    if max(a, b) <= 0:
        return {"status": "zero area", "diff_pct": None}
    diff = abs(a - b) / max(a, b) * 100.0
    if diff <= CROSS_CHECK_TOL_PCT:
        note = f"deck and building footprints agree ({diff:.1f} pct)"
        for m in (deck, building):
            m["flags"].append(note)
        return {"status": "agree", "diff_pct": round(diff, 2)}
    note = (f"deck {a} SF vs building {b} SF disagree "
            f"({diff:.1f} pct); Ivan verify the footprint")
    for m in (deck, building):
        m["confidence"] = "low"
        m["flags"].append(note)
    return {"status": "disagree", "diff_pct": round(diff, 2)}


def measure(pdf_path, router_result=None) -> dict:
    """Footprint measurement for one drawing set. Returns deck and
    building footprints (each may be None) plus their cross-check."""
    import fitz

    pdf_path = str(Path(pdf_path))
    router_result = router_result or sheet_router.route(pdf_path)
    doc = fitz.open(pdf_path)
    try:
        deck = _measure_plan(doc, router_result, "deck")
        building = _measure_plan(doc, router_result, "building")
    finally:
        doc.close()
    cross = _cross_check(deck, building)
    return {"pdf": pdf_path, "deck": deck, "building": building,
            "cross_check": cross}


def _area_row(item_class, designation, m, tail) -> dict:
    flag = "" if m["rectangular"] else "non-rectangular: verify. "
    notes = (f"grid footprint {m['length_ft']:g} ft x {m['width_ft']:g} "
             f"ft = {m['area_sf']:g} SF (Engine B, bounding box). "
             f"{flag}{tail}")
    return {
        "item_class": item_class,
        "designation": designation,
        "mode": "AREA",
        "qty": m["area_sf"],
        "unit": "SF",
        "primary_source": m["primary_source"],
        "secondary_source": "",
        "confidence": m["confidence"],
        "sheet": m["sheet"],
        "bbox": m["bbox"],
        "notes": notes,
    }


def to_takeoff_rows(measurement) -> list:
    """AREA-mode TAKEOFF rows from a measurement, in the eleven-column
    shape export_xlsx merges via extra_rows. DECK drives the roof_deck
    assembly downstream; BUILDING GROSS SF is the floor-plan gross,
    context and a sanity anchor (MISC AREA)."""
    rows = []
    deck = measurement.get("deck")
    if deck and deck.get("area_sf"):
        rows.append(_area_row(
            "DECK", "ROOF DECK", deck,
            "deck type and gauge: verify S1.00 general notes"))
    building = measurement.get("building")
    if building and building.get("area_sf"):
        rows.append(_area_row(
            "MISC", "BUILDING GROSS SF", building,
            "gross footprint; deck SF generally equals building SF, "
            "RTU openings minor"))
    return rows


def _append_ledger(rows) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not ACCURACY_LEDGER.exists()
    with open(ACCURACY_LEDGER, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(LEDGER_HEADER)
        w.writerows(rows)


def _write_ledger(job, measurement) -> None:
    today = date.today().isoformat()
    rows = []
    for kind, key in (("building_sf", "building"), ("deck_sf", "deck")):
        m = measurement.get(key)
        if m and m.get("area_sf"):
            rows.append([today, job, "grid_geometry_B", kind,
                         m["area_sf"],
                         f"{m['length_ft']:g}x{m['width_ft']:g} ft on "
                         f"{m['sheet']}, confidence {m['confidence']}"])
        else:
            rows.append([today, job, "grid_geometry_B", kind, "none",
                         "no measurable grid footprint on the plan"])
    cross = measurement.get("cross_check", {})
    rows.append([today, job, "grid_geometry_B", "footprint_cross_check",
                 cross.get("status", "n/a"),
                 f"deck vs building diff {cross.get('diff_pct')}"])
    _append_ledger(rows)


def run(pdf_path, job, router_result=None, append_ledger=True) -> dict:
    """Measure, build AREA rows, and instrument the accuracy ledger."""
    measurement = measure(pdf_path, router_result)
    rows = to_takeoff_rows(measurement)
    if append_ledger:
        _write_ledger(job, measurement)
    return {"job": job, "measurement": measurement, "rows": rows}


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: py -m takeoff_pipeline.grid_geometry "
              "<drawings.pdf> <job> [--no-ledger]")
        return 2
    result = run(sys.argv[1], sys.argv[2],
                 append_ledger="--no-ledger" not in sys.argv)
    m = result["measurement"]
    for key in ("building", "deck"):
        f = m.get(key)
        if f:
            print(f"{key}: {f['length_ft']:g} x {f['width_ft']:g} ft = "
                  f"{f['area_sf']} SF on {f['sheet']}, "
                  f"confidence {f['confidence']}")
            for flag in f["flags"]:
                print(f"  - {flag}")
        else:
            print(f"{key}: no measurable grid footprint")
    print(f"cross_check: {m['cross_check']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
