"""
Your Company Virtual Office. Runtime Diagnostics Engine.

A live health check that exercises every Bridge method, calculator,
MCP dispatcher, harness, and validator with safe inputs, logs results
to data/diagnostics/, and returns a structured summary.

Usage:
    Chat:     "run diagnostics"
    MCP:      infra.diagnostics
    Python:   from bridge.diagnostics import run_diagnostics
              report = run_diagnostics()

v3.5.12 sim sweep 4.  First release.
"""

import inspect
import json
import logging
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("diagnostics")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LOG_DIR = _DATA_DIR / "diagnostics"

# ── Safe test inputs per method ──────────────────────────────────────
# Methods not listed here get called with no args (or skipped if they
# require positional args).  Methods in _SKIP never run.

_SAFE_ARGS: dict[str, dict[str, Any]] = {
    # Engineering / AISC
    "validate_shapes": {"members": [{"shape": "W14X82", "qty": 1, "length_ft": 20}]},
    "get_aisc_member_info": {"designation": "W14X82"},
    "normalize_shape": {"raw_shape": "w14x82"},
    "list_steel_shapes": {},
    "aisc_mass_balance": {"extracted_tonnage": 0.82, "members": [{"shape": "W14X82", "qty": 1, "length_ft": 20}]},
    "check_connections": {"project": "DIAG_TEST", "nodes": []},
    "batch_check_connections": {"project": "DIAG_TEST", "nodes": []},
    "check_wps_d11_2025": {"wps": {"wps_id": "TEST001"}, "code_year": 2025},
    "drawing_revision_diff": {"old_members": [], "new_members": []},

    # Calculators / math
    "generate_3d_view": {"shape": "W14X82", "length_ft": 20, "count": 1},
    "generate_stl": {"shape_name": "W14X82", "length_ft": 20},
    "generate_dxf": {"shape": "W14X82", "output_type": "cross_section"},
    "generate_wireframe": {"members": [], "grid_spacing_x": 25, "grid_spacing_y": 25, "eave_height": 20},
    "get_fab_productivity": {"hours": 100, "tons": 10},

    # Bid pipeline (read-only probes)
    "get_bid_pipeline": {},
    "get_pipeline": {},
    "get_pipeline_stats": {},
    "get_pipeline_summary": {},
    "get_pipeline_progress": {},
    "list_recent_bids": {"limit": 3},
    "get_bid_rates": {},
    "get_rates": {},
    "get_markup_margin_table": {},
    "get_rate_history": {},
    "suggest_bid_number": {"project_name": "Diagnostic Test", "location_code": "HOU"},
    "next_bid_number": {"city": "Houston"},
    "bid_history_compare": {"tonnage": 100, "total_bid": 375000, "gc_company": "Test GC", "building_type": "commercial"},
    "get_bid_template": {"template_name": "STANDARD"},

    # Scope / narrative
    "generate_scope_narrative": {"members": [], "tonnage": 100, "deck_sf": 5000, "building_type": "commercial", "project_name": "DIAG"},

    # Quality / compliance
    "check_voice": {"text": "Your Company provides structural steel fabrication."},
    "check_bid_compliance": {"content": "Structural steel package", "context": "bid"},
    "run_bid_harness": {},
    "run_compliance_attacks": {},
    "get_pdf_qc_rules": {},
    "score_bid": {"proposal_text": "Your Company steel package", "tonnage": 100, "total_bid": 375000},
    # WARN-03 (v3.2.7.14 post-audit): exercise the two new Bridge methods
    "get_bid": {"bid_id": 0},  # returns _err on id=0, no crash
    "review_bid": {"bid_json": '{"name":"DIAG","tons":85,"bid_total":580000,"margin_pct":0.25,"deck_sf":25000,"scope":["structural steel","erection"]}'},

    # Communications (preview only, never sends)
    "score_email_text": {"subject": "Bid Follow Up", "body": "Following up on our proposal."},
    "get_contacts_for_email": {"company": "Test GC"},
    "check_bid_emr": {"emr": 0.85, "prospect_type": "refinery"},

    # Governance
    "get_governance_status": {},
    "get_governance_audit": {"limit": 5},
    "get_governance_resolution": {"key": "deck_scope"},
    "get_auto_defaults": {},
    "get_rules": {},

    # Skills
    "list_skills": {},
    "list_intents": {},
    "classify_intent": {"message": "build the bid for diagnostics"},
    "match_skill": {"message": "generate proposal"},

    # Infrastructure
    "get_health": {},
    "get_app_info": {},
    "version": {},
    "get_kpis": {},
    "get_integrations": {},
    "get_token_usage": {"days": 7},
    "get_time_saved": {},
    "get_sentry_release": {},
    "gdrive_sync_status": {},
    "get_vault_sync_status": {},
    "mail_scanner_status": {},
    "get_agent_health": {},
    "get_resilience_status": {},
    "run_self_test": {},
    "get_system_inventory": {},
    "get_session_state": {},
    "get_display_prefs": {},
    "get_api_registry": {},
    "get_audit_log": {"limit": 5},
    "get_event_log": {"limit": 5},
    "get_message_log": {"limit": 5},

    # Contacts / CRM
    "search_contacts": {"query": "test", "limit": 3},

    # AR / Finance
    "get_ar_aging": {},
    "get_ar_alerts": {},
    "get_financial_dashboard": {},
    "get_cash_flow_projection": {"bank_balance": 500000, "monthly_overhead": 85000},

    # Shop / production
    "get_shop_log": {"days": 7},
    "get_shop_kpis": {"days": 7},
    "get_production_board": {},
    "get_projects": {},
    "list_fab_tools": {},

    # Market / prices
    "fetch_steel_prices": {},
    "get_steel_prices": {},
    "get_latest_steel_prices": {},
    "get_steel_agent_stats": {},
    "get_market_dashboard": {},
    "get_houston_pipeline": {"top_n": 3},
    "get_macro_indicators": {},
    "get_fuel_surcharge": {},
    "fred_key_status": {},

    # Compliance / ISN
    "get_compliance": {},
    "get_compliance_stats": {},
    "get_blockers": {},
    "get_isn_scorecard": {},
    "get_ravs_scorecard": {},
    "get_audit_readiness": {},
    "check_expiring_certs": {"days": 30},

    # Welding
    "get_wps_status": {},
    "get_prequalified_wps": {},
    "calc_weld_consumable": {"joint_type": "fillet", "leg_size_in": 0.25, "length_in": 12, "process": "SMAW"},
    "estimate_weld_consumable": {"joint_type": "fillet", "size_in": 0.25, "length_in": 12, "process": "SMAW"},

    # Change orders
    "get_change_orders": {},

    # Calibration
    "get_calibration_summary": {},
    "get_calibrated_estimate": {"tonnage": 100, "project_type": "commercial"},
    "get_win_probability": {"bid_amount": 375000, "tonnage": 100, "gc_name": "Test GC", "project_type": "commercial"},

    # Misc read-only
    "get_team": {},
    "get_priorities": {},
    "get_reminders": {},
    "get_quick_actions": {},
    "get_channel_config": {},
    "get_sms_status": {},
    "get_sms_event_toggles": {},
    "get_standing_files": {},
    "get_data_feed_stats": {},
    "get_news_digest": {},
    "get_osha_300a": {"year": 2025, "hours_worked": 200000, "avg_employees": 12},
    "get_bom": {"project_name": "test"},
    "get_dual_account_strategy": {},
    "get_cost_engine_status": {},
    "get_token_routing": {},
    "get_hedge_recommendation": {"tonnage": 100, "duration_days": 90},

    # v6.1.2 diagnostic fixture additions
    "detect_misc_steel": {"text": "W8X31 lintel 6ft embed plate 12x12x3/4"},
    "load_skill": {"name": "bid-pricing"},
    "parse_ssp_export": {"ssp_text": "Mark,Shape,Length,Qty,Weight\nC1,W14X82,30,10,24600"},
    "review_bid_ssp": {"ssp_text": "Mark,Shape,Length,Qty,Weight\nC1,W14X82,30,10,24600", "project_name": "DIAG_TEST"},

    # Virtual Joseph quality agent
    "vj_validate": {"request": "test", "response": "Clean fabrication output."},
    "vj_check_bias": {"text": "Your Company provides structural steel fabrication."},
    "vj_sweep": {},
    "vj_get_corrections": {},

    # LinkedIn content (v3.2.7.9+)
    "linkedin_list_formats":      {},
    "linkedin_approved_numbers":  {},
    "get_stock_watchlist":        {},
    "linkedin_fingerprint_check": {"text": "Your Company builds structural steel in Houston."},
    "draft_linkedin_post":        {"topic": "structural steel fabrication", "format_code": "D"},
    "poll_linkedin_draft":        {"job_id": ""},   # safe - returns 'generating' on empty/missing id

    # Bid pipeline shortcuts (v3.2.7.x)
    "next_bid_state":  {"bid_id": 0},     # returns clean _err on id=0, no crash
    "get_routing_table": {},
}

