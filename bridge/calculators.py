"""
Your Company Virtual Office - Offline Calculators
Tier 1 Rule T1-1: No LLM does arithmetic in any bid number.

All numbers come from these deterministic calculators.
Zero AI tokens. Zero hallucination risk. Full audit trail.

Ported from: Ha-C-Repo/yourco-virtual-office (Linux build)
Source files: steel_weight.py, labor_cost.py, bid_total.py,
             hours_estimate.py, bolt_count.py, margin_scenario.py,
             paint_area.py, plate_weight.py, crew_size.py,
             schedule_pressure.py, weld_consumables.py, trir.py, days_until.py
"""

import csv
import json
import math
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# ── Data Loading ───────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Locked rates - matches Excel workbook Assumptions sheet exactly.
DEFAULT_RATES = {
    "shop_rate": 145.00, "eng_rate": 175.00, "overhead": 1.15,
    "fab_hrs_per_ton": 11.0, "erect_hrs_per_ton": 4.0, "default_eng_hours": 16,
    "steel_lb": 1.35, "plate_lb": 1.20, "galv_lb": 0.55, "paint_lb": 0.18,
    "freight_ton": 75.00, "default_margin": 0.18, "tx_tax": 0.0825,
    "plate_density_lb_per_sf_per_in": 40.8,
    "weld_wire_cost_per_lb": 1.50, "weld_gas_cost_per_cf": 0.05,
    "weld_wire_loss_factor": 1.05, "weld_deposition_lb_per_hr": 0.60,
    "weld_gas_flow_cfh": 35.0, "steel_density_lb_per_in3": 0.283,
    "paint_primer_sf": 0.75, "paint_2coat_sf": 2.00, "paint_intumescent_sf": 5.00,
    "shop_max_workers": 12, "standard_workday_hrs": 8.0, "workdays_per_week": 5,
}

COMPLEXITY = {
    "simple": 0.85, "standard": 1.00, "complex": 1.30,
    "heavy": 1.50, "retrofit": 1.65,
}

# Bolt catalog - Houston yard rates Apr 2026
BOLT_CATALOG = {
    ("3/4", "A325"): (1.95, 0.38), ("7/8", "A325"): (2.85, 0.58),
    ("1", "A325"): (4.10, 0.85), ("3/4", "A490"): (2.95, 0.38),
    ("7/8", "A490"): (4.25, 0.58), ("1", "A490"): (6.20, 0.85),
    ("3/4", "A307"): (1.10, 0.32), ("7/8", "A307"): (1.55, 0.50),
    ("1", "A307"): (2.40, 0.75), ("1/2", "A325"): (1.05, 0.12),
    ("5/8", "A325"): (1.45, 0.22), ("1-1/8", "A325"): (5.80, 1.15),
}

# W-shape surface area lookup (sf/ft by depth)
_W_SURFACE = {
    6: 2.0, 8: 2.5, 10: 3.2, 12: 3.8, 14: 4.5, 16: 4.8,
    18: 5.2, 21: 5.8, 24: 6.5, 27: 7.2, 30: 7.8, 33: 8.5, 36: 9.0,
}


def _load_rates() -> dict:
    rates = dict(DEFAULT_RATES)
    rp = _DATA_DIR / "rates.json"
    if rp.exists():
        try:
            rates.update(json.loads(rp.read_text()))
        except Exception:
            pass
    return rates


