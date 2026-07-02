"""
Your Company Virtual Office - QuickBooks Desktop Bridge (v3.2)
============================================================

Parses QuickBooks Desktop Trial Balance exports (CSV or XLSX) and maps
GL accounts to the Your Company 26-account construction Chart of Accounts.

QuickBooks Desktop exports Trial Balances in two common formats:
  1. CSV: "Account", "Debit", "Credit" columns (QBD Reports → Export to CSV)
  2. XLSX: Same columns in an Excel workbook (QBD Reports → Export to Excel)

The mapper uses a multi-strategy approach:
  1. Exact match on account name (highest confidence)
  2. Keyword match on account name fragments (medium confidence)
  3. Account type inference from debit/credit pattern (low confidence)

HIGH confidence (≥0.8)  → auto-populate cost tracker, no review needed
MEDIUM confidence (0.5-0.79) → populate but flag amber for the Owner's review
LOW confidence (<0.5)   → skip, flag red, Owner must manually assign

Usage:
  from bridge.quickbooks_bridge import parse_trial_balance, map_accounts
  result = parse_trial_balance(csv_text)
  mapped = map_accounts(result["accounts"])
"""

import csv
import io
from datetime import datetime, timezone
from difflib import SequenceMatcher


# ══════════════════════════════════════════════════════════════════════
# YOUR COMPANY CONSTRUCTION COA (must match bridge/agents/ledger/agent.py)
# ══════════════════════════════════════════════════════════════════════

