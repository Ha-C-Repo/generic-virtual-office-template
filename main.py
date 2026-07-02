"""
Your Company Virtual Office - Desktop Launcher
================================================
Serves the frontend via localhost HTTP (Edge WebView2 requires http://)
and opens a pywebview window bridged to the Python AI engine.

CRITICAL BUG FIX APPLIED:
  _SilentHandler is defined at MODULE LEVEL - not inside a function.
  Python 3.13 + PyInstaller + --noconsole cannot compile classes that are
  defined inside functions. Moving it here fixes:
  "TypeError: function() argument 'code' must be code, not str"
"""


import http.server
import os
import socket
import socketserver
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path


# ── Pywebview import (deferred - MCP mode doesn't need a GUI) ─────────────
# When the EXE is invoked with --mcp-server, we run as a stdio JSONRPC daemon
# for Claude Desktop / Cowork. Pywebview is irrelevant in that mode, so we
# only fail on missing pywebview when the user actually wants the GUI.
_MCP_MODE = (len(sys.argv) > 1 and sys.argv[1] in ("--mcp-server", "--mcp"))

if not _MCP_MODE:
    try:
        import webview
    except ImportError as _ie:
        _msg = (
            "pywebview is not installed.\n\n"
            f"Error: {_ie}\n\n"
            "Run: py -3.13 -m pip install pywebview"
        )
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, _msg, "Virtual Office - Missing Dependency", 0x10)
        else:
            print(_msg, file=sys.stderr)
        sys.exit(1)


# ── Package imports (with clear error if misbuilt) ─────────────────────────
try:
    from vo_app import __app_name__, __version__
except ImportError as _ie:
    _msg = (
        f"Your Company Virtual Office failed to load its package.\n\n"
        f"Error: {_ie}\n\n"
        "If you built the EXE yourself:\n"
        "  1. Use make_exe.bat (not raw pyinstaller)\n"
        "  2. make_exe.bat uses VirtualOffice.spec which bundles\n"
        "     Python packages via collect_submodules() correctly.\n"
        "  3. --add-data for Python packages causes this error."
    )
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, _msg, "Virtual Office - Package Error", 0x10)
    else:
        print(_msg, file=sys.stderr)
    sys.exit(1)


from vo_app._resources import resource_path, is_frozen


# ── bridge/ integrity check (P6.3, fixed P18.2) ───────────────────────────
# Runs before Bridge import so a truncated source is caught here, not as a
# cryptic SyntaxError deep inside the import chain.
#
# P18.2 fix: replaced compileall.compile_dir() with ast.parse().
# compile_dir writes .pyc files to __pycache__/ - fails silently in
# read-only Program Files installs, triggering a false-positive dialog.
# ast.parse reads each file in memory, never touches __pycache__,
# works in any install path regardless of write permissions.
def _check_bridge_integrity() -> None:
    import ast
    if getattr(sys, 'frozen', False):
        bridge_dir = Path(sys.executable).parent / "_internal" / "bridge"
    else:
        bridge_dir = Path(__file__).resolve().parent / "bridge"
    if not bridge_dir.is_dir():
        return
    bad = []
    for py in bridge_dir.rglob("*.py"):
        try:
            ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append((py.name, e.lineno, str(e)))
    if bad:
        names = ", ".join(f"{n}:{l}" for n, l, _ in bad[:3])
        _msg = (
            "VirtualOffice cannot start: bridge/ source files are corrupt.\n\n"
            f"Truncated files: {names}\n\n"
            "Fix: run RECOVER.bat from the install folder, then restart."
        )
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, _msg, "Virtual Office - Bridge Corrupt", 0x10)
        else:
            print(_msg, file=sys.stderr)
        sys.exit(2)


if not _MCP_MODE:
    _check_bridge_integrity()

from bridge.api import Bridge


# ── Paths ──────────────────────────────────────────────────────────────────
_FRONTEND_DIR = resource_path("frontend")

# ── Fatal log ──────────────────────────────────────────────────────────────
def _write_fatal(exc: BaseException) -> Path:
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "YourCompany" / "VirtualOffice"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "launch.log"
    content = (
        f"{'='*64}\n"
        f"Your Company Virtual Office v{__version__}  -  fatal startup error\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"Frozen:    {is_frozen()}\n"
        f"Python:    {sys.version}\n"
        f"Platform:  {sys.platform}\n"
        f"Exe:       {sys.executable}\n"
        f"{'-'*64}\n"
        f"{traceback.format_exc()}\n"
        f"{'='*64}\n"
    )
    log_path.write_text(content, encoding="utf-8")
    return log_path


