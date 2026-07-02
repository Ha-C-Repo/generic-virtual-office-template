"""
Your Company - Q2 2026 Calibration Data Loader

Loads data/calibration_2026Q2.json and exposes typed accessors for
every module that needs Houston-MSA market data. Single source of
truth - never duplicate values in module constants.

Sources:
- SAM.gov Wage Determination TX20260025 (May 2026)
- NCCI Texas Workers Comp Base Rates (Jan 2026)
- SteelBenchmarker / Argus / Nucor (Q2 2026 90-day avg)
- AWS D1.1:2025 Vendor Pricing (Houston Supply)
- City/County Fee Schedules (May 2026)
- BLS / EIA / GHBA / Baker Hughes (May 2026)

Usage:
    from bridge.calibration_2026q2 import (
        get_wage_rate, get_steel_price, get_refinery_data,
        get_connection_cost, get_macro_indicators
    )
    rate = get_wage_rate("Welder (CWI-supervised) - Journeyman")
    price = get_steel_price("Wide-flange shapes (W-sections, A992)", tier="typical")
"""
import json
from functools import lru_cache
from pathlib import Path


_CALIB_PATH = Path(__file__).resolve().parent.parent / "data" / "calibration_2026Q2.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    """Load and cache the calibration JSON. One read per process lifetime."""
    if not _CALIB_PATH.exists():
        return {}
    try:
        return json.loads(_CALIB_PATH.read_text())
    except Exception:
        return {}


def get_metadata() -> dict:
    """Return the calibration metadata block (version, issued date, etc)."""
    return _load().get("_metadata", {})


def is_loaded() -> bool:
    """Returns True if calibration JSON loaded successfully."""
    return bool(_load())


# ── Wage rates ─────────────────────────────────────────────────────────────

def get_all_wages() -> list[dict]:
    """Return all 10 trade wage entries from SAM.gov WD-2026."""
    return _load().get("wage_rates_sam_gov_wd_2026", {}).get("trades", [])


def get_wage_rate(trade: str, tier: str = "fully_burdened_rate") -> float | None:
    """Look up a fully-burdened hourly rate for a trade.

    Args:
        trade: full trade name (e.g. "Welder (CWI-supervised) - Journeyman")
        tier:  "base_wage" | "fringe" | "fully_burdened_rate" (default)
    """
    for t in get_all_wages():
        if t.get("trade") == trade:
            return t.get(tier)
    return None


# ── NCCI Workers Comp ──────────────────────────────────────────────────────

def get_wc_rate(ncci_code: int, exp_mod: str = "typical") -> dict | None:
    """Return WC rate per $100 of payroll for an NCCI class code.

    Args:
        ncci_code: 4-digit NCCI code (e.g. 5040 = Iron/Steel Erection frame)
        exp_mod:   "low" | "typical" (default) | "high"

    Returns dict with rate_per_100, exp_mod_value, description.
    """
    for r in _load().get("ncci_workers_comp_tx_2026", {}).get("rates", []):
        if r.get("code") == ncci_code:
            mod = r.get("exp_mod", {}).get(exp_mod, 1.0)
            return {
                "code":              ncci_code,
                "description":       r.get("description"),
                "rate_per_100":      r.get("rate_per_100"),
                "exp_mod":           mod,
                "effective_rate":    r.get("rate_per_100") * mod,
            }
    return None


# ── Steel pricing ──────────────────────────────────────────────────────────

def get_steel_price(grade: str, tier: str = "typical") -> float | None:
    """Return $/ton for a steel grade.

    Args:
        grade: full grade name (e.g. "Wide-flange shapes (W-sections, A992)")
        tier:  "low" | "typical" (default) | "high"
    """
    for g in _load().get("steel_pricing_2026q2", {}).get("grades", []):
        if g.get("grade") == grade:
            return g.get(tier)
    return None


def get_all_steel_grades() -> list[dict]:
    """Return all steel grade pricing entries."""
    return _load().get("steel_pricing_2026q2", {}).get("grades", [])


# ── Welding consumables ────────────────────────────────────────────────────

def get_consumable(consumable_type: str) -> dict | None:
    """Look up a welding consumable by type (e.g. "E70T-1C flux-cored (FCAW)")."""
    for c in _load().get("weld_consumables_aws_d11_2025", {}).get("consumables", []):
        if consumable_type.lower() in c.get("type", "").lower():
            return c
    return None


def get_all_consumables() -> list[dict]:
    """Return all 5 welding consumable entries."""
    return _load().get("weld_consumables_aws_d11_2025", {}).get("consumables", [])


# ── Permit fees ────────────────────────────────────────────────────────────

def get_permit_fee(jurisdiction: str, project_value: float = 0) -> dict | None:
    """Compute a permit fee for a jurisdiction at a given project value.

    Returns {jurisdiction, fee_type, base, variable, total, link}.
    """
    for j in _load().get("permit_fees_houston_msa_2026", {}).get("jurisdictions", []):
        if jurisdiction.lower() in j.get("jurisdiction", "").lower():
            base = j.get("base", 0)
            rate = j.get("per_value_rate", 0)
            variable = project_value * rate
            return {
                "jurisdiction": j.get("jurisdiction"),
                "fee_type":     j.get("fee_type"),
                "base":         base,
                "variable":     variable,
                "total":        base + variable,
                "link":         j.get("link"),
            }
    return None


def get_all_jurisdictions() -> list[dict]:
    """Return all 7 Houston-area permit jurisdictions."""
    return _load().get("permit_fees_houston_msa_2026", {}).get("jurisdictions", [])


# ── Refineries ─────────────────────────────────────────────────────────────

def get_refinery_data(refinery_name: str) -> dict | None:
    """Look up a refinery's TA schedule and contact lead time."""
    for r in _load().get("houston_refineries_2026", {}).get("refineries", []):
        if r.get("name") == refinery_name:
            return r
    return None


