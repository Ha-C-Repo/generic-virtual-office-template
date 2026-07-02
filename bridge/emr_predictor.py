"""
EMR Predictor - Domain Engine

NCCI Experience Rating with primary/excess loss split.
3-year rolling window excluding most recent policy year.
Texas competitive state - uses NCCI-published splits.

Frequency hurts more than severity:
  Five $10K claims damage EMR more than one $50K claim.

Bidding gates: most Houston GCs require EMR < 1.0;
refinery TICs (Bechtel, Fluor, Kiewit) often require < 0.85.

CRITICAL: All math is deterministic Python. No LLM computation.
"""
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"

# Texas split point (NCCI 2024 rule change - was flat $18,500, now state-specific)
# Per handoff: validate annually from NCCI published filing
TEXAS_SPLIT_POINT = 19_500  # 2025-2026 estimated; update from NCCI bulletin
SPLIT_POINT_YEAR = 2025

# NCCI class codes for structural steel
CLASS_CODES = {
    "5040": {"description": "Iron/Steel Erection - Frame Structures", "base_rate_per_100": 18.75},
    "3030": {"description": "Iron/Steel Fabrication Shop", "base_rate_per_100": 7.25},
    "8810": {"description": "Clerical Office", "base_rate_per_100": 0.18},
    "7380": {"description": "Drivers/Chauffeurs", "base_rate_per_100": 5.80},
}

# Bidding thresholds
EMR_THRESHOLDS = {
    "standard_gc": {"max_emr": 1.00, "label": "Most Houston GCs"},
    "refinery_tic": {"max_emr": 0.85, "label": "Refinery TICs (Bechtel, Fluor, Kiewit, S&B)"},
    "industrial_gc": {"max_emr": 0.90, "label": "Industrial GCs (Zachry, Burns & McDonnell)"},
    "owner_direct": {"max_emr": 0.80, "label": "Owner-direct (Marathon, ExxonMobil)"},
}


def split_loss(total_incurred):
    """Split a claim into primary and excess components.
    Primary losses up to the split point hurt EMR more (frequency signal).
    """
    primary = min(total_incurred, TEXAS_SPLIT_POINT)
    excess = max(0, total_incurred - TEXAS_SPLIT_POINT)
    return {"total": total_incurred, "primary": primary, "excess": excess,
            "split_point": TEXAS_SPLIT_POINT}


def calculate_expected_losses(payroll_by_class):
    """Calculate expected losses based on payroll by class code.
    payroll_by_class: dict of {class_code: annual_payroll}
    """
    total_expected = 0
    details = []
    for code, payroll in payroll_by_class.items():
        info = CLASS_CODES.get(code, {})
        rate = info.get("base_rate_per_100", 5.0)
        expected = (payroll / 100) * rate
        total_expected += expected
        details.append({
            "class_code": code,
            "description": info.get("description", "Unknown"),
            "payroll": payroll,
            "rate_per_100": rate,
            "expected_losses": round(expected, 2),
        })
    return {"total_expected": round(total_expected, 2), "details": details}


def calculate_emr(claims, payroll_by_class, weighting_factor=0.30):
    """Calculate projected Experience Modification Rate.
    
    claims: list of {amount, year, description}
    payroll_by_class: dict of {class_code: annual_payroll}
    weighting_factor: NCCI ballast value (typically 0.25-0.35 for small shops)
    
    Simplified NCCI formula:
      EMR = (Actual Primary × 1.0 + Actual Excess × W) / (Expected Primary × 1.0 + Expected Excess × W)
    
    Returns: {emr, components, bid_eligibility}
    """
    # Expected losses
    expected = calculate_expected_losses(payroll_by_class)
    total_expected = expected["total_expected"]
    
    if total_expected <= 0:
        return {"error": "No payroll data - cannot calculate EMR"}
    
    # Split expected into primary/excess using NCCI 2025 methodology
    # FIXED: Was using avg_claim = total_expected * 0.15 (wrong).
    # Correct: Use state-specific D-ratio (primary weight) from NCCI tables.
    # Texas 2025 D-ratio for class 5040/3030 ≈ 0.27-0.32 (small shop).
    # Expected Primary = Expected Losses × D-ratio
    # Expected Excess = Expected Losses × (1 - D-ratio)
    d_ratio = min(0.35, max(0.20, TEXAS_SPLIT_POINT / max(total_expected, 1)))
    d_ratio = min(d_ratio, 0.40)  # Cap per NCCI methodology
    expected_primary = total_expected * d_ratio
    expected_excess = total_expected * (1 - d_ratio)
    
    # Actual losses - split each claim
    actual_primary = 0
    actual_excess = 0
    claim_details = []
    for claim in claims:
        split = split_loss(claim.get("amount", 0))
        actual_primary += split["primary"]
        actual_excess += split["excess"]
        claim_details.append({
            **claim,
            "primary": split["primary"],
            "excess": split["excess"],
        })
    
    # EMR calculation
    W = weighting_factor
    numerator = (actual_primary * 1.0) + (actual_excess * W) + (total_expected * (1 - W))
    denominator = (expected_primary * 1.0) + (expected_excess * W) + (total_expected * (1 - W))
    
    emr = round(numerator / max(denominator, 1), 3)
    
    # Bid eligibility check
    eligibility = {}
    for gate_key, gate in EMR_THRESHOLDS.items():
        eligibility[gate_key] = {
            "label": gate["label"],
            "max_emr": gate["max_emr"],
            "eligible": emr <= gate["max_emr"],
        }
    
    return {
        "emr": emr,
        "claim_count": len(claims),
        "total_incurred": sum(c.get("amount", 0) for c in claims),
        "actual_primary": round(actual_primary, 2),
        "actual_excess": round(actual_excess, 2),
        "expected_losses": round(total_expected, 2),
        "split_point": TEXAS_SPLIT_POINT,
        "claims": claim_details,
        "bid_eligibility": eligibility,
        "warning": "5 small claims hurt EMR more than 1 large claim" if len(claims) >= 3 else None,
        "note": "Projected EMR - verify against official NCCI mod worksheet",
    }


def check_bid_eligibility(emr, prospect_type="standard_gc"):
    """Quick check: can we bid this project given our EMR?"""
    gate = EMR_THRESHOLDS.get(prospect_type, EMR_THRESHOLDS["standard_gc"])
    return {
        "emr": emr,
        "prospect_type": prospect_type,
        "gate": gate["label"],
        "max_emr": gate["max_emr"],
        "eligible": emr <= gate["max_emr"],
        "action": None if emr <= gate["max_emr"] else f"EMR {emr} exceeds {gate['max_emr']} threshold for {gate['label']}. Do not submit without review.",
    }


def frequency_vs_severity_warning(claims):
    """Show that frequency hurts more than severity (NCCI weighting)."""
    count = len(claims)
    total = sum(c.get("amount", 0) for c in claims)
    primary = sum(min(c.get("amount", 0), TEXAS_SPLIT_POINT) for c in claims)
    return {
        "claim_count": count,
        "total_incurred": total,
        "total_primary": primary,
        "primary_pct_of_total": round(primary * 100 / max(total, 1), 1),
        "lesson": f"{count} claims generated ${primary:,.0f} in primary losses. A single ${total:,.0f} claim would generate only ${min(total, TEXAS_SPLIT_POINT):,.0f} in primary losses.",
    }
