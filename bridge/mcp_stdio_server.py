#!/usr/bin/env python3
"""
Your Company Virtual Office - stdio MCP transport for Claude Desktop.

Claude Desktop launches this as a subprocess:
    python.exe -m bridge.mcp_stdio_server

Reads JSON-RPC 2.0 from stdin, writes responses to stdout.
All logging goes to stderr only - stdout is reserved for JSON-RPC.

Protocol logic lives in mcp_server.py (handle_request, MCP_TOOLS).
This module is a thin stdio transport so Claude Desktop can launch
the server directly without the HTTP server or bearer token.
"""
import sys
import json
import logging
from pathlib import Path

# Ensure project root is on sys.path when launched as -m bridge.mcp_stdio_server
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s [mcp-stdio] %(levelname)s %(name)s: %(message)s",
)

from mcp_server import handle_request  # noqa: E402  # type: ignore


def _write(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, default=str) + "\n")
    sys.stdout.flush()


def main() -> None:
    print("[mcp-stdio] Your Company Virtual Office MCP ready", file=sys.stderr, flush=True)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            _write({"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"}})
            continue

        try:
            response = handle_request(request)
        except Exception as exc:
            _write({"jsonrpc": "2.0", "id": request.get("id"),
                    "error": {"code": -32603, "message": str(exc)[:500]}})
            continue

        if response is not None:
            _write(response)


main()
