"""
Your Company Virtual Office - Notifications & External Channel

1. WINDOWS NOTIFICATIONS - toast alerts via PowerShell (no extra packages)
   Fires when a new HIGH-priority bid arrives in the Owner's Outlook.

2. EXTERNAL COMMAND CHANNEL - two paths for Owner to send commands from outside:
   a. DEDICATED EMAIL INBOX: Owner emails/texts the VO address from any device.
      App polls every 5 min. Processes through ai_ask. Replies by email.
   b. LOCAL HTTP WEBHOOK: Flask server on localhost:7750. Can be exposed via
      Cloudflare Tunnel for external access (free, no account needed).

Owner texts from his phone → email-to-SMS gateway or direct email
→ IMAP polling picks it up → ai_ask processes it → reply sent back to Owner.
"""

import imaplib
import json
import smtplib
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TZ_CT = ZoneInfo("America/Chicago")
from email.mime.text import MIMEText
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CONFIG_PATH = _DATA_DIR / "channel_config.json"
_MSG_DB = _DATA_DIR / "messages.db"

# ── Windows Toast Notification ─────────────────────────────────────────

def toast(title: str, message: str, duration: int = 6) -> bool:
    """Fire a Windows toast notification using PowerShell NotifyIcon.

    Works on all Windows 10/11 with no extra packages.
    Returns True if notification fired successfully.
    """
    # Escape single quotes
    title_safe = title.replace("'", "''")
    msg_safe = message.replace("'", "''")

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$notify = New-Object System.Windows.Forms.NotifyIcon; "
        "$notify.Icon = [System.Drawing.SystemIcons]::Information; "
        "$notify.Visible = $true; "
        f"$notify.ShowBalloonTip({duration * 1000}, '{title_safe}', '{msg_safe}', "
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        f"Start-Sleep -Seconds {duration + 1}; "
        "$notify.Visible = $false; "
        "$notify.Dispose()"
    )
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return True
    except Exception:
        return False


def toast_bid_alert(lead: dict) -> bool:
    """Fire a bid alert notification for a new high-priority lead."""
    tier_icons = {"HIGH": "🔴", "MEDIUM": "🟡"}
    icon = tier_icons.get(lead.get("tier", ""), "")
    title = f"Your Company - {icon} New Bid Lead"
    msg = (
        f"{lead.get('subject', 'New RFQ')[:60]}\n"
        f"From: {lead.get('sender', '')[:40]}\n"
        f"Score: {lead.get('score', 0)}/100 - {lead.get('tier', '')}"
    )
    return toast(title, msg)


def toast_message_received(sender: str, preview: str) -> bool:
    """Notify Owner that his external command was received and processed."""
    return toast(
        "Your Company - External Command Received",
        f"From: {sender[:40]}\n{preview[:80]}"
    )


# ── Config ─────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "email_enabled": False,
    "imap_host": "imap.gmail.com",
    "imap_user": "",            # e.g. virtualoffice@gmail.com
    "imap_password": "",        # app password
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "owner_email": "owner@yourcompany.example.com",
    "owner_sms_email": "7133001865@vzwpix.com",  # Verizon MMS gateway
    "poll_interval_minutes": 5,
    "webhook_enabled": False,
    "webhook_port": 7750,
    "cloudflare_tunnel": False,
    "outlook_scan_enabled": True,
    "outlook_scan_interval_hours": 2,
    "notification_high": True,
    "notification_medium": False,
    # ── v3.2: SMS per-event toggles (B2) ──
    "sms_events": {
        "morning_brief": True,       # 7 AM daily briefing
        "bid_won": True,             # Bid status → WON
        "bid_lost": True,            # Bid status → LOST
        "blocker_resolved": True,    # Compliance blocker cleared
        "blocker_escalated": True,   # Blocker open 30+ days
        "high_bid_lead": True,       # HIGH-scoring bid found in Outlook
        "compliance_alert": True,    # Compliance gate failure
        "cert_expiring": True,       # Certificate expiring within 30 days
        "steel_price_alert": True,   # Steel price moves >3%
        "ar_overdue": True,          # Accounts receivable past 30 days
    },
    # ── v3.2: Escalation threshold (B3) ──
    "escalation_days": 30,           # Alert after N days blocked (configurable)
}


def load_config() -> dict:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    cfg = dict(DEFAULT_CONFIG)
    if _CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(_CONFIG_PATH.read_text()))
        except Exception:
            pass
    return cfg


def save_config(updates: dict) -> dict:
    cfg = load_config()
    cfg.update(updates)
    _CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    return cfg


