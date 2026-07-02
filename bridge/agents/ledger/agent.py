"""
Your Company Virtual Office - Ledger Agent

Replaces: QuickBooks Online API ($500) + Sage 100 Connector ($2,500)
Cost: $0

Strategy: Import QBO/Sage CSV exports nightly into a local SQLite
construction accounting ledger. Books still close in QuickBooks -
but every analytic dashboard runs off our SQLite.

Chart of Accounts mirrors QBO's standard construction template:
  Assets / Liabilities / Equity / Income /
  COGS-Materials / COGS-Labor / COGS-Subs / COGS-Equipment / Overhead
"""

import csv, json, sqlite3, threading, io
from datetime import datetime, date, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "ledger.db"
    return Path(__file__).resolve().parent.parent / "data" / "ledger.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# Standard construction Chart of Accounts
CONSTRUCTION_COA = {
    "1000": {"name": "Checking Account", "type": "Asset"},
    "1100": {"name": "Accounts Receivable", "type": "Asset"},
    "1200": {"name": "Retainage Receivable", "type": "Asset"},
    "1300": {"name": "Inventory - Steel", "type": "Asset"},
    "1500": {"name": "Fixed Assets - Equipment", "type": "Asset"},
    "2000": {"name": "Accounts Payable", "type": "Liability"},
    "2100": {"name": "Retainage Payable", "type": "Liability"},
    "2200": {"name": "Accrued Payroll", "type": "Liability"},
    "2300": {"name": "Sales Tax Payable", "type": "Liability"},
    "2400": {"name": "Line of Credit", "type": "Liability"},
    "3000": {"name": "Equity", "type": "Equity"},
    "3100": {"name": "Retained Earnings", "type": "Equity"},
    "4000": {"name": "Revenue - Fabrication", "type": "Income"},
    "4100": {"name": "Revenue - Erection", "type": "Income"},
    "4200": {"name": "Revenue - Change Orders", "type": "Income"},
    "5000": {"name": "COGS - Materials (Steel)", "type": "COGS"},
    "5100": {"name": "COGS - Direct Labor", "type": "COGS"},
    "5200": {"name": "COGS - Subcontractors", "type": "COGS"},
    "5300": {"name": "COGS - Equipment Rental", "type": "COGS"},
    "5400": {"name": "COGS - Consumables (Welding)", "type": "COGS"},
    "6000": {"name": "Overhead - Rent/Lease", "type": "Expense"},
    "6100": {"name": "Overhead - Insurance (WC/GL/Auto)", "type": "Expense"},
    "6200": {"name": "Overhead - Utilities", "type": "Expense"},
    "6300": {"name": "Overhead - Office/Admin", "type": "Expense"},
    "6400": {"name": "Overhead - Vehicle/Fuel", "type": "Expense"},
    "6500": {"name": "Overhead - Professional Fees", "type": "Expense"},
}


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            account_type TEXT NOT NULL, balance REAL DEFAULT 0,
            parent_code TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_date TEXT NOT NULL, account_code TEXT NOT NULL,
            description TEXT DEFAULT '', debit REAL DEFAULT 0,
            credit REAL DEFAULT 0, project TEXT DEFAULT '',
            reference TEXT DEFAULT '', source TEXT DEFAULT 'manual',
            imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reconciliation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recon_date TEXT NOT NULL, bank_balance REAL,
            book_balance REAL, difference REAL,
            status TEXT DEFAULT 'pending', notes TEXT DEFAULT '',
            generated_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_date)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_txn_project ON transactions(project)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_code)")
    except Exception:
        pass  # column may not exist in older schema
    # Seed Chart of Accounts
    for code, info in CONSTRUCTION_COA.items():
        c.execute("INSERT OR IGNORE INTO accounts (account_code,name,account_type) VALUES (?,?,?)",
                  (code, info["name"], info["type"]))
    c.commit(); c.close()
_init()