def _load_shapes() -> dict[str, float]:
    shapes = {}
    # v3.5.12 fix: use master CSV (2,299 shapes) instead of deleted legacy CSV
    candidates = [
        _DATA_DIR / "aisc_master.csv",            # primary: full v16.0
        _DATA_DIR / "legacy" / "aisc_shapes.csv",  # fallback: 224 shapes
    ]
    for sp in candidates:
        if sp.exists():
            with open(sp, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    key = row.get("shape") or row.get("AISC_Manual_Label", "")
                    wt = row.get("lb_per_ft") or row.get("W", "0")
                    if key.strip():
                        shapes[key.strip()] = float(wt)
            break
    if not shapes:
        import logging
        logging.getLogger("calc").warning("_load_shapes: no AISC CSV found, calculator will return 0 for all shapes")
    return shapes


_RATES = None
_SHAPES = None

def rates() -> dict:
    global _RATES
    if _RATES is None:
        _RATES = _load_rates()
    return _RATES

def shapes() -> dict:
    global _SHAPES
    if _SHAPES is None:
        _SHAPES = _load_shapes()
    return _SHAPES


# ── Audit Trail ────────────────────────────────────────────────────────

_AUDIT_LOG = _DATA_DIR / "calc_audit.jsonl"

def _audit(calc_name: str, inputs: dict, outputs: dict) -> None:
    """Append a calculation to the audit log. Fire-and-forget."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "calc": calc_name,
            "inputs": inputs,
            "outputs": {k: v for k, v in outputs.items() if k != "audit"},
        }
        with open(_AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 1: Steel Weight
# AISC shape × length × qty → lbs/tons
# ═══════════════════════════════════════════════════════════════════════

def steel_weight(items: list) -> dict:
    """Calculate steel weight from AISC shapes.

    items: list of (shape, length_ft, qty) tuples OR
           list of {"shape": str, "length_ft": float, "qty": int} dicts
    Returns: {total_lbs, tons, lines: [...]}
    """
    db = shapes()
    lines, total, unknown = [], 0.0, []
    for item in items:
        if isinstance(item, dict):
            shape = item.get("shape", "")
            length = item.get("length_ft", 0)
            qty = item.get("qty", 1)
        else:
            shape, length, qty = item
        if shape not in db:
            unknown.append(shape)
            continue
        lbs = db[shape] * length * qty
        total += lbs
        lines.append({"shape": shape, "length_ft": length, "qty": qty,
                       "lb_per_ft": db[shape], "lbs": round(lbs, 2)})

    result = {"total_lbs": round(total, 2), "tons": round(total / 2000, 4),
              "lines": lines, "line_count": len(lines)}
    if unknown:
        result["unknown_shapes"] = unknown
    _audit("steel_weight", {"items": [list(i) for i in items]}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 2: Hours Estimate
# Tonnage × complexity → fab + erection + engineering hours
# ═══════════════════════════════════════════════════════════════════════

def hours_estimate(tons: float, complexity: str = "standard",
                   eng_hours: float | None = None) -> dict:
    r = rates()
    factor = COMPLEXITY.get(complexity, 1.0)
    fab = tons * r["fab_hrs_per_ton"] * factor
    erect = tons * r["erect_hrs_per_ton"]
    eng = eng_hours if eng_hours is not None else r["default_eng_hours"]
    total = fab + erect + eng
    result = {
        "fab_hours": round(fab, 2), "erect_hours": round(erect, 2),
        "eng_hours": round(eng, 2), "total_hours": round(total, 2),
        "complexity": complexity, "factor": factor,
    }
    _audit("hours_estimate", {"tons": tons, "complexity": complexity}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 3: Labor Cost
# Hours × rates × overhead → burdened cost
# ═══════════════════════════════════════════════════════════════════════

def labor_cost(fab_hours: float = 0, erect_hours: float = 0,
               eng_hours: float = 0) -> dict:
    r = rates()
    fab = fab_hours * r["shop_rate"] * r["overhead"]
    erect = erect_hours * r["shop_rate"] * r["overhead"]
    eng = eng_hours * r["eng_rate"] * r["overhead"]
    total = fab + erect + eng
    total_hrs = fab_hours + erect_hours + eng_hours
    blended = total / total_hrs if total_hrs > 0 else 0
    result = {
        "fab_cost": round(fab, 2), "erect_cost": round(erect, 2),
        "eng_cost": round(eng, 2), "total_labor": round(total, 2),
        "total_burdened": round(total, 2),  # vj-fix: alias - callers use both names
        "total_hours": round(total_hrs, 2), "blended_rate": round(blended, 2),
    }
    _audit("labor_cost", {"fab_hours": fab_hours, "erect_hours": erect_hours,
                          "eng_hours": eng_hours}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 4: Bid Total
# Material + labor + coatings + freight + margin → final bid
# ═══════════════════════════════════════════════════════════════════════

def bid_total(steel_lbs: float, labor_cost_usd: float, tons: float,
              plate_lbs: float = 0, misc_material: float = 0,
              misc_subs: float = 0, coating: str = "shop_paint",
              margin: float | None = None, apply_tax: bool = False) -> dict:
    r = rates()
    m = margin if margin is not None else r["default_margin"]
    steel_mat = steel_lbs * r["steel_lb"]
    plate_mat = plate_lbs * r["plate_lb"]
    material = steel_mat + plate_mat + misc_material
    coat_rate = {"shop_paint": r["paint_lb"], "galvanizing": r["galv_lb"], "none": 0}.get(coating, 0)
    coatings = (steel_lbs + plate_lbs) * coat_rate
    freight = tons * r["freight_ton"]
    direct = material + labor_cost_usd + coatings + freight + misc_subs
    margin_amt = (direct / (1 - m)) - direct if m > 0 else 0
    bid = direct + margin_amt
    tax = bid * r["tx_tax"] if apply_tax else 0
    per_ton = bid / tons if tons > 0 else 0
    labor_pct = labor_cost_usd / bid if bid > 0 else 0
    mat_pct = material / bid if bid > 0 else 0

    # MC-02 / CALIBRATION-01: calibrate sanity gates by tonnage band.
    # Small jobs (<20 tons) carry proportionally more labor and less per-ton
    # cost than large structural jobs. Prior gates were tuned for 50-200 ton
    # mid-size work and flagged valid small-tonnage bids as failed.
    #
    # CALIBRATION-01 (May 2026): material_pct upper bound raised to 0.45 for
    # micro and small bands. Real Your Company small jobs (8-15T) run 36-44%
    # material - the old 35% ceiling produced false failures. Material_pct
    # is now a WARN, not a hard BLOCK, until actuals confirm the right
    # threshold. Recalibrate when 3+ real small-job actuals are available.
    if tons < 5:
        pt_lo, pt_hi = 3500, 12000
        lab_lo, lab_hi = 0.40, 0.75
        mat_lo, mat_hi = 0.10, 0.45   # widened: small repair/misc is material-heavy
        band = "micro (<5T)"
    elif tons < 20:
        pt_lo, pt_hi = 3500, 9000
        lab_lo, lab_hi = 0.35, 0.65
        mat_lo, mat_hi = 0.12, 0.45   # widened: real small jobs run 36-44% material
        band = "small (5-20T)"
    elif tons < 50:
        pt_lo, pt_hi = 4000, 8500
        lab_lo, lab_hi = 0.32, 0.50
        mat_lo, mat_hi = 0.20, 0.40
        band = "mid-small (20-50T)"
    else:
        pt_lo, pt_hi = 4500, 8000
        lab_lo, lab_hi = 0.30, 0.45
        mat_lo, mat_hi = 0.25, 0.40
        band = "standard (50T+)"

    pt_ok  = pt_lo  <= per_ton    <= pt_hi
    lab_ok = lab_lo <= labor_pct  <= lab_hi
    mat_ok = mat_lo <= mat_pct    <= mat_hi

    # CALIBRATION-01: material_pct is informational (WARN) for micro/small
    # bands until recalibrated with real actuals. Hard gates are $/ton and
    # labor_pct only - those are well-grounded in 9 years of shop data.
    mat_is_hard_gate = band not in ("micro (<5T)", "small (5-20T)")
    hard_pass = pt_ok and lab_ok and (mat_ok if mat_is_hard_gate else True)

    result = {
        "bid_total": round(bid, 2), "bid_with_tax": round(bid + tax, 2),
        "direct": round(direct, 2), "margin_amt": round(margin_amt, 2),
        "margin_pct": m, "tax": round(tax, 2),
        "breakdown": {
            "steel_material": round(steel_mat, 2), "plate_material": round(plate_mat, 2),
            "misc_material": round(misc_material, 2), "material_subtotal": round(material, 2),
            "labor": round(labor_cost_usd, 2), "coatings": round(coatings, 2),
            "freight": round(freight, 2), "misc_subs": round(misc_subs, 2),
        },
        "sanity": {
            "per_ton": round(per_ton, 2),
            "labor_pct": round(labor_pct, 4),
            "material_pct": round(mat_pct, 4),
            "per_ton_ok": pt_ok,
            "labor_pct_ok": lab_ok,
            "material_pct_ok": mat_ok,
            "all_pass": hard_pass,
            "material_pct_is_warn": not mat_is_hard_gate,
            "fail_reasons": [
                f"$/ton ${per_ton:,.0f} below ${pt_lo:,} floor for {band}"
                if not pt_ok and per_ton < pt_lo else
                f"$/ton ${per_ton:,.0f} above ${pt_hi:,} ceiling for {band}"
                if not pt_ok else None,
                f"labor {labor_pct*100:.1f}% outside {lab_lo*100:.0f}-{lab_hi*100:.0f}% band for {band}"
                if not lab_ok else None,
                (f"material {mat_pct*100:.1f}% outside {mat_lo*100:.0f}-{mat_hi*100:.0f}% band "
                 f"for {band} [WARN only - not enforced until actuals confirmed]")
                if not mat_ok and not mat_is_hard_gate else
                f"material {mat_pct*100:.1f}% outside {mat_lo*100:.0f}-{mat_hi*100:.0f}% band for {band}"
                if not mat_ok else None,
            ] if not hard_pass or not mat_ok else [],
            "tonnage_band": band,
            "thresholds_applied": {
                "per_ton": [pt_lo, pt_hi],
                "labor_pct": [lab_lo, lab_hi],
                "material_pct": [mat_lo, mat_hi],
            },
        },
    }
    _audit("bid_total", {"steel_lbs": steel_lbs, "tons": tons, "margin": m}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 5: Bolt Count + Cost
# ═══════════════════════════════════════════════════════════════════════

def bolt_count(connections: list[dict]) -> dict:
    """Count bolts and compute cost.

    VJ fix MC-NEW-03: accepts both canonical keys (size, grade) AND
    caller variants (diameter_in, bolt_type, diameter) so callers do
    not need to know the internal key naming.
    """
    total_bolts, total_cost, total_wt = 0, 0.0, 0.0
    lines = []
    for c in connections:
        # Normalize size: accept 'size', 'diameter', 'diameter_in'
        raw_size = (c.get("size") or c.get("diameter") or
                    c.get("diameter_in") or "")
        if raw_size:
            # Convert float like 0.75 -> "3/4", 0.875 -> "7/8", 1.0 -> "1"
            _frac_map = {0.5: "1/2", 0.625: "5/8", 0.75: "3/4",
                         0.875: "7/8", 1.0: "1", 1.125: "1-1/8"}
            try:
                size = _frac_map.get(round(float(raw_size), 3),
                                     str(raw_size))
            except (ValueError, TypeError):
                size = str(raw_size)
        else:
            size = ""
        # Normalize grade: accept 'grade', 'bolt_type'
        grade = str(c.get("grade") or c.get("bolt_type") or "A325").upper()
        count = int(c.get("count", 0))
        key = (size, grade)
        up, uw = BOLT_CATALOG.get(key, (0, 0))
        cost = up * count
        wt = uw * count
        total_bolts += count
        total_cost += cost
        total_wt += wt
        lines.append({"size": size, "grade": grade, "count": count,
                       "unit_price": up, "line_cost": round(cost, 2),
                       "weight_lb": round(wt, 2)})
    result = {"total_bolts": total_bolts, "total_cost": round(total_cost, 2),
              "total_weight_lb": round(total_wt, 2), "lines": lines}
    _audit("bolt_count", {"connection_count": len(connections)}, result)
    return result



# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 6: Margin Scenario
# Run multiple margin percentages to show bid range
# ═══════════════════════════════════════════════════════════════════════

def margin_scenario(direct_cost: float,
                    margins: list[float] | None = None) -> dict:
    if margins is None:
        margins = [0.15, 0.18, 0.20, 0.22, 0.25, 0.30]
    scenarios = []
    for m in margins:
        bid = direct_cost / (1 - m) if m < 1 else 0
        profit = bid - direct_cost
        scenarios.append({"margin_pct": m, "bid_total": round(bid, 2),
                          "profit": round(profit, 2)})
    result = {"direct_cost": round(direct_cost, 2), "scenarios": scenarios}
    _audit("margin_scenario", {"direct_cost": direct_cost}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 7: Crew Size + Schedule
# ═══════════════════════════════════════════════════════════════════════

def crew_size(total_hours: float, target_weeks: float) -> dict:
    r = rates()
    hrs_per_week = r["standard_workday_hrs"] * r["workdays_per_week"]
    crew = math.ceil(total_hours / (target_weeks * hrs_per_week))
    actual_weeks = total_hours / (crew * hrs_per_week) if crew > 0 else 0
    over_cap = crew > r["shop_max_workers"]
    result = {
        "crew_size": crew, "actual_weeks": round(actual_weeks, 1),
        "target_weeks": target_weeks, "over_capacity": over_cap,
        "max_workers": int(r["shop_max_workers"]),
    }
    _audit("crew_size", {"total_hours": total_hours, "target_weeks": target_weeks}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 8: Weld Consumables
# ═══════════════════════════════════════════════════════════════════════

def weld_consumables(leg_in: float, length_in: float, count: int = 1) -> dict:
    r = rates()
    area = 0.5 * leg_in * leg_in  # triangle cross-section
    vol = area * length_in * count
    wire_lbs = vol * r["steel_density_lb_per_in3"] * r["weld_wire_loss_factor"]
    weld_hrs = wire_lbs / r["weld_deposition_lb_per_hr"]
    gas_cf = weld_hrs * r["weld_gas_flow_cfh"]
    wire_cost = wire_lbs * r["weld_wire_cost_per_lb"]
    gas_cost = gas_cf * r["weld_gas_cost_per_cf"]
    result = {
        "wire_lbs": round(wire_lbs, 2), "weld_hours": round(weld_hrs, 2),
        "gas_cf": round(gas_cf, 1), "wire_cost": round(wire_cost, 2),
        "gas_cost": round(gas_cost, 2), "total_cost": round(wire_cost + gas_cost, 2),
    }
    _audit("weld_consumables", {"leg_in": leg_in, "length_in": length_in, "count": count}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 9: Plate Weight
# ═══════════════════════════════════════════════════════════════════════

def plate_weight(thickness_in: float, width_in: float, length_in: float,
                 qty: int = 1) -> dict:
    r = rates()
    area_sf = (width_in * length_in) / 144
    lbs = area_sf * thickness_in * r["plate_density_lb_per_sf_per_in"] * qty
    result = {"lbs": round(lbs, 2), "tons": round(lbs / 2000, 4),
              "area_sf": round(area_sf * qty, 2)}
    _audit("plate_weight", {"thickness": thickness_in, "width": width_in,
                            "length": length_in, "qty": qty}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 10: Paint Area
# ═══════════════════════════════════════════════════════════════════════

def paint_area(items: list[tuple[str, float, int]],
               coating: str = "primer") -> dict:
    total_sf = 0.0
    lines = []
    for shape, length, qty in items:
        depth = 12  # default
        name = shape.strip()
        if name.startswith("W"):
            try:
                depth = int(name.split("x")[0][1:])
            except ValueError:
                pass
        sf_ft = _W_SURFACE.get(depth, 3.8)
        sf = sf_ft * length * qty
        total_sf += sf
        lines.append({"shape": shape, "length_ft": length, "qty": qty,
                       "sf_per_ft": sf_ft, "total_sf": round(sf, 2)})
    r = rates()
    cost_key = {"primer": "paint_primer_sf", "2coat": "paint_2coat_sf",
                "intumescent": "paint_intumescent_sf"}.get(coating, "paint_primer_sf")
    cost = total_sf * r[cost_key]
    result = {"total_sf": round(total_sf, 2), "coating": coating,
              "cost_per_sf": r[cost_key], "total_cost": round(cost, 2), "lines": lines}
    _audit("paint_area", {"item_count": len(items), "coating": coating}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 11: TRIR (Total Recordable Incident Rate)
# ═══════════════════════════════════════════════════════════════════════

def trir(recordables: int, hours_worked: float) -> dict:
    rate = (recordables * 200000 / hours_worked) if hours_worked > 0 else 0
    result = {"trir": round(rate, 2), "recordables": recordables,
              "hours_worked": round(hours_worked, 0),
              "industry_avg": 2.8, "below_avg": rate < 2.8}
    _audit("trir", {"recordables": recordables, "hours_worked": hours_worked}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 12: Days Until Deadline
# ═══════════════════════════════════════════════════════════════════════

def days_until(target_date: str, name: str = "") -> dict:
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"Bad date format: {target_date}. Use YYYY-MM-DD."}
    today = date.today()
    delta = (target - today).days
    severity = "OVERDUE" if delta < 0 else "TODAY" if delta == 0 else \
               "TOMORROW" if delta == 1 else "THIS WEEK" if delta <= 5 else \
               "NEXT WEEK" if delta <= 12 else "SAFE"
    result = {"days": delta, "severity": severity, "target": target_date,
              "name": name, "today": str(today)}
    _audit("days_until", {"target": target_date, "name": name}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# CALCULATOR 13: Schedule Pressure Assessment
# ═══════════════════════════════════════════════════════════════════════

def schedule_pressure(tons: float, deadline_date: str,
                      complexity: str = "standard") -> dict:
    hrs = hours_estimate(tons, complexity)
    cs = crew_size(hrs["total_hours"], 4)  # default 4-week target
    du = days_until(deadline_date, "project deadline")
    if "error" in du:
        return du
    weeks_available = max(du["days"] / 7, 0.1)
    actual_crew = crew_size(hrs["total_hours"], weeks_available)
    r = rates()
    pressure = "RED" if actual_crew["crew_size"] > r["shop_max_workers"] else \
               "YELLOW" if actual_crew["crew_size"] > r["shop_max_workers"] * 0.75 else "GREEN"
    result = {
        "pressure": pressure, "hours_needed": hrs["total_hours"],
        "weeks_available": round(weeks_available, 1),
        "crew_needed": actual_crew["crew_size"],
        "max_capacity": int(r["shop_max_workers"]),
        "deadline": deadline_date, "days_left": du["days"],
    }
    _audit("schedule_pressure", {"tons": tons, "deadline": deadline_date}, result)
    return result


# ═══════════════════════════════════════════════════════════════════════
# QUICK CALC: Single-line calculator for the AI to call
# ═══════════════════════════════════════════════════════════════════════

CALC_REGISTRY = {
    "steel_weight": {"fn": steel_weight, "desc": "AISC shape weight: items=[(shape,length_ft,qty)]"},
    "hours_estimate": {"fn": hours_estimate, "desc": "Project hours: tons, complexity, eng_hours"},
    "labor_cost": {"fn": labor_cost, "desc": "Burdened labor: fab_hours, erect_hours, eng_hours"},
    "bid_total": {"fn": bid_total, "desc": "Final bid: steel_lbs, labor_cost_usd, tons, ..."},
    "bolt_count": {"fn": bolt_count, "desc": "Bolt inventory: connections=[{size,grade,count}]"},
    "margin_scenario": {"fn": margin_scenario, "desc": "Margin scenarios: direct_cost"},
    "crew_size": {"fn": crew_size, "desc": "Crew sizing: total_hours, target_weeks"},
    "weld_consumables": {"fn": weld_consumables, "desc": "Weld wire/gas: leg_in, length_in, count"},
    "plate_weight": {"fn": plate_weight, "desc": "Plate weight: thickness_in, width_in, length_in, qty"},
    "paint_area": {"fn": paint_area, "desc": "Paint area: items=[(shape,length_ft,qty)], coating"},
    "trir": {"fn": trir, "desc": "TRIR: recordables, hours_worked"},
    "days_until": {"fn": days_until, "desc": "Deadline: target_date (YYYY-MM-DD), name"},
    "schedule_pressure": {"fn": schedule_pressure, "desc": "Schedule: tons, deadline_date, complexity"},
}


def list_calculators() -> list[dict]:
    """Return list of available calculators for the AI to reference."""
    return [{"name": k, "description": v["desc"]} for k, v in CALC_REGISTRY.items()]


def run_calc(name: str, **kwargs) -> dict:
    """Run a calculator by name. Returns the result dict."""
    if name not in CALC_REGISTRY:
        return {"error": f"Unknown calculator: {name}. Available: {list(CALC_REGISTRY.keys())}"}
    try:
        return CALC_REGISTRY[name]["fn"](**kwargs)
    except Exception as e:
        return {"error": f"Calculator {name} failed: {e}"}
