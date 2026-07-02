# Your Company Virtual Office - File Index

Version: v3.2.7.15 | Updated: 2026-06-01
Total files: ~3,051 across all directories (plus the `Video Creation/` studio module, added 2026-06-01).

---

## Root - Entry Points

| File | Purpose |
|------|---------|
| `main.py` | pywebview launcher (Edge WebView2); also exposes `--mcp-server` mode for Claude Desktop |
| `mcp_server.py` | stdio JSONRPC server; Claude Desktop connects here to reach the Bridge |
| `config.json` | Live runtime config (API keys, feature flags, routing overrides) |
| `config.template.json` | Committed template for config.json; no real keys |

---

## Root - Build and Deploy

| File | Purpose |
|------|---------|
| `VirtualOffice.spec` | PyInstaller spec; defines the frozen EXE bundle |
| `make_exe.bat` | Standard EXE build via PyInstaller |
| `make_exe_clean.bat` | Full clean + rebuild (removes dist/ and build/ first) |
| `make_exe_signed.bat` | Code-signed EXE build for production release |
| `make_ship_zip.bat` | Packages dist/ into a dated ship zip |
| `BUILD_FOR_OWNER.bat` | One-click signed build + zip for the Owner's machine |
| `INSTALL_DEPENDENCIES.bat` | Installs all pip requirements on a clean Windows machine |
| `OWNER_INSTALL.bat` | Owner-specific install script (handles Edge WebView2 check) |
| `SETUP.ps1` | PowerShell full-environment setup for a fresh workstation |
| `STARTUP.bat` | Launches the app; used by Task Scheduler for auto-start |
| `RUN_VIRTUALOFFICE.bat` | Simple dev launcher shortcut |
| `run_dev.bat` | Dev mode launch with console output visible |
| `watchdog.bat` | Restarts the app if it crashes; runs alongside STARTUP.bat |
| `installer.nsi` | NSIS installer script for the distributable Setup EXE |
| `YourCoVirtualOffice-Setup-v3.2.6.exe` | Previous release installer (v3.2.6) |
| `VirtualOffice_ship_20260516.zip` | Current ship zip (2026-05-16 build) |
| `generate_icon.py` | Generates app.ico and assets/cube_*.png from source SVG |
| `app.ico` | Application icon (Windows .ico format) |
| `check_python.bat` | Verifies Python 3.13 is on PATH before any build |

---

## Root - MCP and Integration

| File | Purpose |
|------|---------|
| `START_MCP_HTTP.bat` | Starts the HTTP MCP server (for remote Claude Desktop connections) |
| `register_with_claude_desktop.bat` | Registers the stdio MCP server in Claude's config |
| `SETUP_CLAUDE_AI_CONNECTOR.md` | Instructions for wiring the Cowork/Claude AI connector |
| `SETUP_GMAIL_AUTO_SCAN.bat` | Configures Gmail OAuth for auto inbox scanning |
| `REGISTER_VENDOR_POLLER.bat` | Registers the vendor quote polling Windows Scheduled Task |
| `VENDOR_POLLER_TASK.xml` | Task Scheduler XML definition for the vendor quote poller |
| `schtasks_setup.bat` | Registers all Windows Scheduled Tasks for background services |

---

