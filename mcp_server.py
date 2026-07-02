#!/usr/bin/env python3
"""
Your Company Virtual Office - MCP Server for Claude Desktop App

Model Context Protocol server that exposes the Virtual Office's
bridge methods as tools the Owner's Claude app can call.

Owner says: "What's my bid pipeline look like?"
Claude app calls: tools/call → get_bid_pipeline
MCP server calls: Bridge().get_pipeline()
Result flows back through Claude → natural language answer

Setup: Add to %APPDATA%\\Claude\\claude_desktop_config.json:
{
  "mcpServers": {
    "your-company-office": {
      "command": "python",
      "args": ["C:\\\\YourCompany\\\\virtualoffice\\\\mcp_server.py"],
      "env": {}
    }
  }
}

Protocol: JSON-RPC 2.0 over stdio
"""

import sys, json, traceback
from pathlib import Path

# Add virtualoffice to path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))


# ═══ MCP TOOL DEFINITIONS ══════════════════════════════════════════
# These are the tools the Owner's Claude app can call.
# Each tool maps to a Bridge method.

# ═══ LEGACY 72-TOOL SURFACE ════════════════════════════════════════
# v3.5.6: This list is preserved per the Owner's directive - when MCP_MODE
# is "both" (default) or "legacy", these 72 tools register exactly as
# they did pre-consolidation. GUI mode (python main.py without --mcp-server)
# does not use this list at all; it calls Bridge methods directly.

