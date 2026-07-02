"""
Takeoff Controller - Full Pipeline Orchestrator
=================================================
Phase 4 of the Sketchdeck parity roadmap (v3.8.0).

Single entry point that chains all 7 stages of the structural takeoff:
  1. Extract: pdfplumber text + page classification
  2. Validate: AISC v16.0 shape verification (2,299 shapes)
  3. Map nodes: AABB intersection detection (node_cropper)
  4. Detail pass: Gemini vision for moments/copes/studs/camber
  5. Calculate: steel weight from AISC lb/ft lookup
  6. Estimate: bid pricing at Q2 2026 rates
  7. Output: workbench data, Tekla XML, or direct bid generation

This replaces manual chaining of individual modules. Drop a PDF,
get a fully priced takeoff with connection details.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("takeoff_controller")


@dataclass
class TakeoffResult:
    """Complete result from a full takeoff pipeline run."""
    project_id: str = ""
    project_name: str = ""
    pdf_path: str = ""
    building_sf: float = 0.0
    building_type: str = "retail_small"

    # Stage 1: Extraction
    pages_processed: int = 0
    structural_pages: int = 0
    raw_members: list = field(default_factory=list)

    # Stage 2: Validation
    valid_members: list = field(default_factory=list)
    rejected_members: list = field(default_factory=list)

    # Stage 3: Connection nodes
    nodes: list = field(default_factory=list)

    # Stage 4: Detail vision
    details: list = field(default_factory=list)

    # Stage 4.5: Misc steel (Phase 5)
    misc_items: dict = field(default_factory=dict)
    misc_lbs: float = 0.0
    misc_tons: float = 0.0
    misc_warnings: list = field(default_factory=list)

    # Stage 5: Weight calculation
    total_lbs: float = 0.0
    total_tons: float = 0.0
    extracted_tonnage: float = 0.0

    # Stage 6: Pricing
    fab_hours: float = 0.0
    erect_hours: float = 0.0
    total_cost: float = 0.0
    cost_per_ton: float = 0.0

    # Stage 6.5: Sanity Gates
    sanity_confidence: int = 0
    sanity_decision: str = ""
    sanity_gates: list = field(default_factory=list)
    sanity_blocked: bool = False
    market_adjusted_bid: float = 0.0

    # Metadata
    stages_completed: list = field(default_factory=list)
    elapsed_seconds: float = 0.0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "pdf_path": self.pdf_path,
            "pages_processed": self.pages_processed,
            "structural_pages": self.structural_pages,
            "member_count": len(self.valid_members),
            "rejected_count": len(self.rejected_members),
            "node_count": len(self.nodes),
            "detail_count": len(self.details),
            "total_lbs": round(self.total_lbs, 1),
            "total_tons": round(self.total_tons, 2),
            "extracted_tonnage": round(self.extracted_tonnage, 2),
            "misc_lbs": round(self.misc_lbs, 1),
            "misc_tons": round(self.misc_tons, 4),
            "misc_items": self.misc_items,
            "misc_warnings": self.misc_warnings,
            "fab_hours": round(self.fab_hours, 1),
            "erect_hours": round(self.erect_hours, 1),
            "total_cost": round(self.total_cost, 2),
            "cost_per_ton": round(self.cost_per_ton, 2),
            "stages_completed": self.stages_completed,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "errors": self.errors,
            "warnings": self.warnings,
            "members": self.valid_members,
            "nodes": self.nodes,
            "details": self.details,
            "sanity_confidence": self.sanity_confidence,
            "sanity_decision": self.sanity_decision,
            "sanity_gates": self.sanity_gates,
            "sanity_blocked": self.sanity_blocked,
            "market_adjusted_bid": round(self.market_adjusted_bid, 2),
        }


def process_full_takeoff(
    pdf_path: str,
    project_id: str = "",
    project_name: str = "",
    skip_vision: bool = False,
    skip_pricing: bool = False,
    building_sf: float = 0.0,
    building_type: str = "retail_small",
    complexity: str = "standard",
    call_provider=None,
) -> TakeoffResult:
    """Run the complete takeoff pipeline on a structural PDF.

    Args:
        pdf_path: Path to the structural drawing PDF
        project_id: Bid number (e.g., "PRJ-2026-HOU-0042")
        project_name: Human-readable project name
        skip_vision: If True, skip Gemini vision for connection details
        skip_pricing: If True, skip cost estimation
        complexity: "standard", "complex", or "simple" for hours calc
        call_provider: Gemini vision callable (injected from bridge)

    Returns:
        TakeoffResult with complete pipeline data.
    """
    t0 = time.time()
    result = TakeoffResult(
        project_id=project_id,
        project_name=project_name,
        pdf_path=str(pdf_path),
        building_sf=building_sf,
        building_type=building_type,
    )

    path = Path(pdf_path)
    if not path.exists():
        result.errors.append(f"PDF not found: {pdf_path}")
        result.elapsed_seconds = time.time() - t0
        return result

    # Pages are populated by Stage 1 and reused by Stage 4.5 for misc
    # steel detection. Initialize empty so the misc stage stays a no-op
    # if extraction fails.
    pages: list = []

    # ── Stage 1: Extract ────────────────────────────────────────────
    try:
        from bridge.drawing_intel.preprocessor import extract_drawing_set
        extraction = extract_drawing_set(str(path))

        if "error" in extraction:
            result.errors.append(f"Extraction failed: {extraction['error']}")
            result.elapsed_seconds = time.time() - t0
            return result

        pages = extraction.get("pages", [])
        result.pages_processed = len(pages)
        result.structural_pages = sum(
            1 for p in pages if p.get("has_structural", False)
        )

        # Collect member-like data from structured content
        for page in pages:
            md = page.get("markdown", "")
            jd = page.get("json_data", {})
            if isinstance(jd, dict):
                members = jd.get("members", [])
                if isinstance(members, list):
                    for m in members:
                        if isinstance(m, dict) and m.get("shape"):
                            m.setdefault("page_num", page.get("page_num", 0))
                            result.raw_members.append(m)

        # Auto-derive building_sf and extracted_tonnage from page metadata.
        # Preprocessor may return these from architectural notes or title block.
        if result.building_sf == 0:
            _sf_keys = ("building_sf", "gross_area_sf", "total_area_sf", "area_sf")
            for _pg in pages:
                _jd = _pg.get("json_data") or {}
                if not isinstance(_jd, dict):
                    continue
                for _k in _sf_keys:
                    _v = _jd.get(_k)
                    if isinstance(_v, (int, float)) and _v > 0:
                        result.building_sf = float(_v)
                        log.info(f"Stage 1: building_sf={result.building_sf} from page {_pg.get('page_num')}")
                        break
                if result.building_sf > 0:
                    break

        _ton_keys = ("total_tonnage", "total_steel_tons", "steel_tons", "structural_tons")
        for _pg in pages:
            _jd = _pg.get("json_data") or {}
            if not isinstance(_jd, dict):
                continue
            for _k in _ton_keys:
                _v = _jd.get(_k)
                if isinstance(_v, (int, float)) and _v > 0:
                    result.extracted_tonnage = float(_v)
                    log.info(f"Stage 1: extracted_tonnage={result.extracted_tonnage} from page {_pg.get('page_num')}")
                    break
            if result.extracted_tonnage > 0:
                break

        result.stages_completed.append("extract")
        log.info(f"Stage 1: Extracted {len(result.raw_members)} raw members "
                 f"from {result.pages_processed} pages")
    except Exception as e:
        result.errors.append(f"Stage 1 (extract): {e}")
        log.error(f"Stage 1 failed: {e}")

    # ── Stage 2: AISC Validation ────────────────────────────────────
    try:
        from bridge.aisc_validator import validate_shape

        for m in result.raw_members:
            shape = m.get("shape") or m.get("normalized") or ""
            vr = validate_shape(shape)
            if vr.get("valid", False):
                m["aisc_valid"] = True
                m["confidence"] = max(m.get("confidence", 0.8), 0.8)
                result.valid_members.append(m)
            else:
                m["aisc_valid"] = False
                result.rejected_members.append(m)
                result.warnings.append(
                    f"Rejected: {shape} not in AISC v16.0"
                )

        result.stages_completed.append("validate")
        log.info(f"Stage 2: {len(result.valid_members)} valid, "
                 f"{len(result.rejected_members)} rejected")
    except Exception as e:
        result.errors.append(f"Stage 2 (validate): {e}")
        # Fall through with raw members
        result.valid_members = result.raw_members

    # ── Stage 3: Node Mapping ───────────────────────────────────────
    try:
        from bridge.drawing_intel.node_cropper import (
            find_connection_nodes, nodes_to_dicts,
        )

        nodes = find_connection_nodes(
            result.valid_members,
            pdf_path=str(path),
            generate_crops=not skip_vision,
        )
        result.nodes = nodes_to_dicts(nodes)
        result.stages_completed.append("node_map")
        log.info(f"Stage 3: {len(result.nodes)} connection nodes found")
    except Exception as e:
        result.errors.append(f"Stage 3 (node_map): {e}")
        log.error(f"Stage 3 failed: {e}")

    # ── Stage 4: Detail Vision ──────────────────────────────────────
    if not skip_vision and result.nodes:
        try:
            from bridge.drawing_intel.node_cropper import find_connection_nodes
            from bridge.drawing_intel.detail_vision import (
                analyze_nodes as _analyze_nodes,
                merge_details_into_takeoff,
            )

            # Re-fetch nodes with crop data for vision
            raw_nodes = find_connection_nodes(
                result.valid_members,
                pdf_path=str(path),
                generate_crops=True,
            )

            details = _analyze_nodes(
                raw_nodes,
                call_provider=call_provider,
            )
            result.details = details

            # Build node-to-member map
            node_map = {
                n.node_id: n.members for n in raw_nodes
            }

            # Merge details (camber, studs, moment) into member data
            merge_details_into_takeoff(
                result.valid_members, details, node_map
            )

            result.stages_completed.append("detail_vision")
            moments = sum(1 for d in details if d.get("moment"))
            log.info(f"Stage 4: {len(details)} details extracted, "
                     f"{moments} moment frames")
        except Exception as e:
            result.errors.append(f"Stage 4 (detail_vision): {e}")
            log.error(f"Stage 4 failed: {e}")
    elif skip_vision:
        result.stages_completed.append("detail_vision_skipped")

    # ── Stage 4.5: Misc Steel Detection (Phase 5) ───────────────────
    # Detects railings, stairs, lintels, and connection plates that the
    # structural-only pipeline misses. Adds 5-15 percent of typical
    # project tonnage. Runs on the same page text Stage 1 collected, so
    # the cost is one regex pass per structural page.
    try:
        from bridge.misc_steel import detect_misc_steel
        if pages:
            rollup = detect_misc_steel(pages)
        else:
            rollup = detect_misc_steel("")
        result.misc_items = rollup
        result.misc_lbs = float(rollup.get("total_weight_lbs", 0) or 0)
        result.misc_tons = float(rollup.get("total_tons", 0) or 0)
        for w in rollup.get("warnings", []) or []:
            result.misc_warnings.append(w)
        result.stages_completed.append("misc_steel")
        log.info(
            f"Stage 4.5: misc steel {result.misc_tons:.4f} tons "
            f"({result.misc_lbs:.0f} lbs). "
            f"Railings: {rollup.get('railings', {}).get('count', 0)}, "
            f"Stairs: {rollup.get('stairs', {}).get('count', 0)}, "
            f"Lintels: {rollup.get('lintels', {}).get('count', 0)}, "
            f"Plates: {rollup.get('plates', {}).get('count', 0)}."
        )
    except Exception as e:
        result.errors.append(f"Stage 4.5 (misc_steel): {e}")
        log.error(f"Stage 4.5 failed: {e}")

    # ── Stage 5: Weight Calculation ─────────────────────────────────
    try:
        from bridge.calculators import steel_weight

        # Build items list: (shape, length_ft, qty)
        items = []
        for m in result.valid_members:
            shape = m.get("shape") or m.get("normalized") or ""
            length = float(m.get("length_ft", 0) or 0)
            qty = int(m.get("qty", 1) or 1)
            if shape and length > 0:
                items.append((shape, length, qty))

        if items:
            wt = steel_weight(items)
            result.total_lbs = wt.get("total_lbs", 0.0)
            result.total_tons = wt.get("tons", 0.0)
            if wt.get("unknown_shapes"):
                for s in wt["unknown_shapes"]:
                    result.warnings.append(f"Weight lookup missed: {s}")

        # Phase 5: roll misc steel into the project totals so Stage 6
        # prices the full tonnage. Misc subtotals stay accessible via
        # result.misc_lbs / result.misc_items for the bid breakdown.
        if result.misc_lbs > 0:
            result.total_lbs += result.misc_lbs
            result.total_tons = result.total_lbs / 2000.0

        result.stages_completed.append("weight_calc")
        log.info(f"Stage 5: {result.total_tons:.2f} tons "
                 f"({result.total_lbs:.0f} lbs, "
                 f"misc {result.misc_lbs:.0f} lbs included)")
    except Exception as e:
        result.errors.append(f"Stage 5 (weight_calc): {e}")
        log.error(f"Stage 5 failed: {e}")

    # ── Stage 6: Cost Estimation (CEO-locked BID_RATES) ────────────
    # Internal calculators are for cost-basis tracking only. Client-
    # facing bid total must use BID_RATES (Hard Rule #6).
    if not skip_pricing and result.total_tons > 0:
        try:
            from bridge.bid_rates import BID_RATES as _BR, price_bid_line as _pbl
            from bridge.calculators import hours_estimate

            # Track hours for internal cost basis (never in proposal)
            hrs = hours_estimate(result.total_tons, complexity=complexity)
            result.fab_hours = hrs.get("fab_hours", 0)
            result.erect_hours = hrs.get("erect_hours", 0)
            moment_count = sum(
                1 for m in result.valid_members
                if m.get("moment", False)
            )
            if moment_count > 0:
                moment_adjustment = moment_count * 8.0
                result.fab_hours += moment_adjustment
                result.warnings.append(
                    f"{moment_count} moment frames detected. "
                    f"Added {moment_adjustment:.0f} fab hours."
                )

            # Price using locked BID_RATES - this is the client-facing number
            fab_line   = _pbl("fab",      result.total_tons)
            erect_line = _pbl("erection", result.total_tons)
            result.total_cost = fab_line["total"] + erect_line["total"]
            result.cost_per_ton = (
                result.total_cost / result.total_tons
                if result.total_tons > 0 else 0
            )

            result.stages_completed.append("pricing")
            log.info(f"Stage 6 (BID_RATES): ${result.total_cost:,.0f} total "
                     f"(${result.cost_per_ton:,.0f}/ton)")
        except Exception as e:
            result.errors.append(f"Stage 6 (pricing): {e}")
            log.error(f"Stage 6 failed: {e}")
    elif skip_pricing:
        result.stages_completed.append("pricing_skipped")

    # -- Stage 6.5: Sanity Gates ----------------------------------------
    # Runs after pricing. Catches undertonnage and underpricing before
    # any proposal PDF is generated. If blocked, the bid requires
    # the Owner's manual review before submission.
    # Root cause: Owner email May 6 2026 "CLAUDE FOR MISTAKES"
    try:
        from bridge.bid_sanity_gates import (
            run_gates, PRICE_BENCHMARKS,
            red_light_check, tonnage_ceiling_check,
        )
        gate_data = {
            'building_sf': result.building_sf,
            'building_type': result.building_type,
            'struct_tons': 0,
            'joist_tons': 0,
            'total_bid': result.total_cost,
            'grid_bays': [],
            'eq_spa_annotations': [],
            'text_joist_count': len([
                m for m in result.valid_members
                if 'K' in (m.get('shape','') or '') and 'HSS' not in (m.get('shape','') or '')
            ]),
            'found_scope_items': [],
        }
        # Populate from extraction metadata if available
        for m in result.valid_members:
            shape = (m.get('shape') or '').upper()
            if shape.startswith('W') or shape.startswith('HSS'):
                if 'structural_columns' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('structural_columns')
                if 'beams_girders' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('beams_girders')
            if 'K' in shape and 'HSS' not in shape:
                if 'bar_joists' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('bar_joists')
            if 'G' in shape and 'N' in shape:
                if 'joist_girders' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('joist_girders')
            if 'L' in shape:
                if 'bracing' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('bracing')
                if 'misc_angles_plates' not in gate_data['found_scope_items']:
                    gate_data['found_scope_items'].append('misc_angles_plates')

        # Tonnage ceiling check - runs regardless of building_sf
        ceil_result = tonnage_ceiling_check(result.total_tons, result.building_type)
        if not ceil_result["ok"]:
            result.sanity_blocked = True
            result.sanity_decision = "BLOCKED - SUSPECT TONNAGE"
            result.warnings.append(ceil_result["warning"])
            log.warning(f"Stage 6.5: {ceil_result['warning']}")

        # Red-light check: compare PDF-stated tonnage vs AISC-calculated
        rl_result = red_light_check(result.extracted_tonnage, result.total_tons)
        if not rl_result["ok"] and not rl_result.get("skipped"):
            result.sanity_blocked = True
            result.warnings.append(rl_result["warning"])
            log.warning(f"Stage 6.5 red-light: {rl_result['warning']}")

        # Full gate suite requires building_sf
        if gate_data['building_sf'] > 0:
            gr = run_gates(gate_data)
            result.sanity_confidence = gr['confidence']
            result.sanity_decision = gr['decision']
            result.sanity_gates = gr['gates']
            result.sanity_blocked = result.sanity_blocked or gr['blocked']

            # Calculate market-adjusted bid
            bench = PRICE_BENCHMARKS.get(gate_data['building_type'], {})
            if bench.get('mid') and gate_data['building_sf'] > 0:
                result.market_adjusted_bid = bench['mid'] * gate_data['building_sf']

            if gr['blocked']:
                result.warnings.append(
                    f"SANITY GATE BLOCKED (confidence {gr['confidence']}/100). "
                    f"Market-adjusted bid: ${result.market_adjusted_bid:,.0f}. "
                    f"DO NOT SUBMIT without Owner review."
                )
            for g in gr['gates']:
                if g.get('warning'):
                    result.warnings.append(f"Gate {g['gate']}: {g['warning']}")

            result.stages_completed.append("sanity_gates")
            log.info(f"Stage 6.5: Confidence {gr['confidence']}/100 - {gr['decision']}")
        else:
            # building_sf unknown - block rather than silently skip
            result.sanity_blocked = True
            if not result.sanity_decision:
                result.sanity_decision = "BLOCKED - building_sf required"
            result.warnings.append(
                "building_sf required for sanity gates - provide project SF to enable checks."
            )
            result.stages_completed.append("sanity_gates_skipped")
            log.warning("Stage 6.5: building_sf=0 - gates blocked, manual review required")
    except Exception as e:
        result.errors.append(f"Stage 6.5 (sanity_gates): {e}")
        log.error(f"Stage 6.5 failed: {e}")

    result.elapsed_seconds = time.time() - t0
    log.info(f"Takeoff complete: {len(result.stages_completed)} stages in "
             f"{result.elapsed_seconds:.1f}s")
    return result