## Root - Documentation

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Primary AI context file; architecture, hard rules, bid rules, key interfaces |
| `CLAUDE.local.md` | Local overrides to CLAUDE.md (machine-specific, not committed) |
| `CHANGELOG.md` | Version history; read before any edit to understand recent changes |
| `DEVELOPER_HANDBOOK.md` | Current developer handbook (patterns, conventions, gotchas) |
| `DEVELOPER_HANDBOOK_v6.1.0.md` | Archived v6.1.0 handbook (reference for legacy decisions) |
| `DEPLOYMENT.md` | Deployment checklist and environment setup instructions |
| `HANDOFF.md` | Context handoff doc for session continuity between AI conversations |
| `INSTALL.md` | End-user installation guide |
| `PLAN.md` | Active development plan; tracks in-progress feature work |
| `SETUP_FOR_OWNER.md` | Step-by-step setup guide written for Owner (non-technical) |
| `STARTUP_PROFILE.md` | Documents the app's startup sequence and boot behavior |
| `BRIDGE_METHOD_MANIFEST.md` | Full manifest of all Bridge methods with signatures |
| `owner-directives-v4.md` | the Owner's standing directives document (v4); CEO operating rules, bid rules, voice rules, and all locked procedures |
| `claude-routines-construction.md` | 8-routine roadmap for autonomous AI agents (email manager, CRM updater, cost tracker, project context, payment claims, weekly report, weather log, meeting minutes); cross-links to `.specify/specs/bid-estimating/scheduled-tasks.md` and `mcp-connectors.md` |
| `claude-estimating-workflow.md` | Three-phase estimating workflow roadmap (understand scope, direct costs, indirect costs + letter of offer + reconciliation); names seven skills (two already BUILT: `.claude/skills/project-indexer/`, `.claude/skills/drawing-analyzer/`; five TO BUILD: requirements-extraction, contract-review, assemblies, schedule-builder, reconciliation); pairs with `claude-routines-construction.md` and `claude-drawing-indexing.md` |
| `claude-drawing-indexing.md` | Drawing pre-processing pipeline (Antigravity + Google Sheets schema, NotebookLM + per-drawing markdown, hybrid recommendation); extends existing `.claude/skills/project-indexer/` and `.claude/skills/drawing-analyzer/`; introduces per-bid `_bid_context/` and `indexed/` companion folders; foundation for `claude-estimating-workflow.md` |
| `BRIDGE_JSON_METHODS.md` | JSON-callable Bridge method reference for MCP consumers |
| `DIAGNOSE_CLAUDE.bat` | Runs 6-test Claude API diagnostic; use when AI calls fail |
| `build_log.txt` | Output log from the most recent EXE build |
| `CHANGES_v327.1/CHANGES.md` | Detailed change notes for the v3.2.7.1 release |
| `OWNER_ROADMAP_v327_1.md` | Roadmap for v3.2.7.1 written for the Owner's review |
| `ROADMAP_v327_UPDATED_v2.pdf` | Updated roadmap PDF (v3.2.7 series) |

---

## Root - Owner Reports (version release notes for CEO)

| File | Purpose |
|------|---------|
| `OWNER_REPORT_V327_20260513.md` | Release report dated 2026-05-13 |
| `OWNER_REPORT_v32100.md` through `OWNER_REPORT_v333.md` | Per-version release summaries delivered to Owner |

---

## `vo_app/` - Package Core

| File | Purpose |
|------|---------|
| `__init__.py` | Package init; exports version constant (`3.2.7.15`) |
| `_resources.py` | `resource_path()` helper; all file paths must go through this (frozen EXE safe) |

---

## `frontend/` - Single-Page App (5 tabs)

| File | Purpose |
|------|---------|
| `index.html` | App shell; loads the SPA and Edge WebView2 bridge |
| `app.js` | Main frontend logic; all Bridge calls via `window.pywebview.api.<method>()` |
| `styles.css` | Dark theme stylesheet for all 5 tabs |
| `favicon.png` | Browser favicon |
| `workbench/` | Workbench tab UI components (MODEL tab canvas and controls) |

---

## `bridge/` - The Bridge Monolith

The Bridge is the single Python backend class (~250 modules). All methods return `_ok(data)` or `_err(msg)`. Every GUI call and every MCP tool call routes through here.

### Core Infrastructure

| File | Purpose |
|------|---------|
| `api.py` | The Bridge class itself; hundreds of methods, all public entry points |
| `api_integrator.py` | Adds new AI APIs to the app through chat; fallback chain controller |
| `api_registry.py` | Registry of all connected external APIs and their health status |
| `direct_route.py` | 36 local routes that intercept common requests before hitting the AI |
| `intent_router.py` | Translates the Owner's shorthand into full pipeline actions |
| `event_bus.py` | Typed pub/sub event bus; 14 event types; modules subscribe without coupling |
| `action_chains.py` | Event-driven workflow chains (e.g. BID_WON triggers project creation) |
| `session_boot.py` | App startup sequence; warms caches and registers background tasks |
| `session_context.py` | Per-session state: active project, current user, conversation thread |
| `prompts.py` | Prompt library for all AI calls made by the Bridge |
| `governance.py` | Three-tier governance enforcement (Tier 1 immutable, Tier 2 CEO, Tier 3 defaults) |
| `resilience.py` | Retry logic, circuit breakers, and graceful degradation patterns |
| `health.py` | Health check endpoint; reports API connectivity and DB status |
| `diagnostics.py` | 6-test diagnostic suite (invoked by DIAGNOSE_CLAUDE.bat or chat) |
| `audit.py` | Audit trail writer; every governance decision is logged |
| `hash_chain.py` | SHA-256 hash chain for tamper-evident document integrity |
| `page_hasher.py` | Per-page drawing hash engine; only re-processes changed pages |
| `keyvault.py` | Encrypted key storage wrapper (keys.enc in data/) |
| `vault.py` | Secure document vault; handles encrypted file storage |
| `memory.py` | Persistent memory store for cross-session context retention |
| `notifications.py` | Sends desktop notifications and SMS alerts |
| `reminders.py` | Reminder scheduler integrated with the event bus |
| `feature_status.py` | Feature flag registry; enables/disables modules at runtime |
| `skill_registry.py` | Progressive-disclosure skill loader following SKILL.md pattern |
| `self_repair.py` | VJ self-repair engine; 7 scan categories, autonomous fix proposals |
| `self_build.py` | Self-modification pipeline for VJ-authored code changes |
| `sentry_setup.py` | Sentry error tracking integration for crash reporting |