# Methods that are destructive, require real API keys, external
# services, or would send real messages.  Never run automatically.
_SKIP: set[str] = {
    # Sends real messages
    "send_sms_to_owner", "send_email_outlook", "draft_email_outlook",
    "send_morning_briefing_now", "send_test_notification",
    "confirm_refinery_outreach", "draft_refinery_outreach",
    # Modifies real data
    "factory_reset", "shutdown", "prune_conversation_history",
    "import_from_backup", "export_all_data",
    "update_bid_rates", "save_channel_config",
    "activate_api", "deactivate_api", "remove_api",
    "set_ceo_preference", "set_user_pref", "set_display_prefs",
    "set_escalation_threshold", "setup_sms",
    "set_sms_event_toggle", "set_bid_template",
    "save_integration_credentials", "save_qb_mapping_override",
    # Requires real files / external services
    "auto_process_drawing", "auto_process_project_files",
    "run_hybrid_3d_pipeline", "takeoff_from_pdf",
    "extract_drawing_set", "rasterize_drawing_page",
    "extract_cad_layer", "hash_drawing_pages",
    "compare_drawing_revisions", "run_pdf_qc",
    "orchestration_ingest", "verify_document",
    "inspect_weld_image", "inspect_weld_vision",
    "capture_drone", "process_drone_images",
    "import_accounting_csv", "import_qb_trial_balance",
    "import_qb_trial_balance_file",
    "parse_dstv", "parse_dstv_extended", "parse_ifc",
    "open_bids_folder", "start_tunnel", "start_webhook",
    # Requires AI API keys (expensive)
    "ai_ask", "compose_full_bid", "run_bid_chain",
    "analyze_bid", "analyze_spec", "auto_respond_to_bid",
    "generate_proposal", "generate_change_order",
    "generate_case_study", "generate_followup_sequence",
    "generate_pay_app", "export_project_card_pdf",
    "orchestration_proofread", "orchestration_verify",
    "knowledge_query", "knowledge_for_ai",
    "pull_rss_news", "pull_houston_pipeline",
    "scan_bids", "search_inbox_for_bid",
    "predict_bid_win", "predict_win_probability",
    "predict_emr",
    # MCP proxy
    "mcp_call_tool", "mcp_list_tools", "mcp_list_servers",
    "mcp_status", "mcp_prefer_routing",
    # Writes to pipeline DB (test isolation)
    "add_bid", "advance_bid", "update_bid_status",
    "add_to_pipeline", "mark_lead_actioned",
    "bid_history_log",
    # Other writes
    "add_blocker", "resolve_blocker",
    "add_contact", "update_contact",
    "add_cost_entry", "update_project_costs",
    "add_project", "add_shop_piece", "add_welder",
    "add_certificate", "add_to_hash_chain",
    "log_production", "log_shop_activity", "log_sensor_reading",
    "log_drone_flight", "log_weld_inspection", "log_ar_payment",
    "log_project_completion",
    "scan_piece", "publish_mes_event", "emit_event",
    "record_shape_correction", "record_weld_activity",
    "create_ar_milestones", "create_co", "create_rfi",
    "create_bluebeam_session",
    "save_bid_artifact", "save_temp_file",
    "ingest_service_center_prices",
    "vault_sync_preferences", "vault_sync_projects",
    "vault_sync_session",
    "gdrive_push", "gdrive_pull",
    "session_boot",
    "track_time_saved",
    # Read-only but needs valid project/ID
    "get_bid_detail", "get_ar_status", "get_contact",
    "read_bid_stl", "read_bid_takeoff", "list_bid_artifacts",
    "get_project_costs", "get_project_profit",
    "get_qbo_sync", "get_cost_engine_status",
    "get_production_board",
    # Diagnostic engine (would recurse)
    "run_diagnostics",
    # Requires special setup
    "run_daily_agents", "pull_steel_prices",
    "fetch_price_emails", "search_federal_opportunities",
    "get_federal_opportunities",
    # v6.1.2: external services or unbootable state
    "batch_check_connections",  # IDEA StatiCa required
    "check_connections",        # IDEA StatiCa required
    "generate_dxf",             # ezdxf required
    "get_bom",                  # needs real takeoff data
    "get_bond_capacity",        # finance module config
    "get_session_state",        # session not booted
    "vj_catalog_correction",    # writes to disk
    "vj_scan",                  # runs full diagnostic suite (timeout)
    "vj_scan_and_fix",          # runs full diagnostic suite + writes fixes
    "vj_train",                 # writes training data to disk
}