def should_send_sms(event_type: str) -> bool:
    """Check if SMS should be sent for this event type (v3.2 per-event toggle).
    Call this before every SMS send. Returns True if the event is enabled.

    vj-fix: previously defaulted to True for unknown event types, which
    allowed any caller to fire SMS by passing an arbitrary string. Now
    fails closed: unknown event types return False. Add new event types
    to DEFAULT_CONFIG['sms_events'] before they can fire.
    """
    cfg = load_config()
    sms_events = cfg.get("sms_events", {})
    return sms_events.get(event_type, False)


def get_sms_event_toggles() -> dict:
    """Return current SMS per-event toggle map."""
    cfg = load_config()
    return cfg.get("sms_events", DEFAULT_CONFIG.get("sms_events", {}))


def set_sms_event_toggle(event_type: str, enabled: bool) -> dict:
    """Enable or disable SMS for a specific event type."""
    cfg = load_config()
    sms_events = cfg.get("sms_events", dict(DEFAULT_CONFIG.get("sms_events", {})))
    sms_events[event_type] = enabled
    cfg["sms_events"] = sms_events
    save_config(cfg)
    return sms_events


def get_escalation_days() -> int:
    """Return configurable escalation threshold (default 30 days)."""
    cfg = load_config()
    return cfg.get("escalation_days", 30)


def set_escalation_days(days: int) -> int:
    """Set escalation threshold in days."""
    cfg = load_config()
    cfg["escalation_days"] = max(1, min(365, days))
    save_config(cfg)
    return cfg["escalation_days"]


# ── Message Database ───────────────────────────────────────────────────

