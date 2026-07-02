"""
Your Company Virtual Office - Houston Market Intelligence Engine

Tracks: EPC pipeline, refinery turnarounds, AGC/ABC directories,
Port of Houston expansion. Scores opportunities against sweet spot.

"Monday morning top-25 board": ranked by (steel tons) × (sub probability) × (proximity)
"""

import json, sqlite3, threading
from datetime import datetime, date, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "houston_market.db"
    return Path(__file__).resolve().parent.parent / "data" / "houston_market.db"

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
        CREATE TABLE IF NOT EXISTS pipeline_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, owner TEXT DEFAULT '', epc TEXT DEFAULT '',
            location TEXT DEFAULT '', county TEXT DEFAULT 'Harris',
            est_value TEXT DEFAULT '', est_steel_tons REAL DEFAULT 0,
            project_type TEXT DEFAULT '', status TEXT DEFAULT 'PLANNING',
            construction_start TEXT DEFAULT '', construction_end TEXT DEFAULT '',
            sub_probability REAL DEFAULT 0.5, distance_miles REAL DEFAULT 30,
            score REAL DEFAULT 0, source TEXT DEFAULT '',
            notes TEXT DEFAULT '', updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS turnarounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility TEXT NOT NULL, owner TEXT NOT NULL,
            location TEXT DEFAULT '', unit TEXT DEFAULT '',
            start_window TEXT DEFAULT '', end_window TEXT DEFAULT '',
            steel_scope TEXT DEFAULT '', notes TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gc_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL, contact_name TEXT DEFAULT '',
            email TEXT DEFAULT '', phone TEXT DEFAULT '',
            csi_codes TEXT DEFAULT '', membership TEXT DEFAULT '',
            last_bid_together TEXT DEFAULT '', relationship TEXT DEFAULT 'cold',
            updated_at TEXT NOT NULL
        );
    """)
    c.commit(); c.close()
_init()


# ═══ SEED: HOUSTON EPC PIPELINE Q3 2025-2027 ═════════════════════

SEED_PROJECTS = [
    {"name": "Eli Lilly Generation Park", "owner": "Eli Lilly", "epc": "TBD",
     "location": "Generation Park, Houston", "est_value": "$6.5B", "est_steel_tons": 8000,
     "project_type": "biomanufacturing", "status": "ENGINEERING", "construction_start": "2026-Q3"},
    {"name": "Air Products Ammonia Complex", "owner": "Air Products", "epc": "TBD",
     "location": "Texas City", "est_value": "$4B+", "est_steel_tons": 5000,
     "project_type": "petrochemical", "status": "FEED", "construction_start": "2026-Q4"},
    {"name": "TMEIC Power Systems Factory", "owner": "TMEIC", "epc": "TBD",
     "location": "Waller County", "est_value": "$200M+", "est_steel_tons": 1500,
     "project_type": "manufacturing", "status": "PERMITTED", "construction_start": "2026-Q2"},
    {"name": "Tesla Megapack BESS Brookshire", "owner": "Tesla", "epc": "TBD",
     "location": "Brookshire TX", "est_value": "$200M+", "est_steel_tons": 800,
     "project_type": "energy_storage", "status": "CONSTRUCTION", "construction_start": "2026-Q1"},
    {"name": "Targa Speedway NGL Pipeline", "owner": "Targa Resources", "epc": "TBD",
     "location": "Permian → Mont Belvieu", "est_value": "$1.6B", "est_steel_tons": 3000,
     "project_type": "pipeline/midstream", "status": "CONSTRUCTION", "construction_start": "2025-Q4"},
    {"name": "Enterprise Train 14 Mont Belvieu", "owner": "Enterprise Products", "epc": "TBD",
     "location": "Mont Belvieu", "est_value": "$800M+", "est_steel_tons": 2000,
     "project_type": "NGL_fractionation", "status": "ENGINEERING", "construction_start": "2026-Q3"},
    {"name": "OxyChem Battleground Chlor-Alkali", "owner": "OxyChem", "epc": "TBD",
     "location": "La Porte TX", "est_value": "$1.1B", "est_steel_tons": 2500,
     "project_type": "chemical", "status": "ENGINEERING", "construction_start": "2026-Q4"},
    {"name": "Dow Freeport Polyethylene Unit 7", "owner": "Dow Chemical", "epc": "TBD",
     "location": "Freeport TX", "est_value": "$715M", "est_steel_tons": 1800,
     "project_type": "petrochemical", "status": "FEED", "construction_start": "2027-Q1"},
    {"name": "Project 11 Houston Ship Channel", "owner": "USACE", "epc": "Great Lakes Dredge",
     "location": "Barbours Cut / Bayport", "est_value": "$1B+", "est_steel_tons": 1200,
     "project_type": "port/marine", "status": "CONSTRUCTION", "construction_start": "2025-Q3"},
    {"name": "RWE Crowned Heron 2 BESS", "owner": "RWE", "epc": "TBD",
     "location": "Richmond TX", "est_value": "$300M+", "est_steel_tons": 600,
     "project_type": "energy_storage", "status": "PERMITTED", "construction_start": "2026-Q2"},
    {"name": "SPR Bryan Mound Life Extension", "owner": "DOE", "epc": "TBD",
     "location": "Brazoria County", "est_value": "$500M+", "est_steel_tons": 1000,
     "project_type": "federal/energy", "status": "ENGINEERING", "construction_start": "2026-Q3"},
    {"name": "Aypa Bypass BESS Richmond", "owner": "Aypa Power", "epc": "TBD",
     "location": "Richmond TX", "est_value": "$150M+", "est_steel_tons": 400,
     "project_type": "energy_storage", "status": "CONSTRUCTION", "construction_start": "2026-Q1"},
]

SEED_TURNAROUNDS = [
    {"facility": "Marathon Galveston Bay", "owner": "Marathon Petroleum", "location": "Texas City",
     "unit": "FCC/Coker", "start_window": "2026-Q4", "end_window": "2027-Q1",
     "steel_scope": "Pipe rack mods, platform extensions, structural repairs"},
    {"facility": "ExxonMobil Baytown", "owner": "ExxonMobil", "location": "Baytown",
     "unit": "Multiple", "start_window": "2026-Q3", "end_window": "2026-Q4",
     "steel_scope": "Structural modifications, equipment supports"},
    {"facility": "LyondellBasell Channelview", "owner": "LyondellBasell", "location": "Channelview",
     "unit": "Olefins", "start_window": "2027-Q1", "end_window": "2027-Q2",
     "steel_scope": "Pipe supports, access platforms"},
    {"facility": "Shell Deer Park", "owner": "Shell/Pemex", "location": "Deer Park",
     "unit": "Multiple", "start_window": "2026-Q3", "end_window": "2026-Q4",
     "steel_scope": "Steel repairs, handrail replacement, misc metals"},
    {"facility": "Valero Texas City", "owner": "Valero", "location": "Texas City",
     "unit": "Reformer", "start_window": "2027-Q2", "end_window": "2027-Q2",
     "steel_scope": "Structural steel modifications"},
]


def seed_pipeline():
    """Seed the Houston EPC pipeline database."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        existing = c.execute("SELECT COUNT(*) FROM pipeline_projects").fetchone()[0]
        if existing == 0:
            for p in SEED_PROJECTS:
                score = _score_opportunity(p)
                c.execute(
                    "INSERT INTO pipeline_projects (name,owner,epc,location,est_value,est_steel_tons,project_type,status,construction_start,score,source,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (p["name"], p["owner"], p["epc"], p["location"], p["est_value"],
                     p["est_steel_tons"], p["project_type"], p["status"],
                     p["construction_start"], score, "IIR/press_releases", now))
            for t in SEED_TURNAROUNDS:
                c.execute(
                    "INSERT INTO turnarounds (facility,owner,location,unit,start_window,end_window,steel_scope,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (t["facility"], t["owner"], t["location"], t["unit"],
                     t["start_window"], t["end_window"], t["steel_scope"], now))
        c.commit(); c.close()
    return {"seeded_projects": len(SEED_PROJECTS), "seeded_turnarounds": len(SEED_TURNAROUNDS)}


