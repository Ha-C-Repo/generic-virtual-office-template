"""Node functions for the takeoff graph.

Each node takes a state dict, mutates it in place, and returns it. The
graph runner is responsible for ordering and parallelism. Inside any
node we are free to use ThreadPoolExecutor for fan-out (Stage 4 vision
calls do this).

Each node is wrapped with a `_timed` decorator that records duration
into state["timings_ms"][stage_name]. The frontend uses these to show
the user where a long bid spent its time.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


def _timed(stage_name: str):
    """Decorator that records duration into state["timings_ms"]."""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(state: dict, *args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(state, *args, **kwargs)
                return result
            finally:
                dur_ms = (time.perf_counter() - t0) * 1000.0
                timings = state.setdefault("timings_ms", {})
                timings[stage_name] = round(dur_ms, 2)
        return wrapper
    return decorator


# ── Stage 1: Extract ──────────────────────────────────────────────────────

@_timed("stage1_extract")
def extract_node(state: dict) -> dict:
    """Extract raw members and page text from the PDF."""
    try:
        from bridge.drawing_intel.preprocessor import extract_drawing_set
        path = Path(state["pdf_path"])
        if not path.exists():
            state["errors"].append(f"pdf_not_found: {path}")
            return state

        result = extract_drawing_set(str(path))
        state["raw_members"] = result.get("members", [])
        state["pages"] = result.get("pages", [])
        state["stages_completed"].append("extract")
        log.info("stage1_extract: %d raw members, %d pages",
                 len(state["raw_members"]), len(state["pages"]))
    except Exception as e:
        state["errors"].append(f"stage1_extract: {e}")
        log.error("stage1_extract failed: %s", e)
    return state


# ── Stage 2: AISC Validation ──────────────────────────────────────────────

@_timed("stage2_validate")
def validate_node(state: dict) -> dict:
    """Validate raw members against AISC v16.0. Non-bypassable gate.

    Every member is validated. Failures are logged with shape, reason,
    and top suggestions. No silent passthrough: rejected shapes never
    reach node_map, detail_vision, weight_calc, or cost_calc.

    If rejection rate exceeds 50%, an error is added so the bid scorecard
    and go-no-go review can flag the takeoff for manual inspection.
    """
    try:
        from bridge.aisc_validator import validate_shape

        valid: list = []
        rejected: list = []
        vlog: list = []

        for m in state.get("raw_members", []):
            shape = f"{m.get('shape', '')}{m.get('size', '')}"
            r = validate_shape(shape)
            if r.get("valid", False):
                entry = {
                    "shape": shape,
                    "status": "pass",
                    "normalized": r.get("normalized", shape),
                    "confidence": r.get("confidence", ""),
                    "weight_per_ft": r.get("weight_per_ft", 0.0),
                }
                valid.append(m)
            else:
                entry = {
                    "shape": shape,
                    "status": "fail",
                    "normalized": r.get("normalized", shape),
                    "confidence": "unknown",
                    "reason": r.get("message", "not_in_aisc_v16"),
                    "suggestions": r.get("suggestions", [])[:3],
                }
                rejected.append(shape)
            vlog.append(entry)

        state["valid_members"] = valid
        state["rejected_shapes"] = rejected

        # Append three-pass disputed entries to validation_log (informational).
        for disputed in state.get("disagreement_report", []):
            vlog.append({
                "shape": disputed.get("shape", ""),
                "status": "disputed",
                "grid_anchor": disputed.get("grid_anchor", ""),
                "vote_count": disputed.get("vote_count", 0),
                "passes_seen": disputed.get("passes_seen", []),
                "note": disputed.get("note", ""),
            })

        state["validation_log"] = vlog
        state["stages_completed"].append("validate")

        total = len(vlog)
        n_fail = len(rejected)
        if n_fail > 0:
            pct = round(n_fail / total * 100, 1) if total else 0.0
            state["warnings"].append(
                f"aisc_gate_rejected_{n_fail}_of_{total}_shapes_{pct}pct"
            )
            log.warning(
                "stage2_validate: %d/%d shapes rejected by AISC v16.0 gate",
                n_fail, total,
            )
            if total > 0 and n_fail / total > 0.5:
                state["errors"].append(
                    f"aisc_rejection_rate_exceeds_50pct:{n_fail}/{total}_shapes_failed"
                )

        log.info("stage2_validate: %d valid, %d rejected", len(valid), len(rejected))
    except Exception as e:
        state["errors"].append(f"stage2_validate:{e}")
        log.error("stage2_validate failed: %s", e)
    return state


# ── Stage 3: Node Mapping ─────────────────────────────────────────────────

@_timed("stage3_node_map")
def node_map_node(state: dict) -> dict:
    """Find connection nodes (AABB intersections) without crops."""
    try:
        if state.get("skip_vision"):
            state["stages_completed"].append("node_map_skipped")
            return state

        from bridge.drawing_intel.node_cropper import find_connection_nodes
        nodes = find_connection_nodes(
            state.get("valid_members", []),
            pdf_path=state["pdf_path"],
            generate_crops=False,
        )
        # Convert to dicts so the state stays JSON-serializable
        state["nodes"] = [
            {"node_id": getattr(n, "node_id", str(i)),
             "members": list(getattr(n, "members", []))}
            for i, n in enumerate(nodes)
        ]
        state["_raw_nodes"] = nodes  # keep refs for stage 4
        state["stages_completed"].append("node_map")
        log.info("stage3_node_map: %d connection nodes", len(nodes))
    except Exception as e:
        state["errors"].append(f"stage3_node_map: {e}")
        log.error("stage3_node_map failed: %s", e)
    return state


# ── Stage 4: Detail Vision (parallel, cached) ─────────────────────────────

@_timed("stage4_detail_vision")
def detail_vision_node(state: dict) -> dict:
    """Per-node vision calls. Fan out across ThreadPoolExecutor.

    Each node's crop is hashed and looked up in the vision cache before
    calling the LLM. Cache hits skip the API round-trip entirely.
    """
    if state.get("skip_vision"):
        state["stages_completed"].append("detail_vision_skipped")
        return state

    if not state.get("nodes"):
        state["stages_completed"].append("detail_vision_skipped")
        return state

    try:
        # Three-pass mode: run ROI + 4x4 + 6x6 tile extraction and vote.
        if state.get("three_pass_enabled"):
            try:
                from bridge.drawing_intel.tiled_inference import TiledInferencePipeline
                from bridge.project_syncer import write_vote_manifest

                tip = TiledInferencePipeline()
                combined_manifest: dict = {}
                total_three_pass_cost = 0.0

                for page in state.get("pages", []):
                    page_num = page.get("page_num", 0)
                    markdown_text = page.get("text", "")
                    r = tip.run_three_pass(
                        state["pdf_path"], page_num, markdown_text
                    )
                    total_three_pass_cost += r.get("cost_estimate_usd", 0.0)
                    # Carry disputed tiles forward for validate_node to log.
                    state.setdefault("disagreement_report", []).extend(
                        r.get("disagreement_report", [])
                    )
                    combined_manifest = r.get("manifest", {})

                state["vote_manifest"] = combined_manifest
                state["warnings"].append(
                    f"three_pass_cost_usd:{round(total_three_pass_cost, 4)}"
                )
                write_vote_manifest(state.get("bid_number", ""), combined_manifest)
                state["stages_completed"].append("three_pass_vision")
                log.info("three_pass_vision: total cost $%.4f", total_three_pass_cost)
            except Exception as e:
                state["warnings"].append(f"three_pass_vision_skipped: {e}")
                log.warning("three_pass_vision failed (non-fatal): %s", e)

        from bridge.drawing_intel.node_cropper import find_connection_nodes
        from bridge.drawing_intel.detail_vision import (
            analyze_crop_with_vision, merge_details_into_takeoff,
        )

        # Re-fetch with crops this time
        raw_nodes = find_connection_nodes(
            state.get("valid_members", []),
            pdf_path=state["pdf_path"],
            generate_crops=True,
        )

        provider = state.get("call_provider")
        workers = max(1, int(state.get("parallel_vision_workers", 4)))
        use_cache = bool(state.get("use_cache", True))
        bid_number = state.get("bid_number", "")

        cache = None
        if use_cache:
            try:
                from bridge.cache import VisionCache
                cache = VisionCache()
            except Exception as e:
                log.warning("vision cache unavailable: %s", e)

        def _process_one(node):
            crop_bytes = getattr(node, "crop_bytes", b"") or b""
            framing_hint = getattr(node, "framing_code", "") or ""
            cache_key = None
            if cache is not None and crop_bytes:
                from bridge.cache import make_cache_key
                cache_key = make_cache_key(
                    crop_bytes, framing_hint, bid_number)
                cached = cache.get(cache_key)
                if cached is not None:
                    return ("hit", node, cached)
            # Cache miss - call vision
            try:
                detail = analyze_crop_with_vision(
                    crop_bytes=crop_bytes,
                    framing_code_hint=framing_hint,
                    call_provider=provider,
                )
                result = detail.to_dict() \
                    if hasattr(detail, "to_dict") else {}
                if cache is not None and cache_key:
                    cache.set(cache_key, result,
                              metadata={"node_id": getattr(node, "node_id", "")})
                return ("miss", node, result)
            except Exception as e:
                log.warning("vision call failed for %s: %s",
                            getattr(node, "node_id", "?"), e)
                return ("error", node, {})

        details = []
        hits = 0
        misses = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_process_one, n) for n in raw_nodes]
            for fut in as_completed(futures):
                kind, node, result = fut.result()
                if kind == "hit":
                    hits += 1
                elif kind == "miss":
                    misses += 1
                if result:
                    # Attach tile source metadata if node carries it.
                    # Enables per-finding PDF coordinate traceability.
                    tile_id = getattr(node, "tile_id", None)
                    if tile_id:
                        result["tile_source"] = {
                            "tile_id": tile_id,
                            "bbox_pdf_pts": getattr(node, "tile_bbox", None),
                            "method": getattr(node, "tile_method", "roi"),
                        }
                    details.append(result)

        state["details"] = details
        state["cache_hits"] += hits
        state["cache_misses"] += misses

        # Build node-to-member map for the merge step
        node_map = {
            getattr(n, "node_id", ""): list(getattr(n, "members", []))
            for n in raw_nodes
        }
        merge_details_into_takeoff(
            state["valid_members"], details, node_map)

        state["stages_completed"].append("detail_vision")
        moments = sum(1 for d in details if d.get("moment"))
        log.info("stage4_detail_vision: %d details (%d moments), "
                 "%d cache hits, %d misses, %d workers",
                 len(details), moments, hits, misses, workers)
    except Exception as e:
        state["errors"].append(f"stage4_detail_vision: {e}")
        log.error("stage4_detail_vision failed: %s", e)
    return state


# ── Stage 4.5: Misc Steel (parallel branch) ───────────────────────────────

@_timed("stage45_misc_steel")
def misc_steel_node(state: dict) -> dict:
    """Misc steel detection. Independent of stages 2-4 - can run in
    parallel."""
    try:
        from bridge.misc_steel import detect_misc_steel

        pages = state.get("pages", [])
        if not pages:
            state["stages_completed"].append("misc_steel_skipped")
            return state

        # Run detection on each page text. detect_misc_steel takes
        # (text, page_num) per Phase 5 contract.
        all_items = []
        all_warnings = []
        total_lbs = 0.0
        for page in pages:
            text = page.get("text", "")
            page_num = page.get("page_num", 0)
            if not text:
                continue
            try:
                rollup = detect_misc_steel(text, page_num=page_num)
                all_items.append(rollup)
                # aggregate_misc_steel returns total_weight_lbs, not total_lbs
                total_lbs += float(rollup.get("total_weight_lbs", 0.0))
                all_warnings.extend(rollup.get("warnings", []))
            except Exception as e:
                all_warnings.append(f"misc_page_{page_num}: {e}")

        state["misc_items"] = all_items
        state["misc_lbs"] = round(total_lbs, 2)
        state["misc_tons"] = round(total_lbs / 2000.0, 4)
        state["misc_warnings"] = all_warnings
        state["stages_completed"].append("misc_steel")
        log.info("stage45_misc_steel: %.4f tons across %d pages",
                 state["misc_tons"], len(all_items))
    except Exception as e:
        state["errors"].append(f"stage45_misc_steel: {e}")
        log.error("stage45_misc_steel failed: %s", e)
    return state


# ── Stage 5: Weight Calculation ───────────────────────────────────────────

@_timed("stage5_weight_calc")
def weight_calc_node(state: dict) -> dict:
    """Compute structural tonnage and roll in misc steel."""
    try:
        from bridge.calculators import steel_weight

        valid = state.get("valid_members", [])
        # Build items list in the (shape, length_ft, qty) shape that
        # steel_weight() expects. Mirror the v1 controller exactly.
        items = []
        for m in valid:
            shape = m.get("shape") or m.get("normalized") or ""
            length = float(m.get("length_ft", 0) or 0)
            qty = int(m.get("qty", 1) or 1)
            if shape and length > 0:
                items.append((shape, length, qty))

        structural_lbs = 0.0
        if items:
            wt = steel_weight(items)
            structural_lbs = float(wt.get("total_lbs", 0.0))
            for s in wt.get("unknown_shapes", []):
                state["warnings"].append(f"weight_lookup_missed: {s}")

        # Roll in misc steel (Phase 5)
        misc_lbs = float(state.get("misc_lbs", 0.0))
        total_lbs = structural_lbs + misc_lbs

        state["structural_tons"] = round(structural_lbs / 2000.0, 4)
        state["total_lbs"] = round(total_lbs, 2)
        state["total_tons"] = round(total_lbs / 2000.0, 4)
        state["stages_completed"].append("weight_calc")
        log.info("stage5_weight_calc: structural=%.0f lbs, misc=%.0f lbs, "
                 "total=%.2f tons",
                 structural_lbs, misc_lbs, state["total_tons"])
    except Exception as e:
        state["errors"].append(f"stage5_weight_calc: {e}")
        log.error("stage5_weight_calc failed: %s", e)
    return state


# ── Stage 6: Cost Estimation ──────────────────────────────────────────────

@_timed("stage6_cost_calc")
def cost_calc_node(state: dict) -> dict:
    """Compute total cost. Mirrors the v1 controller's Stage 6 logic.

    Uses hours_estimate -> labor_cost -> bid_total. Adjusts fab hours
    for moment connections (8 hrs each) before the labor calc.

    Phase 10 (v4.3.0): assembly-based costing adds connection hardware
    cost as misc_subs in bid_total, and adds welding hours from the
    assembly table into fab_hours.
    """
    try:
        from bridge.calculators import hours_estimate, labor_cost, bid_total

        total_tons = float(state.get("total_tons", 0.0))
        total_lbs = float(state.get("total_lbs", 0.0))
        if total_tons <= 0.0:
            state["stages_completed"].append("cost_calc_skipped")
            return state

        hrs = hours_estimate(total_tons, complexity="standard")
        fab_hours = float(hrs.get("fab_hours", 0))
        erect_hours = float(hrs.get("erect_hours", 0))

        # Moment-frame adjustment: 8 fab hours per moment connection
        moment_count = sum(
            1 for m in state.get("valid_members", [])
            if m.get("moment", False)
        )
        if moment_count > 0:
            adj = moment_count * 8.0
            fab_hours += adj
            state["warnings"].append(
                f"{moment_count} moment frames added {adj:.0f} fab hours")

        # Phase 10 (v4.3.0): assembly-based costing
        assembly_cost = 0.0
        assembly_result = {}
        details = state.get("details", [])
        if details:
            try:
                from bridge.assembly_costing import compute_assembly_costs
                assembly_result = compute_assembly_costs(details)
                assembly_cost = float(
                    assembly_result.get("total_connection_cost_usd", 0))
                # Add assembly welding hours to fab hours
                asm_weld = float(
                    assembly_result.get("total_welding_hrs", 0))
                if asm_weld > 0:
                    fab_hours += asm_weld
                    state["warnings"].append(
                        f"Assembly welding: {asm_weld:.1f} hrs added to fab")
            except Exception as e:
                state["warnings"].append(f"assembly_costing_skipped: {e}")

        lc = labor_cost(fab_hours=fab_hours, erect_hours=erect_hours)
        # labor_cost() returns "total_labor", not "total". v1 had this
        # wrong (silently zero). v2 reads the correct key with a fallback.
        total_labor = float(lc.get("total_labor", lc.get("total", 0)))

        bt = bid_total(
            steel_lbs=total_lbs,
            labor_cost_usd=total_labor,
            tons=total_tons,
            misc_subs=assembly_cost,
        )
        # The bid_total() return dict uses key "bid_total", not "total".
        # The v1 controller had this wrong (silently zero). v2 fixes it.
        state["total_cost"] = float(
            bt.get("bid_total", bt.get("total", 0))
        )
        state["cost_breakdown"] = bt
        state["assembly_costs"] = assembly_result
        state["fab_hours"] = round(fab_hours, 2)
        state["erect_hours"] = round(erect_hours, 2)
        state["cost_per_ton"] = round(
            state["total_cost"] / total_tons, 2) if total_tons > 0 else 0.0
        state["stages_completed"].append("cost_calc")
        log.info("stage6_cost_calc: $%.0f total ($%.0f/ton)",
                 state["total_cost"], state["cost_per_ton"])
    except Exception as e:
        state["errors"].append(f"stage6_cost_calc: {e}")
        log.error("stage6_cost_calc failed: %s", e)
    return state
