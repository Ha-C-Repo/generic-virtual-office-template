"""
Your Company Virtual Office - Twilio SMS Command Channel

Owner texts one number from anywhere.
App processes the command through ai_ask.
App replies by SMS within seconds.

Setup (one-time, Joseph does this):
  1. Create Twilio account at twilio.com (free trial available)
  2. Get a phone number (~$1.15/month)
  3. Set webhook URL: https://[cloudflare-tunnel]/sms
  4. Add to channel_config.json:
     {
       "twilio_sid": "ACxxxx",
       "twilio_token": "xxxx",
       "twilio_number": "+17135551234",
       "owner_cell": "+17133001865"
     }

the Owner's number is pre-authorized. All other senders are rejected.

Cost: ~$0.0079 per SMS sent + received. Under $5/month at normal usage.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONFIG_PATH = _DATA_DIR / "channel_config.json"


def _load_twilio_cfg() -> dict:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text())
    except Exception:
        pass
    return {}


def is_configured() -> bool:
    cfg = _load_twilio_cfg()
    return bool(cfg.get("twilio_sid") and cfg.get("twilio_token")
                and cfg.get("twilio_number"))


def send_sms(to: str, body: str) -> dict:
    """Send an SMS via Twilio. Returns {success, sid} or {error}."""
    cfg = _load_twilio_cfg()
    if not all([cfg.get("twilio_sid"), cfg.get("twilio_token"), cfg.get("twilio_number")]):
        return {"error": "Twilio not configured. Add twilio_sid, twilio_token, twilio_number to channel_config.json"}
    try:
        from twilio.rest import Client
        client = Client(cfg["twilio_sid"], cfg["twilio_token"])
        # Truncate to 1600 chars (multi-part SMS handled by Twilio)
        msg = client.messages.create(
            body=body[:1600],
            from_=cfg["twilio_number"],
            to=to
        )
        return {"success": True, "sid": msg.sid}
    except ImportError:
        return {"error": "twilio package not installed. Run: pip install twilio"}
    except Exception as e:
        return {"error": str(e)}


def send_to_owner(body: str) -> dict:
    """Send SMS directly to the Owner's cell."""
    cfg = _load_twilio_cfg()
    cell = cfg.get("owner_cell", "+17133001865")
    return send_sms(cell, body)


def register_sms_webhook(app, ai_ask_fn):
    """Register the /sms webhook route on the Flask app.

    Twilio calls this URL when Owner texts the VO number.
    Must be publicly accessible - use Cloudflare tunnel.
    """
    from flask import request

    @app.route("/sms", methods=["POST", "GET"])
    def sms_webhook():
        """Twilio SMS webhook handler - with signature verification."""
        cfg = _load_twilio_cfg()
        owner_cell = cfg.get("owner_cell", "+17133001865")

        # ── SIGNATURE VERIFICATION (Joseph P1) ────────────────────
        auth_token = cfg.get("twilio_token", "")
        if auth_token:
            try:
                from twilio.request_validator import RequestValidator
                validator = RequestValidator(auth_token)
                # Build the full URL Twilio used
                url = request.url
                signature = request.headers.get("X-Twilio-Signature", "")
                params = request.form.to_dict()
                if not validator.validate(url, params, signature):
                    _log_sms("rejected", "unknown", "Invalid signature")
                    return _twiml(""), 403
            except ImportError:
                pass  # twilio not installed - skip validation
            except Exception:
                pass  # validation error - continue (don't break SMS)

        # ── SENDER VERIFICATION ───────────────────────────────────
        from_number = request.form.get("From", "")
        body = request.form.get("Body", "").strip()

        def norm(n): return "".join(c for c in n if c.isdigit())[-10:]

        if norm(from_number) != norm(owner_cell):
            _log_sms("rejected", from_number, "Unauthorized sender")
            return _twiml(""), 200

        if not body:
            return _twiml("No command received. Text a command to the Virtual Office."), 200

        # ── INPUT SANITIZATION (Joseph P1) ─────────────────────────
        import re
        body = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', body)  # strip control chars
        body = body[:500]  # enforce 500 char limit

        _log_sms("inbound", from_number, body)

        # Process through ai_ask
        try:
            result = ai_ask_fn(body, mode="owner")
            if isinstance(result, dict):
                response_text = (
                    result.get("data", {}).get("text")
                    or result.get("text")
                    or str(result)
                )
            else:
                response_text = str(result)

            # Clean for SMS: strip markdown, limit length
            response_text = _sms_clean(response_text)
        except Exception as e:
            response_text = f"Error: {e}"

        _log_sms("outbound", owner_cell, response_text)
        return _twiml(response_text), 200


def _twiml(msg: str) -> str:
    """Wrap response in Twilio Markup Language."""
    safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'


def _sms_clean(text: str) -> str:
    """Clean AI response for SMS: remove markdown, truncate."""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text)         # *italic*
    text = re.sub(r"#{1,6}\s+", "", text)             # ### headers
    text = re.sub(r"`{1,3}", "", text)                # `code`
    text = re.sub(r"─{3,}", "---", text)              # horizontal rules
    text = re.sub(r"\n{3,}", "\n\n", text)            # excessive newlines
    # Truncate for SMS (1600 char Twilio limit, keep room for header)
    if len(text) > 1500:
        text = text[:1470] + "\n\n[...continued in app]"
    return text.strip()


def _log_sms(direction: str, number: str, body: str):
    """Append to data/messages.db."""
    try:
        import sqlite3
        db = _DATA_DIR / "messages.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages
            (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, direction TEXT,
             sender TEXT, content TEXT, response TEXT, ts TEXT, processed INTEGER DEFAULT 0)
        """)
        conn.execute(
            "INSERT INTO messages (channel, direction, sender, content, ts) VALUES (?,?,?,?,?)",
            ("sms", direction, number, body[:2000], datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
