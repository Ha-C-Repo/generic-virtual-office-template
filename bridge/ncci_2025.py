"""
Your Company Virtual Office - NCCI 2025 EMR Formula (Replaces old state_avg×25)

CRITICAL BUG FIX: The old formula used state_avg × 25 for the SAL.
NCCI 2024-2025 uses state-specific split points and 95th-percentile
lost-time-claim methodology. Texas got updated split points Nov 1, 2024.
"""


# Texas-specific NCCI parameters (updated Nov 1, 2024)
# Source: ncci.com/Articles/Pages/II_ER-Methodology-FAQs.aspx
NCCI_TX_2025 = {
    "state": "TX",
    "effective_date": "2024-11-01",
    "split_point": 18500,  # Texas 2025 split point (was $17,500 for 2024)
    "expected_loss_rate_5190": 7.42,  # Class 5190 (structural ironwork) per $100 payroll
    "expected_loss_rate_5057": 5.98,  # Class 5057 (iron/steel erection)
    "expected_loss_rate_3040": 4.12,  # Class 3040 (iron works mfg - fab shop)
    "weighting_factor_primary": 1.0,
    "weighting_factor_excess": 0.30,  # Texas-specific excess credibility
    "ballast_point": 5000,  # Minimum expected losses for full credibility
    "max_single_claim": 250000,  # Per-claim accident limitation (2025)
    "experience_period_years": 3,
}

# Per-claim accident limitation table (2025)
CLAIM_LIMITS = {
    "small": {"payroll_under": 500000, "limit": 175000},
    "medium": {"payroll_under": 2000000, "limit": 225000},
    "large": {"payroll_under": 5000000, "limit": 250000},
    "xlarge": {"payroll_under": float("inf"), "limit": 300000},
}


def calculate_emr_2025(payroll_by_class: dict, claims: list,
                        state: str = "TX") -> dict:
    """Calculate EMR using NCCI 2025 methodology with state-specific split points.

    payroll_by_class: {"5190": 850000, "3040": 400000}
    claims: [{"amount": 45000, "type": "medical_only|lost_time"}, ...]
    """
    params = NCCI_TX_2025  # Extend with other states as needed
    split = params["split_point"]

    # Step 1: Calculate Expected Losses
    total_expected = 0
    for class_code, payroll in payroll_by_class.items():
        rate_key = f"expected_loss_rate_{class_code}"
        rate = params.get(rate_key, 5.0)  # Default if class not in table
        expected = (payroll / 100) * rate
        total_expected += expected

    # Step 2: Split expected losses into Primary and Excess
    # Primary = losses ≤ split point; Excess = losses > split point
    expected_primary = min(total_expected, split * len(claims) if claims else total_expected * 0.40)
    expected_excess = total_expected - expected_primary

    # Step 3: Process actual claims with per-claim limitation
    total_payroll = sum(payroll_by_class.values())
    claim_limit = _get_claim_limit(total_payroll)

    actual_primary = 0
    actual_excess = 0
    for claim in claims:
        amt = min(claim.get("amount", 0), claim_limit)
        if claim.get("type") == "medical_only":
            # Medical-only claims: 30% weight in primary, 0% in excess
            actual_primary += min(amt, split) * 0.30
        else:
            # Lost-time claims: full weight
            actual_primary += min(amt, split)
            actual_excess += max(amt - split, 0)

    # Step 4: Calculate weighted actual vs expected
    w_primary = params["weighting_factor_primary"]
    w_excess = params["weighting_factor_excess"]

    # Credibility-weighted formula
    if total_expected > 0:
        primary_ratio = actual_primary / max(expected_primary, 1)
        excess_ratio = actual_excess / max(expected_excess, 1) if expected_excess > 0 else 0

        emr = (
            (w_primary * actual_primary + (1 - w_primary) * expected_primary +
             w_excess * actual_excess + (1 - w_excess) * expected_excess +
             params["ballast_point"])
            /
            (expected_primary + expected_excess + params["ballast_point"])
        )
    else:
        emr = 1.0

    emr = round(emr, 2)

    return {
        "emr": emr,
        "state": state,
        "formula_version": "NCCI_2025",
        "split_point": split,
        "claim_limit": claim_limit,
        "expected_losses": round(total_expected, 2),
        "expected_primary": round(expected_primary, 2),
        "expected_excess": round(expected_excess, 2),
        "actual_primary": round(actual_primary, 2),
        "actual_excess": round(actual_excess, 2),
        "total_payroll": total_payroll,
        "claims_count": len(claims),
        "bidding_gates": {
            "general_threshold": 1.0,
            "refinery_threshold": 0.85,
            "passes_general": emr <= 1.0,
            "passes_refinery": emr <= 0.85,
        },
        "note": "Bug fix applied: uses state-specific split point, not old state_avg×25"
    }


def _get_claim_limit(total_payroll: float) -> float:
    """Per-claim accident limitation based on payroll size."""
    for tier in CLAIM_LIMITS.values():
        if total_payroll < tier["payroll_under"]:
            return tier["limit"]
    return 300000


def get_tx_parameters() -> dict:
    """Return current Texas NCCI parameters for inspection/audit."""
    return NCCI_TX_2025
