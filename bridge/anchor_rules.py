"""
Anchor rod count and diameter rules. Authority: Ivan email 2026-05-27 Q4.

Confirms baseline rules and adds the braced-frame and exceptional cases
Ivan called out.
"""

from __future__ import annotations
from typing import Optional


DEFAULT_ANCHOR_DIAMETER_INCHES = 0.75  # 3/4 inch UNO
ANCHORS_PER_SIMPLE_PLATE = 4
ANCHORS_PER_BRACED_FRAME_MIN = 6
ANCHORS_PER_BRACED_FRAME_MAX = 8
ANCHORS_PER_MOMENT_PLATE = 8

# Conditions that may exceed the standard counts. Reported as flags, not
# auto-multiplied, because they depend on the specific load case.
EXCEPTIONAL_CONDITIONS = (
    "large_HSS_columns",
    "high_seismic_zone",
    "crane_columns",
    "cantilevered_conditions",
)


def minimum_anchor_count(
    column_count: int,
    base_plate_type: str = "simple",
    is_braced_frame: bool = False,
) -> dict:
    """Compute the minimum anchor count for a given column census.

    Args:
        column_count: Number of columns in the bid.
        base_plate_type: "simple" or "moment".
        is_braced_frame: True if any column is at a braced-frame location.

    Returns:
        dict with keys:
            count: int, minimum anchor rods total
            per_column: int, the per-column factor used
            diameter_inches: float, default diameter
            rule_applied: str, which rule produced the count
            confidence: str
    """
    bt = base_plate_type.strip().lower()
    if bt == "moment":
        per = ANCHORS_PER_MOMENT_PLATE
        rule = "moment_plate_minimum_8"
        conf = "high"
    elif is_braced_frame:
        # Ivan said 6 to 8. Pick the midpoint conservatively. Maintainer can
        # override per project by passing base_plate_type="moment".
        per = ANCHORS_PER_BRACED_FRAME_MAX
        rule = "braced_frame_minimum_8_per_Ivan_2026_05_27"
        conf = "high"
    else:
        per = ANCHORS_PER_SIMPLE_PLATE
        rule = "simple_plate_minimum_4"
        conf = "high"
    return {
        "count": int(column_count) * per,
        "per_column": per,
        "diameter_inches": DEFAULT_ANCHOR_DIAMETER_INCHES,
        "rule_applied": rule,
        "confidence": conf,
    }


def flag_exceptional_conditions(
    has_large_hss: bool = False,
    high_seismic: bool = False,
    has_crane_columns: bool = False,
    has_cantilever: bool = False,
) -> list:
    """Return a list of exceptional conditions that may push anchor counts
    above the standard. These are FLAGs for human verification, not
    auto-multiplications.
    """
    flags = []
    if has_large_hss:
        flags.append("large_HSS_columns")
    if high_seismic:
        flags.append("high_seismic_zone")
    if has_crane_columns:
        flags.append("crane_columns")
    if has_cantilever:
        flags.append("cantilevered_conditions")
    return flags


def check_anchor_count(actual_count: int, expected: dict) -> dict:
    """Compare an actual anchor count from takeoff to the expected minimum.

    Returns a verdict:
        OK              actual >= expected
        UNDER_COUNT     actual < expected (BLOCK)
        OVER_COUNT      actual > 1.5 * expected (FLAG for review)
    """
    exp = expected.get("count", 0)
    if actual_count < exp:
        return {"verdict": "UNDER_COUNT", "actual": actual_count, "expected": exp,
                "delta": actual_count - exp,
                "message": f"Anchor count {actual_count} below minimum {exp} "
                           f"({expected.get('rule_applied','?')}). BLOCK."}
    if actual_count > 1.5 * exp and exp > 0:
        return {"verdict": "OVER_COUNT", "actual": actual_count, "expected": exp,
                "delta": actual_count - exp,
                "message": f"Anchor count {actual_count} is 50%+ above minimum "
                           f"{exp}. Verify load case."}
    return {"verdict": "OK", "actual": actual_count, "expected": exp, "delta": 0}
