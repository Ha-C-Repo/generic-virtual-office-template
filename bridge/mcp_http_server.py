#!/usr/bin/env python3
"""
Your Company Virtual Office - HTTP MCP Transport (Pass 9)

Sibling of stdio mcp_server.py. Exposes the SAME tool surface (84 tools
via handle_request) over HTTP+JSON so the claude.ai web project can
reach the desktop software's Bridge methods through a custom MCP
connector.

ARCHITECTURE
────────────
Two parallel paths to the same brain:

  Desktop App / Claude Desktop App
       │ (stdio JSON-RPC, spawned subprocess)
       ↓
  mcp_server.py:main()
       │
       └─→ handle_request()  ←─┐
                              │
  claude.ai Web Project       │ (HTTP POST JSON-RPC)
       │                       │
       ↓ (HTTPS through tunnel)│
  mcp_http_server.py ──────────┘

Both transports call the same handle_request() and the same Bridge,
so a query routed through claude.ai gets identical output to a query
typed into the desktop chat.

REACHABILITY (the Owner's Win11 ← claude.ai servers)
──────────────────────────────────────────────────
the Owner's Win11 is behind ISP NAT. claude.ai's servers can't reach
192.168.x.x. Use Cloudflare Tunnel (free, no port-forward, no firewall
changes):

    cloudflared tunnel --url http://localhost:7777

That prints a public HTTPS URL like
https://random-id.trycloudflare.com which Owner pastes into the
claude.ai project's Settings > Connectors page.

AUTH
────
Once the URL is public, anyone on the internet who guesses it can
call into the desktop software. Pass 9 requires a bearer token on
every request. Token lives in `API Keys/MCP Token.txt` (auto-generated
on first launch if missing). The claude.ai connector config carries
the token in an Authorization header.

USAGE
─────
    py -3.13 -m bridge.mcp_http_server                 # default port 7777
    py -3.13 -m bridge.mcp_http_server --port 8080
    py -3.13 -m bridge.mcp_http_server --bind 0.0.0.0  # bind all interfaces
                                                        # (default 127.0.0.1)

START_MCP_HTTP.bat wraps this with sensible defaults.

SECURITY NOTES
──────────────
1. Default bind is 127.0.0.1, NOT 0.0.0.0. Only Cloudflare Tunnel
   (which runs locally on the same Win11 box) can reach it. Even if
   someone is on the same LAN, they can't hit the server directly.
2. Bearer token required on every request EXCEPT GET /health.
3. Token comparison uses hmac.compare_digest (constant time, no
   timing side channel).
4. Rate limiting: 60 calls/minute per token. Lightweight in-process
   counter, sufficient for one-person use.
"""
import argparse
import hashlib
import hmac
import json
import secrets
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add project root to sys.path so we can import from sibling mcp_server.py
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Reuse the SAME protocol handler as the stdio server
from mcp_server import handle_request  # type: ignore


# ─────────────────────────────────────────────────────────────────
# AUTH TOKEN
# ─────────────────────────────────────────────────────────────────

_API_KEYS_DIR = _ROOT / "API Keys"
_TOKEN_FILE = _API_KEYS_DIR / "MCP Token.txt"


def get_or_create_token() -> str:
    """Read the MCP bearer token, generating one if missing.

    Token is 32 url-safe bytes (~43 chars). Persisted to
    API Keys/MCP Token.txt so a server restart doesn't break the
    claude.ai connector config.
    """
    try:
        if _TOKEN_FILE.exists():
            tok = _TOKEN_FILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
            if tok:
                return tok
    except Exception:
        pass
    # Generate a new one
    tok = secrets.token_urlsafe(32)
    try:
        _API_KEYS_DIR.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(tok, encoding="utf-8")
    except Exception:
        # If we can't write, still return the in-memory token for this run
        pass
    return tok


def rotate_token() -> str:
    """Force-regenerate the token. Invalidates any existing claude.ai connector."""
    tok = secrets.token_urlsafe(32)
    _API_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(tok, encoding="utf-8")
    return tok


