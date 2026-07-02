"""
AISC 207-25 Audit Readiness - Domain Engine

Building Fabricator (BU) certification compliance tracking.
Effective June 15, 2025, January 2026 supplemental.

Tracks: Active-fabrication evidence, bolting demonstrations,
QCI qualifications, PQR→WPS chains, Approved Fabricator marking.

CRITICAL: AISC auditors can spot-sample the daily shop log.
All numeric values are Python-computed with provenance, never LLM-generated.
"""
import json, sqlite3, threading
from datetime import datetime, date, timedelta
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "aisc_audit.db"
    return Path(__file__).resolve().parent.parent / "data" / "aisc_audit.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# AISC 207-25 audit checklist items
AUDIT_CHECKLIST = {
    "active_fabrication": {
        "title": "Active Fabrication Evidence (AISC 303 §2.1)",
        "description": "Daily shop log of mark numbers, processes, welder IDs in auditor-sampleable format",
        "frequency": "daily", "critical": True,
    },
    "bolting_demonstration": {
        "title": "Pre-Installation Verification (RCSC §7)",
        "description": "DTI/Squirter/TC bolt lot tracking, calibrated torque wrench dates, personnel assignment",
        "frequency": "per_lot", "critical": True,
    },
    "qci_qualifications": {
        "title": "QCI Qualifications (AISC 360-22 §N4)",
        "description": "CWI/SCWI status, AWS QC1 certification, continuing education hours per inspector",
        "frequency": "annual", "critical": True,
    },
    "wps_pqr_chain": {
        "title": "WPS supported by PQR",
        "description": "Every active WPS has a qualifying PQR on file with essential variables tracked",
        "frequency": "per_wps", "critical": True,
    },
    "welder_qualification": {
        "title": "Welder Qualification Records (WQTR)",
        "description": "6-month continuity rule enforced, test records on file",
        "frequency": "per_welder", "critical": True,
    },
    "fabricator_marking": {
        "title": "Approved Fabricator Marking",
        "description": "Fabricator name/number permanently marked on each piece per IBC",
        "frequency": "per_piece", "critical": False,
    },
    "material_traceability": {
        "title": "Material Test Reports (MTRs)",
        "description": "Heat numbers traced from MTR to piece marks",
        "frequency": "per_heat", "critical": True,
    },
    "nde_records": {
        "title": "NDE Records",
        "description": "RT/UT/MT/PT reports filed per AWS D1.1 §8, performed by qualified NDE personnel",
        "frequency": "per_joint", "critical": True,
    },
    "corrective_actions": {
        "title": "NCR/Corrective Action Log",
        "description": "Non-conformance reports with root cause and corrective action",
        "frequency": "per_event", "critical": False,
    },
    "calibration_records": {
        "title": "Equipment Calibration",
        "description": "Torque wrenches, welding machines, measuring instruments - cal dates current",
        "frequency": "per_equipment", "critical": False,
    },
}

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS qci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, cwi_number TEXT, scwi TEXT DEFAULT 'N',
            aws_qc1 TEXT DEFAULT 'N', ce_hours REAL DEFAULT 0,
            cert_expires TEXT, status TEXT DEFAULT 'ACTIVE'
        );
        CREATE TABLE IF NOT EXISTS shop_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL, mark_number TEXT NOT NULL,
            process TEXT DEFAULT '', welder_id TEXT DEFAULT '',
            operation TEXT DEFAULT '', hours REAL DEFAULT 0,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS bolt_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_number TEXT NOT NULL, bolt_type TEXT DEFAULT '',
            dtc_squirter TEXT DEFAULT '', torque_wrench_cal TEXT,
            verified_by TEXT DEFAULT '', verified_date TEXT,
            project TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS audit_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_item TEXT NOT NULL, status TEXT DEFAULT 'INCOMPLETE',
            last_verified TEXT, verified_by TEXT DEFAULT '',
            notes TEXT DEFAULT '', gap TEXT DEFAULT ''
        );
    """)
    c.commit(); c.close()

_init()

def log_shop_activity(mark_number, process, welder_id, operation, hours=0, notes=""):
    """Log a daily shop activity (AISC 303 §2.1 active-fabrication evidence)."""
    with _lock:
        c = _conn()
        c.execute("INSERT INTO shop_log (log_date,mark_number,process,welder_id,operation,hours,notes) VALUES (?,?,?,?,?,?,?)",
                 (date.today().isoformat(), mark_number, process, welder_id, operation, hours, notes))
        c.commit(); c.close()

def get_shop_log(days=7):
    """Get recent shop log entries for auditor sampling."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM shop_log WHERE log_date >= ? ORDER BY log_date DESC, id DESC",
                        (cutoff,)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def add_qci(name, cwi_number, cert_expires, scwi="N", aws_qc1="N", ce_hours=0):
    """Add a Quality Control Inspector."""
    with _lock:
        c = _conn()
        c.execute("INSERT INTO qci (name,cwi_number,scwi,aws_qc1,ce_hours,cert_expires) VALUES (?,?,?,?,?,?)",
                 (name, cwi_number, scwi, aws_qc1, ce_hours, cert_expires))
        c.commit(); c.close()

def get_qci_status():
    """Get all QCIs with cert expiration status."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM qci WHERE status='ACTIVE'").fetchall()
        c.close()
    result = []
    today = date.today()
    for r in [dict(x) for x in rows]:
        if r.get("cert_expires"):
            exp = date.fromisoformat(r["cert_expires"])
            r["days_until_expiry"] = (exp - today).days
            r["expiring_soon"] = r["days_until_expiry"] <= 90
        result.append(r)
    return result

def audit_readiness_report():
    """Generate a complete audit readiness gap report."""
    report = {"date": date.today().isoformat(), "items": [], "score": 0, "max_score": 0}
    
    for key, item in AUDIT_CHECKLIST.items():
        status = "UNKNOWN"
        gap = ""
        
        if key == "active_fabrication":
            log = get_shop_log(7)
            status = "COMPLIANT" if len(log) >= 3 else "GAP"
            gap = f"Only {len(log)} entries in last 7 days" if status == "GAP" else ""
        elif key == "qci_qualifications":
            qcis = get_qci_status()
            expired = [q for q in qcis if q.get("days_until_expiry", 999) < 0]
            status = "COMPLIANT" if qcis and not expired else "GAP"
            gap = f"{len(expired)} QCI(s) with expired cert" if expired else ("No QCIs registered" if not qcis else "")
        elif key == "welder_qualification":
            try:
                from bridge.aws_d11_2025 import get_continuity_alerts
                alerts = get_continuity_alerts(0)
                status = "COMPLIANT" if not alerts else "GAP"
                gap = f"{len(alerts)} welder(s) with lapsed continuity" if alerts else ""
            except Exception:status = "UNKNOWN"
        else:
            status = "NEEDS_REVIEW"
            gap = "Manual verification required"
        
        points = 10 if item["critical"] else 5
        earned = points if status == "COMPLIANT" else 0
        report["max_score"] += points
        report["score"] += earned
        report["items"].append({
            "key": key, **item, "status": status, "gap": gap,
            "points": earned, "max_points": points,
        })
    
    report["readiness_pct"] = round(report["score"] * 100 / max(report["max_score"], 1))
    report["audit_ready"] = report["readiness_pct"] >= 80
    return report