LEGACY_MCP_TOOLS = [
    # ── Morning Brief & Dashboard ──
    {
        "name": "get_morning_brief",
        "description": "Get the unified morning intelligence brief - steel prices, Houston pipeline, compliance, blockers, bids, shop floor, system health. the Owner's daily executive summary.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_agent_health",
        "description": "Health check across all 5 AI agents (Steel Price, Houston Pipeline, Compliance, Ledger, Field Vision) plus cost comparison showing $47K+ annual savings.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_self_test",
        "description": "Run the full system self-test across all 70 modules. Returns pass/fail for each module.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },

    # ── Bid Pipeline ──
    {
        "name": "get_pipeline",
        "description": "Get the current bid pipeline - all bids with status (SCANNED/REVIEWING/PURSUING/SUBMITTED/WON/LOST/PASSED).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compose_full_bid",
        "description": "Run the full autonomous bid composition chain: analyze -> spec -> takeoff -> price -> comply -> estimate -> propose -> hash -> email. RENDERING: The result includes _files with download links for the client proposal PDF and the internal GP report PDF (served via /files/ endpoint through the tunnel). If _images are present, display drawing overlays inline. Always show the summary (tonnage, member count, total bid, GP margin) as text before the downloads.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bid_text": {"type": "string", "description": "The bid invitation email text or scope description"},
                "pdf_path": {"type": "string", "description": "Path to structural drawing PDF (desktop use)"},
                "content_base64": {"type": "string", "description": "Base64-encoded PDF bytes (claude.ai browser use)"},
                "project_name": {"type": "string", "description": "Project name (optional - auto-detected from text)"},
                "gc_company": {"type": "string", "description": "General contractor name"},
            },
            "required": ["bid_text"],
        },
    },
    {
        "name": "run_compliance_check",
        "description": "Run the 6-gate compliance pre-flight for a project: ISN, DISA, EMR, AISC, AWS D1.1, Special Inspector.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project name to check compliance for"},
            },
            "required": [],
        },
    },

    # ── Steel Prices ──
    {
        "name": "get_latest_steel_prices",
        "description": "Get the latest steel prices from all free sources: FRED PPI, CME HRC futures, AISI utilization, and service-center quotes.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_best_steel_price",
        "description": "Find the best current price for a steel shape type across all service-center suppliers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {"type": "string", "description": "Shape type: W, HSS, L, C, PL, etc.", "default": "W"},
            },
            "required": [],
        },
    },

    # ── Houston Pipeline ──
    {
        "name": "get_project_pipeline",
        "description": "Get the Houston EPC project pipeline - 25+ tracked mega-projects with AI-scored capability match.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: announced/permitting/construction/tracking"},
            },
            "required": [],
        },
    },

    # ── Compliance ──
    {
        "name": "get_ravs_scorecard",
        "description": "Get the ISN-equivalent compliance scorecard (15 RAVS categories, A-F grade).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_expiring_certs",
        "description": "Check certificates and COIs expiring within N days.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days ahead to check", "default": 30},
            },
            "required": [],
        },
    },

    # ── Estimating ──
    {
        "name": "get_calibrated_estimate",
        "description": "Get a calibrated steel estimate using Your Company's actual performance data (or industry baselines if < 3 completed projects).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tonnage": {"type": "number", "description": "Estimated tonnage"},
                "project_type": {"type": "string", "description": "commercial/industrial/warehouse/church", "default": "commercial"},
            },
            "required": ["tonnage"],
        },
    },

    # ── Shop Floor ──
    {
        "name": "get_production_board",
        "description": "Real-time production board - where is every piece in the shop? Shows station-by-station status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Filter by project name (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "log_production",
        "description": "Log daily production: 'log 47 tons erected today ICD 6-man crew'. Voice-friendly.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "tons_fabricated": {"type": "number", "default": 0},
                "tons_erected": {"type": "number", "default": 0},
                "pieces_completed": {"type": "integer", "default": 0},
                "crew_size": {"type": "integer", "default": 0},
                "hours_worked": {"type": "number", "default": 0},
            },
            "required": ["project"],
        },
    },

    # ── Project Controls (PC4+PC5) - CONFIDENTIAL - INTERNAL, never client-facing ──
    {
        "name": "get_spi_cpi",
        "description": "SPI/CPI per WBS line for an awarded project (earned/planned, earned/actual; flag below 0.95) plus the S-curve series. Reads the PC3 progress log and the PC1 frozen baseline. CONFIDENTIAL - INTERNAL, never client-facing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Awarded project code, e.g. PRJ-2026-ACP-001"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_forecast_to_complete",
        "description": "Forecast at completion per WBS line rolled to project level, checked against the Section 07 control limits (investigate outside -1.7/+7.3 percent). CONFIDENTIAL - INTERNAL, never client-facing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Awarded project code, e.g. PRJ-2026-ACP-001"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_variance_by_cost_code",
        "description": "Cost and schedule variance grouped by cost code for an awarded project; client-caused lines carry the contract-admin notice note (PC6). CONFIDENTIAL - INTERNAL, never client-facing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Awarded project code, e.g. PRJ-2026-ACP-001"},
            },
            "required": ["project_id"],
        },
    },

    # ── Cash Flow ──
    {
        "name": "get_cash_flow_projection",
        "description": "30/60/90 day cash flow projection with recommendations. Flags cash-negative dates and LOC draw triggers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bank_balance": {"type": "number", "description": "Current bank balance", "default": 0},
                "monthly_overhead": {"type": "number", "default": 45000},
            },
            "required": [],
        },
    },

    # ── Knowledge Graph ──
    {
        "name": "knowledge_query",
        "description": "Cross-entity search: 'show me everything about Marathon' returns bids, contacts, blockers, conversations, audit trail, compliance status - all from one query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Entity name or keyword to search across all modules"},
            },
            "required": ["query"],
        },
    },

    # ── Financial ──
    {
        "name": "get_financial_dashboard",
        "description": "Financial dashboard - revenue, COGS, gross profit, overhead, net income from the local construction ledger.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_ar_aging",
        "description": "Accounts receivable aging report - current, 30-day, 60-day, 90+ buckets.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },

    # ── v3.2: Q2 2026 Calibration Block (Houston-MSA market reference) ──
    {
        "name": "get_calibration_summary",
        "description": "Q2 2026 calibration metadata: version, issued date, valid_through, and counts for all 13 sections (wage_trades, wc_codes, steel_grades, refineries, etc.). Use to verify market data freshness.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_wage_rate",
        "description": "SAM.gov WD-2026 Houston-MSA wage. Trades: 'Welder (CWI-supervised) - Journeyman', 'Ironworker (structural) - Journeyman', 'Crane Operator (NCCCO) - Journeyman', 'Project Manager', etc. Tier: base_wage|fringe|fully_burdened_rate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "trade": {"type": "string", "description": "Full trade name; empty returns all 10 trades"},
                "tier":  {"type": "string", "enum": ["base_wage","fringe","fully_burdened_rate"], "default": "fully_burdened_rate"},
            },
            "required": [],
        },
    },
    {
        "name": "get_steel_price",
        "description": "Q2 2026 Houston-MSA steel pricing per ton (SteelBenchmarker / Argus / Nucor 90-day avg). Grades: 'Wide-flange shapes (W-sections, A992)', 'Plate (A36, 1/4\" to 2\")', 'HRC (Hot-Rolled Coil)', 'Rebar (#4-#8, A615 Gr 60)', etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "grade": {"type": "string", "description": "Full grade name; empty returns all 9 grades"},
                "tier":  {"type": "string", "enum": ["low","typical","high"], "default": "typical"},
            },
            "required": [],
        },
    },
    {
        "name": "get_wc_rate",
        "description": "NCCI Texas Workers Comp rate per $100 payroll. Codes: 5040 (Iron/Steel Erection frame), 5057 (Iron/Steel Erection NOC), 5102 (shop fab), 3030 (steel fabricating), 5403, 8810, 7380.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ncci_code": {"type": "integer", "default": 5040},
                "exp_mod":   {"type": "string", "enum": ["low","typical","high"], "default": "typical"},
            },
            "required": [],
        },
    },
    {
        "name": "get_permit_fee",
        "description": "Compute Houston-area permit fee at a given project value. Jurisdictions: 'City of Houston', 'Harris County', 'TDI (Windstorm)', 'City of Pasadena', 'City of Baytown', 'City of Deer Park', 'Galveston County'. Returns base + variable + total.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jurisdiction":  {"type": "string", "default": "City of Houston"},
                "project_value": {"type": "number", "description": "Project value in USD", "default": 0},
            },
            "required": [],
        },
    },
    {
        "name": "get_macro_indicators",
        "description": "7 Houston macro indicators (BLS/EIA/GHBA/Baker Hughes May 2026): construction employment, building permits, WTI crude, Henry Hub gas, TX rig count, industrial vacancy, TX sales tax. Each has value, trend_12mo, implication.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_connection_cost",
        "description": "Houston 2026-adjusted connection cost. Types: 'Welded moment connection (CJP)', 'Bolted moment connection (End-plate)', 'Bolted shear connection (Single-plate)', 'Gusset plate (Brace)', 'Base plate w/ 4 anchor rods', etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "connection_type": {"type": "string", "description": "Empty returns all 10 connection types"},
                "tier":            {"type": "string", "enum": ["low_cost","typical_cost","high_cost"], "default": "typical_cost"},
            },
            "required": [],
        },
    },

    # ── v3.2: Operations Agents ──
    {
        "name": "get_panel_data",
        "description": "Highest-signal call: returns full priorities panel (4 active items), recommended bids (2-3), KPIs, compliance blockers, and AR alerts in one shot. Equivalent to a morning brief.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_ar_status",
        "description": "Accounts receivable: invoices, milestones (30/20/50), alerts (PENDING/APPROACHING/DUE_TODAY/WARNING/ESCALATION), TX Property Code §28 1.5%/mo interest accruals.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_name": {"type": "string", "default": ""}},
            "required": [],
        },
    },
    {
        "name": "get_change_orders",
        "description": "All change orders for a project (or all). Auto-numbered CO-PROJ-NNN with 22% default markup. Shows DRAFT/SUBMITTED/ACCEPTED status.",
        "inputSchema": {
            "type": "object",
            "properties": {"project_name": {"type": "string", "default": ""}},
            "required": [],
        },
    },
    {
        "name": "get_rfis",
        "description": "List RFIs filtered by project or overdue-only. Returns rfi_number, question, csi_division, due_date, status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "default": ""},
                "overdue_only": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "draft_refinery_outreach",
        "description": "PREVIEW-ONLY: draft a cold outreach to a Houston refinery. Always returns a preview - never sends or writes to outreach_log. Owner must approve via confirm_refinery_outreach in the desktop app. Requires all 5 inputs (5-input rule).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "company":       {"type": "string", "description": "Refinery name (e.g. 'Marathon Petroleum Galveston Bay')"},
                "contact_name":  {"type": "string"},
                "contact_role":  {"type": "string"},
                "hook":          {"type": "string", "description": "What we offer (e.g. 'Q3 2026 turnaround structural steel')"},
                "timing_reason": {"type": "string", "description": "Why now (e.g. '24-week lead time per their TA schedule')"},
            },
            "required": ["company","contact_name","contact_role","hook","timing_reason"],
        },
    },
    {
        "name": "lookup_aisc_member",
        "description": "Look up a structural steel shape in the AISC catalog. Returns lb/ft, depth, flange width, web thickness. Pure offline CSV lookup - no LLM. Examples: W14X82, W21X44, HSS6X6X1/4, L4X4X3/8.",
        "inputSchema": {
            "type": "object",
            "properties": {"designation": {"type": "string", "description": "AISC shape designation"}},
            "required": ["designation"],
        },
    },
    {
        "name": "generate_3d_view",
        "description": "Generate a 3D STL model of an AISC steel shape. Returns base64-encoded STL (stl_b64), weight, and section properties. Pure offline geometry from AISC CSV data - no LLM. RENDERING: When displaying this result, create a Three.js artifact with STLLoader, OrbitControls, and a light gray MeshStandardMaterial. Load the STL from the stl_b64 field (base64 decode to ArrayBuffer). Add a GridHelper and soft directional lighting. The user should be able to orbit, zoom, and pan the model. Show weight and dimensions as an overlay label.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {"type": "string", "description": "AISC shape designation (e.g. W14X82, W21X44)"},
                "length_ft": {"type": "number", "description": "Member length in feet (default 20)"},
                "count": {"type": "integer", "description": "Number of members (default 1)"},
            },
            "required": ["shape"],
        },
    },
    {
        "name": "run_self_test",
        "description": "Run the 72-check system self-test (data fabric, domain engine, agents, calibration). Returns pass/fail counts and failure details. Use for health checks before bid pushes.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },

    # ── v3.2: MCP routing diagnostics (cost-split visibility) ──
    {
        "name": "mcp_status",
        "description": "Returns MCP integration health: which Claude Desktop MCP servers are registered, which integration categories (email/calendar/drive/etc.) are routable through the Owner's subscription instead of Joseph's API, and the cost-split summary. Use to verify the dual-account architecture is working.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "mcp_prefer_routing",
        "description": "Asks: 'For category X (email|calendar|drive|docs|sheets|slack|github|filesystem|browser|search), should we route through Claude Desktop MCP or fall back to Joseph's API?' Returns the matching server name if MCP-routable, else api_fallback.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["email","calendar","drive","docs","sheets","slack","github","filesystem","browser","search"]},
            },
            "required": ["category"],
        },
    },

    # ── v3.3: Bid document filing + auto-process drawing ──
    {
        "name": "auto_process_drawing",
        "description": "Auto-pipeline triggered when a structural drawing PDF is dropped. Extracts members locally (no LLM math), matches AISC database for verified weights, generates 3D STL, saves takeoff under Documents/Your Company Bids/. Returns member count, verified tonnage, draft estimate. RENDERING: If the result contains _images, display each as an inline image (these are drawing overlays showing extracted members marked up on the original sheet). If the result contains _files, provide download links. If stl_b64 is present, render a Three.js 3D model artifact. Run this BEFORE any bid pricing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_path":       {"type": "string", "description": "Absolute path to the drawing PDF (desktop use)"},
                "content_base64": {"type": "string", "description": "Base64-encoded PDF bytes (claude.ai browser use - pass this instead of pdf_path when the file was uploaded through the web interface)"},
                "bid_number":     {"type": "string", "description": "Optional - auto-suggested if omitted"},
                "project_name":   {"type": "string", "description": "Optional - used in folder name"},
            },
            "required": [],
        },
    },
    {
        "name": "save_bid_artifact",
        "description": "Save a generated bid artifact (proposal PDF, internal estimate, chat log) to Documents/Your Company Bids/YYYY-MM/<bid_number>/. Pass content_b64 for binary or content_text for plain text. Returns the saved path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bid_number":   {"type": "string"},
                "filename":     {"type": "string", "description": "e.g. proposal.pdf, internal_estimate.pdf"},
                "content_b64":  {"type": "string", "description": "base64-encoded bytes for binary files"},
                "content_text": {"type": "string", "description": "raw text for .json/.md/.txt artifacts"},
                "project_name": {"type": "string"},
                "subfolder":    {"type": "string", "description": "Optional subfolder e.g. 'source_drawings'"},
            },
            "required": ["bid_number", "filename"],
        },
    },
    {
        "name": "list_bid_artifacts",
        "description": "List every artifact saved under a bid's folder (proposal, internal estimate, takeoff, 3D model, chat log). Returns metadata for the chat to display 'already saved' badges.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bid_number":   {"type": "string"},
                "project_name": {"type": "string"},
            },
            "required": ["bid_number"],
        },
    },
    {
        "name": "open_bids_folder",
        "description": "Open the Your Company Bids folder in the OS file browser (Explorer on Windows). If bid_number is given, opens that specific bid's subfolder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bid_number":   {"type": "string", "description": "Optional - opens root if omitted"},
                "project_name": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "get_bids_folder",
        "description": "Return the absolute path to the Your Company Bids root folder (creates if missing).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "suggest_bid_number",
        "description": "Suggest the next available bid number for a project (e.g. PRJ-2026-NTH-001). Scans existing folders to find the next sequence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name":  {"type": "string"},
                "location_code": {"type": "string", "description": "Optional 2-4 letter prefix"},
            },
            "required": ["project_name"],
        },
    },
    # ── v3.4.0 tools ──────────────────────────────────────────────────
    {
        "name": "governance_status",
        "description": "Three-tier governance status: compliance rules, CEO preferences, Joseph defaults.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_bid_compliance",
        "description": "Check content against Tier 1 compliance rules. Returns violations list.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Text content to check"},
                "context": {"type": "string", "description": "Context: bid, email, marketing"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "session_boot",
        "description": "Run session boot: load OneDrive standing files, governance, vault context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force_refresh": {"type": "boolean", "description": "Force re-boot even if cached"},
            },
            "required": [],
        },
    },
    {
        "name": "review_bid_ssp",
        "description": "4-section bid review from Steel Suite Pro export. Paste SSP data for scope, weight, cost, and risk analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ssp_text": {"type": "string", "description": "Raw SSP export text (CSV, table, or clipboard)"},
                "project_name": {"type": "string"},
                "complexity": {"type": "string", "description": "simple/standard/complex/heavy/retrofit"},
                "margin_pct": {"type": "number", "description": "Target margin (default 0.18)"},
            },
            "required": ["ssp_text"],
        },
    },
    {
        "name": "vault_sync_status",
        "description": "Cross-platform Obsidian vault sync status. Shows which platforms have synced.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # ── v3.4.3 tools ──────────────────────────────────────────────────
    {
        "name": "run_pdf_qc",
        "description": "Run the Owner's 6 visual QC rules on a generated PDF. Call with was_rendered=True after visual inspection to clear R-01 gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string", "description": "Path to the PDF file"},
                "was_rendered": {"type": "boolean", "description": "True if the PDF has been visually inspected"},
            },
            "required": ["pdf_path"],
        },
    },
    {
        "name": "get_pdf_qc_rules",
        "description": "List all 6 PDF visual QC rules (R-01 through R-06).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # ── v3.4.6 tools ──────────────────────────────────────────────────
    {
        "name": "classify_intent",
        "description": "Classify the Owner's shorthand into a full pipeline. Returns intent, steps, auto-defaults, and which files to load.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "the Owner's message to classify"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "get_auto_defaults",
        "description": "Return all auto-defaults that apply silently to every bid (scope, pricing, payment, voice, timeline).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_intents",
        "description": "List all recognized intent triggers and their pipeline definitions.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # ── v3.5.2 tools ──────────────────────────────────────────────────
    {
        "name": "mail_scanner_status",
        "description": "Get M365 mail scanner status: configured, running, mailbox being monitored.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gdrive_sync_status",
        "description": "Get Google Drive sync status: tracked files, config state, page token.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gdrive_pull",
        "description": "Pull new/changed files from Google Drive to local vault.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "gdrive_push",
        "description": "Push a local file to Google Drive.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local file path to push"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_sentry_release",
        "description": "Get the current Sentry release tag (steel-office@X.Y.Z).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # ── v3.5.2 skill + harness tools ──────────────────────────────────
    {
        "name": "list_skills",
        "description": "List all available operational skills (frontmatter only). Skills are progressive-disclosure: metadata loads first, full body loads on demand.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "load_skill",
        "description": "Load full skill body (~2K tokens). Use after list_skills identifies the right skill for the task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Skill name (e.g., 'drawing-reading', 'bid-pricing')"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "match_skill",
        "description": "Find the best matching skill for a message. Returns skill metadata if matched.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to match against skill triggers"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "run_bid_harness",
        "description": "Run the bid pipeline regression harness. Validates the full 17-step pipeline contract, auto-defaults, and forbidden items.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_voice",
        "description": "Check text against the Owner's 10 voice rules (em-dashes, AI openers, buzzwords, tilde quantities, etc.). Returns pass/fail with violations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to check for voice rule violations"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "run_compliance_attacks",
        "description": "Run 60+ attack phrases through the compliance scanner. Returns accuracy score and any gaps.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    # ── v3.5.2: Creative competitive-edge tools ───────────────────────
    {
        "name": "score_bid",
        "description": "Score a bid proposal A-F on a 100-point scale. Categories: Compliance (40), Voice (20), Pricing (25), Format (15). Returns grade, deductions, and recommendations.",
        "inputSchema": {"type": "object", "properties": {
            "proposal_text": {"type": "string", "description": "Full proposal text to check"},
            "tonnage": {"type": "number", "description": "Project tonnage from takeoff"},
            "total_bid": {"type": "number", "description": "Total bid amount in dollars"},
            "deck_sf": {"type": "number", "description": "Deck square footage if applicable"},
            "pdf_path": {"type": "string", "description": "Path to proposal PDF for format QC"},
            "template": {"type": "string", "description": "Template name (STANDARD, INDUSTRIAL, TILTUP)"},
        }, "required": []},
    },
    {
        "name": "generate_scope_narrative",
        "description": "Generate project-specific scope text from actual takeoff data. No boilerplate. Every sentence grounded in real member counts and tonnage.",
        "inputSchema": {"type": "object", "properties": {
            "members": {"type": "string", "description": "JSON array of {shape, qty, type} dicts from takeoff"},
            "tonnage": {"type": "number"},
            "deck_sf": {"type": "number"},
            "building_type": {"type": "string", "description": "conventional, tilt-up, or pemb"},
            "project_name": {"type": "string"},
            "drawing_stage": {"type": "string", "description": "IFC, DD, Budget, or SD"},
        }, "required": ["members"]},
    },
    {
        "name": "generate_followup_sequence",
        "description": "Auto-generate a 3-email follow-up sequence (day 3/7/14) in the Owner's voice with project-specific details.",
        "inputSchema": {"type": "object", "properties": {
            "project_name": {"type": "string"},
            "gc_name": {"type": "string"},
            "gc_company": {"type": "string"},
            "bid_total": {"type": "number"},
            "tonnage": {"type": "number"},
            "bid_date": {"type": "string", "description": "YYYY-MM-DD"},
            "bid_number": {"type": "string"},
        }, "required": ["project_name", "gc_name"]},
    },
    {
        "name": "bid_history_log",
        "description": "Log a bid outcome (won/lost/pending) for historical learning. Builds win/loss patterns over time.",
        "inputSchema": {"type": "object", "properties": {
            "project_name": {"type": "string"},
            "gc_company": {"type": "string"},
            "tonnage": {"type": "number"},
            "total_bid": {"type": "number"},
            "outcome": {"type": "string", "description": "won, lost, pending, or no_bid"},
            "notes": {"type": "string"},
        }, "required": ["project_name"]},
    },
    {
        "name": "bid_history_compare",
        "description": "Compare a new bid against historical data. Shows how this bid's $/ton stacks up against past bids, GC-specific history, and win rate.",
        "inputSchema": {"type": "object", "properties": {
            "tonnage": {"type": "number"},
            "total_bid": {"type": "number"},
            "gc_company": {"type": "string"},
            "building_type": {"type": "string"},
        }, "required": ["tonnage", "total_bid"]},
    },
    {
        "name": "ve_suggestions",
        "description": "Value engineering suggestions when a bid exceeds budget. Suggests lighter shapes with tonnage and cost savings.",
        "inputSchema": {"type": "object", "properties": {
            "members": {"type": "string", "description": "JSON array of {shape, qty, type} dicts"},
            "budget": {"type": "number", "description": "Target budget in dollars"},
            "current_total": {"type": "number", "description": "Current bid total"},
        }, "required": ["members"]},
    },
    {
        "name": "drawing_revision_diff",
        "description": "Compare two takeoffs to detect scope changes from revised drawings. Returns added/removed/changed members with price delta.",
        "inputSchema": {"type": "object", "properties": {
            "old_members": {"type": "string", "description": "JSON array from original takeoff"},
            "new_members": {"type": "string", "description": "JSON array from revised takeoff"},
        }, "required": ["old_members", "new_members"]},
    },
    # ── v3.5.2: Gemini-report-driven tools ────────────────────────────
    {
        "name": "validate_shapes",
        "description": "AISC Validation Gate. Validates AI-extracted shapes against AISC v16.0 database. Catches hallucinations like 'W14X81' and suggests 'W14X82'.",
        "inputSchema": {"type": "object", "properties": {
            "members": {"type": "string", "description": "JSON array of {shape, qty, length_ft} dicts"},
        }, "required": ["members"]},
    },
    {
        "name": "hash_drawing_pages",
        "description": "Hash each page of a PDF drawing set. Used to detect which pages changed between revisions.",
        "inputSchema": {"type": "object", "properties": {
            "pdf_path": {"type": "string", "description": "Path to PDF drawing file"},
        }, "required": ["pdf_path"]},
    },
    {
        "name": "compare_drawing_revisions",
        "description": "Compare two PDF drawing sets page-by-page. Only changed pages need re-processing through vision AI. Saves API costs.",
        "inputSchema": {"type": "object", "properties": {
            "old_pdf": {"type": "string", "description": "Path to original PDF"},
            "new_pdf": {"type": "string", "description": "Path to revised PDF"},
        }, "required": ["old_pdf", "new_pdf"]},
    },
    {
        "name": "aisc_mass_balance",
        "description": "Compare AI-extracted tonnage against calculated tonnage from member list. Flags missing members if gap exceeds 5%.",
        "inputSchema": {"type": "object", "properties": {
            "extracted_tonnage": {"type": "number", "description": "Tonnage from AI extraction"},
            "members": {"type": "string", "description": "JSON array of {shape, qty, length_ft} dicts"},
        }, "required": ["extracted_tonnage", "members"]},
    },

    # ── Phase 2: Slash Commands (/intake-bid through /approvals) ─────
    {
        "name": "intake_bid",
        "description": "/intake-bid: Intake a bid invite from Cowork or MCP. Creates a 9-folder project structure with CLAUDE.md routing map and adds the bid to the pipeline. Pass project_name plus any available details.",
        "inputSchema": {"type": "object", "properties": {
            "invite_text": {"type": "string", "description": "Free-text bid invitation to parse"},
            "invite_json": {"type": "string", "description": "JSON string with bid fields"},
            "project_name": {"type": "string", "description": "Project name"},
            "gc_company": {"type": "string", "description": "General contractor company"},
            "gc_contact_email": {"type": "string", "description": "GC contact email"},
            "location": {"type": "string", "description": "Project location"},
            "deadline": {"type": "string", "description": "Bid deadline"},
            "estimated_value": {"type": "string", "description": "Estimated project value"},
            "tonnage": {"type": "string", "description": "Estimated steel tonnage"},
            "notes": {"type": "string", "description": "Additional notes"},
            "source": {"type": "string", "description": "Source of intake (cowork, email, manual)"},
        }, "required": []},
    },
    {
        "name": "process_drawing",
        "description": "/takeoff: Run automated drawing takeoff on a structural PDF. Extracts member shapes, quantities, tonnage, and deck area.",
        "inputSchema": {"type": "object", "properties": {
            "pdf_path": {"type": "string", "description": "Path to structural drawing PDF"},
            "project_name": {"type": "string", "description": "Project name for output labeling"},
            "content_base64": {"type": "string", "description": "Base64-encoded PDF bytes (browser use)"},
        }, "required": []},
    },
    {
        "name": "generate_proposal",
        "description": "/price-bid: Generate client proposal PDF and internal GP report from a bid. Returns download links for both PDFs.",
        "inputSchema": {"type": "object", "properties": {
            "bid_id": {"type": "integer", "description": "Pipeline bid ID"},
            "tonnage": {"type": "number", "description": "Steel tonnage from takeoff"},
            "members": {"type": "string", "description": "JSON array of member dicts from takeoff"},
            "project_name": {"type": "string"},
            "gc_company": {"type": "string"},
        }, "required": []},
    },
    {
        "name": "generate_gp",
        "description": "/gp-only: Generate the internal GP report only (no client proposal). Use when pricing changes but the client PDF is already sent.",
        "inputSchema": {"type": "object", "properties": {
            "bid_id": {"type": "integer", "description": "Pipeline bid ID"},
        }, "required": []},
    },
    {
        "name": "compliance_check",
        "description": "/check-compliance: Run compliance cascade and return current status across all 6 gates: ISN, DISA, EMR, AISC, AWS D1.1, Special Inspector.",
        "inputSchema": {"type": "object", "properties": {
            "item_n": {"type": "integer", "description": "Optional: advance a specific compliance item by number"},
            "new_status": {"type": "string", "description": "New status if cascading: OPEN, MONITOR, or OK"},
            "note": {"type": "string", "description": "Optional note for the cascade action"},
        }, "required": []},
    },
    {
        "name": "go_no_go_review",
        "description": "/go-no-go: Composite go/no-go review. Scores the bid 0-100 with factor breakdown, then runs Virtual the Owner's 19-rule review. Returns GO / REVIEW / NO-GO recommendation.",
        "inputSchema": {"type": "object", "properties": {
            "bid_id": {"type": "integer", "description": "Pipeline bid ID"},
            "bid_json": {"type": "string", "description": "JSON string with bid fields (name, tons, bid_total, margin_pct, scope)"},
        }, "required": []},
    },
    {
        "name": "morning_brief",
        "description": "/morning-brief: Get the unified morning intelligence brief - steel prices, Houston pipeline, compliance, blockers, bids, shop floor, system health.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "score_bid_pipeline",
        "description": "/score-bid: Score a bid in the pipeline 0-100 with factor breakdown (risk, GC track record, margin, drawing stage, deadline pressure). Returns score band and suggested action.",
        "inputSchema": {"type": "object", "properties": {
            "bid_id": {"type": "integer", "description": "Pipeline bid ID to score"},
        }, "required": ["bid_id"]},
    },
    {
        "name": "list_bids_active",
        "description": "/list-bids: List active bids in the pipeline (non-terminal states: SCANNED, REVIEWING, PURSUING, SUBMITTED), sorted by score descending.",
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max results (default 25)"},
            "state_filter": {"type": "string", "description": "Filter: active (default), all, won, lost, killed"},
        }, "required": []},
    },
    {
        "name": "pending_approvals",
        "description": "/approvals: List bids awaiting the Owner's review or approval (REVIEWING or PURSUING state). Sorted by score descending.",
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "Max results (default 25)"},
        }, "required": []},
    },
    {
        "name": "prove_variation",
        "description": "/prove-variation: Generate a variation evidence package PDF for a drawing/spec conflict. Reads visual_diff manifest JSON and spec_auditor flags. Returns PDF path and doc number (NC-YYYY-PROJ-NNN-VAR).",
        "inputSchema": {"type": "object", "properties": {
            "conflict_id": {"type": "string", "description": "Conflict identifier (e.g. kzone-001, deck-mismatch-3, member-change-b2)"},
            "project_name": {"type": "string", "description": "Project name"},
            "bid_number": {"type": "string", "description": "Bid number for doc number generation"},
            "member_before": {"type": "string", "description": "AISC member before revision"},
            "member_after": {"type": "string", "description": "AISC member after revision"},
            "spec_flags": {"type": "array", "description": "Spec audit flags from audit_spec_book"},
            "ghost_overlay_path": {"type": "string", "description": "Path to ghost overlay PNG (manifest JSON auto-loaded from same dir)"},
            "cost_delta_usd": {"type": "number", "description": "Estimated cost impact in USD"},
            "location": {"type": "string", "description": "Project location"},
            "output_dir": {"type": "string", "description": "Output directory (default: data/variation_packages)"},
        }, "required": ["conflict_id"]},
    },

    # ── v3.3.2: Project Migration Scanner ─────────────────────────────
    {
        "name": "scan_projects",
        "description": "Pass 1 read-only inventory scan of an existing project directory tree. Returns confirmed project matches, unknown folders, vendor-flagged docs, and file counts. Never writes or copies files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root_dir": {"type": "string", "description": "Absolute path to the directory to scan"},
            },
            "required": ["root_dir"],
        },
    },
]


