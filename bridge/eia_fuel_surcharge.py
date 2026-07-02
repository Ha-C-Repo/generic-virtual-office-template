"""
EIA Fuel Surcharge - Data Fabric Layer

Free diesel price from U.S. Energy Information Administration.
Auto-updates freight surcharge in bid templates.
API: https://api.eia.gov/v2/petroleum/pri/gnd/
No API key required for basic access.
"""
import json, os
from datetime import datetime, timezone
from pathlib import Path

_CACHE = Path(__file__).resolve().parent.parent / "data" / "eia_cache.json"
EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"

def _get_key():
    return os.environ.get("EIA_API_KEY", "")

def fetch_diesel_price(region="PADD3"):
    """Fetch latest ULSD/diesel price. PADD3 = Gulf Coast (Houston).
    Returns {price_per_gallon, date, region}."""
    try:
        import httpx
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[duoarea][]": region,
            "facets[product][]": "EPD2DXL0",  # Ultra-Low Sulfur Diesel
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 4,
        }
        key = _get_key()
        if key:
            params["api_key"] = key
        resp = httpx.get(EIA_BASE, params=params, timeout=15)
        data = resp.json()
        rows = data.get("response", {}).get("data", [])
        if rows:
            latest = rows[0]
            result = {
                "price_per_gallon": float(latest.get("value", 0)),
                "date": latest.get("period", ""),
                "region": region,
                "product": "ULSD (Ultra-Low Sulfur Diesel)",
                "source": "EIA",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            # Calculate freight surcharge (industry standard: base $1.25/gal + overage)
            base_fuel = 1.25
            surcharge_per_mile = max(0, (result["price_per_gallon"] - base_fuel) * 0.06)
            result["surcharge_per_mile"] = round(surcharge_per_mile, 4)
            result["note"] = f"Freight surcharge @ ${surcharge_per_mile:.4f}/mile over ${base_fuel} base"
            _save_cache(result)
            return result
        return {"error": "No data returned from EIA"}
    except ImportError:
        return {"error": "httpx not installed. Run: pip install httpx"}
    except Exception as e:
        return {"error": str(e)[:200]}

def get_cached():
    """Get cached diesel price without API call."""
    try:
        if _CACHE.exists():
            return json.loads(_CACHE.read_text())
    except Exception:pass
    return {"error": "No cached fuel data. Call fetch_diesel_price() first."}

def _save_cache(data):
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(data, indent=2))

def calculate_freight_surcharge(miles, tons, base_fuel_price=1.25):
    """Calculate freight surcharge for a steel delivery.
    Standard: 45,000 lbs per truckload, ~22.5 tons/truck."""
    cached = get_cached()
    current = cached.get("price_per_gallon", 3.50)
    trucks = max(1, tons / 22.5)
    mpg = 5.5  # avg loaded flatbed
    gallons = (miles / mpg) * trucks
    surcharge = max(0, (current - base_fuel_price)) * gallons
    return {
        "miles": miles, "tons": tons, "trucks_needed": round(trucks, 1),
        "gallons": round(gallons, 1), "diesel_price": current,
        "base_price": base_fuel_price,
        "total_surcharge": round(surcharge, 2),
        "per_ton": round(surcharge / max(tons, 1), 2),
    }
