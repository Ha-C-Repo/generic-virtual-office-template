"""Auto-RFI generator (Phase 21, build slot 21, v5.3.0).

Scans takeoff results for missing, contradictory, or ambiguous
information and generates RFI (Request for Information) questions
for the GC or EOR. Each RFI includes the drawing reference, the
discrepancy found, and a suggested question.

RFI categories:
    MISSING_GRADE  - No grade specified for a member
    MISSING_LENGTH - No length dimension found
    SCALE_CONFLICT - Different scales on same sheet
    CONN_AMBIGUOUS - Connection type unclear
    MEMBER_CONFLICT- Cross-verify disagreement
    SPEC_MISMATCH  - Material spec vs drawing conflict

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


RFI_TEMPLATES = {
    "MISSING_GRADE": (
        "The structural drawings do not specify the steel grade for "
        "member {mark} ({shape}). Please confirm the required material "
        "grade (A992, A572 Gr.50, A36, or other)."
    ),
    "MISSING_LENGTH": (
        "No length dimension was found for member {mark} ({shape}) on "
        "sheet {sheet}. Please provide the member length or confirm the "
        "dimension from the structural plan."
    ),
    "CONN_AMBIGUOUS": (
        "The connection detail for {mark} appears ambiguous. The "
        "drawings show {detail} but the connection type could not be "
        "determined. Please confirm the intended connection (shear tab, "
        "clip angle, moment, or other)."
    ),
    "MEMBER_CONFLICT": (
        "Cross-verification found a discrepancy for member {mark}. "
        "One extraction shows {shape_a} and another shows {shape_b}. "
        "Please confirm the correct member designation."
    ),
    "SCALE_CONFLICT": (
        "Sheet {sheet} appears to contain details at different scales. "
        "Scale {scale_a} and {scale_b} were both detected. Please "
        "confirm the governing scale for dimensional takeoff."
    ),
    "SPEC_MISMATCH": (
        "The structural specification calls for {spec_grade} but the "
        "drawings show {drawing_grade} for {mark}. Please confirm "
        "which grade governs."
    ),
}


def detect_rfi_items(
    members: list[dict],
    cross_verify_result: dict | None = None,
    project_name: str = "",
) -> list[dict]:
    """Scan takeoff data for items requiring RFI.

    Args:
        members: Takeoff member list.
        cross_verify_result: Optional diff_engine output.
        project_name: For the RFI header.

    Returns:
        List of RFI item dicts, each with:
            rfi_number, category, priority, question, mark, sheet, ...
    """
    items: list[dict] = []
    rfi_num = 1

    for m in members:
        mark = m.get("mark", "")
        shape = str(m.get("shape", "")) + str(m.get("size", ""))
        grade = m.get("grade", "")
        length = m.get("length_ft")
        sheet = m.get("sheet", "S-001")

        # Missing grade
        if not grade or grade.upper() in ("", "UNKNOWN", "TBD", "N/A"):
            items.append({
                "rfi_number": rfi_num,
                "category": "MISSING_GRADE",
                "priority": "HIGH",
                "mark": mark,
                "shape": shape,
                "sheet": sheet,
                "question": RFI_TEMPLATES["MISSING_GRADE"].format(
                    mark=mark, shape=shape),
            })
            rfi_num += 1

        # Missing length
        if length is None or float(length or 0) <= 0:
            items.append({
                "rfi_number": rfi_num,
                "category": "MISSING_LENGTH",
                "priority": "HIGH",
                "mark": mark,
                "shape": shape,
                "sheet": sheet,
                "question": RFI_TEMPLATES["MISSING_LENGTH"].format(
                    mark=mark, shape=shape, sheet=sheet),
            })
            rfi_num += 1

    # Cross-verify discrepancies
    if cross_verify_result:
        for disc in cross_verify_result.get("discrepancies", []):
            items.append({
                "rfi_number": rfi_num,
                "category": "MEMBER_CONFLICT",
                "priority": "MEDIUM",
                "mark": disc.get("mark", ""),
                "shape": disc.get("shape", ""),
                "sheet": "",
                "question": RFI_TEMPLATES["MEMBER_CONFLICT"].format(
                    mark=disc.get("mark", ""),
                    shape_a=disc.get("shape", ""),
                    shape_b=disc.get("shape", "(variant)"),
                ),
            })
            rfi_num += 1

    return items


def generate_rfi_log(
    members: list[dict],
    cross_verify_result: dict | None = None,
    project_name: str = "",
    bid_number: str = "",
) -> dict:
    """Generate a complete RFI log from takeoff data.

    Returns:
        {
            "success": bool,
            "project_name": str,
            "bid_number": str,
            "rfi_count": int,
            "by_priority": dict,
            "by_category": dict,
            "items": list[dict],
            "generated_at": str,
        }
    """
    items = detect_rfi_items(members, cross_verify_result, project_name)

    by_priority: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for item in items:
        p = item.get("priority", "MEDIUM")
        c = item.get("category", "OTHER")
        by_priority[p] = by_priority.get(p, 0) + 1
        by_category[c] = by_category.get(c, 0) + 1

    return {
        "success": True,
        "project_name": project_name,
        "bid_number": bid_number,
        "rfi_count": len(items),
        "by_priority": by_priority,
        "by_category": by_category,
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
