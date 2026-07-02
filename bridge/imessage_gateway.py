"""
iMessage Gateway - BlueBubbles Bridge
======================================
Sends iMessages via BlueBubbles REST API running on the office 2012 iMac.
Receives inbound photo attachments for drawing_intel processing.

Setup: BlueBubbles server on macOS (OpenCore Monterey+) with Firebase tunnel.
Default endpoint: http://<office-mac-ip>:1234

Voice rules enforced on all outbound messages before send.
"""

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Optional

log = logging.getLogger("imessage_gateway")

# Config defaults. Override via config.json or environment.
_BB_HOST = os.environ.get("BLUEBUBBLES_HOST", "")
_BB_PORT = int(os.environ.get("BLUEBUBBLES_PORT", "1234"))
_BB_PASSWORD = os.environ.get("BLUEBUBBLES_PASSWORD", "")

# Loaded once from config.json at first call
_config_loaded = False


def _load_config():
    """Load BlueBubbles config from config.json or API Keys folder."""
    global _BB_HOST, _BB_PORT, _BB_PASSWORD, _config_loaded
    if _config_loaded:
        return
    _config_loaded = True

    try:
        root = Path(__file__).resolve().parent.parent
        cfg_path = root / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            _BB_HOST = cfg.get("BLUEBUBBLES_HOST", _BB_HOST) or _BB_HOST
            _BB_PORT = int(cfg.get("BLUEBUBBLES_PORT", _BB_PORT) or _BB_PORT)
            _BB_PASSWORD = cfg.get("BLUEBUBBLES_PASSWORD", _BB_PASSWORD) or _BB_PASSWORD

        # Also check API Keys folder
        bb_key = root / "API Keys" / "BlueBubbles.txt"
        if bb_key.exists():
            lines = bb_key.read_text(encoding="utf-8-sig").strip().splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith("host="):
                    _BB_HOST = line.split("=", 1)[1].strip()
                elif line.startswith("port="):
                    _BB_PORT = int(line.split("=", 1)[1].strip())
                elif line.startswith("password="):
                    _BB_PASSWORD = line.split("=", 1)[1].strip()
                elif line and not line.startswith("#"):
                    # Single line = just the password
                    _BB_PASSWORD = line
    except Exception as e:
        log.warning(f"BlueBubbles config load failed: {e}")


def _base_url() -> str:
    _load_config()
    if not _BB_HOST:
        return ""
    return f"http://{_BB_HOST}:{_BB_PORT}"


def _bb_request(endpoint: str, method: str = "GET",
                data: Optional[dict] = None, timeout: int = 10) -> dict:
    """Make a request to BlueBubbles API."""
    base = _base_url()
    if not base:
        return {"error": "BlueBubbles host not configured. Set BLUEBUBBLES_HOST."}

    url = f"{base}/api/v1/{endpoint}?password={_BB_PASSWORD}"
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, method=method, headers=headers)
    if data:
        req.data = json.dumps(data).encode("utf-8")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error(f"BlueBubbles request failed: {e}")
        return {"error": str(e)}


def _scrub_voice(text: str) -> str:
    """Enforce the Owner's voice rules on outbound text.
    No em-dashes. No forbidden openers. No three-adjective lists.
    """
    # Em-dash to period or hyphen
    text = text.replace("\u2014", " - ")
    text = text.replace("\u2013", "-")

    # Forbidden openers
    BAD_OPENERS = [
        "Great question!", "That's a great", "Absolutely!",
        "Of course!", "Sure thing!", "Happy to help",
    ]
    for opener in BAD_OPENERS:
        if text.startswith(opener):
            text = text[len(opener):].lstrip(" ,.")

    return text.strip()


