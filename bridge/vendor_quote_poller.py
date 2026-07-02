"""
Vendor Quote Poller - Data Fabric Layer

Polls the Owner's Outlook for incoming steel vendor quotes. Filters by
sender whitelist, captures quote metadata + attachments, surfaces to UI.

Confirmed active vendors (from Outlook scan, 2026-05-13):
  - Gerdau (mill direct, Midlothian TX)
  - Intsel Steel / SSS Steel (service center, Houston)
  - Brown Strauss (service center)
  - Nucor (Centria panels via Timothy Leach)

Mailbox: owner@yourcompany.example.com (Outlook on Win11, local COM)
Cadence: hourly during business hours (M-F 7am-6pm CT)
Document numbering: NC-{YYYY}-VQ-{NNN}

Win11 deployment: uses win32com.client.Dispatch("Outlook.Application")
which reads the already-signed-in local Outlook session. No msal tokens,
no API permissions, no auth setup. Outlook must be running.

This is the solid-and-simple path. See vendor_quote_poller_test.py for
mock-based testing on non-Windows dev machines.
"""
import json
import re
import sys
from datetime import datetime, timedelta, time, timezone
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# CACHE / STATE FILES
# ─────────────────────────────────────────────────────────────────

_DATA = Path(__file__).resolve().parent.parent / "data"
_QUOTES_FILE     = _DATA / "vendor_quotes.json"
_WHITELIST_FILE  = _DATA / "vendor_whitelist.json"
_POLLER_STATE    = _DATA / "vendor_poller_state.json"
_ATTACHMENT_DIR  = _DATA / "vendor_quote_attachments"

# ─────────────────────────────────────────────────────────────────
# INITIAL WHITELIST (locked from the Owner's Outlook scan)
# ─────────────────────────────────────────────────────────────────

_DEFAULT_WHITELIST = [
    {
        "domain": "gerdau.com",
        "vendor_name": "Gerdau",
        "vendor_type": "mill",
        "location": "Midlothian TX",
        "known_contacts": [
            "brayden.gray@gerdau.com",
            "angela.mucobega@gerdau.com",
            "heidi.ibrahim@gerdau.com",
        ],
        "quote_format": "inline body",
        "payment_terms": "prepay",
        "added_at": "2026-05-13",
    },
    {
        "domain": "intselsteel.com",
        "vendor_name": "Intsel Steel",
        "vendor_type": "service_center",
        "location": "Houston TX (11310 W Little York)",
        "known_contacts": ["guy.freund@intselsteel.com"],
        "quote_format": "pdf attachment",
        "pricing_unit": "CWT",
        "payment_terms": "prepay",
        "added_at": "2026-05-13",
    },
    {
        "domain": "sss-steel.com",
        "vendor_name": "SSS Steel (Intsel brand)",
        "vendor_type": "service_center",
        "location": "Houston TX",
        "known_contacts": ["guy.freund@intselsteel.com"],
        "quote_format": "pdf attachment",
        "pricing_unit": "CWT",
        "payment_terms": "prepay",
        "added_at": "2026-05-13",
    },
    {
        "domain": "brownstrauss.com",
        "vendor_name": "Brown Strauss",
        "vendor_type": "service_center",
        "location": "TX territory",
        "known_contacts": [
            "AParker@brownstrauss.com",
            "MPluemer@brownstrauss.com",
        ],
        "quote_format": "pdf attachment",
        "subject_pattern": "Quote of Materials for Your Company",
        "added_at": "2026-05-13",
    },
    {
        "domain": "nucor.com",
        "vendor_name": "Nucor",
        "vendor_type": "mill",
        "location": "national",
        "known_contacts": [
            "Brandon.Strong@nucor.com",
            "Timothy.Leach@nucor.com",
        ],
        "quote_format": "inline body",
        "notes": "Direct mill currently declining; Centria panels active via Timothy Leach.",
        "added_at": "2026-05-13",
    },
]

# ─────────────────────────────────────────────────────────────────
# BUSINESS HOURS GATE (M-F 7am-6pm CT)
# ─────────────────────────────────────────────────────────────────

def _is_business_hours(now: datetime = None) -> bool:
    """True if now is M-F 7am-6pm Central Time (Houston)."""
    n = now or datetime.now()  # vj: local-time-ok
    if n.weekday() >= 5:  # Saturday/Sunday
        return False
    return time(7, 0) <= n.time() < time(18, 0)

# ─────────────────────────────────────────────────────────────────
# JSON FILE HELPERS
# ─────────────────────────────────────────────────────────────────

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))

# ─────────────────────────────────────────────────────────────────
# WHITELIST OPERATIONS
# ─────────────────────────────────────────────────────────────────

def _ensure_whitelist():
    """Initialize whitelist on first run."""
    if not _WHITELIST_FILE.exists():
        _save_json(_WHITELIST_FILE, _DEFAULT_WHITELIST)
    return _load_json(_WHITELIST_FILE, _DEFAULT_WHITELIST)

def get_whitelist() -> list:
    return _ensure_whitelist()

def get_whitelist_domains() -> set:
    return {entry["domain"].lower() for entry in _ensure_whitelist()}

