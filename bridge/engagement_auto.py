"""Auto-create engagement records from Gmail replies.

When a contact replies to a Your Company email, that counts as a documented
prior business engagement under TCPA. This module extracts the contact
info from email message metadata and proposes (or creates) engagement
records suitable for the TCPA gate on send_imessage_to_contact.

Workflow:
    1. Gmail MCP (or any source) returns a list of message dicts.
    2. scan_messages_for_engagements(messages, dry_run=True) returns
       a list of proposals - what would be created.
    3. Caller reviews and re-invokes with dry_run=False to commit.

This module does NOT call Gmail directly - it accepts message data as
input so it can be tested without external dependencies. Gmail wiring
lives in the Bridge layer.
"""


import re
import datetime as _dt
from typing import List, Dict, Any, Optional, Tuple

from . import engagement_records


# ─── Sender parsing ─────────────────────────────────────────────────
# RFC 5322 "From" header forms:
#   Mike Verdugo <mike@verdugoconstruction.com>
#   "Mike Verdugo" <mike@verdugoconstruction.com>
#   mike@verdugoconstruction.com
_FROM_RE = re.compile(
    r"""^
    (?:                              # optional display name
        "?(?P<name>[^"<>]+?)"?\s+
    )?
    <(?P<email>[^<>\s]+@[^<>\s]+)>   # email in brackets
    | (?P<bare>[^<>\s]+@[^<>\s]+)    # OR bare email only
    $""",
    re.VERBOSE,
)


def _parse_from_header(from_header: str) -> Tuple[str, str]:
    """Parse "From:" header into (display_name, email).

    Display name is best-effort. Email is the @ part inside brackets,
    or the bare email if no brackets present.
    """
    if not from_header:
        return ("", "")
    s = from_header.strip()
    m = _FROM_RE.match(s)
    if not m:
        # Loose fallback: find anything that looks like an email
        em = re.search(r"[^<>\s]+@[^<>\s]+", s)
        return ("", em.group(0) if em else "")
    if m.group("email"):
        return ((m.group("name") or "").strip(), m.group("email").strip())
    # bare email only
    return ("", (m.group("bare") or "").strip())


# Common consumer domains that don't represent a company
_CONSUMER_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "live.com", "msn.com", "comcast.net", "att.net", "verizon.net",
    "sbcglobal.net", "me.com", "mac.com", "protonmail.com", "pm.me",
}


def _company_from_email(email: str) -> str:
    """Infer company name from email domain.

    Strips consumer domains and TLD. 'mike@verdugoconstruction.com' →
    'Verdugoconstruction'. For consumer domains, returns empty string.
    """
    if "@" not in email:
        return ""
    domain = email.split("@", 1)[1].strip().lower()
    if domain in _CONSUMER_DOMAINS:
        return ""
    # Strip subdomains and TLD: mail.acme-steel.com → acme-steel
    parts = domain.split(".")
    if len(parts) >= 2:
        candidate = parts[-2]  # second-level domain
    else:
        candidate = parts[0]
    # Title-case, replacing dashes with spaces
    return candidate.replace("-", " ").title()


# ─── Phone extraction ────────────────────────────────────────────────
# US phone patterns: 713-300-1865, (713) 300-1865, 7133001865, +1 713 300 1865
_PHONE_RE = re.compile(
    r"""
    (?:\+?1[-.\s]?)?            # optional country code
    \(?(?P<area>[2-9]\d{2})\)?  # area code 200-999
    [-.\s]?
    (?P<mid>[2-9]\d{2})         # exchange
    [-.\s]?
    (?P<end>\d{4})              # subscriber
    """,
    re.VERBOSE,
)


def _extract_phone_from_text(text: str) -> Optional[str]:
    """Find first US phone number in text. Returns normalized 10-digit string."""
    if not text:
        return None
    m = _PHONE_RE.search(text)
    if not m:
        return None
    return m.group("area") + m.group("mid") + m.group("end")


