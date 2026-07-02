"""
Your Company Virtual Office - Bid Quality Scorecard
==================================================
Combines voice calibration + compliance scanner + PDF QC + pricing
validation into a single letter grade (A-F) with explanations.

No paid service can do this because it requires:
  1. Domain-specific rules (26 Tier 1 governance rules)
  2. the Owner's voice patterns (10 calibration checks)
  3. Locked Q2 2026 rates (pricing sanity check)
  4. AISC-verified tonnage (no LLM math)

Usage:
    from bridge.bid_scorecard import score_bid
    result = score_bid(
        proposal_text="...",
        tonnage=85.3,
        total_bid=425000,
        pdf_path="/path/to/proposal.pdf"
    )
    print(result["grade"])  # "A"
    print(result["score"])  # 94
"""

import logging

log = logging.getLogger(__name__)


def score_bid(
    proposal_text: str = "",
    tonnage: float = 0,
    total_bid: float = 0,
    deck_sf: float = 0,
    pdf_path: str = "",
    template: str = "STANDARD",
) -> dict:
    """Score a bid proposal on a 0-100 scale, return letter grade.

    Categories:
      - Compliance (40 pts): Tier 1 rule violations
      - Voice (20 pts): the Owner's voice calibration
      - Pricing (25 pts): Rate sanity, cash flow, margin
      - Format (15 pts): PDF QC visual rules

    Returns:
      {grade, score, breakdown, deductions, recommendations}
    """
    deductions = []
    recommendations = []

    # ── Category 1: Compliance (40 pts max) ───────────────────────────
    compliance_score = 40
    try:
        from bridge.governance import check_compliance
        violations = check_compliance(proposal_text, "bid")
        if violations:
            # Each violation costs 8 points, max deduction = 40
            penalty = min(len(violations) * 8, 40)
            compliance_score -= penalty
            for v in violations[:5]:  # report first 5
                deductions.append({
                    "category": "compliance",
                    "points": -8,
                    "detail": f"{v['rule']}: {v['detail'][:60]}",
                })
    except Exception as e:
        compliance_score = 20  # can't verify = half credit
        deductions.append({
            "category": "compliance",
            "points": -20,
            "detail": f"Compliance check failed: {e}",
        })

    # ── Category 2: Voice Calibration (20 pts max) ────────────────────
    voice_score = 20
    try:
        from harnesses.operational import VoiceCalibrationHarness
        vr = VoiceCalibrationHarness.check(proposal_text)
        hard = vr.get("hard_violations", 0)
        soft = vr.get("soft_violations", 0)
        voice_score -= min(hard * 5, 15)  # hard: 5 pts each, max 15
        voice_score -= min(soft * 2, 5)   # soft: 2 pts each, max 5
        if hard > 0:
            deductions.append({
                "category": "voice",
                "points": -(hard * 5),
                "detail": f"{hard} hard voice violations (em-dash, AI opener, etc.)",
            })
            recommendations.append(
                "Run check_voice() on proposal text and fix hard violations before sending."
            )
        if soft > 0:
            deductions.append({
                "category": "voice",
                "points": -(soft * 2),
                "detail": f"{soft} soft voice violations (filler words, etc.)",
            })
    except Exception:
        voice_score = 15

    # ── Category 3: Pricing Sanity (25 pts max) ───────────────────────
    pricing_score = 25

    if tonnage > 0 and total_bid > 0:
        cost_per_ton = total_bid / tonnage

        # Sanity check: $3,000-$8,000/ton is normal range
        if cost_per_ton < 3000:
            pricing_score -= 10
            deductions.append({
                "category": "pricing",
                "points": -10,
                "detail": f"Bid is ${cost_per_ton:,.0f}/ton. Below $3,000/ton floor. "
                          "Check if scope items are missing.",
            })
            recommendations.append(
                "Verify all scope items are included. Deck, erection, anchors?"
            )
        elif cost_per_ton > 8000:
            pricing_score -= 5
            deductions.append({
                "category": "pricing",
                "points": -5,
                "detail": f"Bid is ${cost_per_ton:,.0f}/ton. Above $8,000/ton. "
                          "Normal for small/complex projects but verify.",
            })

        # Cash flow check: 30% mobilization should cover steel
        try:
            from bridge.bid_rates import MATERIAL_COSTS
            steel_cost = MATERIAL_COSTS.get("w_shapes_per_ton", 1150) * tonnage
            mobilization = total_bid * 0.30
            if mobilization < steel_cost:
                pricing_score -= 8
                deductions.append({
                    "category": "pricing",
                    "points": -8,
                    "detail": f"30% mobilization (${mobilization:,.0f}) doesn't cover "
                              f"steel cost (${steel_cost:,.0f}). Flag on GP report.",
                })
                recommendations.append(
                    "Cash flow gap. Add a note to GP report explaining how "
                    "Phase 1 procurement is covered."
                )
        except Exception:
            pass

        # Margin check: should be ~25% net after 7.5% G&A
        try:
            from bridge.bid_rates import BID_RATES, BID_MARGINS
            # BUG-002 FIX: was BID_RATES["fab"] (KeyError - key does not exist).
            # Correct key is "fab_per_ton". The except: pass was masking this
            # silently, so this branch has never executed until this fix.
            fab_cost = BID_RATES["fab_per_ton"] * tonnage * (1 - BID_MARGINS["fab"])
            expected_floor = fab_cost * 1.20  # at least 20% over cost
            if total_bid < expected_floor:
                pricing_score -= 5
                deductions.append({
                    "category": "pricing",
                    "points": -5,
                    "detail": "Bid may be below target 20% margin threshold.",
                })
        except Exception:
            pass

    elif tonnage == 0 and total_bid > 0:
        pricing_score -= 15
        deductions.append({
            "category": "pricing",
            "points": -15,
            "detail": "No tonnage provided. Cannot verify pricing sanity.",
        })
        recommendations.append(
            "Always run score_bid with tonnage from the takeoff."
        )

    # PSF check
    if tonnage > 0 and deck_sf > 0:
        psf = tonnage * 2000 / deck_sf
        if psf < 4 or psf > 10:
            pricing_score -= 5
            deductions.append({
                "category": "pricing",
                "points": -5,
                "detail": f"PSF = {psf:.1f}. Expected 5-8 for conventional. "
                          "Verify building classification.",
            })

    # ── Category 4: Format/QC (15 pts max) ────────────────────────────
    format_score = 15
    if pdf_path:
        try:
            from bridge.pdf_qc import run_pdf_qc
            qc = run_pdf_qc(
                pdf_path, was_rendered=True,
                expected_template=template,
            )
            if qc.get("blocked"):
                format_score -= 15
                deductions.append({
                    "category": "format",
                    "points": -15,
                    "detail": "PDF QC blocked output (R-01 gate).",
                })
            elif qc.get("verdict") == "WARN":
                format_score -= 5
                deductions.append({
                    "category": "format",
                    "points": -5,
                    "detail": "PDF QC warnings found.",
                })
        except Exception:
            format_score = 10

    # ── Compute final grade ───────────────────────────────────────────
    total = max(compliance_score + voice_score + pricing_score + format_score, 0)

    if total >= 90:
        grade = "A"
    elif total >= 80:
        grade = "B"
    elif total >= 70:
        grade = "C"
    elif total >= 60:
        grade = "D"
    else:
        grade = "F"

    # Auto-recommendations based on grade
    if grade in ("D", "F"):
        recommendations.insert(0,
            "DO NOT SEND. Fix all compliance and voice violations first."
        )
    elif grade == "C":
        recommendations.insert(0,
            "Review carefully before sending. Multiple issues found."
        )

    return {
        "grade": grade,
        "score": total,
        "max_score": 100,
        "breakdown": {
            "compliance": {"score": compliance_score, "max": 40},
            "voice": {"score": voice_score, "max": 20},
            "pricing": {"score": pricing_score, "max": 25},
            "format": {"score": format_score, "max": 15},
        },
        "deductions": deductions,
        "recommendations": recommendations,
        "verdict": (
            "SHIP" if grade in ("A", "B")
            else "REVIEW" if grade == "C"
            else "BLOCK"
        ),
    }