# ═══ v3.5.6 CONSOLIDATED DISPATCHER MODE ═══════════════════════════
# the Owner's directive: "keep the original set up in place as backup/alternative.
# If the claude app is not running or he uses it in pc without the software
# should continue without claude app utilizing the best alternatives needed."
#
# MCP_MODE controls which surface registers:
#   "both"         - all legacy named tools + 12 dispatchers (default; safest)
#   "consolidated" - only the 12 dispatchers (cleaner Claude Desktop UX)
#   "legacy"       - only the legacy named tools (full backward compat)
#
# GUI mode (python main.py without --mcp-server) calls Bridge methods
# directly via the Flask API and is unaffected by this flag.
import os as _os
MCP_MODE = _os.environ.get("MCP_MODE", "both").lower().strip()
if MCP_MODE not in ("both", "consolidated", "legacy"):
    MCP_MODE = "both"


# ── Dispatcher command maps ──────────────────────────────────────────
# Each entry maps a (command, kwargs) call to a Bridge method name.
# Verified against bridge/api.py - every target method exists. The
# handoff document had ~15 names that did not exist on Bridge; this map
# uses only verified targets. Calculator commands route through the
# module-level run_calc dispatcher in bridge/calculators.py.

_DISPATCHER_MAPS = {
    "bid_pipeline": {
        "add":           "add_bid",
        "get_all":       "get_bid_pipeline",
        "get_one":       "get_bid_detail",
        "update_status": "update_bid_status",
        "advance":       "advance_bid",
        "score":         "score_bid",
        "history_log":   "bid_history_log",
        "history_diff":  "bid_history_compare",
        "compose":       "compose_full_bid",
        "proposal":      "generate_proposal",
        "auto_respond":  "auto_respond_to_bid",
        "leads":         "get_bid_leads",
        "search_inbox":  "search_inbox_for_bid",
    },
    "engineering": {
        "validate_shapes": "validate_shapes",
        "mass_balance":    "aisc_mass_balance",
        "lookup":          "get_aisc_member_info",
        "list_shapes":     "list_steel_shapes",
        "normalize":       "normalize_shape",
        "check_connections": "check_connections",
        "batch_connections": "batch_check_connections",
        "wps_d11_2025":    "check_wps_d11_2025",
    },
    "drawing_intel": {
        "extract":         "extract_drawing_set",
        "rasterize":       "rasterize_drawing_page",
        "hash":            "hash_drawing_pages",
        "compare":         "compare_drawing_revisions",
        "revision_diff":   "drawing_revision_diff",
        "auto_process":    "auto_process_drawing",
        "extract_cad":     "extract_cad_layer",
        "extract_submittals": "extract_submittals",
        "export_tekla":    "export_tekla_xml",
        "export_strumis":  "export_strumis_xml",
        "tier_status":     "get_vision_tier_status",
        "tier_route":      "route_vision_task",
        "tier_reset":      "reset_vision_tier_tracker",
        "auto_v2":         "process_full_takeoff_v2",
        "graph_status":    "get_graph_runner_status",
        "cache_clear":     "clear_vision_cache",
        "memory_search":   "search_project_memory",
        "memory_index":    "index_project",
        "memory_backtest": "backtest_project",
        "memory_status":   "get_memory_status",
        "assembly_costs":  "compute_assembly_costs",
        "monte_carlo":     "run_monte_carlo",
        "conn_weight":     "estimate_connection_weight",
        "grade_compare":   "compare_grades",
        "watchdog_status": "get_watchdog_status",
        "watchdog_config": "configure_watchdog",
        "watchdog_start":  "start_watchdog",
        "watchdog_stop":   "stop_watchdog",
        "watchdog_poll":   "watchdog_poll_now",
        "plan_objective":  "plan_objective",
        "exec_objective":  "execute_objective",
        "calc_pack":       "generate_calc_pack",
        "cnc_stop_list":   "generate_stop_list",
        "cnc_part_dxf":    "generate_part_dxf",
        "cnc_gcode":       "generate_gcode",
        "cnc_dstv":        "generate_dstv",
        "cnc_punch_map":   "generate_punch_map",
        "conn_shear_tab":  "design_shear_tab",
        "conn_base_plate": "design_base_plate",
        "conn_fea":        "verify_connection_fea",
        "value_engineering":"run_value_engineering",
        "cross_verify":    "cross_verify",
        "rfi_log":         "generate_rfi_log",
        "spec_audit":      "audit_spec_book",
        "ghost_overlay":   "ghost_overlay",
        "prove_variation": "prove_variation",
        "capacity_margin": "capacity_adjusted_margin",
        "bc_status":       "check_bc_status",
        "bc_poll":         "poll_bid_invites",
        "piece_status":    "update_piece_status",
        "job_production":  "get_job_production_status",
        "piece_qr":        "generate_piece_qr",
        "photo_qc":        "verify_photo_qc",
        "compare_actuals": "compare_actuals",
        "truck_loads":     "plan_truck_loads",
        "erection_order":  "recommend_erection_order",
        "oh_status":       "get_openhuman_status",
        "oh_memory":       "search_openhuman_memory",
        "oh_register":     "register_openhuman_skill",
        "oh_files":        "get_openhuman_recent_files",
        "detail_vision":   "analyze_connection_details",
        "connection_nodes": "analyze_connection_details",
        "save_correction":  "save_workbench_correction",
        "workbench_data":   "get_workbench_data",
        "correction_summary": "get_correction_summary",
        "full_takeoff":     "process_full_takeoff",
        "quick_estimate":   "quick_bid_estimate",
        "plate_weight":     "calculate_plate_weight",
        "misc_steel":       "estimate_misc_steel",
        "tagged_pdf":       "render_tagged_pdf",
        "learning_cycle":   "run_learning_cycle",
        "learning_status":  "get_learning_status",
        "misc_steel":       "detect_misc_steel",
        "export_misc_tekla": "export_misc_steel_to_tekla",
    },
    "communications": {
        "draft_email":     "draft_email_outlook",
        "send_email":      "send_email_outlook",
        "send_sms":        "send_sms_to_owner",
        "score_email":     "score_email_text",
        "fetch_prices":    "fetch_price_emails",
        "refinery_outreach": "draft_refinery_outreach",
        "confirm_outreach":  "confirm_refinery_outreach",
        "contacts_for_email": "get_contacts_for_email",
        "imessage_to_contact": "send_imessage_to_contact",
        "confirm_imessage":    "confirm_imessage_send",
        "imessage_owner":    "text_owner_imessage",
        "imessage_joseph":     "text_joseph_imessage",
        "log_engagement":      "create_engagement_record",
        "check_engagement":    "check_engagement_record",
        "list_engagements":    "list_engagement_records",
    },
    "compliance": {
        "check":           "run_compliance_check",
        "stats":           "get_compliance_stats",
        "summary":         "get_compliance",
        "blockers":        "get_blockers",
        "run_attacks":     "run_compliance_attacks",
        "bid_compliance":  "check_bid_compliance",
        "isn_scorecard":   "get_isn_scorecard",
        "ravs_scorecard":  "get_ravs_scorecard",
        "expiring_certs":  "check_expiring_certs",
    },
    "creative": {
        "score":           "score_bid",
        "ve":              "ve_suggestions",
        "history_compare": "bid_history_compare",
        "narrative":       "generate_scope_narrative",
        "followup":        "generate_followup_sequence",
        "case_study":      "generate_case_study",
    },
    "quality": {
        "voice":           "check_voice",
        "harness":         "run_bid_harness",
        "pdf_qc":          "run_pdf_qc",
        "pdf_qc_rules":    "get_pdf_qc_rules",
        "scorecard":       "score_bid",
    },
    "vault": {
        "status":          "get_vault_sync_status",
        "sync_prefs":      "vault_sync_preferences",
        "sync_projects":   "vault_sync_projects",
        "sync_session":    "vault_sync_session",
    },
    "orchestration": {
        "verify":          "orchestration_verify",
        "proofread":       "orchestration_proofread",
        "ingest":          "orchestration_ingest",
        "status":          "orchestration_status",
    },
    "infra": {
        "gdrive_status":   "gdrive_sync_status",
        "gdrive_pull":     "gdrive_pull",
        "gdrive_push":     "gdrive_push",
        "sentry_release":  "get_sentry_release",
        "governance":      "get_governance_status",
        "governance_audit": "get_governance_audit",
        "mail_scanner":    "mail_scanner_status",
        "self_test":       "run_self_test",
        "agent_health":    "get_agent_health",
        "morning_brief":   "get_morning_brief",
        "diagnostics":     "run_diagnostics",
    },
}