NANO_COA = {
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

# ══════════════════════════════════════════════════════════════════════
# KEYWORD MAPPING TABLE - maps QBD account name fragments to Nano COA
# Each entry: (keyword_patterns, nano_code, confidence_boost)
# ══════════════════════════════════════════════════════════════════════

KEYWORD_MAP = [
    # Asset accounts
    (["checking", "cash", "bank", "operating"], "1000", 0.75),
    (["accounts receivable", "a/r", "trade receivable"], "1100", 0.85),
    (["retainage receivable", "retention receivable"], "1200", 0.90),
    (["inventory", "steel inventory", "material inventory", "raw material"], "1300", 0.80),
    (["fixed asset", "equipment", "machinery", "vehicle", "truck", "crane", "forklift"], "1500", 0.75),

    # Liability accounts
    (["accounts payable", "a/p", "trade payable"], "2000", 0.85),
    (["retainage payable", "retention payable"], "2100", 0.90),
    (["payroll liab", "accrued payroll", "wages payable", "payroll tax"], "2200", 0.80),
    (["sales tax", "use tax"], "2300", 0.85),
    (["line of credit", "loc", "credit line", "revolving", "loan"], "2400", 0.70),

    # Equity
    (["equity", "owner", "member", "capital", "draw", "distribution"], "3000", 0.70),
    (["retained earnings", "net income"], "3100", 0.85),

    # Revenue (steel-specific keywords boost confidence)
    (["fabrication revenue", "fab revenue", "steel fabrication"], "4000", 0.90),
    (["erection revenue", "erect revenue", "steel erection", "field revenue"], "4100", 0.90),
    (["change order", "co revenue", "extra work", "modification"], "4200", 0.85),
    (["revenue", "income", "sales", "service income"], "4000", 0.60),  # generic → fab default

    # COGS
    (["material", "steel", "metal", "structural", "plate", "beam", "angle", "hss"], "5000", 0.80),
    (["direct labor", "shop labor", "field labor", "crew", "welder", "fitter", "ironworker"], "5100", 0.80),
    (["subcontract", "sub cost", "sub-contractor", "outside service"], "5200", 0.80),
    (["equipment rental", "crane rental", "tool rental", "equipment lease"], "5300", 0.80),
    (["consumable", "welding", "electrode", "wire", "gas", "flux", "grinding"], "5400", 0.80),
    (["cost of goods", "cogs", "cost of sales", "job cost"], "5000", 0.60),  # generic → materials

    # Overhead
    (["rent", "lease", "shop rent", "office rent", "building lease"], "6000", 0.80),
    (["insurance", "workers comp", "general liability", "auto insurance", "umbrella"], "6100", 0.80),
    (["utilit", "electric", "water", "gas bill", "phone", "internet", "cell"], "6200", 0.75),
    (["office", "admin", "supplies", "postage", "copier", "software", "subscription"], "6300", 0.70),
    (["vehicle", "fuel", "diesel", "gasoline", "mileage", "auto", "truck expense"], "6400", 0.75),
    (["professional", "legal", "accounting", "cpa", "attorney", "consulting", "audit"], "6500", 0.80),
]


# ══════════════════════════════════════════════════════════════════════
# PARSING
# ══════════════════════════════════════════════════════════════════════

def parse_trial_balance(text: str, source: str = "QBD") -> dict:
    """Parse a QuickBooks Desktop Trial Balance export (CSV text).

    Expected column patterns (flexible):
      - Account / Account Name / Name
      - Debit / Dr
      - Credit / Cr
      - Optional: Account Number / Acct No / No

    Returns dict with 'accounts' list and metadata.
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.29; disjoint shapes)
    lines = text.strip().split('\n')
    if not lines:
        return {"error": "Empty input", "accounts": []}

    # Try CSV parsing
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []

    # Normalize column names (QBD exports vary)
    col_map = {}
    for f in fieldnames:
        fl = f.lower().strip()
        if fl in ("account", "account name", "name", "account title"):
            col_map["account_name"] = f
        elif fl in ("debit", "dr", "debit amount"):
            col_map["debit"] = f
        elif fl in ("credit", "cr", "credit amount"):
            col_map["credit"] = f
        elif fl in ("account number", "acct no", "no", "acct #", "number"):
            col_map["account_number"] = f
        elif fl in ("type", "account type", "acct type"):
            col_map["account_type"] = f
        elif fl in ("balance", "net", "amount"):
            col_map["balance"] = f

    if "account_name" not in col_map:
        # Try to detect from first row
        return {"error": f"Could not find 'Account' column. Found columns: {fieldnames}",
                "accounts": [], "columns_found": fieldnames}

    accounts = []
    for row in reader:
        name = (row.get(col_map.get("account_name", ""), "") or "").strip()
        if not name:
            continue

        # Parse amounts (handle parentheses for negatives, commas, dollar signs)
        debit = _parse_amount(row.get(col_map.get("debit", ""), ""))
        credit = _parse_amount(row.get(col_map.get("credit", ""), ""))
        balance = _parse_amount(row.get(col_map.get("balance", ""), ""))
        acct_num = (row.get(col_map.get("account_number", ""), "") or "").strip()
        acct_type = (row.get(col_map.get("account_type", ""), "") or "").strip()

        # If only balance column (no separate debit/credit)
        if balance != 0 and debit == 0 and credit == 0:
            if balance > 0:
                debit = balance
            else:
                credit = abs(balance)

        # Skip zero-balance accounts and header/total rows
        if debit == 0 and credit == 0:
            continue
        if name.lower() in ("total", "grand total", "net income", ""):
            continue

        accounts.append({
            "qb_name": name,
            "qb_number": acct_num,
            "qb_type": acct_type,
            "debit": debit,
            "credit": credit,
            "net": round(debit - credit, 2),
        })

    return {
        "accounts": accounts,
        "count": len(accounts),
        "total_debit": round(sum(a["debit"] for a in accounts), 2),
        "total_credit": round(sum(a["credit"] for a in accounts), 2),
        "balanced": abs(sum(a["debit"] for a in accounts) - sum(a["credit"] for a in accounts)) < 0.02,
        "source": source,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "columns_detected": list(col_map.keys()),
    }


def _parse_amount(val: str) -> float:
    """Parse a dollar amount from QBD export. Handles: $1,234.56  (1,234.56)  -1234.56  empty"""
    if not val:
        return 0.0
    val = str(val).strip()
    if not val or val == "-":
        return 0.0
    # Handle parentheses (accounting negative)
    negative = False
    if val.startswith("(") and val.endswith(")"):
        negative = True
        val = val[1:-1]
    # Strip currency symbols and commas
    val = val.replace("$", "").replace(",", "").strip()
    try:
        result = float(val)
        return -result if negative else result
    except ValueError:
        return 0.0


# ══════════════════════════════════════════════════════════════════════
# ACCOUNT MAPPING
# ══════════════════════════════════════════════════════════════════════

def map_accounts(qb_accounts: list, custom_overrides: dict = None) -> dict:
    """Map QBD accounts to Your Company COA with confidence scoring.

    Args:
        qb_accounts: list of dicts from parse_trial_balance
        custom_overrides: dict of {qb_name: nano_code} for manual mappings

    Returns:
        dict with mapped/unmapped accounts and confidence breakdown.
    """
    overrides = custom_overrides or {}
    mapped = []
    unmapped = []
    high_conf = 0
    med_conf = 0
    low_conf = 0

    for acct in qb_accounts:
        qb_name = acct["qb_name"]
        qb_lower = qb_name.lower()

        # 1. Check manual override first (100% confidence)
        if qb_name in overrides:
            code = overrides[qb_name]
            nano = NANO_COA.get(code, {"name": code, "type": "Unknown"})
            mapped.append({
                **acct,
                "nano_code": code,
                "nano_name": nano["name"],
                "nano_type": nano["type"],
                "confidence": 1.0,
                "match_method": "manual_override",
                "status": "HIGH",
            })
            high_conf += 1
            continue

        # 2. Keyword matching
        best_code = None
        best_conf = 0.0
        best_method = ""

        for keywords, nano_code, base_conf in KEYWORD_MAP:
            for kw in keywords:
                if kw in qb_lower:
                    # Boost confidence for longer keyword matches
                    length_boost = min(len(kw) / max(len(qb_lower), 1), 0.15)
                    conf = min(base_conf + length_boost, 0.95)
                    if conf > best_conf:
                        best_conf = conf
                        best_code = nano_code
                        best_method = f"keyword:{kw}"

        # 3. Fuzzy string matching against COA names (if keyword didn't find a strong match)
        if best_conf < 0.7:
            for code, info in NANO_COA.items():
                ratio = SequenceMatcher(None, qb_lower, info["name"].lower()).ratio()
                if ratio > 0.6 and ratio > best_conf:
                    best_conf = ratio
                    best_code = code
                    best_method = f"fuzzy:{ratio:.2f}"

        # 4. Account type inference (lowest confidence)
        if best_conf < 0.5 and acct.get("qb_type"):
            qb_type = acct["qb_type"].lower()
            type_map = {
                "income": "4000", "revenue": "4000",
                "cost of goods": "5000", "cogs": "5000",
                "expense": "6300", "overhead": "6300",
                "asset": "1000", "liability": "2000",
                "equity": "3000",
            }
            for pattern, code in type_map.items():
                if pattern in qb_type:
                    if best_conf < 0.4:
                        best_conf = 0.4
                        best_code = code
                        best_method = f"type_infer:{qb_type}"
                    break

        if best_code:
            nano = NANO_COA.get(best_code, {"name": best_code, "type": "Unknown"})
            status = "HIGH" if best_conf >= 0.8 else "MEDIUM" if best_conf >= 0.5 else "LOW"
            entry = {
                **acct, "nano_code": best_code, "nano_name": nano["name"],
                "nano_type": nano["type"], "confidence": round(best_conf, 3),
                "match_method": best_method, "status": status,
            }
            mapped.append(entry)
            if status == "HIGH":
                high_conf += 1
            elif status == "MEDIUM":
                med_conf += 1
            else:
                low_conf += 1
        else:
            unmapped.append({**acct, "confidence": 0, "status": "UNMAPPED",
                            "match_method": "none"})

    return {
        "mapped": mapped,
        "unmapped": unmapped,
        "summary": {
            "total": len(qb_accounts),
            "mapped_count": len(mapped),
            "unmapped_count": len(unmapped),
            "high_confidence": high_conf,
            "medium_confidence": med_conf,
            "low_confidence": low_conf,
            "auto_populate_ready": high_conf,
            "needs_review": med_conf + low_conf,
        },
    }


# ══════════════════════════════════════════════════════════════════════
# COST TRACKER POPULATION
# ══════════════════════════════════════════════════════════════════════

def populate_cost_tracker(mapped_accounts: list, project_name: str = "QB Import") -> dict:
    """Auto-populate cost_tracker with QB actuals from mapped accounts.

    Only populates HIGH and MEDIUM confidence accounts.
    LOW confidence accounts are skipped (flagged for manual review).
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.14; disjoint shapes)
    try:
        from bridge.cost_tracker import add_cost_entry, add_project, get_all_projects
    except ImportError:
        return {"error": "cost_tracker module not available", "populated": 0}

    # Find or create the project
    existing = get_all_projects()
    project_id = None
    for p in existing:
        if p["name"].lower() == project_name.lower():
            project_id = p["id"]
            break

    if project_id is None:
        project_id = add_project(project_name, client="QB Import", notes="Auto-imported from QuickBooks Desktop Trial Balance")

    populated = 0
    skipped = 0
    entries = []

    # Category mapping: Nano COA type → cost_tracker category
    type_to_category = {
        "COGS": "direct_cost",
        "Expense": "overhead",
        "Income": "revenue",
        "Asset": "asset",
        "Liability": "liability",
    }

    for acct in mapped_accounts:
        if acct.get("status") == "LOW" or acct.get("confidence", 0) < 0.5:
            skipped += 1
            continue

        category = type_to_category.get(acct.get("nano_type", ""), "other")
        amount = abs(acct.get("net", 0))
        if amount == 0:
            continue

        description = f"QB Import: {acct['qb_name']} → {acct.get('nano_name', 'Unknown')}"
        add_cost_entry(project_id, category, amount, description)
        populated += 1
        entries.append({
            "qb_name": acct["qb_name"],
            "nano_code": acct.get("nano_code", ""),
            "amount": amount,
            "category": category,
            "confidence": acct.get("confidence", 0),
        })

    return {
        "project_id": project_id,
        "project_name": project_name,
        "populated": populated,
        "skipped_low_confidence": skipped,
        "entries": entries,
        "message": f"Imported {populated} entries into cost tracker (skipped {skipped} low-confidence accounts).",
    }


