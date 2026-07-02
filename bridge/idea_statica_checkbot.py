"""
Your Company Virtual Office - IDEA StatiCa Checkbot Integration

IDEA StatiCa BimApi (github.com/idea-statica) allows Tekla/Advance/SDS2
connections to be checked under AISC 360 in batch.

For a small shop: invaluable when you can't afford a full-time connection
engineer. Run batch checks on all unique connections before proposal goes out.

Integration: local IDEA StatiCa installation + BimApi HTTP bridge.
"""

import os, json, httpx, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "idea_checks.db"
    return Path(__file__).resolve().parent.parent / "data" / "idea_checks.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# Default local IDEA StatiCa Checkbot endpoint
IDEA_DEFAULT_URL = "http://localhost:5000"


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS connection_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL, node_id TEXT NOT NULL,
            connection_type TEXT DEFAULT '', members TEXT DEFAULT '',
            check_code TEXT DEFAULT 'AISC360', status TEXT DEFAULT 'PENDING',
            unity_check REAL, result_summary TEXT DEFAULT '',
            checked_at TEXT, created_at TEXT NOT NULL
        );
    """)
    c.commit(); c.close()
_init()


def _get_url():
    url = os.environ.get("IDEA_STATICA_URL", "")
    if not url:
        try:
            from bridge.keyvault import load_keys
            url = load_keys().get("IDEA_STATICA_URL", "")
        except Exception:pass
    return url or IDEA_DEFAULT_URL


def check_connection(project: str, node_id: str, connection_type: str = "",
                     members: str = "") -> dict:
    """Submit a single connection for AISC 360 check via IDEA StatiCa BimApi."""
    # vj: parity-ok (pass 10g classified: mixed J=0.44; needs manual audit)
    url = _get_url()
    now = datetime.now(timezone.utc).isoformat()

    # Log the request
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO connection_checks (project,node_id,connection_type,members,check_code,status,created_at) VALUES (?,?,?,?,?,?,?)",
            (project, node_id, connection_type, members, "AISC360", "CHECKING", now))
        check_id = cur.lastrowid
        c.commit(); c.close()

    try:
        payload = {
            "nodeId": node_id,
            "connectionType": connection_type,
            "members": members.split(",") if members else [],
            "code": "AISC360",
        }
        resp = httpx.post(f"{url}/api/v1/check", json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        unity = result.get("unityCheck", result.get("maxUnityCheck", 0))
        status = "PASS" if unity <= 1.0 else "FAIL"
        summary = result.get("summary", f"Unity check: {unity:.3f}")

        with _lock:
            c = _conn()
            c.execute(
                "UPDATE connection_checks SET status=?, unity_check=?, result_summary=?, checked_at=? WHERE id=?",
                (status, unity, summary[:500], now, check_id))
            c.commit(); c.close()

        return {
            "check_id": check_id, "node_id": node_id, "status": status,
            "unity_check": unity, "summary": summary,
        }
    except httpx.ConnectError:
        _update_status(check_id, "OFFLINE", "IDEA StatiCa not running locally")
        return {"error": "IDEA StatiCa Checkbot not running. Start it at localhost:5000.",
                "check_id": check_id}
    except Exception as e:
        _update_status(check_id, "ERROR", str(e)[:200])
        return {"error": str(e)[:200], "check_id": check_id}


def _update_status(check_id, status, summary):
    with _lock:
        c = _conn()
        c.execute("UPDATE connection_checks SET status=?, result_summary=? WHERE id=?",
                  (status, summary, check_id))
        c.commit(); c.close()


def batch_check(project: str, nodes: list) -> dict:
    """Check multiple connections in batch. For bids with 30+ unique connections."""
    results = []
    passed = 0
    failed = 0
    errors = 0

    for node in nodes:
        r = check_connection(
            project,
            node.get("node_id", ""),
            node.get("connection_type", ""),
            node.get("members", ""),
        )
        results.append(r)
        if r.get("status") == "PASS": passed += 1
        elif r.get("status") == "FAIL": failed += 1
        else: errors += 1

    return {
        "project": project, "total": len(nodes),
        "passed": passed, "failed": failed, "errors": errors,
        "results": results,
        "all_pass": failed == 0 and errors == 0,
    }


def get_project_checks(project: str) -> dict:
    """Get all connection checks for a project."""
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM connection_checks WHERE project=? ORDER BY created_at DESC",
            (project,)).fetchall()
        c.close()
    return {"project": project, "checks": [dict(r) for r in rows], "count": len(rows)}


def get_status():
    """Integration status."""
    url = _get_url()
    online = False
    try:
        resp = httpx.get(f"{url}/api/v1/health", timeout=3)
        online = resp.status_code == 200
    except Exception:pass
    return {
        "url": url,
        "online": online,
        "check_code": "AISC 360-22",
    }