def _dispatcher_tool_def(name: str, commands: list[str]) -> dict:
    """Build the MCP tools/list entry for a dispatcher."""
    return {
        "name": name,
        "description": (
            f"{name.replace('_', ' ').title()} dispatcher. Use 'command' to "
            f"select an operation; 'args' carries the call arguments. "
            f"Available commands: {', '.join(sorted(commands))}."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "enum": sorted(commands)},
                "args": {"type": "object",
                         "description": "Keyword arguments for the underlying Bridge method."},
            },
            "required": ["command"],
        },
    }


# Calc dispatcher is special: it routes to bridge/calculators.py module-level
# run_calc, not a Bridge method. Commands match the calculator names plus
# a top-level "list" for discovery.
_CALC_TOOL_DEF = {
    "name": "calc",
    "description": (
        "Calculator dispatcher. Routes to bridge/calculators.py via run_calc. "
        "Commands: list (return registry), or a calculator name "
        "(steel_weight, hours_estimate, labor_cost, bid_total, bolt_count, "
        "margin_scenario, crew_size, weld_consumables, plate_weight, "
        "paint_area, trir, days_until, schedule_pressure)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "args": {"type": "object"},
        },
        "required": ["command"],
    },
}

# Util escape hatch - guarantees that anything legacy could do is still
# reachable by name via util.invoke when MCP_MODE=consolidated, even if
# the dispatcher map missed something.
_UTIL_TOOL_DEF = {
    "name": "util",
    "description": (
        "Generic Bridge method invoker. Use ONLY when a specific dispatcher "
        "does not cover the call. command='invoke', method='<bridge_method_name>', "
        "args={...}."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": ["invoke"]},
            "method":  {"type": "string", "description": "Bridge method name to call."},
            "args":    {"type": "object"},
        },
        "required": ["command", "method"],
    },
}


