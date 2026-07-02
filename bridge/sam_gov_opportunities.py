"""
SAM.gov Opportunities - Data Fabric Layer

Federal contract opportunities filtered for structural steel:
  NAICS 332312 - Fabricated Structural Metal Manufacturing
  NAICS 238120 - Structural Steel and Precast Concrete Contractors

API: https://api.sam.gov/opportunities/v2/search
Requires: SAM_GOV_API_KEY (free from api.data.gov)
"""
import json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CACHE = Path(__file__).resolve().parent.parent / "data" / "sam_gov_cache.json"
SAM_BASE = "https://api.sam.gov/opportunities/v2/search"
NAICS_CODES = ["332312", "238120"]
HOUSTON_KEYWORDS = ["steel", "structural", "fabricat", "erect", "iron", "welding"]

def _get_key():
    key = os.environ.get("SAM_GOV_API_KEY", "")
    if not key:
        try:
            from bridge.keyvault import load_keys
            key = load_keys().get("SAM_GOV_API_KEY", "")
        except Exception:pass
    return key

def search_opportunities(keywords=None, naics=None, posted_days=30,
                         state="TX", limit=25):
    """Search SAM.gov for federal opportunities.
    Returns list of opportunities with title, agency, dates, value."""
    key = _get_key()
    if not key:
        return {"error": "SAM_GOV_API_KEY not set. Set env var: set SAM_GOV_API_KEY=your_key  (free at api.data.gov)"}
    try:
        import httpx
        posted_from = (datetime.now() - timedelta(days=posted_days)).strftime("%m/%d/%Y")  # vj: duration-math
        params = {
            "api_key": key,
            "postedFrom": posted_from,
            "limit": limit,
            "offset": 0,
        }
        if naics:
            params["ncode"] = ",".join(naics)
        else:
            params["ncode"] = ",".join(NAICS_CODES)
        if state:
            params["state"] = state
        if keywords:
            params["q"] = " ".join(keywords) if isinstance(keywords, list) else keywords
        resp = httpx.get(SAM_BASE, params=params, timeout=20)
        data = resp.json()
        opps = data.get("opportunitiesData", [])
        results = []
        for o in opps:
            results.append({
                "id": o.get("noticeId", ""),
                "title": o.get("title", ""),
                "agency": o.get("fullParentPathName", ""),
                "type": o.get("type", ""),
                "posted": o.get("postedDate", ""),
                "deadline": o.get("responseDeadLine", ""),
                "naics": o.get("naicsCode", ""),
                "set_aside": o.get("typeOfSetAside", ""),
                "place": o.get("placeOfPerformance", {}).get("state", {}).get("code", ""),
                "url": f"https://sam.gov/opp/{o.get('noticeId', '')}/view",
            })
        cache = {"fetched_at": datetime.now(timezone.utc).isoformat(), "count": len(results),
                 "opportunities": results}
        _save_cache(cache)
        return cache
    except ImportError:
        return {"error": "httpx not installed"}
    except Exception as e:
        return {"error": str(e)[:200]}

def get_cached():
    try:
        if _CACHE.exists():
            return json.loads(_CACHE.read_text())
    except Exception:pass
    return {"opportunities": [], "note": "No cached data"}

def _save_cache(data):
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(data, indent=2, default=str))

def houston_steel_opportunities(posted_days=14):
    """Pre-filtered: TX structural steel opportunities, last 14 days."""
    return search_opportunities(
        keywords=HOUSTON_KEYWORDS[:3], naics=NAICS_CODES,
        posted_days=posted_days, state="TX"
    )

def for_morning_briefing():
    """Compact summary for SMS briefing."""
    cached = get_cached()
    opps = cached.get("opportunities", [])
    if not opps:
        return "SAM.gov: no cached federal opportunities."
    lines = [f"SAM.gov: {len(opps)} federal opps:"]
    for o in opps[:3]:
        dl = o.get("deadline", "N/A")[:10]
        lines.append(f"  {o['title'][:50]} - due {dl}")
    return "\n".join(lines)