### AI and Model Routing

| File | Purpose |
|------|---------|
| `ai_model_router.py` | Single source of truth for model-to-task assignment (T1-T4 + GPT/Gemini) |
| `gemini_compat.py` | Compatibility shim for google-genai SDK calls |
| `ai_orchestration/` | Multi-step AI conductor: intake, conduct, verify, correct, proofread |
| `vision_tiers/` | Tiered vision pipeline adapters: Claude, GPT-4o, Gemini, Doctr, Ollama |
| `local_models/` | Local model clients: Ollama, Doctr OCR, hardware detection |
| `dual_account.py` | Manages dual Anthropic account keys for rate-limit failover |
| `claude_connect.py` | Claude API session manager and streaming handler |
| `claude_app_setup.py` | Configures the Claude AI Cowork connector on first run |
| `mcp_client.py` | MCP client for calling external MCP servers from the Bridge |
| `mcp_http_server.py` | HTTP MCP server exposing Bridge methods over HTTP/SSE |
| `mcp_stdio_server.py` | stdio MCP server (the primary Claude Desktop interface) |
| `mcp_remote.py` | Handles remote MCP connections and authentication |

### Bid and Estimating

| File | Purpose |
|------|---------|
| `bid_rates.py` | CEO-locked Q2 2026 rates: fab $[FAB RATE]/T, erection $[ERECTION RATE]/T, joists $[JOIST RATE]/T |
| `bid_pipeline.py` | Bid state machine: SCANNED → REVIEWING → PURSUING → SUBMITTED → WON/LOST |
| `bid_documents.py` | Generates client proposal PDF and GP report PDF (the two-PDF pair) |
| `bid_sanity_gates.py` | 4-gate sanity check run before every bid ships |
| `bid_scanner.py` | Scans inbound emails and attachments for bid opportunities |
| `bid_scorecard.py` | Combines voice check, compliance scan, PDF QC, and pricing into one score |
| `bid_audit.py` | Post-bid audit: logs actuals vs. estimated for learning feedback |
| `bid_followup.py` | Auto-generates follow-up email drafts after bid submission |
| `autonomous_bidding.py` | Full autonomous pipeline: email in → compliance check → proposal → cover email |
| `intake_bid.py` | Manual bid intake form handler |
| `bid_intake/` | BuildingConnected integration for GC-sourced bid invitations |
| `calculators.py` | Core pricing calculators: tonnage, deck SF, anchor count, margin scenarios |
| `assembly_costing.py` | Connection hardware cost assembly (bolts, plates, welding hours per joint type) |
| `misc_steel_calculator.py` | Misc steel estimating (stairs, rails, lintels, plates) |
| `misc_steel/` | Detectors for misc steel types: lintels, plates, railings, stairs |
| `shop_capacity.py` | Capacity-aware margin adjuster: busy shop bids higher, slow shop bids lower |
| `risk_scoring.py` | Monte Carlo 1,000-simulation risk scoring with confidence intervals |
| `learning_estimator.py` | Self-calibrating estimator; feeds actuals back after project completion |
| `calibration_2026q2.py` | Loads Q2 2026 Houston-MSA market calibration data for all pricing modules |
| `scope_narrative.py` | Generates project-specific scope narratives from takeoff data |
| `vm_bid_discovery.py` | Virtual Owner bid discovery: surfaces new opportunities matching NC criteria |
| `grade_comparison.py` | Steel grade comparison tool for value engineering options |

### Takeoff and Drawing Intelligence

