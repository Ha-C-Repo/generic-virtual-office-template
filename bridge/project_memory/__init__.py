"""Project memory package (Phase 9, v4.2.0).

Semantic memory over past projects. When Owner uploads a revision of
a project Your Company bid three months ago, the system recognizes it and
surfaces the historical bid context automatically.

Downstream phases that consume project memory:
    Phase 14 (cloud watchdog) - recognizes returning projects on intake
    Phase 15 (objective planning) - searches past projects for context
    Phase 20 (cross-verification) - compares against historical baselines
    Phase 22 (spec auditor) - stores spec findings for reuse
    Phase 23 (ghost overlay) - links revisions to the same project record

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .memory_store import (
    get_memory_store,
    HAS_CHROMADB,
    ChromaMemoryStore,
    JSONLMemoryStore,
)
from .project_indexer import index_takeoff_result
from .memory_search import search_similar_projects, compare_to_current
from .backtester import backtest

__all__ = [
    "get_memory_store",
    "HAS_CHROMADB",
    "ChromaMemoryStore",
    "JSONLMemoryStore",
    "index_takeoff_result",
    "search_similar_projects",
    "compare_to_current",
    "backtest",
]