# ── Category classification ──────────────────────────────────────────

def _categorize(name: str) -> str:
    """Classify a Bridge method into a human-readable category."""
    prefixes = [
        ("validate_shapes", "engineering"),
        ("aisc_", "engineering"),
        ("check_connections", "engineering"),
        ("batch_check", "engineering"),
        ("normalize_shape", "engineering"),
        ("list_steel", "engineering"),
        ("check_wps", "engineering"),
        ("drawing_revision", "engineering"),
        ("get_aisc", "engineering"),
        ("generate_3d", "engineering"),
        ("generate_stl", "engineering"),
        ("generate_dxf", "engineering"),
        ("generate_wireframe", "engineering"),
        ("generate_gcode", "engineering"),
        ("generate_ironworker", "engineering"),
        ("get_bid", "bid_pipeline"),
        ("get_pipeline", "bid_pipeline"),
        ("get_rate", "bid_pipeline"),
        ("bid_history", "bid_pipeline"),
        ("suggest_bid", "bid_pipeline"),
        ("next_bid", "bid_pipeline"),
        ("score_bid", "quality"),
        ("check_voice", "quality"),
        ("check_bid_compliance", "quality"),
        ("run_bid_harness", "quality"),
        ("run_compliance", "quality"),
        ("get_pdf_qc", "quality"),
        ("check_bid_emr", "quality"),
        ("score_email", "quality"),
        ("get_governance", "governance"),
        ("get_auto_defaults", "governance"),
        ("get_rules", "governance"),
        ("list_skills", "skills"),
        ("list_intents", "skills"),
        ("classify_intent", "skills"),
        ("match_skill", "skills"),
        ("load_skill", "skills"),
        ("get_health", "infrastructure"),
        ("get_app_info", "infrastructure"),
        ("version", "infrastructure"),
        ("get_kpi", "infrastructure"),
        ("run_self_test", "infrastructure"),
        ("get_system", "infrastructure"),
        ("get_session", "infrastructure"),
        ("get_sentry", "infrastructure"),
        ("gdrive_", "infrastructure"),
        ("get_vault", "infrastructure"),
        ("mail_scanner", "infrastructure"),
        ("get_agent_health", "infrastructure"),
        ("get_resilience", "infrastructure"),
        ("get_token", "infrastructure"),
        ("get_time_saved", "infrastructure"),
        ("get_integrations", "infrastructure"),
        ("get_display", "infrastructure"),
        ("get_api_registry", "infrastructure"),
        ("get_audit", "compliance"),
        ("get_compliance", "compliance"),
        ("get_blockers", "compliance"),
        ("get_isn", "compliance"),
        ("get_ravs", "compliance"),
        ("check_expiring", "compliance"),
        ("get_ar_", "finance"),
        ("get_financial", "finance"),
        ("get_cash_flow", "finance"),
        ("calc_weld", "welding"),
        ("estimate_weld", "welding"),
        ("get_wps", "welding"),
        ("get_prequalified", "welding"),
        ("get_shop", "shop"),
        ("get_production", "shop"),
        ("get_fab_", "shop"),
        ("list_fab", "shop"),
        ("get_steel", "market"),
        ("fetch_steel", "market"),
        ("get_latest_steel", "market"),
        ("get_market", "market"),
        ("get_houston", "market"),
        ("get_macro", "market"),
        ("get_fuel", "market"),
        ("fred_key", "market"),
        ("generate_scope", "narrative"),
        ("search_contacts", "contacts"),
        ("get_change_orders", "change_orders"),
        ("get_calibrat", "calibration"),
        ("get_win_prob", "calibration"),
        ("get_team", "misc"),
    ]
    for prefix, cat in prefixes:
        if name.startswith(prefix):
            return cat
    return "other"


