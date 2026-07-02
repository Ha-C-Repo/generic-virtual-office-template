"""
Your Company Virtual Office - Project Cost Tracker

Per-project tracking: estimated vs actual tons, costs, hours.
Calculates variance automatically.
"""
import sqlite3, threading, json
from datetime import datetime, date, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "projects.db"
    return Path(__file__).resolve().parent.parent / "data" / "projects.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, client TEXT DEFAULT '', location TEXT DEFAULT '',
            status TEXT DEFAULT 'ACTIVE',
            est_tons REAL DEFAULT 0, act_tons REAL DEFAULT 0,
            est_cost REAL DEFAULT 0, act_cost REAL DEFAULT 0,
            est_hours REAL DEFAULT 0, act_hours REAL DEFAULT 0,
            fab_rate REAL DEFAULT 3750, erect_rate REAL DEFAULT 970,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            category TEXT NOT NULL, description TEXT DEFAULT '',
            amount REAL NOT NULL, hours REAL DEFAULT 0,
            entry_date TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
    """)
    c.commit(); c.close()
_init()

def add_project(name, client="", location="", est_tons=0, est_cost=0, est_hours=0,
                fab_rate=3750, erect_rate=970, notes=""):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO projects (name,client,location,est_tons,est_cost,est_hours,fab_rate,erect_rate,notes,created_at,updated_at,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, client, location, est_tons, est_cost, est_hours, fab_rate, erect_rate, notes, now, now, "ACTIVE"))
        pid = cur.lastrowid; c.commit(); c.close()
    return pid

def update_project(project_id, **kwargs):
    allowed = {"name","client","location","status","est_tons","act_tons","est_cost","act_cost",
               "est_hours","act_hours","fab_rate","erect_rate","notes"}
    fields = {k:v for k,v in kwargs.items() if k in allowed}
    if not fields: return False
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        c = _conn()
        c.execute(f"UPDATE projects SET {sets} WHERE id=?", [*fields.values(), project_id])
        c.commit(); c.close()
    return True

def add_cost_entry(project_id, category, amount, description="", hours=0, entry_date=None):
    ed = entry_date or date.today().isoformat()
    with _lock:
        c = _conn()
        c.execute("INSERT INTO cost_entries (project_id,category,description,amount,hours,entry_date) VALUES (?,?,?,?,?,?)",
                  (project_id, category, description, amount, hours, ed))
        # Update actuals
        totals = c.execute("SELECT SUM(amount) as total_cost, SUM(hours) as total_hours FROM cost_entries WHERE project_id=?",
                          (project_id,)).fetchone()
        c.execute("UPDATE projects SET act_cost=?, act_hours=?, updated_at=? WHERE id=?",
                  (totals["total_cost"] or 0, totals["total_hours"] or 0, datetime.now(timezone.utc).isoformat(), project_id))
        c.commit(); c.close()

def get_project(project_id):
    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row: c.close(); return None
        p = dict(row)
        entries = c.execute("SELECT * FROM cost_entries WHERE project_id=? ORDER BY entry_date DESC",
                           (project_id,)).fetchall()
        c.close()
    p["entries"] = [dict(e) for e in entries]
    p["variance"] = _calc_variance(p)
    return p

def get_all_projects(status=None, limit=50):
    with _lock:
        c = _conn()
        if status:
            rows = c.execute("SELECT * FROM projects WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                            (status, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        c.close()
    return [{**dict(r), "variance": _calc_variance(dict(r))} for r in rows]

def _calc_variance(p):
    """Calculate cost and tonnage variance."""
    v = {}
    if p.get("est_cost") and p["est_cost"] > 0:
        v["cost_variance"] = round(p.get("act_cost", 0) - p["est_cost"], 2)
        v["cost_variance_pct"] = round((v["cost_variance"] / p["est_cost"]) * 100, 1)
    if p.get("est_tons") and p["est_tons"] > 0:
        v["ton_variance"] = round(p.get("act_tons", 0) - p["est_tons"], 2)
        v["ton_variance_pct"] = round((v["ton_variance"] / p["est_tons"]) * 100, 1)
    if p.get("est_hours") and p["est_hours"] > 0:
        v["hour_variance"] = round(p.get("act_hours", 0) - p["est_hours"], 2)
        v["hour_variance_pct"] = round((v["hour_variance"] / p["est_hours"]) * 100, 1)
    return v

def summary():
    projects = get_all_projects()
    total_est = sum(p.get("est_cost", 0) for p in projects)
    total_act = sum(p.get("act_cost", 0) for p in projects)
    return {
        "project_count": len(projects),
        "total_estimated": round(total_est, 2),
        "total_actual": round(total_act, 2),
        "total_variance": round(total_act - total_est, 2),
    }

def seed_defaults():
    """Seed with known Your Company projects if empty."""
    if get_all_projects(): return
    add_project("ICD Church - Spring TX", "ICD", "Spring TX", est_tons=1500, est_cost=5625000,
                notes="Quantum meruit risk $2.4M. 7 revision cycles.")
    add_project("America First Refining", "AFR", "Brownsville TX", est_tons=0,
                notes="$3.5B refinery. SOQ submitted 4/24/2026.")
seed_defaults()
