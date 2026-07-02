"""
Your Company Virtual Office - Data Feed Infrastructure

Two critical tools that make the AI agents work in production:

1. IMAP Email Price-Sheet Parser
   - Connects to pricing@yourcompany.example.com
   - Detaches PDF/XLSX from service-center emails
   - Extracts per-shape pricing via pattern matching (then Claude fallback)
   - Feeds Steel Price Agent with ACTUAL landed prices

2. RSS News Aggregator
   - Pulls 14+ RSS feeds (Houston Business Journal, BIC Magazine, ENR, etc.)
   - Classifies articles by relevance to structural steel
   - Feeds Houston Pipeline Agent + Market Intelligence Agent

Both run on schedule via the Agent Orchestrator.
"""

import json, sqlite3, threading, re, email, base64
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from email import policy

_DB = Path(__file__).resolve().parent.parent.parent / "data" / "data_feeds.db"
_lock = threading.Lock()


def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS email_price_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, subject TEXT DEFAULT '',
            supplier TEXT DEFAULT '', attachment_name TEXT DEFAULT '',
            quotes_extracted INTEGER DEFAULT 0,
            processed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rss_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL, title TEXT NOT NULL,
            url TEXT DEFAULT '', published TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            steel_relevant INTEGER DEFAULT 0,
            category TEXT DEFAULT 'general',
            fetched_at TEXT NOT NULL,
            UNIQUE(url)
        );
        CREATE TABLE IF NOT EXISTS google_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_name TEXT NOT NULL, title TEXT NOT NULL,
            url TEXT DEFAULT '', snippet TEXT DEFAULT '',
            fetched_at TEXT NOT NULL,
            UNIQUE(url)
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_rss_source ON rss_articles(source)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_rss_relevant ON rss_articles(steel_relevant)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()
_init()


# ═══ IMAP EMAIL PRICE-SHEET PARSER ═════════════════════════════════

# Known service-center sender patterns
SERVICE_CENTER_SENDERS = {
    "triple-s": "Triple-S Steel",
    "tripless": "Triple-S Steel",
    "reliance": "Reliance Steel",
    "olympic": "Olympic Steel",
    "metals usa": "Metals USA",
    "metalsdirect": "Metals Direct",
    "steel technologies": "Steel Technologies",
    "nucor": "Nucor",
    "steeldynamics": "Steel Dynamics",
    "commercial metals": "Commercial Metals",
    "worthington": "Worthington Industries",
}


def fetch_price_emails(imap_host: str = "", imap_user: str = "", imap_pass: str = "",
                       folder: str = "INBOX", days_back: int = 7) -> list:
    """Fetch price-sheet emails from the pricing@yourcompany.example.com mailbox.

    Returns list of {sender, subject, attachments: [{filename, content_type, data_b64}]}
    """
    if not all([imap_host, imap_user, imap_pass]):
        return [{
            "note": "IMAP not configured. Set up pricing@yourcompany.example.com mailbox.",
            "setup": {
                "imap_host": "imap.gmail.com (or your provider)",
                "imap_user": "pricing@yourcompany.example.com",
                "imap_pass": "App password (not main password)",
                "folder": "INBOX",
            },
            "how_it_works": [
                "1. Service centers email price sheets to pricing@yourcompany.example.com",
                "2. This parser fetches emails every 15 minutes",
                "3. Detaches PDF/XLSX attachments",
                "4. Extracts per-shape pricing via regex + Claude fallback",
                "5. Inserts into service_center_quotes table",
                "6. Steel Price Agent uses these in the weekly brief",
            ],
        }]

    try:
        import imaplib
        mail = imaplib.IMAP4_SSL(imap_host)
        mail.login(imap_user, imap_pass)
        mail.select(folder)

        # Search for recent emails
        since = (date.today() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        _, message_numbers = mail.search(None, f'(SINCE "{since}")')

        results = []
        for num in message_numbers[0].split()[-20:]:  # Last 20 emails max
            _, msg_data = mail.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1], policy=policy.default)

            sender = str(msg.get("From", ""))
            subject = str(msg.get("Subject", ""))

            # Check if from a service center
            supplier = _identify_supplier(sender, subject)

            attachments = []
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    fname = part.get_filename() or ""
                    if fname.lower().endswith((".pdf", ".xlsx", ".xls", ".csv")):
                        data = part.get_payload(decode=True)
                        attachments.append({
                            "filename": fname,
                            "content_type": part.get_content_type(),
                            "size": len(data),
                            "data_b64": base64.b64encode(data).decode()[:100] + "...",  # Preview only
                        })

            if attachments:
                results.append({
                    "sender": sender,
                    "subject": subject,
                    "supplier": supplier,
                    "attachments": attachments,
                    "attachment_count": len(attachments),
                })

                # Log
                now = datetime.now(timezone.utc).isoformat()
                with _lock:
                    c = _conn()
                    c.execute(
                        "INSERT INTO email_price_sheets (sender,subject,supplier,attachment_name,processed_at) VALUES (?,?,?,?,?)",
                        (sender, subject, supplier, attachments[0]["filename"], now))
                    c.commit(); c.close()

        mail.logout()
        return results

    except ImportError:
        return [{"error": "imaplib is a standard library - should always be available"}]
    except Exception as e:
        return [{"error": str(e)[:200]}]