# ── Diagnostic runner ────────────────────────────────────────────────

def _call_safe(bridge: Any, method_name: str, args: dict,
               timeout_sec: float = 5.0) -> dict:
    """Call a single Bridge method with safe args, capturing result.

    Uses threading to enforce a timeout so network-bound methods
    don't hang the entire diagnostic run.
    """
    import threading

    fn = getattr(bridge, method_name)
    container: dict = {"result": None, "error": None}

    def _run():
        try:
            container["result"] = fn(**args)
        except Exception as e:
            container["error"] = e

    t0 = time.perf_counter()
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)
    elapsed = time.perf_counter() - t0

    if thread.is_alive():
        return {
            "method": method_name,
            "status": "WARN",
            "elapsed_ms": round(elapsed * 1000, 1),
            "result_type": None,
            "result_preview": None,
            "error": f"TIMEOUT after {timeout_sec}s (method may be waiting on network)",
        }

    if container["error"] is not None:
        e = container["error"]
        return {
            "method": method_name,
            "status": "FAIL",
            "elapsed_ms": round(elapsed * 1000, 1),
            "result_type": None,
            "result_preview": None,
            "error": f"{type(e).__name__}: {str(e)[:200]}",
            "traceback": traceback.format_exception(e)[-1][:500] if hasattr(traceback, 'format_exception') else str(e)[:500],
        }

    result = container["result"]
    if result is None:
        rtype = "None"
        ok = True
    elif isinstance(result, dict):
        rtype = "dict"
        ok = result.get("ok", True) is not False
        if "error" in result and not result.get("ok", True):
            ok = False
    elif isinstance(result, (list, tuple)):
        rtype = f"list[{len(result)}]"
        ok = True
    elif isinstance(result, str):
        rtype = f"str[{len(result)}]"
        ok = True
    else:
        rtype = type(result).__name__
        ok = True

    return {
        "method": method_name,
        "status": "PASS" if ok else "WARN",
        "elapsed_ms": round(elapsed * 1000, 1),
        "result_type": rtype,
        "result_preview": str(result)[:200] if result is not None else "None",
        "error": None,
    }


