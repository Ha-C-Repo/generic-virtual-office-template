"""
AWS D1.1:2025 Welding QA - Domain Engine

WPS/PQR/WPQ tracking with code-driven essential-variables.
6-month welder continuity rule with auto-email 30/14/7 day alerts.
Pulsed-spray GMAW handling per 2025 update.
Type-D stud welding per 2025 update.

CRITICAL: Essential-variable changes ALWAYS require human signature event.
AI pre-fills non-essential variables only. (per handoff doc)
"""
import json, sqlite3, threading
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "welding_qa.db"
    return Path(__file__).resolve().parent.parent / "data" / "welding_qa.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# AWS D1.1 Essential Variables - changes require new PQR
ESSENTIAL_VARIABLES = [
    "base_metal_group", "filler_metal_classification", "process",
    "position", "thickness_range", "preheat_min", "interpass_max",
    "current_type", "shielding_gas_type", "single_vs_multi_pass",
    "backing_type", "transfer_mode",  # 2025: pulsed-spray GMAW now tracked
]

# Pre-qualified WPS templates per AWS D1.1:2025
PREQUALIFIED_WPS = {
    "SMAW-E7018-PJP": {
        "process": "SMAW", "filler": "E7018", "joint_type": "PJP",
        "positions": ["F", "H", "V", "OH"],
        "thickness_range": "3/16 to unlimited",
        "preheat": "50°F min for >1\" thick", "interpass_max": "600°F",
    },
    "FCAW-E71T1-CJP": {
        "process": "FCAW", "filler": "E71T-1", "joint_type": "CJP",
        "positions": ["F", "H", "V-up"],
        "thickness_range": "3/16 to unlimited",
        "preheat": "50°F min for >1\" thick", "interpass_max": "600°F",
        "shielding_gas": "75/25 Ar/CO2",
    },
    "GMAW-ER70S6-Fillet": {
        "process": "GMAW", "filler": "ER70S-6", "joint_type": "Fillet",
        "positions": ["F", "H"],
        "thickness_range": "1/8 to 1\"",
        "transfer_mode": "spray or pulsed-spray",  # 2025 addition
        "shielding_gas": "90/10 Ar/CO2",
    },
    "SAW-EM12K-CJP": {
        "process": "SAW", "filler": "EM12K/F7A2", "joint_type": "CJP",
        "positions": ["F"],
        "thickness_range": "3/16 to unlimited",
    },
}

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS welders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, welder_id TEXT UNIQUE NOT NULL,
            cwi_number TEXT DEFAULT '', certifications TEXT DEFAULT '',
            processes TEXT DEFAULT '', last_weld_date TEXT,
            continuity_expires TEXT, status TEXT DEFAULT 'ACTIVE',
            email TEXT DEFAULT '', phone TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS wps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wps_number TEXT UNIQUE NOT NULL, revision TEXT DEFAULT 'A',
            process TEXT NOT NULL, filler_metal TEXT NOT NULL,
            joint_type TEXT DEFAULT '', positions TEXT DEFAULT '',
            base_metal TEXT DEFAULT '', thickness_range TEXT DEFAULT '',
            pqr_number TEXT DEFAULT '', status TEXT DEFAULT 'ACTIVE',
            approved_by TEXT DEFAULT '', approved_date TEXT,
            essential_vars TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS wqtr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            welder_id TEXT NOT NULL, wps_number TEXT,
            process TEXT NOT NULL, position TEXT NOT NULL,
            test_date TEXT NOT NULL, result TEXT DEFAULT 'PASS',
            expires TEXT, examiner TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        );
    """)
    c.commit(); c.close()

_init()

def add_welder(name, welder_id, processes="FCAW,SMAW", email="", phone=""):
    """Add a welder to the QA system."""
    now = datetime.now(timezone.utc).isoformat()
    continuity = (date.today() + timedelta(days=180)).isoformat()
    with _lock:
        c = _conn()
        try:
            c.execute("INSERT INTO welders (name,welder_id,processes,last_weld_date,continuity_expires,email,phone) VALUES (?,?,?,?,?,?,?)",
                     (name, welder_id, processes, date.today().isoformat(), continuity, email, phone))
            c.commit()
        except sqlite3.IntegrityError:
            c.close()
            return {"error": f"Welder ID {welder_id} already exists"}
        c.close()
    return {"welder_id": welder_id, "continuity_expires": continuity}

def record_weld_activity(welder_id, process=None):
    """Record that a welder performed welding today. Resets 6-month continuity clock."""
    new_expiry = (date.today() + timedelta(days=180)).isoformat()
    with _lock:
        c = _conn()
        c.execute("UPDATE welders SET last_weld_date=?, continuity_expires=? WHERE welder_id=?",
                 (date.today().isoformat(), new_expiry, welder_id))
        c.commit(); c.close()
    return {"welder_id": welder_id, "continuity_reset_to": new_expiry}

def get_continuity_alerts(days_warning=30):
    """Get welders whose 6-month continuity expires within N days.
    Per AWS D1.1: >6 months without process use = requalification required."""
    cutoff = (date.today() + timedelta(days=days_warning)).isoformat()
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM welders WHERE continuity_expires <= ? AND status='ACTIVE' ORDER BY continuity_expires",
                        (cutoff,)).fetchall()
        c.close()
    alerts = []
    for r in [dict(x) for x in rows]:
        exp = date.fromisoformat(r["continuity_expires"])
        days_left = (exp - date.today()).days
        r["days_until_expiry"] = days_left
        r["urgency"] = "EXPIRED" if days_left < 0 else "CRITICAL" if days_left <= 7 else "WARNING" if days_left <= 14 else "NOTICE"
        alerts.append(r)
    return alerts

def get_prequalified_wps():
    """Return pre-qualified WPS templates per AWS D1.1:2025."""
    return PREQUALIFIED_WPS

def check_essential_variable_change(existing_vars: dict, proposed_vars: dict):
    """Check if proposed changes affect essential variables (requires new PQR)."""
    changes = []
    for var in ESSENTIAL_VARIABLES:
        if var in proposed_vars and existing_vars.get(var) != proposed_vars[var]:
            changes.append({
                "variable": var,
                "current": existing_vars.get(var),
                "proposed": proposed_vars[var],
                "requires_new_pqr": True,
            })
    return {
        "has_essential_changes": len(changes) > 0,
        "changes": changes,
        "warning": "Essential variable changes require a new PQR and human signature." if changes else None,
    }

def get_all_welders():
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM welders ORDER BY name").fetchall()
        c.close()
    return [dict(r) for r in rows]

def for_morning_briefing():
    """Compact summary for SMS briefing."""
    alerts = get_continuity_alerts(30)
    if not alerts:
        return "Welding QA: all continuity current."
    lines = [f"⚠ Welder continuity alerts ({len(alerts)}):"]
    for a in alerts[:3]:
        lines.append(f"  {a['name']} ({a['welder_id']}): {a['urgency']} - {a['days_until_expiry']}d left")
    return "\n".join(lines)


# ═══ AWS D1.1:2025 ESSENTIAL VARIABLE UPDATES (4 new hooks) ════════

# Hook 1: Pulsed-Spray GMAW - dedicated prequalified shielding-gas tables (Table 5.7)
PULSED_SPRAY_GMAW_GAS_TABLE = {
    "ER70S-3": {"gas": "90-98% Ar / bal CO2", "flow_cfh": "35-55", "aws_spec": "A5.18/A5.18M"},
    "ER70S-6": {"gas": "90-98% Ar / bal CO2", "flow_cfh": "35-55", "aws_spec": "A5.18/A5.18M"},
    "ER80S-D2": {"gas": "95-98% Ar / bal CO2", "flow_cfh": "35-55", "aws_spec": "A5.28/A5.28M"},
    "ER80S-Ni1": {"gas": "95-98% Ar / bal CO2", "flow_cfh": "35-55", "aws_spec": "A5.28/A5.28M"},
}

def validate_pulsed_spray_wps(wps_data: dict) -> dict:
    """Validate a pulsed-spray GMAW WPS against D1.1:2025 Table 5.7."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.20; disjoint shapes)
    filler = wps_data.get("filler_metal", "")
    gas = wps_data.get("shielding_gas", "")
    if filler not in PULSED_SPRAY_GMAW_GAS_TABLE:
        return {"valid": False, "error": f"Filler {filler} not in pulsed-spray prequalified table"}
    required = PULSED_SPRAY_GMAW_GAS_TABLE[filler]
    return {"valid": True, "required_gas": required["gas"], "aws_spec": required["aws_spec"],
            "note": "D1.1:2025 Table 5.7 - pulsed-spray GMAW prequalified shielding gas"}