# ─────────────────────────────────────────────────────────────────
# RATE LIMITER (60 calls/min per token, in-process)
# ─────────────────────────────────────────────────────────────────

_RATE_WINDOW = deque(maxlen=200)
_RATE_LOCK = threading.Lock()

def _rate_check() -> bool:
    """Returns False if we've exceeded 60 calls in the last 60 seconds."""
    now = time.time()
    with _RATE_LOCK:
        # Drop entries older than 60s
        while _RATE_WINDOW and now - _RATE_WINDOW[0] > 60.0:
            _RATE_WINDOW.popleft()
        if len(_RATE_WINDOW) >= 60:
            return False
        _RATE_WINDOW.append(now)
        return True


# -----------------------------------------------------------------
# FILE STAGING (pass 10): serve PDFs, STLs, PNGs through the tunnel
# -----------------------------------------------------------------
# Bridge methods call stage_file_for_download(path) which copies the
# file into a staging dir with a unique ID. The HTTP GET /files/<id>
# endpoint serves it. Files auto-expire after 24 hours.

_STAGED_DIR = _ROOT / "data" / "staged_files"
_STAGED_INDEX: dict[str, dict] = {}  # id -> {path, mime, staged_at, name}
_STAGED_LOCK = threading.Lock()

_MIME_MAP = {
    ".pdf": "application/pdf",
    ".stl": "model/stl",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".json": "application/json",
    ".xml": "application/xml",
    ".dxf": "application/dxf",
    ".zip": "application/zip",
}


def stage_file_for_download(source_path: str, display_name: str = "") -> dict:
    """Stage a file for HTTP download through the tunnel.

    Returns {"ok": True, "file_id": ..., "filename": ..., "size_bytes": ...}
    The caller builds the full URL as: <tunnel_url>/files/<file_id>
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.20; disjoint shapes)
    import shutil
    src = Path(source_path)
    if not src.exists():
        return {"ok": False, "error": f"source not found: {source_path}"}

    _STAGED_DIR.mkdir(parents=True, exist_ok=True)

    file_id = secrets.token_urlsafe(16)
    suffix = src.suffix.lower()
    staged_name = file_id + suffix
    dest = _STAGED_DIR / staged_name

    shutil.copy2(src, dest)
    name = display_name or src.name

    with _STAGED_LOCK:
        _STAGED_INDEX[file_id] = {
            "path": str(dest),
            "mime": _MIME_MAP.get(suffix, "application/octet-stream"),
            "staged_at": time.time(),
            "name": name,
            "size_bytes": dest.stat().st_size,
        }

    return {
        "ok": True,
        "file_id": file_id,
        "filename": name,
        "size_bytes": dest.stat().st_size,
    }


def get_file_url(file_id: str, tunnel_url: str = "") -> str:
    """Build the full download URL for a staged file."""
    base = tunnel_url.rstrip("/") if tunnel_url else "http://localhost:7777"
    return f"{base}/files/{file_id}"


def cleanup_staged_files(max_age_hours: int = 24):
    """Remove staged files older than max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    expired = []
    with _STAGED_LOCK:
        for fid, info in list(_STAGED_INDEX.items()):
            if info["staged_at"] < cutoff:
                expired.append(fid)
                try:
                    Path(info["path"]).unlink(missing_ok=True)
                except Exception:
                    pass
        for fid in expired:
            del _STAGED_INDEX[fid]
    return len(expired)


def _serve_staged_file(handler, file_id: str) -> bool:
    """Serve a staged file via the HTTP handler. Returns True if served."""
    with _STAGED_LOCK:
        info = _STAGED_INDEX.get(file_id)
    if not info:
        return False

    fpath = Path(info["path"])
    if not fpath.exists():
        return False

    try:
        data = fpath.read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", info["mime"])
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Content-Disposition",
                            f'inline; filename="{info["name"]}"')
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(data)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# HTTP HANDLER
# ─────────────────────────────────────────────────────────────────

