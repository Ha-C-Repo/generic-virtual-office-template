"""
Your Company Virtual Office - Contact Database

GC contacts, subcontractors, vendors, inspectors.
AI references this when drafting emails for personalization.

Schema: name, company, role, email, phone, last_contact, notes, tags
"""
import json, sqlite3, threading
from datetime import datetime, date, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "contacts.db"
    return Path(__file__).resolve().parent.parent / "data" / "contacts.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row
    return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, company TEXT DEFAULT '', role TEXT DEFAULT '',
            email TEXT DEFAULT '', phone TEXT DEFAULT '',
            last_contact TEXT, notes TEXT DEFAULT '', tags TEXT DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()

_init()

def add(name, company="", role="", email="", phone="", notes="", tags=""):
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        cur = c.execute(
            "INSERT INTO contacts (name,company,role,email,phone,notes,tags,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (name, company, role, email, phone, notes, tags, now, now))
        cid = cur.lastrowid; c.commit(); c.close()
    return cid

def update(contact_id, **kwargs):
    allowed = {"name","company","role","email","phone","notes","tags","last_contact"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields: return False
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k}=?" for k in fields)
    with _lock:
        c = _conn()
        c.execute(f"UPDATE contacts SET {sets} WHERE id=?", [*fields.values(), contact_id])
        c.commit(); c.close()
    return True

def delete(contact_id):
    with _lock:
        c = _conn()
        c.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
        c.commit(); c.close()

def search(query="", company="", tag="", limit=50):
    with _lock:
        c = _conn()
        sql = "SELECT * FROM contacts WHERE 1=1"
        params = []
        if query:
            sql += " AND (name LIKE ? OR email LIKE ? OR company LIKE ?)"
            params += [f"%{query}%"]*3
        if company:
            sql += " AND company LIKE ?"
            params.append(f"%{company}%")
        if tag:
            sql += " AND tags LIKE ?"
            params.append(f"%{tag}%")
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(sql, params).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get(contact_id):
    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        c.close()
    return dict(row) if row else None

def get_all(limit=200):
    return search(limit=limit)

def record_contact(contact_id):
    """Mark that we contacted this person today."""
    update(contact_id, last_contact=date.today().isoformat())

def get_for_ai(company="", limit=5):
    """Get contacts formatted for AI email personalization."""
    contacts = search(company=company, limit=limit) if company else search(limit=limit)
    if not contacts: return ""
    lines = ["Known contacts:"]
    for c in contacts:
        line = f"- {c['name']}"
        if c.get('company'): line += f" ({c['company']})"
        if c.get('role'): line += f" - {c['role']}"
        if c.get('last_contact'): line += f" [last contact: {c['last_contact']}]"
        lines.append(line)
    return "\n".join(lines)

def stats():
    with _lock:
        c = _conn()
        total = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        companies = c.execute("SELECT COUNT(DISTINCT company) FROM contacts WHERE company != ''").fetchone()[0]
        c.close()
    return {"total_contacts": total, "unique_companies": companies}

def seed_defaults():
    """Seed with known Your Company contacts if empty."""
    if stats()["total_contacts"] > 0: return
    defaults = [
        ("Ivan", "Your Company", "Foreman", "", "", "Validates field hours for ICD Church", "internal"),
        ("Amber", "Your Company", "Admin/Insurance", "", "", "Handles carrier upgrades, insurance docs", "internal"),
        ("Texas Mutual", "Texas Mutual Insurance", "Workers Comp Carrier", "", "800-859-5995", "Policy [POLICY NUMBER]. EMR letter source.", "insurance,carrier"),
    ]
    for d in defaults:
        add(*d)

seed_defaults()
