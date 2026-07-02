"""OpenHuman memory bridge (Phase 29, v6.1.0).

Queries OpenHuman's Memory Tree for past project context. Replaces
the need for a separate ChromaDB vector DB. OpenHuman auto-indexes
emails, documents, calendar events, and bid history.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Optional

from .rpc_client import OpenHumanClient

log = logging.getLogger(__name__)


def search_memory(
    query: str,
    max_results: int = 5,
    client: OpenHumanClient | None = None,
) -> dict:
    """Search OpenHuman Memory Tree for project context.

    Args:
        query: Natural language query.
        max_results: Max results to return.
        client: Optional RPC client (for testing).

    Returns:
        {"success": bool, "results": list, "source": "openhuman"}
    """
    c = client or OpenHumanClient()
    if not c.is_available():
        return {
            "success": False,
            "results": [],
            "source": "openhuman",
            "error": "OpenHuman not running. Falling back to local "
                     "project_memory if available.",
        }

    result = c.call("memory.search", {
        "query": query,
        "limit": max_results,
    })

    if "error" in result:
        return {"success": False, "results": [], "error": result["error"],
                "source": "openhuman"}

    return {
        "success": True,
        "results": result.get("items", []),
        "total": result.get("total", 0),
        "source": "openhuman",
    }


def index_project(
    project_data: dict,
    client: OpenHumanClient | None = None,
) -> dict:
    """Index a completed project into OpenHuman Memory Tree.

    Args:
        project_data: Dict with bid_number, project_name, tonnage, etc.
        client: Optional RPC client.
    """
    c = client or OpenHumanClient()
    if not c.is_available():
        return {"success": False, "error": "openhuman_not_running"}

    result = c.call("memory.index", {"document": project_data})
    return {"success": "error" not in result, **result}