def add_to_whitelist(domain: str, vendor_name: str = "",
                     vendor_type: str = "service_center", notes: str = "") -> dict:
    domain = domain.lower().strip()
    if "@" in domain:
        domain = domain.split("@", 1)[1]
    wl = _ensure_whitelist()
    if any(e["domain"] == domain for e in wl):
        return {"added": False, "reason": "already in whitelist", "domain": domain}
    entry = {
        "domain": domain,
        "vendor_name": vendor_name or domain.split(".")[0].title(),
        "vendor_type": vendor_type,
        "added_at": datetime.now().date().isoformat(),  # vj: local-time-ok
    }
    if notes:
        entry["notes"] = notes
    wl.append(entry)
    _save_json(_WHITELIST_FILE, wl)
    return {"added": True, "domain": domain, "entry": entry}

def _sender_matches_whitelist(sender_email: str) -> dict | None:
    if not sender_email or "@" not in sender_email:
        return None
    domain = sender_email.split("@", 1)[1].lower()
    for entry in _ensure_whitelist():
        if entry["domain"].lower() == domain:
            return entry
    return None

# ─────────────────────────────────────────────────────────────────
# QUOTE PARSING (signal detection, not full extraction)
# ─────────────────────────────────────────────────────────────────

_QUOTE_SIGNALS = [
    "quote", "quoted", "quoting", "pricing", "price list",
    "per cwt", "$/cwt", "/cwt", "lead time", "in stock",
    "credit application", "rolling", "prepay",
]

_PROJECT_REF_RE = re.compile(
    r"^(?:RE:|FW:|Fw:|Re:|Fwd:)?\s*(.+?)(?:\s*[-—]\s*|\s*\|\s*|$)",
    re.IGNORECASE,
)

def _extract_project_ref(subject: str) -> str:
    """Pull project name from subject. Strips RE:/FW: prefixes."""
    if not subject:
        return ""
    m = _PROJECT_REF_RE.match(subject.strip())
    if m:
        candidate = m.group(1).strip()
        # Drop boilerplate
        for boiler in ["Quote of Materials for Your Company",
                       "Direct Mill Purchase Request",
                       "Credit Application",
                       "YOUR COMPANY"]:
            if boiler.lower() in candidate.lower():
                candidate = candidate.replace(boiler, "").strip(" -|—:")
        return candidate[:120]
    return subject[:120]

def _detect_quote_signals(subject: str, body: str) -> list:
    """Return list of quote-relevant signals found in the email."""
    text = (subject + " " + body).lower()
    return [sig for sig in _QUOTE_SIGNALS if sig in text]

# ─────────────────────────────────────────────────────────────────
# DOCUMENT NUMBERING (NC-{YYYY}-VQ-{NNN})
# ─────────────────────────────────────────────────────────────────

def _next_doc_number(quotes: list) -> str:
    year = datetime.now().year  # vj: local-time-ok
    pattern = re.compile(rf"^NC-{year}-VQ-(\d+)$")
    existing = [int(m.group(1)) for q in quotes
                if (m := pattern.match(q.get("doc_number", "")))]
    next_n = (max(existing) + 1) if existing else 1
    return f"NC-{year}-VQ-{next_n:03d}"

# ─────────────────────────────────────────────────────────────────
# QUOTE STORAGE
# ─────────────────────────────────────────────────────────────────

def _load_quotes() -> list:
    return _load_json(_QUOTES_FILE, [])

