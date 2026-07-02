# Your Company Virtual Office - Developer Handbook v6.1.0

**Date: May 10, 2026**
**Author: Joseph Hasse, Director of I.T.**
**Baseline: v3.5.12 pkgAC + Phases 1-29**

This document is the single source of truth for rebuilding the system.
It supersedes the v3.5.12 handbook for all content related to Phases 5-29.

---

## 1. Current State

| Metric | Value |
|---|---|
| Version | 6.1.0 |
| Python files | 225 |
| Lines of code | 54,563 |
| Bridge methods | 427 |
| Test files | 22 phase-specific + baseline |
| Tests passing | 726 (+ 3 skipped for sandbox deps) |
| AISC shapes | 2,299 (v16.0, locked) |
| Packages | 39 bridge sub-packages |
| MCP dispatcher entries | 624+ |

---

## 2. Architecture Overview

```
virtualoffice/
  main.py                        # pywebview launcher
  mcp_server.py                  # MCP dispatcher (624+ tools)
  bridge/
    api.py                       # Primary bridge class (~8,500+ LOC, 427 methods)
    aisc_validator.py             # AISC v16.0 validation (2,299 shapes) [PROTECTED]
    calculators.py                # Weight, hours, labor, bid totals
    takeoff_controller.py         # Phase 4: 7-stage pipeline orchestrator (v1)
    bid_scanner.py                # Outlook email scan + lead scoring
    page_hasher.py                # Drawing set hash + revision compare
    assembly_costing.py           # Phase 10: connection hardware costs
    risk_scoring.py               # Phase 11: Monte Carlo 1,000-sim confidence
    connection_weight.py          # Phase 12: plate/angle/stiffener estimator
    grade_comparison.py           # Phase 13: A36/A572/A992/A500 comparison
    shop_capacity.py              # Phase 24: utilization-based margin adjustment
    rfi_generator.py              # Phase 21: auto-RFI from missing info
    ai_orchestration/             # LLM routing (Gemini primary, Claude fallback)
    drawing_intel/                # Vision pipeline
      tiled_inference.py          # Low/high DPI ROI + tile extraction
      node_cropper.py             # Phase 2: AABB intersection detection
      detail_vision.py            # Phase 2: Gemini symbol classifier
      connection_check.py         # Bolt capacity + kzone clearance
      visual_diff.py              # Phase 23: ghost overlay (OpenCV)
      model_3d.py                 # Three.js wireframe (STL)
      preprocessor.py             # PDF extraction + sheet classification
      self_healer.py              # Correction recording + firm rules
    exporters/
      tekla_xml_gen.py            # Phase 1: FabSuiteXMLRequest XML
      strumis_export.py           # Phase 6: Strumis ERP XML
      calc_pack_gen.py            # Phase 16: PE-friendly Excel workbook
    vision_tiers/                 # Phase 7: Three-tier vision
      doctr_wrapper.py            # Tier 1: local OCR (guarded)
      gemini_adapter.py           # Tier 2: Gemini shim
      gpt4o_wrapper.py            # Tier 3: OpenRouter GPT-4o (guarded)
      tier_router.py              # Task routing by complexity
      cost_tracker.py             # Per-bid USD ledger
    takeoff_graph/                # Phase 8: LangGraph DAG pipeline (v2)
      state.py                    # TypedDict state shape
      nodes.py                    # Node functions (7 stages)
      graph.py                    # DAG builder + ThreadPool fallback
    cache/
      vision_cache.py             # SHA-256 keyed JSONL cache
    project_memory/               # Phase 9: Project RAG
      memory_store.py             # ChromaDB + JSONL dual-backend
      project_indexer.py          # Post-takeoff indexing
      memory_search.py            # Semantic search over past projects
      backtester.py               # Shape-level BOM diff
    objective_planner/            # Phase 15: natural language objectives
      planner.py                  # Template matching + task chains
      deadline_tracker.py         # Calendar-aware deadline parsing
    cnc/                          # Phase 17: CNC post-processor
      stop_list_gen.py            # CSV for Geka/Sunrise back gauges
      dxf_part_gen.py             # 1:1 DXF via ezdxf (guarded)
      gcode_gen.py                # G-code for Piranha plasma
      dstv_writer.py              # NC1/DSTV for robotic beam lines
      punch_map_gen.py            # PDF overlay via reportlab
    connection_engine/            # Phase 18: delegated connection design
      shear_tab_designer.py       # AISC 360-16 J3/J4, 7 limit states
      base_plate_designer.py      # AISC DG1 + ACI 318
      pynite_bridge.py            # PyNite FEA wrapper (guarded)
    value_engineering/            # Phase 19: VE proposals
      section_optimizer.py        # Lighter shapes from aisc_master.csv
      connection_standardizer.py  # Reduce bolt pattern variety
      ve_report_gen.py            # Combined VE proposal
    cross_verify/                 # Phase 20: multi-model cross-verification
      dual_extract.py             # Same page through Gemini + Claude
      diff_engine.py              # Compare results, flag discrepancies
    spec_auditor/                 # Phase 22: spec-book cost flag scanner
      cost_flag_scanner.py        # 12 cost-impacting pattern matchers
    bid_intake/                   # Phase 25: BuildingConnected API
      buildingconnected.py        # Autodesk Platform Services wrapper
    cloud_watchdog/               # Phase 14: folder monitoring
      watchdog_service.py         # Polling loop, SHA-256 dedup
      onedrive_watcher.py         # M365 Graph delta
      gdrive_watcher.py           # Drive changes.list
    shop_floor/                   # Phase 26: production tracking
      production_tracker.py       # 9-stage state machine, JSONL storage
      qr_generator.py             # QR labels for piece marks (guarded)
      photo_qc.py                 # OpenCV hole detection vs CNC coords
    analytics/                    # Phase 27: post-project analytics
      post_project.py             # Actuals vs estimated comparison
    logistics/                    # Phase 28: delivery + erection
      delivery_tracker.py         # Truck load planning + BOL + sequence
    openhuman/                    # Phase 29: OpenHuman sidecar
      rpc_client.py               # JSON-RPC at localhost:7788
      memory_bridge.py            # Memory Tree queries
      watchdog_bridge.py          # Auto-fetch event subscription
      skill_manifest.py           # "Structural Steel Detective" skill
    workbench/
      correction_lake.py          # Phase 3: Append-only JSONL storage
      correction_bridge.py        # Phase 3: UI-to-backend connector
    learning/
      correction_analyzer.py      # Phase 4: Pattern detection
      prompt_updater.py           # Phase 4: Few-shot prompt supplement
    misc_steel/                   # Phase 5: stairs, railings, plates
      railing_detector.py
      stair_detector.py
      lintel_detector.py
      plate_detector.py
      misc_calculator.py
    agents/                       # Steel price, compliance, pipeline, etc.
  frontend/
    index.html                    # Main GUI
    styles.css                    # CSS (molten theme, append-only)
    app.js                        # JS (2,115+ lines)
    workbench/                    # Phase 3: PDF.js review workbench
  data/
    aisc_master.csv               # 2,299 AISC shapes (canonical) [PROTECTED]
    aisc-shapes-v160-US.csv       # Full 84-column US customary reference
    governance.json               # API keys + config [PROTECTED]
  tests/                          # 22+ test files
```