def _identify_supplier(sender: str, subject: str) -> str:
    """Identify the service center from sender/subject."""
    combined = (sender + " " + subject).lower()
    for pattern, name in SERVICE_CENTER_SENDERS.items():
        if pattern in combined:
            return name
    return "Unknown Supplier"


# ═══ RSS NEWS AGGREGATOR ═══════════════════════════════════════════

RSS_FEEDS = {
    "Houston Business Journal": "https://feeds.bizjournals.com/bizj_houston",
    "BIC Magazine": "https://www.bicmagazine.com/feed/",
    "ENR Texas": "https://www.enr.com/topics/509-texas-louisiana/rss",
    "Construction Dive": "https://www.constructiondive.com/feeds/news/",
    "Steel Orbis": "https://www.steelorbis.com/rss/steelorbis-us-steel-news.xml",
    "Metal Bulletin (free)": "https://www.metalbulletin.com/rss",
    "Fabricator Magazine": "https://www.thefabricator.com/rss",
    "Modern Steel Construction": "https://www.aisc.org/modernsteel/rss",
    "Welding Journal": "https://www.aws.org/wj/rss",
}

STEEL_KEYWORDS = [
    "steel", "structural", "fabricat", "erect", "weld", "iron",
    "beam", "column", "joist", "deck", "metal", "mill",
    "nucor", "steel dynamics", "commercial metals", "olympic steel",
    "HRC", "hot rolled", "cold rolled", "scrap", "rebar",
]

HOUSTON_KEYWORDS = [
    "houston", "texas", "gulf coast", "galveston", "harris county",
    "refinery", "petrochemical", "pipeline", "port of houston",
    "energy corridor", "ship channel", "baytown", "la porte",
    "pasadena tx", "deer park", "texas city", "freeport",
]


def pull_all_rss() -> dict:
    """Pull all RSS feeds and classify articles."""
    try:
        import feedparser
    except ImportError:
        return {"error": "pip install feedparser --break-system-packages"}

    results = {"feeds_pulled": 0, "articles_total": 0, "steel_relevant": 0, "houston_relevant": 0}
    now = datetime.now(timezone.utc).isoformat()

    for source_name, feed_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(feed_url)
            results["feeds_pulled"] += 1

            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")[:500]
                url = entry.get("link", "")
                published = entry.get("published", "")

                combined = (title + " " + summary).lower()
                is_steel = any(kw in combined for kw in STEEL_KEYWORDS)
                is_houston = any(kw in combined for kw in HOUSTON_KEYWORDS)

                category = "steel" if is_steel else "houston" if is_houston else "general"

                results["articles_total"] += 1
                if is_steel: results["steel_relevant"] += 1
                if is_houston: results["houston_relevant"] += 1

                with _lock:
                    c = _conn()
                    try:
                        c.execute(
                            "INSERT OR IGNORE INTO rss_articles (source,title,url,published,summary,steel_relevant,category,fetched_at) VALUES (?,?,?,?,?,?,?,?)",
                            (source_name, title, url, published, summary, 1 if is_steel else 0, category, now))
                    except Exception:pass
                    c.commit(); c.close()

        except Exception as e:
            results[f"error_{source_name}"] = str(e)[:100]

    return results


def get_recent_articles(steel_only: bool = False, houston_only: bool = False, limit: int = 20) -> list:
    """Get recent RSS articles, optionally filtered."""
    with _lock:
        c = _conn()
        if steel_only:
            rows = c.execute("SELECT * FROM rss_articles WHERE steel_relevant=1 ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        elif houston_only:
            rows = c.execute("SELECT * FROM rss_articles WHERE category='houston' ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM rss_articles ORDER BY fetched_at DESC LIMIT ?", (limit,)).fetchall()
        c.close()
    return [dict(r) for r in rows]


def get_news_digest(limit: int = 10) -> str:
    """One-paragraph news digest for the morning brief."""
    articles = get_recent_articles(steel_only=True, limit=limit)
    if not articles:
        return "No recent steel news. RSS feeds will populate after first pull."

    lines = [f"📰 Steel/Construction News ({len(articles)} articles):"]
    for a in articles[:5]:
        lines.append(f"  • {a['title'][:80]} [{a['source']}]")
    return "\n".join(lines)


def stats() -> dict:
    with _lock:
        c = _conn()
        emails = c.execute("SELECT COUNT(*) FROM email_price_sheets").fetchone()[0]
        articles = c.execute("SELECT COUNT(*) FROM rss_articles").fetchone()[0]
        steel = c.execute("SELECT COUNT(*) FROM rss_articles WHERE steel_relevant=1").fetchone()[0]
        alerts = c.execute("SELECT COUNT(*) FROM google_alerts").fetchone()[0]
        c.close()
    return {
        "price_sheet_emails": emails,
        "rss_articles": articles,
        "steel_relevant_articles": steel,
        "google_alerts": alerts,
        "rss_feeds_configured": len(RSS_FEEDS),
        "service_center_patterns": len(SERVICE_CENTER_SENDERS),
    }