# ── HTTP server (module-level class - PyInstaller Python 3.13 fix) ─────────
#
# CRITICAL: This class MUST be at module level.
# Python 3.13 + PyInstaller + --noconsole cannot compile classes defined
# inside functions: "TypeError: function() argument 'code' must be code, not str"
# The directory is injected via a class variable before server starts.

class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    """Static-file handler that serves from serve_dir silently."""
    serve_dir: str = "."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.__class__.serve_dir, **kwargs)

    def log_message(self, format, *args):
        pass  # suppress per-request logging in production


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_local_server(directory: Path, port: int):
    """Serve directory on 127.0.0.1:port in a daemon thread."""
    _SilentHandler.serve_dir = str(directory)
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), _SilentHandler)
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


# ── Auto-backup on launch (v3.2) ──────────────────────────────────────────
def _auto_backup_on_launch():
    """Create a ZIP backup of all data files on every launch. Keep last 7 days."""
    import zipfile
    import glob

    backup_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "YourCompany" / "VirtualOffice" / "Backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Source: all SQLite DBs + JSON configs in data/ and bridge/data/
    app_root = Path(__file__).parent
    data_files = []
    for pattern in ["data/*.json", "data/*.db", "data/*.csv", "data/*.enc",
                    "bridge/data/*.db"]:
        data_files.extend(glob.glob(str(app_root / pattern)))

    if not data_files:
        return  # Nothing to back up

    # Create today's backup
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")  # vj: local-display-ok
    backup_path = backup_dir / f"YourCo_AutoBackup_{ts}.zip"

    # Skip if today's backup already exists (prevents double-backup on restart)
    today_prefix = f"YourCo_AutoBackup_{datetime.now().strftime('%Y-%m-%d')}"  # vj: local-display-ok
    existing_today = list(backup_dir.glob(f"{today_prefix}*.zip"))
    if existing_today:
        return

    with zipfile.ZipFile(str(backup_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in data_files:
            zf.write(fp, os.path.relpath(fp, str(app_root)))

    # Prune backups older than 7 days
    all_backups = sorted(backup_dir.glob("YourCo_AutoBackup_*.zip"))
    cutoff = datetime.now(timezone.utc).timestamp() - (7 * 86400)
    for bk in all_backups:
        if bk.stat().st_mtime < cutoff:
            bk.unlink()


# ── Cowork companion startup check (Phase 1, psutil) ─────────────────────
def _ensure_cowork_running() -> None:
    """Check if the Cowork companion is running; auto-start it if not."""
    try:
        import psutil
        import subprocess
        running = any(
            "cowork" in (p.name() or "").lower()
            for p in psutil.process_iter(["name"])
        )
        if running:
            print("[main] Cowork companion already running", flush=True)
            return
        local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        candidates = [
            local_appdata / "YourCompany" / "Cowork" / "Cowork.exe",
            Path(sys.executable).parent / "Cowork.exe",
        ]
        for exe in candidates:
            if exe.is_file():
                subprocess.Popen(
                    [str(exe)],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                print(f"[main] Cowork companion started: {exe}", flush=True)
                return
        print("[main] Cowork companion not installed (skipped)", flush=True)
    except Exception as e:
        print(f"[main] Cowork startup check warning: {e}", flush=True)


# ── Application run ────────────────────────────────────────────────────────
def _run() -> int:
    if not (_FRONTEND_DIR / "index.html").is_file():
        raise FileNotFoundError(
            f"Frontend not found at {_FRONTEND_DIR}.\n"
            f"Frozen={is_frozen()}, _MEIPASS={getattr(sys, '_MEIPASS', '<unset>')}.\n"
            "Re-run make_exe.bat to rebuild with the shipped .spec file."
        )

    bridge = Bridge()

    # ── Health: crash detection on boot (Joseph P2) ────────────────
    try:
        from bridge.health import check_last_boot, start as health_start
        boot_status = check_last_boot()
        if not boot_status.get("clean"):
            print(f"[main] CRASH DETECTED - last heartbeat was {boot_status.get('gap_seconds', '?')}s ago", flush=True)
        health_start()
        print("[main] health watchdog started (60s heartbeat)", flush=True)
    except Exception as e:
        print(f"[main] health monitor warning: {e}", flush=True)

    # ── Auto-backup on launch (v3.2 - keep last 7 days) ───────────
    try:
        _auto_backup_on_launch()
        print("[main] auto-backup complete", flush=True)
    except Exception as e:
        print(f"[main] auto-backup warning: {e}", flush=True)

    # ── Memory: start conversation session (Joseph P1) ─────────────
    try:
        from bridge.memory import start_session
        sid = start_session()
        print(f"[main] conversation session {sid} started", flush=True)
    except Exception as e:
        print(f"[main] memory warning: {e}", flush=True)

    port = _pick_free_port()
    httpd = _start_local_server(_FRONTEND_DIR, port)
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"[main] serving frontend at {url}", flush=True)

    # ── Start background services ──────────────────────────────────────
    try:
        from bridge.notifications import start_background_poller, load_config, start_webhook_server
        start_background_poller(bridge.ai_ask)
        cfg = load_config()
        if cfg.get("webhook_enabled", False):
            start_webhook_server(bridge.ai_ask, port=cfg.get("webhook_port", 7750))
            print(f"[main] webhook server started on port {cfg['webhook_port']}", flush=True)
        print("[main] background pollers started (email, bid scanner, daily summary)", flush=True)
    except Exception as e:
        print(f"[main] background services warning: {e}", flush=True)

    # ── Reminders: follow-up automation (Joseph P2) ────────────────
    try:
        from bridge.reminders import start_reminder_loop
        from bridge.sms_channel import send_to_owner
        start_reminder_loop(sms_fn=send_to_owner)
        print("[main] reminder loop started (30min interval)", flush=True)
    except Exception as e:
        print(f"[main] reminders warning: {e}", flush=True)

    # ── CoworkScheduler: 5 recurring tasks on CT schedule ─────────────────
    try:
        from bridge.cowork_scheduler import get_scheduler
        get_scheduler().start()
        print("[main] CoworkScheduler started (5 tasks)", flush=True)
    except Exception as e:
        print(f"[main] CoworkScheduler warning: {e}", flush=True)

    # ── Cowork companion: check running, auto-start if not ────────────────
    _ensure_cowork_running()

    # ── Cloudflare quick tunnel (auto-start for Claude MCP connector) ─────
    try:
        from bridge.cloudflare_tunnel import start as _tunnel_start
        _tunnel_start(port=7777)
    except Exception as e:
        print(f"[main] tunnel warning: {e}", flush=True)

    # ── Chat RPC server (P18.4: localhost:8765 for Cowork/automation) ─────
    try:
        from bridge.chat_rpc_server import start_server as _chat_rpc_start
        _chat_rpc_start(bridge, port=8765)
        print("[main] chat RPC server started on http://127.0.0.1:8765/chat", flush=True)
    except Exception as e:
        print(f"[main] chat RPC server warning: {e}", flush=True)

    webview.create_window(
        title=f"Your Company - Virtual Office v{__version__}  |  Houston, TX",
        url=url,
        js_api=bridge,
        width=1440,
        height=900,
        min_size=(1200, 780),
        background_color="#0E1117",
        resizable=True,
        text_select=True,
    )

    try:
        webview.start(debug=False)
    finally:
        # ── Graceful shutdown (Joseph P3) ──────────────────────────
        print("[main] shutting down...", flush=True)
        try:
            from bridge.cloudflare_tunnel import stop as _tunnel_stop
            _tunnel_stop()
        except Exception:
            pass
        try:
            bridge.shutdown()
        except Exception:
            pass
        httpd.shutdown()

    return 0


def main() -> int:
    # ─── --mcp-server flag: run as MCP server over stdio (no UI) ──────
    # Claude Desktop invokes the EXE this way (per claude_desktop_config.json).
    # We import lazily so MCP mode adds no startup overhead to the GUI path.
    if len(sys.argv) > 1 and sys.argv[1] in ("--mcp-server", "--mcp"):
        try:
            # Make sure project root is on sys.path even when frozen
            here = Path(__file__).resolve().parent
            if str(here) not in sys.path:
                sys.path.insert(0, str(here))
            from mcp_server import main as mcp_main
            return mcp_main() or 0
        except SystemExit as se:
            return int(se.code or 0)
        except BaseException as e:
            # Stderr is the only safe place to write - stdout is reserved for JSONRPC
            sys.stderr.write(f"MCP server fatal: {type(e).__name__}: {e}\n{traceback.format_exc()}\n")
            return 1

    # ─── Default: launch the GUI ──────────────────────────────────────
    try:
        return _run()
    except BaseException as e:
        log_path = _write_fatal(e)
        if not is_frozen():
            traceback.print_exc()
        if is_frozen() and os.name == "nt":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Your Company Virtual Office could not start.\n\n"
                    f"A crash report was written to:\n{log_path}\n\n"
                    f"Email this file to joseph@yourcompany.example.com.\n\n"
                    f"Error: {type(e).__name__}: {e}",
                    "Virtual Office - Startup Error",
                    0x10,
                )
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
