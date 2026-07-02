"""Monte Carlo risk scoring (Phase 11, build slot 11, v4.3.1).

Runs 1,000 simulations with randomized bid variables to produce
confidence intervals. Extends the deterministic margin_scenario() in
calculators.py with probabilistic output.

Output example: "Your bid of $485,000 has a 72% probability of covering
actual costs. At $520,000, confidence rises to 91%."

Tool stack: Python random module only. No numpy. 1,000 sims run in
under 1 second on the Mac Mini M4.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import math
import random
from typing import Optional

log = logging.getLogger(__name__)


# Default variable distributions (Houston market, May 2026 calibration).
# Joseph can override per call via the `overrides` dict.

DEFAULTS = {
    "material_cv": 0.15,       # coefficient of variation for $/ton
    "fab_hrs_mean": 11.0,      # hrs/ton baseline
    "fab_hrs_std": 2.2,        # std dev
    "erect_cv": 0.25,          # coefficient of variation for erect hrs
    "connection_cv": 0.30,     # connection hardware lognormal spread
    "overhead_low": 1.10,      # uniform distribution bounds
    "overhead_high": 1.20,
    "simulations": 1000,
    "seed": None,              # for reproducible tests
}


def _lognormal_sample(mean: float, cv: float, rng: random.Random) -> float:
    """Sample from a lognormal distribution with the given mean and
    coefficient of variation. Returns a positive float."""
    if mean <= 0 or cv <= 0:
        return max(mean, 0.0)
    sigma2 = math.log(1 + cv ** 2)
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - sigma2 / 2.0
    return rng.lognormvariate(mu, sigma)


def monte_carlo_bid_risk(
    direct_cost: float,
    material_tons: float,
    fab_hours: float,
    erect_hours: float,
    connection_cost: float = 0.0,
    bid_amount: float = 0.0,
    overrides: Optional[dict] = None,
) -> dict:
    """Run Monte Carlo simulation on bid variables.

    Args:
        direct_cost: Deterministic direct cost from bid_total().
        material_tons: Total project tonnage.
        fab_hours: Total fabrication hours.
        erect_hours: Total erection hours.
        connection_cost: Assembly hardware cost from Phase 10.
        bid_amount: The proposed bid price. If zero, uses direct_cost.
        overrides: Override any DEFAULTS key (e.g., simulations, seed).

    Returns:
        {
            "bid_amount": float,
            "simulations": int,
            "confidence_50": float (50th percentile cost),
            "confidence_75": float,
            "confidence_90": float,
            "confidence_95": float,
            "mean_cost": float,
            "std_dev": float,
            "min_cost": float,
            "max_cost": float,
            "prob_of_covering": float (% chance bid covers actual cost),
            "bid_drift_risk": "LOW"|"MODERATE"|"HIGH",
            "histogram": list[float] (20 bins for UI chart),
            "warnings": list[str],
        }
    """
    cfg = dict(DEFAULTS)
    if overrides:
        cfg.update(overrides)

    n_sims = int(cfg.get("simulations", 1000))
    seed = cfg.get("seed")
    rng = random.Random(seed)

    warnings: list[str] = []
    if direct_cost <= 0:
        warnings.append("direct_cost is zero or negative")
        return _empty_result(bid_amount, n_sims, warnings)

    bid = bid_amount if bid_amount > 0 else direct_cost

    # Base rates derived from inputs
    if material_tons > 0:
        material_rate = direct_cost * 0.35 / material_tons  # ~35% material
    else:
        material_rate = 0.0
        warnings.append("material_tons is zero; material variance disabled")

    shop_rate = 145.0  # $/hr from calibration
    fab_rate_per_ton = fab_hours / material_tons if material_tons > 0 else 11.0
    erect_rate_per_ton = erect_hours / material_tons if material_tons > 0 else 5.0

    results: list[float] = []
    for _ in range(n_sims):
        # Material cost
        mat_per_ton = rng.gauss(material_rate, material_rate * cfg["material_cv"])
        mat_per_ton = max(mat_per_ton, 0.0)
        sim_material = mat_per_ton * material_tons

        # Fab hours
        sim_fab_rate = rng.gauss(cfg["fab_hrs_mean"], cfg["fab_hrs_std"])
        sim_fab_rate = max(sim_fab_rate, 4.0)  # floor at 4 hrs/ton
        sim_fab_hrs = sim_fab_rate * material_tons
        sim_fab_cost = sim_fab_hrs * shop_rate

        # Erection hours
        sim_erect_rate = rng.gauss(
            erect_rate_per_ton, erect_rate_per_ton * cfg["erect_cv"])
        sim_erect_rate = max(sim_erect_rate, 2.0)
        sim_erect_hrs = sim_erect_rate * material_tons
        sim_erect_cost = sim_erect_hrs * shop_rate

        # Connection hardware
        if connection_cost > 0:
            sim_conn = _lognormal_sample(
                connection_cost, cfg["connection_cv"], rng)
        else:
            sim_conn = 0.0

        # Overhead multiplier
        sim_overhead = rng.uniform(
            cfg["overhead_low"], cfg["overhead_high"])

        sim_direct = sim_material + sim_fab_cost + sim_erect_cost + sim_conn
        sim_total = sim_direct * sim_overhead
        results.append(sim_total)

    results.sort()

    def _pct(p: float) -> float:
        idx = int(len(results) * p)
        idx = min(idx, len(results) - 1)
        return round(results[idx], 2)

    mean_cost = sum(results) / len(results)
    variance = sum((x - mean_cost) ** 2 for x in results) / len(results)
    std_dev = math.sqrt(variance)

    # Probability that the bid covers actual cost
    covered = sum(1 for r in results if r <= bid)
    prob_covering = round(covered / len(results) * 100.0, 1)

    # Risk classification
    if prob_covering >= 85:
        drift_risk = "LOW"
    elif prob_covering >= 65:
        drift_risk = "MODERATE"
    else:
        drift_risk = "HIGH"

    # Histogram: 20 bins for the GUI chart
    hist_min = results[0]
    hist_max = results[-1]
    hist_range = hist_max - hist_min
    n_bins = 20
    if hist_range <= 0:
        histogram = [float(len(results))] + [0.0] * (n_bins - 1)
    else:
        bin_width = hist_range / n_bins
        histogram = [0.0] * n_bins
        for r in results:
            b = int((r - hist_min) / bin_width)
            b = min(b, n_bins - 1)
            histogram[b] += 1.0

    return {
        "bid_amount": round(bid, 2),
        "simulations": n_sims,
        "confidence_50": _pct(0.50),
        "confidence_75": _pct(0.75),
        "confidence_90": _pct(0.90),
        "confidence_95": _pct(0.95),
        "mean_cost": round(mean_cost, 2),
        "std_dev": round(std_dev, 2),
        "min_cost": round(results[0], 2),
        "max_cost": round(results[-1], 2),
        "prob_of_covering": prob_covering,
        "bid_drift_risk": drift_risk,
        "histogram": histogram,
        "warnings": warnings,
    }


def _empty_result(bid: float, n_sims: int, warnings: list[str]) -> dict:
    return {
        "bid_amount": round(bid, 2),
        "simulations": n_sims,
        "confidence_50": 0.0,
        "confidence_75": 0.0,
        "confidence_90": 0.0,
        "confidence_95": 0.0,
        "mean_cost": 0.0,
        "std_dev": 0.0,
        "min_cost": 0.0,
        "max_cost": 0.0,
        "prob_of_covering": 0.0,
        "bid_drift_risk": "HIGH",
        "histogram": [0.0] * 20,
        "warnings": warnings,
    }