# ─── Main extraction ────────────────────────────────────────────────
def extract_contact_from_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Extract contact info from a single Gmail message dict.

    Expected message keys (any subset; tolerant of missing fields):
        from:      "From:" header string
        subject:   subject line
        body:      plain-text body (used for phone extraction)
        date:      date string (any format)
        thread_id: optional, for dedup

    Returns dict with: contact_name, sender_email, company, phone, subject, date.
    """
    from_h = message.get("from", "") or message.get("From", "")
    name, email = _parse_from_header(from_h)
    body = message.get("body", "") or message.get("Body", "")
    subject = message.get("subject", "") or message.get("Subject", "")
    date = message.get("date", "") or message.get("Date", "") or \
        _dt.datetime.now().strftime("%Y-%m-%d")  # vj: local-display-ok

    # Phone: try body first, then the "From" header (unusual but possible)
    phone = _extract_phone_from_text(body) or _extract_phone_from_text(from_h)

    # Company: prefer signature inference, fall back to domain
    company = _company_from_email(email)

    return {
        "contact_name": name or email.split("@", 1)[0] if email else "",
        "sender_email": email,
        "company": company,
        "phone": phone or "",
        "subject": subject,
        "date": date,
        "thread_id": message.get("thread_id", ""),
        "has_phone": bool(phone),
    }


def propose_engagement(message: Dict[str, Any]) -> Dict[str, Any]:
    """Decide whether an engagement record should be created for this message.

    Returns dict with:
        action:   'create' | 'skip' | 'exists' | 'no_phone' | 'no_sender'
        contact:  the extracted contact info
        reason:   short explanation
    """
    contact = extract_contact_from_message(message)

    if not contact["sender_email"]:
        return {"action": "no_sender", "contact": contact,
                "reason": "No parseable sender email"}

    if not contact["has_phone"]:
        return {"action": "no_phone", "contact": contact,
                "reason": "No phone number in body or headers (can't gate iMessage without one)"}

    # Check for existing record
    if engagement_records.has_engagement(contact["phone"]):
        return {"action": "exists", "contact": contact,
                "reason": f"Engagement record already exists for {contact['phone']}"}

    return {"action": "create", "contact": contact,
            "reason": "New contact with phone, will create engagement record"}


def scan_messages_for_engagements(messages: List[Dict[str, Any]],
                                  dry_run: bool = True) -> Dict[str, Any]:
    """Process a batch of Gmail messages. Returns proposals + optionally creates.

    When dry_run=True (default), no records are created. Use this to preview.
    When dry_run=False, records flagged 'create' are created via
    engagement_records.create_from_email_reply.
    """
    proposals = []
    created = []
    errors = []

    for msg in messages:
        try:
            proposal = propose_engagement(msg)
        except Exception as e:
            errors.append({"error": str(e), "message_preview": str(msg)[:80]})
            continue
        proposals.append(proposal)

        if proposal["action"] == "create" and not dry_run:
            c = proposal["contact"]
            try:
                rec = engagement_records.create_from_email_reply(
                    sender_name=c["contact_name"],
                    sender_company=c["company"],
                    sender_phone=c["phone"],
                    email_subject=c["subject"],
                    reply_date=c["date"],
                )
                created.append({"phone": c["phone"], "name": c["contact_name"],
                                "result": rec})
            except Exception as e:
                errors.append({"phone": c["phone"], "error": str(e)})

    # Summary counts
    counts = {"create": 0, "skip": 0, "exists": 0, "no_phone": 0, "no_sender": 0}
    for p in proposals:
        counts[p["action"]] = counts.get(p["action"], 0) + 1

    return {
        "ok": True,
        "dry_run": dry_run,
        "scanned": len(messages),
        "counts": counts,
        "proposals": proposals,
        "created": created,
        "errors": errors,
    }