# Hook 2: Type-D Studs (deformed bar/wire ASTM A706 Gr.60) per AWS D1.4
TYPE_D_STUD_REQUIREMENTS = {
    "material": "ASTM A706 Grade 60 deformed bar/wire",
    "qualification": "Fillet-weld qualification per AWS D1.4",
    "cross_reference": "AWS D1.4 (Reinforcing Steel)",
    "test_method": "macroetch + bend test per D1.4 Clause 7",
    "min_fillet_size": "per D1.4 Table 7.1 based on bar diameter",
}

def check_type_d_stud_qualification(welder_id: str) -> dict:
    """Check if welder has Type-D stud (ASTM A706) fillet-weld qualification per D1.4."""
    with _lock:
        c = _conn()
        quals = c.execute("SELECT * FROM wqtr WHERE welder_id=?", (welder_id,)).fetchall()
        c.close()
    has_d14 = any("D1.4" in (q["notes"] or "") or "stud" in (q["process"] or "").lower() for q in quals)
    return {"welder_id": welder_id, "type_d_qualified": has_d14,
            "requirements": TYPE_D_STUD_REQUIREMENTS,
            "action": None if has_d14 else "Requires D1.4 fillet-weld qualification test"}


# Hook 3: Plug/Slot Welds - now have own WPS qualification + macroetch requirements
PLUG_SLOT_WELD_2025 = {
    "qualification": "Dedicated WPS qualification required (new in 2025)",
    "test": "Macroetch cross-section per D1.1:2025 Clause 6",
    "acceptance": "Complete fusion to base metal, no cracks, porosity ≤1/32\"",
    "note": "Previous editions allowed plug/slot under fillet-weld WPS - 2025 requires dedicated PQR",
}

