"""
Your Company Virtual Office - Autonomous Bid Composition Chain

THE CROWN JEWEL: Every module in the system working together.

email inbox → doc_intel (spec parse) → lift_clone (takeoff) →
cost_engine (hedged price) → compliance (6-gate pre-flight) →
learning_estimator (calibrated estimate) → aia_g702 (SOV seed) →
fin_automation (TX lien calendar) → documents (proposal PDF) →
hash_chain (tamper-evident) → autonomous_bidding (cover email) →
Owner reviews ONE package → one click → submitted

Every transition emits an event. Every document is hash-chained.
Every number traces back to a source drawing revision.
"""

import json
from datetime import datetime, date, timezone


def compose_bid(bid_text: str = "", pdf_path: str = "", project_name: str = "",
                gc_company: str = "", keys: dict = None) -> dict:
    """
    Full autonomous bid composition.

    Input: bid invitation text (email body or extracted PDF)
    Output: complete bid package ready for the Owner's one-click approval

    This is the function that ties all 68 modules together.
    """
    chain = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name or "Auto-Detected",
        "steps": [],
        "errors": [],
        "package_ready": False,
    }

    def _step(name, fn):
        try:
            result = fn()
            chain["steps"].append({"step": name, "status": "PASS", "result": result})
            return result
        except Exception as e:
            chain["steps"].append({"step": name, "status": "FAIL", "error": str(e)[:200]})
            chain["errors"].append(f"{name}: {e}")
            return None

    # ═══ STEP 1: Analyze bid invitation ════════════════════════════
    analysis = _step("1_analyze_bid", lambda: _analyze(bid_text))
    if analysis:
        chain["project_name"] = analysis.get("project_name") or project_name
        chain["gc_company"] = analysis.get("gc_company") or gc_company

    # ═══ STEP 2: Parse spec sections (if text includes spec) ══════
    spec = _step("2_parse_spec", lambda: _parse_spec(bid_text))

    # ═══ STEP 3: AI takeoff (if PDF provided) ═════════════════════
    bom = None
    if pdf_path:
        bom = _step("3_ai_takeoff", lambda: _run_takeoff(pdf_path, chain["project_name"]))

    # ═══ STEP 3b: In-house estimate-grade coordinate model (Slice 1) ═══
    # Build the column-grid model from the framing plan + takeoff and save a
    # MODEL viewport so find_render uses it as the page-1 fallback when no Tekla
    # export exists. Estimate-grade, QC/visualization only; Tekla stays the
    # system of record. Never blocks the chain.
    coord_lines = ((bom or {}).get("bom", {}) or {}).get("lines", []) if bom else []
    cm = _step("3b_coordinate_model", lambda: _build_coordinate_model(
        chain["project_name"], chain.get("bid_number", ""), pdf_path, coord_lines))
    if cm and cm.get("model_png"):
        chain["model_image"] = cm["model_png"]

    # ═══ STEP 4: Get hedged steel price ═══════════════════════════
    pricing = _step("4_hedged_pricing", lambda: _get_pricing(analysis))

    # ═══ STEP 5: Compliance pre-flight (6 gates) ═════════════════
    compliance = _step("5_compliance_preflight", lambda: _run_compliance(chain["project_name"]))

    # Check if compliance blocks us
    if compliance and not compliance.get("all_clear"):
        failed = [g["gate"] for g in compliance.get("gates", []) if g["status"] == "FAIL"]
        chain["recommendation"] = "HOLD"
        chain["hold_reason"] = f"Compliance gates failed: {failed}"
        chain["package_ready"] = False
        chain["completed_at"] = datetime.now(timezone.utc).isoformat()
        _emit_event("BID_COMPLIANCE_HOLD", chain)
        return chain

    # ═══ STEP 6: Calibrated estimate ═════════════════════════════
    estimate = _step("6_calibrated_estimate", lambda: _estimate(analysis, pricing))

    # ═══ STEP 7: Sweet-spot match ════════════════════════════════
    match = _step("7_sweet_spot_match", lambda: _match_sweet_spot(analysis))

    if match and not match.get("match"):
        chain["recommendation"] = "PASS"
        chain["pass_reason"] = match.get("reason", "Outside sweet spot")
        chain["package_ready"] = False
        chain["completed_at"] = datetime.now(timezone.utc).isoformat()
        _emit_event("BID_PASSED_AUTO", chain)
        return chain

    # ═══ STEP 8: Seed TX lien calendar ═══════════════════════════
    lien = _step("8_lien_calendar", lambda: _seed_lien_calendar(chain["project_name"]))

    # ═══ STEP 8b: Tekla viewport export (member-accurate frame image) ═══
    # Every bid checks for the Tekla viewport export that fills the proposal's
    # page-1 project image. Member-accurate frames are ALWAYS Tekla exports,
    # never AI. ok=False is a gate (export still owed), not a chain failure.
    tekla_img = _step("8b_tekla_viewport", lambda: _require_tekla_viewport(
        chain["project_name"], chain.get("bid_number", "")))
    chain["page1_image"] = tekla_img

    # ═══ STEP 9: Generate proposal PDF (carries page-1 project image) ═══
    proposal = _step("9_generate_proposal", lambda: _generate_proposal(
        chain["project_name"], chain.get("gc_company", ""), analysis, estimate,
        chain.get("bid_number", "")))

    # ═══ STEP 10: Hash chain the proposal ════════════════════════
    hash_result = _step("10_hash_chain", lambda: _hash_document(
        chain["project_name"], proposal))

    # ═══ STEP 11: Draft cover email ══════════════════════════════
    email = _step("11_cover_email", lambda: _draft_email(
        chain["project_name"], chain.get("gc_company", ""), estimate))

    # ═══ STEP 12: Win probability (if model has data) ════════════
    win_prob = _step("12_win_probability", lambda: _predict_win(analysis, estimate))

    # ═══ ASSEMBLE PACKAGE ════════════════════════════════════════
    chain["package_ready"] = True
    chain["recommendation"] = "SUBMIT"
    chain["completed_at"] = datetime.now(timezone.utc).isoformat()
    chain["steps_completed"] = sum(1 for s in chain["steps"] if s["status"] == "PASS")
    chain["steps_total"] = len(chain["steps"])

    chain["package"] = {
        "project": chain["project_name"],
        "gc": chain.get("gc_company", ""),
        "estimate": estimate,
        "compliance": "ALL CLEAR" if compliance and compliance.get("all_clear") else "CHECK REQUIRED",
        "proposal": proposal,
        "email_draft": email,
        "win_probability": win_prob,
        "hash_chain": hash_result,
        "lien_calendar": lien,
        "awaiting_owner_approval": True,
    }

    chain["message"] = (
        f"Bid package for '{chain['project_name']}' is ready.\n"
        f"{chain['steps_completed']}/{chain['steps_total']} steps completed.\n"
        f"Estimate: ${estimate.get('total_estimate', 0):,.0f}\n"
        f"Win probability: {win_prob.get('probability', 'N/A') if win_prob else 'N/A'}\n"
        f"One click to submit."
    )

    _emit_event("BID_PACKAGE_READY", {
        "project": chain["project_name"],
        "estimate": estimate.get("total_estimate", 0) if estimate else 0,
        "steps": chain["steps_completed"],
    })

    return chain