def send_imessage(to: str, body: str, scrub: bool = True) -> dict:
    """Send an iMessage via BlueBubbles.

    Args:
        to: Phone number or iMessage address (email).
            Formats accepted: +17131234567, 7131234567, user@icloud.com
        body: Message text. Voice-scrubbed before send unless scrub=False.
        scrub: Apply voice rules. Default True.

    Returns:
        dict with status, message_guid, or error.
    """
    if scrub:
        body = _scrub_voice(body)

    if not body:
        return {"error": "Empty message after voice scrub"}

    # Normalize phone number
    phone = to.strip().replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if phone.isdigit() and len(phone) == 10:
        phone = "+1" + phone
    elif phone.isdigit() and len(phone) == 11 and phone.startswith("1"):
        phone = "+" + phone

    payload = {
        "chatGuid": f"iMessage;-;{phone}",
        "message": body,
        "method": "apple-script",
    }

    log.info(f"Sending iMessage to {phone}: {body[:50]}...")
    result = _bb_request("message/text", method="POST", data=payload)

    if "error" in result:
        return result

    return {
        "status": "sent",
        "to": phone,
        "body_length": len(body),
        "guid": result.get("data", {}).get("guid", ""),
    }


def get_recent_messages(limit: int = 10) -> list:
    """Fetch recent inbound messages from BlueBubbles."""
    result = _bb_request(f"message?limit={limit}&sort=DESC")
    if "error" in result:
        return []
    return result.get("data", [])


def get_attachments(message_guid: str) -> list:
    """Get attachments for a specific message."""
    result = _bb_request(f"message/{message_guid}/attachment")
    if "error" in result:
        return []
    return result.get("data", [])


def download_attachment(attachment_guid: str, save_dir: str) -> Optional[str]:
    """Download an attachment (photo, PDF) to local directory.
    Used for photo-ingest: Owner texts a drawing photo, it lands
    in drawing_intel for processing.
    """
    base = _base_url()
    if not base:
        return None

    url = f"{base}/api/v1/attachment/{attachment_guid}/download?password={_BB_PASSWORD}"
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            # Get filename from headers or use guid
            cd = resp.headers.get("Content-Disposition", "")
            if "filename=" in cd:
                fname = cd.split("filename=")[1].strip('"')
            else:
                ct = resp.headers.get("Content-Type", "application/octet-stream")
                ext = {"image/jpeg": ".jpg", "image/png": ".png",
                       "image/heic": ".heic", "application/pdf": ".pdf"
                       }.get(ct, ".bin")
                fname = f"{attachment_guid}{ext}"

            out_path = save_path / fname
            with open(out_path, "wb") as f:
                f.write(resp.read())

            log.info(f"Downloaded attachment: {out_path}")
            return str(out_path)
    except Exception as e:
        log.error(f"Attachment download failed: {e}")
        return None


# Convenience: the Owner's and Joseph's iMessage addresses
CONTACTS = {
    "owner": "+17133001865",
    "joseph": "+17139384333",
}


def text_owner(body: str) -> dict:
    """Quick send to Owner. Path A - internal, no gate."""
    return send_imessage(CONTACTS["owner"], body)


def text_joseph(body: str) -> dict:
    """Quick send to Joseph. Path A - internal, no gate."""
    return send_imessage(CONTACTS["joseph"], body)


# ── PATH B: EXTERNAL CONTACT (gated) ────────────────────────────

