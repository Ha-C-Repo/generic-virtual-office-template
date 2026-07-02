"""
Your Company Virtual Office - MCP Client
======================================
Reverse direction: Virtual Office talks TO the Owner's existing Claude Desktop
MCP servers (Gmail, Calendar, Drive, etc.) so the bridge can use them
during agent workflows.

WHY THIS EXISTS - TWO-CLOUD COST OPTIMIZATION
─────────────────────────────────────────────
Virtual Office runs against two Anthropic accounts on purpose:

  • Joseph's Anthropic API key  → autonomous engine work (bid analysis,
                                   doc parsing, vision, agent reasoning)
  • the Owner's Claude Desktop     → chat-driven work + integrations
    subscription                   (Gmail, Calendar, Drive)

When the bridge needs to do an INTEGRATION task (read mail, post to
calendar, fetch a Drive file), it should prefer this MCP client over a
direct API call. Two reasons:

  1. Cost: the integration runs on the Owner's existing subscription with
     pre-authenticated credentials - Joseph's API key never gets touched.
  2. Accuracy: Claude Desktop already has authenticated, working
     connections to the Owner's actual mailbox/calendar/drive. We don't
     have to re-implement OAuth, token refresh, or scope handshakes.

Use prefer_mcp_for_integration() to ask "is this routable through
Claude Desktop?" before falling back to a direct API call.

How it works:
  1. Read Claude Desktop's claude_desktop_config.json on Windows
     (%APPDATA%\\Claude\\claude_desktop_config.json)
  2. Discover registered mcpServers
  3. Spawn each as a subprocess on demand (stdio JSONRPC)
  4. Cache the connection so repeated calls reuse the process

Security:
  - This module ONLY reads config; never modifies it.
  - Subprocesses inherit the user's environment.
  - Each spawned MCP server runs with whatever credentials Claude Desktop
    has already authorized - Virtual Office adds no new auth surface.

Usage from a Bridge method:
    from bridge.mcp_client import (
        list_servers, call_tool, status, prefer_mcp_for_integration
    )

    servers = list_servers()                          # discovery
    if prefer_mcp_for_integration("email"):           # routing decision
        r = call_tool("gmail-mcp", "send_email", {...})
    else:
        r = bridge.send_email_via_anthropic_api(...)  # fallback

    health = status()
"""

import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path


# ── Config discovery ───────────────────────────────────────────────────────

def _config_path() -> Path | None:
    """Return path to claude_desktop_config.json based on OS, or None."""
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
    elif platform.system() == "Darwin":   # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:                                  # Linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return None


def _load_config() -> dict:
    """Load Claude Desktop config. Returns empty dict if missing/corrupt."""
    p = _config_path()
    if not p or not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def list_servers() -> list[dict]:
    """List all MCP servers registered with Claude Desktop.

    Returns list of {name, command, args, env, connected}.
    """
    cfg = _load_config()
    servers = cfg.get("mcpServers", {})
    out = []
    for name, spec in servers.items():
        out.append({
            "name":      name,
            "command":   spec.get("command", ""),
            "args":      spec.get("args", []),
            "env_keys":  list((spec.get("env") or {}).keys()),
            "connected": name in _CONNECTIONS,
        })
    return out


# ── Subprocess connection cache ───────────────────────────────────────────

