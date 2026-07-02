"""
Your Company Virtual Office - Miscellaneous Steel Calculator
=========================================================
Handles steel items NOT in the AISC Shapes Database:
  - Plates (PL): base plates, gusset plates, stiffeners, shear tabs
  - Bent plates
  - Embed plates
  - Anchor bolt assemblies (estimated weight)
  - Misc connection hardware (clip angles, shear tabs, stiffeners)
  - Configurable misc factor (5-8% of structural tonnage)

All weight calculations use steel density: 490 lb/ft3 = 0.2836 lb/in3.
No LLM calls. Pure geometry.
"""

import re
from typing import Optional

STEEL_DENSITY_LB_PER_IN3 = 0.2836  # A36/A992 carbon steel


# ── PLATE NOTATION PARSER ─────────────────────────────────────────

# PL{thickness}X{width}X{length}  e.g. PL.750X12X12, PL1X18X24
# Also handles: PL 3/4 X 12 X 12, PL 0.75 X 12 X 12
PL_PATTERN = re.compile(
    r'PL\s*'
    r'(\d*/?\d*\.?\d+)\s*'   # thickness (fraction or decimal)
    r'[xX\u00d7]\s*'
    r'(\d*\.?\d+)\s*'        # width
    r'[xX\u00d7]\s*'
    r'(\d*\.?\d+)',           # length
    re.IGNORECASE
)

# Shorthand: PL 3/4" x 12 x 1'-0"
PL_SHORTHAND = re.compile(
    r'PL\s*'
    r'(\d*/?\d*\.?\d+)\s*["\u2033]?\s*'
    r'[xX\u00d7]\s*'
    r'(\d*\.?\d+)\s*["\u2033]?\s*'
    r'[xX\u00d7]\s*'
    r"(\d+)\s*['\u2032]\s*-?\s*(\d*)\s*[\"\\u2033]?",
    re.IGNORECASE
)


def parse_fraction(val: str) -> float:
    """Parse '3/4', '0.750', '.750', '1.5' to float inches."""
    val = val.strip()
    if '/' in val:
        parts = val.split('/')
        return float(parts[0]) / float(parts[1])
    return float(val)


def calculate_plate_weight(thickness_in: float, width_in: float,
                           length_in: float, qty: int = 1) -> dict:
    """Calculate plate weight from dimensions in inches.
    Returns weight per piece and total weight.
    """
    volume_in3 = thickness_in * width_in * length_in
    weight_lbs = volume_in3 * STEEL_DENSITY_LB_PER_IN3
    return {
        "thickness_in": thickness_in,
        "width_in": width_in,
        "length_in": length_in,
        "qty": qty,
        "weight_per_piece_lbs": round(weight_lbs, 2),
        "weight_total_lbs": round(weight_lbs * qty, 2),
        "weight_total_tons": round((weight_lbs * qty) / 2000, 4),
    }


def parse_plate_notation(text: str) -> Optional[dict]:
    """Parse PL notation string to dimensions.
    Examples:
        PL.750X12X12   -> 0.75" x 12" x 12"
        PL1X18X24      -> 1.0" x 18" x 24"
        PL3/4X12X12    -> 0.75" x 12" x 12"
        1/2X12X12 PL   -> 0.5" x 12" x 12"  (PL at end)
        3/8 PL 24x36   -> 0.375" x 24" x 36" (PL in middle)
    """
    raw = text.strip()
    # Try shorthand with feet-inches length first
    m = PL_SHORTHAND.match(raw)
    if m:
        thickness = parse_fraction(m.group(1))
        width = float(m.group(2))
        feet = float(m.group(3))
        inches = float(m.group(4)) if m.group(4) else 0
        length = feet * 12 + inches
        return {"thickness_in": thickness, "width_in": width, "length_in": length}

    # Standard PL notation (PL at start)
    m = PL_PATTERN.match(raw)
    if m:
        thickness = parse_fraction(m.group(1))
        width = float(m.group(2))
        length = float(m.group(3))
        return {"thickness_in": thickness, "width_in": width, "length_in": length}

    # Flexible fallback: strip 'PL' from anywhere, then try as bare dimensions
    # Handles: "1/2X12X12 PL", "3/8 PL 24x36", "PL", etc.
    stripped = re.sub(r'\bPL\b', '', raw, flags=re.IGNORECASE).strip()
    # Allow either X or space as the FIRST separator (thickness can be space-separated from width)
    bare_pattern = re.compile(
        r'^(\d*/?\d*\.?\d+)\s*[xX\u00d7\s]\s*(\d*\.?\d+)\s*[xX\u00d7]\s*(\d*\.?\d+)$',
        re.IGNORECASE,
    )
    m = bare_pattern.match(stripped)
    if m:
        thickness = parse_fraction(m.group(1))
        width = float(m.group(2))
        length = float(m.group(3))
        return {"thickness_in": thickness, "width_in": width, "length_in": length}

    return None


