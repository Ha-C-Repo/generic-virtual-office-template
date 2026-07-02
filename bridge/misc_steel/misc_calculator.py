"""
Misc Steel Calculator / Aggregator
==================================
Phase 5 of the post-parity roadmap (v3.9.0).

Aggregates the four misc-steel detector outputs (railings, stairs,
lintels, plates) into a single rollup that:

    1. Reports total misc tonnage (lbs and tons).
    2. Provides a per-category subtotal for the bid.
    3. Converts AISC misc items (stringers, lintels, posts, rails) into
       Tekla exporter input dicts so the misc steel rides into the same
       FabSuiteXMLRequest as the structural members.
    4. Exposes a single detect_misc_steel() entry point that runs all
       four detectors against the same input.

Plates are intentionally excluded from the Tekla feed for v3.9.0 because
PL is not in the AISC v16.0 set and would be rejected by the validator.
Plates appear in the bid summary as a separate line.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Iterable

log = logging.getLogger("misc_calculator")


# ---- Aggregation -----------------------------------------------------------

def aggregate_misc_steel(
    railings: list[dict] | None = None,
    stairs: list[dict] | None = None,
    lintels: list[dict] | None = None,
    plates: list[dict] | None = None,
) -> dict:
    """Combine all misc-steel detections into one rollup.

    Returns a dict with category subtotals and a grand total. Tons are
    rounded to 4 decimal places (the convention used elsewhere in
    calculators.py for steel_weight output).
    """
    railings = railings or []
    stairs = stairs or []
    lintels = lintels or []
    plates = plates or []

    railing_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in railings)
    stair_lbs = sum(float(d.get("total_weight_lbs", 0) or 0) for d in stairs)
    lintel_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in lintels)
    plate_lbs = sum(float(d.get("weight_lbs", 0) or 0) for d in plates)

    total_lbs = railing_lbs + stair_lbs + lintel_lbs + plate_lbs
    total_tons = total_lbs / 2000.0 if total_lbs else 0.0

    # Per-category warnings rollup
    warnings: list[str] = []
    for d in railings:
        for w in d.get("code_warnings", []) or []:
            warnings.append(f"[{d.get('mark')}] {w}")
    for d in stairs:
        for w in d.get("warnings", []) or []:
            warnings.append(f"[{d.get('mark')}] {w}")
    for d in lintels:
        for w in d.get("warnings", []) or []:
            warnings.append(f"[{d.get('mark')}] {w}")
    for d in plates:
        for w in d.get("warnings", []) or []:
            warnings.append(f"[{d.get('mark')}] {w}")

    return {
        "railings": {
            "items": railings,
            "count": len(railings),
            "linear_ft": round(
                sum(float(d.get("linear_ft", 0) or 0) for d in railings), 2
            ),
            "weight_lbs": round(railing_lbs, 2),
            "tons": round(railing_lbs / 2000.0, 4) if railing_lbs else 0.0,
        },
        "stairs": {
            "items": stairs,
            "count": len(stairs),
            "flights": sum(int(d.get("flights", 0) or 0) for d in stairs),
            "weight_lbs": round(stair_lbs, 2),
            "tons": round(stair_lbs / 2000.0, 4) if stair_lbs else 0.0,
        },
        "lintels": {
            "items": lintels,
            "count": len(lintels),
            "weight_lbs": round(lintel_lbs, 2),
            "tons": round(lintel_lbs / 2000.0, 4) if lintel_lbs else 0.0,
        },
        "plates": {
            "items": plates,
            "count": len(plates),
            "weight_lbs": round(plate_lbs, 2),
            "tons": round(plate_lbs / 2000.0, 4) if plate_lbs else 0.0,
        },
        "total_weight_lbs": round(total_lbs, 2),
        "total_tons": round(total_tons, 4),
        "warnings": warnings,
    }


# ---- One-call detection entry point ----------------------------------------

def detect_misc_steel(text: str | Iterable[dict],
                      page_num: int = 0) -> dict:
    """Run all four misc-steel detectors and return the aggregated rollup.

    This is the bridge-side entry point. It mirrors the per-detector
    signature so callers can pass either a single markdown string with a
    page number, or an iterable of preprocessor page dicts.
    """
    # Defer imports so the package init does not load all four modules
    # when consumers only need one detector.
    from bridge.misc_steel.railing_detector import detect_railings
    from bridge.misc_steel.stair_detector import detect_stairs
    from bridge.misc_steel.lintel_detector import detect_lintels
    from bridge.misc_steel.plate_detector import detect_plates

    railings = detect_railings(text, page_num=page_num)
    stairs = detect_stairs(text, page_num=page_num)
    lintels = detect_lintels(text, page_num=page_num)
    plates = detect_plates(text, page_num=page_num)

    return aggregate_misc_steel(
        railings=railings,
        stairs=stairs,
        lintels=lintels,
        plates=plates,
    )


# ---- Tekla exporter bridge -------------------------------------------------

def misc_to_tekla_items(rollup: dict) -> list[dict]:
    """Convert AISC-valid misc steel items to Tekla exporter input dicts.

    The Tekla exporter (bridge.exporters.tekla_xml_gen.generate_tekla_xml)
    expects items shaped like:
        {
            "mark": "L-001",
            "qty": 4,
            "shape": "L",            # family prefix
            "size": "4X4X1/4",       # remainder
            "length_in": 78.0,
            "grade": "A36",
            "lot": "MISC",
        }

    Plates are intentionally NOT returned here. The AISC validator rejects
    PL items (PL is generic, not a fixed cross section). Plates show up in
    the bid summary instead. Stair and railing items DO ride here when
    their shape is in the AISC set.

    Args:
        rollup: Output of aggregate_misc_steel().

    Returns:
        List of Tekla-shaped dicts ready for generate_tekla_xml().
    """
    items: list[dict] = []
    if not isinstance(rollup, dict):
        return items

    # ---- Lintels: AISC angles, double angles, WT, W, C ------------------
    for d in rollup.get("lintels", {}).get("items", []) or []:
        if not d.get("aisc_valid"):
            continue
        shape_full = str(d.get("shape", ""))
        family, size = _split_shape(shape_full)
        if not family or not size:
            continue
        span_ft = float(d.get("span_ft", 0) or 0)
        if span_ft <= 0:
            continue
        items.append({
            "mark": str(d.get("mark", "")) or "LINTEL",
            "qty": int(d.get("qty", 1) or 1),
            "shape": family,
            "size": size,
            "length_in": round(span_ft * 12.0, 2),
            "grade": "A36",
            "lot": "MISC-LINTEL",
        })

    # ---- Stair stringers: AISC channels primarily -----------------------
    for d in rollup.get("stairs", {}).get("items", []) or []:
        shape_full = str(d.get("stringer_shape", ""))
        family, size = _split_shape(shape_full)
        if not family or not size:
            continue
        length_ft = float(d.get("stringer_length_ft", 0) or 0)
        if length_ft <= 0:
            continue
        # Two stringers per flight is the default. flights * stringer_count.
        flights = int(d.get("flights", 1) or 1)
        per_flight = int(d.get("stringer_count", 2) or 2)
        items.append({
            "mark": f"{d.get('mark', 'STR')}-STG",
            "qty": flights * per_flight,
            "shape": family,
            "size": size,
            "length_in": round(length_ft * 12.0, 2),
            "grade": "A36",
            "lot": "MISC-STAIR",
        })

    # ---- Railings: PIPE rails as PIPE-shape items -----------------------
    # PIPE 2 in AISC uses size token "2STD". We map our nominal sizes to
    # the AISC PIPE label set. Only emit if the size is mappable.
    pipe_aisc_size = {
        "1": "1STD",
        "1-1/4": "1-1/4STD",
        "1-1/2": "1-1/2STD",
        "2": "2STD",
        "2-1/2": "2-1/2STD",
        "3": "3STD",
        "3/4": "3/4STD",
    }
    for d in rollup.get("railings", {}).get("items", []) or []:
        nom = str(d.get("rail_size", "")).strip()
        size = pipe_aisc_size.get(nom)
        if not size:
            continue
        lf = float(d.get("linear_ft", 0) or 0)
        if lf <= 0:
            continue
        # One Tekla item per rail run. Top + mid rails counted separately.
        rails_per_run = 2 if d.get("type") in ("guard", "pipe", "rail") else 1
        items.append({
            "mark": f"{d.get('mark', 'RAIL')}-TOP",
            "qty": rails_per_run,
            "shape": "PIPE",
            "size": size,
            "length_in": round(lf * 12.0, 2),
            "grade": "A53",
            "lot": "MISC-RAIL",
        })
        # Posts: nominal 2STD x post_height, qty = post_count
        post_count = int(d.get("post_count", 0) or 0)
        if post_count > 0:
            items.append({
                "mark": f"{d.get('mark', 'RAIL')}-PST",
                "qty": post_count,
                "shape": "PIPE",
                "size": "2STD",
                "length_in": round(
                    float(d.get("height_in", 42)) + 6.0, 2
                ),  # 6 inches embed below floor
                "grade": "A53",
                "lot": "MISC-RAIL",
            })

    return items


def _split_shape(full_shape: str) -> tuple[str, str]:
    """Split a full AISC shape into (family, size).

    Examples:
        "C12X20.7"   -> ("C", "12X20.7")
        "L4X4X1/4"   -> ("L", "4X4X1/4")
        "2L3X3X1/4"  -> ("2L", "3X3X1/4")
        "WT5X11"     -> ("WT", "5X11")
        "W6X9"       -> ("W", "6X9")
        "PIPE2STD"   -> ("PIPE", "2STD")
        "HSS6X6X1/4" -> ("HSS", "6X6X1/4")
    """
    if not full_shape:
        return "", ""
    s = full_shape.strip().upper().replace("\u00d7", "X")
    # Order matters: longest prefixes first to avoid mis-splits.
    prefixes = ["HSS", "PIPE", "2L", "WT", "MT", "ST", "HP", "MC", "W", "S",
                "M", "L", "C"]
    for p in prefixes:
        if s.startswith(p):
            rest = s[len(p):]
            if rest:
                return p, rest
    return "", s


# ---- Bid integration -------------------------------------------------------

def add_misc_to_bid_breakdown(bid_breakdown: dict, rollup: dict) -> dict:
    """Append a misc steel line to a bid_total breakdown dict.

    The bid_total calculator returns a "breakdown" sub-dict. This helper
    augments it with a misc_steel line that sums all four categories. It
    does NOT mutate the input. Returns a new dict.

    Used by takeoff_controller Stage 5 to surface misc tonnage on the
    bid card alongside structural tonnage.
    """
    if not isinstance(bid_breakdown, dict) or not isinstance(rollup, dict):
        return dict(bid_breakdown) if isinstance(bid_breakdown, dict) else {}
    out = dict(bid_breakdown)
    out["misc_steel_lbs"] = float(rollup.get("total_weight_lbs", 0) or 0)
    out["misc_steel_tons"] = float(rollup.get("total_tons", 0) or 0)
    out["misc_steel_railings_lbs"] = float(
        rollup.get("railings", {}).get("weight_lbs", 0) or 0
    )
    out["misc_steel_stairs_lbs"] = float(
        rollup.get("stairs", {}).get("weight_lbs", 0) or 0
    )
    out["misc_steel_lintels_lbs"] = float(
        rollup.get("lintels", {}).get("weight_lbs", 0) or 0
    )
    out["misc_steel_plates_lbs"] = float(
        rollup.get("plates", {}).get("weight_lbs", 0) or 0
    )
    return out