def _run_calculator_suite() -> list[dict]:
    """Exercise all 13 calculators through run_calc."""
    from bridge.calculators import run_calc
    results = []

    calc_tests = {
        "steel_weight": {"items": [("W14X82", 20, 1)]},
        "hours_estimate": {"tons": 50, "complexity": "standard"},
        "labor_cost": {"fab_hours": 80, "erect_hours": 20},
        "bid_total": {"steel_lbs": 200000, "labor_cost_usd": 50000, "tons": 100},
        "bolt_count": {"connections": [{"type": "shear_tab", "bolts": 4}]},
        "margin_scenario": {"direct_cost": 750000},
        "crew_size": {"total_hours": 800, "target_weeks": 8},
        "weld_consumables": {"leg_in": 0.25, "length_in": 120},
        "plate_weight": {"thickness_in": 0.5, "width_in": 12, "length_in": 48},
        "paint_area": {"items": [("W14X82", 20, 1)]},
        "trir": {"recordables": 1, "hours_worked": 200000},
        "days_until": {"target_date": "2026-12-31"},
        "schedule_pressure": {"tons": 100, "deadline_date": "2026-08-01"},
    }

    for name, args in calc_tests.items():
        t0 = time.perf_counter()
        try:
            r = run_calc(name, **args)
            elapsed = time.perf_counter() - t0
            has_error = "error" in r if isinstance(r, dict) else False
            results.append({
                "calculator": name,
                "status": "WARN" if has_error else "PASS",
                "elapsed_ms": round(elapsed * 1000, 1),
                "result_preview": str(r)[:200],
                "error": r.get("error") if has_error else None,
            })
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results.append({
                "calculator": name,
                "status": "FAIL",
                "elapsed_ms": round(elapsed * 1000, 1),
                "result_preview": None,
                "error": f"{type(e).__name__}: {str(e)[:150]}",
            })

    return results


