"""
Correction Bridge - Workbench to Backend Connection
=====================================================
Phase 3 of the Sketchdeck parity roadmap (v3.7.0).

Connects the Review Workbench frontend to the correction lake and
the existing self_healer. When a user corrects a detection:
  1. Records the correction in the lake (for active learning)
  2. Records it in the self_healer (for immediate firm-specific rules)
  3. Updates the takeoff data for re-export to Tekla

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import logging

from . import correction_lake

log = logging.getLogger("correction_bridge")


def process_correction(
    project_id: str,
    member_id: str,
    field_name: str,
    old_value: str,
    new_value: str,
    source_drawing: str = "",
    page_num: int = 0,
    confidence: float = 0.0,
    user: str = "joseph",
    pe_firm: str = "",
) -> dict:
    """Process a user correction from the workbench.

    Writes to both the correction lake (Phase 4 learning) and the
    existing self_healer (immediate firm rules).

    Args:
        project_id: Bid number
        member_id: ID or mark of the corrected member
        field_name: Which field was corrected (shape, qty, mark, camber, etc.)
        old_value: What the AI detected
        new_value: What the user corrected it to
        source_drawing: Sheet ID
        page_num: Page number
        confidence: Original AI confidence
        user: Who made the correction
        pe_firm: Engineering firm name (for firm-specific rules)

    Returns:
        {"saved": bool, "lake_result": dict, "healer_result": dict}
    """
    # 1. Write to correction lake
    lake_result = correction_lake.record_correction(
        project_id=project_id,
        original_ai=old_value,
        corrected=new_value,
        source_drawing=source_drawing,
        page_num=page_num,
        confidence=confidence,
        user=user,
        correction_type=field_name,
        extra={"member_id": member_id},
    )

    # 2. Write to self_healer (for shape corrections)
    healer_result = {"recorded": False}
    if field_name == "shape":
        try:
            from bridge.drawing_intel.self_healer import record_correction as heal_record
            heal_result = heal_record(
                raw_text=old_value,
                corrected_shape=new_value,
                pe_firm=pe_firm,
                source_drawing=source_drawing,
            )
            healer_result = {"recorded": True, "result": str(heal_result)[:200]}
        except Exception as e:
            healer_result = {"recorded": False, "error": str(e)[:200]}
            log.warning(f"Self-healer recording failed: {e}")

    return {
        "saved": lake_result.get("saved", False),
        "lake_result": lake_result,
        "healer_result": healer_result,
    }


def get_workbench_data(project_id: str = "", members_json: str = "") -> dict:
    """Get data formatted for the workbench overlay.

    Combines member takeoff data with correction history to show
    which items have been user-verified vs AI-only.

    Args:
        project_id: Bid number to filter corrections
        members_json: JSON array of member dicts from takeoff

    Returns:
        {
            "members": [...],     # members with correction status
            "corrections": [...], # correction history for this project
            "stats": {...},       # summary stats
        }
    """
    members = []
    if members_json:
        try:
            members = json.loads(members_json)
        except (json.JSONDecodeError, TypeError):
            members = []

    # Get corrections for this project
    corrections = correction_lake.get_records(
        limit=500,
        project_id=project_id,
    )

    # Build a set of corrected member IDs
    corrected_ids = set()
    for c in corrections:
        extra = c.get("extra", {})
        if isinstance(extra, dict):
            mid = extra.get("member_id", "")
            if mid:
                corrected_ids.add(mid)

    # Annotate members with status
    for m in members:
        mid = m.get("id") or m.get("mark") or ""
        conf = m.get("confidence", 0.8)

        if str(mid) in corrected_ids:
            m["workbench_status"] = "approved"
        elif conf >= 0.9:
            m["workbench_status"] = "high_confidence"
        elif conf >= 0.5:
            m["workbench_status"] = "needs_review"
        else:
            m["workbench_status"] = "low_confidence"

    # Stats
    by_status = {}
    for m in members:
        st = m.get("workbench_status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "members": members,
        "corrections": corrections[:50],  # last 50 for the UI
        "stats": {
            "total_members": len(members),
            "by_status": by_status,
            "total_corrections": len(corrections),
            "needs_prompt_update": correction_lake.count_records() >= 500,
        },
    }
