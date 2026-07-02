"""
bridge/agents/change_order.py - Your Company Change Order Agent (v3.2)
========================================================================
AIA G701-style change orders. Auto-numbered per project.
8 Houston-calibrated task rates (shop + field).
Approval workflow: DRAFT → APPROVED → SUBMITTED → ACCEPTED/REJECTED
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "change_orders.db"
    return Path(__file__).resolve().parent.parent / "data" / "change_orders.db"

DB_PATH = _resolve_db_path()
# Houston-calibrated task rates (April 2026)
TASK_RATES = {
    "welded_moment_joint":  {"hours": 12,  "unit": "each",   "desc": "Full-penetration welded moment connection"},
    "gusset_plate":         {"hours": 4,   "unit": "each",   "desc": "Gusset plate fabrication + fit-up"},
    "field_handrail":       {"rate": 82.50, "unit": "LF",    "desc": "Field-fabricated handrail @ $82.50/LF"},
    "a325_bolts":           {"rate": 1.85,  "unit": "each",  "desc": "A325 high-strength bolt installed @ $1.85/ea"},
    "stair_risers":         {"rate": 345.0, "unit": "each",  "desc": "Steel stair riser, fabricated + installed"},
    "misc_steel":           {"rate": 9.50,  "unit": "lb",    "desc": "Miscellaneous steel @ $9.50/lb"},
    "field_weld":           {"rate": 18.50, "unit": "in",    "desc": "Field weld @ $18.50/linear inch"},
    "crane_time":           {"rate": 350.0, "unit": "hr",    "desc": "Crane rental + operator @ $350/hr"},
}

SHOP_RATE    = 145.0   # burdened $/hr
DEFAULT_MARKUP = 0.22  # 22% markup on direct cost


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS change_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            co_number TEXT UNIQUE,
            project_name TEXT,
            description TEXT,
            line_items TEXT,      -- JSON
            direct_cost REAL,
            markup_pct REAL,
            total_cost REAL,
            schedule_impact_days INTEGER DEFAULT 0,
            status TEXT DEFAULT 'DRAFT',  -- DRAFT|APPROVED|SUBMITTED|ACCEPTED|REJECTED
            submitted_date TEXT,
            accepted_date TEXT,
            notes TEXT,
            created_at TEXT
        )
    """)
    c.commit()
    return c


def _next_co_number(project_name: str) -> str:
    """Generate next CO number for this project.

    Counts by the truncated 8-char prefix that ends up in the co_number,
    not the full project name - prevents collisions when two projects
    share the same first 8 characters.
    """
    conn = _conn()
    proj_slug = project_name[:8].upper().replace(" ", "")
    pattern = f"CO-{proj_slug}-%"
    count = conn.execute("SELECT COUNT(*) FROM change_orders WHERE co_number LIKE ?",
                         (pattern,)).fetchone()[0]
    conn.close()
    return f"CO-{proj_slug}-{count+1:03d}"


