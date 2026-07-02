"""Connection plate weight estimation (Phase 12, build slot 12, v4.4.0).

Estimates the additional tonnage from connection hardware that does not
appear in the member schedule: clip angles, end plates, stiffeners,
base plates, gussets. On a typical project this is 10-15 percent of the
structural weight. Missing it means the material cost is 10-15 percent
low.

Uses Phase 2 detail_vision bolt_count + connection_type + member shapes
to estimate each component. Steel density is 0.283 lb/in3, locked in
bridge/misc_steel/plate_detector.py as well.

All arithmetic is deterministic. No LLM math.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import math

log = logging.getLogger(__name__)


STEEL_DENSITY_LB_IN3 = 0.283

# Typical member depths used when the actual depth is not in the detail.
# Keyed by AISC shape family prefix.
_TYPICAL_DEPTHS_IN = {
    "W": 14.0,
    "S": 12.0,
    "C": 10.0,
    "MC": 8.0,
    "HP": 14.0,
    "HSS": 8.0,
    "L": 4.0,
    "WT": 7.0,
}


def _get_depth(detail: dict, default: float = 14.0) -> float:
    """Extract member depth in inches from the detail or fall back to
    the typical depth for the shape family."""
    d = detail.get("member_depth_in")
    if d and float(d) > 0:
        return float(d)
    shape = str(detail.get("shape", detail.get("member_shape", "")))
    for prefix, depth in _TYPICAL_DEPTHS_IN.items():
        if shape.upper().startswith(prefix):
            return depth
    return default


def _get_flange_width(detail: dict, default: float = 7.0) -> float:
    """Extract flange width in inches."""
    w = detail.get("flange_width_in")
    if w and float(w) > 0:
        return float(w)
    return default


def _plate_weight(thickness_in: float, width_in: float,
                  length_in: float) -> float:
    """Rectangular plate weight in lbs."""
    return thickness_in * width_in * length_in * STEEL_DENSITY_LB_IN3


def estimate_clip_angle(bolt_count: int, depth_in: float) -> float:
    """Clip angle pair weight (2 angles). Typical L4X3X1/4 at 4.7 lb/ft."""
    if bolt_count <= 0:
        return 0.0
    # Angle length = bolt spacing * (bolt_count - 1) + 3" top/bottom
    spacing = 3.0  # inch bolt spacing
    angle_length_in = spacing * max(bolt_count - 1, 1) + 6.0
    lb_per_ft = 4.7
    return 2 * (angle_length_in / 12.0) * lb_per_ft


def estimate_end_plate(depth_in: float, flange_width_in: float,
                       thickness_in: float = 1.0) -> float:
    """End plate weight for moment connections. Full depth, full width."""
    # Plate extends 1" above and below flanges
    height = depth_in + 2.0
    width = max(flange_width_in + 2.0, 8.0)
    return _plate_weight(thickness_in, width, height)


def estimate_stiffeners(depth_in: float, flange_width_in: float,
                        thickness_in: float = 0.5,
                        count: int = 2) -> float:
    """Stiffener plates for moment connections. Welded to column web."""
    # Stiffener fills the clear depth between flanges
    # Approximate flange thickness as 0.75"
    clear_depth = depth_in - 2 * 0.75
    if clear_depth <= 0:
        clear_depth = depth_in * 0.8
    width = max(flange_width_in / 2.0 - 0.5, 3.0)
    return count * _plate_weight(thickness_in, width, clear_depth)


def estimate_base_plate(column_depth_in: float,
                        column_width_in: float = 0.0,
                        overhang_in: float = 6.0,
                        thickness_in: float = 1.5) -> float:
    """Base plate weight. Column footprint + overhang on each side."""
    if column_width_in <= 0:
        column_width_in = column_depth_in * 0.7  # typical W-shape ratio
    width = column_width_in + 2 * overhang_in
    length = column_depth_in + 2 * overhang_in
    return _plate_weight(thickness_in, width, length)


def estimate_gusset(depth_in: float,
                    thickness_in: float = 0.5) -> float:
    """Triangular gusset plate for brace connections.

    Approximated as a right triangle with base = height = 1.5x member depth.
    Weight = 0.5 * base * height * thickness * density.
    """
    side = depth_in * 1.5
    area = 0.5 * side * side
    return area * thickness_in * STEEL_DENSITY_LB_IN3


def estimate_single_connection(detail: dict) -> dict:
    """Estimate plate/hardware weight for one connection.

    Args:
        detail: Phase 2 detail_vision dict. Keys used:
            connection_type, moment, bolt_count, shape/member_shape,
            member_depth_in, flange_width_in.

    Returns:
        {
            "connection_type": str,
            "clip_angle_lbs": float,
            "end_plate_lbs": float,
            "stiffener_lbs": float,
            "base_plate_lbs": float,
            "gusset_lbs": float,
            "total_lbs": float,
        }
    """
    conn = str(detail.get("connection_type", "")).strip().upper()
    is_moment = bool(detail.get("moment", False))
    bolt_count = int(detail.get("bolt_count", 0) or 0)
    depth = _get_depth(detail)
    flange_w = _get_flange_width(detail)

    clip = 0.0
    end_pl = 0.0
    stiff = 0.0
    base = 0.0
    gusset = 0.0

    if conn in ("B2B", "B2C") and not is_moment:
        # Shear connection: clip angles
        clip = estimate_clip_angle(bolt_count or 3, depth)

    elif conn == "B2C" and is_moment:
        # Moment: end plate + stiffeners (no clip angles)
        end_pl = estimate_end_plate(depth, flange_w)
        stiff = estimate_stiffeners(depth, flange_w)

    elif conn == "C2F":
        base = estimate_base_plate(depth)

    elif conn in ("SPLICE", "C2C"):
        # Two splice plates: simplified as rectangular plates
        # covering the web, 1/2" thick, web depth x flange width
        web_depth = depth * 0.8
        splice_w = max(flange_w, 7.0)
        clip = 2 * _plate_weight(0.5, splice_w, web_depth)

    elif conn in ("BR2C", "BR2B"):
        gusset = estimate_gusset(depth)

    else:
        # Unknown type: conservative estimate using clip angles
        clip = estimate_clip_angle(bolt_count or 4, depth)

    total = clip + end_pl + stiff + base + gusset
    return {
        "connection_type": conn,
        "clip_angle_lbs": round(clip, 2),
        "end_plate_lbs": round(end_pl, 2),
        "stiffener_lbs": round(stiff, 2),
        "base_plate_lbs": round(base, 2),
        "gusset_lbs": round(gusset, 2),
        "total_lbs": round(total, 2),
    }


def estimate_connection_weight(
    details: list[dict],
    structural_tons: float = 0.0,
) -> dict:
    """Estimate total connection hardware weight for a project.

    Args:
        details: List of Phase 2 detail_vision result dicts.
        structural_tons: Structural member tonnage (for % validation).

    Returns:
        {
            "total_connection_lbs": float,
            "total_connection_tons": float,
            "pct_of_structural": float,
            "in_expected_range": bool (10-15% is normal),
            "per_connection": list of estimate_single_connection results,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    per_conn = []
    total_lbs = 0.0

    for d in details:
        est = estimate_single_connection(d)
        per_conn.append(est)
        total_lbs += est["total_lbs"]

    total_tons = total_lbs / 2000.0

    pct = 0.0
    in_range = True
    if structural_tons > 0:
        pct = (total_tons / structural_tons) * 100.0
        in_range = 5.0 <= pct <= 25.0
        if pct < 5.0:
            warnings.append(
                f"Connection weight {pct:.1f}% of structural is below "
                f"typical 10-15%. Check bolt counts.")
        elif pct > 25.0:
            warnings.append(
                f"Connection weight {pct:.1f}% of structural exceeds "
                f"typical 10-15%. Verify heavy connections.")

    return {
        "total_connection_lbs": round(total_lbs, 2),
        "total_connection_tons": round(total_tons, 4),
        "pct_of_structural": round(pct, 2),
        "in_expected_range": in_range,
        "per_connection": per_conn,
        "warnings": warnings,
    }