---

## 3. Phase Manifest (Complete, v3.6.0 to v6.1.0)

| Phase | Version | Deliverable | Tests | Status |
|---|---|---|---|---|
| 1 | v3.6.0 | Tekla PowerFab XML export | 26 | COMPLETE |
| 2 | v3.6.1 | Connection detail vision | 46 | COMPLETE |
| 3 | v3.7.0 | HITL Review Workbench | 25 | COMPLETE |
| 4 | v3.8.0 | Takeoff controller + active learning | 28 | COMPLETE |
| 5 | v3.9.0 | Misc Steel module | 88 | COMPLETE |
| 6 | v3.9.1 | Strumis ERP export | 28 | COMPLETE |
| 7 | v4.0.0 | Three-tier vision (DocTR + Gemini + GPT-4o) | 71 | COMPLETE |
| 8 | v4.1.0 | LangGraph pipeline + speed optimization | 43 | COMPLETE |
| 9 | v4.2.0 | Project RAG + shadow backtesting | 38 | COMPLETE |
| 10 | v4.3.0 | Assembly-based costing | 29 | COMPLETE |
| 11 | v4.3.1 | Monte Carlo risk scoring | 38 (combined) | COMPLETE |
| 12 | v4.4.0 | Connection plate weight | (combined) | COMPLETE |
| 13 | v4.4.1 | What-if grade comparison | (combined) | COMPLETE |
| 14 | v4.5.0 | Cloud folder watchdog | 29 | COMPLETE |
| 15 | v4.6.0 | Objective-based planning | 38 | COMPLETE |
| 16 | v4.7.0 | Auditable calculation pack | 11 | COMPLETE |
| 17 | v4.8.0 | CNC post-processor | 34 | COMPLETE |
| 18 | v5.0.0 | Connection design engine | 30 | COMPLETE |
| 19 | v5.1.0 | Value engineering | 23 | COMPLETE |
| 20 | v5.2.0 | Three-model cross-verification | 25 (combined) | COMPLETE |
| 21 | v5.3.0 | Auto-RFI generator | (combined) | COMPLETE |
| 22 | v5.4.0 | Spec-Book Auditor | 28 (combined) | COMPLETE |
| 23 | v5.5.0 | Ghost Overlay (visual diff) | (combined) | COMPLETE |
| 24 | v5.6.0 | Shop Capacity Bidding | (combined) | COMPLETE |
| 25 | v5.7.0 | BuildingConnected API | (combined) | COMPLETE |
| 26 | v5.8.0 | Shop Floor QC + Production Tracking | 30 (combined) | COMPLETE |
| 27 | v5.9.0 | Post-Project Analytics | (combined) | COMPLETE |
| 28 | v6.0.0 | Delivery + Erection Tracking | (combined) | COMPLETE |
| 29 | v6.1.0 | OpenHuman Sidecar Integration | 18 | COMPLETE |

