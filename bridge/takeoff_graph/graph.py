"""Takeoff graph runner.

Two execution paths, same DAG topology:

    LangGraph path (preferred when langgraph is installed):
        Stage 1 -> Stage 2 -> Stage 3 -> Stage 4 -> Stage 5 -> Stage 6
        Stage 1 -> Stage 4.5 -----------------------> Stage 5

    ThreadPoolExecutor fallback (always available):
        Stage 1 (sequential)
        Stage 2 + Stage 4.5 in parallel
        Stage 3 (sequential after Stage 2)
        Stage 4 (sequential after Stage 3, but per-node fan-out inside)
        Stage 5 (after both Stage 4 and Stage 4.5)
        Stage 6 (sequential after Stage 5)

The fallback exists for two reasons:
    1. Sandbox / fresh box where langgraph install fails
    2. Joseph's Mac Mini if langgraph itself misbehaves

Both paths use the exact same node functions and produce the exact
same state dict, so swapping executors does not change correctness -
only timing.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from datetime import datetime, timezone

from .state import make_initial_state
from .nodes import (
    extract_node,
    validate_node,
    node_map_node,
    detail_vision_node,
    misc_steel_node,
    weight_calc_node,
    cost_calc_node,
)

log = logging.getLogger(__name__)


# Probe for LangGraph at import time, store the flag, never crash.
try:
    from langgraph.graph import StateGraph, END  # noqa: F401
    HAS_LANGGRAPH = True
except (ImportError, ModuleNotFoundError):
    HAS_LANGGRAPH = False


def build_langgraph(state_schema_cls=None) -> Any:
    """Construct a LangGraph StateGraph if the library is installed.

    Returns the compiled graph object, or None if LangGraph is absent.

    Saturday-4: defaults to TakeoffState (TypedDict with Annotated
    reducers on errors/warnings/stages_completed/timings_ms) so parallel
    branches do not crash with INVALID_CONCURRENT_GRAPH_UPDATE.
    """
    if not HAS_LANGGRAPH:
        return None

    from langgraph.graph import StateGraph, END

    # Saturday-4: use the reducer-annotated TypedDict by default.
    if state_schema_cls is None:
        try:
            from .state import TakeoffState
            state_schema_cls = TakeoffState
        except ImportError:
            state_schema_cls = dict

    g = StateGraph(state_schema_cls)
    g.add_node("extract", extract_node)
    g.add_node("validate", validate_node)
    g.add_node("misc_steel", misc_steel_node)
    g.add_node("node_map", node_map_node)
    g.add_node("detail_vision", detail_vision_node)
    g.add_node("weight_calc", weight_calc_node)
    g.add_node("cost_calc", cost_calc_node)

    g.set_entry_point("extract")
    # Parallel fan-out from extract
    g.add_edge("extract", "validate")
    g.add_edge("extract", "misc_steel")
    # Critical path
    g.add_edge("validate", "node_map")
    g.add_edge("node_map", "detail_vision")
    # Both branches converge at weight_calc
    g.add_edge("detail_vision", "weight_calc")
    g.add_edge("misc_steel", "weight_calc")
    # Final stage
    g.add_edge("weight_calc", "cost_calc")
    g.add_edge("cost_calc", END)

    return g.compile()


def _write_validation_log(state: dict) -> None:
    """Write validation_log to 3.Estimate/Takeoff/validation_log.json if bid_number set."""
    vlog = state.get("validation_log")
    if not vlog:
        return
    bid_number = state.get("bid_number", "")
    if not bid_number:
        return
    try:
        from bridge.project_syncer import write_takeoff_json
        payload = {
            "bid_number": bid_number,
            "project_name": state.get("project_name", ""),
            "timestamp": state.get("ended_at") or state.get("started_at", ""),
            "total_shapes": len(vlog),
            "passed": sum(1 for e in vlog if e.get("status") == "pass"),
            "failed": sum(1 for e in vlog if e.get("status") == "fail"),
            "entries": vlog,
        }
        write_takeoff_json(bid_number, "3.Estimate/Takeoff/validation_log.json", payload)
    except Exception as e:
        log.warning("_write_validation_log failed: %s", e)


def run_takeoff_graph(
    pdf_path: str,
    bid_number: str = "",
    project_name: str = "",
    skip_vision: bool = False,
    use_cache: bool = True,
    parallel_vision_workers: int = 4,
    call_provider: Any = None,
    vision_tier_router: Any = None,
    force_executor: str = "",
) -> dict:
    """Run the full takeoff DAG and return the final state.

    force_executor:
        ""           - auto. LangGraph if installed, else fallback.
        "langgraph"  - require LangGraph. Errors if absent.
        "fallback"   - force ThreadPoolExecutor path. Useful for tests
                       and benchmarks.
    """
    state = make_initial_state(
        pdf_path=pdf_path,
        bid_number=bid_number,
        project_name=project_name,
        skip_vision=skip_vision,
        use_cache=use_cache,
        parallel_vision_workers=parallel_vision_workers,
        vision_tier_router=vision_tier_router,
        call_provider=call_provider,
    )

    use_langgraph = (
        force_executor == "langgraph"
        # Saturday-4 fix: with TakeoffState reducers in place (state.py),
        # parallel branches no longer trigger INVALID_CONCURRENT_GRAPH_UPDATE.
        # Default back to LangGraph when installed.
        or (force_executor == "" and HAS_LANGGRAPH)
    )
    if force_executor == "langgraph" and not HAS_LANGGRAPH:
        state["errors"].append("langgraph_not_installed")
        return state

    if use_langgraph:
        final = _run_langgraph(state)
    else:
        final = _run_threadpool_fallback(state)

    _write_validation_log(final)
    return final


def _run_langgraph(state: dict) -> dict:
    """Execute via LangGraph compiled DAG."""
    state["executor"] = "langgraph"
    try:
        compiled = build_langgraph()
        if compiled is None:
            state["errors"].append("langgraph_compile_returned_none")
            state["executor"] = "fallback_after_langgraph_compile_fail"
            return _run_threadpool_fallback(state)
        # invoke returns the final state dict
        final = compiled.invoke(state)
        # LangGraph may return its own dict; merge to be safe
        if isinstance(final, dict):
            state.update(final)
        state["ended_at"] = datetime.now(timezone.utc).isoformat()
        return state
    except Exception as e:
        log.error("langgraph execution failed: %s", e)
        state["errors"].append(f"langgraph_runtime: {e}")
        state["executor"] = "fallback_after_langgraph_runtime_fail"
        return _run_threadpool_fallback(state)


def _run_threadpool_fallback(state: dict) -> dict:
    """Execute via ThreadPoolExecutor.

    Same DAG topology as the LangGraph path, hand-orchestrated.
    """
    state["executor"] = state.get("executor") or "threadpool_fallback"

    # Stage 1: extract (sequential, blocks everything)
    state = extract_node(state)
    if "extract" not in state.get("stages_completed", []):
        state["ended_at"] = datetime.now(timezone.utc).isoformat()
        return state

    # Stages 2 and 4.5 in parallel
    with ThreadPoolExecutor(max_workers=2,
                            thread_name_prefix="ncti-stage2-45") as ex:
        f_validate = ex.submit(validate_node, state)
        f_misc = ex.submit(misc_steel_node, state)
        # Both nodes mutate the same state dict in place. We just wait
        # for both to finish.
        f_validate.result()
        f_misc.result()

    # Stage 3: node mapping (sequential after Stage 2)
    state = node_map_node(state)

    # Stage 4: detail vision (sequential, but parallel inside per node)
    state = detail_vision_node(state)

    # Stage 5: weight calc (must come after both Stage 4 and 4.5)
    state = weight_calc_node(state)

    # Stage 6: cost (sequential after Stage 5)
    state = cost_calc_node(state)

    state["ended_at"] = datetime.now(timezone.utc).isoformat()
    return state


def runner_status() -> dict:
    """Snapshot for diagnostics. The Bridge uses this for the GUI."""
    return {
        "langgraph_available": HAS_LANGGRAPH,
        "default_executor": "langgraph" if HAS_LANGGRAPH
                            else "threadpool_fallback",
    }