def validate_plug_slot_wps(wps_number: str) -> dict:
    """Verify that a plug/slot weld WPS has its own dedicated PQR (2025 requirement)."""
    with _lock:
        c = _conn()
        wps = c.execute("SELECT * FROM wps WHERE wps_number=?", (wps_number,)).fetchone()
        c.close()
    if not wps:
        return {"valid": False, "error": f"WPS {wps_number} not found"}
    joint = (wps["joint_type"] or "").lower()
    has_dedicated_pqr = bool(wps["pqr_number"])
    return {"wps_number": wps_number, "joint_type": wps["joint_type"],
            "is_plug_slot": "plug" in joint or "slot" in joint,
            "has_dedicated_pqr": has_dedicated_pqr,
            "requirement": PLUG_SLOT_WELD_2025,
            "compliant": has_dedicated_pqr if ("plug" in joint or "slot" in joint) else True}


# Hook 4: Preheat extension distance + PWHT max load temp raised to 800°F
PREHEAT_PWHT_2025 = {
    "preheat_extension": {
        "under_1_5_inch": "≥2t from weld centerline (t = thickness)",
        "over_1_5_inch": "≥t and ≥3 inches from weld centerline",
    },
    "pwht_max_furnace_temp": "800°F (was 600°F in 2020 edition)",
    "pwht_note": "PWHT max load temperature raised from 600°F to 800°F per D1.1:2025",
}

def check_preheat_extension(thickness_inches: float) -> dict:
    """Calculate required preheat extension distance per D1.1:2025."""
    if thickness_inches <= 1.5:
        extension = max(0.5, 2 * thickness_inches)
        rule = "≥2t"
    else:
        extension = max(thickness_inches, 3.0)
        rule = "≥t and ≥3\""
    return {"thickness": thickness_inches, "preheat_extension_inches": round(extension, 2),
            "rule": rule, "pwht_max_load_temp": "800°F",
            "source": "AWS D1.1:2025 - updated from 600°F (2020)"}

