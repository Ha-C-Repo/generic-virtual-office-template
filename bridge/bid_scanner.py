"""
Your Company Virtual Office - Bid Scanner

Scans the Owner's Outlook inbox for RFQs, RFPs, and ITBs in scope for
Your Company (structural steel fab/erection, Houston/Texas).

Two backends:
  1. win32com - direct local Outlook COM automation (preferred, Windows only)
  2. IMAP fallback - if Outlook COM not available

Scoring: each email scored 0-100 against Your Company's scope criteria.
  ≥ 70 → HIGH priority, show immediately
  40-69 → MEDIUM priority, show in daily summary
  < 40  → ignore

HARD DISQUALIFIERS (score → 0, skip immediately):
  - PEMB / pre-engineered metal buildings
  - Residential / single-family / apartments
  - Outside 300-mile radius AND no Houston mention

Results stored in data/bid_leads.db (SQLite).
"""

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_PATH = _DATA_DIR / "bid_leads.db"

# ── Houston coordinates for radius filtering ───────────────────────────
HOUSTON_LAT = 29.7604
HOUSTON_LNG = -95.3698
MAX_RADIUS_MILES = 200  # the Owner's stated preference

# ── HARD DISQUALIFIERS - immediate score = 0, do not show ─────────────
# Owner said: "PEMB is not in scope. Full stop."
HARD_DISQUALIFIERS = [
    "pre-engineered metal building", "pre-engineered metal buildings",
    "pemb", "pre-engineered building", "metal building system",
    "metal building systems", "pre-engineered steel building",
    "butler building", "nucor building", "robertson building",
    "varco pruden", "ceco building", "bluescope",
    "residential", "single family", "single-family",
    "townhome", "townhomes", "apartment complex", "multifamily",
    "multi-family", "duplex", "condominium",
    "carpentry only", "plumbing only", "hvac only",
    "electrical only", "landscaping", "painting only",
    "canada", "mexico", "international", "overseas",
    "united kingdom", "australia",
]

# ── Must-have keywords (any one → eligible) ────────────────────────────
IN_SCOPE_KEYWORDS = [
    "structural steel", "steel fabrication", "steel erection",
    "structural fabrication", "structural erection",
    "steel structure", "steel framing", "structural framing",
    "fab and erect", "fabrication and erection", "fab/erect",
    "wide flange", "W-shape", "W shape", "HSS", "hollow structural section",
    "AISC", "A36", "A992", "A500", "A572",
    "structural framing", "steel columns", "steel beams",
    "structural members", "moment frame", "braced frame",
    "steel joists", "SJI", "roof deck", "floor deck", "composite deck",
    "anchor bolts", "base plate", "column base plate",
    "RFQ", "RFP", "ITB", "bid request", "request for quote",
    "request for proposal", "invitation to bid",
    "fabrication shop", "fab shop", "erection contractor",
]

# ── Location boosters ──────────────────────────────────────────────────
HOUSTON_KEYWORDS = [
    "houston", "baytown", "pasadena", "deer park", "la marque",
    "texas city", "freeport", "harris county", "galveston county",
    "brazoria county", "fort bend county", "montgomery county",
    "beaumont", "port arthur", "orange, tx", "corpus christi",
    "san antonio", "austin, tx", "waco", "tyler, tx", "longview, tx",
    "midland", "odessa", "lubbock", "abilene",
    "gulf coast", "texas", " tx ", ", tx,", "(tx)", "77",  # TX zip prefix
]

# ── High-value project types ───────────────────────────────────────────
HIGH_VALUE_KEYWORDS = [
    "refinery", "petrochemical", "chemical plant", "lng",
    "industrial facility", "industrial building", "manufacturing",
    "distribution center", "distribution warehouse", "warehouse",
    "commercial building", "office building", "hospital", "school",
    "arena", "stadium", "hangar", "airport", "terminal",
    "data center", "power plant", "water treatment",
]

