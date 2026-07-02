"""
bridge/agents/industrial_outreach.py - Your Company (v3.2)
============================================================
Systematic refinery/EPC outreach. 5-input rule enforced.
8 Houston refineries with turnaround windows. SQLite log.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "outreach_log.db"
    return Path(__file__).resolve().parent.parent / "data" / "outreach_log.db"

DB_PATH = _resolve_db_path()
# Houston refineries with turnaround lead-time requirements
def _build_refineries_from_calibration() -> dict:
    """Build HOUSTON_REFINERIES from the Q2 2026 calibration JSON.

    Falls back to inline dict if calibration file is missing. Adds metadata
    fields the templates need: location (derived), turnaround_months,
    contact_lead_weeks, capacity_bpd, owner.
    """
    try:
        from bridge.calibration_2026q2 import get_all_refineries
        rows = get_all_refineries()
        if not rows:
            return _INLINE_REFINERIES
        out = {}
        for r in rows:
            name = r.get("name", "")
            # Derive a location string from the name
            location = name.split(" ", 1)[-1] + ", TX" if "," not in name else "Texas"
            for marker, loc in [
                ("Galveston Bay", "Texas City, TX"),
                ("Baytown",       "Baytown, TX"),
                ("Deer Park",     "Deer Park, TX"),
                ("Port Arthur",   "Port Arthur, TX"),
                ("Sweeny",        "Sweeny, TX"),
                ("Pasadena",      "Pasadena, TX"),
                ("Houston",       "Houston, TX"),
                ("Corpus Christi","Corpus Christi, TX"),
            ]:
                if marker in name:
                    location = loc
                    break
            out[name] = {
                "location":           location,
                "contact_lead_weeks": r.get("contact_lead_weeks", 12),
                "turnaround_months":  r.get("typical_TA_months", []),
                "capacity_bpd":       r.get("capacity_bpd", 0),
                "owner":              r.get("owner", ""),
                "avg_TA_duration_days": r.get("avg_TA_duration_days", 45),
                "notes":              f"{r.get('owner','')} · {r.get('capacity_bpd',0):,} bpd · "
                                       f"{r.get('avg_TA_duration_days',45)}-day TAs",
            }
        return out
    except Exception:
        return _INLINE_REFINERIES


# Inline fallback (preserved for offline / calibration-missing scenarios)
_INLINE_REFINERIES = {
    "Marathon Petroleum Galveston Bay": {
        "location": "Texas City, TX",
        "contact_lead_weeks": 16,
        "turnaround_months": [3, 9],
        "notes": "PLA 2026 active. ISN required. Marathon safety orientation.",
    },
    "Valero Port Arthur": {
        "location": "Port Arthur, TX",
        "contact_lead_weeks": 12,
        "turnaround_months": [4, 10],
        "notes": "Large refinery. Multiple contractors. Bid markup approved.",
    },
    "ExxonMobil Baytown": {
        "location": "Baytown, TX",
        "contact_lead_weeks": 20,
        "turnaround_months": [2, 8],
        "notes": "Baytown complex. Highest safety standards. Long procurement lead.",
    },
    "LyondellBasell Houston": {
        "location": "Houston, TX",
        "contact_lead_weeks": 10,
        "turnaround_months": [5, 11],
        "notes": "Close proximity. Good fit for fab + erect.",
    },
    "Shell Deer Park": {
        "location": "Deer Park, TX",
        "contact_lead_weeks": 14,
        "turnaround_months": [3, 10],
        "notes": "Shell/Pemex JV. Two procurement paths.",
    },
    "Chevron Phillips Cedar Bayou": {
        "location": "Baytown, TX",
        "contact_lead_weeks": 12,
        "turnaround_months": [4, 9],
        "notes": "Petrochemical focus. Specialty steel connections.",
    },
    "Total Energies Port Arthur": {
        "location": "Port Arthur, TX",
        "contact_lead_weeks": 16,
        "turnaround_months": [6, 12],
        "notes": "European procurement style. Long review cycles.",
    },
    "Huntsman Port Neches": {
        "location": "Port Neches, TX",
        "contact_lead_weeks": 8,
        "turnaround_months": [5, 10],
        "notes": "Smaller turnarounds. Good entry-point for relationship building.",
    },
}


HOUSTON_REFINERIES = _build_refineries_from_calibration()

TEMPLATES = {
    "refinery_turnaround": """Subject: Structural Steel Fabrication & Erection - {refinery} Turnaround Support

{name},

Your Company is a Houston-based structural steel fabricator and erector.
We specialize in refinery turnaround support - fast-track fab, field erection, and QC.

Our Q2 2026 capacity: 1,500+ active tons. ISN [ISN ID]. AISC 207-25 certified.
We're reaching out {lead_time_note} ahead of your {turnaround_note} window.

Scope we can support: structural platforms, pipe racks, equipment supports,
access steel, and emergency field repairs.

Available for a 20-minute call to discuss your 2026 turnaround scope?

The Owner
Your Company, LLC · [COMPANY PHONE] · owner@yourcompany.example.com
""",
    "epc_project": """Subject: Structural Steel Partner - {project_name}

{name},

Your Company is pursuing structural steel scope on {project_name}.
We fabricate and erect in Houston - 1,500+ active tons, ISN-verified, AISC 207-25.

Scope offered: {scope}. We can turn a takeoff in 48 hours once drawings are issued.

Is Your Company on your approved bidder list for this project?

The Owner
Your Company · [COMPANY PHONE]
""",
    "gc_introduction": """Subject: Structural Steel Subcontractor - Houston Metro

{name},

We're a Houston structural steel fabricator and erector: Your Company.
ISN [ISN ID] | AISC 207-25 | Texas-licensed | 12-person crew + field team.

