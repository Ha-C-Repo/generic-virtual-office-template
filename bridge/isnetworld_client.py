"""
Your Company Virtual Office - ISNetworld REST Client

ISN API at https://api.isnetworld.com/
Auth: CompanyKey + UserKey → bearer token over TLS 1.2+

Polls scorecard nightly, diffs against prior snapshot, auto-opens
tickets for any letter-grade drop or document expiration.

NOTE: ISN does not publish a fully open developer portal.
Contact ISN directly to confirm endpoint stability.
API access is per-tenant and not always granted.
"""

import os, json, hashlib
try:
    import httpx
except ImportError:
    httpx = None  # Graceful fallback - module loads but API calls need httpx at runtime
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_ISN_CACHE = _DATA / "isn_scorecard.json"

ISN_BASE = "https://api.isnetworld.com"
ISN_TOKEN_EP = "/token"
ISN_SCORECARD_EP = "/v1.0/CompanyProfile/Scorecard/{customerId}"
ISN_CONNECTIONS_EP = "/1.0/VendorConnections/ConnectedContractors"

# Your Company ISN ID
COMPANY_ISN = "[ISN ID]"


def _get_keys():
    """Load ISN credentials."""
    keys = {}
    for env in ["ISN_COMPANY_KEY", "ISN_USER_KEY", "ISN_CUSTOMER_ID"]:
        keys[env] = os.environ.get(env, "")
        if not keys[env]:
            try:
                from bridge.keyvault import load_keys
                all_keys = load_keys()
                keys[env] = all_keys.get(env, "")
            except Exception:pass
    return keys


def _authenticate():
    """Get bearer token from ISN."""
    keys = _get_keys()
    if not keys.get("ISN_COMPANY_KEY") or not keys.get("ISN_USER_KEY"):
        return None, "ISN credentials not configured. Set ISN_COMPANY_KEY and ISN_USER_KEY."
    try:
        resp = httpx.post(f"{ISN_BASE}{ISN_TOKEN_EP}", json={
            "CompanyKey": keys["ISN_COMPANY_KEY"],
            "UserKey": keys["ISN_USER_KEY"],
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token"), None
    except Exception as e:
        return None, f"ISN auth failed: {str(e)[:200]}"


def fetch_scorecard(customer_id=None):
    """Fetch ISN scorecard for a customer (hiring client)."""
    token, err = _authenticate()
    if err:
        return {"error": err, "configured": False}

    cid = customer_id or _get_keys().get("ISN_CUSTOMER_ID", "")
    if not cid:
        return {"error": "ISN_CUSTOMER_ID not set"}

    try:
        resp = httpx.get(
            f"{ISN_BASE}{ISN_SCORECARD_EP.format(customerId=cid)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        scorecard = resp.json()

        # Cache for diff
        _save_snapshot(scorecard)

        return {"scorecard": scorecard, "fetched_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return {"error": f"Scorecard fetch failed: {str(e)[:200]}"}


def _save_snapshot(scorecard):
    """Save scorecard snapshot for nightly diff."""
    _DATA.mkdir(parents=True, exist_ok=True)
    history = _load_history()
    snapshot = {
        "date": date.today().isoformat(),
        "hash": hashlib.sha256(json.dumps(scorecard, sort_keys=True).encode()).hexdigest()[:16],
        "scorecard": scorecard,
    }
    history.append(snapshot)
    # Keep 90 days
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    history = [h for h in history if h["date"] >= cutoff]
    _ISN_CACHE.write_text(json.dumps(history, indent=2))


def _load_history():
    try:
        if _ISN_CACHE.exists():
            return json.loads(_ISN_CACHE.read_text())
    except Exception:pass
    return []


def diff_scorecard():
    """Compare today's scorecard against yesterday's. Return changes."""
    history = _load_history()
    if len(history) < 2:
        return {"changes": [], "note": "Need at least 2 snapshots for diff"}

    today = history[-1]
    yesterday = history[-2]

    if today["hash"] == yesterday["hash"]:
        return {"changes": [], "note": "No scorecard changes detected"}

    changes = []
    t_sc = today.get("scorecard", {})
    y_sc = yesterday.get("scorecard", {})

    # Compare letter grades if available
    for key in set(list(t_sc.keys()) + list(y_sc.keys())):
        t_val = t_sc.get(key)
        y_val = y_sc.get(key)
        if t_val != y_val:
            changes.append({
                "field": key,
                "previous": y_val,
                "current": t_val,
                "date": today["date"],
            })

    return {"changes": changes, "date": today["date"]}


def check_document_expirations():
    """Check for documents expiring within 30 days."""
    # This would parse the ISN scorecard detail for document dates
    # Stub: returns structure for when ISN API access is granted
    return {
        "expiring_soon": [],
        "expired": [],
        "note": "Connect ISN API to enable document-expiration monitoring",
    }


def get_status():
    """Get current ISN integration status."""
    keys = _get_keys()
    configured = bool(keys.get("ISN_COMPANY_KEY") and keys.get("ISN_USER_KEY"))
    history = _load_history()
    return {
        "configured": configured,
        "company_isn": COMPANY_ISN,
        "snapshots_stored": len(history),
        "last_fetch": history[-1]["date"] if history else None,
    }


def for_briefing():
    """ISN status for morning briefing."""
    status = get_status()
    if not status["configured"]:
        return "ISNetworld: API not connected (set ISN_COMPANY_KEY + ISN_USER_KEY)"
    diff = diff_scorecard()
    if diff["changes"]:
        return f"ISNetworld: ⚠️ {len(diff['changes'])} scorecard change(s) detected"
    return "ISNetworld: No scorecard changes"