| File | Purpose |
|------|---------|
| `takeoff_controller.py` | Top-level takeoff orchestrator: drawing in → member schedule out |
| `drawing_intel/` | Vision pipeline: preprocess, connection check, detail vision, 3D model, visual diff |
| `hybrid_3d_pipeline.py` | PDF drawing → local OCR/pdfplumber → AISC match → 3D geometry |
| `doc_intel/` | Document intelligence engine for non-drawing PDFs (specs, submittals) |
| `spec_auditor/` | Spec cost-flag scanner; identifies spec sections that drive cost |
| `takeoff_graph/` | Graph-based takeoff state machine with typed nodes |
| `bim_layer/` | BIM integration layer for IFC/Revit model data |
| `dstv_parser.py` | Parses DSTV/NC1 CNC exchange files from Tekla, SDS2, Advance Steel |
| `cnc/` | CNC output generators: DSTV writer, DXF parts, G-code, punch maps, stop lists |
| `stl_generator.py` | Generates 3D STL files from AISC shape geometry and member length |
| `stl_thumbnail.py` | Renders STL files to PNG thumbnails for the MODEL tab |
| `building_assembler.py` | Assembles full 3D building STL from individual member geometry |
| `member_inventory_thumbnail.py` | Renders a side-by-side PNG of all unique shapes from a drawing |
| `pdf_qc.py` | 6-rule PDF visual QC check run on every generated document |
| `tagged_pdf_renderer.py` | Renders tagged/accessible PDFs (ADA-compliant output) |
| `variation_prover.py` | Generates ReportLab PDF evidence packages for drawing/spec conflicts |
| `cross_verify/` | Correction data lake and bridge for cross-checking extracted data |
| `aisc_validator.py` | AISC v16.0 shape database wrapper; 2,299 shapes, authoritative weights |
| `aisc_ingest.py` | One-time ingestion script for the AISC CSV into the SQLite database |
| `aisc_207_audit.py` | AISC 207-25 Building Fabricator certification compliance tracker |
| `connection_engine/` | Structural connection designers: base plates, shear tabs, pynite bridge |
| `connection_weight.py` | Estimates connection plate tonnage not in member schedules |
| `idea_statica_checkbot.py` | IDEA StatiCa BimAPI integration for connection code checks |

### Project and Field Operations

| File | Purpose |
|------|---------|
| `fabrication.py` | Shop production tracking: cut lists, weld sequences, QC holds |
| `shop_floor/` | Shop floor module: photo QC, production tracker, QR code generator |
| `shop_floor.py` | Shop floor Bridge entry points (wraps shop_floor/ submodule) |
| `field_tech/` | Field technology module for field operations support |
| `create_project.py` | Creates a new project record and folder structure |
| `project_processor.py` | Processes project data updates and triggers downstream events |
| `project_syncer.py` | Syncs project state across Bridge, databases, and connected tools |
| `project_memory/` | Project memory store with backtester, search, and indexer |
| `project_migration/` | One-time scanner for seeding historical project data |
| `change_order.py` | Scope creep detection and AIA G701 change order generation |
| `rfi_generator.py` | Generates RFI documents from detected drawing conflicts |
| `procore_rfi_submittal.py` | Pushes RFIs and submittals to Procore via API |
| `aia_g702_g703.py` | Generates AIA G702 Application for Payment and G703 Continuation Sheet |
| `logistics/` | Delivery tracker for material shipments |
| `weld_consumable.py` | Weld consumable cost calculator using Lincoln Electric/ESAB formulas |
| `aws_d11_2025.py` | AWS D1.1 2025 welding code compliance reference |
| `aws_d11_2025_compliance.py` | AWS D1.1 2025 essential variable tracker; pulsed-spray GMAW and new prequalified WPS tables |
| `tekla.py` | Tekla Structures API integration for model data exchange |

### Finance and Compliance

| File | Purpose |
|------|---------|
| `cashflow_cfo.py` | 30/60/90-day cash flow projection combining AR, payroll, materials, insurance |
| `quickbooks_bridge.py` | QuickBooks Online API integration for invoicing and AR |
| `cost_tracker.py` | Real-time job cost tracker updated from shop and field actuals |
| `cost_engine/` | Core cost computation engine |
| `fin_automation/` | Finance automation module (automated AP/AR workflows) |
| `compliance.py` | Tier 1 immutable compliance rule enforcer |
| `governance.py` | Three-tier governance: Tier 1 immutable, Tier 2 CEO, Tier 3 defaults |
| `isnetworld_client.py` | ISNetworld REST API client for prequalification data |
| `disa_status.py` | DISA drug testing status lookup for field personnel |
| `ncci_2025.py` | NCCI 2025 EMR formula with correct primary/excess loss split |
| `emr_predictor.py` | EMR 3-year rolling predictor using NCCI experience rating math |
| `davis_bacon_wages.py` | Davis-Bacon prevailing wage lookup for Harris County classifications |
| `houston_permits.py` | Houston building permit lookup and status tracker |
| `houston_market/` | Houston-MSA market data feeds (pricing, labor, economic indicators) |
| `sam_gov_opportunities.py` | SAM.gov federal contract opportunity scanner (NAICS 332312) |
| `fred_steel_pricing.py` | FRED API PPI data for real-time structural steel pricing |
| `eia_fuel_surcharge.py` | EIA fuel price feed for delivery surcharge calculations |
| `value_engineering/` | VE tools: connection standardizer, section optimizer, VE report generator |

### Contacts, Outreach, and Communications

