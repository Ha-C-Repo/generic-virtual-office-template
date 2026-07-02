"""
bridge/agents/ops_agents.py - Your Company Ops Sub-Agents (v3.2)
==================================================================
4 sub-agents covering recurring operational admin:
  1. RFI Tracker     - auto-numbered, CSI tagged, overdue detection
  2. OSHA 300A       - TRIR/DART computation, posting requirements
  3. Prequal Package - 12-item checklist assembler
  4. Case Study      - Tier 1 compliant project summaries
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "ops_agents.db"
    return Path(__file__).resolve().parent.parent / "data" / "ops_agents.db"

DB_PATH = _resolve_db_path()
# AISC NAICS for OSHA industry average comparison
INDUSTRY_TRIR_AVG = 3.2    # NAICS 332312 (Fabricated Structural Steel)
INDUSTRY_DART_AVG = 1.8

# Tier 1: Projects that may appear in case studies
APPROVED_CASE_STUDY_PROJECTS = [
    "icd church", "icd community church",
    "elite crossing",
    "topgolf northbrook",
    "carvana",
]

PREQUAL_CHECKLIST = [
    "AISC 207-25 Quality Management Certification",
    "ISNetworld contractor profile ([ISN ID])",
    "OSHA 300A annual summary (posted + filed)",
    "Experience Modification Rate (EMR) letter from Texas Mutual",
    "Certificate of Insurance - General Liability ($2M CSL)",
    "Certificate of Insurance - Umbrella ($5M)",
    "Certificate of Insurance - Workers Compensation",
    "Certificate of Insurance - Auto Liability ($2M CSL)",
    "Company W-9",
    "Texas Secretary of State registration",
    "Bank reference letter",
    "3 project references (contacts + phone numbers)",
]


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS rfis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfi_number TEXT UNIQUE,
            project_name TEXT,
            csi_division TEXT,
            question TEXT,
            submitted_to TEXT,
            submitted_date TEXT,
            due_date TEXT,
            response TEXT,
            status TEXT DEFAULT 'OPEN',  -- OPEN|RESPONDED|CLOSED
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_date TEXT,
            description TEXT,
            days_away INTEGER DEFAULT 0,
            job_transfer INTEGER DEFAULT 0,
            recordable INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    c.commit()
    return c


# ── 1. RFI TRACKER ─────────────────────────────────────────────────

def create_rfi(project_name: str, question: str, csi_division: str = "05 12 00",
               submitted_to: str = "", due_days: int = 7) -> dict:
    """Create and log an RFI. Auto-numbers as RFI-Project-001.

    Numbering uses the same truncated 8-char prefix that ends up in the
    rfi_number, so projects with similar prefixes don't collide.
    """
    conn = _conn()
    prefix = project_name[:8].upper().replace(" ", "")
    # Count existing RFIs with the same generated prefix (matches what we'll insert)
    pattern = f"RFI-{prefix}-%"
    count = conn.execute("SELECT COUNT(*) FROM rfis WHERE rfi_number LIKE ?",
                         (pattern,)).fetchone()[0]
    rfi_num  = f"RFI-{prefix}-{count+1:03d}"
    due      = (datetime.now() + timedelta(days=due_days)).date().isoformat()  # vj: duration-math
    now      = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO rfis (rfi_number, project_name, csi_division, question,
                          submitted_to, submitted_date, due_date, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (rfi_num, project_name, csi_division, question,
          submitted_to, datetime.now().date().isoformat(), due, now))  # vj: local-time-ok
    conn.commit()
    conn.close()
    return {"rfi_number": rfi_num, "due_date": due, "status": "OPEN"}


def list_rfis(project_name: str = None, overdue_only: bool = False) -> list[dict]:
    today = datetime.now().date().isoformat()  # vj: local-time-ok
    conn  = _conn()
    q     = "SELECT * FROM rfis WHERE 1=1"
    p     = []
    if project_name:
        q += " AND project_name=?"; p.append(project_name)
    if overdue_only:
        q += " AND due_date<? AND status='OPEN'"; p.append(today)
    q += " ORDER BY due_date ASC"
    rows  = conn.execute(q, p).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["overdue"] = (d["due_date"] < today and d["status"] == "OPEN")
        result.append(d)
    return result


# ── 2. OSHA 300A ────────────────────────────────────────────────────

def log_incident(description: str, days_away: int = 0,
                 job_transfer: int = 0, incident_date: str = None) -> dict:
    date = incident_date or datetime.now().date().isoformat()  # vj: local-time-ok
    conn = _conn()
    conn.execute("""
        INSERT INTO incidents (incident_date, description, days_away, job_transfer, created_at)
        VALUES (?,?,?,?,?)
    """, (date, description, days_away, job_transfer, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    return {"logged": True, "date": date, "description": description}


def generate_osha_300a(year: int = None, total_hours_worked: float = 25000.0,
                        avg_employees: int = 12) -> dict:
    """Compute OSHA 300A summary statistics."""
    yr   = year or datetime.now().year  # vj: local-time-ok
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM incidents WHERE strftime('%Y', incident_date)=?", (str(yr),)
    ).fetchall()
    conn.close()

    total_cases  = len(rows)
    days_away    = sum(r["days_away"] for r in rows)
    transfers    = sum(r["job_transfer"] for r in rows)

    # TRIR = (recordable cases × 200,000) / hours worked
    trir = round((total_cases * 200000) / total_hours_worked, 2) if total_hours_worked else 0
    # DART = (days away + transfers) × 200,000 / hours
    dart_cases = sum(1 for r in rows if r["days_away"] > 0 or r["job_transfer"] > 0)
    dart = round((dart_cases * 200000) / total_hours_worked, 2) if total_hours_worked else 0

    posting_deadline = f"February 1, {yr+1}"
    removal_deadline = f"April 30, {yr+1}"

    return {
        "year":               yr,
        "total_recordable":   total_cases,
        "days_away_cases":    len([r for r in rows if r["days_away"] > 0]),
        "total_days_away":    days_away,
        "restricted_transfer":transfers,
        "avg_employees":      avg_employees,
        "hours_worked":       total_hours_worked,
        "trir":               trir,
        "dart":               dart,
        "industry_trir_avg":  INDUSTRY_TRIR_AVG,
        "industry_dart_avg":  INDUSTRY_DART_AVG,
        "trir_vs_industry":   f"{'BELOW' if trir < INDUSTRY_TRIR_AVG else 'ABOVE'} industry avg",
        "posting_required":   posting_deadline,
        "can_remove":         removal_deadline,
        "naics":              "332312",
    }


# ── 3. PREQUAL PACKAGE ─────────────────────────────────────────────

def get_prequal_status(completed_items: list[str] = None) -> dict:
    """Return prequal checklist with completion status."""
    completed = set(completed_items or [])
    items = []
    for item in PREQUAL_CHECKLIST:
        done = any(c.lower() in item.lower() for c in completed)
        items.append({"item": item, "complete": done})
    total     = len(PREQUAL_CHECKLIST)
    complete  = sum(1 for i in items if i["complete"])
    missing   = [i["item"] for i in items if not i["complete"]]
    pct       = round(complete / total * 100)
    critical  = [m for m in missing if "EMR" in m or "Insurance" in m or "AISC" in m]

    return {
        "total":           total,
        "complete":        complete,
        "percent":         pct,
        "items":           items,
        "missing":         missing,
        "critical_missing":critical,
        "ready_to_submit": pct >= 100,
        "summary":         f"{pct}% complete ({complete}/{total}). "
                           + (f"Critical gaps: {', '.join(critical)}" if critical else "No critical gaps."),
    }


def assemble_prequal_package(gc_name: str = "") -> str:
    """Generate a prequal submission cover letter."""
    return f"""