class _MCPConnection:
    """Thread-safe wrapper around a spawned MCP server subprocess."""

    def __init__(self, name: str, command: str, args: list[str], env: dict):
        self.name = name
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._command = command
        self._args = args
        self._env = {**os.environ, **(env or {})}
        self._initialized = False

    def _spawn(self) -> bool:
        """Start the subprocess. Returns True on success."""
        try:
            self._proc = subprocess.Popen(
                [self._command, *self._args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                text=True,
                bufsize=1,
                creationflags=(0x08000000 if platform.system() == "Windows" else 0),  # CREATE_NO_WINDOW
            )
            return True
        except (FileNotFoundError, OSError):
            self._proc = None
            return False

    def _send(self, msg: dict) -> dict | None:
        """Send a JSONRPC request and wait up to 5s for a response."""
        if not self._proc or self._proc.poll() is not None:
            if not self._spawn():
                return None

        line = json.dumps(msg, separators=(",", ":")) + "\n"
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None

        # Wait for matching response (id-keyed)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            ready = self._proc.stdout.readline()
            if not ready:
                time.sleep(0.05)
                continue
            try:
                resp = json.loads(ready.strip())
            except json.JSONDecodeError:
                continue
            if resp.get("id") == msg.get("id"):
                return resp
            # else: notification or stale - keep reading
        return None

    def initialize(self) -> bool:
        """Run the MCP initialize handshake."""
        if self._initialized:
            return True
        with self._lock:
            r = self._send({
                "jsonrpc": "2.0",
                "id":      self._next_id,
                "method":  "initialize",
                "params":  {"protocolVersion": "2024-11-05", "capabilities": {}},
            })
            self._next_id += 1
            self._initialized = bool(r and r.get("result"))
            return self._initialized

    def list_tools(self) -> list[dict]:
        """Return list of tools this server exposes."""
        if not self.initialize():
            return []
        with self._lock:
            r = self._send({
                "jsonrpc": "2.0",
                "id":      self._next_id,
                "method":  "tools/list",
                "params":  {},
            })
            self._next_id += 1
            if not r or "result" not in r:
                return []
            return r["result"].get("tools", [])

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on this server. Returns {ok, data, error?}."""
        if not self.initialize():
            return {"ok": False, "error": f"Failed to initialize {self.name}"}
        with self._lock:
            r = self._send({
                "jsonrpc": "2.0",
                "id":      self._next_id,
                "method":  "tools/call",
                "params":  {"name": tool_name, "arguments": arguments or {}},
            })
            self._next_id += 1
            if not r:
                return {"ok": False, "error": f"No response from {self.name}"}
            if "error" in r:
                return {"ok": False, "error": r["error"].get("message", "unknown")}
            result = r.get("result", {})
            content = result.get("content", [])
            text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
            return {
                "ok":      not result.get("isError", False),
                "data":    text,
                "isError": result.get("isError", False),
            }

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._initialized = False


_CONNECTIONS: dict[str, _MCPConnection] = {}


def _get_connection(name: str) -> _MCPConnection | None:
    """Get or create a connection to a named MCP server."""
    if name in _CONNECTIONS:
        return _CONNECTIONS[name]

    cfg = _load_config()
    spec = cfg.get("mcpServers", {}).get(name)
    if not spec:
        return None

    conn = _MCPConnection(
        name=name,
        command=spec.get("command", ""),
        args=spec.get("args", []),
        env=spec.get("env", {}),
    )
    _CONNECTIONS[name] = conn
    return conn


# ── Public API ─────────────────────────────────────────────────────────────

def list_tools(server_name: str) -> list[dict]:
    """List tools exposed by a registered MCP server."""
    conn = _get_connection(server_name)
    if not conn:
        return []
    return conn.list_tools()


def call_tool(server_name: str, tool_name: str, arguments: dict | None = None) -> dict:
    """Invoke a tool on a registered MCP server. Returns {ok, data, error?}."""
    conn = _get_connection(server_name)
    if not conn:
        return {"ok": False, "error": f"MCP server '{server_name}' not registered in Claude Desktop config"}
    return conn.call_tool(tool_name, arguments or {})


def status() -> dict:
    """Health check: config found, server count, active connections."""
    p = _config_path()
    cfg = _load_config()
    servers = cfg.get("mcpServers", {})
    return {
        "config_path":         str(p) if p else None,
        "config_exists":       bool(p and p.exists()),
        "platform":            platform.system(),
        "registered_servers":  len(servers),
        "server_names":        list(servers.keys()),
        "active_connections":  list(_CONNECTIONS.keys()),
        "claude_desktop_ready": bool(p and p.exists() and servers),
    }


def shutdown_all() -> None:
    """Close all spawned MCP server subprocesses. Call on Bridge shutdown."""
    for conn in list(_CONNECTIONS.values()):
        conn.close()
    _CONNECTIONS.clear()


# ── Cost-optimization routing ──────────────────────────────────────────────

# Maps integration categories → name patterns that typically expose them
# in Claude Desktop config. Used by prefer_mcp_for_integration() to decide
# whether to route an integration call through MCP (the Owner's subscription)
# instead of through Joseph's direct Anthropic API key.
INTEGRATION_HINTS: dict[str, list[str]] = {
    "email":      ["gmail", "mail", "outlook", "smtp"],
    "calendar":   ["calendar", "gcal", "outlook"],
    "drive":      ["drive", "gdrive", "onedrive", "dropbox"],
    "docs":       ["docs", "doc", "google-docs"],
    "sheets":     ["sheets", "google-sheets", "excel"],
    "slack":      ["slack"],
    "github":     ["github", "git"],
    "filesystem": ["filesystem", "fs", "files"],
    "browser":    ["browser", "puppeteer", "playwright", "fetch"],
    "search":     ["search", "brave", "google-search"],
}


def prefer_mcp_for_integration(category: str) -> str | None:
    """Decide whether a given integration category should route via MCP.

    Returns the name of a matching Claude Desktop MCP server if one is
    registered and the category hint matches, else None. The bridge can
    then either route through MCP (cheaper - the Owner's subscription) or
    fall back to a direct Anthropic API call (Joseph's key).

    Args:
        category: one of the keys in INTEGRATION_HINTS (e.g. "email",
                  "calendar", "drive"). Case-insensitive.

    Returns:
        Server name from claude_desktop_config.json that matches the
        category, or None if no match.

    Example:
        >>> server = prefer_mcp_for_integration("email")
        >>> if server:
        ...     call_tool(server, "send_email", {"to": "...", ...})
        ... else:
        ...     # fall back to direct API
        ...     ...
    """
    hints = INTEGRATION_HINTS.get(category.lower(), [])
    if not hints:
        return None

    for srv in list_servers():
        name_lower = srv["name"].lower()
        for hint in hints:
            if hint in name_lower:
                return srv["name"]
    return None