def _run_dispatcher_suite() -> list[dict]:
    """Probe every MCP dispatcher with valid + invalid commands."""
    results = []
    try:
        from mcp_server import _dispatch_call, _DISPATCHER_MAPS
    except ImportError:
        return [{"dispatcher": "import", "status": "FAIL",
                 "error": "Cannot import mcp_server"}]

    for name in sorted(_DISPATCHER_MAPS):
        # Invalid command (should return ok:false, not crash)
        t0 = time.perf_counter()
        try:
            r = _dispatch_call(name, "__INVALID__", {})
            elapsed = time.perf_counter() - t0
            ok = isinstance(r, dict) and r.get("ok") is False
            results.append({
                "dispatcher": name,
                "test": "invalid_command",
                "status": "PASS" if ok else "WARN",
                "elapsed_ms": round(elapsed * 1000, 1),
                "error": None if ok else f"Expected ok:false, got {r}",
            })
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results.append({
                "dispatcher": name,
                "test": "invalid_command",
                "status": "FAIL",
                "elapsed_ms": round(elapsed * 1000, 1),
                "error": f"CRASH: {type(e).__name__}: {str(e)[:150]}",
            })

        # First valid command with empty args (should not crash)
        cmds = list(_DISPATCHER_MAPS[name].keys())
        if cmds:
            cmd = cmds[0]
            t0 = time.perf_counter()
            try:
                r = _dispatch_call(name, cmd, {})
                elapsed = time.perf_counter() - t0
                results.append({
                    "dispatcher": name,
                    "test": f"cmd:{cmd}",
                    "status": "PASS",
                    "elapsed_ms": round(elapsed * 1000, 1),
                    "error": None,
                })
            except Exception as e:
                elapsed = time.perf_counter() - t0
                results.append({
                    "dispatcher": name,
                    "test": f"cmd:{cmd}",
                    "status": "FAIL",
                    "elapsed_ms": round(elapsed * 1000, 1),
                    "error": f"CRASH: {type(e).__name__}: {str(e)[:150]}",
                })

    return results


def _run_harness_suite() -> list[dict]:
    """Run all 3 quality harnesses."""
    results = []

    # Compliance attacks
    try:
        from harnesses.operational import ComplianceAttackLibrary
        r = ComplianceAttackLibrary().run_all()
        results.append({
            "harness": "compliance_attacks",
            "status": "PASS" if r["accuracy"] == 100.0 else "FAIL",
            "detail": f"{r['correct']}/{r['total_phrases']} ({r['accuracy']}%)",
            "missed": r.get("missed", 0),
        })
    except Exception as e:
        results.append({"harness": "compliance_attacks", "status": "FAIL",
                        "error": f"{type(e).__name__}: {e}"})

    # Bid pipeline
    try:
        from harnesses.operational import BidPipelineHarness
        r = BidPipelineHarness.run()
        results.append({
            "harness": "bid_pipeline",
            "status": "PASS" if r["passed"] == r["total"] else "FAIL",
            "detail": f"{r['passed']}/{r['total']}",
        })
    except Exception as e:
        results.append({"harness": "bid_pipeline", "status": "FAIL",
                        "error": f"{type(e).__name__}: {e}"})

    # Voice calibration
    try:
        from harnesses.operational import VoiceCalibrationHarness
        vh = VoiceCalibrationHarness()
        clean_text = "Your Company provides structural steel fabrication and erection."
        r = vh.check(clean_text)
        violations = r.get("hard_violations", 0) + r.get("soft_violations", 0)
        results.append({
            "harness": "voice_calibration",
            "status": "PASS" if violations == 0 else "WARN",
            "detail": f"{violations} violations on clean text",
        })
    except Exception as e:
        results.append({"harness": "voice_calibration", "status": "FAIL",
                        "error": f"{type(e).__name__}: {e}"})

    return results


def _run_aisc_suite() -> list[dict]:
    """Probe AISC validator with known shapes and edge cases."""
    results = []
    try:
        from bridge.aisc_validator import (
            AISCValidator, extract_shape_designations,
            audit_shapes_in_text, _normalize_shape,
        )
    except ImportError as e:
        return [{"test": "import", "status": "FAIL", "error": str(e)}]

    v = AISCValidator()
    results.append({
        "test": "shape_count",
        "status": "PASS" if len(v.shape_list) >= 2200 else "FAIL",
        "detail": f"{len(v.shape_list)} shapes loaded",
    })

    # Valid shapes
    for shape, expected_wt in [("W14X82", 82.0), ("W18X35", 35.0), ("HSS6X6X1/2", 35.24)]:
        r = v.validate_shape(shape)
        ok = r.get("valid") and abs(r.get("weight_per_ft", 0) - expected_wt) < 0.1
        results.append({
            "test": f"valid:{shape}",
            "status": "PASS" if ok else "FAIL",
            "detail": f"valid={r.get('valid')}, wt={r.get('weight_per_ft')}",
        })

    # Invalid shape
    r = v.validate_shape("W14X81")
    results.append({
        "test": "invalid:W14X81",
        "status": "PASS" if not r.get("valid") else "FAIL",
        "detail": f"suggestions={r.get('suggestions', [])}",
    })

    # Normalization
    for raw, expected in [("w14x82", "W14X82"), ("HSS6X6X.500", "HSS6X6X1/2"),
                          ("W14\u00d782", "W14X82")]:
        normed = _normalize_shape(raw)
        results.append({
            "test": f"normalize:{raw}",
            "status": "PASS" if normed == expected else "FAIL",
            "detail": f"{raw} -> {normed} (expected {expected})",
        })

    # Extraction
    found = extract_shape_designations("Use W14X82 columns and HSS6X6X1/2 bracing")
    results.append({
        "test": "extraction:multi",
        "status": "PASS" if len(found) == 2 else "FAIL",
        "detail": f"found {len(found)} shapes: {found}",
    })

    # False positive guard
    found = extract_shape_designations("License plate MA1234")
    results.append({
        "test": "extraction:false_positive",
        "status": "PASS" if len(found) == 0 else "WARN",
        "detail": f"found {found} (should be empty)",
    })

    # Audit
    audit = audit_shapes_in_text("The W14X82 and W99X999 columns")
    results.append({
        "test": "audit:mixed",
        "status": "PASS" if "W99X999" in audit.get("invalid", [])
                         and "W14X82" in audit.get("valid", []) else "FAIL",
        "detail": f"valid={audit.get('valid')}, invalid={audit.get('invalid')}",
    })

    return results