YOUR COMPANY, LLC - PRE-QUALIFICATION PACKAGE
[COMPANY ADDRESS] · Houston TX 77064 · [COMPANY PHONE]
ISNetworld: [ISN ID] | AISC 207-25 Certified

Date: {datetime.now().strftime('%B %d, %Y')}  # vj: local-display-ok
{"Submitted to: " + gc_name if gc_name else ""}

COMPANY PROFILE:
Your Company, LLC is a Houston-based structural steel fabricator and erector.
Specialties: commercial, industrial, and refinery structural steel.
Team: 12 direct employees, licensed ironworkers, NCCER-certified welders.
Capacity: 1,500+ tons active fabrication.

SAFETY:
OSHA 300A current | EMR from Texas Mutual (available on request)
ISNetworld Grade A | No OSHA citations (past 3 years)

CERTIFICATIONS:
• AISC 207-25 Quality Management System
• AWS D1.1 Structural Welding (shop + field)
• ISNetworld [ISN ID] (current standing)

REFERENCES available upon request.

The Owner, CEO
owner@yourcompany.example.com | [COMPANY PHONE]
""".strip()


# ── 4. CASE STUDY ──────────────────────────────────────────────────

def generate_case_study(project_name: str, tonnage: float = 0,
                         scope: str = "", outcome: str = "") -> dict:
    """
    Generate a case study for an approved project.
    Tier 1: only approved projects may appear in marketing materials.
    """
    project_lower = project_name.lower()
    approved = any(p in project_lower for p in APPROVED_CASE_STUDY_PROJECTS)

    if not approved:
        return {
            "refused": True,
            "reason":  (f"'{project_name}' is not on the approved case study list. "
                        "Tier 1 rule: only ICD Church, Elite Crossing, Topgolf NB, "
                        "and Carvana may appear in external materials."),
            "approved_projects": APPROVED_CASE_STUDY_PROJECTS,
        }

    text = f"""
CASE STUDY: {project_name.upper()}

Your Company delivered {f'{tonnage:.0f} tons of ' if tonnage else ''}structural steel
{"for " + scope + ". " if scope else ""}

{"Outcome: " + outcome if outcome else ""}

SCOPE: Fabrication, delivery, and erection of structural steel per AISC 207-25.
All welding per AWS D1.1. Delivered on schedule with zero recordable incidents.

Your Company · Houston, TX · [COMPANY PHONE] · owner@yourcompany.example.com
ISNetworld [ISN ID] · AISC 207-25 Certified
""".strip()

    return {"approved": True, "project": project_name, "case_study": text}