def import_qbo_csv(csv_text: str, source: str = "QBO") -> dict:
    """Import QuickBooks CSV export into the ledger.

    Expected columns: Date, Account, Description, Debit, Credit, Class/Project
    Flexible: handles QBO, Sage, and generic CSV formats.
    """
    now = datetime.now(timezone.utc).isoformat()
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    errors = []

    with _lock:
        c = _conn()
        for i, row in enumerate(reader):
            try:
                txn_date = row.get("Date", row.get("Trans Date", row.get("date", "")))
                account = row.get("Account", row.get("Account Name", row.get("account", "")))
                desc = row.get("Description", row.get("Memo", row.get("description", "")))
                debit = float(row.get("Debit", row.get("debit", 0)) or 0)
                credit = float(row.get("Credit", row.get("credit", 0)) or 0)
                project = row.get("Class", row.get("Project", row.get("Job", "")))
                ref = row.get("Reference", row.get("Num", row.get("Check #", "")))

                # Map account name to code
                acct_code = _find_account_code(c, account)

                c.execute(
                    "INSERT INTO transactions (txn_date,account_code,description,debit,credit,project,reference,source,imported_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (txn_date, acct_code, desc, debit, credit, project, ref, source, now))
                imported += 1
            except Exception as e:
                errors.append(f"Row {i+1}: {str(e)[:100]}")

        c.commit(); c.close()

    return {"imported": imported, "errors": len(errors), "error_details": errors[:5],
            "source": source}


def _find_account_code(conn, account_name: str) -> str:
    """Map an account name to our Chart of Accounts code."""
    if not account_name:
        return "6300"  # Default to Office/Admin
    name_lower = account_name.lower()

    # Direct code match
    for code, info in CONSTRUCTION_COA.items():
        if info["name"].lower() in name_lower or name_lower in info["name"].lower():
            return code

    # Keyword matching
    if any(kw in name_lower for kw in ["check", "bank", "cash"]):
        return "1000"
    if any(kw in name_lower for kw in ["receivable", "a/r"]):
        return "1100"
    if any(kw in name_lower for kw in ["payable", "a/p"]):
        return "2000"
    if any(kw in name_lower for kw in ["steel", "material", "metal"]):
        return "5000"
    if any(kw in name_lower for kw in ["labor", "payroll", "wage"]):
        return "5100"
    if any(kw in name_lower for kw in ["sub", "contractor"]):
        return "5200"
    if any(kw in name_lower for kw in ["insurance", "wc", "gl"]):
        return "6100"
    if any(kw in name_lower for kw in ["revenue", "income", "billing"]):
        return "4000"
    return "6300"  # Default


def get_project_profitability(project: str) -> dict:
    """P&L for a specific project."""
    with _lock:
        c = _conn()
        income = c.execute(
            "SELECT SUM(credit) - SUM(debit) FROM transactions WHERE project=? AND account_code LIKE '4%'",
            (project,)).fetchone()[0] or 0
        cogs = c.execute(
            "SELECT SUM(debit) - SUM(credit) FROM transactions WHERE project=? AND account_code LIKE '5%'",
            (project,)).fetchone()[0] or 0
        c.close()

    gross_profit = income - cogs
    margin = (gross_profit / income * 100) if income > 0 else 0

    return {
        "project": project,
        "income": round(income, 2),
        "cogs": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(margin, 1),
    }


def get_ar_aging() -> dict:
    """Accounts receivable aging."""
    with _lock:
        c = _conn()
        rows = c.execute(
            "SELECT project, SUM(debit) - SUM(credit) as balance, MAX(txn_date) as last_date FROM transactions WHERE account_code='1100' GROUP BY project HAVING balance > 0 ORDER BY balance DESC"
        ).fetchall()
        c.close()

    aging = {"current": 0, "30_day": 0, "60_day": 0, "90_plus": 0, "details": []}
    today = date.today()
    for r in rows:
        try:
            last = date.fromisoformat(r["last_date"])
            days = (today - last).days
        except Exception:
            days = 0
        bucket = "current" if days <= 30 else "30_day" if days <= 60 else "60_day" if days <= 90 else "90_plus"
        aging[bucket] += r["balance"]
        aging["details"].append({"project": r["project"], "balance": r["balance"], "days": days, "bucket": bucket})

    return aging


def get_dashboard() -> dict:
    """Financial dashboard for Owner."""
    with _lock:
        c = _conn()
        total_income = c.execute("SELECT SUM(credit) - SUM(debit) FROM transactions WHERE account_code LIKE '4%'").fetchone()[0] or 0
        total_cogs = c.execute("SELECT SUM(debit) - SUM(credit) FROM transactions WHERE account_code LIKE '5%'").fetchone()[0] or 0
        total_overhead = c.execute("SELECT SUM(debit) - SUM(credit) FROM transactions WHERE account_code LIKE '6%'").fetchone()[0] or 0
        txn_count = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        c.close()

    return {
        "revenue": round(total_income, 2),
        "cogs": round(total_cogs, 2),
        "gross_profit": round(total_income - total_cogs, 2),
        "overhead": round(total_overhead, 2),
        "net_income": round(total_income - total_cogs - total_overhead, 2),
        "transactions_imported": txn_count,
    }


def stats() -> dict:
    with _lock:
        c = _conn()
        accounts = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        txns = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        c.close()
    return {"accounts": accounts, "transactions": txns,
            "replaces": "QBO API ($500) + Sage 100 ($2,500) = $3,000/yr",
            "our_cost": "$0 - CSV import from QBO/Sage exports"}