**Total: 726 tests passing, 3 skipped (sandbox dependency guards).**

---

## 4. Phase Details (Phases 6-29)

### Phase 6: Strumis ERP Export (v3.9.1)

**Module:** `bridge/exporters/strumis_export.py` (175 lines)

Generates Strumis-compatible XML from takeoff data. Same AISC validation gate as Tekla. Schema: StrumisExport root, Item > Component grouping, ItemMark/MaterialGrade naming, separate Length + LengthUnit elements.

**Bridge methods:** `export_strumis_xml()`
**MCP entry:** `export_strumis`

### Phase 7: Three-Tier Vision (v4.0.0)

**Package:** `bridge/vision_tiers/` (5 modules, 1,107 lines)

Three-tier vision pipeline:
- Tier 1 (local, free): DocTR OCR for text extraction. Lazy-loaded, HAS_DOCTR guard.
- Tier 2 (cloud, Gemini): structural detail extraction via existing detail_vision.
- Tier 3 (cloud, GPT-4o): deterministic AISC math verification. OpenRouter client, hard-disabled without API key.

Cost tracker: thread-safe per-bid USD ledger, $1.50 default cap.
Tier router: routes tasks by complexity, escalates on failure, respects cost cap.

**Bridge methods:** `get_vision_tier_status()`, `route_vision_task()`, `reset_vision_tier_tracker()`
**MCP entries:** `tier_status`, `tier_route`, `tier_reset`
**Frontend:** tier status pills in header (DocTR/Gemini/GPT-4o with on/off/pending states)

**Decision:** Tier 3 hard-disabled by default. tier3_enabled=False. Zero risk of unauthorized OpenRouter charge.

### Phase 8: LangGraph Pipeline (v4.1.0)

**Package:** `bridge/takeoff_graph/` (4 modules, 758 lines) + `bridge/cache/vision_cache.py` (164 lines)

LangGraph DAG with ThreadPoolExecutor fallback (same topology, same state shape). Parallel Stage 2 (validate) + Stage 4.5 (misc steel) after Stage 1. Per-node vision fan-out via ThreadPoolExecutor (default 4 workers).

**Bridge methods:** `process_full_takeoff_v2()`, `get_graph_runner_status()`, `clear_vision_cache()`
**MCP entries:** `auto_v2`, `graph_status`, `cache_clear`

**Known bug (v1 only):** v1 controller Stage 6 has two silent zeros: `lc.get("total", 0)` should be `lc.get("total_labor", 0)`, and `bt.get("total", 0)` should be `bt.get("bid_total", 0)`. v1 returns $0 for total_cost. v2 reads correct keys. v1 left untouched for regression parity.

### Phase 9: Project RAG + Shadow Backtesting (v4.2.0)

**Package:** `bridge/project_memory/` (4 modules, 769 lines)

ChromaDB preferred when installed; JSONL keyword-overlap fallback always available. Per-bid deduplication via upsert. Backtester: shape-level BOM diff producing accuracy/precision/recall/tonnage delta.

**Bridge methods:** `search_project_memory()`, `index_project()`, `backtest_project()`, `get_memory_status()`
**MCP entries:** `memory_search`, `memory_index`, `memory_backtest`, `memory_status`
**Frontend:** "SIMILAR PROJECTS" button on bid card

### Phase 10: Assembly-Based Costing (v4.3.0)

**Module:** `bridge/assembly_costing.py` (252 lines)

Assembly costs: B2B=$145, B2C=$175, B2C_MOMENT=$970, C2F=$498, SPLICE=$755, BR2C/BR2B=$425. Default unknown=$200. Integrated into v2 cost_calc_node. Welding hours added to fab_hours.

**Bridge methods:** `compute_assembly_costs()`
**MCP entry:** `assembly_costs`

### Phase 11: Monte Carlo Risk Scoring (v4.3.1)

**Module:** `bridge/risk_scoring.py` (224 lines)

1,000 simulations using Python random module. Variables: material +/-15%, fab hrs +/-20%, erect hrs +/-25%, connection hardware +/-30%, overhead 1.10x-1.20x. Seeded mode for reproducibility.

