"""Shared state for the takeoff graph.

LangGraph nodes mutate a single state dict that flows through the DAG.
This module defines the schema and a helper that constructs an empty
state from a (pdf_path, bid_number, project_name) tuple.

When LangGraph is installed we use its TypedDict-based state. When it
is not (sandbox / fresh box), the fallback orchestrator uses the same
plain dict shape.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from typing import Any
from datetime import datetime, timezone


# Default schema. Plain dict so the fallback orchestrator can use it
# directly. The graph builder upgrades this to a LangGraph TypedDict
# when LangGraph is present.
def make_initial_state(
    pdf_path: str,
    bid_number: str = "",
    project_name: str = "",
    skip_vision: bool = False,
    use_cache: bool = True,
    parallel_vision_workers: int = 4,
    vision_tier_router: Any = None,
    call_provider: Any = None,
    three_pass_enabled: bool = False,
) -> dict[str, Any]:
    """Construct an empty state dict for a takeoff run."""
    return {
        # Inputs
        "pdf_path": str(pdf_path),
        "bid_number": str(bid_number),
        "project_name": str(project_name),
        "skip_vision": bool(skip_vision),
        "use_cache": bool(use_cache),
        "parallel_vision_workers": int(parallel_vision_workers),
        "vision_tier_router": vision_tier_router,
        "call_provider": call_provider,
        "three_pass_enabled": bool(three_pass_enabled),

        # Stage 1
        "raw_members": [],
        "pages": [],

        # Stage 2
        "valid_members": [],
        "rejected_shapes": [],
        "validation_log": [],
        "disagreement_report": [],

        # Stage 3
        "nodes": [],

        # Stage 4
        "details": [],
        "vote_manifest": {},

        # Stage 4.5
        "misc_items": [],
        "misc_lbs": 0.0,
        "misc_tons": 0.0,
        "misc_warnings": [],

        # Stage 5
        "total_tons": 0.0,
        "total_lbs": 0.0,
        "structural_tons": 0.0,

        # Stage 6
        "total_cost": 0.0,
        "cost_per_ton": 0.0,
        "fab_hours": 0.0,
        "erect_hours": 0.0,
        "cost_breakdown": {},
        "assembly_costs": {},

        # Bookkeeping
        "stages_completed": [],
        "errors": [],
        "warnings": [],
        "timings_ms": {},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": "",
        "cache_hits": 0,
        "cache_misses": 0,
        "executor": "",  # "langgraph" or "threadpool_fallback"
    }


# Saturday-4: LangGraph TypedDict schema with reducers for parallel branches.
# The original plain-dict state crashed with INVALID_CONCURRENT_GRAPH_UPDATE
# when validate || misc_steel ran in parallel and both wrote to errors/
# warnings/stages_completed. LangGraph requires Annotated[T, reducer]
# on any field that may receive concurrent updates.
#
# Only the keys that parallel branches write to need reducers.
# Single-writer keys (e.g. nodes, details, total_cost) keep last-write-wins.

try:
    from typing import Annotated, TypedDict
    import operator
    HAS_TYPING_ANNOTATED = True
except ImportError:
    HAS_TYPING_ANNOTATED = False


def _merge_dicts(left: dict, right: dict) -> dict:
    """Reducer for dict merges (e.g. timings_ms). Right side wins on key collision."""
    out = dict(left) if left else {}
    if right:
        out.update(right)
    return out


def _take_right(left, right):
    """Last-writer-wins reducer for scalars and single-owner lists.

    LangGraph treats a node returning a state key as a concurrent update
    even when only one node writes to that key in practice. Adding this
    reducer to scalar fields tells LangGraph: drop the prior, take this
    one. Required to compile a graph where any node returns input keys.
    """
    return right if right is not None else left


if HAS_TYPING_ANNOTATED:

    class TakeoffState(TypedDict, total=False):
        """LangGraph state schema. Use only when LangGraph is in use.

        Every key uses an Annotated reducer because LangGraph treats
        any node-returned key as a concurrent update, even when there
        is exactly one writer. The reducer choice controls semantics:
        - operator.add for lists that parallel branches append to
        - _merge_dicts for dicts that parallel branches extend
        - _take_right for everything else (last write wins)
        """
        # Inputs - set once, but reducer still required
        pdf_path: Annotated[str, _take_right]
        bid_number: Annotated[str, _take_right]
        project_name: Annotated[str, _take_right]
        skip_vision: Annotated[bool, _take_right]
        use_cache: Annotated[bool, _take_right]
        parallel_vision_workers: Annotated[int, _take_right]
        vision_tier_router: Annotated[Any, _take_right]
        call_provider: Annotated[Any, _take_right]
        three_pass_enabled: Annotated[bool, _take_right]

        # Stage outputs - single writer per key
        raw_members: Annotated[list, _take_right]
        pages: Annotated[list, _take_right]
        valid_members: Annotated[list, _take_right]
        rejected_shapes: Annotated[list, _take_right]
        validation_log: Annotated[list, _take_right]
        disagreement_report: Annotated[list, _take_right]
        nodes: Annotated[list, _take_right]
        details: Annotated[list, _take_right]
        vote_manifest: Annotated[dict, _merge_dicts]
        misc_items: Annotated[list, _take_right]
        misc_lbs: Annotated[float, _take_right]
        misc_tons: Annotated[float, _take_right]
        total_tons: Annotated[float, _take_right]
        total_lbs: Annotated[float, _take_right]
        structural_tons: Annotated[float, _take_right]
        total_cost: Annotated[float, _take_right]
        cost_per_ton: Annotated[float, _take_right]
        fab_hours: Annotated[float, _take_right]
        erect_hours: Annotated[float, _take_right]
        cost_breakdown: Annotated[dict, _merge_dicts]
        assembly_costs: Annotated[dict, _merge_dicts]
        started_at: Annotated[str, _take_right]
        ended_at: Annotated[str, _take_right]
        cache_hits: Annotated[int, _take_right]
        cache_misses: Annotated[int, _take_right]
        executor: Annotated[str, _take_right]

        # Bookkeeping - parallel branches append, MUST be additive
        errors: Annotated[list, operator.add]
        warnings: Annotated[list, operator.add]
        misc_warnings: Annotated[list, operator.add]
        stages_completed: Annotated[list, operator.add]
        timings_ms: Annotated[dict, _merge_dicts]
else:
    TakeoffState = dict  # fallback when typing.Annotated unavailable