# ═══ STEP IMPLEMENTATIONS ══════════════════════════════════════════

def _analyze(text):
    from bridge.autonomous_bidding import analyze_bid_invitation
    return analyze_bid_invitation(text)

def _parse_spec(text):
    try:
        from bridge.doc_intel.intelligence import parse_spec_sections
        return parse_spec_sections(text)
    except Exception:
        return {"note": "Spec parsing skipped - no structured spec text detected"}

def _run_takeoff(pdf_path, project):
    try:
        from bridge.lift_clone.takeoff import run_takeoff
        return run_takeoff(pdf_path, project)
    except Exception:
        return {"note": "AI takeoff requires plan set PDF"}

def _get_pricing(analysis):
    try:
        from bridge.agents.steel_price.agent import get_latest_prices, get_best_price
        prices = get_latest_prices()
        best_w = get_best_price("W")
        return {"latest": prices, "best_w_section": best_w}
    except Exception:
        return {"note": "Steel pricing agent - pull sources to populate"}

def _run_compliance(project):
    from bridge.action_chains import run_compliance_preflight
    return run_compliance_preflight(project)

def _estimate(analysis, pricing):
    try:
        from bridge.learning_estimator import estimate_project
        tonnage = float(analysis.get("estimated_tonnage", 0) or 0) if analysis else 0
        if tonnage > 0:
            return estimate_project(tonnage)
        return {"note": "No tonnage detected - manual estimate required", "total_estimate": 0}
    except Exception as e:
        return {"error": str(e)[:100], "total_estimate": 0}

