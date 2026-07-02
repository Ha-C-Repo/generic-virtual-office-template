"""OpenHuman watchdog bridge (Phase 29, v6.1.0).

Subscribes to OpenHuman auto-fetch events. When a new PDF appears in
the connected Drive/OneDrive "Bids" folder, OpenHuman notifies our
app to trigger the takeoff pipeline. Replaces custom cloud watchers.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Any, Callable, Optional

from .rpc_client import OpenHumanClient

log = logging.getLogger(__name__)


def get_recent_files(
    folder_filter: str = "Bids",
    file_types: list[str] | None = None,
    since_minutes: int = 60,
    client: OpenHumanClient | None = None,
) -> dict:
    """Get recently detected files from OpenHuman auto-fetch.

    Args:
        folder_filter: Folder name to filter (e.g., "Bids").
        file_types: File extensions to include (e.g., [".pdf"]).
        since_minutes: Look back window.
        client: Optional RPC client.

    Returns:
        {"success": bool, "files": list, "count": int}
    """
    c = client or OpenHumanClient()
    if not c.is_available():
        return {"success": False, "files": [], "count": 0,
                "error": "openhuman_not_running"}

    result = c.call("files.recent", {
        "folder": folder_filter,
        "types": file_types or [".pdf"],
        "since_minutes": since_minutes,
    })

    if "error" in result:
        return {"success": False, "files": [], "count": 0,
                "error": result["error"]}

    files = result.get("files", [])
    return {"success": True, "files": files, "count": len(files)}


def register_file_callback(
    callback_url: str = "http://127.0.0.1:8080/mcp",
    event_type: str = "new_file",
    folder: str = "Bids",
    client: OpenHumanClient | None = None,
) -> dict:
    """Register a callback URL for OpenHuman file events.

    When OpenHuman detects a new file matching the filter, it POSTs
    to the callback URL. Our MCP server handles the incoming event
    and triggers the takeoff pipeline.
    """
    c = client or OpenHumanClient()
    if not c.is_available():
        return {"success": False, "error": "openhuman_not_running"}

    result = c.call("events.subscribe", {
        "callback": callback_url,
        "event": event_type,
        "filter": {"folder": folder, "types": [".pdf"]},
    })

    return {"success": "error" not in result, **result}