def get_all_refineries() -> list[dict]:
    """Return all 9 Houston-area refineries with TA schedules."""
    return _load().get("houston_refineries_2026", {}).get("refineries", [])


# ── Connection costs ───────────────────────────────────────────────────────

def get_connection_cost(connection_type: str, tier: str = "typical_cost") -> dict | None:
    """Return cost for a connection type.

    Args:
        connection_type: e.g. "Welded moment connection (CJP)"
        tier:            "low_cost" | "typical_cost" (default) | "high_cost"
    """
    for c in _load().get("connection_costs_2026q2", {}).get("connections", []):
        if connection_type.lower() in c.get("type", "").lower():
            return {
                "type":  c.get("type"),
                "cost":  c.get(tier),
                "units": c.get("units"),
                "notes": c.get("notes"),
            }
    return None


def get_all_connection_types() -> list[dict]:
    """Return all 10 connection types with full cost ranges."""
    return _load().get("connection_costs_2026q2", {}).get("connections", [])


# ── Insurance ──────────────────────────────────────────────────────────────

def get_insurance_block() -> dict:
    """Return the full TX mid-market insurance block."""
    return _load().get("insurance_tx_mid_market_2026", {})


# ── Vendor compliance portals ──────────────────────────────────────────────

def get_compliance_portal(portal_name: str) -> dict | None:
    """Look up a compliance portal (ISN, Avetta, PEC, Veriforce, DISA, NCMS)."""
    for p in _load().get("vendor_compliance_portals_2026", {}).get("portals", []):
        if portal_name.lower() in p.get("name", "").lower():
            return p
    return None


def get_all_portals() -> list[dict]:
    """Return all 6 vendor compliance portals."""
    return _load().get("vendor_compliance_portals_2026", {}).get("portals", [])


# ── Macro indicators ───────────────────────────────────────────────────────

def get_macro_indicators() -> list[dict]:
    """Return all 7 Houston macro indicators (BLS/EIA/GHBA/Baker Hughes)."""
    return _load().get("houston_macro_indicators_2026q2", {}).get("indicators", [])


def get_macro_indicator(name: str) -> dict | None:
    """Look up one macro indicator by name."""
    for ind in get_macro_indicators():
        if name.lower() in ind.get("indicator", "").lower():
            return ind
    return None


# ── NDT / Inspection rates ─────────────────────────────────────────────────

def get_ndt_rate(rate_type: str) -> float | None:
    """Look up an NDT rate (e.g. "CWI_hourly", "UT_per_joint")."""
    rates = _load().get("ndt_inspection_rates_houston_2026", {}).get("rates", {})
    return rates.get(rate_type)


def get_all_ndt_rates() -> dict:
    """Return the full NDT rate block."""
    return _load().get("ndt_inspection_rates_houston_2026", {}).get("rates", {})


# ── Detailing rates ────────────────────────────────────────────────────────

def get_detailing_rate(location: str = "houston", rate_type: str = "per_ton_rate") -> float | None:
    """Get detailing rate.

    Args:
        location:  "houston" or "offshore"
        rate_type: "per_ton_rate" or "hourly_rate"
    """
    block = _load().get("detailing_market_houston_2026", {})
    return block.get(location, {}).get(rate_type)


# ── AISC top shapes ────────────────────────────────────────────────────────

def get_top_shapes() -> list[dict]:
    """Return the top 13 most-used AISC shapes for Houston commercial/industrial."""
    return _load().get("aisc_top_shapes_houston_2026", {}).get("shapes", [])


# ── Health check ───────────────────────────────────────────────────────────

def calibration_summary() -> dict:
    """Quick summary of what's loaded - used by self-test and morning brief."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.06; disjoint shapes)
    d = _load()
    if not d:
        return {"loaded": False, "error": "Calibration JSON not found"}
    return {
        "loaded":             True,
        "version":            d.get("_metadata", {}).get("version"),
        "issued":             d.get("_metadata", {}).get("issued"),
        "valid_through":      d.get("_metadata", {}).get("valid_through"),
        "wage_trades":        len(get_all_wages()),
        "wc_codes":           len(d.get("ncci_workers_comp_tx_2026", {}).get("rates", [])),
        "steel_grades":       len(get_all_steel_grades()),
        "consumables":        len(get_all_consumables()),
        "jurisdictions":      len(get_all_jurisdictions()),
        "refineries":         len(get_all_refineries()),
        "connection_types":   len(get_all_connection_types()),
        "compliance_portals": len(get_all_portals()),
        "macro_indicators":   len(get_macro_indicators()),
        "ndt_rates":          len(get_all_ndt_rates()),
        "top_shapes":         len(get_top_shapes()),
    }