| File | Purpose |
|------|---------|
| `contacts.py` | Contact database CRUD and deduplication |
| `engagement_records.py` | Documents prior business engagement per TCPA requirements |
| `engagement_auto.py` | Auto-creates engagement records from Gmail reply detection |
| `sms_channel.py` | SMS message channel via BlueBubbles/iMessage gateway |
| `imessage_gateway.py` | BlueBubbles API bridge for iMessage send/receive |
| `m365_mail_scanner.py` | Microsoft 365 email scanner for bid opportunities and follow-ups |
| `linkedin_content.py` | LinkedIn post generator for project announcements |
| `bluebeam_studio.py` | Bluebeam Studio integration for collaborative drawing markup |
| `outreach_log.db` | (data/) Log of all outbound outreach attempts |

### Intelligence and Learning

| File | Purpose |
|------|---------|
| `virtual_owner.py` | CEO bid review agent; enforces 15 documented decision patterns |
| `virtual_joseph.py` | QA agent; persistent quality gate between user and system responses |
| `vj_orchestrator.py` | VJ autonomous agent: model selection, tool choice, feature design |
| `vj_knowledge.py` | VJ expert knowledge base of the codebase and fix history |
| `vj_trainer.py` | Trains VJ on new corrections and preference updates |
| `knowledge_graph.py` | Entity graph linking Projects, Bids, Contacts, Compliance, Cost, Welders |
| `learning/` | Correction analyzer and prompt updater for continuous improvement |
| `predictive/` | Predictive analytics module |
| `objective_planner/` | Deadline tracker and autonomous planner for multi-step objectives |
| `archetypes/` | Archetype engine for bid and project pattern classification |
| `ceo_prefs_logger.py` | Auto-extracts and logs CEO preferences revealed during conversation |
| `vm_training_data.json` | Training examples for Virtual Owner bid review decisions |
| `vm_training_preferences.json` | the Owner's logged pricing and scope preferences (auto-updated) |

### External Integrations

| File | Purpose |
|------|---------|
| `integrations.py` | Connector registry for all third-party integrations |
| `gdrive_sync.py` | Google Drive file sync for shared project documents |
| `obsidian_sync.py` | Obsidian vault sync for knowledge base notes |
| `cloud_watchdog/` | Cloud file watchers: Google Drive and OneDrive change detection |
| `cloud_registry.py` | Registry of connected cloud storage accounts |
| `data_sources.py` | Data source abstraction layer for all external feeds |
| `openhuman/` | OpenHuman integration for persistent agent memory RPC |
| `cowork_scheduler.py` | Cowork scheduled task runner (5 recurring CT-timezone tasks) |
| `productivity_kpis.py` | KPI tracker for time-saved and task completion metrics |

### Utilities

| File | Purpose |
|------|---------|
| `_date_utils.py` | Date parsing and formatting utilities used across the Bridge |
| `blockers.py` | Active blocker tracker (surfaces the EMR letter and similar open items) |
| `documents.py` | General document read/write utilities |
| `exporters/` | Export generators: calculation packs, Strumis, Tekla XML |
| `pipeline.py` | Generic pipeline runner for chained processing steps |
| `agents/` | Agent submodules: orchestrator, AR invoicing, bid chain, compliance, ops |
| `workbench/` | Correction bridge and data lake for the workbench tab |

---

## `data/` - Databases and Persistent State

### AISC and Steel Reference

| File | Purpose |
|------|---------|
| `aisc-shapes-v160-US.csv` | Source CSV for AISC v16.0 shapes (2,299 rows, US customary) |
| `aisc_master.csv` | Cleaned master AISC shape table used by the validator |
| `aisc_sections.csv` | Supplemental section properties for connection design |
| `aisc_audit.db` | AISC 207-25 certification audit records |

### Bid and Pipeline Databases

| File | Purpose |
|------|---------|
| `bid_pipeline.db` | Active bid pipeline state machine records |
| `bid_pipeline_legacy.db` | Pre-migration bid records (read-only archive) |
| `bid_leads.db` | Inbound bid lead log from scanner and BuildingConnected |
| `bid_attachments/` | Binary attachments (drawings, specs) attached to bid records |
| `bid_counter.json` | Auto-incrementing bid number counter |
| `ar_invoices.db` | Accounts receivable invoice records |
| `change_orders.db` | Change order records linked to projects |
| `cost_engine.db` | Job cost actuals by project and cost code |
| `estimator_learning.db` | Historical estimate-vs-actual feedback for the learning estimator |

### Contacts and Engagement

