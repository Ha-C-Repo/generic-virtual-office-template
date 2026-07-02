"""
Your Company Virtual Office - Autonomous Bid Response

Bid arrives by email → auto-extract scope/due date/GC →
compliance pre-flight → generate proposal → draft cover email →
Owner reviews ONE finished package → one click = submitted.

Also: proactive opportunity hunting from SAM.gov, BIC Magazine,
AGC Houston. Matches against Your Company's sweet spot.
"""

import json, re
from datetime import date, datetime, timedelta

# Your Company's sweet spot (from company knowledge)
SWEET_SPOT = {
    "min_tons": 50,
    "max_tons": 5000,
    "max_distance_miles": 200,
    "preferred_types": ["church", "worship", "commercial", "warehouse", "school",
                        "hospital", "retail", "office", "industrial"],
    "excluded_types": ["pemb", "pre-engineered", "metal building", "butler", "nucor"],
    "home_base": {"lat": 29.8607, "lon": -95.4619},  # Houston TX
    "max_emr_general": 1.0,
    "max_emr_refinery": 0.85,
}


def analyze_bid_invitation(text: str) -> dict:
    """Extract structured data from a bid invitation email/document."""
    result = {
        "project_name": "",
        "gc_company": "",
        "location": "",
        "bid_due_date": "",
        "scope_keywords": [],
        "estimated_tonnage": "",
        "special_requirements": [],
        "davis_bacon": False,
        "is_pemb": False,
        "in_sweet_spot": True,
        "disqualifiers": [],
    }

    text_lower = text.lower()

    # PEMB check (hard disqualifier)
    pemb_kw = ["pre-engineered", "pemb", "metal building", "butler building",
               "nucor building", "varco-pruden", "chief industries"]
    for kw in pemb_kw:
        if kw in text_lower:
            result["is_pemb"] = True
            result["in_sweet_spot"] = False
            result["disqualifiers"].append(f"PEMB detected: '{kw}'")

    # Davis-Bacon detection
    db_kw = ["davis-bacon", "prevailing wage", "wage determination", "dol.gov"]
    result["davis_bacon"] = any(kw in text_lower for kw in db_kw)

    # Scope keywords
    structural_kw = ["structural steel", "steel erection", "fabricat", "joist",
                     "deck", "misc metals", "handrail", "stair", "embed",
                     "column", "beam", "brace", "connection"]
    result["scope_keywords"] = [kw for kw in structural_kw if kw in text_lower]

    # Special requirements
    if "aisc" in text_lower: result["special_requirements"].append("AISC certification required")
    if "aws d1.1" in text_lower: result["special_requirements"].append("AWS D1.1 welding")
    if "isn" in text_lower or "isnetworld" in text_lower:
        result["special_requirements"].append("ISNetworld required")
    if "disa" in text_lower: result["special_requirements"].append("DISA consortium required")
    if any(kw in text_lower for kw in ["emr", "experience mod"]):
        result["special_requirements"].append("EMR requirement")

    # Tonnage extraction - prefer tons over SF
    ton_match = re.search(r"(\d[\d,]*)\s*tons?\b", text_lower)
    if ton_match:
        result["estimated_tonnage"] = ton_match.group(1).replace(",", "")
    else:
        # Fallback: square footage (not tonnage - flag it)
        sf_match = re.search(r"(\d[\d,]*)\s*(?:sf|square feet)", text_lower)
        if sf_match:
            result["square_footage"] = sf_match.group(1).replace(",", "")

    return result


