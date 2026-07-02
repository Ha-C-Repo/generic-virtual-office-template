"""
BID SANITY GATES v4 - Ivan-confirmed calibration (2026-05-27 + 2026-05-28).

Changes from v3:
  - TONNAGE_BENCHMARKS expanded from 9 to 18 building types per Ivan email
    2026-05-27. Placeholders for tilt_up, tilt_wall, medical replaced with
    empirical numbers. Added: church, fire_station, restaurant, gas_station,
    school, parking_garage, hangar, hotel, mixed_use.
  - PRICE_BENCHMARKS expanded from 9 to 18 building types. Ivan's 2026-05-27
    reply covered 12 types and his 2026-05-28 reply filled the remaining 6
    (tilt_up, fire_station, restaurant, gas_station, hangar, mixed_use).
  - PLACEHOLDER_BENCHMARKS is now empty. All 18 building types have
    Ivan-confirmed floor/mid/ceiling ranges.
  - SCOPE_CHECKLIST expanded per Ivan Q7 with Ivan-confirmed must-flag
    items for tilt-wall (embed plates, joist embeds, caged ladders, roof
    hatches, deck closures, canopy framing, lintels, sill angles, base
    plate templates, leveling nuts), multistory + mezzanine (floor deck,
    stairs and handrails, mezzanine framing), and PEMB (secondary
    framing, misc steel, canopies, roof screen framing).
  - Data is loaded from data/calibration/ivan_confirmed_2026Q2.json at
    module import. Inline values below are the fallback if the JSON is
    missing or malformed - they should match the JSON.

Gate 5 calibration status (unchanged):
  All ratio ranges are roadmap engineering defaults. Each ratio check is
  labeled calibrated=False, source="roadmap_default". Owner can supply
  real bid structural data to recalibrate. Until then, Gate 5 fires WARNs
  (not BLOCKs).
"""

from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger("bridge.bid_sanity_gates")


