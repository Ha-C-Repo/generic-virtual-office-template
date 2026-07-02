"""
FRED Steel Pricing - Data Fabric Layer

Free real-time PPI data from the St. Louis Fed (FRED API).
Series IDs from handoff document - specific to structural steel fabrication.

Requires: FRED_API_KEY (free from https://fred.stlouisfed.org/docs/api/api_key.html)
Package: pip install fredapi
"""
import os, json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CACHE = Path(__file__).resolve().parent.parent / "data" / "fred_cache.json"

# Series IDs that matter for a Houston structural shop (per handoff doc)
SERIES = {
    "WPU101704":        "PPI Hot Rolled Steel Bars, Plates & Structural Shapes (NSA)",
    "WPS101704":        "PPI Hot Rolled Steel (Seasonally Adjusted)",
    "WPU10170406":      "PPI Alloy Hot-Rolled Bars/Plates/Structural",
    "PCU33231233231212": "PPI Fabricated Structural Steel - Commercial/Residential",
    "PCU33231233231211": "PPI Fabricated Structural Steel - Industrial/Bar Joists",
    "PCU33123312":       "PPI Steel Product Mfg from Purchased Steel",
}

def _get_key():
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        try:
            from bridge.keyvault import load_keys
            keys = load_keys()
            key = keys.get("FRED_API_KEY", "")
        except Exception:pass
    return key

def _load_cache():
    try:
        if _CACHE.exists():
            return json.loads(_CACHE.read_text())
    except Exception:pass
    return {}

def _save_cache(data):
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(data, indent=2, default=str))

def fetch_series(series_id, lookback_months=12):
    """Fetch a single FRED series. Returns list of {date, value}."""
    key = _get_key()
    if not key:
        return {"error": "FRED_API_KEY not set. Set env var: set FRED_API_KEY=your_key  (free at fred.stlouisfed.org/docs/api/api_key.html)"}
    try:
        from fredapi import Fred
        fred = Fred(api_key=key)
        start = (datetime.now() - timedelta(days=lookback_months * 30)).strftime("%Y-%m-%d")  # vj: duration-math
        data = fred.get_series(series_id, observation_start=start)
        points = [{"date": str(d.date()), "value": round(float(v), 2)}
                  for d, v in data.items() if not __import__('math').isnan(v)]
        return {"series_id": series_id, "name": SERIES.get(series_id, series_id),
                "points": points, "latest": points[-1] if points else None,
                "source": "FRED", "fetched_at": datetime.now(timezone.utc).isoformat()}
    except ImportError:
        return {"error": "fredapi not installed. Run: pip install fredapi"}
    except Exception as e:
        return {"error": str(e)[:200]}

def fetch_all(lookback_months=6):
    """Fetch all steel-relevant series and cache locally."""
    results = {}
    for sid, name in SERIES.items():
        results[sid] = fetch_series(sid, lookback_months)
    _save_cache({"fetched_at": datetime.now(timezone.utc).isoformat(), "series": results})
    return results

def get_latest_prices():
    """Get just the latest value for each series (for bid template injection)."""
    cache = _load_cache()
    if cache.get("series"):
        latest = {}
        for sid, data in cache["series"].items():
            if isinstance(data, dict) and data.get("latest"):
                latest[sid] = {
                    "name": SERIES.get(sid, sid),
                    "value": data["latest"]["value"],
                    "date": data["latest"]["date"],
                }
        if latest:
            return {"prices": latest, "cache_age": cache.get("fetched_at"),
                    "source": "FRED (cached)"}
    return {"prices": {}, "note": "No cached data. Call fetch_all() first."}

def week_over_week_alert(threshold_pct=3.0):
    """Check if any series moved more than threshold% week-over-week."""
    cache = _load_cache()
    alerts = []
    for sid, data in cache.get("series", {}).items():
        if isinstance(data, dict) and not data.get("error"):
            pts = data.get("points", [])
            if len(pts) >= 2:
                prev, curr = pts[-2]["value"], pts[-1]["value"]
                if prev > 0:
                    pct = ((curr - prev) / prev) * 100
                    if abs(pct) >= threshold_pct:
                        alerts.append({
                            "series": sid, "name": SERIES.get(sid, sid),
                            "prev": prev, "curr": curr,
                            "change_pct": round(pct, 2),
                            "direction": "UP" if pct > 0 else "DOWN",
                        })
    return alerts

def for_morning_briefing():
    """Compact summary for SMS morning briefing."""
    prices = get_latest_prices()
    if not prices.get("prices"):
        return "Steel PPI: no FRED data cached."
    lines = ["Steel PPI (FRED):"]
    for sid, info in list(prices["prices"].items())[:3]:
        lines.append(f"  {info['name'][:40]}: {info['value']} ({info['date']})")
    alerts = week_over_week_alert()
    if alerts:
        lines.append("⚠ WoW alerts:")
        for a in alerts:
            lines.append(f"  {a['name'][:30]}: {a['change_pct']:+.1f}%")
    return "\n".join(lines)