DISPATCHER_TOOLS = (
    [_dispatcher_tool_def(name, list(cmds.keys()))
     for name, cmds in _DISPATCHER_MAPS.items()]
    + [_CALC_TOOL_DEF, _UTIL_TOOL_DEF]
)
# Sanity: 10 named dispatchers + calc + util = 12. Matches handoff spec.
assert len(DISPATCHER_TOOLS) == 12, f"dispatcher count: {len(DISPATCHER_TOOLS)}"


# ── Active tool list resolved at import based on MCP_MODE ────────────
if MCP_MODE == "legacy":
    MCP_TOOLS = list(LEGACY_MCP_TOOLS)
elif MCP_MODE == "consolidated":
    MCP_TOOLS = list(DISPATCHER_TOOLS)
else:  # "both"
    MCP_TOOLS = list(LEGACY_MCP_TOOLS) + list(DISPATCHER_TOOLS)


def _dispatch_call(tool_name: str, command: str, args: dict,
                   method_override: str | None = None) -> dict:
    """Route a dispatcher call to the underlying Bridge method or run_calc.

    Returns a plain dict (not an MCP envelope) - caller wraps it.

    Errors return {"ok": False, "error": ..., "available": [...]} so
    Claude can see what commands exist when it picks a wrong one.
    """
    # vj: parity-ok (auto-applied pass 10f; audit return shape later)
    args = args or {}

    # calc dispatcher routes through bridge/calculators.py::run_calc
    if tool_name == "calc":
        from bridge.calculators import run_calc, list_calculators
        if command == "list":
            return {"ok": True, "calculators": list_calculators()}
        try:
            result = run_calc(command, **args)
            return {"ok": "error" not in result, **result}
        except TypeError as e:
            return {"ok": False, "error": f"Bad args for calc.{command}: {e}"}

    # util.invoke - generic Bridge method by name
    if tool_name == "util":
        if command != "invoke":
            return {"ok": False, "error": f"util only supports command='invoke', got '{command}'"}
        method_name = method_override
        if not method_name:
            return {"ok": False, "error": "util.invoke requires 'method' parameter"}
        from bridge.api import Bridge
        bridge = Bridge()
        method = getattr(bridge, method_name, None)
        if method is None or not callable(method) or method_name.startswith("_"):
            return {"ok": False, "error": f"Bridge method '{method_name}' not found or not callable"}
        try:
            import inspect
            sig = inspect.signature(method)
            valid = {k: v for k, v in args.items() if k in sig.parameters}
            dropped = set(args) - set(valid)
            if dropped:
                import logging
                logging.getLogger("mcp").warning(
                    "Dropped unknown arg(s) %s for util.invoke(%s) (expected: %s)",
                    dropped, method_name, list(sig.parameters)
                )
            return {"ok": True, "result": method(**valid)}
        except TypeError as e:
            return {"ok": False, "error": f"Bad args for util.invoke({method_name}): {e}",
                    "method": method_name}

    # Standard dispatcher: look up command in the map
    cmap = _DISPATCHER_MAPS.get(tool_name)
    if cmap is None:
        return {"ok": False, "error": f"Unknown dispatcher: {tool_name}"}
    if command not in cmap:
        return {"ok": False,
                "error": f"Unknown command '{command}' for {tool_name}",
                "available": sorted(cmap.keys())}

    method_name = cmap[command]
    from bridge.api import Bridge
    bridge = Bridge()
    method = getattr(bridge, method_name, None)
    if method is None:
        return {"ok": False,
                "error": f"Bridge method '{method_name}' not found",
                "dispatcher": tool_name, "command": command}
    try:
        import inspect
        sig = inspect.signature(method)
        valid = {k: v for k, v in args.items() if k in sig.parameters}
        dropped = set(args) - set(valid)
        if dropped:
            import logging
            logging.getLogger("mcp").warning(
                "Dropped unknown arg(s) %s for %s.%s (expected: %s)",
                dropped, tool_name, command, list(sig.parameters)
            )
        return {"ok": True, "result": method(**valid)}
    except TypeError as e:
        return {"ok": False,
                "error": f"Bad args for {tool_name}.{command}: {e}",
                "method": method_name}
    except Exception as e:
        # v3.5.10 Bug #1: dispatcher must not crash on downstream exceptions.
        # Before this fix, only TypeError was caught. Anything else (e.g.,
        # pymupdf.FileDataError when passing /dev/null to drawing_intel.hash)
        # propagated up and crashed the daemon. Sim report Bug #1.
        # Sanitize the message to avoid leaking Python internals (Bug #8).
        err_class = type(e).__name__
        # Keep message concise; full traceback is logged elsewhere if enabled.
        msg = str(e)[:200]
        return {"ok": False,
                "error": f"{tool_name}.{command} failed: {err_class}: {msg}",
                "method": method_name,
                "exception_class": err_class}


