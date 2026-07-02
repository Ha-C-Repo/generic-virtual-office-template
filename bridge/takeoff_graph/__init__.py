"""Takeoff graph package (Phase 8, v4.1.0).

LangGraph-driven (with ThreadPoolExecutor fallback) replacement for the
linear takeoff_controller. Same six stages, but:

- Stage 1 (extract) blocks everything.
- Stage 2 (validate) and Stage 4.5 (misc steel) run in parallel.
- Stage 4 (detail vision) fans out per-node calls inside.
- Stages 5 and 6 stay sequential at the tail.

The original linear controller (bridge/takeoff_controller.py) stays in
place as a known-good fallback. The Bridge picks which to use via the
`use_graph` flag on `process_full_takeoff_v2`. Joseph can override per
call.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .state import make_initial_state
from .graph import (
    run_takeoff_graph,
    build_langgraph,
    runner_status,
    HAS_LANGGRAPH,
)
from .nodes import (
    extract_node,
    validate_node,
    node_map_node,
    detail_vision_node,
    misc_steel_node,
    weight_calc_node,
    cost_calc_node,
)

__all__ = [
    "make_initial_state",
    "run_takeoff_graph",
    "build_langgraph",
    "runner_status",
    "HAS_LANGGRAPH",
    "extract_node",
    "validate_node",
    "node_map_node",
    "detail_vision_node",
    "misc_steel_node",
    "weight_calc_node",
    "cost_calc_node",
]