# ── Main entry point ─────────────────────────────────────────────────

def run_diagnostics(
    include_bridge: bool = True,
    include_calculators: bool = True,
    include_dispatchers: bool = True,
    include_harnesses: bool = True,
    include_aisc: bool = True,
    log_to_file: bool = True,
) -> dict:
    """Run the full diagnostic suite and return a structured report.

    Args:
        include_*: toggle individual test suites
        log_to_file: write timestamped JSON log to data/diagnostics/

    Returns:
        {
            started_at, finished_at, duration_sec,
            summary: {total, passed, failed, warned, skipped},
            bridge_methods: [...],
            calculators: [...],
            dispatchers: [...],
            harnesses: [...],
            aisc: [...],
        }
    """
    started = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "started_at": started.isoformat(),
        "version": "diagnostics-v1",
    }
    all_results: list[dict] = []

    # ── Bridge methods ───────────────────────────────────────────
    bridge_results = []
    if include_bridge:
        from bridge.api import Bridge
        b = Bridge()
        public_methods = sorted(
            m for m in dir(b)
            if not m.startswith("_") and callable(getattr(b, m))
        )

        for method_name in public_methods:
            if method_name in _SKIP:
                bridge_results.append({
                    "method": method_name,
                    "status": "SKIP",
                    "category": _categorize(method_name),
                    "reason": "destructive/external/expensive",
                })
                continue

            args = _SAFE_ARGS.get(method_name)
            if args is None:
                # Try calling with no args
                fn = getattr(b, method_name)
                sig = inspect.signature(fn)
                required = [
                    p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty
                    and p.name != "self"
                ]
                if required:
                    bridge_results.append({
                        "method": method_name,
                        "status": "SKIP",
                        "category": _categorize(method_name),
                        "reason": f"no safe args defined (needs: {[p.name for p in required]})",
                    })
                    continue
                args = {}

            result = _call_safe(b, method_name, args)
            result["category"] = _categorize(method_name)
            bridge_results.append(result)

        report["bridge_methods"] = bridge_results
        all_results.extend(bridge_results)

    # ── Calculators ──────────────────────────────────────────────
    calc_results = []
    if include_calculators:
        calc_results = _run_calculator_suite()
        report["calculators"] = calc_results
        all_results.extend(calc_results)

    # ── MCP dispatchers ──────────────────────────────────────────
    disp_results = []
    if include_dispatchers:
        disp_results = _run_dispatcher_suite()
        report["dispatchers"] = disp_results
        all_results.extend(disp_results)

    # ── Harnesses ────────────────────────────────────────────────
    harness_results = []
    if include_harnesses:
        harness_results = _run_harness_suite()
        report["harnesses"] = harness_results
        all_results.extend(harness_results)

    # ── AISC validator ───────────────────────────────────────────
    aisc_results = []
    if include_aisc:
        aisc_results = _run_aisc_suite()
        report["aisc"] = aisc_results
        all_results.extend(aisc_results)

    # ── Summary ──────────────────────────────────────────────────
    finished = datetime.now(timezone.utc)
    counts = {"total": 0, "passed": 0, "failed": 0, "warned": 0, "skipped": 0}
    for r in all_results:
        s = r.get("status", "SKIP")
        counts["total"] += 1
        if s == "PASS":
            counts["passed"] += 1
        elif s == "FAIL":
            counts["failed"] += 1
        elif s == "WARN":
            counts["warned"] += 1
        elif s == "SKIP":
            counts["skipped"] += 1

    report["finished_at"] = finished.isoformat()
    report["duration_sec"] = round((finished - started).total_seconds(), 2)
    report["summary"] = counts

    # Collect failures for quick review
    failures = [
        r for r in all_results
        if r.get("status") == "FAIL"
    ]
    report["failures"] = failures

    # ── Log to file ──────────────────────────────────────────────
    if log_to_file:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = started.strftime("%Y%m%d_%H%M%S")
        log_path = _LOG_DIR / f"diag_{ts}.json"
        # Strip tracebacks for the JSON log (keep them in memory)
        log_data = json.loads(json.dumps(report, default=str))
        for entry in log_data.get("bridge_methods", []):
            entry.pop("traceback", None)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, default=str)
        report["log_file"] = str(log_path)
        logger.info("Diagnostic log written to %s", log_path)

    return report


