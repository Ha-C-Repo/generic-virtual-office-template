"""
Your Company Virtual Office - DISA Status Client

DISA Contractors Consortium (DCC) - the single source of truth for
drug-and-alcohol and background data on Gulf Coast refinery work.

Status values: SATISFACTORY / CONDITIONAL / UNSATISFACTORY / INCOMPLETE / IN REVIEW

Daily cross-check before crew dispatch prevents non-current
employees showing up at a refinery gate.
"""

import os, json, sqlite3, threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "disa_employees.db"
    return Path(__file__).resolve().parent.parent / "data" / "disa_employees.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

STATUSES = ["SATISFACTORY", "CONDITIONAL", "UNSATISFACTORY", "INCOMPLETE", "IN_REVIEW"]

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, employee_id TEXT UNIQUE,
            disa_status TEXT DEFAULT 'INCOMPLETE',
            disa_expiry TEXT, drug_test_date TEXT, background_date TEXT,
            badge_number TEXT DEFAULT '', site_assignments TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            last_checked TEXT, updated_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_emp_status ON employees(disa_status)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()
_init()

def add_employee(name, employee_id="", disa_status="INCOMPLETE", disa_expiry="",
                 badge_number="", notes=""):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO employees (name,employee_id,disa_status,disa_expiry,badge_number,notes,updated_at) VALUES (?,?,?,?,?,?,?)",
            (name, employee_id, disa_status, disa_expiry, badge_number, notes, now))
        c.commit(); c.close()

def update_status(employee_id, disa_status, disa_expiry="", drug_test_date="", background_date=""):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        c.execute(
            "UPDATE employees SET disa_status=?, disa_expiry=?, drug_test_date=?, background_date=?, last_checked=?, updated_at=? WHERE employee_id=?",
            (disa_status, disa_expiry, drug_test_date, background_date, now, now, employee_id))
        c.commit(); c.close()

def get_all():
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM employees ORDER BY name").fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_cleared_for_site():
    """Employees cleared for refinery dispatch (SATISFACTORY only)."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM employees WHERE disa_status='SATISFACTORY'").fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_non_current():
    """Employees NOT cleared - block from refinery gate dispatch."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM employees WHERE disa_status != 'SATISFACTORY'").fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_expiring(days=30):
    """Employees whose DISA compliance expires within N days."""
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM employees WHERE disa_expiry != '' AND disa_expiry <= ? AND disa_status='SATISFACTORY'",
            (cutoff,)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def pre_dispatch_check(employee_ids: list) -> dict:
    """Pre-dispatch verification for a crew. Returns pass/fail per employee."""
    results = {"cleared": [], "blocked": [], "unknown": []}
    with _lock:
        c = _conn()
        for eid in employee_ids:
            row = c.execute("SELECT * FROM employees WHERE employee_id=?", (eid,)).fetchone()
            if not row:
                results["unknown"].append(eid)
            elif row["disa_status"] == "SATISFACTORY":
                results["cleared"].append({"name": row["name"], "id": eid})
            else:
                results["blocked"].append({
                    "name": row["name"], "id": eid,
                    "status": row["disa_status"], "reason": "Non-SATISFACTORY DISA status"
                })
        c.close()
    results["dispatch_ok"] = len(results["blocked"]) == 0 and len(results["unknown"]) == 0
    return results

def for_briefing():
    """DISA summary for morning briefing."""
    all_emp = get_all()
    if not all_emp:
        return "DISA: No employees tracked"
    sat = sum(1 for e in all_emp if e["disa_status"] == "SATISFACTORY")
    exp = get_expiring(30)
    non = get_non_current()
    lines = [f"DISA: {sat}/{len(all_emp)} SATISFACTORY"]
    if non:
        lines.append(f"  ⛔ {len(non)} non-current: {', '.join(e['name'] for e in non[:3])}")
    if exp:
        lines.append(f"  ⚠️ {len(exp)} expiring within 30d")
    return "\n".join(lines)