# ══════════════════════════════════════════════════════════════════════
# FULL PIPELINE: parse → map → populate
# ══════════════════════════════════════════════════════════════════════

def import_trial_balance(csv_text: str, project_name: str = "QB Import",
                         custom_overrides: dict = None, auto_populate: bool = True) -> dict:
    """Full pipeline: parse QB Trial Balance → map to Nano COA → populate cost tracker.

    Args:
        csv_text: Raw CSV text from QB Desktop Trial Balance export
        project_name: Project name for cost tracker entries
        custom_overrides: Manual account mappings {qb_name: nano_code}
        auto_populate: If True, auto-populate cost tracker with HIGH+MEDIUM matches

    Returns:
        Complete import result with parse, mapping, and population details.
    """
    # Step 1: Parse
    parsed = parse_trial_balance(csv_text)
    if parsed.get("error"):
        return {"error": parsed["error"], "step": "parse"}
    if not parsed["accounts"]:
        return {"error": "No accounts found in Trial Balance", "step": "parse"}

    # Step 2: Map
    mapping = map_accounts(parsed["accounts"], custom_overrides)

    # Step 3: Populate (if auto_populate)
    population = {"populated": 0, "message": "Auto-populate disabled"}
    if auto_populate and mapping["mapped"]:
        population = populate_cost_tracker(mapping["mapped"], project_name)

    return {
        "parse": {
            "account_count": parsed["count"],
            "total_debit": parsed["total_debit"],
            "total_credit": parsed["total_credit"],
            "balanced": parsed["balanced"],
        },
        "mapping": mapping["summary"],
        "population": population,
        "accounts": {
            "high_confidence": [a for a in mapping["mapped"] if a["status"] == "HIGH"],
            "needs_review": [a for a in mapping["mapped"] if a["status"] in ("MEDIUM", "LOW")],
            "unmapped": mapping["unmapped"],
        },
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════
# XLSX SUPPORT
# ══════════════════════════════════════════════════════════════════════

def parse_trial_balance_xlsx(file_path: str) -> dict:
    """Parse QB Trial Balance from XLSX file.
    Falls back to CSV if openpyxl not available."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        # Convert to CSV text for the standard parser
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(",".join(str(c) if c is not None else "" for c in row))
        wb.close()

        csv_text = "\n".join(rows)
        return parse_trial_balance(csv_text, source="QBD-XLSX")
    except ImportError:
        return {"error": "openpyxl not installed. Run: pip install openpyxl", "accounts": []}
    except Exception as e:
        return {"error": f"XLSX parse failed: {e}", "accounts": []}