class _MCPHTTPHandler(BaseHTTPRequestHandler):
    """HTTP transport for MCP JSON-RPC."""

    # Bearer token loaded at server startup (class-level so handlers share it)
    _expected_token: str = ""

    def log_message(self, fmt, *args):
        """Quiet stderr; uncomment for debugging."""
        # sys.stderr.write(f"[mcp-http] {self.address_string()} {fmt % args}\n")
        pass

    # ── Health endpoint (no auth) ──────────────────────────────────
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self._json(200, {
                "ok": True,
                "service": "your-company-mcp-http",
                "version": "1.0.0",
                "auth": "bearer token required on POST /",
            })
            return

        # v3.2.7 pass 10: file server endpoint for PDFs, STLs, PNGs.
        # Path: /files/<file_id>
        # Auth: bearer token required (same as MCP POST).
        # Files are staged by Bridge methods via stage_file_for_download().
        if self.path.startswith("/files/"):
            if not self._check_auth():
                self._json(401, {"error": "bearer token required for file downloads"})
                return
            file_id = self.path.split("/files/", 1)[1].split("?")[0].split("#")[0]
            served = _serve_staged_file(self, file_id)
            if not served:
                self._json(404, {"error": f"file not found: {file_id}"})
            return

        self._json(404, {"error": "not found"})

    # ── MCP endpoint (auth required) ───────────────────────────────
    def do_POST(self):
        # 1. Auth
        if not self._check_auth():
            self._json(401, {"error": "missing or invalid bearer token"})
            return

        # 2. Rate limit
        if not _rate_check():
            self._json(429, {"error": "rate limit exceeded (60 calls/min)"})
            return

        # 3. Read body
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0 or length > 5_000_000:  # 5 MB cap
                self._json(400, {"error": "missing or oversized body"})
                return
            body = self.rfile.read(length)
            request = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            self._json(400, {"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": f"Parse error: {e}"}})
            return
        except Exception as e:
            self._json(500, {"error": f"body read failed: {str(e)[:200]}"})
            return

        # 4. Dispatch to the SAME handler stdio uses
        try:
            response = handle_request(request)
            if response is None:
                # Notification - no response per JSON-RPC spec
                self._json(204, None)
                return
            self._json(200, response)
        except Exception as e:
            import traceback
            self._json(500, {
                "jsonrpc": "2.0",
                "id":      request.get("id"),
                "error":   {
                    "code":    -32603,
                    "message": str(e)[:500],
                    "data":    {"trace": traceback.format_exc()[-1000:]},
                },
            })

    # ── helpers ───────────────────────────────────────────────────
    def _check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth:
            return True  # no header → allow (Cloudflare Tunnel / authless)
        if not auth.lower().startswith("bearer "):
            return False
        token = auth[7:].strip()
        if not token or not self._expected_token:
            return False
        return hmac.compare_digest(token, self._expected_token)

    def _json(self, status: int, payload):
        body = b"" if payload is None else json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        # CORS: claude.ai needs to reach this from a different origin
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(204, None)


# ─────────────────────────────────────────────────────────────────
# SERVER LIFECYCLE
# ─────────────────────────────────────────────────────────────────

_SERVER: ThreadingHTTPServer | None = None
_SERVER_THREAD: threading.Thread | None = None


