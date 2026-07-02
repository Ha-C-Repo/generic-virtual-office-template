"""Section optimizer for value engineering proposals.

Scans AISC v16.0 shapes to find lighter sections that maintain adequate
depth and capacity. Every substitution requires PE approval. The output
is a proposal, not a directive.

Uses aisc_master.csv as the single source of truth.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import csv
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_AISC_PATH = Path(__file__).resolve().parent.parent / "data" / "aisc_master.csv"
_SHAPE_CACHE: list[dict] | None = None


def _load_shapes() -> list[dict]:
    """Load AISC shapes from master CSV. Cached after first call."""
    global _SHAPE_CACHE
    if _SHAPE_CACHE is not None:
        return _SHAPE_CACHE

    if not _AISC_PATH.exists():
        # Fallback path (test environment)
        alt = Path("data/aisc_master.csv")
        if not alt.exists():
            return []
        path = alt
    else:
        path = _AISC_PATH

    shapes = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                shapes.append({
                    "shape": row.get("shape", ""),
                    "family": row.get("family", ""),
                    "plf": float(row.get("lb_per_ft", 0) or 0),
                    "d_in": float(row.get("d_in", 0) or 0),
                    "A_in2": float(row.get("A_in2", 0) or 0),
                    "bf_in": float(row.get("bf_in", 0) or 0),
                    "tf_in": float(row.get("tf_in", 0) or 0),
                    "tw_in": float(row.get("tw_in", 0) or 0),
                })
            except (ValueError, TypeError):
                continue
    _SHAPE_CACHE = shapes
    return shapes


def _parse_family(shape_name: str) -> str:
    """Extract the family prefix from a shape name."""
    m = re.match(r"([A-Z]+)", shape_name.upper())
    return m.group(1) if m else ""


def find_lighter_section(
    current_shape: str,
    min_depth_in: float = 0.0,
    material_cost_per_lb: float = 0.55,
    length_ft: float = 1.0,
    qty: int = 1,
) -> dict | None:
    """Find a lighter AISC section in the same family.

    Constraints:
        - Same family (W -> W, HSS -> HSS)
        - Depth >= min_depth_in (or >= 0.7 * current depth if not given)
        - Must be lighter (lower lb/ft)

    Returns None if current section is already the lightest adequate.
    Returns dict with current, proposed, weight_savings_lbs, cost_savings.
    """
    shapes = _load_shapes()
    if not shapes:
        return None

    family = _parse_family(current_shape)
    upper = current_shape.upper().replace(" ", "")

    # Find current shape in database
    current = None
    for s in shapes:
        if s["shape"].upper().replace(" ", "") == upper:
            current = s
            break
    if current is None:
        return None

    if min_depth_in <= 0:
        min_depth_in = current["d_in"] * 0.7

    # Find lighter alternatives in same family
    candidates = []
    for s in shapes:
        if s["family"] != current["family"]:
            continue
        if s["plf"] >= current["plf"]:
            continue
        if s["d_in"] < min_depth_in:
            continue
        # Web thickness must be adequate (not too thin)
        if s["tw_in"] > 0 and s["tw_in"] < current["tw_in"] * 0.5:
            continue
        candidates.append(s)

    if not candidates:
        return None

    # Pick the lightest adequate candidate
    best = min(candidates, key=lambda c: c["plf"])

    savings_plf = current["plf"] - best["plf"]
    savings_lbs = savings_plf * length_ft * qty
    cost_savings = savings_lbs * material_cost_per_lb

    return {
        "current": current["shape"],
        "proposed": best["shape"],
        "current_plf": current["plf"],
        "proposed_plf": best["plf"],
        "savings_plf": round(savings_plf, 2),
        "weight_savings_lbs": round(savings_lbs, 1),
        "cost_savings_usd": round(cost_savings, 2),
        "depth_current": current["d_in"],
        "depth_proposed": best["d_in"],
        "note": "Requires PE approval. Verify deflection and capacity "
                "for the proposed section before substituting.",
    }


def optimize_project(
    members: list[dict],
    material_cost_per_lb: float = 0.55,
) -> dict:
    """Run section optimization across an entire project.

    Args:
        members: List of member dicts with shape, size, length_ft, qty.
        material_cost_per_lb: Current material cost.

    Returns:
        {
            "total_weight_savings_lbs": float,
            "total_cost_savings_usd": float,
            "substitutions": list[dict],
            "members_checked": int,
            "members_optimizable": int,
        }
    """
    substitutions = []
    total_weight = 0.0
    total_cost = 0.0

    for m in members:
        shape = str(m.get("shape", "")) + str(m.get("size", ""))
        if not shape:
            continue
        length = float(m.get("length_ft", 0) or 0)
        qty = int(m.get("qty", 1) or 1)

        result = find_lighter_section(
            shape,
            material_cost_per_lb=material_cost_per_lb,
            length_ft=length,
            qty=qty,
        )
        if result:
            result["mark"] = m.get("mark", "")
            substitutions.append(result)
            total_weight += result["weight_savings_lbs"]
            total_cost += result["cost_savings_usd"]

    return {
        "total_weight_savings_lbs": round(total_weight, 1),
        "total_cost_savings_usd": round(total_cost, 2),
        "substitutions": substitutions,
        "members_checked": len(members),
        "members_optimizable": len(substitutions),
    }
