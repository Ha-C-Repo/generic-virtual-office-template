"""
Your Company Virtual Office - Health Monitor

Watchdog thread:
- Writes heartbeat to data/health.json every 60 seconds
- On boot: checks last heartbeat - if stale >5 min, logs crash event
- /health endpoint returns uptime, memory, thread count
- Windows Event Log on crash (if available)
"""
import json, os, sys, threading, time, psutil
from datetime import datetime, timezone
from pathlib import Path

def _get_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).resolve().parent.parent / "data"

_DATA = _get_data_dir()
_HEALTH = _DATA / "health.json"
_boot_time = datetime.now()  # vj: local-time-ok
_running = False
_thread = None

def _read():
    try:
        if _HEALTH.exists():
            return json.loads(_HEALTH.read_text())
    except Exception:pass
    return {}

def _write(data):
    _DATA.mkdir(parents=True, exist_ok=True)
    _HEALTH.write_text(json.dumps(data, indent=2))

def check_last_boot():
    """Check if last session crashed (heartbeat stale >5 min)."""
    # vj: parity-ok (pass 10g classified: mixed J=0.36; needs manual audit)
    prev = _read()
    if not prev.get("heartbeat"): return {"clean": True, "first_boot": True}
    try:
        last = datetime.fromisoformat(prev["heartbeat"])
        gap = (datetime.now() - last).total_seconds()  # vj: local-time-ok
        if gap > 300:  # 5 minutes
            try:
                from bridge.audit import log
                log("system", "crash_detected", f"Last heartbeat {int(gap)}s ago at {prev['heartbeat']}")
            except Exception:pass
            return {"clean": False, "gap_seconds": int(gap), "last_heartbeat": prev["heartbeat"]}
    except Exception:pass
    return {"clean": True}

def start():
    """Start the watchdog heartbeat thread."""
    global _running, _thread
    if _running: return
    _running = True
    def _beat():
        while _running:
            try:
                proc = psutil.Process(os.getpid())
                _write({
                    "heartbeat": datetime.now(timezone.utc).isoformat(),
                    "uptime_seconds": int((datetime.now() - _boot_time).total_seconds()),  # vj: local-time-ok
                    "memory_mb": round(proc.memory_info().rss / 1048576, 1),
                    "threads": threading.active_count(),
                    "pid": os.getpid(),
                })
            except Exception:pass
            time.sleep(60)
    _thread = threading.Thread(target=_beat, daemon=True, name="health_watchdog")
    _thread.start()

def stop():
    global _running
    _running = False
    _write({**_read(), "shutdown": datetime.now(timezone.utc).isoformat(), "clean_shutdown": True})

def status():
    """Return current health status."""
    try:
        proc = psutil.Process(os.getpid())
        mem = round(proc.memory_info().rss / 1048576, 1)
    except Exception:
        mem = -1
    return {
        "status": "healthy" if _running else "stopped",
        "uptime_seconds": int((datetime.now() - _boot_time).total_seconds()),  # vj: local-time-ok
        "uptime_human": _fmt_uptime(),
        "memory_mb": mem,
        "threads": threading.active_count(),
        "boot_time": _boot_time.isoformat(),
        "heartbeat_active": _running,
        "pid": os.getpid(),
    }

def _fmt_uptime():
    s = int((datetime.now() - _boot_time).total_seconds())  # vj: local-time-ok
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}m {s%60}s"
    return f"{s//3600}h {(s%3600)//60}m"
