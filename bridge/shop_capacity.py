"""Shop capacity-aware margin adjustment (Phase 24, v5.6.0).

When the shop is busy, bid higher. When slow, bid aggressive to keep
the crew employed. the Owner's pricing instinct, quantified.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging

log = logging.getLogger(__name__)


# Utilization bands and margin adjustments
BANDS = [
    (0.40, -0.03, "Bid aggressive. Keep crew busy."),
    (0.70,  0.00, "Standard pricing."),
    (0.85,  0.03, "Premium pricing recommended."),
    (1.00,  0.05, "Very premium or pass. Consider overtime cost."),
    (9.99,  0.08, "Over capacity. Pass or subcontract."),
]


def capacity_adjusted_margin(
    direct_cost: float,
    current_backlog_tons: float = 0.0,
    shop_capacity_tons_per_week: float = 20.0,
    target_weeks: int = 4,
    base_margin: float = 0.20,
) -> dict:
    """Adjust bid margin based on shop utilization.

    Args:
        direct_cost: Pre-margin direct cost ($).
        current_backlog_tons: Tons currently in the shop queue.
        shop_capacity_tons_per_week: Shop throughput (tons/week).
        target_weeks: Planning horizon.
        base_margin: Default margin before adjustment.

    Returns:
        {
            "utilization_pct": float,
            "base_margin": float,
            "margin_adjustment": float,
            "recommended_margin": float,
            "reasoning": str,
            "bid_total": float,
            "direct_cost": float,
        }
    """
    total_capacity = shop_capacity_tons_per_week * target_weeks
    utilization = current_backlog_tons / max(total_capacity, 0.01)
    utilization_pct = round(utilization * 100, 1)

    adjustment = 0.0
    reasoning = ""
    for threshold, adj, reason in BANDS:
        if utilization <= threshold:
            adjustment = adj
            reasoning = reason
            break

    recommended = round(base_margin + adjustment, 4)
    recommended = max(0.05, min(0.50, recommended))  # clamp

    if recommended > 0 and recommended < 1.0:
        bid_total = round(direct_cost / (1.0 - recommended), 2)
    else:
        bid_total = round(direct_cost * 1.2, 2)

    return {
        "utilization_pct": utilization_pct,
        "current_backlog_tons": current_backlog_tons,
        "shop_capacity_tons_per_week": shop_capacity_tons_per_week,
        "base_margin": base_margin,
        "margin_adjustment": adjustment,
        "recommended_margin": recommended,
        "reasoning": reasoning,
        "direct_cost": direct_cost,
        "bid_total": bid_total,
    }
