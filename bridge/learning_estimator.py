"""
Your Company Virtual Office - Self-Learning Bid Estimator

After each project completes, actual cost/tons/hours feed back into
the pricing model. After 10 projects, estimates calibrate to Your Company's
actual shop performance instead of industry averages.

"Your W14 column erection runs 4.2 hr/ton, not the industry 5.5."
"""

import json, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "estimator_learning.db"
    return Path(__file__).resolve().parent.parent / "data" / "estimator_learning.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# Industry baselines (from handoff document §8)
INDUSTRY_BASELINES = {
    "fab_hours_per_ton": {"light": 25, "medium": 35, "heavy": 50, "default": 30},
    "erect_hours_per_ton": {"warehouse": 4.5, "commercial": 6.5, "industrial": 8, "default": 5.5},
    "fab_cost_per_ton": 3750,  # Q2 2026 locked rate
    "erect_cost_per_ton": 970,
    "weld_deposition_efficiency": {"SMAW": 0.60, "FCAW": 0.82, "GMAW": 0.92, "SAW": 0.97},
    "markup_typical": 0.30,  # 30% markup = 23% margin
    "ga_rate": 0.075,
}

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS actuals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL, project_type TEXT DEFAULT 'commercial',
            est_tons REAL, act_tons REAL, est_hours REAL, act_hours REAL,
            est_cost REAL, act_cost REAL, est_fab_hrs_per_ton REAL, act_fab_hrs_per_ton REAL,
            est_erect_hrs_per_ton REAL, act_erect_hrs_per_ton REAL,
            completed_at TEXT, logged_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT UNIQUE NOT NULL, industry_value REAL NOT NULL,
            yourco_value REAL, sample_count INTEGER DEFAULT 0,
            confidence TEXT DEFAULT 'low', updated_at TEXT NOT NULL
        );
    """)
    c.commit(); c.close()
_init()


def log_project_completion(project_name: str, project_type: str = "commercial",
                           est_tons: float = 0, act_tons: float = 0,
                           est_hours: float = 0, act_hours: float = 0,
                           est_cost: float = 0, act_cost: float = 0):
    """Log a completed project for learning."""
    now = datetime.now(timezone.utc).isoformat()
    fab_hpt_est = est_hours / est_tons if est_tons > 0 else 0
    fab_hpt_act = act_hours / act_tons if act_tons > 0 else 0

    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO actuals (project_name,project_type,est_tons,act_tons,est_hours,act_hours,est_cost,act_cost,est_fab_hrs_per_ton,act_fab_hrs_per_ton,logged_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (project_name, project_type, est_tons, act_tons, est_hours, act_hours, est_cost, act_cost, fab_hpt_est, fab_hpt_act, now))
        c.commit(); c.close()

    # Recalibrate
    _recalibrate()


def _recalibrate():
    """Recalculate Your Company-specific benchmarks from actuals."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM actuals ORDER BY logged_at DESC").fetchall()
        count = len(rows)

        if count >= 3:  # Minimum 3 projects for initial calibration
            # Average actual fab hours per ton
            fab_hpt = [r["act_fab_hrs_per_ton"] for r in rows if r["act_fab_hrs_per_ton"] and r["act_fab_hrs_per_ton"] > 0]
            if fab_hpt:
                avg = sum(fab_hpt) / len(fab_hpt)
                conf = "high" if len(fab_hpt) >= 10 else "medium" if len(fab_hpt) >= 5 else "low"
                c.execute(
                    "INSERT OR REPLACE INTO calibration (metric,industry_value,yourco_value,sample_count,confidence,updated_at) VALUES (?,?,?,?,?,?)",
                    ("fab_hours_per_ton", INDUSTRY_BASELINES["fab_hours_per_ton"]["default"], round(avg, 2), len(fab_hpt), conf, datetime.now(timezone.utc).isoformat()))

            # Cost per ton
            cost_pt = [(r["act_cost"] / r["act_tons"]) for r in rows if r["act_tons"] and r["act_tons"] > 0 and r["act_cost"]]
            if cost_pt:
                avg = sum(cost_pt) / len(cost_pt)
                conf = "high" if len(cost_pt) >= 10 else "medium" if len(cost_pt) >= 5 else "low"
                c.execute(
                    "INSERT OR REPLACE INTO calibration (metric,industry_value,yourco_value,sample_count,confidence,updated_at) VALUES (?,?,?,?,?,?)",
                    ("cost_per_ton", INDUSTRY_BASELINES["fab_cost_per_ton"], round(avg, 2), len(cost_pt), conf, datetime.now(timezone.utc).isoformat()))

            # Tonnage accuracy (est vs actual)
            ton_ratios = [(r["act_tons"] / r["est_tons"]) for r in rows if r["est_tons"] and r["est_tons"] > 0 and r["act_tons"]]
            if ton_ratios:
                avg = sum(ton_ratios) / len(ton_ratios)
                c.execute(
                    "INSERT OR REPLACE INTO calibration (metric,industry_value,yourco_value,sample_count,confidence,updated_at) VALUES (?,?,?,?,?,?)",
                    ("tonnage_accuracy_ratio", 1.0, round(avg, 3), len(ton_ratios), "medium" if len(ton_ratios) >= 5 else "low", datetime.now(timezone.utc).isoformat()))

        c.commit(); c.close()


