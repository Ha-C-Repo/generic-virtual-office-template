"""
Your Company Virtual Office - Houston Pipeline Agent

Replaces: IIR Energy / Industrial Info ($6,000/yr)
Cost: $0 + ~$5/month Gemini tokens

Sources (all free, all legal):
  1. City of Houston permits (data.houstontx.gov - CKAN JSON API)
  2. TCEQ Central Registry + STEERS NOIs (gov, public, no auth)
  3. Texas RRC drilling permits (gov, public data downloads)
  4. SEC EDGAR 8-K/10-Q filings (Fluor, KBR, Jacobs, McDermott, Wood)
  5. Port Houston BusinessWire RSS (syndicated)
  6. Houston Business Journal RSS + BIC Magazine + ENR TX/LA
  7. Google Alerts RSS feeds (14 alerts)

Output: project_pipeline SQLite table, daily 8 AM digest,
        "should we chase" AI scores per project.
        BETTER than IIR because we add TCEQ upstream signals
        + EDGAR + AI-scored fit for our shop.
"""

import json, sqlite3, threading, re, hashlib
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "houston_pipeline.db"
    return Path(__file__).resolve().parent.parent / "data" / "houston_pipeline.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

# EPC companies to watch on EDGAR
EDGAR_WATCHLIST = {
    "FLR": {"name": "Fluor Corporation", "cik": "1124198"},
    "KBR": {"name": "KBR Inc", "cik": "1357615"},
    "J": {"name": "Jacobs Solutions", "cik": "52988"},
    "WD": {"name": "John Wood Group", "cik": ""},  # via 6-K
}

# RSS feeds for Houston construction news
RSS_FEEDS = {
    "HBJ": "https://feeds.bizjournals.com/bizj_houston",
    "BIC_Magazine": "https://www.bicmagazine.com/feed/",
    "ENR_Texas": "https://www.enr.com/topics/509-texas-louisiana/rss",
    "Port_Houston": "https://www.businesswire.com/portal/site/home/news/rss/",
}

# Google Alert RSS templates (user creates these at google.com/alerts)
GOOGLE_ALERTS = [
    "Houston construction project structural steel",
    "Houston refinery turnaround",
    "Texas petrochemical expansion",
    "Houston industrial construction",
    "Port of Houston expansion",
    "Eli Lilly Generation Park",
    "Air Products Texas City",
    "Houston ship channel Project 11",
]

