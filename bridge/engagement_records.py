"""
Engagement Records - TCPA Compliance Gate
==========================================
Before any external iMessage can be drafted, the contact must have a
logged prior engagement (email reply, in-person meeting, referral).

No record = no draft = no send.

Storage: virtualoffice/data/engagement_records/
Format: One JSON file per contact, keyed by phone number.

This is the paper trail. If anyone challenges an outbound iMessage,
the record shows the contact engaged with Your Company first.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("engagement_records")

_SANDBOX = os.environ.get("YOURCO_SANDBOX", "")
if _SANDBOX:
    _RECORDS_DIR = Path(__file__).resolve().parent.parent / "data" / "engagement_records"
else:
    _RECORDS_DIR = Path(__file__).resolve().parent.parent / "data" / "engagement_records"

# Valid engagement types that establish contact permission
VALID_ENGAGEMENT_TYPES = {
    "email_reply",       # Contact replied to a Your Company email
    "inbound_email",     # Contact emailed Your Company first
    "in_person_meeting", # Met at job site, trade event, office visit
    "phone_call",        # Contact called or returned a call
    "referral",          # Introduced by a mutual contact
    "bid_invitation",    # Contact invited Your Company to bid
}


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to +1XXXXXXXXXX format."""
    digits = re.sub(r"[^\d]", "", phone)
    if len(digits) == 10:
        return "+1" + digits
    elif len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return phone.strip()


def _record_path(phone: str) -> Path:
    """Get the file path for a contact's engagement record."""
    safe_name = _normalize_phone(phone).replace("+", "").replace("-", "")
    return _RECORDS_DIR / f"{safe_name}.json"


def get_record(phone: str) -> Optional[Dict]:
    """Get engagement record for a phone number. Returns None if no record."""
    path = _record_path(phone)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.error("Failed to read engagement record %s: %s", path, e)
        return None


def has_engagement(phone: str) -> bool:
    """Check if a contact has a valid engagement record on file."""
    record = get_record(phone)
    if not record:
        return False
    # Must have a valid engagement type
    eng_type = record.get("engagement_type", "")
    return eng_type in VALID_ENGAGEMENT_TYPES


def create_record(contact_name: str, company: str, phone: str,
                  engagement_type: str, engagement_date: str,
                  engagement_detail: str, logged_by: str = "") -> Dict:
    """Create or update an engagement record for a contact.

    Args:
        contact_name: Full name of the contact
        company: Company name
        phone: Phone number (any format, gets normalized)
        engagement_type: One of VALID_ENGAGEMENT_TYPES
        engagement_date: Date of engagement (YYYY-MM-DD)
        engagement_detail: Description of the engagement
        logged_by: Email of person creating the record

    Returns:
        The created record dict, or error dict.
    """
    if engagement_type not in VALID_ENGAGEMENT_TYPES:
        return {
            "error": f"Invalid engagement type: {engagement_type}",
            "valid_types": sorted(VALID_ENGAGEMENT_TYPES),
        }

    normalized = _normalize_phone(phone)
    if len(re.sub(r"[^\d]", "", normalized)) < 10:
        return {"error": f"Invalid phone number: {phone}"}

    _RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "contact_name": contact_name.strip(),
        "company": company.strip(),
        "phone": normalized,
        "engagement_type": engagement_type,
        "engagement_date": engagement_date,
        "engagement_detail": engagement_detail.strip(),
        "logged_by": logged_by or "system",
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }

    # If record already exists, append to engagement history
    existing = get_record(normalized)
    if existing:
        history = existing.get("history", [])
        # Move current top-level engagement to history
        history.append({
            "engagement_type": existing.get("engagement_type"),
            "engagement_date": existing.get("engagement_date"),
            "engagement_detail": existing.get("engagement_detail"),
            "logged_by": existing.get("logged_by"),
            "logged_at": existing.get("logged_at"),
        })
        record["history"] = history
    else:
        record["history"] = []

    path = _record_path(normalized)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    log.info("Engagement record created for %s (%s): %s",
             contact_name, normalized, engagement_type)

    return record


def create_from_email_reply(sender_name: str, sender_company: str,
                            sender_phone: str, email_subject: str,
                            reply_date: str) -> Dict:
    """Auto-create engagement record when a contact replies to a Your Company email.
    This is the most common path. Contact replied = documented prior engagement.
    """
    return create_record(
        contact_name=sender_name,
        company=sender_company,
        phone=sender_phone,
        engagement_type="email_reply",
        engagement_date=reply_date,
        engagement_detail=f"Replied to Your Company email re: {email_subject}",
        logged_by="system",
    )


def create_from_meeting(contact_name: str, company: str, phone: str,
                        event: str, notes: str, date: str,
                        logged_by: str = "") -> Dict:
    """Create engagement record from in-person meeting.
    Owner types: 'Follow up with John from ABC - met at AISC expo'
    """
    return create_record(
        contact_name=contact_name,
        company=company,
        phone=phone,
        engagement_type="in_person_meeting",
        engagement_date=date,
        engagement_detail=f"Met at {event}. {notes}".strip(),
        logged_by=logged_by,
    )


def list_records(limit: int = 50) -> List[Dict]:
    """List all engagement records, most recent first."""
    _RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(_RECORDS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
        if len(records) >= limit:
            break
    return records


def find_by_name(name: str) -> Optional[Dict]:
    """Find an engagement record by contact name (case-insensitive).

    Used when the iMessage flow receives a contact name from the user instead
    of a phone number. Scans all records and returns the most recent match.

    Returns the full record dict, or None if no match.
    """
    if not name or not name.strip():
        return None
    target = name.strip().lower()
    # First try exact match on contact_name
    for rec in list_records(limit=500):
        rec_name = (rec.get("contact_name") or "").strip().lower()
        if rec_name == target:
            return rec
    # Fall back to substring match
    for rec in list_records(limit=500):
        rec_name = (rec.get("contact_name") or "").strip().lower()
        if target in rec_name or rec_name in target:
            return rec
    return None


def delete_record(phone: str) -> bool:
    """Delete an engagement record. Returns True if deleted."""
    path = _record_path(phone)
    if path.exists():
        path.unlink()
        log.info("Engagement record deleted for %s", phone)
        return True
    return False


def check_and_gate(phone: str) -> Dict:
    """Check engagement record and return gate result.
    Used by send_imessage_to_contact before drafting.

    Returns:
        {allowed: bool, record: dict or None, reason: str}
    """
    record = get_record(phone)
    if not record:
        return {
            "allowed": False,
            "record": None,
            "reason": (
                "Blocked. No engagement record on file for this contact. "
                "Sending iMessage to contacts who have not initiated or replied "
                "to prior contact is a TCPA violation. Penalties start at $500 per message.\n\n"
                "Compliant alternative: If this contact replied to an email or "
                "met you in person, log the engagement first with: "
                "log_engagement(name, company, phone, type, date, detail)"
            ),
        }

    eng_type = record.get("engagement_type", "")
    if eng_type not in VALID_ENGAGEMENT_TYPES:
        return {
            "allowed": False,
            "record": record,
            "reason": f"Engagement type '{eng_type}' is not a valid basis for contact.",
        }

    return {
        "allowed": True,
        "record": record,
        "reason": f"Prior engagement: {eng_type} on {record.get('engagement_date', 'unknown date')}",
    }
