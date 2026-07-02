"""
Houston Permits - Data Fabric Layer

Houston Permitting Center integration:
- Special Inspector registry refresh (firms certified for Structural Steel, Welds)
- Inspection scheduling reminders
- IBC Chapter 17 §1705 compliance (field welding/HSB requires Special Inspector)

Per handoff: City publishes registered Special Inspectors PDF at
houstonpermittingcenter.org/media/2151/download
"""
import json, sqlite3, threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "houston_permits.db"
    return Path(__file__).resolve().parent.parent / "data" / "houston_permits.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# Known Special Inspection firms in Houston area (seeded from industry knowledge)
DEFAULT_INSPECTORS = [
    {"firm": "Professional Service Industries (PSI/Intertek)", "scope": "Structural Steel, Welds, HSB",
     "phone": "713-681-5227", "cert_expires": "2026-12-31", "status": "ACTIVE"},
    {"firm": "Terracon Consultants", "scope": "Structural Steel, Welds, Concrete",
     "phone": "713-690-8989", "cert_expires": "2026-12-31", "status": "ACTIVE"},
    {"firm": "Kleinfelder", "scope": "Structural Steel, Welds, HSB, Concrete",
     "phone": "713-526-6000", "cert_expires": "2026-12-31", "status": "ACTIVE"},
    {"firm": "Atlas Technical Consultants", "scope": "Structural Steel, Welds",
     "phone": "713-956-2tried", "cert_expires": "2026-06-30", "status": "ACTIVE"},
    {"firm": "Tolunay-Wong Engineers (TWE)", "scope": "Structural Steel, Welds, Geotechnical",
     "phone": "713-658-8888", "cert_expires": "2026-12-31", "status": "ACTIVE"},
]

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS special_inspectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firm TEXT NOT NULL, scope TEXT DEFAULT '',
            phone TEXT DEFAULT '', cert_expires TEXT,
            status TEXT DEFAULT 'ACTIVE', notes TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL, inspection_type TEXT NOT NULL,
            inspector_id INTEGER, scheduled_date TEXT,
            status TEXT DEFAULT 'PENDING',
            notes TEXT DEFAULT '', created_at TEXT NOT NULL
        );
    """)
    # Seed defaults if empty
    count = c.execute("SELECT COUNT(*) FROM special_inspectors").fetchone()[0]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        for si in DEFAULT_INSPECTORS:
            c.execute("INSERT INTO special_inspectors (firm,scope,phone,cert_expires,status,updated_at) VALUES (?,?,?,?,?,?)",
                     (si["firm"], si["scope"], si["phone"], si["cert_expires"], si["status"], now))
    c.commit(); c.close()

_init()

def get_inspectors(scope_filter="steel"):
    """Get Special Inspectors filtered by scope."""
    with _lock:
        c = _conn()
        if scope_filter:
            rows = c.execute("SELECT * FROM special_inspectors WHERE scope LIKE ? AND status='ACTIVE'",
                           (f"%{scope_filter}%",)).fetchall()
        else:
            rows = c.execute("SELECT * FROM special_inspectors WHERE status='ACTIVE'").fetchall()
        c.close()
    inspectors = [dict(r) for r in rows]
    # Flag expiring certs
    today = date.today()
    for si in inspectors:
        if si.get("cert_expires"):
            exp = date.fromisoformat(si["cert_expires"])
            si["days_until_expiry"] = (exp - today).days
            si["expiring_soon"] = si["days_until_expiry"] <= 60
    return inspectors

def schedule_inspection(project, inspection_type, scheduled_date, inspector_id=None, notes=""):
    """Schedule a special inspection."""
    with _lock:
        c = _conn()
        c.execute("INSERT INTO inspections (project,inspection_type,inspector_id,scheduled_date,notes,status,created_at) VALUES (?,?,?,?,?,?,?)",
                 (project, inspection_type, inspector_id, scheduled_date, notes, "PENDING", datetime.now(timezone.utc).isoformat()))
        c.commit(); c.close()

def get_upcoming_inspections(days=14):
    """Get inspections scheduled within N days."""
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    today = date.today().isoformat()
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT i.*, s.firm as inspector_firm FROM inspections i LEFT JOIN special_inspectors s ON i.inspector_id=s.id WHERE i.scheduled_date BETWEEN ? AND ? AND i.status='PENDING' ORDER BY i.scheduled_date",
            (today, cutoff)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def requires_special_inspection(work_type):
    """IBC Chapter 17 §1705: Does this work require a Special Inspector?"""
    si_required = [
        "field welding", "shop welding", "high-strength bolting", "hsb",
        "structural steel erection", "steel framing", "moment connections",
    ]
    return any(w in work_type.lower() for w in si_required)
