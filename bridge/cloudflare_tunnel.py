"""
Cloudflare quick-tunnel manager.

Spawns `cloudflared tunnel --url http://localhost:<port>` on app launch,
parses the trycloudflare.com URL from stdout in a background thread,
and stores it so the SETTINGS tab can display it with a copy button.

Called from main.py; Bridge methods poll get_status().
"""
import re
import subprocess
import threading

_proc: "subprocess.Popen | None" = None
_url: "str | None" = None
_lock = threading.Lock()
_URL_RE = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')


def start(port: int = 7777) -> None:
    """Spawn cloudflared quick tunnel targeting localhost:port.

    No-ops silently if cloudflared is not on PATH or already running.
    URL is parsed asynchronously; poll get_status() to retrieve it.
    """
    global _proc, _url

    with _lock:
        if _proc is not None and _proc.poll() is None:
            return
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            print("[tunnel] cloudflared not on PATH - skipping auto-tunnel", flush=True)
            return
        except Exception as e:
            print(f"[tunnel] start failed: {e}", flush=True)
            return
        _proc = proc
        _url = None

    def _reader():
        global _url
        try:
            for line in proc.stdout:
                m = _URL_RE.search(line)
                if m:
                    _url = m.group(0)
                    print(f"[tunnel] public URL: {_url}", flush=True)
                    break
        except Exception:
            pass

    threading.Thread(target=_reader, daemon=True, name="cf_tunnel_reader").start()
    print(f"[tunnel] cloudflared started (pid {proc.pid}) -> port {port}", flush=True)


def get_status() -> dict:
    """Return current tunnel state for Bridge callers.

    Returns dict with keys:
      running (bool)   - True if subprocess is alive
      url (str|None)   - public trycloudflare.com URL once parsed
    """
    running = _proc is not None and _proc.poll() is None
    return {"running": running, "url": _url}


def stop() -> None:
    """Terminate the cloudflared subprocess on app shutdown."""
    global _proc, _url
    with _lock:
        if _proc:
            try:
                _proc.terminate()
            except Exception:
                pass
            _proc = None
            _url = None