def create_change_order(project_name: str, description: str,
                        line_items: list[dict],
                        schedule_impact_days: int = 0,
                        markup_pct: float = DEFAULT_MARKUP,
                        notes: str = "") -> dict:
    """
    Create a change order.

    line_items format:
      [{"task": "field_weld", "qty": 24, "unit": "in"},
       {"task": "misc_steel", "qty": 450, "unit": "lb"},
       {"description": "Custom scope", "cost": 1200.0}]
    """
    direct_cost = 0.0
    priced_items = []

    for item in line_items:
        task_key = item.get("task", "")
        qty      = float(item.get("qty", 1))

        if task_key and task_key in TASK_RATES:
            rate_info = TASK_RATES[task_key]
            if "hours" in rate_info:
                item_cost = rate_info["hours"] * qty * SHOP_RATE
            else:
                item_cost = rate_info["rate"] * qty
            priced_items.append({
                "task":        task_key,
                "description": item.get("description", rate_info["desc"]),
                "qty":         qty,
                "unit":        rate_info["unit"],
                "unit_cost":   rate_info.get("rate", rate_info.get("hours", 0) * SHOP_RATE),
                "total":       round(item_cost, 2),
            })
        elif "cost" in item:
            item_cost = float(item["cost"])
            priced_items.append({
                "description": item.get("description", "Custom scope"),
                "qty":         qty,
                "total":       round(item_cost, 2),
            })
        else:
            continue

        direct_cost += item_cost

    markup_amount = direct_cost * markup_pct
    total_cost    = round(direct_cost + markup_amount, 2)
    co_number     = _next_co_number(project_name)
    now           = datetime.now(timezone.utc).isoformat()

    conn = _conn()
    conn.execute("""
        INSERT INTO change_orders
        (co_number, project_name, description, line_items, direct_cost,
         markup_pct, total_cost, schedule_impact_days, notes, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (co_number, project_name, description,
          json.dumps(priced_items), round(direct_cost, 2),
          markup_pct, total_cost, schedule_impact_days, notes, now))
    conn.commit()
    conn.close()

    return {
        "co_number":            co_number,
        "project":              project_name,
        "description":          description,
        "line_items":           priced_items,
        "direct_cost":          round(direct_cost, 2),
        "markup":               round(markup_amount, 2),
        "total":                total_cost,
        "schedule_impact_days": schedule_impact_days,
        "status":               "DRAFT",
    }


def update_co_status(co_number: str, status: str) -> dict:
    """Advance CO through approval workflow."""
    valid = ("DRAFT", "APPROVED", "SUBMITTED", "ACCEPTED", "REJECTED")
    if status not in valid:
        return {"error": f"Invalid status. Must be one of: {valid}"}
    now  = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    if status == "SUBMITTED":
        conn.execute("UPDATE change_orders SET status=?, submitted_date=? WHERE co_number=?",
                     (status, now, co_number))
    elif status == "ACCEPTED":
        conn.execute("UPDATE change_orders SET status=?, accepted_date=? WHERE co_number=?",
                     (status, now, co_number))
    else:
        conn.execute("UPDATE change_orders SET status=? WHERE co_number=?",
                     (status, co_number))
    conn.commit()
    conn.close()
    return {"co_number": co_number, "status": status, "updated": now}


def list_change_orders(project_name: str = None, status: str = None) -> list[dict]:
    """List change orders with optional filters."""
    conn = _conn()
    q = "SELECT * FROM change_orders WHERE 1=1"
    params = []
    if project_name:
        q += " AND project_name=?"
        params.append(project_name)
    if status:
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def format_co_document(co_number: str) -> str:
    """Format a printable change order document."""
    conn = _conn()
    r = conn.execute("SELECT * FROM change_orders WHERE co_number=?", (co_number,)).fetchone()
    conn.close()
    if not r:
        return f"Change order {co_number} not found."

    items = json.loads(r["line_items"]) if r["line_items"] else []
    item_lines = "\n".join(
        f"  {i['description']:<45} ${i['total']:>10,.2f}"
        for i in items
    )

    schedule_note = (f"\nSCHEDULE IMPACT: {r['schedule_impact_days']} calendar days extension"
                     if r["schedule_impact_days"] else "")

    return f"""
CHANGE ORDER {r['co_number']}
PROJECT: {r['project_name']}
DATE:    {r['created_at'][:10]}
STATUS:  {r['status']}

DESCRIPTION:
{r['description']}

LINE ITEMS:
{item_lines}
                                                ─────────────
  Direct Cost                                    ${r['direct_cost']:>10,.2f}
  Markup ({int(r['markup_pct']*100)}%)                                   ${r['direct_cost']*r['markup_pct']:>10,.2f}
                                                ─────────────
  TOTAL CHANGE ORDER VALUE                       ${r['total_cost']:>10,.2f}
{schedule_note}

Submitted by Your Company, LLC
The Owner, CEO · [COMPANY PHONE]
""".strip()
