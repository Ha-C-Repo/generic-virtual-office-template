"""What-if grade comparison (Phase 13, build slot 13, v4.4.1).

Compares total material cost across steel grades for a given member
list. Shows Owner the cost impact of grade substitution before the
PE stamps the drawings.

Default price table is static (Houston May 2026 calibration). The
steel_price agent can inject live prices at runtime via the
`price_overrides` parameter. The module never calls the agent
itself - that is the caller's responsibility.

PE approval warning: grade changes require engineer approval. This
module flags the warning in every output so it cannot be missed on
the bid card.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


# Default $/lb by grade. Houston-market averages, May 2026 calibration.
# Joseph can override per call via price_overrides.

DEFAULT_PRICES_PER_LB: dict[str, float] = {
    "A36": 0.47,
    "A572": 0.52,
    "A572 Gr.50": 0.52,
    "A992": 0.55,
    "A500 Gr.B": 0.50,
    "A500 Gr.C": 0.53,
}

# PE warning text. Included in every output.
PE_WARNING = (
    "Grade substitution requires Professional Engineer approval. "
    "Do not commit to an alternate grade without a PE-stamped "
    "review of the load calculations."
)


def _member_weight_lbs(member: dict) -> float:
    """Extract or compute per-member weight. Falls back to AISC lookup
    if the member dict does not carry pre-computed weight data."""
    w = member.get("weight_lbs") or member.get("total_weight_lbs") or 0.0
    if w and float(w) > 0:
        return float(w)
    # Fallback: qty * length_ft * plf (if available)
    plf = float(member.get("plf", 0) or 0)
    length = float(member.get("length_ft", 0) or 0)
    qty = int(member.get("qty", 1) or 1)
    if plf > 0 and length > 0:
        return plf * length * qty
    # Last resort: AISC lookup for lb/ft from shape name
    if length > 0:
        shape_name = str(member.get("shape", "") or "").strip()
        if shape_name:
            try:
                from bridge.aisc_validator import validate_shape
                result = validate_shape(shape_name)
                if isinstance(result, dict) and result.get("valid"):
                    lookup_plf = result.get("weight_per_ft", 0)
                    if lookup_plf and lookup_plf > 0:
                        return float(lookup_plf) * length * qty
            except Exception:
                pass
    return 0.0


def _current_grade(member: dict) -> str:
    """Read the member's specified grade. Default A992 (wide flange)."""
    g = str(member.get("grade", "") or "").strip().upper()
    if not g:
        shape = str(member.get("shape", "") or "").upper()
        if shape.startswith("HSS") or shape.startswith("TS"):
            return "A500 Gr.B"
        return "A992"
    return g


def grade_comparison(
    members: list[dict],
    grades: list[str] | None = None,
    price_overrides: dict[str, float] | None = None,
) -> dict:
    """Compare total material cost across steel grades.

    Args:
        members: Takeoff member dicts. Uses weight_lbs (or plf + length)
            and grade fields.
        grades: Grades to compare. Defaults to all five in the table.
        price_overrides: Inject live $/lb from the steel_price agent.

    Returns:
        {
            "current_grade": str (most common grade in the member list),
            "total_weight_lbs": float,
            "scenarios": list of {grade, price_per_lb, total_cost, delta_vs_current},
            "cheapest_grade": str,
            "savings_vs_current": float,
            "pe_warning": str,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    prices = dict(DEFAULT_PRICES_PER_LB)
    if price_overrides:
        prices.update(price_overrides)

    if grades is None:
        grades = list(DEFAULT_PRICES_PER_LB.keys())

    # Deduplicate while preserving order
    seen = set()
    unique_grades = []
    for g in grades:
        gn = g.strip()
        if gn not in seen:
            seen.add(gn)
            unique_grades.append(gn)

    # Compute total weight and current cost
    total_lbs = 0.0
    grade_counts: dict[str, int] = {}
    for m in members:
        w = _member_weight_lbs(m)
        total_lbs += w
        g = _current_grade(m)
        grade_counts[g] = grade_counts.get(g, 0) + 1

    if total_lbs <= 0:
        warnings.append("no weight data in member list")

    # Most common grade
    current_grade = max(grade_counts, key=grade_counts.get) \
        if grade_counts else "A992"

    current_price = prices.get(current_grade, 0.55)
    current_cost = total_lbs * current_price

    # Build scenarios
    scenarios = []
    for g in unique_grades:
        ppl = prices.get(g)
        if ppl is None:
            warnings.append(f"no price for grade {g}, skipped")
            continue
        cost = total_lbs * ppl
        delta = cost - current_cost
        scenarios.append({
            "grade": g,
            "price_per_lb": round(ppl, 4),
            "total_cost": round(cost, 2),
            "delta_vs_current": round(delta, 2),
        })

    # Find cheapest
    cheapest = min(scenarios, key=lambda s: s["total_cost"]) \
               if scenarios else {"grade": current_grade, "total_cost": current_cost}
    savings = current_cost - cheapest["total_cost"]

    return {
        "current_grade": current_grade,
        "total_weight_lbs": round(total_lbs, 2),
        "scenarios": scenarios,
        "cheapest_grade": cheapest["grade"],
        "savings_vs_current": round(savings, 2),
        "pe_warning": PE_WARNING,
        "warnings": warnings,
    }