_DISPATCHER_NAMES = set(_DISPATCHER_MAPS.keys()) | {"calc", "util"}



# Most tool names map 1:1 to Bridge method names. Exceptions go here.
# Also: tools that need forced argument injection (e.g. preview_only).
_TOOL_BRIDGE_MAP = {
    "lookup_aisc_member": "get_aisc_member_info",
    "generate_3d_view":   "generate_3d_view",
    "run_self_test":      "_run_self_test_via_module",   # synthetic
    # v3.4.0
    "governance_status":    "get_governance_status",
    "vault_sync_status":    "get_vault_sync_status",
    # Phase 2 slash commands
    "intake_bid":           "intake_bid_from_invite",
    "process_drawing":      "auto_process_drawing",
    "generate_proposal":    "generate_proposal_from_bid",
    "generate_gp":          "generate_gp_only",
    "compliance_check":     "cascade_compliance",
    "morning_brief":        "morning_briefing",
    "score_bid_pipeline":   "pipeline_score",
    "list_bids_active":     "list_active_bids",
    "pending_approvals":    "list_pending_approvals",
    # Phase 5
    "prove_variation":       "prove_variation",
    # v3.3.2
    "scan_projects":         "run_migration_scan_pass1",
}

_TOOL_FORCED_ARGS = {
    # Outreach must NEVER auto-send via Claude/Cowork - preview only.
    # Owner confirms in the desktop app via confirm_refinery_outreach.
    "draft_refinery_outreach": {"preview_only": True},
    # iMessage to external contacts: preview only + engagement record required.
    # Owner confirms in desktop GUI. Never auto-sends. TCPA compliance.
    "send_imessage_to_contact": {"preview_only": True, "require_engagement_record": True},
}