def auto_response_pipeline(bid_text: str, keys: dict = None) -> dict:
    """Full autonomous bid response pipeline.

    1. Analyze invitation
    2. Check sweet spot
    3. Run compliance pre-flight
    4. Estimate pricing
    5. Generate proposal
    6. Draft cover email
    7. Return complete package for the Owner's review
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.46; needs manual audit)
    steps = []

    # Step 1: Analyze
    analysis = analyze_bid_invitation(bid_text)
    steps.append({"step": "analyze", "status": "complete", "result": analysis})

    if not analysis["in_sweet_spot"]:
        return {
            "recommendation": "PASS",
            "reason": analysis["disqualifiers"],
            "steps": steps,
            "package_ready": False,
        }

    # Step 2: Compliance pre-flight
    try:
        from bridge.action_chains import run_compliance_preflight
        preflight = run_compliance_preflight(analysis.get("project_name", ""))
        steps.append({"step": "compliance", "status": "complete", "result": preflight})
        if not preflight["all_clear"]:
            failed_gates = [g["gate"] for g in preflight["gates"] if g["status"] == "FAIL"]
            return {
                "recommendation": "HOLD",
                "reason": f"Compliance gates failed: {failed_gates}",
                "steps": steps,
                "package_ready": False,
                "fix_required": failed_gates,
            }
    except Exception as e:
        steps.append({"step": "compliance", "status": "skipped", "error": str(e)})

    # Step 3: Estimate
    try:
        from bridge.learning_estimator import estimate_project
        tonnage = float(analysis.get("estimated_tonnage", 0) or 0)
        if tonnage > 0:
            estimate = estimate_project(tonnage)
            steps.append({"step": "estimate", "status": "complete", "result": estimate})
        else:
            estimate = None
            steps.append({"step": "estimate", "status": "skipped", "reason": "No tonnage found"})
    except Exception as e:
        estimate = None
        steps.append({"step": "estimate", "status": "error", "error": str(e)})

    # Step 4: Generate proposal
    proposal_result = None
    try:
        from bridge.documents import generate_proposal
        if estimate:
            proposal_result = generate_proposal(
                project_name=analysis.get("project_name", "Bid Response"),
                gc_name="",
                gc_company=analysis.get("gc_company", ""),
                scope_text="\n".join(f"• {kw}" for kw in analysis["scope_keywords"]),
                tonnage=str(analysis.get("estimated_tonnage", "TBD")),
                total_estimate=f"${estimate['total_estimate']:,.2f}" if estimate else "TBD",
            )
            steps.append({"step": "proposal", "status": "complete",
                          "result": {"filename": proposal_result.get("filename", "")}})
    except Exception as e:
        steps.append({"step": "proposal", "status": "error", "error": str(e)})

    # Step 5: Draft cover email
    email_draft = {
        "subject": f"Bid Submission - {analysis.get('project_name', 'Project')} - Your Company",
        "body": (
            f"Please find attached our proposal for the referenced project.\n\n"
            f"Your Company LLC is an AISC-certified structural steel fabricator "
            f"and erector based in Houston, TX (ISN: [ISN ID]).\n\n"
            f"We look forward to the opportunity to participate.\n\n"
            f"The Owner\nCEO, Your Company LLC\n[COMPANY PHONE]"
        ),
    }
    steps.append({"step": "email_draft", "status": "complete", "result": email_draft})

    return {
        "recommendation": "SUBMIT",
        "analysis": analysis,
        "estimate": estimate,
        "proposal": proposal_result,
        "email_draft": email_draft,
        "steps": steps,
        "package_ready": True,
        "awaiting_owner_approval": True,
        "message": "Bid package ready for your review. One click to submit.",
    }


def match_opportunity(opportunity: dict) -> dict:
    """Score an opportunity against Your Company's sweet spot."""
    score = 0
    reasons = []

    desc = (opportunity.get("description", "") + " " + opportunity.get("title", "")).lower()

    # Check for structural steel keywords
    steel_kw = ["structural steel", "steel fabricat", "steel erect", "miscellaneous metals"]
    if any(kw in desc for kw in steel_kw):
        score += 40
        reasons.append("Structural steel scope detected")

    # Check for PEMB exclusion
    for kw in SWEET_SPOT["excluded_types"]:
        if kw in desc:
            return {"score": 0, "match": False, "reason": f"PEMB/excluded: {kw}"}

    # Check for preferred types
    for pt in SWEET_SPOT["preferred_types"]:
        if pt in desc:
            score += 15
            reasons.append(f"Preferred type: {pt}")
            break

    # Location check (Texas/Gulf Coast)
    loc = opportunity.get("location", "").lower()
    if any(s in loc for s in ["texas", "tx", "houston", "harris", "galveston"]):
        score += 20
        reasons.append("Houston/Texas location")
    elif any(s in loc for s in ["louisiana", "la", "gulf"]):
        score += 10
        reasons.append("Gulf Coast location")

    return {
        "score": min(score, 100),
        "match": score >= 40,
        "reasons": reasons,
        "sweet_spot": score >= 60,
    }
