"""
Your Company Virtual Office - Localhost Chat RPC Server (P18.4)

Thin HTTP endpoint on 127.0.0.1:8765 so Cowork pilots and automation
can drive the Bridge without needing to synthesize WebView2 GUI events.

Endpoints:
  POST /chat  {"text": "..."} -> Bridge.ai_ask result JSON
  GET  /health                -> {"ok": true}

No auth - localhost only. Never bind to 0.0.0.0 from here.

P19.1 fix: handler calls try_direct_route() first and returns immediately
if matched. Only falls through to bridge.ai_ask() if no direct route
matches. This prevents async-launch commands (vj scan and fix, self test,
etc.) from blocking the HTTP thread on the LLM path when the direct route
handler times out inside ai_ask.

Usage:
  from bridge.chat_rpc_server import start_server
  start_server(bridge_instance, port=8765)
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Module-level reference to the Bridge instance.
# Injected by start_server() before the first request.
# Module-level (not inside a function) - PyInstaller Python 3.13 requirement.
_bridge = None


class _ChatRPCHandler(BaseHTTPRequestHandler):
    """Request handler for the localhost chat RPC endpoint."""

    def do_POST(self):
        if self.path != "/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            text = str(data.get("text", "")).strip()
        except Exception:
            self.send_error(400, "invalid JSON body")
            return
        if not text:
            self._json_response(400, {"ok": False, "error": "text required"})
            return
        try:
            # P19.1: fast path via direct route. Returns immediately for both
            # sync commands and async-launch commands (vj scan, self test, etc.).
            # Never blocks waiting for a background job to complete.
            from bridge.direct_route import try_direct_route
            dr = try_direct_route(_bridge, text)
            if dr is not None:
                self._json_response(200, {"ok": True, "data": dr})
                return
            # P23.3: slow path with 30s timeout. Unknown commands that match no
            # direct route go to the LLM. Without a timeout, the HTTP thread
            # blocks indefinitely if the LLM API hangs, returning empty to curl.
            _ai_result = [None]
            _ai_exc = [None]
            def _run_ai():
                try:
                    _ai_result[0] = _bridge.ai_ask(message=text)
                except Exception as _e:
                    _ai_exc[0] = _e
            _t = threading.Thread(target=_run_ai, daemon=True)
            _t.start()
            _t.join(timeout=30.0)
            if _t.is_alive():
                result = {"ok": False, "error": "timeout", "data": {
                    "text": "Command timed out. No direct route matched and LLM did not respond within 30s.",
                    "provider": "RPC", "error": "timeout",
                }}
            elif _ai_exc[0] is not None:
                result = {"ok": False, "error": str(_ai_exc[0])}
            else:
                result = _ai_result[0]
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._json_response(200, result)

    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self._json_response(200, {"ok": True})

    def _json_response(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress per-request console noise


def start_server(bridge, port: int = 8765, host: str = "127.0.0.1"):
    """Start the chat RPC server in a daemon thread.

    Args:
        bridge: Bridge instance (must have .ai_ask() method)
        port:   Port to listen on (default 8765)
        host:   Bind address (default 127.0.0.1 - localhost only)
    """
    global _bridge
    _bridge = bridge
    httpd = ThreadingHTTPServer((host, port), _ChatRPCHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