**Bridge methods:** `run_monte_carlo()`
**MCP entry:** `monte_carlo`

### Phase 12: Connection Plate Weight (v4.4.0)

**Module:** `bridge/connection_weight.py` (248 lines)

Estimates plate/angle/stiffener/base/gusset weight from Phase 2 bolt data. 10-15% rule validation (total connection weight vs structural weight).

**Bridge methods:** `estimate_connection_weight()`
**MCP entry:** `conn_weight`

### Phase 13: What-If Grade Comparison (v4.4.1)

**Module:** `bridge/grade_comparison.py` (162 lines)

A36/A572/A992/A500 comparison with PE warning hardcoded. Pulls pricing from steel_price agent.

**Bridge methods:** `compare_grades()`
**MCP entry:** `grade_compare`

### Phase 14: Cloud Folder Watchdog (v4.5.0)

**Package:** `bridge/cloud_watchdog/` (3 modules)

Daemon thread, 5-min default interval, configurable. SHA-256 dedup prevents re-processing. RAG-aware: auto-indexes detected files. OneDrive via M365 Graph delta, Google Drive via changes.list.

**Bridge methods:** `get_watchdog_status()`, `configure_watchdog()`, `start_watchdog()`, `stop_watchdog()`, `watchdog_poll_now()`
**MCP entries:** `watchdog_status`, `watchdog_config`, `watchdog_start`, `watchdog_stop`, `watchdog_poll`

### Phase 15: Objective-Based Planning (v4.6.0)

**Package:** `bridge/objective_planner/` (3 modules, 453 lines)

Four task templates: bid, followup, reprice, compliance. Each maps a natural-language objective to an ordered task chain of existing Bridge methods. Sequential execution with on_step callback. CrewAI integration guarded (HAS_CREWAI).

Deadline tracker: parses "by Friday," "tomorrow," "end of week," ISO/US dates. Urgency: CRITICAL/TIGHT/NORMAL/RELAXED.

**Bridge methods:** `execute_objective()`, `plan_objective()`
**MCP entries:** `plan_objective`, `exec_objective`

### Phase 16: Auditable Calculation Pack (v4.7.0)

**Module:** `bridge/exporters/calc_pack_gen.py` (279 lines)