| File | Purpose |
|------|---------|
| `contacts.db` | Contact records (GCs, owners, vendors, inspectors) |
| `engagement_records/` | Per-contact engagement evidence files (TCPA documentation) |
| `outreach_log.db` | Log of all outbound outreach attempts |
| `messages.db` | iMessage and SMS message history |
| `conversations.db` | AI conversation history for context retention |

### Compliance and Governance

| File | Purpose |
|------|---------|
| `audit.db` | Governance audit trail (all Tier 1/2 decisions logged) |
| `governance.json` | Active governance configuration (tier overrides and exceptions) |
| `governance_audit.jsonl` | Append-only governance event log |
| `compliance_snapshots/` | Point-in-time compliance status captures |
| `disa_employees.db` | DISA drug test status records for field personnel |
| `hash_chain.db` | Document hash chain for tamper-evident integrity |
| `CALIBRATION_HASHES.json` | Integrity hashes for the Q2 2026 calibration dataset |

### Market and Financial Data

| File | Purpose |
|------|---------|
| `calibration_2026Q2.json` | Q2 2026 Houston-MSA market calibration data (steel prices, labor rates) |
| `calibration/` | Historical calibration snapshots by quarter |
| `fred_cache.json` | Cached FRED API PPI responses (TTL: 24 hours) |
| `houston_market.db` | Houston-MSA market data (permits, labor, economic indicators) |
| `houston_permits.db` | Scraped Houston building permit records |
| `houston_pipeline_seed.json` | Seed data for the Houston construction pipeline feed |
| `vision_cost_baseline.json` | Baseline vision API cost data for tier routing decisions |
| `fin_automation.db` | Financial automation workflow records |
| `data_feeds.db` | External data feed status and cache records |
| `predictive.db` | Predictive analytics model outputs and history |

### Project and Shop Data

| File | Purpose |
|------|---------|
| `projects.db` | Project master records (status, scope, contacts, financials) |
| `projects/` | Per-project subfolders (drawings, proposals, field photos) |
| `shop_floor.db` | Shop production records (cut lists, weld logs, QC holds) |
| `welding_qa.db` | Welding QA records linked to WPS and welder certifications |
| `idea_checks.db` | IDEA StatiCa connection check results |
| `token_usage.db` | AI token consumption log by model and task |
| `learning_store.db` | VJ learning store (corrections, prompt updates, pattern data) |
| `ops_agents.db` | Ops agent task and execution records |

### Config and Logs

| File | Purpose |
|------|---------|
| `user_prefs.json` | User preference store (UI settings, routing overrides) |
| `channel_config.json` | Communication channel config (SMS, iMessage, email routing) |
| `model_routing.json` | AI model routing config (T1-T4 assignments, fallback order) |
| `remote_mcps.json` | Registry of remote MCP server endpoints |
| `vendor_whitelist.json` | Approved vendor list for quote acceptance |
| `cowork_schedule.json` | Cowork recurring task schedule definitions |
| `hardware_profile.json` | Host machine hardware profile (CPU, RAM, GPU for local model routing) |
| `time_saved.json` | Cumulative time-saved metric tracker |
| `blockers.json` | Active blocker list surfaced in morning briefing |
| `health.json` | Last-written health check snapshot |
| `startup.log` | App startup log (appended each launch) |
| `crash.log` | Last crash traceback |
| `event_log.jsonl` | Append-only event bus log |
| `calc_audit.jsonl` | Append-only calculation audit log (every pricing computation) |
| `ceo_interactions.jsonl` | Append-only log of CEO preference events |
| `governance_audit.jsonl` | Append-only governance decision log |
| `vj_logs/` | VJ scan results and self-repair logs |
| `session/` | Active session state files |
| `templates/` | Document and email templates |
| `excel/` | Excel output files (BOM exports, pricing workbooks) |
| `backtest_phase3_results.json` | Phase 3 Monte Carlo backtest output |
| `legacy/` | Pre-migration data files (read-only archive) |
| `fixtures/` | Test fixture data for harness runs |
| `production/` | Production output artifacts |
| `corrections/` | Human correction records fed back to the learning system |
| `cowork/` | Cowork connector state and artifact cache |
| `task_scheduler/` | Windows Task Scheduler export files |
| `variation_packages/` | Generated variation evidence packages (PDF) |
| `virtual_joseph/` | Virtual Joseph persistent state and knowledge files |
| `core/` | Core data files shared across modules |

---

## `skills/` - Self-Knowledge SKILL.md Files

Each skill is a SKILL.md file loaded by the AI to guide task-specific behavior.