We bid commercial, industrial, and refinery scope across Houston metro.
Current pipeline: ${pipeline_value}M.

Are there any upcoming projects where you need a steel sub?

The Owner · Your Company · [COMPANY PHONE]
""",
}


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS outreach (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            contact_name TEXT,
            contact_role TEXT,
            template_type TEXT,
            message_draft TEXT,
            hook TEXT,
            timing_reason TEXT,
            sent_date TEXT,
            follow_up_date TEXT,
            response TEXT,
            status TEXT DEFAULT 'DRAFTED',  -- DRAFTED|SENT|RESPONDED|CLOSED
            created_at TEXT
        )
    """)
    c.commit()
    return c


def draft_outreach(company: str, contact_name: str, contact_role: str,
                   hook: str, timing_reason: str,
                   template: str = "refinery_turnaround",
                   extra_vars: dict = None,
                   preview_only: bool = False) -> dict:
    """
    Draft a cold outreach message. 5 inputs required:
      company, contact_name, contact_role, hook, timing_reason.

    Args:
        preview_only: if True, returns the rendered message WITHOUT writing
                      to the outreach database. UI uses this to show a
                      preview gate so Joseph/Owner approve before commit.
                      Call confirm_outreach() to commit a previewed draft.
    """
    if not all([company, contact_name, contact_role, hook, timing_reason]):
        return {
            "error": ("5 inputs required: company, contact_name, contact_role, "
                      "hook, timing_reason. All must be non-empty.")
        }

    # Get refinery data if applicable
    refinery_data = HOUSTON_REFINERIES.get(company, {})
    lead_weeks    = refinery_data.get("contact_lead_weeks", 8)
    ta_months     = refinery_data.get("turnaround_months", [])
    ta_note       = (f"Q{(ta_months[0]-1)//3+1} turnaround"
                     if ta_months else "upcoming turnaround")
    lead_note     = f"{lead_weeks} weeks"

    vars_dict = {
        "name":            contact_name,
        "refinery":        company,
        "project_name":    company,
        "contact_role":    contact_role,
        "hook":            hook,
        "timing_reason":   timing_reason,
        "lead_time_note":  lead_note,
        "turnaround_note": ta_note,
        "scope":           hook,
        "pipeline_value":  "5.9",
    }
    if extra_vars:
        vars_dict.update(extra_vars)

    tpl = TEMPLATES.get(template, TEMPLATES["refinery_turnaround"])
    try:
        message = tpl.format(**vars_dict)
    except KeyError as e:
        message = tpl  # return raw if formatting fails

    # Follow-up in 10 business days
    follow_up = (datetime.now() + timedelta(days=14)).date().isoformat()  # vj: duration-math

    # PREVIEW GATE: render message but skip DB write
    if preview_only:
        return {
            "preview":       True,
            "company":       company,
            "contact":       contact_name,
            "contact_role":  contact_role,
            "template":      template,
            "message":       message,
            "follow_up":     follow_up,
            "refinery_data": refinery_data,
            "hook":          hook,
            "timing_reason": timing_reason,
            "next_step":     "Call confirm_outreach() with these inputs to commit",
        }

    conn = _conn()
    cursor = conn.execute("""
        INSERT INTO outreach
        (company, contact_name, contact_role, template_type, message_draft,
         hook, timing_reason, follow_up_date, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (company, contact_name, contact_role, template, message,
          hook, timing_reason, follow_up, datetime.now(timezone.utc).isoformat()))
    outreach_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id":            outreach_id,
        "company":       company,
        "contact":       contact_name,
        "template":      template,
        "message":       message,
        "follow_up":     follow_up,
        "refinery_data": refinery_data,
    }


def confirm_outreach(company: str, contact_name: str, contact_role: str,
                     hook: str, timing_reason: str,
                     template: str = "refinery_turnaround") -> dict:
    """Commit a previously-previewed outreach to the database.

    Same arguments as draft_outreach() but always writes (preview_only=False).
    Use this after a preview has been approved by Joseph or Owner.
    """
    return draft_outreach(company, contact_name, contact_role,
                           hook, timing_reason, template, preview_only=False)


def log_sent(outreach_id: int) -> dict:
    conn = _conn()
    conn.execute("UPDATE outreach SET status='SENT', sent_date=? WHERE id=?",
                 (datetime.now(timezone.utc).isoformat(), outreach_id))
    conn.commit()
    conn.close()
    return {"id": outreach_id, "status": "SENT"}


def log_response(outreach_id: int, response_text: str) -> dict:
    conn = _conn()
    conn.execute("UPDATE outreach SET status='RESPONDED', response=? WHERE id=?",
                 (response_text, outreach_id))
    conn.commit()
    conn.close()
    return {"id": outreach_id, "status": "RESPONDED"}


def get_outreach_log(company: str = None) -> list[dict]:
    conn = _conn()
    if company:
        rows = conn.execute("SELECT * FROM outreach WHERE company=? ORDER BY created_at DESC",
                            (company,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM outreach ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_due_followups() -> list[dict]:
    """Return outreach items where follow-up is due today or overdue."""
    today = datetime.now().date().isoformat()  # vj: local-time-ok
    conn  = _conn()
    rows  = conn.execute(
        "SELECT * FROM outreach WHERE follow_up_date<=? AND status='SENT'",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def schedule_followup(outreach_id: int, days: int = 7) -> dict:
    new_date = (datetime.now() + timedelta(days=days)).date().isoformat()  # vj: duration-math
    conn = _conn()
    conn.execute("UPDATE outreach SET follow_up_date=? WHERE id=?",
                 (new_date, outreach_id))
    conn.commit()
    conn.close()
    return {"id": outreach_id, "follow_up_date": new_date}
