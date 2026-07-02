# TEMPLATE FILE - all rates zeroed. Set your own values before use.
"""
Your Company Virtual Office - Locked Bid Rates (Q2 2026)
======================================================
Source: the Owner's directives Section 6 (locked April 28, 2026).
Override requires explicit Owner (CEO) approval.

These are CLIENT-FACING bid rates, not internal cost basis.
Internal costs are in calibration_2026q2.py. Never expose internal
costs on client documents.
"""

# ── Bid Rates (client-facing, per-unit) ───────────────────────────────
BID_RATES = {
    "fab_per_ton": 0,  # TODO set your value (was CEO-locked)
    "erection_per_ton": 0,  # TODO set your value (was CEO-locked)
    "joists_per_ton": 0,  # TODO set your value (was CEO-locked)
    "roof_deck_per_sf": 0.0,  # TODO set your value (was CEO-locked)
    "composite_deck_per_sf": 0.0,  # TODO set your value (was CEO-locked)
    "anchor_rod_1x20_each": 0,  # TODO set your value (was CEO-locked)
    "ga_overhead_pct": 0.0,  # TODO set your value (was CEO-locked)
    "net_target_gp_pct": 0.0,  # TODO set your value (was CEO-locked)
}

# ── GP Margins by Line Item ───────────────────────────────────────────
BID_MARGINS = {
    "fab":             0.0,
    "erection":        0.0,
    "joists":          0.0,
    "roof_deck":       0.0,
    "composite_deck":  0.0,
    "anchor_rods":     0.31,
}

# ── Material Cost Basis (internal only, NEVER on client docs) ─────────
# BUG-001 FIX: merged with the volatility-guard dict that previously
# re-defined MATERIAL_COSTS at line 156, silently overwriting this one.
# Volatility keys renamed: w_shapes_per_ton_low / _high to avoid
# collision with the internal cost basis w_shapes_per_ton (1250).
MATERIAL_COSTS = {
    # Internal cost basis
    "w_shapes_per_ton":         1250,    # A992/A36 midpoint
    "hss_per_ton":              1600,    # A500 Gr.B/C
    "joist_raw_per_ton":        1250,    # midpoint 1200-1325
    "joist_total_per_ton":      2700,    # matl + labor + freight
    "roof_deck_1_5B22_per_sf":  2.85,    # landed Houston
    "composite_deck_per_sf":    2.85,    # landed Houston
    "anchor_rod_1x20_each":       57,    # midpoint 52-62
    "anchor_rod_3_4x9_each":      22,    # midpoint 18-25
    "hdg_premium_per_ton":       525,    # midpoint 450-600
    # Q2 2026 volatility range (used by check_material_volatility)
    "w_shapes_per_ton_low":     1150,    # low end of Q2 2026 service center range
    "w_shapes_per_ton_high":    1400,    # high end
    "plate_per_ton":            1250,    # A36 plate landed Houston
}

# ── Drawing-Stage Adders (apply to QUANTITY, never as line item) ──────
DRAWING_STAGE_ADDERS = {
    "IFC":      0.00,    # ±5% qty tolerance only
    "DD":       0.05,    # +3 to +5%, use +5% if bay/elevation missing
    "BUDGET":   0.08,    # +5 to +8%, use +8% for single-page or no EOR
    "SD":       0.08,    # same as budget
    "CONCEPT":  0.08,    # same as budget
}

# ── Payment Structure (locked, supersedes 40/20/40) ──────────────────
PAYMENT_STRUCTURE = {
    "mobilization_pct":   0.30,   # upon shop drawing approval
    "first_delivery_pct": 0.20,   # first fabricated delivery on site
    "sov_pct":            0.50,   # per Schedule of Values
}

PAYMENT_CLIENT_WORDING = (
    "Payment structure:\n"
    "30% mobilization upon approval of shop drawings\n"
    "20% upon first fabricated delivery on site\n"
    "50% per Schedule of Values through completion"
)

# ── Small-Project Override ────────────────────────────────────────────
SMALL_PROJECT_PROFIT_TARGET = 0.50   # 50% GP when Owner flags "small"
SMALL_PROJECT_THRESHOLD = 200_000    # typical <$200K base bid

# ── Schedule Benchmarks (publish on bids) ─────────────────────────────
SCHEDULE_BENCHMARKS = {
    "shop_drawings":  "2-3 wks (overseas AISC teams)",
    "joist_fab":      "2-3 wks",
    "delivery":       "3-4 wks with main steel",
    "deck":           "3-4 wks from PO",
    "misc":           "1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame",
    "anchor_rods":    "10-14 days from AB plan",
    "erection":       "~6-7 wks per 116K SF; misc concurrent + 3-5 day punch",
}

# ── Takeoff Benchmarks (sanity-check only, never replacement) ─────────
TAKEOFF_BENCHMARKS = {
    "conventional_steel_psf":  (6, 8),
    "tilt_up_psf":             (5, 6),
    "joists_girders_psf":      (1.5, 2),
    "deck_sf_per_sf":          1.0,
    "anchor_rods_per_pier":    4,
    "tolerance_absorbed_pct":  0.05,
}


def apply_drawing_stage_adder(base_qty: float, stage: str) -> dict:
    """Apply drawing-stage contingency to a quantity.

    Adder rides on quantity, not price. Never disclose to client.
    """
    stage_upper = stage.upper()
    adder = DRAWING_STAGE_ADDERS.get(stage_upper, 0.0)
    adjusted = base_qty * (1 + adder)
    return {
        "base_qty": base_qty,
        "stage": stage_upper,
        "adder_pct": adder,
        "adjusted_qty": round(adjusted, 2),
        "note": f"Contingency +{adder*100:.0f}% applied to quantity "
                f"(drawing stage: {stage_upper})" if adder > 0
                else "IFC drawings. No contingency applied.",
    }


