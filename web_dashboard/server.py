"""
Your Company VirtualOffice - Web Admin Dashboard server.

Exposes an allowlisted subset of the Bridge over HTTP with token auth.
New file. Does not modify bridge/ or main.py. Run from project root:

    py web_dashboard\\server.py

Stdlib only. Port 8765. Token in web_dashboard/.token (auto-generated
on first run, printed once to console).
"""

import base64
import json
import logging
import secrets
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # project root
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TOKEN_FILE = HERE / ".token"
ACCESS_LOG = HERE / "access.log"
UPLOAD_DIR = ROOT / "_requests" / "dashboard_uploads"
PORT = 8765

logging.basicConfig(
    filename=str(ACCESS_LOG), level=logging.INFO,
    format="%(asctime)s %(message)s")
log = logging.getLogger("dashboard")

# Bridge methods callable via POST /api/invoke. Read paths plus the
# pipeline actions Owner uses daily. Nothing destructive, nothing that
# sends outbound, nothing that touches rates, files on disk, or the site.
ALLOWED_METHODS = {
    # status / dashboard
    "daily_status", "get_kpis", "get_health", "morning_briefing",
    "get_pipeline_summary", "get_steel_brief_context",
    # bids
    "list_bids", "get_bid_detail", "get_bid_leads", "next_bid_number",
    "add_bid", "update_bid_status", "get_bid_template",
    "check_bid_emr", "check_bid_compliance",
    # compliance (read only)
    "compliance_summary", "get_compliance", "get_compliance_stats",
    "get_isn_scorecard",
    # misc read
    "get_message_log",
}

_bridge_lock = threading.Lock()


def _get_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    tok = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(tok, encoding="utf-8")
    print(f"[dashboard] NEW ACCESS TOKEN (share with Owner/Joseph only): {tok}")
    return tok


TOKEN = _get_token()


def _bridge():
    from bridge.api import Bridge   # late import, same pattern as mcp_server
    return Bridge()


class Handler(BaseHTTPRequestHandler):
    server_version = "NCVO-Dash/1.0"

    # ---------- plumbing ----------
    def _send(self, code: int, payload, ctype="application/json"):
        body = payload if isinstance(payload, (bytes, bytearray)) else \
            json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        auth = self.headers.get("Authorization", "")
        tok = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") \
            else self.headers.get("X-Auth-Token", "").strip()
        ok = secrets.compare_digest(tok, TOKEN) if tok else False
        if not ok:
            log.info("DENY %s %s from %s", self.command, self.path,
                     self.client_address[0])
        return ok

    def _json_body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > 64 * 1024 * 1024:   # 64 MB cap
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):   # quiet stderr; file log instead
        log.info("%s %s", self.client_address[0], fmt % args)

    # ---------- routes ----------
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            page = (HERE / "dashboard.html").read_bytes()
            return self._send(200, page, "text/html; charset=utf-8")
        if path == "/api/ping":
            return self._send(200, {"ok": True, "ts": _now()})
        if not self._authed():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        if path == "/api/status":
            return self._api_status()
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self._authed():
            return self._send(401, {"ok": False, "error": "unauthorized"})
        path = self.path.split("?")[0]
        body = self._json_body()
        if path == "/api/invoke":
            return self._api_invoke(body)
        if path == "/api/chat":
            return self._api_chat(body)
        if path == "/api/upload":
            return self._api_upload(body)
        return self._send(404, {"ok": False, "error": "not found"})

    # ---------- handlers ----------
    def _api_status(self):
        out, b = {}, _bridge()
        for m in ("daily_status", "get_kpis", "get_pipeline_summary",
                  "compliance_summary"):
            try:
                with _bridge_lock:
                    out[m] = getattr(b, m)()
            except Exception as e:
                out[m] = {"ok": False, "error": str(e)}
        self._send(200, {"ok": True, "data": out})

    def _api_invoke(self, body: dict):
        method = str(body.get("method", ""))
        args = body.get("args") or {}
        if method not in ALLOWED_METHODS:
            log.info("BLOCKED method=%s from %s", method, self.client_address[0])
            return self._send(403, {"ok": False,
                                    "error": f"method '{method}' not allowed on the dashboard"})
        try:
            import inspect
            b = _bridge()
            fn = getattr(b, method)
            sig = inspect.signature(fn)
            valid = {k: v for k, v in args.items() if k in sig.parameters}
            with _bridge_lock:
                result = fn(**valid)
            log.info("INVOKE %s args=%s from %s", method, list(valid),
                     self.client_address[0])
            return self._send(200, result)
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    def _api_chat(self, body: dict):
        message = str(body.get("message", "")).strip()
        history = body.get("history") or []
        files = body.get("files") or []
        if not message and not files:
            return self._send(400, {"ok": False, "error": "empty message"})
        # files: [{name, type, cat, data}] straight through to ai_ask
        try:
            b = _bridge()
            with _bridge_lock:
                result = b.ai_ask(message=message, mode="owner",
                                  history=history, files=files)
            log.info("CHAT %d chars, %d files from %s", len(message),
                     len(files), self.client_address[0])
            return self._send(200, result)
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    def _api_upload(self, body: dict):
        name = Path(str(body.get("name", "upload.bin"))).name   # strip paths
        data = body.get("data_b64", "")
        if not data:
            return self._send(400, {"ok": False, "error": "no data"})
        try:
            raw = base64.b64decode(data)
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            dest = UPLOAD_DIR / f"{stamp}_{name}"
            dest.write_bytes(raw)
            log.info("UPLOAD %s (%d bytes) from %s", dest.name, len(raw),
                     self.client_address[0])
            return self._send(200, {"ok": True,
                                    "data": {"saved": str(dest), "bytes": len(raw)}})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    addr = ("0.0.0.0", PORT)
    httpd = ThreadingHTTPServer(addr, Handler)
    print(f"[dashboard] Your Company VirtualOffice dashboard on http://0.0.0.0:{PORT}")
    print(f"[dashboard] token file: {TOKEN_FILE}")
    log.info("SERVER START port=%s", PORT)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
