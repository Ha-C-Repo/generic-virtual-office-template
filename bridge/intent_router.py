"""
Your Company Virtual Office - Intent Router
==========================================
Translates the Owner's shorthand into full pipeline actions.

Source: core/intent-recognition.md (compiled from 224 conversations).

Principle: Owner should ask once and get what he is intending, not
just what he is literally saying. Apply pipelines silently. Ask only
when something is genuinely ambiguous.

Usage:
    from bridge.intent_router import classify_intent
    result = classify_intent("Build the bid")
    # result.intent = "full_bid_pipeline"
    # result.pipeline = [step1, step2, ...]
    # result.auto_defaults = {deck: "in_scope", ...}
    # result.ask_first = []  (nothing to ask)
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str                          # pipeline name
    confidence: float                    # 0.0-1.0
    pipeline: list[str]                  # ordered steps
    auto_defaults: dict[str, Any]        # apply silently
    ask_first: list[str]                 # ask Owner before proceeding
    context_files: list[str]             # project files to load
    voice: str = "owner"               # "owner" or "joseph"
    turnaround: str = ""                 # expected delivery speed


# ── Trigger Patterns ──────────────────────────────────────────────────
# Each entry: (list of trigger phrases, intent name)

_TRIGGERS: list[tuple[list[str], str]] = [
    # ── Bid generation ────────────────────────────────────────────────
    ([
        "build the bid", "take off this", "bid this", "complete takeoff",
        "take off this project", "run a takeoff", "get me a bid",
        "need a proposal", "build a complete structural steel proposal",
        "build complete bid now", "build me final bid", "build complete bid",
        "estimate this", "rough estimate", "price this job",
        "how much will this cost", "take off these",
    ], "full_bid_pipeline"),

    # ── Small project override ────────────────────────────────────────
    ([
        "50% minimum profit", "50% profit across the board",
        "small project, 50%", "50% profit", "small project",
    ], "small_project_override"),

    # ── Past bid review ───────────────────────────────────────────────
    ([
        "review against rulebook", "scrutinize it against our rules",
        "run against our latest rulebook", "check this past submitted bid",
        "review your bid", "does it make sense",
        "review this bid", "against our rules", "check this bid",
    ], "bid_review_against_rules"),

    # ── Designer PDF edit ─────────────────────────────────────────────
    ([
        "use my file", "use my altered file", "fix the pricing",
        "update this", "remove section", "preserve my original",
        "my altered file", "mirror my format", "use my designer",
    ], "designer_pdf_edit"),

    # ── Drawings uploaded ─────────────────────────────────────────────
    ([
        "client drawings", "arch drawings", "drawing set",
        "structural drawings", "s-sheets", "here are the drawings",
        "attached are the", "plan set",
        "drawings uploaded", "uploaded drawings", "uploaded here",
    ], "drawings_uploaded"),

    # ── GC response / screenshot ──────────────────────────────────────
    ([
        "response screenshot", "gc response", "gc's email",
        "screenshot from gc", "their response", "excel from gc",
        "see gc screenshot",
    ], "gc_response"),

    # ── Post-pipeline proposal generation ─────────────────────────────
    ([
        "generate the proposal", "build the proposal pdf",
        "make the client-facing pdf", "generate both pdfs",
        "now generate the proposal", "build the proposal",
        "generate proposal", "make the pdf", "create the proposal",
        "proposal pdf", "build both pdfs",
    ], "generate_proposal_from_pipeline"),

    # ── Email composition ─────────────────────────────────────────────
    ([
        "compelling email", "short selling email", "email body",
        "copy and paste", "my tone please", "casual and human",
        "short but strong body email", "make compelling body email",
        "friendly, agreeable", "structurally oriented email",
        "compose email", "compose an email", "write an email",
    ], "compose_email"),

    # ── Contact / email finding ───────────────────────────────────────
    ([
        "email addresses", "decision maker emails", "need their email",
        "get me other decision makers", "pull emails",
        "pms, superintendents", "front office emails",
        "find contacts", "find contact",
    ], "find_contacts"),

    # ── Strategic advisory / VE ───────────────────────────────────────
    ([
        "strategic advisory", "ve plan", "design change",
        "stop the bleeding", "ppv is seor", "we are not the engineer",
        "awaiting seor sign off", "strategic advisory plan",
    ], "strategic_advisory"),

    # ── Field issue ───────────────────────────────────────────────────
    ([
        "joist deflection", "field modification", "mario's message",
        "from on site", "need fix today", "build those options per aisc",
        "field modification report",
    ], "field_issue"),

    # ── Memory save ───────────────────────────────────────────────────
    ([
        "save this rule", "lock this in", "memorize", "save these rules",
        "make this part of our qc", "save all of this data",
        "lock this in your brain",
        "save this", "save for later", "remember this",
    ], "save_memory"),

    # ── Memory delete ─────────────────────────────────────────────────
    ([
        "delete contradictory memory", "remove old rule",
        "delete any other contradictory", "get rid of the old rule",
    ], "delete_memory"),

    # 3D model generation
    ([
        "generate 3d model", "create a 3d model", "3d view",
        "generate stl", "show me in 3d", "build 3d",
        "3d model from this", "render this in 3d",
    ], "generate_3d_model"),

    # Send email──────────────────────────────────────────────────
    ([
        "send email", "send the bid", "send to all decision makers",
        "draft and send",
    ], "send_email"),

    # ── Internal recap ────────────────────────────────────────────────
    ([
        "make a recap", "for amber", "for the team", "for mario",
        "condensed version", "short number equation",
        "internal recap", "give me a recap", "recap this",
    ], "internal_recap"),

    # ── Frustration correction (CAPS) ─────────────────────────────────
    ([
        "stop adding so much detail", "internal info on client doc",
        "we don't tell them why", "dangerous for the business",
    ], "frustration_internal_leak"),

    ([
        "why did you not run", "we need to discuss that first",
        "why do you keep doing this", "we cannot make this mistake",
        "you are the owner of full and complete takeoff",
    ], "frustration_takeoff_skipped"),

    # ── Done / close ──────────────────────────────────────────────────
    ([
        "done", "sent", "thanks", "got it", "i'll be right back",
        "close this", "close task", "mark complete",
    ], "task_closed"),

    # ── Daily shorthand commands ──────────────────────────────────────
    ([
        "morning brief", "morning update", "what's happening",
        "daily brief", "brief me", "status update",
        "what did i miss", "catch me up",
    ], "morning_brief"),

    ([
        "steel prices", "market update", "hrc prices",
        "steel market", "ppi data", "steel market brief",
        "what are steel prices", "steel cost update",
    ], "steel_market_brief"),

    ([
        "what's on my plate", "what is on my plate", "active projects", "what am i working on",
        "project status", "open bids", "pipeline status",
        "what's pending", "what's open",
    ], "active_projects"),

    ([
        "check isnetworld", "compliance status", "isnetworld status",
        "are we compliant", "ravs status", "safety compliance",
        "marathon status", "avetta status",
        "show compliance", "compliance check", "check compliance",
        "compliance", "my compliance", "compliance grade",
        "what's my compliance", "compliance score",
    ], "compliance_check"),

    ([
        "send morning text", "text owner", "send sms",
        "push notification", "text me", "send text",
        "send a text", "text joseph",
    ], "send_sms"),

    ([
        "linkedin post", "draft a post", "draft a linkedin post",
        "write a post", "linkedin draft", "social post",
        "write linkedin", "post for linkedin", "draft post",
        "linkedin content", "post about",
    ], "linkedin_post"),

    ([
        "run diagnostics", "diagnostics", "system check",
        "health check", "full system test", "diagnostic report",
        "check everything", "test all functions",
        # Real-world phrases Owner types (from Image 2 production session)
        "vj scan", "vj scan and fix", "scan and fix", "run scan",
        "vj fix", "run vj", "vj check", "vj self test", "vj selftest",
        "self test", "self-test", "run self test", "system scan",
        "scan for issues", "scan and repair", "fix issues",
    ], "run_diagnostics"),

    # MC-NEW-09 VJ fix: missing trigger patterns for core daily commands.
    # These covered natural-language phrasings that returned "unknown".
    ([
        "bid pipeline", "show pipeline", "list bids", "my bids",
        "what bids", "active bids", "pipeline status", "pipeline summary",
        "what's in the pipeline", "show bids", "bid list",
    ], "morning_brief"),

    ([
        "run takeoff", "takeoff from pdf", "do a takeoff",
        "process this pdf", "read these drawings", "parse this pdf",
        "process drawings", "extract members", "member list",
        "pdf takeoff", "takeoff pdf",
    ], "full_bid_pipeline"),

    ([
        "add change order", "create change order", "draft change order",
        "new change order", "write change order", "generate co",
        "change order for", "co for", "write a co", "open a change order",
        "add a change order", "create a change order", "draft a change order",
        "scope creep", "additional work", "extra work order",
    ], "change_order"),

    ([
        "bolt count", "how many bolts", "count bolts", "bolt cost",
        "a325 bolts", "a490 bolts", "bolt calculation", "bolt calc",
        "figure out bolts",
    ], "shape_lookup"),

    ([
        "draft outreach", "write outreach", "cold email", "outreach email",
        "email to", "reach out to", "contact gc", "email marathon",
        "write email to", "send outreach",
    ], "full_bid_pipeline"),

    ([
        "trir", "my trir", "safety rate", "incident rate",
        "calculate trir", "what is trir", "recordable rate",
    ], "compliance_check"),

    ([
        "add bid", "new bid", "create bid", "log a bid",
        "track this bid", "add to pipeline", "add a lead",
    ], "morning_brief"),

    ([
        "advance bid", "move bid", "update bid status", "push bid to",
        "bid to reviewing", "bid to pursuing", "change bid stage",
    ], "morning_brief"),

]

# ── Shape lookup regex (handled separately) ──────────────────────────
# Matches three forms:
#   1. Standard families with weight: W14X82, HSS6X4X1/4, L4X3X1/4, C12X20.7
#   2. Double angles: 2L4X3X1/4, 2L6X4X3/8 (the leading "2L" prefix)
#   3. PIPE schedule designations: PIPE6STD, PIPE12XS, PIPE3XXS, PIPE4SCH40
#      (PIPE doesn't follow the X-weight convention - it uses pipe schedule)
import re as _re
_SHAPE_PATTERN = _re.compile(
    r'\b('
    r'2L\d+[xX]\d+(?:[xX][\d/]+)?'                        # 2L double angles
    r'|(?:W|HSS|L|C|WT|MT|ST|S|HP|MC|M)\d+[xX][\d./]+'    # standard X-weight
    r'|PIPE\d+(?:\.\d+)?(?:STD|XS|XXS|SCH\d+|S40|S80|S160)'  # PIPE schedules
    r')',
    _re.IGNORECASE
)


# ── Pipeline Definitions ─────────────────────────────────────────────

_PIPELINES: dict[str, IntentResult] = {
    "full_bid_pipeline": IntentResult(
        intent="full_bid_pipeline",
        confidence=1.0,
        pipeline=[
            "classify_building",           # conventional/tilt-up/PEMB/bearing-wall
            "detect_drawing_stage",        # IFC/DD/Budget → apply contingency
            "detect_project_size",         # small project → 50% override
            "run_drawing_reading_protocol", # rasterize + view every sheet
            "read_general_notes_first",    # S-001/S-002
            "complete_tonnage_takeoff",    # member-by-member from images
            "cross_check_sf_vs_ton",       # must land within 10%
            "apply_locked_q2_rates",       # bid_rates.py
            "apply_auto_defaults",         # deck IN, CFMF OUT, 30/20/50, etc.
            "validate_cash_flow",          # 30%+20% covers all materials
            "build_client_proposal_pdf",   # Format v1.0 LOCKED
            "build_gp_report_pdf",         # CONFIDENTIAL, KPI, P&L
            "run_four_pass_qc",            # review-before-output
            "copy_to_outputs",             # /mnt/user-data/outputs/
            "present_files",               # same turn
            "draft_client_email",          # the Owner's voice
            "deliver_summary_line",        # one-line status
        ],
        auto_defaults={
            "deck": "in_scope",
            "cfmf": "excluded_csi_05_4000",
            "payment": "30_20_50",
            "validity": "30_days",
            "engineering": "folded_into_rates",
            "shop_drawings": "included_2_3_wks",
            "capabilities_close": "aisc_aws_sji_osha",
            "output_format": "pdf_only",
            "two_pdfs": True,
        },
        ask_first=[],
        context_files=[
            "data/rates-and-pricing.md",
            "templates/bidding-rules.md",
            "protocols/review-before-output.md",
            "protocols/drawing-reading-protocol.md",
        ],
        voice="owner",
        turnaround="same-day to 24 hours",
    ),

    "small_project_override": IntentResult(
        intent="small_project_override",
        confidence=1.0,
        pipeline=[
            "override_standard_gp_rates",
            "recompute_section_a_b_50pct",
            "flag_gp_report_cover",
            "no_client_disclosure",
        ],
        auto_defaults={
            "profit_target": 0.50,
            "gp_report_flag": "SMALL PROJECT 50% OVERRIDE per CEO directive",
        },
        ask_first=[],
        context_files=["data/rates-and-pricing.md"],
        voice="owner",
        turnaround="immediate (pricing adjustment only)",
    ),

    "bid_review_against_rules": IntentResult(
        intent="bid_review_against_rules",
        confidence=1.0,
        pipeline=[
            "load_verified_bid_corrections",
            "parse_uploaded_pdf",
            "run_20_hard_rules",
            "run_pass_3_leak_scan",
            "run_pass_4_layout_scan",
            "run_drawing_reading_if_quantities_questioned",
            "build_violations_list",
            "apply_pdf_edit_rule_if_asked",
            "confirm_total_matches_original",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[
            "data/verified-bid-corrections.md",
            "protocols/review-before-output.md",
        ],
        voice="owner",
        turnaround="<1 hour",
    ),

    "designer_pdf_edit": IntentResult(
        intent="designer_pdf_edit",
        confidence=1.0,
        pipeline=[
            "identify_changed_pages",
            "pypdf_keep_untouched_pages",
            "reportlab_rebuild_changed_pages",
            "splice_with_pypdf",
            "render_compare_pages",
            "run_pass_4_layout",
            "copy_and_present",
        ],
        auto_defaults={
            "preserve_unchanged": True,
            "never_rebuild_whole": True,
        },
        ask_first=[],
        context_files=["protocols/pdf-edit-rule.md"],
        voice="owner",
        turnaround="<30 min",
    ),

    "drawings_uploaded": IntentResult(
        intent="drawings_uploaded",
        confidence=1.0,
        pipeline=[
            "classify_pdf_input",
            "rasterize_all_plan_sheets",
            "view_each_rasterized_image",
            "read_s001_s002_first",
            "proceed_to_takeoff",
        ],
        auto_defaults={
            "text_extraction": "forbidden_for_quantities",
        },
        ask_first=[],
        context_files=[
            "protocols/drawing-reading-protocol.md",
            "protocols/pdf-input-classifier.md",
        ],
        voice="owner",
        turnaround="same-day",
    ),

    "gc_response": IntentResult(
        intent="gc_response",
        confidence=1.0,
        pipeline=[
            "view_screenshot",
            "identify_gc_action",
            "verify_gc_numbers_against_rulebook",
            "apply_pdf_edit_if_revision",
            "draft_response_if_question",
        ],
        auto_defaults={
            "trust_gc_numbers": False,  # always verify
        },
        ask_first=[],
        context_files=[],
        voice="owner",
        turnaround="<2 hours",
    ),

    "generate_proposal_from_pipeline": IntentResult(
        intent="generate_proposal_from_pipeline",
        confidence=1.0,
        pipeline=[
            "load_pipeline_results",         # tonnage, members, AISC data
            "apply_locked_q2_rates",         # bid_rates.py
            "apply_auto_defaults",           # deck IN, 30/20/50, etc.
            "validate_cash_flow",            # 30%+20% covers materials
            "build_client_proposal_pdf",     # Format v1.0 LOCKED
            "build_gp_report_pdf",           # CONFIDENTIAL
            "run_four_pass_qc",              # review-before-output
            "copy_to_outputs",               # /mnt/user-data/outputs/
            "present_files",                 # same turn
            "draft_client_email",            # the Owner's voice
            "deliver_summary_line",          # one-line status
        ],
        auto_defaults={
            "deck": "in_scope",
            "payment": "30_20_50",
            "engineering": "folded_into_rates",
            "output_format": "pdf_only",
            "two_pdfs": True,
            "use_pipeline_results": True,    # DO NOT restart takeoff
        },
        ask_first=[],
        context_files=[
            "data/rates-and-pricing.md",
            "templates/bidding-rules.md",
            "protocols/review-before-output.md",
        ],
        voice="owner",
        turnaround="<30 min",
    ),

    "compose_email": IntentResult(
        intent="compose_email",
        confidence=1.0,
        pipeline=[
            "load_email_patterns",
            "apply_owner_voice",
            "sign_owner_steel",
            "one_ask_per_email",
            "format_plain_text_copy_paste",
        ],
        auto_defaults={
            "signature": "Owner Steel",
            "no_apology_paragraph": True,
        },
        ask_first=[],
        context_files=["templates/email-patterns.md"],
        voice="owner",
        turnaround="immediate",
    ),

    "find_contacts": IntentResult(
        intent="find_contacts",
        confidence=1.0,
        pipeline=[
            "search_apollo_rocketreach",
            "filter_pm_superintendent_estimator",
            "return_name_title_email_linkedin",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "strategic_advisory": IntentResult(
        intent="strategic_advisory",
        confidence=1.0,
        pipeline=[
            "load_advisory_format",
            "authorship_owner_ceo_only",
            "no_pe_names_no_eng_names",
            "framing_seor_retains_responsibility",
            "distribution_restriction",
            "future_charge_protection",
        ],
        auto_defaults={
            "authorship": "The Owner, CEO only",
            "no_pe_names": True,
            "seor_statement": True,
        },
        ask_first=[],
        context_files=["templates/strategic-advisory-format.md"],
        voice="owner",
        turnaround="4-8 hours",
    ),

    "field_issue": IntentResult(
        intent="field_issue",
        confidence=1.0,
        pipeline=[
            "load_field_mod_template",
            "build_preliminary_assessment",
            "include_observations_causes_risks_next",
            "build_client_and_internal_versions",
            "build_single_page_action_report",
            "draft_email_your_company_to_the_rescue",
        ],
        auto_defaults={
            "disclaimer": "preliminary visual assessment only",
            "mario_routing": "never_assign_mario_tasks",
        },
        ask_first=[],
        context_files=["templates/field-modification-report.md"],
        voice="owner",
        turnaround="same-day",
    ),

    "save_memory": IntentResult(
        intent="save_memory",
        confidence=1.0,
        pipeline=[
            "identify_rule",
            "quote_owner_exact_wording",
            "save_to_memories",
            "update_mirrored_files",
            "delete_contradictory_older_text",
            "confirm_with_location",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=["data/saved-memories.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "delete_memory": IntentResult(
        intent="delete_memory",
        confidence=1.0,
        pipeline=[
            "identify_old_rule",
            "remove_entirely",
            "add_new_rule",
            "confirm_both_actions",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=["data/saved-memories.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "send_email": IntentResult(
        intent="send_email",
        confidence=1.0,
        pipeline=[
            "compose_email_body_owner_voice",
            "use_zapier_connector",
            "attach_pdfs",
            "confirm_sent",
        ],
        auto_defaults={"signature": "Owner Steel"},
        ask_first=[],
        context_files=[],
        voice="owner",
        turnaround="immediate",
    ),

    "internal_recap": IntentResult(
        intent="internal_recap",
        confidence=1.0,
        pipeline=[
            "strip_detail",
            "bullet_dollars_and_conclusions",
            "mirror_owner_altered_format",
            "no_marketing_language",
        ],
        auto_defaults={"distribution": "internal"},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "frustration_internal_leak": IntentResult(
        intent="frustration_internal_leak",
        confidence=1.0,
        pipeline=[
            "strip_rationale_from_client_doc",
            "keep_percentages_and_milestones_only",
            "move_rationale_to_gp_report",
            "rerun_pass_3_leak_scan",
            "regenerate_and_present",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=["protocols/review-before-output.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "frustration_takeoff_skipped": IntentResult(
        intent="frustration_takeoff_skipped",
        confidence=1.0,
        pipeline=[
            "explain_honestly_why_skipped",
            "apologize_for_rule_violation",
            "rerun_drawing_reading_protocol",
            "rebuild_bid_correct_quantities",
            "save_lesson_to_memories",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[
            "protocols/drawing-reading-protocol.md",
            "data/saved-memories.md",
        ],
        voice="joseph",
        turnaround="same-day",
    ),

    "task_closed": IntentResult(
        intent="task_closed",
        confidence=1.0,
        pipeline=["stop"],
        auto_defaults={},
        ask_first=[],
        context_files=[],
        voice="owner",
        turnaround="n/a",
    ),

    # ── Daily shorthand pipelines ─────────────────────────────────────

    "morning_brief": IntentResult(
        intent="morning_brief",
        confidence=1.0,
        pipeline=[
            "load_active_projects",
            "load_pending_bids",
            "load_blockers",
            "load_calendar_today",
            "build_brief_summary",
            "deliver_one_screen",
        ],
        auto_defaults={"format": "brief_bullets"},
        ask_first=[],
        context_files=["data/project-archive.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "steel_market_brief": IntentResult(
        intent="steel_market_brief",
        confidence=1.0,
        pipeline=[
            "pull_fred_ppi_data",
            "pull_hrc_midwest_price",
            "compare_to_last_month",
            "deliver_market_snapshot",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "shape_lookup": IntentResult(
        intent="shape_lookup",
        confidence=1.0,
        pipeline=[
            "parse_shape_designation",
            "lookup_aisc_database",
            "generate_3d_stl_if_length_given",
            "deliver_member_properties",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "active_projects": IntentResult(
        intent="active_projects",
        confidence=1.0,
        pipeline=[
            "load_active_projects",
            "load_pending_bids",
            "summarize_by_status",
            "deliver_table",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=["data/project-archive.md", "data/bid-pipeline.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "compliance_check": IntentResult(
        intent="compliance_check",
        confidence=1.0,
        pipeline=[
            "load_compliance_status",
            "check_isnetworld_gaps",
            "check_avetta_gaps",
            "check_emr_blocker",
            "deliver_compliance_summary",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=["data/compliance-status.md"],
        voice="joseph",
        turnaround="immediate",
    ),

    "change_order": IntentResult(
        intent="change_order",
        confidence=1.0,
        pipeline=[
            "scan_email_for_scope_changes",
            "identify_out_of_scope_items",
            "calculate_co_cost_impact",
            "generate_aia_g701_draft",
            "run_pdf_qc",
        ],
        auto_defaults={
            "format": "AIA G701",
            "skip_visual_qc": True,
        },
        ask_first=["Project name?", "Brief description of the extra scope?"],
        context_files=["change-order"],
        voice="owner",
        turnaround="10 min",
    ),

    "send_sms": IntentResult(
        intent="send_sms",
        confidence=1.0,
        pipeline=[
            "compose_sms_body",
            "send_via_twilio",
            "confirm_sent",
        ],
        auto_defaults={
            "owner_sms": "7133001865@vtext.com",
            "joseph_sms": "7139384333@vtext.com",
        },
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "linkedin_post": IntentResult(
        intent="linkedin_post",
        confidence=1.0,
        pipeline=[
            "select_format_A_B_C_D",
            "draft_post_with_portfolio_facts",
            "fingerprint_check",
            "preview_for_approval",
        ],
        auto_defaults={
            "voice": "owner",
            "target_words": "150-250",
            "max_hashtags": 3,
        },
        ask_first=["the Owner's voice or Joseph's?"],
        context_files=["linkedin-content", "brand-voice"],
        voice="owner",
        turnaround="3-5 min",
    ),

    "run_diagnostics": IntentResult(
        intent="run_diagnostics",
        confidence=1.0,
        pipeline=[
            "run_bridge_diagnostics",
            "run_calculator_diagnostics",
            "run_dispatcher_diagnostics",
            "run_harness_diagnostics",
            "run_aisc_diagnostics",
            "build_diagnostic_report",
        ],
        auto_defaults={"suites": "all"},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),

    "generate_3d_model": IntentResult(
        intent="generate_3d_model",
        confidence=1.0,
        pipeline=[
            "parse_shape_or_extract_from_file",
            "generate_stl_model",
            "deliver_stl_file",
        ],
        auto_defaults={},
        ask_first=[],
        context_files=[],
        voice="joseph",
        turnaround="immediate",
    ),
}


# ── Classification Engine ─────────────────────────────────────────────

def classify_intent(message: str) -> IntentResult:
    """Classify the Owner's message into a pipeline.

    Returns the best-matching IntentResult. If no match, returns
    an "unknown" result that prompts a single clarifying question.
    """
    msg_lower = message.lower().strip()

    # ── Shape lookup (regex, not trigger list) ────────────────────────
    if _SHAPE_PATTERN.search(message):
        result = _PIPELINES["shape_lookup"]
        result.confidence = 0.95
        return result

    # Exact and substring matching against trigger phrases
    best_match = None
    best_score = 0.0

    for triggers, intent_name in _TRIGGERS:
        for trigger in triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in msg_lower:
                # Score by specificity (longer match = better)
                score = len(trigger_lower) / max(len(msg_lower), 1)
                # Boost exact matches
                if msg_lower == trigger_lower:
                    score = 1.0
                # Boost if message starts with trigger
                if msg_lower.startswith(trigger_lower):
                    score = min(score * 1.5, 0.99)

                if score > best_score:
                    best_score = score
                    best_match = intent_name

    if best_match and best_match in _PIPELINES:
        result = _PIPELINES[best_match]
        result.confidence = round(min(best_score + 0.3, 1.0), 2)
        return result

    # No match: return unknown
    return IntentResult(
        intent="unknown",
        confidence=0.0,
        pipeline=["ask_one_clarifying_question"],
        auto_defaults={},
        ask_first=["Two ways to read this. (A) {option}. (B) {option}. Which?"],
        context_files=[],
        voice="owner",
        turnaround="depends",
    )


def get_auto_defaults() -> dict:
    """Return the full auto-defaults dictionary for reference.

    These apply silently to every bid unless overridden.
    """
    return {
        # Scope defaults
        "deck": "in_scope_always",
        "erection": "in_scope_per_ton",
        "shop_drawings": "included_2_3_wks",
        "engineering": "folded_into_fab_erection",
        "anchor_bolt_furnishing": "in_scope_when_structural",
        "cfmf": "excluded_csi_05_4000",
        "tapered_plate": "excluded",
        "alloy_modules": "excluded",
        "asme_vessels": "excluded",
        "janus_self_storage": "excluded_csi_10_51_13",

        # Pricing defaults
        "rates": "locked_q2_2026",
        "drawing_stage_adder": "auto_detect",
        "small_project_override": "auto_detect_under_200k",

        # Payment defaults
        "payment": "30_20_50_locked",
        "sov": "itemized_aia_g702_g703",
        "cash_flow_validation": "mandatory",

        # Document defaults
        "format": "pdf_only",
        "two_pdfs": True,
        "template": "format_v1_locked",
        "bid_validity": "30_days",

        # Voice defaults
        "client_signature": "Owner Steel",
        "legal_signature": "The Owner",
        "capabilities_close": "All work performed in-house per AISC/AWS/SJI/OSHA standards.",

        # Timeline defaults
        "shop_drawings_lead": "2-3 wks",
        "joist_fab_lead": "2-3 wks",
        "delivery_lead": "3-4 wks",
        "deck_lead": "3-4 wks from PO",
        "anchor_rod_lead": "10-14 days from AB plan",

        # Forbidden defaults (never apply silently)
        "porsche_plano": "FORBIDDEN",
        "est_2017": "FORBIDDEN_without_confirmation",
        "headcount": "FORBIDDEN",
        "supplier_names": "FORBIDDEN",
        "pe_names": "FORBIDDEN",
        "40_20_40": "DEAD",
        "alamo_heights": "DEAD",
        "14_16_wk_fab": "COMPETITOR_NUMBER",
    }


def list_intents() -> list[dict]:
    """List all recognized intents for display."""
    return [
        {
            "intent": name,
            "triggers": [t for triggers, n in _TRIGGERS if n == name for t in triggers][:5],
            "pipeline_length": len(result.pipeline),
            "turnaround": result.turnaround,
        }
        for name, result in _PIPELINES.items()
    ]


# ── Skill-Intent mapping ─────────────────────────────────────────────
# Maps intent names to skills that should be loaded for that intent.

INTENT_SKILLS: dict[str, list[str]] = {
    "full_bid_pipeline": ["drawing-reading", "bid-pricing", "bid-compliance", "proposal-format"],
    "generate_proposal_from_pipeline": ["bid-pricing", "proposal-format", "bid-compliance"],
    "small_project_override": ["bid-pricing"],
    "bid_review_against_rules": ["bid-compliance", "bid-pricing"],
    "designer_pdf_edit": ["proposal-format"],
    "drawings_uploaded": ["drawing-reading"],
    "compose_email": ["email-voice"],
    "strategic_advisory": ["email-voice"],
    "field_issue": ["drawing-reading"],
    "compliance_check": ["isnetworld-ravs", "bid-compliance"],
    "shape_lookup": ["bid-pricing"],
    "linkedin_post": ["linkedin-content", "brand-voice"],
}


def get_skills_for_intent(intent_name: str) -> list[str]:
    """Return which skills should be loaded for a given intent.

    Used by the system prompt builder to inject only the skills
    relevant to the current task.
    """
    return INTENT_SKILLS.get(intent_name, [])


# ── v3.5.2 creative intent families ──────────────────────────────────

CREATIVE_INTENTS: list[dict] = [
    {
        "name": "score_this_bid",
        "triggers": ["score", "grade", "rate this bid", "how good", "quality check",
                     "scorecard", "letter grade"],
        "pipeline": [
            "Run bid scorecard on the current proposal",
            "Return grade (A-F), score, deductions, recommendations",
            "If grade is D or F: block output, list fixes",
        ],
        "skills": ["bid-compliance", "bid-pricing", "proposal-format"],
    },
    {
        "name": "write_scope",
        "triggers": ["scope narrative", "scope text", "write the scope",
                     "project scope", "scope section"],
        "pipeline": [
            "Read takeoff members from pipeline state",
            "Generate scope narrative from actual data",
            "Insert into proposal template scope section",
        ],
        "skills": ["drawing-reading", "proposal-format"],
    },
    {
        "name": "generate_followups",
        "triggers": ["follow up", "follow-up emails", "followup sequence",
                     "chase email", "bid follow"],
        "pipeline": [
            "Read project + GC from pipeline state",
            "Generate 3-email sequence (day 3/7/14)",
            "Schedule reminders in calendar",
        ],
        "skills": ["email-voice"],
    },
    {
        "name": "log_bid_outcome",
        "triggers": ["we won", "we lost", "bid result", "outcome", "awarded",
                     "not awarded", "went with someone else"],
        "pipeline": [
            "Extract project and outcome from message",
            "Log to bid_history table",
            "Return updated win rate and stats",
        ],
        "skills": ["bid-pricing"],
    },
    {
        "name": "compare_to_history",
        "triggers": ["how does this compare", "historical", "past bids",
                     "vs average", "benchmark this"],
        "pipeline": [
            "Query bid_history for comparable bids",
            "Compare $/ton against average",
            "Flag if >15% above or below",
        ],
        "skills": ["bid-pricing"],
    },
    {
        "name": "value_engineer",
        "triggers": ["ve", "value engineer", "over budget", "too expensive",
                     "reduce cost", "lighter", "cut weight"],
        "pipeline": [
            "Read members from pipeline state",
            "Suggest lighter shapes with savings",
            "Show total potential savings vs budget gap",
        ],
        "skills": ["bid-pricing", "drawing-reading"],
    },
    {
        "name": "revision_diff",
        "triggers": ["revised drawings", "new set", "addendum", "revision",
                     "what changed", "rev", "ase"],
        "pipeline": [
            "Run takeoff on new drawings",
            "Compare against previous takeoff",
            "Generate addendum with price delta",
        ],
        "skills": ["drawing-reading", "bid-pricing"],
    },
]

# Update INTENT_SKILLS with creative intents
for ci in CREATIVE_INTENTS:
    INTENT_SKILLS[ci["name"]] = ci["skills"]