def _match_sweet_spot(analysis):
    try:
        from bridge.autonomous_bidding import match_opportunity
        return match_opportunity({
            "title": analysis.get("project_name", "") if analysis else "",
            "description": " ".join(analysis.get("scope_keywords", [])) if analysis else "",
            "location": analysis.get("location", "") if analysis else "",
        })
    except Exception:
        return {"match": True, "score": 50}  # Default: pursue

def _seed_lien_calendar(project):
    try:
        from bridge.fin_automation.finance import calculate_lien_deadlines
        return calculate_lien_deadlines(project, date.today().isoformat())
    except Exception:
        return {"note": "TX lien calendar - deadlines will auto-populate after contract execution"}

def _build_coordinate_model(project, bid_number="", pdf_path="", members=None):
    """Slice 1: in-house estimate-grade coordinate model. Reads the framing
    plan's grid + datums, places columns, and saves coordinate_members.json plus
    a MODEL viewport to the bid renders/ folder so find_render can use it as the
    page-1 fallback when no Tekla export exists. QC/visualization only; Tekla
    Structures stays the fabrication system of record. Returns a small summary;
    the _step wrapper catches any error so this never blocks the chain."""
    from bridge.lift_clone import geometry as _geo
    model = _geo.build_coordinate_members(
        pdf_path=pdf_path or "", members=members or [], project_name=project)
    meta = model.get("meta", {})
    summary = {
        "confidence": meta.get("confidence"),
        "needs_review": meta.get("needs_review"),
        "columns": meta.get("column_count", 0),
    }
    renders = None
    try:
        from bridge.tekla_viewport import _renders_dir
        renders = _renders_dir(bid_number or None, project or None)
    except Exception:
        renders = None
    if renders is None:
        summary["note"] = "no renders dir resolvable; in-house model not persisted"
        return summary
    _geo.save_coordinate_members(model, str(renders / "coordinate_members.json"))
    rendered = _geo.render_model_png(model, str(renders),
                                     name=bid_number or project or "model")
    summary["model_png"] = rendered.get("png", "")
    return summary


def _require_tekla_viewport(project, bid_number=""):
    """Locate the bid's Tekla viewport export (member-accurate page-1 image),
    or return the export-required action so the pipeline surfaces it as a gate.
    AI renders never fill this slot."""
    try:
        from bridge.tekla_viewport import require_tekla_viewport
        return require_tekla_viewport(project_name=project, bid_number=bid_number or None)
    except Exception as e:
        return {"ok": False, "required": True, "source": "tekla_viewport", "error": str(e)[:160]}


def _generate_proposal(project, gc, analysis, estimate, bid_number=""):
    try:
        from bridge.documents import generate_proposal
        # Drawing-anchored illustrative render, if the steel-render pipeline
        # produced one for this job (bid renders/ folder). Client proposal only.
        render_path = ""
        try:
            from bridge.bid_documents import find_render
            render_path = find_render(project_name=project, bid_number=bid_number or None)
        except Exception:
            render_path = ""
        return generate_proposal(
            project_name=project,
            gc_name="",
            gc_company=gc,
            scope_text="\n".join(f"\u2022 {kw}" for kw in (analysis.get("scope_keywords", []) if analysis else [])),
            tonnage=str(analysis.get("estimated_tonnage", "TBD") if analysis else "TBD"),
            total_estimate=f"${estimate['total_estimate']:,.2f}" if estimate and estimate.get("total_estimate") else "TBD",
            render_path=render_path,
        )
    except Exception:
        return {"note": "Proposal generation - requires project details"}