def _score_opportunity(p: dict) -> float:
    """Score: (est_steel_tons) × (sub_probability) × (proximity_factor)"""
    tons = p.get("est_steel_tons", 0)
    prob = p.get("sub_probability", 0.3)
    # Houston shop = 30 mi avg; closer = better
    dist = p.get("distance_miles", 50)
    prox = max(0.2, 1.0 - (dist / 200))
    return round(tons * prob * prox, 1)


def get_pipeline(top_n: int = 25) -> list:
    """Monday morning pipeline board - top N scored opportunities."""
    seed_pipeline()
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM pipeline_projects ORDER BY score DESC LIMIT ?",
                         (top_n,)).fetchall()
        c.close()
    return [dict(r) for r in rows]


def get_turnarounds() -> list:
    """Upcoming refinery turnaround windows."""
    seed_pipeline()
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM turnarounds ORDER BY start_window").fetchall()
        c.close()
    return [dict(r) for r in rows]


def add_gc_contact(company: str, contact_name: str = "", email: str = "",
                    phone: str = "", csi_codes: str = "", membership: str = "") -> dict:
    """Add a GC/EPC contact from AGC/ABC directory."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO gc_contacts (company,contact_name,email,phone,csi_codes,membership,updated_at) VALUES (?,?,?,?,?,?,?)",
            (company, contact_name, email, phone, csi_codes, membership, now))
        c.commit(); c.close()
    return {"company": company, "added": True}


def get_gc_contacts(membership: str = "") -> list:
    with _lock:
        c = _conn()
        if membership:
            rows = c.execute("SELECT * FROM gc_contacts WHERE membership LIKE ? ORDER BY company",
                            (f"%{membership}%",)).fetchall()
        else:
            rows = c.execute("SELECT * FROM gc_contacts ORDER BY company").fetchall()
        c.close()
    return [dict(r) for r in rows]


def for_briefing() -> str:
    """Pipeline summary for morning briefing."""
    projects = get_pipeline(5)
    if projects:
        lines = ["Houston Pipeline Top 5:"]
        for p in projects:
            lines.append(f"  • {p['name']} ({p['owner']}) - {p['est_steel_tons']} tons, {p['status']}")
        return "\n".join(lines)
    return "Houston pipeline: No projects tracked"


def stats() -> dict:
    with _lock:
        c = _conn()
        projects = c.execute("SELECT COUNT(*) FROM pipeline_projects").fetchone()[0]
        turnarounds = c.execute("SELECT COUNT(*) FROM turnarounds").fetchone()[0]
        contacts = c.execute("SELECT COUNT(*) FROM gc_contacts").fetchone()[0]
        c.close()
    return {"pipeline_projects": projects, "turnarounds": turnarounds, "gc_contacts": contacts}
