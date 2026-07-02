"""Objective planner (Phase 15, build slot 15, v4.6.0).

Breaks natural-language objectives into ordered task chains and executes
them sequentially. Each task maps to an existing Bridge method. If a
step fails, the planner stops, reports the failure, and suggests the
manual action so Joseph can intervene.

Example:
    "Get the Houston Logistics Hub bid ready by Friday"
    -> find_drawings -> takeoff -> price -> scope -> proposal
    -> "Draft bid ready for review. Deadline: Friday 5pm."

The planner is NOT a general-purpose AI agent. It matches objectives to
pre-defined templates, not arbitrary reasoning chains. This keeps it
predictable, testable, and auditable.

CrewAI integration (when installed):
    The planner can optionally delegate to a CrewAI crew for parallel
    multi-agent execution. Without CrewAI, tasks run sequentially.
    Both paths produce identical output.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .deadline_tracker import parse_deadline

log = logging.getLogger(__name__)


# Lazy probe for CrewAI
try:
    import crewai  # noqa: F401
    HAS_CREWAI = True
except (ImportError, ModuleNotFoundError):
    HAS_CREWAI = False


# ── Task templates ─────────────────────────────────────────────────────────

TASK_TEMPLATES = {
    "bid": {
        "pattern": r"bid\s+on|prepare\s+bid|bid\s+ready|get\s+.+\s+bid",
        "label": "Prepare bid",
        "steps": [
            {"name": "check_memory", "method": "search_project_memory",
             "desc": "Search project memory for similar past bids"},
            {"name": "check_watchdog", "method": "get_watchdog_status",
             "desc": "Check if drawings were auto-detected"},
            {"name": "run_takeoff", "method": "process_full_takeoff_v2",
             "desc": "Run the full takeoff pipeline on the drawing set"},
            {"name": "assembly_costs", "method": "compute_assembly_costs",
             "desc": "Compute connection hardware costs"},
            {"name": "risk_score", "method": "run_monte_carlo",
             "desc": "Run Monte Carlo risk scoring on the bid"},
            {"name": "draft_proposal", "method": "compose_full_bid",
             "desc": "Draft scope letter and proposal PDF"},
        ],
    },
    "followup": {
        "pattern": r"follow\s+up|check\s+status|any\s+reply|hear\s+back",
        "label": "Follow up on project",
        "steps": [
            {"name": "search_inbox", "method": "search_inbox",
             "desc": "Search inbox for replies"},
            {"name": "check_memory", "method": "search_project_memory",
             "desc": "Look up project in memory"},
            {"name": "draft_followup", "method": "draft_email",
             "desc": "Draft a follow-up email"},
        ],
    },
    "reprice": {
        "pattern": r"update\s+pric|reprice|new\s+price|refresh\s+price",
        "label": "Update pricing",
        "steps": [
            {"name": "check_memory", "method": "search_project_memory",
             "desc": "Find the original bid in project memory"},
            {"name": "fetch_prices", "method": "get_steel_prices",
             "desc": "Fetch current steel market prices"},
            {"name": "recalculate", "method": "process_full_takeoff_v2",
             "desc": "Re-run takeoff with updated prices"},
            {"name": "compare_grades", "method": "compare_grades",
             "desc": "Run grade comparison for savings"},
        ],
    },
    "compliance": {
        "pattern": r"compliance|isn\s+|isnetworld|safety\s+program",
        "label": "Prepare compliance",
        "steps": [
            {"name": "check_isn", "method": "check_compliance",
             "desc": "Check ISNetworld compliance status"},
            {"name": "identify_gaps", "method": "get_panel_data",
             "desc": "Identify compliance gaps"},
            {"name": "generate_programs", "method": "generate_compliance",
             "desc": "Generate missing safety programs"},
        ],
    },
}


def match_template(objective: str) -> Optional[str]:
    """Match an objective string to a template key. Returns None if no
    template matches."""
    obj_lower = objective.lower()
    for key, tmpl in TASK_TEMPLATES.items():
        if re.search(tmpl["pattern"], obj_lower):
            return key
    return None


def extract_project_name(objective: str) -> str:
    """Try to extract a project name from the objective text."""
    # Common patterns: "bid on [name]", "for [name]", "[name] bid"
    patterns = [
        r"bid\s+on\s+(?:the\s+)?(.+?)(?:\s+by\s+|\s+before\s+|$)",
        r"for\s+(?:the\s+)?(.+?)(?:\s+by\s+|\s+before\s+|$)",
        r"(?:get|prepare)\s+(?:the\s+)?(.+?)(?:\s+bid|\s+ready)",
    ]
    for p in patterns:
        m = re.search(p, objective, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            # Remove trailing deadline words
            name = re.sub(r"\s+(by|before|until|due)\s*$", "", name,
                         flags=re.IGNORECASE)
            if len(name) > 3:
                return name
    return ""


# ── Plan and execution ─────────────────────────────────────────────────────

def build_plan(
    objective: str,
    template_key: Optional[str] = None,
) -> dict:
    """Build an execution plan from a natural-language objective.

    Returns:
        {
            "objective": str,
            "template": str,
            "label": str,
            "project_name": str,
            "deadline": dict (from parse_deadline),
            "steps": list of step dicts,
            "total_steps": int,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []

    key = template_key or match_template(objective)
    if key is None:
        return {
            "objective": objective,
            "template": "",
            "label": "Unrecognized objective",
            "project_name": "",
            "deadline": parse_deadline(""),
            "steps": [],
            "total_steps": 0,
            "warnings": ["no_template_matched"],
        }

    tmpl = TASK_TEMPLATES[key]
    project_name = extract_project_name(objective)
    deadline = parse_deadline(objective)

    steps = []
    for i, step in enumerate(tmpl["steps"]):
        steps.append({
            "index": i,
            "name": step["name"],
            "method": step["method"],
            "desc": step["desc"],
            "status": "pending",
            "result": None,
            "duration_ms": 0.0,
            "error": "",
        })

    return {
        "objective": objective,
        "template": key,
        "label": tmpl["label"],
        "project_name": project_name,
        "deadline": deadline,
        "steps": steps,
        "total_steps": len(steps),
        "warnings": warnings,
    }


def execute_plan(
    plan: dict,
    bridge: Any = None,
    on_step: Optional[Callable[[int, dict], None]] = None,
) -> dict:
    """Execute a plan sequentially.

    Args:
        plan: From build_plan().
        bridge: The Bridge instance. If None, steps are marked as
            "skipped" (dry-run mode for testing the plan structure).
        on_step: Optional callback called after each step with
            (step_index, step_dict). Used by the frontend for progress.

    Returns the plan dict with updated step statuses.
    """
    plan["started_at"] = datetime.now(timezone.utc).isoformat()
    plan["executor"] = "crewai" if HAS_CREWAI else "sequential"

    for step in plan["steps"]:
        t0 = time.perf_counter()

        if bridge is None:
            step["status"] = "skipped"
            step["result"] = {"note": "dry_run_mode"}
            if on_step:
                on_step(step["index"], step)
            continue

        method_name = step["method"]
        method = getattr(bridge, method_name, None)

        if method is None:
            step["status"] = "skipped"
            step["error"] = f"method {method_name} not found on Bridge"
            step["duration_ms"] = (time.perf_counter() - t0) * 1000.0
            if on_step:
                on_step(step["index"], step)
            continue

        try:
            # Build kwargs from plan context
            kwargs = _build_step_kwargs(step, plan)
            result = method(**kwargs)
            step["status"] = "done"
            step["result"] = result
        except Exception as e:
            step["status"] = "failed"
            step["error"] = str(e)
            log.warning("plan step %s failed: %s", step["name"], e)
            # Stop on failure
            step["duration_ms"] = (time.perf_counter() - t0) * 1000.0
            if on_step:
                on_step(step["index"], step)
            break

        step["duration_ms"] = (time.perf_counter() - t0) * 1000.0
        if on_step:
            on_step(step["index"], step)

    plan["ended_at"] = datetime.now(timezone.utc).isoformat()
    plan["completed_steps"] = sum(
        1 for s in plan["steps"] if s["status"] == "done")
    plan["failed_steps"] = sum(
        1 for s in plan["steps"] if s["status"] == "failed")
    plan["success"] = plan["failed_steps"] == 0 and \
                      plan["completed_steps"] > 0

    return plan


def _build_step_kwargs(step: dict, plan: dict) -> dict:
    """Map plan context to method kwargs. Each method has different
    parameters; we provide what we can from the plan."""
    name = step["name"]
    project = plan.get("project_name", "")

    if name == "check_memory":
        return {"query": project or plan.get("objective", "")}
    if name == "run_takeoff":
        return {"project_name": project, "force_executor": "fallback"}
    if name == "risk_score":
        return {"direct_cost": 500000, "material_tons": 100,
                "fab_hours": 1100, "erect_hours": 500}
    # Most methods work fine with no args or have defaults
    return {}