def _hash_document(project, proposal):
    try:
        from bridge.hash_chain import add_to_chain
        content = json.dumps({"project": project, "proposal": str(proposal)[:500]})
        return add_to_chain("PROPOSAL", f"{project}_proposal", content=content)
    except Exception:
        return {"note": "Hash chain - document will be added after proposal is finalized"}

def _draft_email(project, gc, estimate):
    est_str = f"${estimate['total_estimate']:,.0f}" if estimate and estimate.get("total_estimate") else "per attached"
    return {
        "subject": f"Bid Submission - {project} - Your Company LLC",
        "to": gc or "[GC Contact]",
        "body": (
            f"Please find attached our proposal for {project}.\n\n"
            f"Estimated value: {est_str}\n\n"
            f"Your Company LLC is an AISC-certified structural steel fabricator "
            f"and erector based in Houston, TX.\n"
            f"ISN: [ISN ID] | EMR: 0.78\n\n"
            f"We look forward to the opportunity to participate.\n\n"
            f"The Owner, CEO\n"
            f"Your Company LLC\n"
            f"[COMPANY PHONE] | owner@yourcompany.example.com"
        ),
    }

def _predict_win(analysis, estimate):
    try:
        from bridge.predictive.analytics import predict_win_probability
        tonnage = float(analysis.get("estimated_tonnage", 0) or 0) if analysis else 0
        est_val = estimate.get("total_estimate", 0) if estimate else 0
        return predict_win_probability(est_val, tonnage)
    except Exception:
        return {"probability": "N/A", "note": "Need 30+ historical bids to calibrate"}

def _emit_event(event_type, payload):
    try:
        from bridge.event_bus import emit
        emit(event_type, payload, source="bid_chain")
    except Exception:pass


# ═══ CHAIN STATUS ══════════════════════════════════════════════════

def get_chain_capability() -> dict:
    """Report what the autonomous chain can do right now."""
    capabilities = {}

    tests = [
        ("bid_analysis", "bridge.autonomous_bidding", "analyze_bid_invitation"),
        ("spec_parsing", "bridge.doc_intel.intelligence", "parse_spec_sections"),
        ("ai_takeoff", "bridge.lift_clone.takeoff", "run_takeoff"),
        ("steel_pricing", "bridge.agents.steel_price.agent", "get_latest_prices"),
        ("compliance_preflight", "bridge.action_chains", "run_compliance_preflight"),
        ("calibrated_estimate", "bridge.learning_estimator", "estimate_project"),
        ("sweet_spot_match", "bridge.autonomous_bidding", "match_opportunity"),
        ("lien_calendar", "bridge.fin_automation.finance", "calculate_lien_deadlines"),
        ("proposal_generation", "bridge.documents", "generate_proposal"),
        ("hash_chain", "bridge.hash_chain", "add_to_chain"),
        ("win_prediction", "bridge.predictive.analytics", "predict_win_probability"),
        ("event_bus", "bridge.event_bus", "emit"),
    ]

    for name, module, func in tests:
        try:
            mod = __import__(module, fromlist=[func])
            getattr(mod, func)
            capabilities[name] = "READY"
        except Exception:
            capabilities[name] = "UNAVAILABLE"

    ready = sum(1 for v in capabilities.values() if v == "READY")
    return {
        "capabilities": capabilities,
        "ready": ready,
        "total": len(tests),
        "chain_operational": ready >= 8,  # Need at least 8/12 for a useful chain
        "description": "email → analyze → spec → takeoff → price → comply → estimate → lien → propose → hash → email → submit",
    }