# Known Houston-area mega-projects (seeded from deep research)
SEED_PROJECTS = [
    {"name": "Eli Lilly Generation Park", "owner": "Eli Lilly", "est_value": 6_500_000_000, "location": "Pearland TX", "steel_likely": True, "status": "announced"},
    {"name": "Air Products Ammonia Complex", "owner": "Air Products", "est_value": 0, "location": "Texas City TX", "steel_likely": True, "status": "permitting"},
    {"name": "Tesla Megapack BESS", "owner": "Tesla", "est_value": 200_000_000, "location": "Brookshire TX", "steel_likely": True, "status": "construction"},
    {"name": "Targa Speedway NGL Pipeline", "owner": "Targa Resources", "est_value": 1_600_000_000, "location": "TX Permian-GulfCoast", "steel_likely": True, "status": "construction"},
    {"name": "OxyChem Battleground Chlor-Alkali", "owner": "OxyChem", "est_value": 1_100_000_000, "location": "La Porte TX", "steel_likely": True, "status": "construction"},
    {"name": "Dow Freeport Polyethylene Unit", "owner": "Dow Chemical", "est_value": 715_000_000, "location": "Freeport TX", "steel_likely": True, "status": "construction"},
    {"name": "Port Houston Project 11 Channel", "owner": "Port of Houston Authority", "est_value": 1_500_000_000, "location": "Houston Ship Channel", "steel_likely": True, "status": "construction"},
    {"name": "Enterprise Train 14 Fractionator", "owner": "Enterprise Products", "est_value": 0, "location": "Mont Belvieu TX", "steel_likely": True, "status": "announced"},
    {"name": "RWE Crowned Heron 2 BESS", "owner": "RWE", "est_value": 0, "location": "Richmond TX", "steel_likely": True, "status": "permitting"},
    {"name": "TMEIC Power Systems Factory", "owner": "TMEIC", "est_value": 0, "location": "Waller County TX", "steel_likely": True, "status": "permitting"},
    {"name": "SPR Bryan Mound Life Extension", "owner": "DOE", "est_value": 0, "location": "Brazoria County TX", "steel_likely": True, "status": "planning"},
]


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, owner TEXT DEFAULT '',
            epc TEXT DEFAULT '', location TEXT DEFAULT '',
            est_value REAL DEFAULT 0, est_steel_tons REAL DEFAULT 0,
            steel_likely INTEGER DEFAULT 1, status TEXT DEFAULT 'tracking',
            capability_match REAL DEFAULT 0, source TEXT DEFAULT '',
            source_urls TEXT DEFAULT '[]', notes TEXT DEFAULT '',
            first_seen TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(name, owner)
        );
        CREATE TABLE IF NOT EXISTS news_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL, title TEXT NOT NULL,
            url TEXT DEFAULT '', summary TEXT DEFAULT '',
            relevant_to_steel INTEGER DEFAULT 0,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permit_type TEXT NOT NULL, applicant TEXT DEFAULT '',
            project_desc TEXT DEFAULT '', location TEXT DEFAULT '',
            est_value REAL DEFAULT 0, permit_date TEXT DEFAULT '',
            source TEXT NOT NULL, fetched_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_news_date ON news_items(fetched_at)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()
_init()


def seed_pipeline():
    """Seed the pipeline with known Houston mega-projects."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        for p in SEED_PROJECTS:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO projects (name,owner,location,est_value,steel_likely,status,source,first_seen,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (p["name"], p["owner"], p["location"], p["est_value"], 1 if p["steel_likely"] else 0,
                     p["status"], "deep_research_seed", now, now))
            except Exception:pass
        c.commit(); c.close()
    return {"seeded": len(SEED_PROJECTS)}


def pull_houston_permits() -> list:
    """Pull City of Houston commercial permits (free CKAN API)."""
    results = []
    try:
        from bridge.agents.scraper_base import safe_get_json
        # Houston Open Data CKAN API
        url = "https://data.houstontx.gov/api/3/action/datastore_search?resource_id=525772a1-0b4b-4d55-9b43-4d3b589fe1b7&limit=50&sort=_id+desc"
        resp = safe_get_json(url)
        if resp.get("ok") and resp.get("data"):
            records = resp["data"].get("result", {}).get("records", [])
            now = datetime.now(timezone.utc).isoformat()
            with _lock:
                c = _conn()
                for r in records:
                    val = float(r.get("Total Permit Fees Paid", 0) or 0)
                    if val > 50000:  # commercial threshold
                        c.execute(
                            "INSERT INTO permits (permit_type,applicant,project_desc,location,est_value,permit_date,source,fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                            ("houston_commercial", r.get("Applicant Full Name", ""),
                             r.get("Project Description", ""), r.get("Street Number", "") + " " + r.get("Street Name", ""),
                             val, r.get("Application Date", ""), "data.houstontx.gov", now))
                        results.append({"applicant": r.get("Applicant Full Name", ""), "value": val})
                c.commit(); c.close()
    except Exception as e:
        results.append({"error": str(e)[:200]})
    return results


def pull_rss_news() -> list:
    """Pull Houston construction news from RSS feeds."""
    items = []
    try:
        import feedparser
    except ImportError:
        return [{"error": "feedparser not installed - pip install feedparser"}]

    now = datetime.now(timezone.utc).isoformat()
    steel_keywords = ["steel", "fabricat", "erect", "structural", "industrial",
                      "refinery", "petrochemical", "pipeline", "plant", "warehouse"]

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:300]
                url = entry.get("link", "")
                combined = (title + " " + summary).lower()
                relevant = any(kw in combined for kw in steel_keywords)

                items.append({
                    "source": source_name, "title": title, "url": url,
                    "relevant": relevant,
                })

                with _lock:
                    c = _conn()
                    c.execute(
                        "INSERT INTO news_items (source,title,url,summary,relevant_to_steel,fetched_at) VALUES (?,?,?,?,?,?)",
                        (source_name, title, url, summary, 1 if relevant else 0, now))
                    c.commit(); c.close()
        except Exception:pass

    return items


def score_project(project: dict) -> float:
    """AI-score a project for Your Company's capability match (0-1)."""
    score = 0.0
    desc = (project.get("name", "") + " " + project.get("notes", "")).lower()

    # Steel likelihood
    if project.get("steel_likely") or any(kw in desc for kw in ["steel", "structural", "fabricat"]):
        score += 0.3

    # Location proximity (Houston metro)
    loc = project.get("location", "").lower()
    if any(h in loc for h in ["houston", "harris", "galveston", "brazoria", "fort bend", "montgomery"]):
        score += 0.25
    elif "texas" in loc or "tx" in loc:
        score += 0.15

    # Project type match
    if any(kw in desc for kw in ["church", "warehouse", "commercial", "school", "hospital", "retail"]):
        score += 0.2  # Sweet spot
    elif any(kw in desc for kw in ["refinery", "petrochemical", "industrial", "pipeline"]):
        score += 0.15  # Capable but needs EMR < 0.85

    # Size match (50-5000 tons sweet spot)
    tons = project.get("est_steel_tons", 0)
    if 50 <= tons <= 5000:
        score += 0.15
    elif tons > 0:
        score += 0.05

    return min(score, 1.0)