def price_bid_line(item: str, quantity: float,
                   override_rate: float = None) -> dict:
    """Price a single bid line item using locked rates.

    Returns client-facing rate, total, and internal GP data.
    """
    rate_map = {
        "fab":            ("fab_per_ton", "fab"),
        "erection":       ("erection_per_ton", "erection"),
        "joists":         ("joists_per_ton", "joists"),
        "roof_deck":      ("roof_deck_per_sf", "roof_deck"),
        "composite_deck": ("composite_deck_per_sf", "composite_deck"),
        "anchor_rods":    ("anchor_rod_1x20_each", "anchor_rods"),
    }

    if item not in rate_map:
        return {"error": f"Unknown bid item: {item}. "
                         f"Valid: {', '.join(rate_map.keys())}"}

    rate_key, margin_key = rate_map[item]
    rate = override_rate or BID_RATES[rate_key]
    margin = BID_MARGINS[margin_key]
    total = round(rate * quantity, 2)
    gp = round(total * margin, 2)

    return {
        "item": item,
        "quantity": quantity,
        "rate": rate,
        "total": total,
        "gp_pct": margin,
        "gp_amount": gp,
        "net_cost": round(total - gp, 2),
    }


# ---- Material Volatility Guard (Gemini suggestion #3) ----
# If a bid takes longer than 10 days to close, auto-flag for price refresh.
# Q2 2026: W-shapes trading $1,100-$1,400/ton at service centers.
# NOTE: volatility range keys (w_shapes_per_ton_low/_high, plate_per_ton)
# are now part of the single MATERIAL_COSTS dict above (BUG-001 fix).

MATERIAL_PRICE_VALID_DAYS = 10  # days before material prices need refresh


def check_material_volatility(bid_date: str, total_tons: float) -> dict:
    """Check if bid pricing is still valid based on material volatility.

    If bid is older than 10 days, flag for price refresh.
    Shows potential exposure at high-end material pricing.

    Accepts ISO date (YYYY-MM-DD) OR ISO datetime (YYYY-MM-DDTHH:MM:SS[.ffffff]).
    """
    from datetime import datetime
    from bridge._date_utils import parse_bid_date

    # Try ISO date, then ISO datetime. Surface parse failures explicitly
    # rather than silently masking. v3.5.6 routes through the shared
    # helper; v3.5.5 had the same logic inline here.
    bid_dt, parse_failed = parse_bid_date(bid_date)

    age_days = (datetime.now() - bid_dt).days  # vj: duration-math
    stale = age_days > MATERIAL_PRICE_VALID_DAYS

    # Calculate exposure: difference between low and high material cost
    # BUG-001 fix: key renamed from "w_shapes_per_ton" to "w_shapes_per_ton_low"
    # to avoid collision with internal cost basis in the merged MATERIAL_COSTS dict.
    exposure = total_tons * (MATERIAL_COSTS["w_shapes_per_ton_high"] -
                            MATERIAL_COSTS["w_shapes_per_ton_low"])

    result = {
        "bid_age_days": age_days,
        "valid_days": MATERIAL_PRICE_VALID_DAYS,
        "stale": stale,
        "material_exposure": round(exposure, 0),
        "action": (
            f"PRICE REFRESH NEEDED. Bid is {age_days} days old. "
            f"Material exposure: ${exposure:,.0f} on {total_tons:.0f}T."
            if stale else
            f"Pricing valid. {MATERIAL_PRICE_VALID_DAYS - age_days} days remaining."
        ),
    }
    if parse_failed:
        result["bid_date_parse_failed"] = True
        result["action"] = (
            f"WARNING: bid_date '{bid_date}' could not be parsed as ISO date "
            f"or datetime. Defaulted to today; volatility check is unreliable."
        )
    return result


# ---- Red-Light Rule (Gemini suggestion #4) ----
# If tonnage variance > 10%, BLOCK the export button.
# LIFT lets estimators send wrong bids. Your Company prevents it.

TONNAGE_VARIANCE_THRESHOLD = 0.10  # 10%


def red_light_check(extracted_tonnage: float, calculated_tonnage: float) -> dict:
    """Red-Light Rule: block proposal export if tonnage variance > 10%.
    
    LIFT will let an estimator send a wrong bid.
    Your Company PREVENTS it.
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.25; disjoint shapes)
    if extracted_tonnage <= 0 or calculated_tonnage <= 0:
        return {
            "blocked": True,
            "reason": "Missing tonnage data. Cannot verify.",
            "variance_pct": None,
        }
    
    variance = abs(extracted_tonnage - calculated_tonnage) / max(extracted_tonnage, calculated_tonnage)
    blocked = variance > TONNAGE_VARIANCE_THRESHOLD
    
    return {
        "blocked": blocked,
        "extracted_tonnage": extracted_tonnage,
        "calculated_tonnage": calculated_tonnage,
        "variance_pct": round(variance * 100, 1),
        "threshold_pct": round(TONNAGE_VARIANCE_THRESHOLD * 100, 1),
        "status": "RED_LIGHT" if blocked else "GREEN",
        "action": (
            f"BLOCKED. Tonnage variance {variance*100:.1f}% exceeds {TONNAGE_VARIANCE_THRESHOLD*100:.0f}% threshold. "
            f"AI extracted {extracted_tonnage:.1f}T but members calculate to {calculated_tonnage:.1f}T. "
            f"Resolve before exporting proposal."
            if blocked else
            f"CLEAR. Variance {variance*100:.1f}% within {TONNAGE_VARIANCE_THRESHOLD*100:.0f}% threshold."
        ),
    }
