"""Objective planner package (Phase 15, build slot 15, v4.6.0).

Natural-language objective -> ordered task chain -> sequential execution.
Each task maps to an existing Bridge method. Joseph says "get the bid
ready by Friday" and the system plans backwards from the deadline.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .planner import (
    build_plan,
    execute_plan,
    match_template,
    extract_project_name,
    TASK_TEMPLATES,
    HAS_CREWAI,
)
from .deadline_tracker import parse_deadline

__all__ = [
    "build_plan",
    "execute_plan",
    "match_template",
    "extract_project_name",
    "parse_deadline",
    "TASK_TEMPLATES",
    "HAS_CREWAI",
]