def _load_ivan_calibration() -> dict:
    """Load Ivan-confirmed 2026Q2 calibration from disk.

    Falls back to an empty dict if the file is missing. Each consumer
    below merges its inline default with the loaded values, so a missing
    file degrades to the v3 behavior, not a crash.
    """
    # Try the canonical path first (per CLAUDE.md path convention).
    candidates = [
        Path(__file__).resolve().parent.parent / "data" / "calibration" / "ivan_confirmed_2026Q2.json",
        Path.cwd() / "data" / "calibration" / "ivan_confirmed_2026Q2.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.warning("Could not load Ivan calibration from %s: %s", p, e)
    return {}


_IVAN = _load_ivan_calibration()


def _ivan_tonnage(bt: str, fallback: dict) -> dict:
    """Prefer Ivan's confirmed tonnage entry for `bt`, else use fallback."""
    src = _IVAN.get("tonnage_benchmarks_lb_per_sf", {}).get(bt)
    if src and "low" in src and "mid" in src and "high" in src:
        return {"low": src["low"], "mid": src["mid"], "high": src["high"]}
    return fallback


def _ivan_price(bt: str, fallback: dict) -> dict:
    src = _IVAN.get("price_benchmarks_dollar_per_sf", {}).get(bt)
    if src and "floor" in src and "mid" in src and "ceiling" in src:
        return {"floor": src["floor"], "mid": src["mid"], "ceiling": src["ceiling"]}
    return fallback


# Lbs/SF ranges. Gate 2 BLOCKs below low, targets mid, warns above high.
# Authority: Ivan L. Martinez, email 2026-05-27. See
# .specify/specs/bid-estimating/ivan-calibration-2026-05-27.md
TONNAGE_BENCHMARKS = {
    'retail_small':      _ivan_tonnage('retail_small',     {'low': 3.5,  'mid': 4.5,  'high': 5.5}),
    'retail_big_box':    _ivan_tonnage('retail_big_box',   {'low': 4.0,  'mid': 5.5,  'high': 7.0}),
    'fitness':           _ivan_tonnage('fitness',          {'low': 5.0,  'mid': 6.5,  'high': 8.0}),
    'warehouse':         _ivan_tonnage('warehouse',        {'low': 4.0,  'mid': 5.0,  'high': 6.5}),
    'office_multistory': _ivan_tonnage('office_multistory',{'low': 8.0,  'mid': 10.0, 'high': 14.0}),
    'dealership':        _ivan_tonnage('dealership',       {'low': 4.5,  'mid': 6.0,  'high': 7.5}),
    'tilt_up':           _ivan_tonnage('tilt_up',          {'low': 3.0,  'mid': 4.5,  'high': 6.0}),
    'tilt_wall':         _ivan_tonnage('tilt_wall',        {'low': 3.0,  'mid': 4.5,  'high': 6.0}),
    'medical':           _ivan_tonnage('medical',          {'low': 5.5,  'mid': 7.5,  'high': 10.0}),
    'church':            _ivan_tonnage('church',           {'low': 6.0,  'mid': 8.0,  'high': 12.0}),
    'fire_station':      _ivan_tonnage('fire_station',     {'low': 5.0,  'mid': 7.0,  'high': 9.0}),
    'restaurant':        _ivan_tonnage('restaurant',       {'low': 4.0,  'mid': 5.5,  'high': 7.0}),
    'gas_station':       _ivan_tonnage('gas_station',      {'low': 3.0,  'mid': 4.5,  'high': 6.0}),
    'school':            _ivan_tonnage('school',           {'low': 5.0,  'mid': 7.0,  'high': 9.0}),
    'parking_garage':    _ivan_tonnage('parking_garage',   {'low': 12.0, 'mid': 16.0, 'high': 22.0}),
    'hangar':            _ivan_tonnage('hangar',           {'low': 5.0,  'mid': 7.0,  'high': 10.0}),
    'hotel':             _ivan_tonnage('hotel',            {'low': 8.0,  'mid': 11.0, 'high': 15.0}),
    'mixed_use':         _ivan_tonnage('mixed_use',        {'low': 8.0,  'mid': 12.0, 'high': 16.0}),
}

# $/SF ranges. Floor BLOCKs export. Mid targets. Ceiling triggers upper warn.
# Authority: Ivan L. Martinez, emails 2026-05-27 and 2026-05-28.
# All 18 building types now have confirmed ranges. No proxies remaining.
PRICE_BENCHMARKS = {
    'retail_small':      _ivan_price('retail_small',     {'floor': 14, 'mid': 18, 'ceiling': 24}),
    'retail_big_box':    _ivan_price('retail_big_box',   {'floor': 12, 'mid': 17, 'ceiling': 22}),
    'fitness':           _ivan_price('fitness',          {'floor': 16, 'mid': 21, 'ceiling': 28}),
    'warehouse':         _ivan_price('warehouse',        {'floor': 11, 'mid': 16, 'ceiling': 22}),
    'office_multistory': _ivan_price('office_multistory',{'floor': 28, 'mid': 38, 'ceiling': 52}),
    'dealership':        _ivan_price('dealership',       {'floor': 18, 'mid': 24, 'ceiling': 32}),
    'tilt_up':           _ivan_price('tilt_up',          {'floor': 12, 'mid': 18, 'ceiling': 26}),
    'tilt_wall':         _ivan_price('tilt_wall',        {'floor': 12, 'mid': 18, 'ceiling': 25}),
    'medical':           _ivan_price('medical',          {'floor': 20, 'mid': 28, 'ceiling': 38}),
    'church':            _ivan_price('church',           {'floor': 24, 'mid': 35, 'ceiling': 50}),
    'fire_station':      _ivan_price('fire_station',     {'floor': 20, 'mid': 28, 'ceiling': 40}),
    'restaurant':        _ivan_price('restaurant',       {'floor': 16, 'mid': 22, 'ceiling': 32}),
    'gas_station':       _ivan_price('gas_station',      {'floor': 14, 'mid': 20, 'ceiling': 30}),
    'school':            _ivan_price('school',           {'floor': 18, 'mid': 26, 'ceiling': 36}),
    'parking_garage':    _ivan_price('parking_garage',   {'floor': 35, 'mid': 48, 'ceiling': 70}),
    'hangar':            _ivan_price('hangar',           {'floor': 18, 'mid': 28, 'ceiling': 42}),
    'hotel':             _ivan_price('hotel',            {'floor': 30, 'mid': 42, 'ceiling': 58}),
    'mixed_use':         _ivan_price('mixed_use',        {'floor': 22, 'mid': 35, 'ceiling': 45}),
}

# Gate 4: Scope items that MUST be present or explicitly excluded.
# Authority: Ivan email 2026-05-27 Q7. The "*_must_flag" lists are appended
# to the base checklist per building type.
_BASE_CHECKLIST = [
    'structural_columns', 'beams_girders', 'bar_joists',
    'joist_girders', 'roof_deck', 'base_plates_anchors',
    'bracing', 'misc_angles_plates',
]

# Per Ivan Q7: tilt-wall + tilt-up additions
_TILT_ADDITIONS = [
    'embed_plates', 'joist_embeds', 'caged_ladders',
    'roof_hatches_and_surrounds', 'deck_closures',
    'canopy_framing', 'lintels', 'sill_angles',
    'base_plate_templates', 'leveling_nuts',
]

# Per Ivan Q7: multistory + mezzanine additions
_MULTISTORY_ADDITIONS = [
    'floor_deck', 'stairs_handrails', 'mezzanine_framing',
]

# Per Ivan Q7: PEMB additions
_PEMB_ADDITIONS = [
    'secondary_framing', 'misc_steel', 'canopies', 'roof_screen_framing',
]

SCOPE_CHECKLIST = {
    'retail_small':      _BASE_CHECKLIST + ['canopy_framing'],
    'retail_big_box':    _BASE_CHECKLIST + ['canopy_framing'],
    'fitness':           _BASE_CHECKLIST + _MULTISTORY_ADDITIONS,
    'warehouse':         _BASE_CHECKLIST,
    'office_multistory': _BASE_CHECKLIST + _MULTISTORY_ADDITIONS,
    'dealership':        _BASE_CHECKLIST + ['canopy_framing', 'mezzanine_framing'],
    'tilt_up':           _BASE_CHECKLIST + _TILT_ADDITIONS,
    'tilt_wall':         _BASE_CHECKLIST + _TILT_ADDITIONS,
    'medical':           _BASE_CHECKLIST + ['stairs_handrails', 'canopy_framing'],
    'church':            _BASE_CHECKLIST + ['stairs_handrails'],
    'fire_station':      _BASE_CHECKLIST + ['canopy_framing'],
    'restaurant':        _BASE_CHECKLIST + ['canopy_framing'],
    'gas_station':       _BASE_CHECKLIST + ['canopy_framing'],
    'school':            _BASE_CHECKLIST + _MULTISTORY_ADDITIONS,
    'parking_garage':    _BASE_CHECKLIST + ['stairs_handrails'],
    'hangar':            _BASE_CHECKLIST + ['canopy_framing'],
    'hotel':             _BASE_CHECKLIST + _MULTISTORY_ADDITIONS,
    'mixed_use':         _BASE_CHECKLIST + _MULTISTORY_ADDITIONS,
    'PEMB':              _BASE_CHECKLIST + _PEMB_ADDITIONS,
}


# Building types whose $/SF benchmarks are placeholders. Gate3 downgrades
# BLOCK to FLAG for these. Empty set means Ivan fully confirmed all 18
# building types. Source: Ivan emails 2026-05-27 + 2026-05-28.
#
# Status as of 2026-05-28: all 18 building types have Ivan-confirmed
# floor/mid/ceiling. tilt_up, fire_station, restaurant, gas_station,
# hangar, mixed_use were filled in Ivan's 2026-05-28 reply.
PLACEHOLDER_BENCHMARKS = frozenset()


# ── Gate 5: Structural Ratio Checks ─────────────────────────────────────────
#
# Six ratios derived from structural engineering practice. These are
# ROADMAP DEFAULT ranges - not calibrated against real Your Company bid data.
# Each entry is flagged calibrated=False so the source is transparent.
# TODO: recalibrate once Owner provides column/bolt/deck counts from
# completed ICD Church, Elite Crossing, or Topgolf takeoffs.

_NON_INDUSTRIAL_TYPES = frozenset({
    'retail_small', 'retail_big_box', 'fitness',
    'office_multistory', 'dealership',
})

STRUCTURAL_RATIOS = {
    "columns_per_grid_intersection": {
        "low": 0.8,
        "high": 1.2,
        "unit": "columns/intersection",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Column count divided by grid intersection count. Below 0.8 suggests missed columns.",
    },
    "bolts_per_column": {
        "low": 3.5,
        "high": 4.5,
        "unit": "bolts/column",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Anchor bolt count divided by column count. Typical 4-bolt base plate.",
    },
    "deck_sf_per_floor": {
        "tolerance_pct": 10.0,
        "unit": "SF/floor vs building footprint",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Deck SF per floor should match building footprint within 10%.",
    },
    "joists_per_bay": {
        "spans": {
            "short": {"max_ft": 30, "low": 3, "high": 6},
            "medium": {"max_ft": 50, "low": 4, "high": 8},
            "long": {"max_ft": 999, "low": 5, "high": 10},
        },
        "unit": "joists/bay",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Joist count per bay, span-dependent. Short (<30 ft), medium (<50 ft), long (>50 ft).",
    },
    "bracing_bays_per_frame_line": {
        "low": 0.10,
        "high": 0.50,
        "unit": "bracing bays/frame line",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Bracing bay count divided by frame line count. IBC code minimum ~1 braced bay per 10 bays.",
    },
    "tons_per_sf": {
        "conventional": {"low": 5.0, "high": 8.0},
        "moment_frame": {"low": 8.0, "high": 12.0},
        "unit": "lbs/SF",
        "calibrated": False,
        "source": "roadmap_default",
        "description": "Steel intensity check. Conventional framing 5-8 lbs/SF, moment frame 8-12 lbs/SF.",
    },
}


def gate5_structural_ratios(data: dict) -> tuple[str, list, str | None]:
    """Run six structural ratio checks against roadmap-default ranges.

    Args:
        data: same dict passed to run_gates(). Keys used (all optional):
            column_count:      int
            grid_intersections:int
            bolt_count:        int
            deck_sf:           float
            floor_count:       int
            joist_count:       int
            bay_count:         int
            avg_span_ft:       float  (for joist span bucket)
            bracing_bays:      int
            frame_lines:       int
            total_tons:        float  (struct_tons + joist_tons)
            building_sf:       float
            frame_type:        str    "conventional" or "moment_frame"
            building_type:     str

    Returns:
        (status, violations, summary_warning)
        status: "PASS", "FLAG", or "DATA_UNAVAILABLE"
        violations: list of ratio dicts with name/expected/actual/status fields
        summary_warning: str or None
    """
    violations = []
    skipped = []

    # --- Ratio 1: columns per grid intersection ---
    col = data.get("column_count")
    grid = data.get("grid_intersections")
    if col is not None and grid is not None and grid > 0:
        r = col / grid
        rng = STRUCTURAL_RATIOS["columns_per_grid_intersection"]
        if r < rng["low"] or r > rng["high"]:
            violations.append({
                "ratio": "columns_per_grid_intersection",
                "actual": round(r, 2),
                "expected_low": rng["low"],
                "expected_high": rng["high"],
                "unit": rng["unit"],
                "calibrated": rng["calibrated"],
                "source": rng["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("columns_per_grid_intersection")

    # --- Ratio 2: bolts per column ---
    bolts = data.get("bolt_count")
    col2 = data.get("column_count")
    if bolts is not None and col2 is not None and col2 > 0:
        r = bolts / col2
        rng = STRUCTURAL_RATIOS["bolts_per_column"]
        if r < rng["low"] or r > rng["high"]:
            violations.append({
                "ratio": "bolts_per_column",
                "actual": round(r, 2),
                "expected_low": rng["low"],
                "expected_high": rng["high"],
                "unit": rng["unit"],
                "calibrated": rng["calibrated"],
                "source": rng["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("bolts_per_column")

    # --- Ratio 3: deck SF per floor vs building footprint ---
    deck_sf = data.get("deck_sf")
    floors = data.get("floor_count")
    bsf = data.get("building_sf")
    if deck_sf is not None and floors is not None and floors > 0 and bsf:
        per_floor = deck_sf / floors
        tol = STRUCTURAL_RATIOS["deck_sf_per_floor"]["tolerance_pct"] / 100.0
        low = bsf * (1.0 - tol)
        high = bsf * (1.0 + tol)
        if per_floor < low or per_floor > high:
            violations.append({
                "ratio": "deck_sf_per_floor",
                "actual": round(per_floor, 0),
                "expected_low": round(low, 0),
                "expected_high": round(high, 0),
                "unit": STRUCTURAL_RATIOS["deck_sf_per_floor"]["unit"],
                "calibrated": STRUCTURAL_RATIOS["deck_sf_per_floor"]["calibrated"],
                "source": STRUCTURAL_RATIOS["deck_sf_per_floor"]["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("deck_sf_per_floor")

    # --- Ratio 4: joists per bay (span-dependent) ---
    joists = data.get("joist_count")
    bays = data.get("bay_count")
    span_ft = data.get("avg_span_ft", 0)
    if joists is not None and bays is not None and bays > 0:
        r = joists / bays
        spans = STRUCTURAL_RATIOS["joists_per_bay"]["spans"]
        if span_ft <= spans["short"]["max_ft"]:
            bucket = spans["short"]
        elif span_ft <= spans["medium"]["max_ft"]:
            bucket = spans["medium"]
        else:
            bucket = spans["long"]
        if r < bucket["low"] or r > bucket["high"]:
            violations.append({
                "ratio": "joists_per_bay",
                "actual": round(r, 2),
                "expected_low": bucket["low"],
                "expected_high": bucket["high"],
                "span_bucket_ft": span_ft,
                "unit": STRUCTURAL_RATIOS["joists_per_bay"]["unit"],
                "calibrated": STRUCTURAL_RATIOS["joists_per_bay"]["calibrated"],
                "source": STRUCTURAL_RATIOS["joists_per_bay"]["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("joists_per_bay")

    # --- Ratio 5: bracing bays per frame line ---
    br_bays = data.get("bracing_bays")
    fr_lines = data.get("frame_lines")
    if br_bays is not None and fr_lines is not None and fr_lines > 0:
        r = br_bays / fr_lines
        rng = STRUCTURAL_RATIOS["bracing_bays_per_frame_line"]
        if r < rng["low"] or r > rng["high"]:
            violations.append({
                "ratio": "bracing_bays_per_frame_line",
                "actual": round(r, 3),
                "expected_low": rng["low"],
                "expected_high": rng["high"],
                "unit": rng["unit"],
                "calibrated": rng["calibrated"],
                "source": rng["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("bracing_bays_per_frame_line")

    # --- Ratio 6: tons per SF by frame type ---
    total_tons = data.get("struct_tons", 0) + data.get("joist_tons", 0)
    bsf6 = data.get("building_sf")
    frame_type = data.get("frame_type", "conventional")
    if total_tons > 0 and bsf6:
        lbs_per_sf = (total_tons * 2000.0) / bsf6
        rng6 = STRUCTURAL_RATIOS["tons_per_sf"].get(frame_type, STRUCTURAL_RATIOS["tons_per_sf"]["conventional"])
        if lbs_per_sf < rng6["low"] or lbs_per_sf > rng6["high"]:
            violations.append({
                "ratio": "tons_per_sf",
                "actual": round(lbs_per_sf, 2),
                "expected_low": rng6["low"],
                "expected_high": rng6["high"],
                "frame_type": frame_type,
                "unit": STRUCTURAL_RATIOS["tons_per_sf"]["unit"],
                "calibrated": STRUCTURAL_RATIOS["tons_per_sf"]["calibrated"],
                "source": STRUCTURAL_RATIOS["tons_per_sf"]["source"],
                "status": "FLAG",
            })
    else:
        skipped.append("tons_per_sf")

    n_checked = 6 - len(skipped)
    if n_checked == 0:
        summary = (
            "Gate 5 skipped: no structural ratio data in bid dict. "
            "Add column_count, bolt_count, deck_sf, floor_count, joist_count, "
            "bay_count, bracing_bays, frame_lines to enable checks."
        )
        return "DATA_UNAVAILABLE", [], summary

    summary = None
    if skipped:
        summary = f"Gate 5: {len(skipped)} ratio(s) skipped - data not provided: {', '.join(skipped)}"

    if violations:
        return "FLAG", violations, summary
    return "PASS", [], summary


def gate1_bay_joist_check(grid_bays, eq_spa_annotations, text_joist_count):
    """Fix: multiply joist labels by bay geometry when text undercounts."""
    if not eq_spa_annotations:
        return text_joist_count, 'LOW', 'No EQ.SPA. annotations found. Count unverified.'
    
    geo_joists_per_line = sum(max(n - 1, 0) for n in eq_spa_annotations)
    num_joist_lines = len([b for b in grid_bays if b['width'] > 20])
    geo_total = geo_joists_per_line * num_joist_lines
    
    if text_joist_count >= geo_total * 0.9:
        return text_joist_count, 'HIGH', None
    else:
        delta_pct = ((geo_total - text_joist_count) / geo_total) * 100
        return (geo_total, 'CORRECTED',
                f"Joist undercount: text={text_joist_count}, geometry={geo_total} ({delta_pct:.0f}% gap)")


def gate2_tonnage_per_sf(total_tons, building_sf, building_type):
    """Flag if steel intensity below industry norm."""
    bench = TONNAGE_BENCHMARKS.get(building_type, TONNAGE_BENCHMARKS['retail_small'])
    actual = (total_tons * 2000) / building_sf
    
    if actual >= bench['low']:
        return 'PASS', actual, None
    
    deficit = ((bench['mid'] - actual) * building_sf) / 2000
    return ('FLAG', actual,
            f"Steel intensity {actual:.1f} lbs/SF below {bench['low']} floor. "
            f"Add ~{deficit:.1f} tons to reach market midpoint ({bench['mid']} lbs/SF).")


def gate3_dollar_per_sf(total_bid, building_sf, building_type):
    """BLOCK below floor. CAUTION between floor and midpoint.

    Types in PLACEHOLDER_BENCHMARKS get BLOCK downgraded to FLAG and
    CAUTION downgraded to FLAG; their benchmarks are unconfirmed
    placeholders pending Ivan's empirical numbers. We will not block a
    real bid on a guessed range.
    """
    bench = PRICE_BENCHMARKS.get(building_type, PRICE_BENCHMARKS['retail_small'])
    actual = total_bid / building_sf
    is_placeholder = building_type in PLACEHOLDER_BENCHMARKS
    placeholder_note = " (placeholder benchmark, awaiting Ivan confirmation)" if is_placeholder else ""

    if actual >= bench['mid']:
        return 'PASS', actual, None
    elif actual >= bench['floor']:
        gap = (bench['mid'] - actual) * building_sf
        status = 'FLAG' if is_placeholder else 'CAUTION'
        return (status, actual,
                f"${actual:.2f}/SF is below market midpoint ${bench['mid']}/SF{placeholder_note}. "
                f"Consider adding ${gap:,.0f} to reach midpoint.")
    else:
        gap = (bench['floor'] - actual) * building_sf
        adjusted_bid = bench['mid'] * building_sf
        status = 'FLAG' if is_placeholder else 'BLOCK'
        prefix = "PLACEHOLDER BENCHMARK FLAG" if is_placeholder else "BLOCKED"
        tail = ("Verify benchmark with Ivan before acting." if is_placeholder
                else "DO NOT SUBMIT. Verify tonnage, rates, and scope.")
        return (status, actual,
                f"{prefix}: ${actual:.2f}/SF is below ${bench['floor']}/SF floor. "
                f"Market midpoint bid: ${adjusted_bid:,.0f} (${bench['mid']}/SF). "
                f"{tail}")


def gate4_scope_completeness(found_items, building_type):
    """Check that all expected scope items are present or explicitly excluded."""
    required = SCOPE_CHECKLIST.get(building_type, SCOPE_CHECKLIST['retail_small'])
    missing = [item for item in required if item not in found_items]
    
    if not missing:
        return 'PASS', None
    return ('FLAG', f"Missing scope items: {', '.join(missing)}. "
            f"Verify these are excluded intentionally or add to takeoff.")



def gate6_anchor_count(anchor_count, column_count, base_plate_type="simple"):
    # Gate 6: anchor rod count must be plausible vs column count.
    # Source: Ivan L. Martinez, 2026-05-25 SP183 B1 review.
    # 4 rods per simple plate, 8 per moment plate. SP183 B1 v10 had 6
    # anchors quoted for ~16 columns -> caught as BLOCK by this gate.
    if column_count is None or column_count <= 0:
        return ("LOW", anchor_count, "column_count missing or zero; cannot verify anchor count")
    per_column = 4 if (base_plate_type or "simple") == "simple" else 8
    min_required = column_count * per_column
    if anchor_count < min_required:
        deficit = min_required - anchor_count
        return ("BLOCK", anchor_count,
                "anchor_count {} below minimum {} ({} columns x {} rods/{} plate). "
                "Add {} rods or verify base-plate type. Diameter default 3/4 inch UNO.".format(
                    anchor_count, min_required, column_count, per_column, base_plate_type, deficit))
    ratio = anchor_count / float(min_required)
    if ratio > 3.0:
        return ("FLAG", anchor_count,
                "anchor_count {} is {:.1f}x the {} minimum. Plausible for heavy moment-frame; "
                "otherwise verify schedule.".format(anchor_count, ratio, min_required))
    return ("PASS", anchor_count, None)


def calculate_confidence(gate_results):
    """0-100 score. 80+ = ready to send. 60-79 = review. <60 = do not send."""
    score = 100
    for g in gate_results:
        if g['status'] == 'BLOCK':       score -= 40
        elif g['status'] == 'FLAG':      score -= 20
        elif g['status'] == 'CAUTION':   score -= 10
        elif g['status'] == 'CORRECTED': score -= 5
        # BUG-003 FIX: LOW was not penalized. Gate 1 returns LOW when there
        # are no EQ.SPA annotations (joist count unverifiable from geometry).
        # An unverified joist count is a real risk - penalize 15 points.
        elif g['status'] == 'LOW':       score -= 15
    return max(0, min(100, score))


def run_gates(data):
    """Master runner. Returns structured result with go/no-go."""
    data = dict(data)  # don't mutate caller's dict
    if "grid_bays" not in data:
        bx = data.get("bays_x", 0)
        by = data.get("bays_y", 0)
        data["grid_bays"] = (bx, by) if (bx and by) else None
    if not data["grid_bays"]:
        return {"ok": False, "error": "run_gates: needs grid_bays or (bays_x, bays_y)"}
    data.setdefault("eq_spa_annotations", [])
    data.setdefault("text_joist_count", 0)
    data.setdefault("joist_tons", 0)
    data.setdefault("found_scope_items", [])
    # struct_tons falls back to 'tons' (total structural tons from takeoff)
    data.setdefault("struct_tons", data.get("tons", 0))
    # total_bid defaults to 0 when not yet priced (gates 3 will flag as low)
    data.setdefault("total_bid", 0)

    results = []

    # Gate 1
    count, conf, w1 = gate1_bay_joist_check(
        data['grid_bays'], data['eq_spa_annotations'], data['text_joist_count'])
    results.append({'gate': 1, 'name': 'Joist Count', 'status': conf, 
                    'value': count, 'warning': w1})
    
    # Gate 2
    total_tons = data['struct_tons'] + data['joist_tons']
    s2, val2, w2 = gate2_tonnage_per_sf(total_tons, data['building_sf'], data['building_type'])
    results.append({'gate': 2, 'name': 'Tonnage/SF', 'status': s2,
                    'value': f"{val2:.1f} lbs/SF", 'warning': w2})
    
    # Gate 3
    s3, val3, w3 = gate3_dollar_per_sf(data['total_bid'], data['building_sf'], data['building_type'])
    results.append({'gate': 3, 'name': '$/SF Check', 'status': s3,
                    'value': f"${val3:.2f}/SF", 'warning': w3})
    
    # Gate 4
    s4, w4 = gate4_scope_completeness(data.get('found_scope_items', []), data['building_type'])
    results.append({'gate': 4, 'name': 'Scope Complete', 'status': s4, 'warning': w4})

    # Gate 5: structural ratio checks (roadmap defaults - not calibrated from real bids)
    s5, violations5, w5 = gate5_structural_ratios(data)
    results.append({
        'gate': 5,
        'name': 'Structural Ratios',
        'status': s5,
        'violations': violations5,
        'warning': w5,
        'calibrated': False,
        'note': 'Ranges are roadmap defaults. Recalibrate with real bid data.',
    })

    # Gate 6: anchor count vs column count (Ivan 2026-05-25 SP183 B1)
    ac = data.get("anchor_count", 0)
    cc = data.get("column_count", 0)
    bp = data.get("base_plate_type", "simple")
    s6, val6, w6 = gate6_anchor_count(ac, cc, bp)
    results.append({'gate': 6, 'name': 'Anchor Count', 'status': s6,
                    'value': val6, 'warning': w6})

    confidence = calculate_confidence(results)
    blocked = any(r['status'] == 'BLOCK' for r in results)
    
    return {
        'gates': results,
        'confidence': confidence,
        'blocked': blocked,
        'decision': 'BLOCKED - MANUAL REVIEW' if blocked else 
                    'CAUTION - REVIEW RECOMMENDED' if confidence < 80 else
                    'GO - READY TO SUBMIT'
    }


def red_light_check(extracted_tonnage: float, calculated_tonnage: float) -> dict:
    """Compare PDF-stated tonnage vs AISC-calculated tonnage.

    If variance exceeds 10%, the bid should be blocked for manual review.
    Either value being 0 means we cannot compare - returns skipped=True.

    Returns dict: ok, variance_pct, warning, skipped
    """
    if not extracted_tonnage or not calculated_tonnage:
        return {"ok": True, "variance_pct": None, "warning": None, "skipped": True}
    variance_pct = abs(extracted_tonnage - calculated_tonnage) / calculated_tonnage * 100
    if variance_pct > 10:
        return {
            "ok": False,
            "variance_pct": round(variance_pct, 1),
            "warning": (
                f"Tonnage mismatch: PDF states {extracted_tonnage:.1f}T, "
                f"AISC calc yields {calculated_tonnage:.1f}T "
                f"({variance_pct:.1f}% variance, limit 10%). "
                f"Verify member list before submitting."
            ),
            "skipped": False,
        }
    return {"ok": True, "variance_pct": round(variance_pct, 1), "warning": None, "skipped": False}


def tonnage_ceiling_check(total_tons: float, building_type: str) -> dict:
    """Hard ceiling: flag non-industrial bids over 500T as SUSPECT.

    500T is roughly 20x a typical retail_small bid. Exceeding it almost
    certainly indicates a PDF parse error - the ICD Church pattern where
    the extractor returned 3,914T for a single-story church.

    Warehouse is excluded from the ceiling - distribution centers can
    legitimately exceed 500T.

    Returns dict: ok, suspect, warning
    """
    if building_type not in _NON_INDUSTRIAL_TYPES:
        return {"ok": True, "suspect": False, "warning": None}
    if total_tons > 500:
        return {
            "ok": False,
            "suspect": True,
            "warning": (
                f"SUSPECT: {total_tons:.1f}T exceeds 500T ceiling for "
                f"'{building_type}' project type. Likely PDF parse error. "
                f"Do not auto-accept - verify raw members before proceeding."
            ),
        }
    return {"ok": True, "suspect": False, "warning": None}


# ── Reconciliation advisory cross-check (plan item 1.2) ─────────────────────
#
# ADVISORY AND READ-ONLY. This function never sets, produces, or changes a
# price, quantity, weight, or rate, and never returns a go/no-go verdict on a
# price. It diffs a finished estimate against a requirements-and-exclusions
# register and reports a coverage rate plus named gaps. Member weights stay in
# bridge/aisc_validator.py. Rates stay in bridge/bid_rates.py. The only numbers
# it emits are diagnostic counts and a coverage ratio over the inputs.
#
# Matching is deterministic identity only: an estimate line's explicit
# requirement_refs and a register row's priced_line_ref. Items the script
# cannot link are routed to a needs_judgment bucket for the model or a human.
# The script never keyword-guesses a semantic match (the "AI classifies,
# scripts never pattern-match" rule). Best run as a fresh, memoryless pass so
# it checks against source, not its own prior working.
#
# Source: ConstructIQ 7.1 reconciliation pass; docs/KB-IMPLEMENTATION-PLAN.md
# Workstream 1 item 1.2. Pairs with skills/bid-reconciliation-check/SKILL.md
# and the heavier engine spec in skills/bid/reconciliation.skill.md.

# Register categories that are NOT Your Company priced scope. Everything else is
# treated as a priceable requirement (covers both the skill-doc category set
# Direct/ContingencyPrelim and the requirements_register.py emitter category
# set STRUCTURAL_STEEL/JOISTS/DECK/...).
_RECON_NON_PRICEABLE = frozenset({"Subcontractor", "Excluded"})

_RECON_DISCLAIMER = (
    "Advisory cross-check only. Reports coverage and named gaps over the "
    "inputs. Does not set or change any price, quantity, weight, or rate. "
    "Member weights come from bridge/aisc_validator.py and rates from "
    "bridge/bid_rates.py. Every finding is reviewed by a human before "
    "bid submission."
)


def _recon_norm(s) -> str:
    """Lowercase and collapse whitespace. Identity normalization only."""
    if not s:
        return ""
    return " ".join(str(s).split()).lower()


def _recon_register_row(row: dict) -> dict:
    """Normalize a register row across the two in-repo register shapes.

    Accepts the skill-doc shape (req_id, requirement_text, category, status,
    priced_line_ref, source_doc/source_page) and the requirements_register.py
    emitter shape (id, description, category, confidence, source_citations).
    Never invents data; missing fields stay empty or None.
    """
    req_id = str(row.get("req_id") or row.get("id") or "")
    text = row.get("requirement_text") or row.get("description") or ""
    category = row.get("category") or "Direct"
    status = row.get("status") or "Gap"
    priced_line_ref = row.get("priced_line_ref")
    src = ""
    if row.get("source_doc"):
        src = str(row.get("source_doc"))
        if row.get("source_page") not in (None, ""):
            src += " p." + str(row.get("source_page"))
    elif isinstance(row.get("source_citations"), list) and row["source_citations"]:
        c0 = row["source_citations"][0] or {}
        if isinstance(c0, dict):
            src = str(c0.get("file", ""))
            if c0.get("page") not in (None, ""):
                src += " p." + str(c0.get("page"))
    return {
        "req_id": req_id,
        "requirement_text": str(text),
        "category": str(category),
        "status": str(status),
        "priced_line_ref": str(priced_line_ref) if priced_line_ref else "",
        "source": src,
    }


def _recon_estimate_line(line: dict) -> dict:
    """Normalize an estimate/BOQ line to the canonical fields used here."""
    refs = line.get("requirement_refs")
    if not isinstance(refs, list):
        refs = []
    return {
        "line_id": str(line.get("line_id") or ""),
        "description": str(line.get("description") or ""),
        "category": str(line.get("category") or "Direct"),
        "unit": str(line.get("unit") or ""),
        "requirement_refs": [str(r) for r in refs if r not in (None, "")],
    }


def reconcile_advisory(estimate_lines, register, building_type=None) -> dict:
    """ADVISORY cross-check. Diff a finished estimate against a
    requirements-and-exclusions register and report a coverage rate plus
    named gaps. READ-ONLY: never sets or changes any price, quantity, weight,
    or rate, and never returns a go/no-go verdict on price.

    Matching is deterministic identity only: explicit requirement_refs on an
    estimate line and priced_line_ref on a register row. Items the script
    cannot link are routed to a needs_judgment bucket for the model or a
    human; the script never keyword-guesses a semantic match.

    Args:
        estimate_lines: list of estimate/BOQ line dicts. Canonical fields:
            line_id, description, category, unit, requirement_refs[].
            Tolerant of missing optional keys.
        register: list of requirement/exclusion rows. Exclusions are rows with
            category "Excluded" (or status "ExcludedByDesign").
        building_type: optional str, echoed into the report for context only.
            Never used to derive a number.

    Returns:
        A plain advisory dict (the Bridge wrapper adds the _ok/_err envelope):
        advisory, generates_numbers (False), building_type, coverage{...},
        findings[...], summary{...}, verdict (None), disclaimer.
    """
    lines = [_recon_estimate_line(l) for l in (estimate_lines or []) if isinstance(l, dict)]
    regs = [_recon_register_row(r) for r in (register or []) if isinstance(r, dict)]

    # ── Build the deterministic link map (identity only) ──
    # req_id -> set of line_ids that explicitly claim to satisfy it.
    req_to_lines: dict = {}
    for ln in lines:
        for ref in ln["requirement_refs"]:
            req_to_lines.setdefault(ref, set()).add(ln["line_id"] or "<unnamed-line>")
    for rg in regs:
        if rg["req_id"] and rg["priced_line_ref"]:
            req_to_lines.setdefault(rg["req_id"], set()).add(rg["priced_line_ref"])
    linked_req_ids = {rid for rid, ls in req_to_lines.items() if ls}

    findings: list = []

    # ── Coverage over priceable requirements (explicit links only) ──
    priceable = [r for r in regs if r["category"] not in _RECON_NON_PRICEABLE]
    priceable_total = len(priceable)
    matched = [r for r in priceable if r["req_id"] and r["req_id"] in linked_req_ids]
    coverage_rate = round(len(matched) / priceable_total, 3) if priceable_total else None

    # ── Finding 1: UNPRICED_REQUIREMENT (named gaps) ──
    for r in priceable:
        if r["req_id"] and r["req_id"] in linked_req_ids:
            continue
        findings.append({
            "type": "UNPRICED_REQUIREMENT",
            "req_id": r["req_id"],
            "requirement_text": r["requirement_text"][:240],
            "category": r["category"],
            "confidence": "medium",
            "needs_judgment": True,
            "method": "no explicit priced-line link (requirement_refs / priced_line_ref)",
            "source": r["source"],
            "note": ("No estimate line is linked to this requirement. Confirm by hand "
                     "whether an unlinked line covers it before treating it as a gap."),
        })

    # ── Finding 2: EXCLUDED_BUT_PRICED (scope contradiction) ──
    for r in regs:
        if r["category"] != "Excluded" and r["status"] != "ExcludedByDesign":
            continue
        ls = req_to_lines.get(r["req_id"]) if r["req_id"] else None
        if ls:
            findings.append({
                "type": "EXCLUDED_BUT_PRICED",
                "req_id": r["req_id"],
                "requirement_text": r["requirement_text"][:240],
                "line_ids": sorted(ls),
                "confidence": "high",
                "needs_judgment": False,
                "method": "register row is excluded but an estimate line links to it",
                "source": r["source"],
                "note": "Priced scope was declared excluded. Resolve before submitting.",
            })

    # ── Finding 3: DOUBLE_LINK (double-count candidate) ──
    for rid, ls in sorted(req_to_lines.items()):
        if len(ls) >= 2:
            findings.append({
                "type": "DOUBLE_LINK",
                "req_id": rid,
                "line_ids": sorted(ls),
                "confidence": "medium",
                "needs_judgment": True,
                "method": "one requirement is linked by two or more estimate lines",
                "note": ("Two or more lines claim the same requirement. May be a "
                         "legitimate split. Confirm it is not a double count."),
            })

    # ── Finding 4: DUPLICATE_LINE (double-count candidate) ──
    seen: dict = {}
    for ln in lines:
        desc = _recon_norm(ln["description"])
        if not desc:
            continue
        key = (desc, _recon_norm(ln["unit"]), _recon_norm(ln["category"]))
        seen.setdefault(key, []).append(ln["line_id"] or "<unnamed-line>")
    for key, ids in seen.items():
        if len(ids) >= 2:
            findings.append({
                "type": "DUPLICATE_LINE",
                "line_ids": sorted(ids),
                "description": key[0][:240],
                "unit": key[1],
                "confidence": "medium",
                "needs_judgment": True,
                "method": "two or more estimate lines share an identical description, unit, and category",
                "note": "Identical lines. Confirm they are not the same scope priced twice.",
            })

    # ── Finding 5: ORPHAN_LINE (possible scope creep or missing requirement) ──
    matched_line_ids: set = set()
    for ls in req_to_lines.values():
        matched_line_ids |= ls
    for ln in lines:
        lid = ln["line_id"]
        if not ln["requirement_refs"] and (not lid or lid not in matched_line_ids):
            findings.append({
                "type": "ORPHAN_LINE",
                "line_id": lid or "<unnamed-line>",
                "description": ln["description"][:240],
                "category": ln["category"],
                "confidence": "medium",
                "needs_judgment": True,
                "method": "estimate line has no requirement_refs and no register row links to it",
                "note": ("Priced line traces to no requirement. Confirm it is in scope, "
                         "or that the register is missing the requirement."),
            })

    summary = {
        "estimate_line_count": len(lines),
        "register_row_count": len(regs),
        "priceable_requirements": priceable_total,
        "linked_matched": len(matched),
        "unpriced_count": sum(1 for f in findings if f["type"] == "UNPRICED_REQUIREMENT"),
        "excluded_but_priced_count": sum(1 for f in findings if f["type"] == "EXCLUDED_BUT_PRICED"),
        "double_count_candidates": sum(1 for f in findings if f["type"] in ("DOUBLE_LINK", "DUPLICATE_LINE")),
        "orphan_count": sum(1 for f in findings if f["type"] == "ORPHAN_LINE"),
        "needs_judgment_count": sum(1 for f in findings if f.get("needs_judgment")),
    }

    return {
        "advisory": True,
        "generates_numbers": False,
        "building_type": building_type or None,
        "coverage": {
            "priceable_total": priceable_total,
            "linked_matched": len(matched),
            "coverage_rate": coverage_rate,
            "basis": ("explicit requirement_refs / priced_line_ref links only; "
                      "unlinked items are routed to needs_judgment for AI or human review"),
        },
        "findings": findings,
        "summary": summary,
        "verdict": None,
        "disclaimer": _RECON_DISCLAIMER,
    }


# ============================================================
# DEMO: TSC Sumter SC
# ============================================================
if __name__ == '__main__':
    tsc = {
        'building_sf': 21930,
        'building_type': 'retail_small',
        'struct_tons': 12.6,
        'joist_tons': 29.0,
        'total_bid': 283315,
        'grid_bays': [
            {'width': 42.0}, {'width': 42.67}, {'width': 42.0}, {'width': 28.67}
        ],
        'eq_spa_annotations': [6, 6, 6, 6, 2],
        'text_joist_count': 84,
        'found_scope_items': [
            'structural_columns', 'beams_girders', 'bar_joists',
            'joist_girders', 'roof_deck', 'bracing', 'misc_angles_plates',
            # MISSING: base_plates_anchors, canopy_framing
        ],
    }
    
    r = run_gates(tsc)
    
    print("=" * 65)
    print("  BID SANITY GATES v2 - TSC Sumter SC")
    print("=" * 65)
    
    for g in r['gates']:
        status_icon = {'PASS':'[OK]', 'HIGH':'[OK]', 'CAUTION':'[!!]', 
                       'FLAG':'[XX]', 'BLOCK':'[XX]', 'CORRECTED':'[~~]', 'LOW':'[??]'}
        icon = status_icon.get(g['status'], '[??]')
        val = f" = {g.get('value','')}" if g.get('value') else ''
        print(f"  Gate {g['gate']} {icon} {g['name']}{val}")
        if g['warning']:
            print(f"         {g['warning']}")
    
    print(f"\n  Confidence: {r['confidence']}/100")
    print(f"  Decision:   {r['decision']}")
    
    bench = PRICE_BENCHMARKS['retail_small']
    adjusted = bench['mid'] * tsc['building_sf']
    print(f"\n  Sandbox bid:      ${tsc['total_bid']:>10,}")
    print(f"  Market midpoint:  ${adjusted:>10,}  (${bench['mid']}/SF)")
    print(f"  Owner Rev.2:    $   393,000")
    print(f"  Midpoint vs Rev2: {(adjusted/393000-1)*100:+.1f}%")