# ── Bid type patterns ──────────────────────────────────────────────────
BID_TYPE_PATTERNS = [
    r"RFQ\s*#?\s*\d*", r"RFP\s*#?\s*\d*", r"ITB\s*#?\s*\d*",
    r"project\s+#?\s*\d+", r"bid\s+due", r"proposals?\s+due",
    r"quotes?\s+due", r"submit\s+by", r"deadline\s*:",
    r"invitation\s+to\s+bid", r"request\s+for\s+(quote|proposal|bid)",
]


def _is_hard_disqualified(text: str) -> tuple[bool, str]:
    """Check if text contains any hard disqualifier.
    Returns (is_disqualified, reason).
    """
    lower = text.lower()
    for kw in HARD_DISQUALIFIERS:
        if kw.lower() in lower:
            return True, f"hard disqualifier: {kw}"
    return False, ""


def _extract_city_state(text: str) -> list[str]:
    """Extract city/state mentions from text."""
    # Look for "City, TX" or "City, Texas" patterns
    pattern = re.findall(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),?\s+(?:TX|Texas)\b", text)
    return pattern


def score_email(subject: str, body: str, sender: str = "") -> dict:
    """Score an email against Your Company's scope criteria.

    Returns {score, tier, reasons, is_bid, project_signals, disqualified}
    """
    full_text = (subject + " " + body + " " + sender)
    lower = full_text.lower()
    score = 0
    reasons = []
    project_signals = {}

    # ── HARD DISQUALIFIER CHECK - stops everything ─────────────────────
    disq, disq_reason = _is_hard_disqualified(full_text)
    if disq:
        return {
            "score": 0,
            "tier": "DISQUALIFIED",
            "reasons": [disq_reason],
            "is_bid": False,
            "project_signals": {},
            "disqualified": True,
            "disq_reason": disq_reason,
        }

    # ── Bid type indicators ────────────────────────────────────────────
    is_bid = False
    for pat in BID_TYPE_PATTERNS:
        if re.search(pat, full_text, re.IGNORECASE):
            is_bid = True
            score += 15
            reasons.append("bid request confirmed")
            break

    # ── In-scope keyword check ─────────────────────────────────────────
    scope_hits = [kw for kw in IN_SCOPE_KEYWORDS if kw.lower() in lower]
    if scope_hits:
        score += min(len(scope_hits) * 8, 40)
        reasons.append(f"scope: {', '.join(scope_hits[:3])}")
    else:
        score -= 25  # No scope keywords = likely out of scope

    # ── Location: Houston/Texas boost ──────────────────────────────────
    location_hits = [kw for kw in HOUSTON_KEYWORDS if kw.lower() in lower]
    if location_hits:
        score += min(len(location_hits) * 5, 20)
        reasons.append(f"location: {location_hits[0]}")
        project_signals["location"] = location_hits[0]
    else:
        # No Texas/Houston mention - reduce score significantly
        score -= 15
        reasons.append("no TX/Houston location found")

    # ── High-value project type ────────────────────────────────────────
    hv_hits = [kw for kw in HIGH_VALUE_KEYWORDS if kw.lower() in lower]
    if hv_hits:
        score += min(len(hv_hits) * 5, 15)
        reasons.append(f"project type: {hv_hits[0]}")
        project_signals["project_type"] = hv_hits[0]

    # ── Dollar value extraction ────────────────────────────────────────
    dollar_match = re.search(
        r"\$[\d,]+(?:\.\d+)?[KMkm]?\b|\d+(?:\.\d+)?\s*(?:million|M\b)",
        full_text, re.IGNORECASE
    )
    if dollar_match:
        project_signals["value_hint"] = dollar_match.group(0)
        score += 5
        reasons.append(f"value: {dollar_match.group(0)}")

    # ── Deadline extraction ────────────────────────────────────────────
    deadline_match = re.search(
        r"(?:due|submit|deadline|by)\s+(?:on\s+)?(\w+\s+\d+|\d+[/-]\d+[/-]\d+)",
        full_text, re.IGNORECASE
    )
    if deadline_match:
        project_signals["deadline_hint"] = deadline_match.group(1)

    # ── Subject line bonus ─────────────────────────────────────────────
    subj_lower = subject.lower()
    if any(kw.lower() in subj_lower for kw in ["rfq", "rfp", "itb", "bid", "quote", "proposal"]):
        score += 10
        reasons.append("bid keyword in subject line")

    score = max(0, min(100, score))
    tier = "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"

    return {
        "score": score,
        "tier": tier,
        "reasons": reasons[:4],  # top 4 reasons
        "is_bid": is_bid,
        "project_signals": project_signals,
        "disqualified": False,
    }


