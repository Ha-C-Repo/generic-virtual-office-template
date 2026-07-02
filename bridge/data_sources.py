"""
Your Company Virtual Office - Free Data Sources
No AI tokens spent. Pure Python data gathering.
"""

import json
from datetime import datetime, timedelta, timezone


def fetch_stock_data(tickers: list[str], period: str = "1mo") -> dict:
    """Fetch OHLCV + fundamentals via yfinance (free, no API key).

    Returns {ticker: {price, change_pct, pe, market_cap, volume, ...}}
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed. Run: pip install yfinance"}

    results = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            hist = t.history(period="5d")
            price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            prev = info.get("regularMarketPreviousClose", price)
            change_pct = round((price - prev) / prev * 100, 2) if prev else 0

            results[ticker] = {
                "price": round(price, 2),
                "change_pct": change_pct,
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "volume": info.get("volume"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "sector": info.get("sector", ""),
                "name": info.get("shortName", ticker),
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


def fetch_watchlist() -> dict:
    """Fetch the full Your Company steel/construction watchlist."""
    # BUG-9 fix: "X" (US Steel) removed after Nippon acquisition June 2025
    STEEL = ["NUE", "STLD", "CMC", "CLF", "RS"]
    CONSTRUCTION = ["FLR", "PWR", "KBR", "ACM"]
    BENCHMARKS = ["SPY", "XLB", "XLI"]
    all_tickers = STEEL + CONSTRUCTION + BENCHMARKS
    data = fetch_stock_data(all_tickers)
    return {
        "steel": {t: data.get(t, {}) for t in STEEL},
        "construction": {t: data.get(t, {}) for t in CONSTRUCTION},
        "benchmarks": {t: data.get(t, {}) for t in BENCHMARKS},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_steel_price_index() -> dict:
    """Get steel price index from NUE + STLD as proxy."""
    data = fetch_stock_data(["NUE", "STLD"])
    nue = data.get("NUE", {})
    stld = data.get("STLD", {})
    return {
        "nue_price": nue.get("price", 0),
        "stld_price": stld.get("price", 0),
        "nue_change": nue.get("change_pct", 0),
        "stld_change": stld.get("change_pct", 0),
        "index_direction": "UP" if (nue.get("change_pct", 0) + stld.get("change_pct", 0)) > 0 else "DOWN",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def capitol_trades_recent(days: int = 30) -> list[dict]:
    """Fetch recent congressional trades from Capitol Trades API (free)."""
    try:
        import urllib.request
        url = f"https://api.capitoltrades.com/trades?per_page=20&page=1"
        req = urllib.request.Request(url, headers={"User-Agent": "YourCo/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])[:20]
    except Exception as e:
        return [{"error": str(e)}]


def houston_weather() -> dict:
    """Get Houston weather for briefings (free wttr.in API)."""
    try:
        import urllib.request
        url = "https://wttr.in/Houston,TX?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "YourCo/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            current = data.get("current_condition", [{}])[0]
            return {
                "temp_f": current.get("temp_F", "?"),
                "condition": current.get("weatherDesc", [{}])[0].get("value", "?"),
                "humidity": current.get("humidity", "?"),
                "wind_mph": current.get("windspeedMiles", "?"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        return {"error": str(e)}