| Skill | Purpose |
|-------|---------|
| `bid-compliance/` | 26 Tier 1 immutable rules + 18 compliance scanner patterns; runs before every client document |
| `bid-output-scrubber/` | Final scrub for supplier names, precedent projects, and engineering line items |
| `bid-pricing/` | Locked Q2 2026 rates, margin targets, drawing-stage adders, and cash flow validation |
| `bid-pricing-sanity-check/` | Validates generated bid line items against locked rates; flags divergence over 3% |
| `change-order/` | Scope creep detection and AIA G701 change order generation workflow |
| `claude-design/` | Routes visual/canvas design work to Claude Design via Chrome (Windows MCP fallback); Tier 1 - no costs, suppliers, or margins in visuals |
| `cowork-cheat-sheet/` | Full command reference for Virtual Office slash commands and natural language |
| `drawing-reading/` | Structural drawing reading protocol; prevents skipping the takeoff |
| `drawing-stage-classifier/` | Classifies drawing stage (SD/DD/CD/IFC) to apply correct pricing adder |
| `email-voice/` | the Owner's voice rules for all outbound email composition |
| `emr-letter-drafter/` | Drafts EMR letter request to Texas Mutual; active until Marathon blocker clears |
| `excel-bid-pricing-validator/` | Read-only Excel pricing validation against Q2 2026 rates |
| `excel-bom-parser/` | Parses Excel BOM/member schedules into Your Company pricing tables |
| `excel-formula-auditor/` | Diagnoses broken Excel formulas; proposes fixes, never applies silently |
| `isn-ravs-responder/` | ISNetworld RAVS questionnaire response using 18 safety programs |
| `marathon-prequaltracker/` | Tracks Marathon Petroleum prequalification blockers; verified data only |
| `owner-voice-check/` | Final-pass voice check for AI-isms, em-dashes, three-adjective lists |
| `project-migration-scanner/` | Two-pass historical project file scanner (read-only Pass 1, copy on approval) |
| `proposal-format/` | Locked PDF proposal format spec (April 28, 2026) |
| `scope-creep-detector/` | Detects scope additions in emails and meeting notes |
| `supplier-quote-tracker/` | Tracks inbound supplier quotes against open material needs |
| `takeoff-completeness-check/` | Checks CSI takeoff against required sections; deck 05 31/36 never optional |
| `two-pdf-pair-check/` | Enforces the two-PDF rule (client proposal + GP report); blocks delivery if incomplete |
| `vj-scan/` | VJ codebase scan: 9 governance/safety/correctness categories, PASS/WARN/BLOCKER |
| `vj-self-knowledge/` | VJ expert knowledge of 471 Bridge methods, known bugs, and fix history |
| `ROADMAP.md` | Skills development roadmap |

---

## `Video Creation/` - Ad and Video Studio Module (added 2026-06-01)

Self-contained AI video production studio for Your Company and Pinnacle advertisements, commercials, reels, and brand films. Firewalled from the bid pipeline: video work never touches bid folders and bid work never touches this folder. Routed from `0.ai-context/CLAUDE.md` on any motion or advertising request. Read `Video Creation/FOLDER_INSTRUCTIONS.md` and `Video Creation/CLAUDE.md` first.

| File / Folder | Purpose |
|------|---------|
| `Video Creation/CLAUDE.md` | Studio role, 16 Anti-AI laws, 5 style systems, prompt formula, QA checklist, HYBRID Runway + HyperFrames flow, persistent-driver discipline |
| `Video Creation/FOLDER_INSTRUCTIONS.md` | Intake-to-deliver pipeline order, output rules, approval chain, brand context |
| `Video Creation/README.md` | Module overview |
| `Video Creation/RUNWAY_PIPELINE.md` | Runway pipeline architecture |
| `Video Creation/orchestrate.js` | Engine detection (HYBRID / HyperFrames-local / Runway-Chrome); run first each session |
| `Video Creation/package.json` | npm deps (hyperframes runtime) |
| `Video Creation/.env.template` | Per-machine config template; `.env` is git-ignored (no secrets committed) |
| `Video Creation/SKILLS/` | Reference skills: VIDEO_STUDIO, ANTI_AI, RUNWAY, CREATIVE_BRIEF, HYPERFRAMES, SHORT_FILM, plus `runway/` slash skills and style generators |
| `Video Creation/TEMPLATES/` | 30s/15s/reel/brand-film/product-demo/explainer templates + `script.template.json` |
| `Video Creation/TOOLKIT/` | Chrome MCP + Runway canvas scripts (inspect, wire, run nodes) |
| `Video Creation/ACTIVE_PROJECTS/` | Live work, one subfolder per project (numbered brief/script/shot-list/prompts/workflow/QA) |
| `Video Creation/OUTPUTS/` | Final approved deliverables (Owner sign-off required before release) |
| `Video Creation/ASSETS/brand/` | Logos and brand color files for Your Company (Style 01) and Pinnacle (Style 02) |
| `Video Creation/src/` | `hyperframes/` compositions and `shared_assets/` (Runway downloads, TTS, renders; media git-ignored) |

