"""
Remote MCP Connector Registry - Pass 8

The Claude Desktop App on Windows holds TWO kinds of MCP servers:
  (1) Stdio servers - command + args - stored in claude_desktop_config.json
      → handled by bridge/mcp_client.py
  (2) Remote URL connectors - https URLs - stored inside the Claude App's
      preference database (NOT in claude_desktop_config.json)
      → handled by THIS module

For (2), there's no public file to scrape - the app holds them internally.
The pragmatic solution: maintain a curated list in data/remote_mcps.json
that Joseph populates from Claude Desktop's Settings > Connectors. Then,
when the Bridge makes an Anthropic API call, it can include the matching
mcp_servers parameter so Claude (via API) has access to the same remote
services Owner sees in his Desktop App.

This is how the API supports remote MCPs:
    client.messages.create(
        model="claude-sonnet-4-6",
        mcp_servers=[
            {"type": "url", "url": "https://...", "name": "service-name"}
        ],
        messages=[...]
    )

Joseph adds connectors via `add remote mcp <name> <url>` in chat.
Owner sees them via `connectors`.

SEEDED DEFAULTS
───────────────
Microsoft 365 is seeded because the vendor quote poller could call into
it directly via API+MCP as an alternative to local Outlook COM, useful
when the Bridge runs from a non-Win11 host or when Outlook isn't open.
"""

import json
from datetime import datetime
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_REMOTE_MCPS_FILE = _DATA / "remote_mcps.json"

# ─────────────────────────────────────────────────────────────────
# SEEDED DEFAULTS (Joseph confirms what's actually in the Owner's
# Claude Desktop App; this is the conservative starter set)
# ─────────────────────────────────────────────────────────────────

_DEFAULTS = [
    {
        "name": "microsoft-365",
        "url": "https://microsoft365.mcp.claude.com/mcp",
        "description": "Outlook mail/calendar/files, SharePoint, Teams. "
                       "Alternative path for vendor quote poller when local "
                       "Outlook COM unavailable.",
        "categories": ["email", "calendar", "files", "office"],
        "added_at": "2026-05-13",
        "enabled": True,
    },
]

# ─────────────────────────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────────────────────────

def _load() -> list:
    try:
        if _REMOTE_MCPS_FILE.exists():
            return json.loads(_REMOTE_MCPS_FILE.read_text())
    except Exception:
        pass
    return None

def _save(data: list) -> None:
    _REMOTE_MCPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _REMOTE_MCPS_FILE.write_text(json.dumps(data, indent=2, default=str))

def _ensure() -> list:
    """Initialize registry on first call."""
    existing = _load()
    if existing is None:
        _save(_DEFAULTS)
        return list(_DEFAULTS)
    return existing

# ─────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────

def list_remote_servers() -> list:
    """Return all registered remote MCP connectors."""
    return _ensure()

def get_enabled() -> list:
    """Return only enabled connectors (for API call inclusion)."""
    return [s for s in _ensure() if s.get("enabled", True)]

def add_remote_server(name: str, url: str, description: str = "",
                      categories: list = None) -> dict:
    """Register a new remote MCP connector."""
    name = name.strip()
    url = url.strip()
    if not name or not url:
        return {"added": False, "error": "name and url required"}
    if not url.startswith("https://"):
        return {"added": False, "error": "url must be https://"}
    servers = _ensure()
    if any(s["name"].lower() == name.lower() for s in servers):
        return {"added": False, "error": f"'{name}' already registered"}
    entry = {
        "name": name,
        "url": url,
        "description": description or "(no description)",
        "categories": categories or [],
        "added_at": datetime.now().date().isoformat(),  # vj: local-time-ok
        "enabled": True,
    }
    servers.append(entry)
    _save(servers)
    return {"added": True, "entry": entry}

def remove_remote_server(name: str) -> dict:
    """Remove a remote MCP connector by name."""
    servers = _ensure()
    before = len(servers)
    servers = [s for s in servers if s["name"].lower() != name.lower()]
    if len(servers) == before:
        return {"removed": False, "error": f"'{name}' not found"}
    _save(servers)
    return {"removed": True, "name": name, "remaining": len(servers)}

def set_enabled(name: str, enabled: bool) -> dict:
    """Toggle a connector's enabled flag without removing it."""
    servers = _ensure()
    for s in servers:
        if s["name"].lower() == name.lower():
            s["enabled"] = bool(enabled)
            _save(servers)
            return {"ok": True, "name": name, "enabled": bool(enabled)}
    return {"ok": False, "error": f"'{name}' not found"}

def select_for_task(category: str = "") -> list:
    """Return connectors whose categories match a given task category.

    Used by call_claude_with_mcps() to attach only relevant servers
    (passing all 100+ remote MCPs to every API call would blow context).
    """
    if not category:
        return []
    cat = category.lower()
    return [s for s in get_enabled() if cat in [c.lower() for c in s.get("categories", [])]]

def as_api_param(names: list = None, category: str = "") -> list:
    """Build the mcp_servers parameter list for the Anthropic Messages API.

    Args:
      names: explicit list of connector names to include. Empty means use
             category filter or all enabled.
      category: if names is empty, filter by category instead.

    Returns:
      List of {type:"url", url:..., name:...} dicts ready to pass as
      the mcp_servers param. Returns [] if nothing matches (caller
      should then skip the parameter entirely).
    """
    if names:
        wanted = {n.lower() for n in names}
        selected = [s for s in get_enabled() if s["name"].lower() in wanted]
    elif category:
        selected = select_for_task(category)
    else:
        selected = get_enabled()
    return [{"type": "url", "url": s["url"], "name": s["name"]} for s in selected]

def status() -> dict:
    """Snapshot for the Bridge UI."""
    servers = _ensure()
    return {
        "total":     len(servers),
        "enabled":   len([s for s in servers if s.get("enabled", True)]),
        "names":     [s["name"] for s in servers],
        "config_file": str(_REMOTE_MCPS_FILE),
    }

# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        print(json.dumps(list_remote_servers(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(status(), indent=2))
    elif len(sys.argv) > 3 and sys.argv[1] == "add":
        print(json.dumps(add_remote_server(sys.argv[2], sys.argv[3]), indent=2))
    elif len(sys.argv) > 2 and sys.argv[1] == "remove":
        print(json.dumps(remove_remote_server(sys.argv[2]), indent=2))
    else:
        print("Usage: python mcp_remote.py [list|status|add <name> <url>|remove <name>]")
