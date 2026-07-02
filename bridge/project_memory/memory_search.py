"""Project memory search.

Given a new project's name, drawing text, or any free-form query, finds
the top N similar past projects and generates a comparison summary that
Owner can read on the bid card.

Example output:
    "This appears similar to PRJ-2026-HOU-0038 (Baytown Industrial).
     That project was 220 tons at $3,200/ton. Current project is 15
     percent larger."

The search runs against whichever backend is available (ChromaDB for
semantic similarity, JSONL for keyword overlap). The comparison
generator is backend-agnostic - it works the same on both.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Any, Optional

from .memory_store import get_memory_store

log = logging.getLogger(__name__)


def search_similar_projects(
    query: str,
    n_results: int = 3,
    store=None,
) -> dict:
    """Search project memory for similar past projects.

    Args:
        query: Free-form text. Can be a project name, drawing text,
            location, client name, or any combination.
        n_results: Max number of results to return.
        store: Override the default memory store (for testing).

    Returns:
        {
            "success": bool,
            "results": list of match dicts (see below),
            "result_count": int,
            "backend": str,
            "warnings": list[str],
        }

    Each match dict:
        {
            "bid_number": str,
            "project_name": str,
            "similarity": float (0 to 1),
            "total_tons": float,
            "total_cost": float,
            "cost_per_ton": float,
            "member_count": int,
            "moment_count": int,
            "client": str,
            "location": str,
            "document_preview": str (first 200 chars),
        }
    """
    if not query or not query.strip():
        return {
            "success": False,
            "results": [],
            "result_count": 0,
            "backend": "",
            "warnings": ["empty_query"],
        }

    if store is None:
        store = get_memory_store()

    backend = type(store).__name__
    raw = store.search(query=query.strip(), n_results=n_results)
    results = []
    for r in raw:
        meta = r.get("metadata", {}) or {}
        results.append({
            "bid_number": r.get("bid_number", ""),
            "project_name": str(meta.get("project_name", "")),
            "similarity": float(r.get("similarity", 0)),
            "type": str(meta.get("type", "project")),
            "total_tons": float(meta.get("total_tons", 0)),
            "total_cost": float(meta.get("total_cost", 0)),
            "cost_per_ton": float(meta.get("cost_per_ton", 0)),
            "member_count": int(meta.get("member_count", 0)),
            "moment_count": int(meta.get("moment_count", 0)),
            "client": str(meta.get("client", "")),
            "location": str(meta.get("location", "")),
            "document_preview": str(
                r.get("document", ""))[:200],
        })

    return {
        "success": True,
        "results": results,
        "result_count": len(results),
        "backend": backend,
        "warnings": [],
    }


def compare_to_current(
    current_tons: float,
    current_cost: float,
    match: dict,
) -> str:
    """Generate a plain-English comparison between a current project and
    a past match. Returns a single sentence for the bid card.

    Example: "15 percent larger than Baytown Industrial (220 tons at
    $3,200/ton)."
    """
    past_tons = float(match.get("total_tons", 0))
    past_cost = float(match.get("cost_per_ton", 0))
    past_name = match.get("project_name") or match.get("bid_number", "")

    if past_tons <= 0:
        return f"Past project {past_name} has no tonnage data for comparison."

    pct_diff = ((current_tons - past_tons) / past_tons) * 100.0
    direction = "larger" if pct_diff > 0 else "smaller"
    abs_pct = abs(pct_diff)

    parts = []
    if abs_pct < 2:
        parts.append(f"Similar tonnage to {past_name}")
    else:
        parts.append(f"{abs_pct:.0f} percent {direction} than {past_name}")

    parts.append(f"({past_tons:.0f} tons")
    if past_cost > 0:
        parts.append(f"at ${past_cost:,.0f}/ton")
    parts[-1] += ")."

    return " ".join(parts)