def calculate_plate_from_notation(notation: str, qty: int = 1) -> dict:
    """Parse PL notation and calculate weight.
    Input: "PL.750X12X12", qty=24
    Output: {notation, dims, weight_per_piece, weight_total, weight_tons}
    """
    parsed = parse_plate_notation(notation)
    if not parsed:
        return {"error": f"Cannot parse plate notation: {notation}"}

    result = calculate_plate_weight(
        parsed["thickness_in"], parsed["width_in"], parsed["length_in"], qty
    )
    result["notation"] = notation
    result["shape_type"] = "PL"
    return result


# ── CONNECTION HARDWARE ESTIMATOR ─────────────────────────────────

# Industry-standard connection weights (lbs per connection)
CONNECTION_WEIGHTS = {
    "shear_tab": 12,        # typical single-plate shear connection
    "clip_angle": 8,        # double-angle connection (pair)
    "stiffener": 15,        # column stiffener plate
    "gusset_small": 25,     # small brace gusset
    "gusset_large": 65,     # large brace gusset
    "base_plate_small": 45, # base plate for HSS columns
    "base_plate_large": 120,# base plate for W-columns
    "cap_plate": 20,        # column cap plate
    "shear_stud": 0.5,      # Nelson stud (each)
    "anchor_bolt_set": 15,  # 4-bolt set with template
    "embed_plate": 35,      # cast-in embed
}


def estimate_connection_weight(member_count: int, struct_tons: float,
                               building_type: str = "commercial") -> dict:
    """Estimate total connection hardware weight.

    Industry rules of thumb:
      - Commercial: 5-7% of structural tonnage
      - Industrial/refinery: 7-10%
      - Warehouse (simple): 4-6%

    Returns itemized breakdown + total.
    """
    factors = {
        "warehouse": {"pct": 0.05, "shear_tabs_per_member": 1.5, "base_plates": 0.15},
        "commercial": {"pct": 0.06, "shear_tabs_per_member": 2.0, "base_plates": 0.20},
        "retail_small": {"pct": 0.055, "shear_tabs_per_member": 1.8, "base_plates": 0.18},
        "dealership": {"pct": 0.07, "shear_tabs_per_member": 2.2, "base_plates": 0.22},
        "industrial": {"pct": 0.08, "shear_tabs_per_member": 2.5, "base_plates": 0.25},
        "refinery": {"pct": 0.09, "shear_tabs_per_member": 3.0, "base_plates": 0.30},
    }
    f = factors.get(building_type, factors["commercial"])

    # Method 1: percentage of structural tonnage
    pct_weight_lbs = struct_tons * 2000 * f["pct"]

    # Method 2: itemized estimate
    est_shear_tabs = int(member_count * f["shear_tabs_per_member"])
    est_base_plates = int(member_count * f["base_plates"])
    est_stiffeners = int(member_count * 0.3)
    est_gussets = int(member_count * 0.1)
    est_anchor_sets = est_base_plates

    itemized = {
        "shear_tabs": {"count": est_shear_tabs, "lbs": est_shear_tabs * CONNECTION_WEIGHTS["shear_tab"]},
        "base_plates": {"count": est_base_plates, "lbs": est_base_plates * CONNECTION_WEIGHTS["base_plate_large"]},
        "stiffeners": {"count": est_stiffeners, "lbs": est_stiffeners * CONNECTION_WEIGHTS["stiffener"]},
        "gussets": {"count": est_gussets, "lbs": est_gussets * CONNECTION_WEIGHTS["gusset_small"]},
        "anchor_bolt_sets": {"count": est_anchor_sets, "lbs": est_anchor_sets * CONNECTION_WEIGHTS["anchor_bolt_set"]},
        "cap_plates": {"count": est_base_plates, "lbs": est_base_plates * CONNECTION_WEIGHTS["cap_plate"]},
    }
    itemized_total_lbs = sum(v["lbs"] for v in itemized.values())

    # Use the HIGHER of the two methods (conservative for bidding)
    final_lbs = max(pct_weight_lbs, itemized_total_lbs)
    method_used = "percentage" if pct_weight_lbs >= itemized_total_lbs else "itemized"

    return {
        "method": method_used,
        "percentage_estimate_lbs": round(pct_weight_lbs),
        "itemized_estimate_lbs": round(itemized_total_lbs),
        "final_lbs": round(final_lbs),
        "final_tons": round(final_lbs / 2000, 2),
        "factor_pct": f["pct"] * 100,
        "building_type": building_type,
        "itemized": itemized,
    }


