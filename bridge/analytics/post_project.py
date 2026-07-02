"""Post-project analytics (Phase 27, v5.9.0).

After a job completes, compare actual production data against bid
estimates. Every bid gets more accurate than the last.

Owner sees: "Estimated 20% margin. Actual 14.8%. Lesson: moment
frame multiplier should be 2.9x for this engineer's drawings."

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def compare_actuals_vs_estimated(
    job_number: str = "",
    estimated_tons: float = 0.0,
    actual_tons: float = 0.0,
    estimated_fab_hrs: float = 0.0,
    actual_fab_hrs: float = 0.0,
    estimated_bid_usd: float = 0.0,
    actual_cost_usd: float = 0.0,
    notes: list[str] | None = None,
) -> dict:
    """Compare actual production data to bid estimates.

    Returns:
        {
            "job_number": str,
            "tonnage_variance_pct": float,
            "hours_variance_pct": float,
            "cost_variance_pct": float,
            "actual_hrs_per_ton": float,
            "estimated_margin_pct": float,
            "actual_margin_pct": float,
            "lessons": list[str],
            "recommendation": str,
        }
    """
    # Tonnage variance
    ton_var = 0.0
    if estimated_tons > 0:
        ton_var = (actual_tons - estimated_tons) / estimated_tons * 100

    # Hours variance
    hrs_var = 0.0
    if estimated_fab_hrs > 0:
        hrs_var = (actual_fab_hrs - estimated_fab_hrs) / estimated_fab_hrs * 100

    # Cost variance
    cost_var = 0.0
    if estimated_bid_usd > 0:
        cost_var = (actual_cost_usd - estimated_bid_usd) / estimated_bid_usd * 100

    # Actual hrs/ton
    actual_hpt = actual_fab_hrs / max(actual_tons, 0.01)

    # Margin
    est_margin = 0.0
    if estimated_bid_usd > 0 and actual_cost_usd > 0:
        est_margin = (estimated_bid_usd - actual_cost_usd) / estimated_bid_usd * 100
    act_margin = 0.0
    if estimated_bid_usd > 0:
        act_margin = (estimated_bid_usd - actual_cost_usd) / estimated_bid_usd * 100

    # Generate lessons
    lessons = list(notes or [])
    if hrs_var > 15:
        lessons.append(
            f"Fab hours ran {hrs_var:.0f}% over estimate. "
            f"Actual: {actual_hpt:.1f} hrs/ton vs 11 baseline.")
    if ton_var > 5:
        lessons.append(
            f"Tonnage was {ton_var:.1f}% higher than estimated. "
            f"Check connection weight assumptions.")
    if cost_var > 10:
        lessons.append(
            f"Costs exceeded bid by {cost_var:.1f}%. "
            f"Review material pricing assumptions.")

    # Recommendation
    if actual_hpt > 13:
        rec = (f"Adjust fab baseline from 11 to {actual_hpt:.1f} hrs/ton "
               f"for similar projects (complex connections or AESS).")
    elif actual_hpt < 9:
        rec = (f"This job ran efficiently at {actual_hpt:.1f} hrs/ton. "
               f"Consider bidding more aggressively on similar work.")
    else:
        rec = f"Performance was close to baseline ({actual_hpt:.1f} hrs/ton). No adjustment needed."

    return {
        "success": True,
        "job_number": job_number,
        "estimated_tons": estimated_tons,
        "actual_tons": actual_tons,
        "tonnage_variance_pct": round(ton_var, 1),
        "estimated_fab_hrs": estimated_fab_hrs,
        "actual_fab_hrs": actual_fab_hrs,
        "hours_variance_pct": round(hrs_var, 1),
        "actual_hrs_per_ton": round(actual_hpt, 1),
        "estimated_bid_usd": estimated_bid_usd,
        "actual_cost_usd": actual_cost_usd,
        "cost_variance_pct": round(cost_var, 1),
        "actual_margin_pct": round(act_margin, 1),
        "lessons": lessons,
        "recommendation": rec,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