def get_calibrated_rates() -> dict:
    """Get rates calibrated to Your Company actuals (or industry baselines if insufficient data)."""
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM calibration").fetchall()
        project_count = c.execute("SELECT COUNT(*) FROM actuals").fetchone()[0]
        c.close()

    calibrated = {}
    for r in rows:
        calibrated[r["metric"]] = {
            "industry": r["industry_value"],
            "yourco": r["yourco_value"],
            "using": "yourco" if r["yourco_value"] and r["sample_count"] >= 3 else "industry",
            "value": r["yourco_value"] if r["yourco_value"] and r["sample_count"] >= 3 else r["industry_value"],
            "sample_count": r["sample_count"],
            "confidence": r["confidence"],
        }

    return {
        "calibrated_rates": calibrated,
        "project_count": project_count,
        "calibration_status": "active" if project_count >= 3 else "collecting" if project_count > 0 else "no_data",
        "baselines": INDUSTRY_BASELINES,
    }


def estimate_project(tonnage: float, project_type: str = "commercial") -> dict:
    """Generate an estimate using calibrated rates (or baselines)."""
    cal = get_calibrated_rates()
    rates = cal.get("calibrated_rates", {})

    fab_hpt = rates.get("fab_hours_per_ton", {}).get("value", INDUSTRY_BASELINES["fab_hours_per_ton"]["default"])
    cost_pt = rates.get("cost_per_ton", {}).get("value", INDUSTRY_BASELINES["fab_cost_per_ton"])

    fab_hours = tonnage * fab_hpt
    fab_cost = tonnage * cost_pt
    erect_cost = tonnage * INDUSTRY_BASELINES["erect_cost_per_ton"]
    ga = (fab_cost + erect_cost) * INDUSTRY_BASELINES["ga_rate"]
    total = fab_cost + erect_cost + ga

    return {
        "tonnage": tonnage,
        "project_type": project_type,
        "fab_hours": round(fab_hours, 1),
        "fab_cost": round(fab_cost, 2),
        "erect_cost": round(erect_cost, 2),
        "ga_markup": round(ga, 2),
        "total_estimate": round(total, 2),
        "rates_source": cal.get("calibration_status", "no_data"),
        "fab_hrs_per_ton": fab_hpt,
        "note": "Calibrated to Your Company actuals" if cal.get("calibration_status") == "active" else "Using industry baselines - need 3+ completed projects to calibrate",
    }
