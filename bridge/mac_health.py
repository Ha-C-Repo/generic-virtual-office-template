"""
Mac Health Monitor - Office iMac Heartbeat
============================================
Monitors the 2012 iMac running BlueBubbles at the office.
Single responsibility: is the gateway alive or dead?

Heartbeat: pings BlueBubbles /api/v1/server/info every 60s.
If 3 consecutive pings fail, status flips to RED.

Optional (if SSH enabled): CPU temp, disk SMART, uptime.
These are nice-to-have. The heartbeat alone catches 95% of failures.
"""

import json
import logging
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("mac_health")


@dataclass
class MacStatus:
    """Current state of the office Mac."""
    alive: bool = False
    last_seen: float = 0.0
    consecutive_failures: int = 0
    bb_version: str = ""
    os_version: str = ""
    uptime_hours: float = 0.0
    cpu_temp_c: Optional[float] = None
    disk_free_gb: Optional[float] = None
    imessage_connected: bool = False
    firebase_connected: bool = False
    error: str = ""

    @property
    def status_color(self) -> str:
        """GREEN = healthy, YELLOW = degraded, RED = down."""
        if not self.alive:
            return "RED"
        if self.consecutive_failures > 0:
            return "YELLOW"
        if self.cpu_temp_c and self.cpu_temp_c > 85:
            return "YELLOW"
        if self.disk_free_gb and self.disk_free_gb < 5:
            return "YELLOW"
        return "GREEN"

    def to_dict(self) -> dict:
        return {
            "alive": self.alive,
            "status": self.status_color,
            "last_seen": self.last_seen,
            "last_seen_ago": f"{time.time() - self.last_seen:.0f}s" if self.last_seen else "never",
            "consecutive_failures": self.consecutive_failures,
            "bb_version": self.bb_version,
            "os_version": self.os_version,
            "uptime_hours": round(self.uptime_hours, 1),
            "cpu_temp_c": self.cpu_temp_c,
            "disk_free_gb": self.disk_free_gb,
            "imessage_connected": self.imessage_connected,
            "firebase_connected": self.firebase_connected,
            "error": self.error,
        }


# Singleton status
_status = MacStatus()
_monitor_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

# Failure threshold before RED
FAIL_THRESHOLD = 3
PING_INTERVAL = 60  # seconds


def _get_bb_config():
    """Get BlueBubbles host/port/password from imessage_gateway config."""
    try:
        from bridge.imessage_gateway import _load_config, _BB_HOST, _BB_PORT, _BB_PASSWORD
        _load_config()
        from bridge import imessage_gateway as ig
        return ig._BB_HOST, ig._BB_PORT, ig._BB_PASSWORD
    except Exception:
        host = os.environ.get("BLUEBUBBLES_HOST", "")
        port = int(os.environ.get("BLUEBUBBLES_PORT", "1234"))
        pwd = os.environ.get("BLUEBUBBLES_PASSWORD", "")
        return host, port, pwd


def ping() -> MacStatus:
    """Single heartbeat ping to BlueBubbles server info endpoint."""
    global _status
    host, port, password = _get_bb_config()

    if not host:
        _status.alive = False
        _status.error = "BLUEBUBBLES_HOST not configured"
        return _status

    url = f"http://{host}:{port}/api/v1/server/info?password={password}"

    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        info = data.get("data", {})
        _status.alive = True
        _status.last_seen = time.time()
        _status.consecutive_failures = 0
        _status.bb_version = info.get("server_version", "")
        _status.os_version = info.get("os_version", "")
        _status.imessage_connected = info.get("detected_imessage", False)
        _status.firebase_connected = info.get("proxy_service_connected", False)
        _status.error = ""

        # BlueBubbles doesn't expose CPU temp directly.
        # If SSH is available, we could query it separately.
        log.debug(f"Mac heartbeat OK: BB {_status.bb_version}, "
                  f"iMessage={_status.imessage_connected}")

    except Exception as e:
        _status.consecutive_failures += 1
        _status.error = str(e)
        if _status.consecutive_failures >= FAIL_THRESHOLD:
            _status.alive = False
            log.warning(f"Mac gateway DOWN: {FAIL_THRESHOLD} consecutive failures. "
                        f"Last error: {e}")
        else:
            log.info(f"Mac ping failed ({_status.consecutive_failures}/{FAIL_THRESHOLD}): {e}")

    return _status


def get_status() -> dict:
    """Get current Mac status as dict for UI health card."""
    return _status.to_dict()


def is_alive() -> bool:
    """Quick check: is the gateway responding?"""
    return _status.alive


def _monitor_loop():
    """Background thread: ping every PING_INTERVAL seconds."""
    log.info(f"Mac health monitor started (interval={PING_INTERVAL}s, "
             f"threshold={FAIL_THRESHOLD})")
    while not _stop_event.is_set():
        try:
            ping()
        except Exception as e:
            log.error(f"Monitor loop error: {e}")
        _stop_event.wait(PING_INTERVAL)
    log.info("Mac health monitor stopped")


def start_monitor():
    """Start background heartbeat monitoring."""
    global _monitor_thread
    if _monitor_thread and _monitor_thread.is_alive():
        return  # Already running
    _stop_event.clear()
    _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True,
                                        name="mac-health-monitor")
    _monitor_thread.start()


def stop_monitor():
    """Stop background monitoring."""
    _stop_event.set()
    if _monitor_thread:
        _monitor_thread.join(timeout=5)