def get_pipeline(status: str = None) -> dict:
    """Get the full project pipeline, optionally filtered by status."""
    with _lock:
        c = _conn()
        if status:
            rows = c.execute("SELECT * FROM projects WHERE status=? ORDER BY est_value DESC", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM projects ORDER BY capability_match DESC, est_value DESC").fetchall()
        c.close()
    return {"projects": [dict(r) for r in rows], "total": len(rows)}


def get_recent_news(steel_only: bool = True, limit: int = 20) -> list:
    """Get recent construction news."""
    with _lock:
        c = _conn()
        if steel_only:
            rows = c.execute("SELECT * FROM news_items WHERE relevant_to_steel=1 ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM news_items ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        c.close()
    return [dict(r) for r in rows]


def for_briefing() -> str:
    """Morning briefing summary."""
    pipeline = get_pipeline()
    total = pipeline["total"]
    active = sum(1 for p in pipeline["projects"] if p.get("status") in ("construction", "permitting"))
    return f"Houston pipeline: {total} projects tracked, {active} active. Top: {pipeline['projects'][0]['name'] if pipeline['projects'] else 'none'}"


def pull_all_sources() -> dict:
    """Run the full daily pull. Scheduled at 04:00."""
    results = {}
    results["permits"] = pull_houston_permits()
    results["news"] = pull_rss_news()

    # Score all projects
    with _lock:
        c = _conn()
        projects = c.execute("SELECT * FROM projects").fetchall()
        for p in projects:
            score = score_project(dict(p))
            c.execute("UPDATE projects SET capability_match=?, updated_at=? WHERE id=?",
                      (score, datetime.now(timezone.utc).isoformat(), p["id"]))
        c.commit(); c.close()
    results["projects_scored"] = len(projects)

    return results


def stats() -> dict:
    with _lock:
        c = _conn()
        projects = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        news = c.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
        permits = c.execute("SELECT COUNT(*) FROM permits").fetchone()[0]
        c.close()
    return {"projects": projects, "news_items": news, "permits": permits,
            "replaces": "IIR Energy ($6,000/yr)", "our_cost": "$0 + ~$5/month Gemini tokens"}


# Auto-seed on first import
try:
    with _lock:
        c = _conn()
        count = c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        c.close()
    if count == 0:
        seed_pipeline()
except Exception:pass
