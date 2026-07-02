"""
bridge/agents/ar_invoice.py - Your Company AR Invoice Tracker (v3.2)
======================================================================
Tracks accounts receivable across 30/20/50 payment milestones.
Calculates TX Prompt Pay interest (1.5%/month, Property Code §28).
Generates SMS alerts when invoices go overdue.
"""

import os, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = (Path(os.environ["LOCALAPPDATA"]) / "YourCompany" / "VirtualOffice" / "data" / "ar_invoices.db") if os.environ.get("LOCALAPPDATA") else (Path(__file__).parent.parent.parent / "data" / "ar_invoices.db")

TX_PROMPT_PAY_RATE_MONTHLY = 0.015   # 1.5%/month per TX Property Code §28


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            contract_value REAL,
            milestone TEXT,        -- MOBILIZATION | DELIVERY | COMPLETION
            milestone_pct REAL,    -- 0.30 | 0.20 | 0.50
            invoice_amount REAL,
            invoice_number TEXT,
            issued_date TEXT,
            due_date TEXT,
            paid_date TEXT,
            status TEXT DEFAULT 'PENDING',  -- PENDING | APPROACHING | DUE_TODAY | WARNING | ESCALATION | PAID
            interest_accrued REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT
        )
    """)
    c.commit()
    return c


# ── Milestone creation ─────────────────────────────────────────────

def create_milestone_invoices(project_name: str, contract_value: float,
                               start_date: str = None) -> list[dict]:
    """Create 30/20/50 milestone invoices for a project."""
    today = start_date or datetime.now().date().isoformat()  # vj: local-time-ok
    milestones = [
        ("MOBILIZATION", 0.30, 30),   # due 30 days from start
        ("DELIVERY",     0.20, 60),   # due 60 days from start
        ("COMPLETION",   0.50, 120),  # due 120 days from start
    ]
    conn = _conn()
    created = []
    for i, (name, pct, offset_days) in enumerate(milestones, 1):
        amount = round(contract_value * pct, 2)
        due = (datetime.now().date() + timedelta(days=offset_days)).isoformat()  # vj: duration-math
        num = f"NC-{datetime.now().year}-{project_name[:6].upper()}-{i:02d}"  # vj: local-time-ok
        conn.execute("""
            INSERT INTO invoices
            (project_name, contract_value, milestone, milestone_pct,
             invoice_amount, invoice_number, issued_date, due_date, created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (project_name, contract_value, name, pct, amount, num,
              today, due, datetime.now(timezone.utc).isoformat()))
        created.append({"milestone": name, "amount": amount, "due": due, "number": num})
    conn.commit()
    conn.close()
    return created


# ── Status computation ─────────────────────────────────────────────

def _compute_status(due_date: str, paid_date: str) -> str:
    if paid_date:
        return "PAID"
    today = datetime.now().date()  # vj: local-time-ok
    due   = datetime.fromisoformat(due_date).date()
    days_to_due = (due - today).days
    days_overdue = (today - due).days

    if days_overdue >= 30:  return "ESCALATION"
    if days_overdue >= 7:   return "WARNING"
    if days_overdue >= 0:   return "DUE_TODAY"
    if days_to_due <= 7:    return "APPROACHING"
    return "PENDING"


def _compute_interest(invoice_amount: float, due_date: str, paid_date: str) -> float:
    """TX Prompt Pay: 1.5%/month on overdue balance."""
    if paid_date:
        return 0.0
    today = datetime.now().date()  # vj: local-time-ok
    due   = datetime.fromisoformat(due_date).date()
    if today <= due:
        return 0.0
    months_overdue = (today - due).days / 30.0
    return round(invoice_amount * TX_PROMPT_PAY_RATE_MONTHLY * months_overdue, 2)


# ── Queries ────────────────────────────────────────────────────────

def get_ar_status(project_name: str = None) -> dict:
    """Get AR status for one project or all active projects."""
    conn = _conn()
    if project_name:
        rows = conn.execute("SELECT * FROM invoices WHERE project_name=?",
                            (project_name,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM invoices WHERE paid_date IS NULL").fetchall()
    conn.close()

    invoices = []
    total_outstanding = 0.0
    total_interest = 0.0
    alerts = []

    for r in rows:
        status   = _compute_status(r["due_date"], r["paid_date"])
        interest = _compute_interest(r["invoice_amount"], r["due_date"], r["paid_date"])
        inv = {
            "id":             r["id"],
            "project":        r["project_name"],
            "milestone":      r["milestone"],
            "invoice_number": r["invoice_number"],
            "amount":         r["invoice_amount"],
            "due_date":       r["due_date"],
            "status":         status,
            "interest":       interest,
            "days_overdue":   max(0, (datetime.now().date() -  # vj: local-time-ok
                                datetime.fromisoformat(r["due_date"]).date()).days),
        }
        invoices.append(inv)

        if not r["paid_date"]:
            total_outstanding += r["invoice_amount"]
            total_interest    += interest

        if status in ("ESCALATION", "WARNING"):
            alerts.append({
                "type":    status,
                "project": r["project_name"],
                "amount":  r["invoice_amount"],
                "interest":interest,
                "message": (f"{r['project_name']} {r['milestone']} ${r['invoice_amount']:,.0f} "
                           f"- {inv['days_overdue']}d overdue, ${interest:,.2f} interest accrued")
            })

    return {
        "invoices":           invoices,
        "total_outstanding":  round(total_outstanding, 2),
        "total_interest":     round(total_interest, 2),
        "alerts":             alerts,
        "escalations":        [a for a in alerts if a["type"] == "ESCALATION"],
    }


def log_payment(invoice_number: str, paid_date: str = None) -> dict:
    """Record a payment received for an invoice."""
    paid = paid_date or datetime.now().date().isoformat()  # vj: local-time-ok
    conn = _conn()
    conn.execute("UPDATE invoices SET paid_date=?, status='PAID' WHERE invoice_number=?",
                 (paid, invoice_number))
    conn.commit()
    conn.close()
    return {"invoice": invoice_number, "paid_date": paid, "status": "PAID"}


def get_ar_alerts() -> list[dict]:
    """Return only alert-level invoices (ESCALATION or WARNING)."""
    status = get_ar_status()
    return status["alerts"]


def draft_invoice_text(invoice_id: int) -> str:
    """Draft a text invoice for sending/printing."""
    conn = _conn()
    r = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    conn.close()
    if not r:
        return f"Invoice ID {invoice_id} not found."
    interest = _compute_interest(r["invoice_amount"], r["due_date"], r["paid_date"])
    total_due = r["invoice_amount"] + interest

    return f"""
YOUR COMPANY, LLC
[COMPANY ADDRESS] · Houston TX 77064 · [COMPANY PHONE]

INVOICE {r['invoice_number']}
Project:   {r['project_name']}
Milestone: {r['milestone']} ({int(r['milestone_pct']*100)}% of contract)
Issued:    {r['issued_date']}
Due:       {r['due_date']}

AMOUNT DUE:    ${r['invoice_amount']:,.2f}
{"TX Prompt Pay Interest: $" + f"{interest:,.2f}" if interest > 0 else ""}
{"TOTAL DUE:    $" + f"{total_due:,.2f}" if interest > 0 else ""}

Payment Terms: Per TX Property Code §28 - 35 days owner→GC, 7 days GC→sub
Late Interest: 1.5%/month on overdue balance

Remit to: owner@yourcompany.example.com | [COMPANY PHONE]
""".strip()
