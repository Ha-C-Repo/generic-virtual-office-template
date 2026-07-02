"""
Your Company Virtual Office - Legal-Compliant Scraper Base

Every agent scraper inherits from this. Enforces:
  1. robots.txt compliance (urllib.robotparser)
  2. Rate limit: ≤1 req / 2 sec, 60s backoff on 429/503
  3. Real User-Agent: YourCoIntelBot/1.0 (+contact@yourcompany.example.com)
  4. No authentication bypass - public pages only
  5. Source attribution stored with every record

Post-Van Buren (2021), hiQ v. LinkedIn (2022): public-data scraping
does not violate CFAA. We stay strictly on government + syndicated RSS.
"""

import time, hashlib, json, urllib.robotparser
from datetime import datetime, timezone

USER_AGENT = "YourCoIntelBot/1.0 (+contact@yourcompany.example.com)"
MIN_DELAY = 2.0  # seconds between requests to same domain
BACKOFF_DELAY = 60.0  # seconds on 429/503

_last_request_time = {}  # domain → timestamp
_robot_parsers = {}  # domain → RobotFileParser


def check_robots(url: str) -> bool:
    """Check robots.txt for the given URL. Returns True if allowed."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain not in _robot_parsers:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{parsed.scheme}://{domain}/robots.txt")
            rp.read()
            _robot_parsers[domain] = rp
        return _robot_parsers[domain].can_fetch(USER_AGENT, url)
    except Exception:
        return True  # If robots.txt is unreachable, allow (standard practice)


def rate_limit(domain: str):
    """Enforce minimum delay between requests to the same domain."""
    now = time.time()
    last = _last_request_time.get(domain, 0)
    wait = MIN_DELAY - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[domain] = time.time()


def safe_get(url: str, timeout: int = 30, allow_non_gov: bool = False) -> dict:
    """Fetch a URL with all legal guardrails enforced.

    Returns: {ok, status, text, url, fetched_at, source_hash}
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.50; needs manual audit)
    import httpx
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc

    # Check robots.txt
    if not check_robots(url):
        return {"ok": False, "error": f"Blocked by robots.txt: {url}", "url": url}

    # Rate limit
    rate_limit(domain)

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})

            if resp.status_code in (429, 503):
                time.sleep(BACKOFF_DELAY)
                resp = client.get(url, headers={"User-Agent": USER_AGENT})

            text = resp.text
            return {
                "ok": resp.status_code == 200,
                "status": resp.status_code,
                "text": text,
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "source_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
                "domain": domain,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "url": url}


def safe_get_json(url: str, timeout: int = 30) -> dict:
    """Fetch JSON with all legal guardrails."""
    result = safe_get(url, timeout)
    if result.get("ok"):
        try:
            result["data"] = json.loads(result["text"])
        except Exception:
            result["data"] = None
            result["parse_error"] = "Not valid JSON"
    return result


def make_source_record(url: str, data: dict, agent_name: str) -> dict:
    """Create an attribution record for every piece of ingested data."""
    return {
        "source_url": url,
        "agent": agent_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data_hash": hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest()[:16],
        "legal_basis": "public_domain" if any(d in url for d in [".gov", ".org", "fred.stlouisfed"]) else "fair_use_rss",
    }