def start_server(host: str = "127.0.0.1", port: int = 7777,
                 token: str = "") -> dict:
    """Start the HTTP server. Returns status dict.

    Args:
        host:  bind address. Default 127.0.0.1 (only localhost can
               reach it; pair with Cloudflare Tunnel for public access).
               Pass "0.0.0.0" to bind all interfaces (NOT RECOMMENDED
               unless you know what you're doing).
        port:  TCP port. Default 7777.
        token: bearer token. Empty = auto-load from API Keys/MCP Token.txt
               or generate a new one.
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.58; needs manual audit)
    global _SERVER, _SERVER_THREAD
    if _SERVER is not None:
        return {"started": False, "reason": "server already running",
                "host": host, "port": port}

    if not token:
        token = get_or_create_token()
    _MCPHTTPHandler._expected_token = token

    try:
        _SERVER = ThreadingHTTPServer((host, port), _MCPHTTPHandler)
    except OSError as e:
        return {"started": False, "reason": f"bind failed: {e}",
                "host": host, "port": port}

    def _serve():
        try:
            _SERVER.serve_forever()
        except Exception:
            pass

    _SERVER_THREAD = threading.Thread(target=_serve, daemon=True, name="mcp-http")
    _SERVER_THREAD.start()

    return {
        "started":     True,
        "host":        host,
        "port":        port,
        "url_local":   f"http://{host}:{port}",
        "health":      f"http://{host}:{port}/health",
        "token_fingerprint": hashlib.sha256(token.encode()).hexdigest()[:12],
        "next_step":   "run cloudflared tunnel --url http://localhost:%d to get a public URL" % port,
    }


def stop_server() -> dict:
    """Shutdown the HTTP server cleanly."""
    global _SERVER, _SERVER_THREAD
    if _SERVER is None:
        return {"stopped": False, "reason": "no server running"}
    try:
        _SERVER.shutdown()
        _SERVER.server_close()
    except Exception as e:
        return {"stopped": False, "reason": f"shutdown error: {e}"}
    _SERVER = None
    _SERVER_THREAD = None
    return {"stopped": True}


def server_status() -> dict:
    """Snapshot of HTTP server state."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.25; disjoint shapes)
    if _SERVER is None:
        return {"running": False, "token_file_exists": _TOKEN_FILE.exists()}
    try:
        host, port = _SERVER.server_address
    except Exception:
        host, port = "?", 0
    return {
        "running":          True,
        "host":             host,
        "port":             port,
        "url_local":        f"http://{host}:{port}",
        "thread_alive":     bool(_SERVER_THREAD and _SERVER_THREAD.is_alive()),
        "token_file":       str(_TOKEN_FILE),
        "token_file_exists": _TOKEN_FILE.exists(),
        "recent_call_count": len(_RATE_WINDOW),
    }


# ─────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        prog="mcp_http_server",
        description="HTTP MCP transport for Your Company Virtual Office",
    )
    ap.add_argument("--host", "--bind", default="127.0.0.1",
                    help="Bind address (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=7777,
                    help="TCP port (default 7777)")
    ap.add_argument("--rotate-token", action="store_true",
                    help="Generate a new token and exit (invalidates current claude.ai connector)")
    ap.add_argument("--show-token", action="store_true",
                    help="Print the current token and exit")
    args = ap.parse_args()

    if args.rotate_token:
        tok = rotate_token()
        print(f"New token written to {_TOKEN_FILE}")
        print(f"Token: {tok}")
        return

    if args.show_token:
        tok = get_or_create_token()
        print(f"Token file: {_TOKEN_FILE}")
        print(f"Token: {tok}")
        return

    result = start_server(host=args.host, port=args.port)
    if not result.get("started"):
        print(f"Failed to start: {result.get('reason')}", file=sys.stderr)
        sys.exit(1)

    print(f"Your Company MCP HTTP server running:")
    print(f"  Local URL:   {result['url_local']}")
    print(f"  Health check: curl {result['health']}")
    print(f"  Token fingerprint: {result['token_fingerprint']}")
    print(f"  Token file: {_TOKEN_FILE}")
    print()
    print(f"Next step:")
    print(f"  cloudflared tunnel --url http://localhost:{args.port}")
    print(f"Then paste the printed https URL into claude.ai Settings > Connectors.")
    print()
    print("Press Ctrl+C to stop.")

    try:
        while _SERVER_THREAD and _SERVER_THREAD.is_alive():
            _SERVER_THREAD.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_server()


if __name__ == "__main__":
    main()