---

## `assets/` - Static Assets

| File | Purpose |
|------|---------|
| `cube_16.png` through `cube_512.png` | App icon at multiple resolutions (16, 32, 48, 64, 128, 256, 512 px) |
| `icon.ico` | Compiled Windows icon file |
| `logo_full.png` | Full Your Company logo (used in proposal PDFs and the app header) |

---

## `output/` - Generated Output Files

Runtime output directory. Contents are regenerated and not committed (except `.gitkeep`).

| Contents | Purpose |
|----------|---------|
| `*.stl` | 3D STL files generated by the STL generator (W-shapes, HSS, angles) |
| `NC_Proposal_*.pdf` | Generated bid proposal PDFs |
| `YourCo_Backup_*.zip` | Auto-backup zips |
| `.gitkeep` | Keeps the directory in git when empty |

---

## `tools/` - Developer Utilities

| File | Purpose |
|------|---------|
| `numeric_hardening.py` | Audits Bridge math for float precision issues and division-by-zero risks |
| `parity_review_sample_audit.py` | Samples Bridge method parity between GUI and MCP modes |
| `prebuild_hygiene.sh` | Pre-build checks: pycache clean, import validation, secret scan |
| `vacuum_dbs.py` | Runs VACUUM on all SQLite databases to reclaim space |

---

## `harnesses/` - Self-Test Harnesses

| File | Purpose |
|------|---------|
| `operational.py` | 91-test operational harness; must pass 91/91 before any ship |
| `__init__.py` | Harness package init |

---

## `hooks/` - PyInstaller Hooks

| File | Purpose |
|------|---------|
| `hook-tesseract.py` | PyInstaller hook to bundle Tesseract OCR binaries into the frozen EXE |

---

## `research/` - Channel Watch Knowledge Bases (built by /watch)

Knowledge bases distilled from industry video channels using the /watch skill in
Claude Code. One markdown note per video plus a per-channel SUMMARY.md. Source
material is third-party reference, attributed, never relabeled as Your Company work.
Figures pulled from video are low-confidence until verified the normal way.

| Folder / File | Purpose |
|------|---------|
| `research/constructiq-watch/` | ConstructIQ channel (Tim Fairley): 15 per-video notes plus SUMMARY.md. AI-for-construction, estimating, contracts, project controls. Watched 2026-06-24 |
| `docs/AISC-EDU-KB.md` | AISC Education channel KB: connection design, fabrication, erection, bolting, welding, AISC 360 and 341. Built by /watch 2026-06-24 |

---

## `docs/` - Parity Audit Results

| File | Purpose |
|------|---------|
| `parity_audit_pass10g.json` | GUI/MCP method parity audit results (pass 10g) |
| `parity_audit_pass10i_sample.json` | Sample parity audit (pass 10i) |
| `parity_audit_pass10j_complete.json` | Complete parity audit (pass 10j, most recent) |

---

## `sim_external_connected/` - Integration Simulation

| Contents | Purpose |
|----------|---------|
| `RUN_SIMULATION.md` | Instructions for running the integration simulation suite |
| `Claude/` | Simulated Claude AI connector responses |
| `integrations/` | Mock integration responses for testing without live APIs |
| `mcp_mocks/` | MCP server mock responses for offline testing |

---

## `vault/` - Secure Document Vault

| File | Purpose |
|------|---------|
| `.last_sync` | Timestamp of the last vault sync operation |

---

## `API Keys/` - Key Storage (Local Only, Not Committed)

| File | Purpose |
|------|---------|
| `Claude API.txt` | Anthropic API key |
| `OpenAI API.txt` | OpenAI API key |
| `Gemini API.txt` | Google Gemini API key |
| `FRED API.txt` | St. Louis Fed FRED API key |
| `MCP Token.txt` | MCP authentication token |
| `BlueBubbles.txt` | BlueBubbles server URL and API key |

---

## `.claude/` - Claude Code Configuration

| File | Purpose |
|------|---------|
| `settings.local.json` | Local Claude Code settings (permissions, model overrides) |
| `agents/` | Claude agent definitions for task-specific AI roles |
| `rules/` | Claude rule files (behavioral constraints for this project) |
| `skills/` | Claude Code skill definitions (symlinked or local copies) |

---

## Research and Reference

| File | Purpose |
|------|---------|
| `02_Wiki/research/2026-06-16-uploaded-materials.md` | Report on 6 video transcripts + 1 screenshot (AI estimating, Claude Code features, skill trees, multi-model orchestration, OSS directories). Integration decisions in `UPLOADED-MATERIALS-INTEGRATION-PLAN-2026-06-16.md`. |