def _init_msg_db():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_MSG_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            direction TEXT,
            sender TEXT,
            content TEXT,
            response TEXT,
            ts TEXT,
            processed INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def _log_message(channel: str, direction: str, sender: str,
                  content: str, response: str = ""):
    _init_msg_db()
    try:
        conn = sqlite3.connect(str(_MSG_DB))
        conn.execute(
            "INSERT INTO messages (channel, direction, sender, content, response, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (channel, direction, sender, content[:2000], response[:2000],
             datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_message_log(limit: int = 20) -> list[dict]:
    _init_msg_db()
    try:
        conn = sqlite3.connect(str(_MSG_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Email Reply Sender ─────────────────────────────────────────────────

def _send_reply(to: str, subject: str, body: str, cfg: dict) -> bool:
    """Send an email reply via SMTP."""
    try:
        msg = MIMEText(body, "plain")
        msg["From"] = cfg["smtp_user"]
        msg["To"] = to
        msg["Subject"] = "Re: " + subject.lstrip("Re: ")

        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.starttls()
            server.login(cfg["smtp_user"], cfg["smtp_password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


# ── IMAP Email Poller ──────────────────────────────────────────────────

def poll_email_inbox(ai_ask_fn) -> dict:
    """Poll the dedicated VO inbox for external commands from Owner.

    For each unread message from the Owner's addresses:
    1. Parse the command
    2. Call ai_ask_fn(message)
    3. Reply with the response
    4. Log the exchange
    """
    cfg = load_config()
    if not cfg.get("email_enabled") or not cfg.get("imap_user"):
        return {"skipped": True, "reason": "Email channel not configured"}

    processed = 0
    errors = []

    try:
        import email as email_lib
        from email.header import decode_header

        mail = imaplib.IMAP4_SSL(cfg["imap_host"])
        mail.login(cfg["imap_user"], cfg["imap_password"])
        mail.select("INBOX")

        # Only look for messages from the Owner's known addresses
        authorized_senders = [
            cfg.get("owner_email", "").lower(),
            cfg.get("owner_sms_email", "").lower(),
            "owner@yourcompany.example.com",
            "7133001865",  # partial SMS gateway address
        ]

        _, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        for eid in email_ids[-20:]:  # max 20 at a time
            try:
                _, msg_data = mail.fetch(eid, "(RFC822)")
                msg = email_lib.message_from_bytes(msg_data[0][1])

                sender = msg.get("From", "").lower()
                # Check if from an authorized sender
                if not any(auth in sender for auth in authorized_senders if auth):
                    continue  # skip unauthorized senders

                # Decode subject
                raw_subject = msg.get("Subject", "")
                subject = ""
                for part, enc in decode_header(raw_subject):
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += str(part)

                # Get body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_payload(decode=True).decode(
                                "utf-8", errors="replace")
                            break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="replace")

                # Extract command (first non-empty line, remove reply chains)
                command = _extract_command(body or subject)
                if not command:
                    continue

                # Process through ai_ask
                try:
                    result = ai_ask_fn(command, mode="owner")
                    if isinstance(result, dict):
                        response_text = result.get("data", {}).get("text", str(result))
                    else:
                        response_text = str(result)
                except Exception as e:
                    response_text = f"Error processing command: {e}"

                # Reply
                reply_sent = _send_reply(
                    to=msg.get("From", cfg["owner_email"]),
                    subject=subject,
                    body=f"Your Company Virtual Office\n\n{response_text}",
                    cfg=cfg
                )

                # Log
                _log_message("email", "inbound", sender, command, response_text)
                if reply_sent:
                    _log_message("email", "outbound", cfg["smtp_user"],
                                 response_text[:500])

                # Mark as read
                mail.store(eid, "+FLAGS", "\\Seen")

                # Toast notification
                toast_message_received(sender, command[:80])
                processed += 1

            except Exception as e:
                errors.append(str(e))

        mail.logout()
    except Exception as e:
        return {"error": str(e), "processed": processed}

    return {"processed": processed, "errors": errors}


def _extract_command(text: str) -> str:
    """Extract the actual command from an email body, stripping reply chains."""
    lines = text.split("\n")
    command_lines = []
    for line in lines:
        stripped = line.strip()
        # Stop at reply chain indicators
        if stripped.startswith(">") or stripped.startswith("On ") or \
           "wrote:" in stripped or stripped.startswith("From:"):
            break
        if stripped:
            command_lines.append(stripped)
        if len(command_lines) >= 5:
            break
    return " ".join(command_lines).strip()[:500]


# ── Local HTTP Webhook Server ──────────────────────────────────────────

_webhook_server = None
_webhook_thread = None


def start_webhook_server(ai_ask_fn, port: int = 7750):
    """Start a local HTTP server that accepts commands via POST /command.

    Expose externally via:
      cloudflared tunnel --url http://localhost:7750
    or
      npx cloudflare-tunnel http://localhost:7750

    Owner can then POST from anywhere:
      curl -X POST https://xyz.trycloudflare.com/command -d "command=compliance status"
    """
    global _webhook_server, _webhook_thread
    from flask import Flask, request, jsonify

    app = Flask("vo_webhook")

    @app.route("/", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "Your Company Virtual Office"})

    @app.route("/command", methods=["POST", "GET"])
    def command():
        if request.method == "GET":
            cmd = request.args.get("q", "")
        else:
            data = request.get_json(silent=True) or {}
            cmd = data.get("command", data.get("q", request.form.get("q", "")))

        if not cmd:
            return jsonify({"error": "No command. Use ?q=your+command or POST {command}"}), 400

        # Security: log the request
        _log_message("webhook", "inbound", request.remote_addr, cmd)

        try:
            result = ai_ask_fn(cmd, mode="owner")
            if isinstance(result, dict):
                response_text = result.get("data", {}).get("text", str(result))
            else:
                response_text = str(result)
        except Exception as e:
            response_text = f"Error: {e}"

        _log_message("webhook", "outbound", "server", response_text[:500])
        toast_message_received(f"Webhook ({request.remote_addr})", cmd[:80])

        return jsonify({
            "command": cmd,
            "response": response_text,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @app.route("/bid_leads", methods=["GET"])
    def bid_leads():
        from bridge.bid_scanner import get_daily_summary
        return jsonify(get_daily_summary())

    # ── Register Twilio SMS webhook ────────────────────────────────────
    try:
        from bridge.sms_channel import register_sms_webhook
        register_sms_webhook(app, ai_ask_fn)
    except Exception:
        pass  # SMS webhook is optional

    def _run():
        import logging
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    _webhook_thread = threading.Thread(target=_run, daemon=True)
    _webhook_thread.start()
    return {"port": port, "url": f"http://localhost:{port}"}


def start_cloudflare_tunnel(port: int = 7750) -> dict:
    """Start a Cloudflare quick tunnel (free, no account) for external access.

    Returns the public URL.
    """
    try:
        # Try cloudflared binary
        for binary in ["cloudflared", "cloudflared.exe"]:
            try:
                proc = subprocess.Popen(
                    [binary, "tunnel", "--url", f"http://localhost:{port}"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True
                )
                # Read lines until we find the URL
                for _ in range(30):
                    line = proc.stderr.readline()
                    if "trycloudflare.com" in line or ".cloudflare" in line:
                        url = re.search(r"https://\S+\.trycloudflare\.com", line)
                        if url:
                            return {"url": url.group(0), "pid": proc.pid}
                    time.sleep(0.5)
                return {"url": f"http://localhost:{port}", "note": "cloudflared running but URL not parsed"}
            except FileNotFoundError:
                continue
        return {"error": "cloudflared not installed. Download from: cloudflare.com/products/tunnel"}
    except Exception as e:
        return {"error": str(e)}


# ── Background Polling Thread ──────────────────────────────────────────

_poller_running = False


def start_background_poller(ai_ask_fn):
    """Start background threads for:
    1. Email polling (every 5 min)
    2. Outlook bid scanning (every 2 hours)
    3. Daily bid summary notification (9 AM)
    """
    global _poller_running
    if _poller_running:
        return

    _poller_running = True

    def _email_loop():
        while _poller_running:
            try:
                poll_email_inbox(ai_ask_fn)
            except Exception:
                pass
            cfg = load_config()
            time.sleep(cfg.get("poll_interval_minutes", 5) * 60)

    def _scan_loop():
        while _poller_running:
            try:
                from bridge.bid_scanner import scan_outlook, get_leads
                cfg = load_config()
                if cfg.get("outlook_scan_enabled", True):
                    result = scan_outlook(days_back=3)
                    # Notify for each new HIGH lead
                    for lead in result.get("leads", []):
                        if lead.get("tier") == "HIGH" and cfg.get("notification_high", True):
                            toast_bid_alert(lead)
                        elif lead.get("tier") == "MEDIUM" and cfg.get("notification_medium", False):
                            toast_bid_alert(lead)
            except Exception:
                pass
            cfg = load_config()
            time.sleep(cfg.get("outlook_scan_interval_hours", 2) * 3600)

    def _daily_summary():
        """6 AM CT -> SMS briefing to the Owner's cell. 9 AM CT -> toast for bid summary."""
        last_briefing_date = None
        while _poller_running:
            now_ct = datetime.now(_TZ_CT)
            today = now_ct.date()

            # 6 AM CT SMS briefing - once per day
            if now_ct.hour == 6 and now_ct.minute < 5 and last_briefing_date != today:
                try:
                    _send_owner_morning_briefing()
                    last_briefing_date = today
                except Exception:
                    pass

            # 9 AM CT toast for in-app bid summary
            if now_ct.hour == 9 and now_ct.minute < 5:
                try:
                    from bridge.bid_scanner import get_leads
                    high = get_leads(tier="HIGH", limit=3)
                    if high:
                        toast("Your Company - Daily Bid Summary",
                              f"{len(high)} high-priority bids need review")
                except Exception:
                    pass
                time.sleep(300)

            time.sleep(60)


def _build_morning_briefing() -> str:
    """Build the Owner's 3-line morning briefing.

    1. Active blockers (items blocking revenue)
    2. Deadlines today or within 3 days
    3. Items that specifically require Owner

    Returns a concise SMS-ready string (max 300 chars).
    """
    lines = ["Your Company - Good morning.\n"]

    # ── Blockers (Joseph P1 - dynamic from stored dates) ────────
    blockers = []
    try:
        from bridge.blockers import get_blocked, summary_for_briefing
        blocker_text = summary_for_briefing()
        if blocker_text and blocker_text != "No active blockers.":
            for line in blocker_text.strip().split("\n"):
                if line.strip():
                    blockers.append(line.strip())
    except Exception:
        # Fallback to static if blocker module not available
        blocker_map = {
            "EMR letter": "Call Texas Mutual 800-859-5995 (Policy [POLICY NUMBER])",
            "Auto Liability $2M CSL": "Amber handling carrier upgrade",
        }
        for name, action in blocker_map.items():
            blockers.append(f"⛔ BLOCKED: {name} - {action}")

    if blockers:
        lines.append(f"⛔ {blockers[0]}")
        if len(blockers) > 1:
            lines.append(f"⛔ {blockers[1]}")

    # ── Bid leads due / pending ────────────────────────────────────────
    try:
        from bridge.bid_scanner import get_leads
        high_leads = get_leads(tier="HIGH", limit=2, unactioned=True)
        if high_leads:
            lines.append(f"📋 {len(high_leads)} HIGH bid lead(s) need review")
    except Exception:
        pass

    # ── Sign-off ──────────────────────────────────────────────────────
    from datetime import date
    lines.append(f"\n{date.today().strftime('%A, %B %d')}")

    return "\n".join(lines)[:320]


def _send_owner_morning_briefing():
    """Send the 7 AM briefing SMS to the Owner's cell via Twilio."""
    try:
        from bridge.sms_channel import send_to_owner, is_configured
        if not is_configured():
            # Fall back to Windows toast only
            briefing = _build_morning_briefing()
            toast("Your Company - Morning Briefing", briefing[:200])
            return

        briefing = _build_morning_briefing()
        send_to_owner(briefing)
        # Also fire toast on the desktop
        toast("Your Company - Morning Briefing sent", "Check your phone.")
    except Exception:
        pass

    threading.Thread(target=_email_loop, daemon=True, name="email_poller").start()
    threading.Thread(target=_scan_loop, daemon=True, name="outlook_scanner").start()
    threading.Thread(target=_daily_summary, daemon=True, name="daily_summary").start()


import re  # needed by start_cloudflare_tunnel
