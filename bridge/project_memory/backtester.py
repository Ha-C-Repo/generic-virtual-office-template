"""Shadow project backtester.

Takes a completed project with known manual takeoff results, runs the
same drawings through the AI pipeline, and compares the two. Produces
real accuracy numbers rather than fabricated claims. If accuracy is 94
percent, we say 94 percent. We do not claim 99.9 percent without
evidence.

Usage flow:
    1. Joseph picks a completed project with a finalized manual takeoff.
    2. He exports the manual takeoff as a list of member dicts.
    3. The backtester runs the same PDF through process_full_takeoff_v2.
    4. It diffs the two member lists and reports:
       - accuracy (percent of AI members that match manual)
       - missed_members (in manual but not in AI)
       - false_positives (in AI but not in manual)
       - tonnage_delta (abs difference in total tons)
    5. Results are indexed into project memory for trend tracking.

The diff is shape-level, not location-level. A member matches if its
normalized AISC designation matches a manual entry, regardless of
mark or page. This mirrors how a PE reviewer would audit the BOM.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# Estimated per-structural-page API costs for Phase 3 subtask routing.
# Based on Phase 3 SUBTASK_ROUTING: gpt4o primary for ocr_small_text,
# claude primary for table_extract, gemini (free) primary for spatial.
# Crosscheck models add one additional call on high-density pages (~50%).
_PHASE3_COST_PER_STRUCTURAL_PAGE = {
    "ocr_small_text_primary_gpt4o": 0.05,   # 1 call per page
    "table_extract_primary_claude": 0.03,    # ~0.5 calls (not every page)
    "spatial_classify_primary_gemini": 0.00, # covered by subscription
    "crosscheck_claude_50pct": 0.015,        # claude crosscheck on ~50% of pages
    "crosscheck_gpt4o_50pct": 0.025,         # gpt4o crosscheck on ~50% of pages
}
_PHASE3_USD_PER_STRUCTURAL_PAGE = round(
    sum(_PHASE3_COST_PER_STRUCTURAL_PAGE.values()), 4
)


def _normalize_shape(m: dict) -> str:
    """Extract a normalized shape string from a member dict.

    Handles both AI output (shape + size) and manual input (designation
    field or combined shape field). Strips whitespace and uppercases.
    """
    # Try combined designation first (manual exports often use this)
    designation = str(
        m.get("designation")
        or m.get("normalized")
        or m.get("shape", "") + str(m.get("size", ""))
    ).strip().upper()
    return designation


def _build_shape_bag(members: list[dict]) -> Counter:
    """Build a bag-of-shapes from a member list, factoring in qty."""
    bag: Counter = Counter()
    for m in members:
        shape = _normalize_shape(m)
        if not shape:
            continue
        qty = int(m.get("qty", 1) or 1)
        bag[shape] += qty
    return bag


def backtest(
    manual_members: list[dict],
    ai_members: list[dict],
    manual_tons: float = 0.0,
    ai_tons: float = 0.0,
    bid_number: str = "",
    project_name: str = "",
) -> dict:
    """Compare AI takeoff against manual ground truth.

    Args:
        manual_members: List of member dicts from the manual takeoff.
            Must have at least a shape/designation key.
        ai_members: List of member dicts from the AI pipeline.
        manual_tons: Manually computed tonnage (optional, for delta).
        ai_tons: AI-computed tonnage (optional, for delta).
        bid_number: For indexing the backtest result.
        project_name: For the report.

    Returns:
        {
            "accuracy_pct": float,
            "precision_pct": float,
            "recall_pct": float,
            "missed_members": list of shape strings,
            "false_positives": list of shape strings,
            "matched_count": int,
            "manual_count": int,
            "ai_count": int,
            "tonnage_delta_tons": float,
            "tonnage_delta_pct": float,
            "bid_number": str,
            "project_name": str,
            "timestamp": str,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    manual_bag = _build_shape_bag(manual_members)
    ai_bag = _build_shape_bag(ai_members)

    manual_total = sum(manual_bag.values())
    ai_total = sum(ai_bag.values())

    if manual_total == 0:
        warnings.append("manual_members empty or no valid shapes")
        return {
            "accuracy_pct": 0.0,
            "precision_pct": 0.0,
            "recall_pct": 0.0,
            "missed_members": [],
            "false_positives": list(ai_bag.elements()),
            "matched_count": 0,
            "manual_count": 0,
            "ai_count": ai_total,
            "tonnage_delta_tons": 0.0,
            "tonnage_delta_pct": 0.0,
            "bid_number": bid_number,
            "project_name": project_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warnings": warnings,
        }

    # Matched = intersection (min of each shape's count)
    all_shapes = set(manual_bag.keys()) | set(ai_bag.keys())
    matched = sum(min(manual_bag[s], ai_bag[s]) for s in all_shapes)

    # Missed = shapes in manual but not sufficiently in AI
    missed: list[str] = []
    for shape in manual_bag:
        shortfall = manual_bag[shape] - ai_bag.get(shape, 0)
        if shortfall > 0:
            missed.extend([shape] * shortfall)

    # False positives = shapes in AI but not in manual
    false_pos: list[str] = []
    for shape in ai_bag:
        excess = ai_bag[shape] - manual_bag.get(shape, 0)
        if excess > 0:
            false_pos.extend([shape] * excess)

    # Accuracy = matched / manual_total (what fraction of truth did we get)
    accuracy = (matched / manual_total * 100.0) if manual_total > 0 else 0.0

    # Precision = matched / ai_total (what fraction of AI output was correct)
    precision = (matched / ai_total * 100.0) if ai_total > 0 else 0.0

    # Recall = accuracy (same as matched / manual_total)
    recall = accuracy

    # Tonnage delta
    ton_delta = ai_tons - manual_tons
    ton_delta_pct = (
        (ton_delta / manual_tons * 100.0) if manual_tons > 0 else 0.0
    )

    return {
        "accuracy_pct": round(accuracy, 2),
        "precision_pct": round(precision, 2),
        "recall_pct": round(recall, 2),
        "missed_members": missed,
        "false_positives": false_pos,
        "matched_count": matched,
        "manual_count": manual_total,
        "ai_count": ai_total,
        "tonnage_delta_tons": round(ton_delta, 4),
        "tonnage_delta_pct": round(ton_delta_pct, 2),
        "bid_number": bid_number,
        "project_name": project_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
    }


def routing_backtest(
    pdf_path: str,
    bid_number: str = "",
    project_name: str = "",
    manual_members: Optional[list[dict]] = None,
    manual_tons: float = 0.0,
    dry_run: bool = True,
) -> dict:
    """Compare text-extraction baseline against manual ground truth.

    Runs Stage 1 (pymupdf4llm text extraction, zero API cost) on the real
    PDF, then compares whatever members text-only extraction finds against
    the manual BOM. Vision stages are skipped when dry_run=True.

    Establishes the text-only baseline so Phase 3 vision improvements can
    be measured against a real starting point.

    Args:
        pdf_path:       Path to the structural drawing PDF.
        bid_number:     Bid identifier for tracking.
        project_name:   Human-readable project name.
        manual_members: Ground truth member list from manual BOM. If None,
                        the backtest comparison is skipped.
        manual_tons:    Manual BOM tonnage for delta comparison.
        dry_run:        If True, skip all vision API calls. Only
                        pymupdf4llm text extraction runs (zero cost).

    Returns:
        {
            "pdf_path": str,
            "pdf_page_count": int,
            "structural_page_count": int,
            "dry_run": bool,
            "text_only_member_count": int,
            "backtest_result": dict or None,
            "estimated_cost_per_structural_page_usd": float,
            "estimated_total_vision_cost_usd": float,
            "timestamp": str,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    p = Path(pdf_path)
    if not p.exists():
        return {
            "pdf_path": pdf_path,
            "pdf_page_count": 0,
            "structural_page_count": 0,
            "dry_run": dry_run,
            "text_only_member_count": 0,
            "backtest_result": None,
            "estimated_cost_per_structural_page_usd": _PHASE3_USD_PER_STRUCTURAL_PAGE,
            "estimated_total_vision_cost_usd": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warnings": [f"pdf_not_found: {pdf_path}"],
        }

    # Stage 1: text extraction (zero API cost)
    try:
        from bridge.drawing_intel.preprocessor import extract_drawing_set
        draw_result = extract_drawing_set(str(p))
        raw_members = draw_result.get("members", [])
        pages = draw_result.get("pages", [])
        stats = draw_result.get("stats", {})
        pdf_page_count = stats.get("total_pages", len(pages))
        structural_page_count = stats.get("structural_pages", 0)
        if structural_page_count == 0:
            # Count from page list
            structural_page_count = sum(
                1 for pg in pages if pg.get("has_structural"))
    except Exception as e:
        warnings.append(f"extract_drawing_set_failed: {e}")
        log.error("routing_backtest extract failed: %s", e)
        raw_members = []
        pages = []
        pdf_page_count = 0
        structural_page_count = 0

    text_member_count = len(raw_members)

    # Stage 2: AISC validation of text-extracted members (zero API cost)
    ai_members: list[dict] = []
    if raw_members:
        try:
            from bridge.aisc_validator import validate_shape
            for m in raw_members:
                shape = f"{m.get('shape', '')}{m.get('size', '')}"
                r = validate_shape(shape)
                if r.get("valid", False):
                    ai_members.append(m)
        except Exception as e:
            warnings.append(f"aisc_validate_failed: {e}")

    if dry_run:
        warnings.append(
            "dry_run: vision stages skipped. Text-only baseline only.")

    # Estimate cost if we ran full vision
    total_cost_est = round(
        structural_page_count * _PHASE3_USD_PER_STRUCTURAL_PAGE, 4)

    # Backtest comparison against manual BOM
    backtest_result = None
    if manual_members is not None:
        ai_tons = sum(
            float(m.get("weight_lbs", 0) or 0)
            for m in ai_members
        ) / 2000.0
        backtest_result = backtest(
            manual_members=manual_members,
            ai_members=ai_members,
            manual_tons=manual_tons,
            ai_tons=ai_tons,
            bid_number=bid_number,
            project_name=project_name,
        )

    return {
        "pdf_path": str(p),
        "pdf_page_count": pdf_page_count,
        "structural_page_count": structural_page_count,
        "dry_run": dry_run,
        "text_only_member_count": text_member_count,
        "backtest_result": backtest_result,
        "estimated_cost_per_structural_page_usd": _PHASE3_USD_PER_STRUCTURAL_PAGE,
        "estimated_total_vision_cost_usd": total_cost_est,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings,
    }