# ═══ MCP PROTOCOL HANDLER ══════════════════════════════════════════

def handle_request(request: dict) -> dict:
    """Handle a JSON-RPC 2.0 request from the Claude app."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "your-company-office",
                "version": "1.0.0",
            },
        })

    elif method == "notifications/initialized":
        return None  # No response needed for notifications

    elif method == "tools/list":
        return _result(req_id, {"tools": MCP_TOOLS})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        return _call_tool(req_id, tool_name, arguments)

    elif method == "ping":
        return _result(req_id, {})

    else:
        return _error(req_id, -32601, f"Method not found: {method}")


def _call_tool(req_id, tool_name: str, arguments: dict) -> dict:
    """Call a bridge method (with forced-arg overrides) and return MCP content.

    Routing (v3.5.6):
      0. Dispatcher tools (bid_pipeline, engineering, …, calc, util) →
         routed through _dispatch_call which uses _DISPATCHER_MAPS.
      1. Synthetic tools (e.g. run_self_test) → handled inline
      2. Tools in _TOOL_BRIDGE_MAP → map to a different Bridge method name
      3. Otherwise → tool name == Bridge method name (existing convention)

    Forced args from _TOOL_FORCED_ARGS override anything Claude/Cowork sends -
    this is how we guarantee preview_only=True for outreach regardless of how
    the LLM formats its request.
    """
    try:
        # 0. Dispatcher routing (v3.5.6)
        if tool_name in _DISPATCHER_NAMES:
            args = arguments or {}
            command = args.get("command", "")
            method_override = args.get("method")  # for util.invoke
            inner_args = args.get("args", {}) or {}
            result = _dispatch_call(tool_name, command, inner_args, method_override)
            text = json.dumps(result, indent=2, default=str)
            return _result(req_id, {
                "content": [{"type": "text", "text": text}],
                **({"isError": True} if not result.get("ok", True) else {}),
            })

        # 1. Synthetic: self-test runs the agent module directly
        if tool_name == "run_self_test":
            from bridge.agents.self_test import run_full_self_test
            r = run_full_self_test()
            return _result(req_id, {
                "content": [{"type": "text", "text": json.dumps(r, indent=2, default=str)}],
            })

        from bridge.api import Bridge
        bridge = Bridge()

        # 2. Apply name remap for tools whose MCP name differs from bridge name
        bridge_method_name = _TOOL_BRIDGE_MAP.get(tool_name, tool_name)

        if not hasattr(bridge, bridge_method_name):
            return _error(req_id, -32602, f"Unknown tool: {tool_name} (no bridge method {bridge_method_name})")

        method = getattr(bridge, bridge_method_name)

        # 3. Merge user args + forced args (forced wins - security boundary)
        final_args = dict(arguments or {})
        final_args.update(_TOOL_FORCED_ARGS.get(tool_name, {}))

        # 3b. v3.2.7 pass 9b: content_base64 passthrough for claude.ai.
        # When a PDF is uploaded through the browser, claude.ai can pass
        # the bytes as base64. Decode to a temp file and inject pdf_path
        # so every pdf-accepting Bridge method works without modification.
        if "content_base64" in final_args and not final_args.get("pdf_path"):
            import base64 as _b64, tempfile as _tmpf
            try:
                raw = _b64.b64decode(final_args["content_base64"])
                tmp = _tmpf.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="nc_mcp_")
                tmp.write(raw)
                tmp.close()
                final_args["pdf_path"] = tmp.name
            except Exception as b64e:
                return _error(req_id, -32602, f"content_base64 decode failed: {b64e}")

        # 4. Filter to args the method actually accepts (defends against LLM-extra args)
        import inspect
        try:
            sig = inspect.signature(method)
            valid = {k: v for k, v in final_args.items() if k in sig.parameters}
            dropped = set(final_args) - set(valid)
            if dropped:
                import logging
                logging.getLogger("mcp").warning(
                    "Dropped unknown arg(s) %s for %s (expected: %s)",
                    dropped, tool_name, list(sig.parameters)
                )
        except (ValueError, TypeError):
            valid = final_args

        result = method(**valid)

        # v3.2.7 pass 10: build rich MCP content blocks.
        # Standard: JSON text block with the full result.
        # If result contains _images, _files, or _artifact_hint,
        # add image content blocks and structured download links
        # so claude.ai can render them inline.
        content_blocks = _build_rich_content(result)

        return _result(req_id, {
            "content": content_blocks,
        })

    except TypeError as e:
        return _result(req_id, {
            "content": [{"type": "text", "text": f"Argument error: {e}"}],
            "isError": True,
        })
    except Exception as e:
        return _result(req_id, {
            "content": [{"type": "text", "text": f"Error: {str(e)}\n{traceback.format_exc()[-500:]}"}],
            "isError": True,
        })


def _build_rich_content(result: dict) -> list[dict]:
    """Build MCP content blocks from a Bridge method result.

    Standard result: single text block with JSON.
    Rich result (pass 10): text block + image blocks + file links + artifact hints.

    Checks both top-level keys AND result["data"] for rich media:
      _images / _files / _artifact_hint  (explicit, Bridge sets these)
      stl_b64  (auto-detected in data dict, triggers 3D artifact hint)
      overlay_pages  (auto-detected, triggers image content blocks)

    Rich keys are stripped from the JSON text to avoid bloat.
    """
    blocks = []
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}

    # Extract explicit rich-media keys (top-level or inside data)
    images = result.pop("_images", None) or data.pop("_images", None)
    files = result.pop("_files", None) or data.pop("_files", None)
    artifact_hint = result.pop("_artifact_hint", None) or data.pop("_artifact_hint", None)

    # Auto-detect STL in data (generate_3d_view, auto_process_drawing)
    stl_b64 = result.pop("_stl_b64", None)
    has_stl_in_data = "stl_b64" in data

    # Auto-detect overlay pages in data (render_tagged_pdf)
    overlay_pages = data.pop("_overlay_pages", None)

    # 1. Always include the JSON text block
    text = json.dumps(result, indent=2, default=str)
    blocks.append({"type": "text", "text": text})

    # 2. Image content blocks (overlays, thumbnails, rasterized pages)
    if images:
        for img in images:
            if img.get("data_b64") and img.get("mime"):
                blocks.append({
                    "type": "image",
                    "data": img["data_b64"],
                    "mimeType": img["mime"],
                })
                if img.get("label"):
                    blocks.append({"type": "text", "text": f"[Image: {img['label']}]"})

    if overlay_pages:
        for page in overlay_pages:
            if page.get("png_b64"):
                blocks.append({
                    "type": "image",
                    "data": page["png_b64"],
                    "mimeType": "image/png",
                })
                if page.get("label"):
                    blocks.append({"type": "text", "text": f"[Overlay: {page['label']}]"})

    # 3. File download links (PDFs, STLs served via /files/ endpoint)
    if files:
        file_lines = ["**Downloads:**"]
        for f in files:
            url = f.get("url", "")
            name = f.get("filename", "file")
            size = f.get("size_bytes", 0)
            size_label = f"{size/1024:.0f} KB" if size < 1_000_000 else f"{size/1_000_000:.1f} MB"
            file_lines.append(f"- [{name}]({url}) ({size_label})")
        blocks.append({"type": "text", "text": "\n".join(file_lines)})

    # 4. Artifact hint for claude.ai to render interactive content
    if artifact_hint:
        blocks.append({"type": "text", "text": f"\n---\n**Artifact instruction:** {artifact_hint}"})

    # 5. Auto-detected STL: instruct claude.ai to build a Three.js artifact
    if stl_b64 or has_stl_in_data:
        blocks.append({"type": "text", "text": (
            "\n---\n**3D Model:** This response includes STL geometry in the "
            "data.stl_b64 field (base64-encoded binary STL). Render it as a "
            "Three.js artifact: use STLLoader to parse the base64, "
            "MeshStandardMaterial with color #b0b0b0, DirectionalLight + "
            "AmbientLight, OrbitControls for rotate/zoom/pan, and a "
            "GridHelper for scale reference. Show shape name, weight, and "
            "dimensions as an overlay label in the artifact."
        )})

    return blocks


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}

def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ═══ STDIO TRANSPORT ═══════════════════════════════════════════════

def main():
    """Run the MCP server on stdio (JSON-RPC 2.0)."""
    # Read from stdin, write to stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            error = _error(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(error) + "\n")
            sys.stdout.flush()
        except Exception as e:
            error = _error(None, -32603, str(e))
            sys.stdout.write(json.dumps(error) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