def record_quote(sender_email: str, subject: str, body: str,
                 received_at: str, attachments: list = None,
                 message_id: str = "") -> dict:
    """Record a single quote. Returns the quote record."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.28; disjoint shapes)
    wl_entry = _sender_matches_whitelist(sender_email)
    if not wl_entry:
        return {"recorded": False, "reason": "sender not in whitelist",
                "sender": sender_email}
    quotes = _load_quotes()
    # Dedupe by message_id if provided
    if message_id and any(q.get("message_id") == message_id for q in quotes):
        return {"recorded": False, "reason": "duplicate message_id",
                "message_id": message_id}
    record = {
        "doc_number": _next_doc_number(quotes),
        "vendor_name": wl_entry["vendor_name"],
        "vendor_type": wl_entry["vendor_type"],
        "domain": wl_entry["domain"],
        "sender_email": sender_email,
        "project_ref": _extract_project_ref(subject),
        "subject": subject,
        "body_preview": (body or "")[:2000],
        "received_at": received_at,
        "message_id": message_id,
        "attachments": attachments or [],
        "signals": _detect_quote_signals(subject, body or ""),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "new",
    }
    quotes.append(record)
    _save_json(_QUOTES_FILE, quotes)
    return {"recorded": True, "doc_number": record["doc_number"],
            "vendor": record["vendor_name"], "project_ref": record["project_ref"]}

def get_quotes(vendor: str = None, project: str = None, days: int = 30,
               status: str = None) -> list:
    """Retrieve recorded quotes with optional filters."""
    quotes = _load_quotes()
    cutoff = datetime.now() - timedelta(days=days)  # vj: local-time-ok
    out = []
    for q in quotes:
        try:
            received = datetime.fromisoformat(q["received_at"].replace("Z", "+00:00").split("+")[0])
            if received < cutoff:
                continue
        except Exception:
            pass
        if vendor and vendor.lower() not in q.get("vendor_name", "").lower():
            continue
        if project and project.lower() not in q.get("project_ref", "").lower():
            continue
        if status and q.get("status") != status:
            continue
        out.append(q)
    return sorted(out, key=lambda x: x.get("received_at", ""), reverse=True)

# ─────────────────────────────────────────────────────────────────
# OUTLOOK COM POLLER (Win11 only)
# ─────────────────────────────────────────────────────────────────

def _get_outlook_inbox():
    """Get the Outlook Inbox folder via COM. Win11-only."""
    if sys.platform != "win32":
        return None, "not on Windows (poller requires Win11 Outlook)"
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        # 6 = olFolderInbox
        return outlook.GetDefaultFolder(6), None
    except ImportError:
        return None, "pywin32 not installed - run: pip install pywin32"
    except Exception as e:
        return None, f"Outlook COM unavailable: {str(e)[:200]}"

def _load_state() -> dict:
    return _load_json(_POLLER_STATE, {"last_poll_at": None, "last_processed_id": None})

def _save_state(state: dict):
    _save_json(_POLLER_STATE, state)

def poll_now(force: bool = False) -> dict:
    """Run one poll cycle. Returns summary dict.

    force=True bypasses business-hours gate. Use for manual invocation.
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.38; needs manual audit)
    if not force and not _is_business_hours():
        return {"polled": False, "reason": "outside business hours (M-F 7am-6pm CT)",
                "next_poll_window": "next weekday at 7am CT"}

    inbox, err = _get_outlook_inbox()
    if err:
        return {"polled": False, "reason": err, "fix":
                "ensure Outlook is running and pywin32 is installed"}

    state = _load_state()
    last_poll = state.get("last_poll_at")
    cutoff = datetime.fromisoformat(last_poll) if last_poll else \
             datetime.now() - timedelta(hours=2)  # vj: local-time-ok

    whitelist_domains = get_whitelist_domains()
    recorded = []
    skipped = 0
    _ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)  # newest first
        for item in items:
            try:
                received = item.ReceivedTime
                if hasattr(received, "replace"):
                    # COM datetime -> Python datetime
                    received_dt = datetime(received.year, received.month, received.day,
                                            received.hour, received.minute, received.second)
                else:
                    received_dt = datetime.now(timezone.utc)  # vj: utc-storage
                if received_dt < cutoff:
                    break  # sorted descending, so older items are past

                sender = (item.SenderEmailAddress or "").lower()
                if "@" not in sender or sender.split("@", 1)[1] not in whitelist_domains:
                    skipped += 1
                    continue

                # Save attachments
                saved_attachments = []
                try:
                    for att in item.Attachments:
                        fname = re.sub(r"[^\w.\-]", "_", att.FileName)[:120]
                        dest = _ATTACHMENT_DIR / f"{received_dt.strftime('%Y%m%d_%H%M%S')}_{fname}"
                        att.SaveAsFile(str(dest))
                        saved_attachments.append({"filename": att.FileName, "saved_path": str(dest)})
                except Exception:
                    pass

                result = record_quote(
                    sender_email=sender,
                    subject=item.Subject or "",
                    body=item.Body or "",
                    received_at=received_dt.isoformat(),
                    attachments=saved_attachments,
                    message_id=getattr(item, "EntryID", ""),
                )
                if result.get("recorded"):
                    recorded.append(result)
            except Exception:
                continue
    except Exception as e:
        return {"polled": False, "reason": f"inbox iteration failed: {str(e)[:200]}"}

    _save_state({"last_poll_at": datetime.now(timezone.utc).isoformat(),
                 "recorded_count": len(recorded),
                 "skipped_count": skipped})
    return {"polled": True, "recorded": recorded, "skipped": skipped,
            "whitelist_size": len(whitelist_domains),
            "polled_at": datetime.now(timezone.utc).isoformat()}

def poller_status() -> dict:
    """Quick status check: when did we last poll, how many quotes total."""
    state = _load_state()
    quotes = _load_quotes()
    wl = _ensure_whitelist()
    return {
        "last_poll_at": state.get("last_poll_at"),
        "total_quotes": len(quotes),
        "recent_quotes_30d": len(get_quotes(days=30)),
        "whitelist_size": len(wl),
        "whitelist_domains": [e["domain"] for e in wl],
        "business_hours_now": _is_business_hours(),
        "platform": sys.platform,
        "outlook_available": sys.platform == "win32",
    }

# ─────────────────────────────────────────────────────────────────
# MANUAL CLI (for Joseph's debugging on dev machine)
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json as _j
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(_j.dumps(poller_status(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "whitelist":
        print(_j.dumps(get_whitelist(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "poll":
        force = "--force" in sys.argv
        print(_j.dumps(poll_now(force=force), indent=2))
    else:
        print("Usage: python vendor_quote_poller.py [status|whitelist|poll [--force]]")