# ── Database ───────────────────────────────────────────────────────────

def _init_db():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bid_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT UNIQUE,
            subject TEXT,
            sender TEXT,
            received_at TEXT,
            score INTEGER,
            tier TEXT,
            reasons TEXT,
            project_signals TEXT,
            body_preview TEXT,
            actioned INTEGER DEFAULT 0,
            scanned_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _save_lead(lead: dict) -> bool:
    """Save a bid lead. Returns True if new, False if already exists."""
    _init_db()
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("""
            INSERT OR IGNORE INTO bid_leads
            (email_id, subject, sender, received_at, score, tier,
             reasons, project_signals, body_preview, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["email_id"], lead["subject"], lead["sender"],
            lead["received_at"], lead["score"], lead["tier"],
            json.dumps(lead.get("reasons", [])),
            json.dumps(lead.get("project_signals", {})),
            lead.get("body_preview", "")[:500],
            datetime.now(timezone.utc).isoformat(),
        ))
        affected = conn.total_changes
        conn.commit()
        conn.close()
        return affected > 0
    except Exception:
        return False


def get_leads(tier: str = "", limit: int = 10, unactioned: bool = True) -> list[dict]:
    """Get bid leads from database."""
    _init_db()
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        clauses = []
        params = []
        if tier:
            clauses.append("tier = ?")
            params.append(tier)
        if unactioned:
            clauses.append("actioned = 0")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM bid_leads {where} ORDER BY score DESC, received_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def mark_actioned(email_id: str):
    _init_db()
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("UPDATE bid_leads SET actioned = 1 WHERE email_id = ?", (email_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Outlook Scanner (win32com, Windows EXE) ───────────────────────────

def scan_outlook(days_back: int = 3, max_emails: int = 200) -> dict:
    """Scan Outlook inbox for bid leads via win32com."""
    try:
        import win32com.client
    except ImportError:
        return {"error": "win32com not available. Run: pip install pywin32",
                "scanned": 0, "leads": []}

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # 6 = Inbox
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)  # newest first

        cutoff = datetime.now() - timedelta(days=days_back)  # vj: duration-math
        scanned = 0
        new_leads = []

        for msg in messages:
            try:
                received = msg.ReceivedTime
                # win32com dates are COM objects
                if hasattr(received, "year"):
                    if received.replace(tzinfo=None) < cutoff:
                        break  # sorted newest first, stop when past cutoff
                subject = str(msg.Subject or "")
                sender = str(msg.SenderEmailAddress or "")
                body = str(msg.Body or "")[:3000]
                email_id = str(msg.EntryID or "")

                result = score_email(subject, body, sender)
                scanned += 1

                if result["tier"] in ("HIGH", "MEDIUM"):
                    lead = {
                        "email_id": email_id,
                        "subject": subject,
                        "sender": sender,
                        "received_at": str(received)[:19],
                        "score": result["score"],
                        "tier": result["tier"],
                        "reasons": result["reasons"],
                        "project_signals": result["project_signals"],
                        "body_preview": body[:300],
                    }
                    is_new = _save_lead(lead)
                    if is_new:
                        new_leads.append(lead)

                if scanned >= max_emails:
                    break
            except Exception:
                continue

        return {
            "scanned": scanned,
            "new_leads": len(new_leads),
            "leads": new_leads,
            "backend": "outlook_com",
        }
    except Exception as e:
        return {"error": str(e), "scanned": 0, "leads": []}


# ── Project-specific Email Search ─────────────────────────────────────

def search_emails_by_query(query: str, days_back: int = 7, max_results: int = 5) -> list:
    """Search Outlook inbox for emails matching a query string.
    Used by the auto-pipeline to find email chains related to a project
    before asking clarifying questions. Returns list of matching emails.
    Searches the Owner's mailbox via Joseph's delegated access."""
    try:
        import win32com.client
    except ImportError:
        return []

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")

        # Search the Owner's inbox (Joseph has delegated access)
        try:
            recipient = ns.CreateRecipient("owner@yourcompany.example.com")
            recipient.Resolve()
            if recipient.Resolved:
                inbox = ns.GetSharedDefaultFolder(recipient, 6)
            else:
                inbox = ns.GetDefaultFolder(6)
        except Exception:
            inbox = ns.GetDefaultFolder(6)

        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)

        cutoff = datetime.now() - timedelta(days=days_back)  # vj: duration-math
        query_words = [w for w in query.lower().split() if len(w) > 2]
        results = []

        for msg in messages:
            try:
                received = msg.ReceivedTime
                if hasattr(received, "year"):
                    if received.replace(tzinfo=None) < cutoff:
                        break
                subject = str(msg.Subject or "")
                sender = str(msg.SenderEmailAddress or "")
                body = str(msg.Body or "")[:3000]
                combined = (subject + " " + body).lower()

                if any(w in combined for w in query_words):
                    results.append({
                        "subject": subject,
                        "sender": sender,
                        "date": str(received)[:10],
                        "body": body,
                    })
                    if len(results) >= max_results:
                        break
            except Exception:
                continue

        return results
    except Exception:
        return []


# ── IMAP Scanner (email fallback) ─────────────────────────────────────

def scan_imap(host: str, username: str, password: str,
              folder: str = "INBOX", days_back: int = 3) -> dict:
    """Scan any IMAP mailbox for bid leads."""
    import imaplib
    import email as email_lib
    from email.header import decode_header

    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(username, password)
        mail.select(folder)

        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")  # vj: duration-math
        _, data = mail.search(None, f"(SINCE {cutoff})")
        email_ids = data[0].split()

        scanned = 0
        new_leads = []

        for eid in reversed(email_ids[-200:]):  # newest 200
            try:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = email_lib.message_from_bytes(msg_data[0][1])

                # Decode subject
                raw_subject = msg.get("Subject", "")
                subject = ""
                for part, enc in decode_header(raw_subject):
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += str(part)

                sender = msg.get("From", "")

                # Extract body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                            if len(body) > 3000:
                                break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
                body = body[:3000]

                result = score_email(subject, body, sender)
                scanned += 1

                if result["tier"] in ("HIGH", "MEDIUM"):
                    lead = {
                        "email_id": eid.decode(),
                        "subject": subject[:200],
                        "sender": sender[:100],
                        "received_at": msg.get("Date", "")[:19],
                        "score": result["score"],
                        "tier": result["tier"],
                        "reasons": result["reasons"],
                        "project_signals": result["project_signals"],
                        "body_preview": body[:300],
                    }
                    is_new = _save_lead(lead)
                    if is_new:
                        new_leads.append(lead)
            except Exception:
                continue

        mail.logout()
        return {
            "scanned": scanned,
            "new_leads": len(new_leads),
            "leads": new_leads,
            "backend": "imap",
        }
    except Exception as e:
        return {"error": str(e), "scanned": 0, "leads": []}


def get_daily_summary() -> dict:
    """Get today's bid lead summary for the dashboard."""
    high = get_leads(tier="HIGH", limit=5)
    medium = get_leads(tier="MEDIUM", limit=5)
    all_unactioned = get_leads(limit=20)
    return {
        "high_priority": high,
        "medium_priority": medium,
        "total_unactioned": len(all_unactioned),
        "last_scan": _last_scan_time(),
    }


def _last_scan_time() -> str:
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        row = conn.execute(
            "SELECT MAX(scanned_at) FROM bid_leads"
        ).fetchone()
        conn.close()
        return row[0][:16] if row and row[0] else "Never"
    except Exception:
        return "Never"