# ── MISC STEEL FACTOR ────────────────────────────────────────────

def apply_misc_factor(verified_tons: float, misc_pct: float = 0.06,
                      plates: list = None, building_type: str = "commercial",
                      member_count: int = 0) -> dict:
    """Apply misc steel factor to verified tonnage.

    Combines:
    1. Verified AISC tonnage (from database match)
    2. Explicit plate weights (parsed from PL notation)
    3. Connection hardware estimate
    4. Remaining misc factor for items not individually counted

    Returns complete tonnage breakdown.
    """
    plate_tons = 0
    plate_details = []
    if plates:
        for p in plates:
            if isinstance(p, str):
                # Parse PL notation
                result = calculate_plate_from_notation(p, qty=p.get("qty", 1) if isinstance(p, dict) else 1)
                if "error" not in result:
                    plate_tons += result["weight_total_tons"]
                    plate_details.append(result)
            elif isinstance(p, dict):
                notation = p.get("notation", p.get("shape", ""))
                qty = p.get("qty", 1)
                if notation:
                    result = calculate_plate_from_notation(notation, qty)
                    if "error" not in result:
                        plate_tons += result["weight_total_tons"]
                        plate_details.append(result)
                else:
                    # Raw dimension dict: {"thickness":"1/2","width":12,"length":12,"qty":24}
                    thick = p.get("thickness", p.get("thickness_in", 0))
                    width = p.get("width", p.get("width_in", 0))
                    length = p.get("length", p.get("length_in", 0))
                    if thick and width and length:
                        # Parse fraction strings like "1/2" → 0.5
                        if isinstance(thick, str):
                            thick = parse_fraction(thick)
                        result = calculate_plate_weight(
                            float(thick), float(width), float(length), int(qty)
                        )
                        if "error" not in result:
                            plate_tons += result.get("weight_total_tons", 0)
                            plate_details.append(result)

    # Connection hardware
    conn = estimate_connection_weight(member_count, verified_tons, building_type)
    conn_tons = conn["final_tons"]

    # Remaining misc (bolts, shims, leveling nuts, erection aids)
    # Apply to structural only, not joists (joists come with their own hardware)
    remaining_misc_tons = verified_tons * (misc_pct * 0.3)  # 30% of misc factor for uncounted items

    total_tons = verified_tons + plate_tons + conn_tons + remaining_misc_tons

    return {
        "verified_aisc_tons": round(verified_tons, 2),
        "plate_tons": round(plate_tons, 4),
        "plate_details": plate_details,
        "connection_tons": round(conn_tons, 2),
        "connection_detail": conn,
        "remaining_misc_tons": round(remaining_misc_tons, 2),
        "total_tons": round(total_tons, 2),
        "misc_pct_applied": misc_pct * 100,
        "tonnage_increase_pct": round((total_tons / verified_tons - 1) * 100, 1) if verified_tons > 0 else 0,
    }
