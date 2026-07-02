"""
Weld Consumable Calculator - Domain Engine

Pure-Python deterministic formulas from Lincoln Electric / ESAB handbooks.
No LLM math - all computed from physical constants.

Steel density: 0.2836 lb/in³
Weld-metal weight = (cross-sectional area in²) × (length in) × 0.2836
Deposition efficiency: SMAW 55-65%, FCAW 80-85%, GMAW 90-95%, SAW 95-100%
10-15% buffer for spatter/repair/rework (per handoff doc)
"""
import math

STEEL_DENSITY = 0.2836  # lb/in³

# Deposition efficiency by process (midpoint of published ranges)
DEPOSITION_EFF = {
    "SMAW":  0.60,   # 55-65% - stub loss, spatter
    "FCAW":  0.825,  # 80-85%
    "GMAW":  0.925,  # 90-95%
    "SAW":   0.975,  # 95-100%
}

# Common filler metals and their unit costs ($/lb, Houston 2025-2026 approximate)
FILLER_COSTS = {
    "E7018":       1.85,   # SMAW - most common structural
    "E7018-A1":    2.40,   # SMAW - Cr-Mo
    "ER70S-6":     1.50,   # GMAW solid wire
    "E71T-1":      1.65,   # FCAW flux-cored
    "E71T-8":      1.90,   # FCAW self-shielded (field)
    "EM12K":       1.30,   # SAW
    "ER309L":      6.50,   # Stainless dissimilar
}

# Common weld joint cross-sectional areas (in²) by type and size
def fillet_area(leg_size_in):
    """Cross-sectional area of a fillet weld (right-triangle)."""
    return 0.5 * leg_size_in * leg_size_in

def vgroove_area(plate_thickness_in, included_angle_deg=60, root_gap_in=0.125):
    """Cross-sectional area of a single-V groove weld."""
    half_angle = math.radians(included_angle_deg / 2)
    return (plate_thickness_in ** 2) * math.tan(half_angle) + (root_gap_in * plate_thickness_in)

def bevel_area(plate_thickness_in, bevel_angle_deg=45, root_gap_in=0.125):
    """Cross-sectional area of a single-bevel groove weld."""
    angle = math.radians(bevel_angle_deg)
    return 0.5 * (plate_thickness_in ** 2) * math.tan(angle) + (root_gap_in * plate_thickness_in)


def weld_metal_weight(cross_section_area_sq_in, length_in):
    """Weight of deposited weld metal in pounds."""
    return cross_section_area_sq_in * length_in * STEEL_DENSITY


def consumable_required(weld_weight_lb, process="FCAW", buffer_pct=12):
    """Total consumable required accounting for deposition efficiency and buffer.
    Returns {deposited_lb, consumable_lb, buffer_pct, efficiency}."""
    eff = DEPOSITION_EFF.get(process.upper(), 0.85)
    raw = weld_weight_lb / eff
    buffered = raw * (1 + buffer_pct / 100)
    return {
        "deposited_weld_metal_lb": round(weld_weight_lb, 3),
        "consumable_before_buffer_lb": round(raw, 3),
        "buffer_pct": buffer_pct,
        "total_consumable_lb": round(buffered, 3),
        "process": process.upper(),
        "deposition_efficiency": eff,
    }


def estimate_joint(joint_type, size_in, length_in, process="FCAW",
                    filler="E71T-1", buffer_pct=12):
    """Full estimate for a single weld joint.
    joint_type: 'fillet', 'vgroove', 'bevel'
    size_in: leg size for fillet, plate thickness for groove
    length_in: weld length in inches
    Returns complete breakdown with cost."""
    if joint_type.lower() == "fillet":
        area = fillet_area(size_in)
    elif joint_type.lower() == "vgroove":
        area = vgroove_area(size_in)
    elif joint_type.lower() == "bevel":
        area = bevel_area(size_in)
    else:
        return {"error": f"Unknown joint type: {joint_type}. Use fillet/vgroove/bevel."}

    weight = weld_metal_weight(area, length_in)
    consumable = consumable_required(weight, process, buffer_pct)
    cost_per_lb = FILLER_COSTS.get(filler, 1.75)
    total_cost = consumable["total_consumable_lb"] * cost_per_lb

    return {
        "joint_type": joint_type,
        "size_in": size_in,
        "length_in": length_in,
        "cross_section_area_sq_in": round(area, 4),
        **consumable,
        "filler_metal": filler,
        "cost_per_lb": cost_per_lb,
        "total_cost": round(total_cost, 2),
        "source": "Lincoln Electric / ESAB formulas, 0.2836 lb/in³ steel density",
    }


def estimate_project_consumables(joints):
    """Estimate total consumables for a project.
    joints: list of {type, size_in, length_in, qty, process, filler}"""
    total_weight = 0
    total_cost = 0
    details = []
    for j in joints:
        qty = j.get("qty", 1)
        est = estimate_joint(
            j.get("type", "fillet"), j.get("size_in", 0.25),
            j.get("length_in", 12), j.get("process", "FCAW"),
            j.get("filler", "E71T-1"), j.get("buffer_pct", 12)
        )
        if est.get("error"):
            details.append(est)
            continue
        est["qty"] = qty
        est["line_weight"] = round(est["total_consumable_lb"] * qty, 3)
        est["line_cost"] = round(est["total_cost"] * qty, 2)
        total_weight += est["line_weight"]
        total_cost += est["line_cost"]
        details.append(est)
    return {
        "joints": details,
        "total_consumable_lb": round(total_weight, 2),
        "total_cost": round(total_cost, 2),
    }