def diagnose_working_tree() -> dict:
    """Compare each bridge/**/*.py on disk against git HEAD.

    Returns a dict with keys:
      ok (bool)          - True if no significant truncations detected
      issues (list[str]) - human-readable lines describing each truncated file
      checked (int)      - number of files compared
    """
    import subprocess
    import glob

    issues: list[str] = []
    checked = 0
    bridge_root = Path(__file__).resolve().parent

    py_files = list(bridge_root.rglob("*.py"))
    for abs_path in py_files:
        rel_path = abs_path.relative_to(bridge_root.parent)  # relative to project root
        rel_posix = rel_path.as_posix()
        try:
            result = subprocess.run(
                ["git", "show", f"HEAD:{rel_posix}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(bridge_root.parent),
            )
            if result.returncode != 0:
                continue  # file not tracked in HEAD - skip
            head_len = len(result.stdout)
            disk_len = abs_path.stat().st_size
            checked += 1
            if head_len > 0 and disk_len < head_len * 0.95:
                missing = head_len - disk_len
                pct = missing / head_len * 100
                issues.append(
                    f"{rel_posix}: disk is {missing} bytes shorter than HEAD ({pct:.1f}% missing)"
                )
        except Exception as exc:
            issues.append(f"{rel_posix}: comparison error: {exc}")

    return {"ok": len(issues) == 0, "issues": issues, "checked": checked}


def format_report(report: dict) -> str:
    """Format a diagnostic report as human-readable text for chat.

    MC-05 fix: lead with a plain-English health line so Owner sees the
    relevant number first. Raw passed/total counts include 195 expected
    skips (destructive/external/expensive methods that are intentionally
    not exercised) which made the headline look much worse than reality.
    """
    s = report.get("summary", {})
    total = s.get("total", 0)
    passed = s.get("passed", 0)
    failed = s.get("failed", 0)
    warned = s.get("warned", 0)
    skipped = s.get("skipped", 0)
    exercised = max(total - skipped, 0)
    adjusted_pct = (passed / exercised * 100) if exercised > 0 else 0.0

    if failed == 0 and adjusted_pct >= 95:
        health = "HEALTHY"
    elif failed == 0 and adjusted_pct >= 85:
        health = "OK (warnings only)"
    elif failed <= 2:
        health = "DEGRADED"
    else:
        health = "UNHEALTHY"

    lines = [
        "DIAGNOSTIC REPORT",
        f"  Health: {health} - {passed}/{exercised} exercised checks pass ({adjusted_pct:.1f}%)",
        f"  Ran at: {report.get('started_at', '?')[:19]}",
        f"  Duration: {report.get('duration_sec', '?')}s",
        "",
        f"  PASS:  {passed}",
        f"  FAIL:  {failed}",
        f"  WARN:  {warned}",
        f"  SKIP:  {skipped}  (destructive/external calls - not exercised on purpose)",
        f"  TOTAL: {total}",
    ]

    failures = report.get("failures", [])
    if failures:
        lines.append("")
        lines.append(f"FAILURES ({len(failures)}):")
        for f in failures:
            name = f.get("method") or f.get("calculator") or f.get("dispatcher") or f.get("harness") or f.get("test") or "?"
            error = f.get("error", "unknown")
            lines.append(f"  FAIL: {name}: {error[:120]}")

    if report.get("log_file"):
        lines.append("")
        lines.append(f"Full log: {report['log_file']}")

    return "\n".join(lines)