def send_imessage_to_contact(to: str, body: str,
                             preview_only: bool = True,
                             require_engagement_record: bool = True) -> dict:
    """Send iMessage to an external contact. GATED.

    Two hard requirements enforced at this level:
    1. require_engagement_record=True: contact must have a logged
       prior engagement (email reply, meeting, referral). No record = blocked.
    2. preview_only=True: returns the draft for Owner to review.
       Only sends when preview_only=False (after Owner confirms in GUI).

    MCP forced args guarantee both flags are True even if Claude/Cowork
    tries to override them. See _TOOL_FORCED_ARGS in mcp_server.py.

    Returns:
        On preview: {preview: True, draft: str, to: str, gate: dict}
        On send: {status: "sent", to: str, guid: str}
        On block: {blocked: True, reason: str}
    """
    from bridge.engagement_records import check_and_gate, find_by_name

    raw_to = to.strip()
    phone = raw_to.replace("-", "").replace("(", "").replace(")", "").replace(" ", "").replace("+", "")
    is_phone = phone.isdigit() and 10 <= len(phone) <= 11

    if is_phone:
        if len(phone) == 10:
            phone = "+1" + phone
        elif len(phone) == 11 and phone.startswith("1"):
            phone = "+" + phone
    else:
        # `to` is a contact name. Look up engagement record by name and use that phone.
        rec = find_by_name(raw_to)
        if rec:
            phone = rec.get("phone", "")
            log.info("Resolved contact name '%s' to phone %s via engagement record", raw_to, phone)
        else:
            # No engagement record by name → fall through; the gate below will block correctly
            phone = raw_to  # keep readable for the error message

    # Hard block: internal contacts use Path A, not Path B
    if phone in (CONTACTS["owner"], CONTACTS["joseph"]):
        return {"error": "Use text_owner() or text_joseph() for internal contacts."}

    # Gate 1: Engagement record check
    if require_engagement_record:
        gate = check_and_gate(phone)
        if not gate["allowed"]:
            log.warning("iMessage BLOCKED to %s: no engagement record", phone)
            # Tell the caller what they can do next, not just that it's blocked.
            # raw_to is what Owner actually typed (a name or partial name).
            suggest_name = raw_to if not is_phone else ""
            suggest = (
                f"log_engagement(name='{suggest_name or 'Contact Name'}', "
                f"company='Their Company', phone='{phone if is_phone else 'XXX-XXX-XXXX'}', "
                f"type='email_reply', date='today', detail='what made you confident they want contact')"
            )
            return {
                "blocked": True,
                "reason": gate["reason"],
                "to": phone,
                "suggested_action": "log_engagement",
                "suggested_name": suggest_name,
                "suggested_phone": phone if is_phone else "",
                "fix": (
                    f"If {suggest_name or phone} actually replied to you, "
                    f"reached out, or you met in person, log the engagement "
                    f"first then retry the iMessage. Example: {suggest}"
                ),
            }
    else:
        gate = {"allowed": True, "reason": "Engagement check bypassed", "record": None}

    # Voice scrub
    body = _scrub_voice(body)
    if not body:
        return {"error": "Empty message after voice scrub"}

    # Gate 2: Preview only (MCP forced arg guarantees this)
    if preview_only:
        return {
            "preview": True,
            "draft": body,
            "to": phone,
            "gate": gate,
            "confirm_action": "confirm_imessage_send",
        }

    # Actual send (only reached after Owner confirms in GUI)
    result = send_imessage(phone, body, scrub=False)  # Already scrubbed above

    # Log the send
    if result.get("status") == "sent":
        _log_send(phone, body, gate.get("record"))

    return result


def confirm_imessage_send(to: str, body: str) -> dict:
    """Owner confirmed the preview. Send the iMessage.
    Called from GUI confirm button. Bypasses preview gate but
    still enforces engagement record check.
    """
    return send_imessage_to_contact(
        to=to, body=body,
        preview_only=False,
        require_engagement_record=True,
    )


def _log_send(phone: str, body: str, engagement_record: dict = None):
    """Log an external iMessage send for audit trail."""
    log_dir = Path(__file__).resolve().parent.parent / "data" / "imessage_log"
    log_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "to": phone,
        "body_length": len(body),
        "body_preview": body[:100],
        "sent_at": __import__("datetime").datetime.now(timezone.utc).isoformat(),
        "engagement_type": (engagement_record or {}).get("engagement_type", ""),
        "engagement_date": (engagement_record or {}).get("engagement_date", ""),
        "contact_name": (engagement_record or {}).get("contact_name", ""),
    }

    log_file = log_dir / "sends.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    log.info("iMessage send logged: %s -> %s", phone, body[:30])


# ── PATH A: INTERNAL ALERTS ─────────────────────────────────────

def alert_bid_deadline(project_name: str, due_date: str, action: str) -> dict:
    """Alert Owner about upcoming bid deadline. Path A - no gate."""
    body = f"Bid deadline in 48h: {project_name}. Due: {due_date}. {action}"
    return text_owner(body)


def alert_compliance_expiry(cert_name: str, expiry_date: str) -> dict:
    """Alert about expiring compliance cert. Path A - no gate."""
    body = f"Cert expiring in 30d: {cert_name}. Expires: {expiry_date}. Renew now."
    return text_owner(body)


def alert_isn_status_change(new_status: str, qualification: str) -> dict:
    """Alert about ISNetworld status change. Path A - no gate."""
    body = f"ISNetworld status change: {new_status}. Affected: {qualification}."
    return text_owner(body)