PE-friendly Excel workbook with 4 tabs: Summary (project totals), Members (AISC v16.0 Table 1-1 weight per shape), Connections (Phase 10 assembly costs), Rates (Q2 2026 calibration). Uses openpyxl. Navy headers (#1F2A44) for document branding.

**Bridge methods:** `generate_calc_pack()`
**MCP entry:** `calc_pack`

### Phase 17: CNC Post-Processor (v4.8.0)

**Package:** `bridge/cnc/` (6 modules, 652 lines)

Five CNC output formats:
1. **Stop-list CSV** for Geka/Sunrise back gauges (zero deps). Mario's crew loads USB directly.
2. **DXF part drawings** via ezdxf (guarded). 1:1 scale, layers: OUTLINE/HOLES/COPES/DIMENSIONS.
3. **G-code** for Piranha A-series plasma tables (zero deps). Feed rates by thickness.
4. **DSTV/NC1** for robotic beam lines (zero deps). PythonX/Ficep/Voortman compatible.
5. **Punch map PDF** via reportlab. 11x17 printable, color-coded holes with X,Y coordinates.

**Bridge methods:** `generate_stop_list()`, `generate_part_dxf()`, `generate_gcode()`, `generate_dstv()`, `generate_punch_map()`
**MCP entries:** `cnc_stop_list`, `cnc_part_dxf`, `cnc_gcode`, `cnc_dstv`, `cnc_punch_map`

### Phase 18: Connection Design Engine (v5.0.0)

**Package:** `bridge/connection_engine/` (4 modules, 569 lines)

Automates delegated connection design per AISC 303-22 Section 4.4 Option 3. Internalizes ~$20/ton of connection engineering cost.

**Shear tab designer** checks 7 limit states per AISC 360-16 Chapter J:
1. Bolt shear (J3.6) - phi=0.75
2. Bolt bearing (J3.10) - phi=0.75
3. Plate shear yielding (J4.2a) - phi=1.00
4. Plate shear rupture (J4.2b) - phi=0.75
5. Block shear (J4.3) - phi=0.75
6. Weld capacity (J2.4) - phi=0.75
7. Beam web coping (F11)

Auto-sizes bolt count, plate thickness, and weld. GREEN/YELLOW/RED status with DCR.

**Base plate designer** per AISC DG1 + ACI 318: concrete bearing, plate bending, anchor bolt capacity.

**PyNite bridge** for non-standard connections (guarded, HAS_PYNITE).

**Bridge methods:** `design_shear_tab()`, `design_base_plate()`, `verify_connection_fea()`
**MCP entries:** `conn_shear_tab`, `conn_base_plate`, `conn_fea`

### Phase 19: Value Engineering (v5.1.0)

**Package:** `bridge/value_engineering/` (4 modules, 414 lines)

Section optimizer scans AISC v16.0 (2,299 shapes) to find lighter sections in the same family. Connection standardizer reduces bolt size variety. Combined VE report with PE approval requirement.

**Bridge methods:** `run_value_engineering()`
**MCP entry:** `value_engineering`

### Phase 20: Three-Model Cross-Verification (v5.2.0)

**Package:** `bridge/cross_verify/` (3 modules, 233 lines)

Sends same drawing page to multiple AI providers (Gemini + Claude, optionally GPT-4o). Diff engine compares member counts, shapes, piece marks. Agreement boosts confidence (up to +20%). Discrepancies flagged as VERIFY.

**Bridge methods:** `cross_verify()`
**MCP entry:** `cross_verify`

### Phase 21: Auto-RFI Generator (v5.3.0)

**Module:** `bridge/rfi_generator.py` (177 lines)

Scans takeoff results for missing grades, missing lengths, connection ambiguities, and cross-verify discrepancies. Generates numbered RFI items with priority (HIGH/MEDIUM) and pre-written questions.

Categories: MISSING_GRADE, MISSING_LENGTH, SCALE_CONFLICT, CONN_AMBIGUOUS, MEMBER_CONFLICT, SPEC_MISMATCH.

**Bridge methods:** `generate_rfi_log()`
**MCP entry:** `rfi_log`

### Phase 22: Spec-Book Auditor (v5.4.0)

**Package:** `bridge/spec_auditor/` (2 modules, 275 lines)

Scans specification text for 12 cost-impacting requirements:

| Flag | Detection | Impact |
|---|---|---|
| GALVANIZE | "galvaniz", "ASTM A123", "HDG" | +$0.40-0.60/lb |
| BLAST_SP10 | "SSPC-SP10", "near-white" | +$1.50/sqft |
| BLAST_SP6 | "SSPC-SP6", "commercial blast" | +$0.75/sqft |
| SPECIAL_INSPECT | "special inspection", "IBC 1705" | +$5K-15K |
| NDT_FULL | "UT", "ultrasonic", "100% NDT" | +$2K-8K |
| INTUMESCENT | "intumescent", "fire rating" | +$5-15/sqft |
| SEISMIC | "AISC 341", "seismic" | +15-25% labor |
| AESS | "AESS", "architecturally exposed" | +30-50% fab |
| PREVAILING_WAGE | "Davis-Bacon", "prevailing wage" | +20-40% labor |
| BUY_AMERICA | "Buy America", "melted and poured" | +5% material |
| INORGANIC_ZINC | "inorganic zinc", "IOZ primer" | +$3/sqft |
| NO_A36 | "A992 only", "no A36" | eliminates VE |

**Bridge methods:** `audit_spec_book()`
**MCP entry:** `spec_audit`

### Phase 23: Ghost Overlay (v5.5.0)

**Module:** `bridge/drawing_intel/visual_diff.py` (144 lines)

Visual diff between two PDF drawing revisions using OpenCV alignment and pixel-wise subtraction. Red for removed, green for added, gray for unchanged. Reports change percentage.

**Bridge methods:** `ghost_overlay()`
**MCP entry:** `ghost_overlay`

### Phase 24: Shop Capacity-Aware Bidding (v5.6.0)

**Module:** `bridge/shop_capacity.py` (83 lines)

| Utilization | Margin Adjustment | Signal |
|---|---|---|
| <40% (slow) | -3% | "Bid aggressive. Keep crew busy." |
| 40-70% (normal) | +0% | "Standard pricing." |
| 70-85% (busy) | +3% | "Premium pricing recommended." |
| >85% (slammed) | +5-8% | "Very premium or pass." |

**Bridge methods:** `capacity_adjusted_margin()`
**MCP entry:** `capacity_margin`

### Phase 25: BuildingConnected API (v5.7.0)

**Package:** `bridge/bid_intake/` (2 modules, 146 lines)

Polls BuildingConnected (Autodesk) for structural bid invites. Credential-gated (stub until APS credentials configured). Follows cloud_watchdog polling pattern.

**Bridge methods:** `check_bc_status()`, `poll_bid_invites()`
**MCP entries:** `bc_status`, `bc_poll`

### Phase 26: Shop Floor QC + Production Tracking (v5.8.0)

**Package:** `bridge/shop_floor/` (4 modules, 464 lines)

**Production tracker:** 9-stage state machine:
```
ORDERED -> CUT -> FIT_UP -> WELD -> FINISH -> QC_PASS -> SHIPPED -> ERECTED -> INSPECTED
```
JSONL storage per job in data/production/{job_number}.jsonl. Detects pieces stuck >48 hours.

**QR generator:** yourco://status/{job_number}/{piece_mark}. Guarded (qrcode library).

**Photo QC:** OpenCV HoughCircles detects bolt holes in fabrication photos. Compares against CNC coordinates. Flags deviations > 1/16" (AISC tolerance).

**Bridge methods:** `update_piece_status()`, `get_job_production_status()`, `generate_piece_qr()`, `verify_photo_qc()`
**MCP entries:** `piece_status`, `job_production`, `piece_qr`, `photo_qc`

### Phase 27: Post-Project Analytics (v5.9.0)

**Module:** `bridge/analytics/post_project.py` (114 lines)

Compares actual production data to bid estimates. Tonnage/hours/cost variance. Generates lessons and calibration recommendations. If actual hrs/ton > 13, recommends baseline adjustment. If < 9, recommends more aggressive bidding.

**Bridge methods:** `compare_actuals()`
**MCP entry:** `compare_actuals`

### Phase 28: Delivery + Erection Tracking (v6.0.0)

**Package:** `bridge/logistics/` (2 modules, 165 lines)

Truck load planning with weight limits and erection priority. BOL generation. Erection sequence: columns first (priority 0), beams (1), bracing (2), misc (3).

**Bridge methods:** `plan_truck_loads()`, `recommend_erection_order()`
**MCP entries:** `truck_loads`, `erection_order`

### Phase 29: OpenHuman Sidecar Integration (v6.1.0)

**Package:** `bridge/openhuman/` (5 modules, 344 lines)

JSON-RPC 2.0 client at localhost:7788. Graceful fallback when OpenHuman is not running.

- **Memory bridge:** queries Memory Tree for project context (replaces standalone RAG need)
- **Watchdog bridge:** subscribes to auto-fetch events from Drive/OneDrive
- **Skill manifest:** registers "Structural Steel Detective" with triggers and actions

**Bridge methods:** `get_openhuman_status()`, `search_openhuman_memory()`, `register_openhuman_skill()`, `get_openhuman_recent_files()`
**MCP entries:** `oh_status`, `oh_memory`, `oh_register`, `oh_files`

---

## 5. Dependency Matrix

| Library | Phase | Guard | Fallback |
|---|---|---|---|
| DocTR (python-doctr) | 7 | HAS_DOCTR | Falls through to Gemini |
| LangGraph | 8 | HAS_LANGGRAPH | ThreadPoolExecutor |
| ChromaDB | 9 | HAS_CHROMADB | JSONL keyword search |
| CrewAI | 15 | HAS_CREWAI | Sequential execution |
| ezdxf | 17 | HAS_EZDXF | DXF generation skipped |
| PyNiteFEA | 18 | HAS_PYNITE | Closed-form AISC only |
| qrcode | 26 | HAS_QRCODE | URL returned without image |
| OpenHuman | 29 | is_available() | Standalone operation |
| openpyxl | 16 | HAS_OPENPYXL | Calc pack skipped |
| reportlab | 17 | HAS_REPORTLAB | Punch map skipped |
| OpenCV (cv2) | 23, 26 | HAS_CV2 | Visual diff/QC skipped |
| pymupdf (fitz) | 23 | HAS_FITZ | Visual diff skipped |

---

## 6. Mac Mini First-Boot Checklist

```bash
# 1. Core upgrades (free, pip install)
pip install chromadb                # RAG: JSONL -> semantic search
pip install langgraph               # Pipeline: ThreadPool -> DAG
pip install python-doctr[torch]     # Tier 1: local OCR
pip install crewai                  # Planner: sequential -> multi-agent
pip install ezdxf gscrib            # CNC: DXF + G-code output
pip install PyNiteFEA               # Connection: FEA verification
pip install qrcode                  # Shop floor: QR labels

# 2. API keys (in data/governance.json)
# vision_tiers.openrouter_api_key   -> enables Tier 3 GPT-4o
# building_connected.client_id      -> enables BC bid intake
# building_connected.client_secret

# 3. OpenHuman sidecar (optional)
# Install from tinyhumans.ai/openhuman
# Connect Google Drive + Gmail via one-click OAuth
# Virtual office detects at localhost:7788 on startup

# 4. Use v2 pipeline for production bids
# process_full_takeoff_v2() reads correct cost keys
# v1 has a known $0 cost bug in Stage 6
```

---

## 7. Critical Rules (unchanged from v3.5.12)

1. ZERO EM-DASHES ANYWHERE. Hyphens (-) or periods only.
2. AISC VALIDATOR IS THE SINGLE SOURCE OF TRUTH. 2,299 shapes.
3. AI NEVER DOES ARITHMETIC. All math in calculators.py.
4. NO PAID DEPENDENCIES BEYOND THE STACK.
5. PYWEBVIEW ARCHITECTURE. No REST endpoints.
6. TEST EVERYTHING.
7. THE OWNER'S VOICE RULES. No "leverage," "synergy," "streamline."
8. MOLTEN ORANGE (#ff5f00) IS THE GUI THEME.
9. PROTECTED FILES: aisc_validator.py, prompts.py, governance.json, aisc_master.csv. styles.css append-only. installer.nsi version-bump only.
10. NO SUPPLIER NAMES IN CLIENT-FACING DOCUMENTS.

---

## 8. Full Lifecycle Coverage

```
BID INTAKE ............ Phases 14 (watchdog), 25 (BuildingConnected), 29 (OpenHuman)
DRAWING ANALYSIS ...... Phases 1-5 (takeoff), 7 (vision tiers), 8 (LangGraph), 20 (cross-verify)
SPEC AUDIT ............ Phase 22 (cost flag scanner)
BID PRICING ........... Phases 10-13 (assembly/MC/plate/grade), 24 (shop capacity)
BID DOCUMENTS ......... Phases 16 (calc pack), 21 (auto-RFI), 19 (VE proposal)
CONNECTION DESIGN ..... Phase 18 (AISC 360-16 engine)
CNC OUTPUT ............ Phase 17 (stop-list/DXF/G-code/DSTV/punch-map)
SHOP PRODUCTION ....... Phase 26 (state machine + QR + photo QC)
DELIVERY .............. Phase 28 (truck loads + BOL + erection sequence)
PROJECT CLOSEOUT ...... Phase 27 (actuals vs estimated)
MEMORY + LEARNING ..... Phases 4 (corrections), 9 (RAG), 15 (objectives), 29 (OpenHuman)
REVISION TRACKING ..... Phase 23 (ghost overlay)
```

---

## 9. Verification Checklist

```bash
# 1. Bracket balance
grep -o '{' frontend/app.js | wc -l   # must match } count
grep -o '<div' frontend/index.html | wc -l  # must match </div> count

# 2. Em-dash sweep (ZERO tolerance)
grep -r '\xe2\x80\x94' frontend/ bridge/ tests/ --include='*.py' --include='*.js' --include='*.html'
# Must return NOTHING

# 3. AISC shape count
python -c "import csv; print(sum(1 for _ in csv.reader(open('data/aisc_master.csv')))-1)"
# Must print 2299

# 4. Protected files unchanged
diff -q BASELINE/bridge/aisc_validator.py bridge/aisc_validator.py
diff -q BASELINE/bridge/ai_orchestration/prompts.py bridge/ai_orchestration/prompts.py
diff -q BASELINE/data/governance.json data/governance.json
diff -q BASELINE/data/aisc_master.csv data/aisc_master.csv

# 5. Run all phase tests
python -m pytest tests/test_phase*.py tests/test_tekla_export.py --tb=short -q
# Must show 726+ passed
```

---

## 10. MCP Dispatcher Entries (Phases 6-29)

All entries are in the `drawing_intel` dispatcher block of `mcp_server.py`:

```python
"export_strumis":   "export_strumis_xml",      # Phase 6
"tier_status":      "get_vision_tier_status",   # Phase 7
"tier_route":       "route_vision_task",        # Phase 7
"tier_reset":       "reset_vision_tier_tracker",# Phase 7
"auto_v2":          "process_full_takeoff_v2",  # Phase 8
"graph_status":     "get_graph_runner_status",  # Phase 8
"cache_clear":      "clear_vision_cache",       # Phase 8
"memory_search":    "search_project_memory",    # Phase 9
"memory_index":     "index_project",            # Phase 9
"memory_backtest":  "backtest_project",         # Phase 9
"memory_status":    "get_memory_status",        # Phase 9
"assembly_costs":   "compute_assembly_costs",   # Phase 10
"monte_carlo":      "run_monte_carlo",          # Phase 11
"conn_weight":      "estimate_connection_weight",# Phase 12
"grade_compare":    "compare_grades",           # Phase 13
"watchdog_status":  "get_watchdog_status",      # Phase 14
"watchdog_config":  "configure_watchdog",       # Phase 14
"watchdog_start":   "start_watchdog",           # Phase 14
"watchdog_stop":    "stop_watchdog",            # Phase 14
"watchdog_poll":    "watchdog_poll_now",        # Phase 14
"plan_objective":   "plan_objective",           # Phase 15
"exec_objective":   "execute_objective",        # Phase 15
"calc_pack":        "generate_calc_pack",       # Phase 16
"cnc_stop_list":    "generate_stop_list",       # Phase 17
"cnc_part_dxf":     "generate_part_dxf",        # Phase 17
"cnc_gcode":        "generate_gcode",           # Phase 17
"cnc_dstv":         "generate_dstv",            # Phase 17
"cnc_punch_map":    "generate_punch_map",       # Phase 17
"conn_shear_tab":   "design_shear_tab",         # Phase 18
"conn_base_plate":  "design_base_plate",        # Phase 18
"conn_fea":         "verify_connection_fea",    # Phase 18
"value_engineering":"run_value_engineering",     # Phase 19
"cross_verify":     "cross_verify",             # Phase 20
"rfi_log":          "generate_rfi_log",         # Phase 21
"spec_audit":       "audit_spec_book",          # Phase 22
"ghost_overlay":    "ghost_overlay",            # Phase 23
"capacity_margin":  "capacity_adjusted_margin", # Phase 24
"bc_status":        "check_bc_status",          # Phase 25
"bc_poll":          "poll_bid_invites",          # Phase 25
"piece_status":     "update_piece_status",      # Phase 26
"job_production":   "get_job_production_status", # Phase 26
"piece_qr":         "generate_piece_qr",        # Phase 26
"photo_qc":         "verify_photo_qc",          # Phase 26
"compare_actuals":  "compare_actuals",          # Phase 27
"truck_loads":      "plan_truck_loads",          # Phase 28
"erection_order":   "recommend_erection_order", # Phase 28
"oh_status":        "get_openhuman_status",     # Phase 29
"oh_memory":        "search_openhuman_memory",  # Phase 29
"oh_register":      "register_openhuman_skill", # Phase 29
"oh_files":         "get_openhuman_recent_files",# Phase 29
```

---

## 11. Test File Map

| Test File | Phase(s) | Tests |
|---|---|---|
| test_tekla_export.py | 1 | 26 |
| test_phase2_detail_vision.py | 2 | 46 |
| test_phase3_workbench.py | 3 | 25 |
| test_phase4_controller.py | 4 | 28 |
| test_phase5_misc_steel.py | 5 | 88 |
| test_phase6_strumis.py | 6 | 28 |
| test_phase7a_vision_tiers.py | 7a | 36 |
| test_phase7b_vision_integration.py | 7b | 35 |
| test_phase8_langgraph.py | 8 | 43 |
| test_phase9_project_rag.py | 9 | 38 |
| test_phase10_assembly_costing.py | 10 | 29 |
| test_phase11_12_13_bid_intelligence.py | 11-13 | 38 |
| test_phase14_cloud_watchdog.py | 14 | 29 |
| test_phase15_objective_planner.py | 15 | 38 |
| test_phase16_calc_pack.py | 16 | 11 |
| test_phase17_cnc.py | 17 | 34 |
| test_phase18_connection_engine.py | 18 | 30 |
| test_phase19_value_engineering.py | 19 | 23 |
| test_phase20_21_verify_rfi.py | 20-21 | 25 |
| test_phase22_25_final.py | 22-25 | 28 |
| test_phase26_28_shop_lifecycle.py | 26-28 | 30 |
| test_phase29_openhuman.py | 29 | 18 |

---

## 12. Competitive Position After v6.1.0

No single competitor covers this entire lifecycle:

| Capability | Sketchdeck | Beam AI | Togal | ProEst | Your Company v6.1.0 |
|---|---|---|---|---|---|
| Structural takeoff | Yes | Yes | Yes | No | Yes (2,299 shapes) |
| Misc steel | No | Yes | Partial | No | Yes |
| Connection details | Yes | No | No | No | Yes |
| Tekla + Strumis export | Tekla only | No | No | No | Both |
| Assembly costing | No | No | No | Yes | Yes |
| Monte Carlo risk | No | No | No | No | Yes |
| Connection design | No | No | No | No | Yes (AISC 360-16) |
| Value engineering | No | No | No | No | Yes |
| CNC output | No | No | No | No | Yes (5 formats) |
| Spec auditor | No | No | No | No | Yes (12 flags) |
| Ghost overlay | No | No | No | No | Yes (OpenCV) |
| Shop floor tracking | STRUMIS | No | No | No | Yes (9-stage) |
| Delivery tracking | STRUMIS | No | No | No | Yes |
| Post-project analytics | No | No | No | No | Yes |
| Bid generation | No | No | No | Yes | Yes |
| Offline operation | No | No | No | No | Yes |
| ISN compliance | No | No | No | No | Yes (59 checks) |
| Cost | $$$$/month | $$$$/month | $$$$/month | $$$$/month | $0 marginal |

---

End of Your Company Virtual Office v6.1.0 Developer Handbook.
Full lifecycle: bid intake through project closeout.
Single source of truth for rebuilding the system.
