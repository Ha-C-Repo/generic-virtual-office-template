"""
Productivity KPIs - Domain Engine

Industry-anchored benchmarks computed in real time against actuals.
All numbers from handoff document's published sources.

Fabrication: 25-60 sh-hrs/ton (light/medium/heavy), 30-35% gross margin upper echelon
Erection: 4-6 hr/ton warehouse, 5-8 hr/ton multi-story commercial
Markup vs margin: 33% markup = 25% margin; 50% markup = 33% margin
Industry: $65.5B (2025), 3,187 firms, 4-10% operating profit

CRITICAL: Always show markup AND margin on same screen.
"Shops that conflate the two routinely under-bid." - handoff doc
"""

# Industry benchmarks (from handoff doc sources: FMA, IBISWorld, Construction Physics)
BENCHMARKS = {
    "fab_light": {"label": "Fabrication - Light structural", "sh_hrs_per_ton": 25, "range": "20-30"},
    "fab_medium": {"label": "Fabrication - Medium structural", "sh_hrs_per_ton": 35, "range": "30-45"},
    "fab_heavy": {"label": "Fabrication - Heavy/complex", "sh_hrs_per_ton": 55, "range": "45-65+"},
    "erect_warehouse": {"label": "Erection - Warehouse/light", "man_hrs_per_ton": 4.5, "range": "4-6"},
    "erect_commercial": {"label": "Erection - Multi-story commercial", "man_hrs_per_ton": 6.5, "range": "5-8"},
    "erect_industrial": {"label": "Erection - Industrial/refinery", "man_hrs_per_ton": 9, "range": "7-12"},
    "tons_per_day_crane": {"label": "Erection tons/day (1 crane + crew)", "value": 50, "note": "Modern commercial, normalized for connection complexity"},
}

INDUSTRY_FINANCIALS = {
    "us_market_size_2025": "$65.5B",
    "firm_count": 3187,
    "cagr_2020_2025": "0.6%",
    "operating_profit_range": "4-10%",
    "operating_profit_trough_2020": "4%",
    "gross_margin_upper_echelon": "30-35%",
    "typical_erection_markup": "25-40% over direct cost",
    "custom_fab_net_avg": "4%",
}


def markup_to_margin(markup_pct):
    """Convert markup percentage to margin percentage.
    markup = (price - cost) / cost × 100
    margin = (price - cost) / price × 100
    """
    return round((markup_pct / (100 + markup_pct)) * 100, 2)


def margin_to_markup(margin_pct):
    """Convert margin percentage to markup percentage."""
    if margin_pct >= 100:
        return None
    return round((margin_pct / (100 - margin_pct)) * 100, 2)


def markup_margin_table():
    """Generate the 'always show both' table per handoff doc requirement."""
    rows = []
    for markup in [10, 15, 20, 25, 30, 33, 40, 50, 60, 75, 100]:
        margin = markup_to_margin(markup)
        rows.append({
            "markup_pct": markup,
            "margin_pct": margin,
            "example": f"${1000 * (1 + markup/100):,.0f} sell on $1,000 cost",
        })
    return rows


def calculate_fab_productivity(actual_hours, tons, complexity="medium"):
    """Compare actual shop hours to benchmark.
    Returns {actual_rate, benchmark, variance_pct, rating}."""
    key = f"fab_{complexity}"
    bench = BENCHMARKS.get(key, BENCHMARKS["fab_medium"])
    benchmark = bench["sh_hrs_per_ton"]
    actual = actual_hours / max(tons, 0.1)
    variance = ((actual - benchmark) / benchmark) * 100
    if variance <= -10:
        rating = "EXCELLENT"
    elif variance <= 5:
        rating = "ON_TARGET"
    elif variance <= 20:
        rating = "OVER"
    else:
        rating = "CRITICAL"
    return {
        "actual_sh_hrs_per_ton": round(actual, 2),
        "benchmark": benchmark,
        "benchmark_range": bench["range"],
        "variance_pct": round(variance, 1),
        "rating": rating,
        "total_hours": actual_hours,
        "tons": tons,
        "complexity": complexity,
    }


def calculate_erect_productivity(actual_hours, tons, project_type="warehouse"):
    """Compare actual erection hours to benchmark."""
    key = f"erect_{project_type}"
    bench = BENCHMARKS.get(key, BENCHMARKS["erect_warehouse"])
    benchmark = bench["man_hrs_per_ton"]
    actual = actual_hours / max(tons, 0.1)
    variance = ((actual - benchmark) / benchmark) * 100
    if variance <= -10:
        rating = "EXCELLENT"
    elif variance <= 10:
        rating = "ON_TARGET"
    elif variance <= 25:
        rating = "OVER"
    else:
        rating = "CRITICAL"
    return {
        "actual_man_hrs_per_ton": round(actual, 2),
        "benchmark": benchmark,
        "benchmark_range": bench["range"],
        "variance_pct": round(variance, 1),
        "rating": rating,
    }


def schedule_check(tons, ship_date_iso, shop_capacity_hrs_per_ton=30):
    """Check if projected backlog exceeds shop capacity.
    Per handoff: 25-30 sh-hrs/ton for light-medium structural."""
    from datetime import date, timedelta
    ship = date.fromisoformat(ship_date_iso)
    today = date.today()
    available_days = max(1, (ship - today).days)
    # 8 hrs/day, 5 days/week → ~5.7 productive days/week
    productive_days = available_days * (5/7)
    available_hours = productive_days * 8
    required_hours = tons * shop_capacity_hrs_per_ton
    feasible = available_hours >= required_hours
    return {
        "tons": tons,
        "ship_date": ship_date_iso,
        "calendar_days": available_days,
        "productive_days": round(productive_days, 1),
        "available_shop_hours": round(available_hours, 0),
        "required_shop_hours": round(required_hours, 0),
        "utilization_pct": round(required_hours * 100 / max(available_hours, 1), 1),
        "feasible": feasible,
        "warning": None if feasible else f"Need {required_hours:.0f} hrs but only {available_hours:.0f} available. Requires overtime or outsource.",
    }


def project_dashboard(tons, actual_hours_fab=0, actual_hours_erect=0,
                       direct_cost=0, sell_price=0, project_type="warehouse"):
    """Complete KPI dashboard for one project."""
    result = {"tons": tons}
    if actual_hours_fab > 0:
        result["fabrication"] = calculate_fab_productivity(actual_hours_fab, tons)
    if actual_hours_erect > 0:
        result["erection"] = calculate_erect_productivity(actual_hours_erect, tons, project_type)
    if direct_cost > 0 and sell_price > 0:
        markup = ((sell_price - direct_cost) / direct_cost) * 100
        margin = ((sell_price - direct_cost) / sell_price) * 100
        result["financials"] = {
            "direct_cost": direct_cost,
            "sell_price": sell_price,
            "gross_profit": round(sell_price - direct_cost, 2),
            "markup_pct": round(markup, 2),
            "margin_pct": round(margin, 2),
            "vs_industry_avg": "ABOVE" if margin > 10 else "AT" if margin >= 4 else "BELOW",
            "industry_avg_net": "4-10%",
        }
    return result
