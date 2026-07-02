"""
Your Company Virtual Office - M365 Mail Scanner
=============================================
Monitors pricing@yourcompany.example.com (or any M365 mailbox) for incoming
bid invitations. Uses Microsoft Graph delta queries for efficient
polling (only new/changed messages since last check).

Fallback: raw IMAP with OAuth2 XOAUTH2 if Graph permissions unavailable.

Setup:
  1. Create API Keys/M365 Mail Config.txt with 3 lines:
       client_id
       tenant_id
       mailbox_email
  2. On first run, a device-code auth flow prompts the user.
  3. Token is cached in data/m365_token_cache.json for refresh.

Integration:
  scanner = M365MailScanner(config, on_bid_invite=handle_bid)
  scanner.start()   # daemon thread, polls every 2 min
  scanner.stop()    # graceful shutdown
"""

import threading
import base64
import logging
import re
import email
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ── Bid invite detection patterns ────────────────────────────────────

BID_SUBJECT_PATTERNS = [
    r"\brfq\b", r"\brequest\s+for\s+quot", r"\bbid\s+invit",
    r"\binvitation\s+to\s+bid\b", r"\bitb\b", r"\bquote\s+request\b",
    r"\brfp\b", r"\brequest\s+for\s+proposal\b",
    r"\bprice\s+request\b", r"\bsteel\s+bid\b", r"\bstructural\s+bid\b",
    r"\bscope\s+of\s+work\b",
]

_BID_RE = re.compile("|".join(BID_SUBJECT_PATTERNS), re.IGNORECASE)


def is_bid_invite(subject: str) -> bool:
    """Check if an email subject looks like a bid invitation."""
    return bool(_BID_RE.search(subject or ""))


# ── Config loader ────────────────────────────────────────────────────

def _load_config(root: Path) -> dict:
    """Load M365 mail config from API Keys folder."""
    cfg_path = root / "API Keys" / "M365 Mail Config.txt"
    if not cfg_path.exists():
        return {}
    lines = [l.strip() for l in cfg_path.read_text().splitlines() if l.strip()]
    if len(lines) < 3:
        return {}
    return {
        "client_id": lines[0],
        "tenant_id": lines[1],
        "mailbox_email": lines[2],
    }


# ── Microsoft Graph scanner (primary) ────────────────────────────────

class M365MailScanner:
    """Polls M365 inbox via Microsoft Graph delta queries."""

    GRAPH = "https://graph.microsoft.com/v1.0"
    SCOPES = ["Mail.Read"]

    def __init__(self, root: Path, on_bid_invite: Callable,
                 poll_seconds: int = 120):
        self.root = root
        self.on_bid_invite = on_bid_invite
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread = None
        self._delta_link = None
        self._config = _load_config(root)
        self._cache_path = root / "data" / "m365_token_cache.json"
        self._delta_path = root / "data" / "m365_delta_token.txt"
        self._attachment_dir = root / "data" / "bid_attachments"
        self._attachment_dir.mkdir(parents=True, exist_ok=True)

        # Load persisted delta token
        if self._delta_path.exists():
            self._delta_link = self._delta_path.read_text().strip()

    @property
    def configured(self) -> bool:
        return bool(self._config.get("client_id"))

    def _get_token(self) -> str:
        """Acquire OAuth2 token via MSAL device-code flow."""
        try:
            from msal import PublicClientApplication, SerializableTokenCache
        except ImportError:
            raise RuntimeError("msal not installed. Run: pip install msal")

        cache = SerializableTokenCache()
        if self._cache_path.exists():
            cache.deserialize(self._cache_path.read_text())

        app = PublicClientApplication(
            self._config["client_id"],
            authority=f"https://login.microsoftonline.com/{self._config['tenant_id']}",
            token_cache=cache,
        )

        # Try silent first (cached token)
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]

        # Interactive: device-code flow
        flow = app.initiate_device_flow(scopes=self.SCOPES)
        log.info("M365 Auth: %s", flow.get("message", "Check console"))
        result = app.acquire_token_by_device_flow(flow)

        if cache.has_state_changed:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(cache.serialize())

        if "access_token" not in result:
            raise RuntimeError(f"M365 auth failed: {result.get('error_description')}")

        return result["access_token"]

    def _poll_once(self, headers: dict) -> list:
        """Run one delta query cycle. Returns list of bid invites found."""
        import httpx

        url = self._delta_link or (
            f"{self.GRAPH}/me/mailFolders/Inbox/messages/delta"
            "?$select=id,subject,from,receivedDateTime,hasAttachments"
            "&$top=50"
        )

        invites = []
        while url:
            resp = httpx.get(url, headers=headers, timeout=30)
            if resp.status_code == 401:
                raise PermissionError("Token expired")
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("value", []):
                subject = msg.get("subject", "")
                if is_bid_invite(subject):
                    log.info("Bid invite found: %s", subject)
                    paths = []
                    if msg.get("hasAttachments"):
                        paths = self._save_attachments(headers, msg["id"])
                    invite = {
                        "id": msg["id"],
                        "subject": subject,
                        "from_name": msg.get("from", {}).get(
                            "emailAddress", {}).get("name", ""),
                        "from_email": msg.get("from", {}).get(
                            "emailAddress", {}).get("address", ""),
                        "received": msg.get("receivedDateTime", ""),
                        "attachment_paths": paths,
                    }
                    invites.append(invite)
                    try:
                        self.on_bid_invite(invite)
                    except Exception:
                        log.exception("on_bid_invite callback failed")

            url = data.get("@odata.nextLink")
            if "@odata.deltaLink" in data:
                self._delta_link = data["@odata.deltaLink"]
                self._delta_path.parent.mkdir(parents=True, exist_ok=True)
                self._delta_path.write_text(self._delta_link)

        return invites

    def _save_attachments(self, headers: dict, msg_id: str) -> list:
        """Download PDF attachments from a message."""
        import httpx

        url = f"{self.GRAPH}/me/messages/{msg_id}/attachments"
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return []

        saved = []
        for att in resp.json().get("value", []):
            if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
                continue
            name = att.get("name", "unknown.pdf")
            if not name.lower().endswith(".pdf"):
                continue
            content = base64.b64decode(att.get("contentBytes", ""))
            target = self._attachment_dir / msg_id[:12] / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            saved.append(str(target))
            log.info("Saved attachment: %s", target)

        return saved

    def _run(self):
        """Main scanner loop (runs on daemon thread)."""
        if not self.configured:
            log.warning("M365 Mail Scanner: not configured, exiting thread")
            return

        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}

        while not self._stop.is_set():
            try:
                self._poll_once(headers)
            except PermissionError:
                # Token expired, refresh
                try:
                    token = self._get_token()
                    headers["Authorization"] = f"Bearer {token}"
                except Exception:
                    log.exception("Token refresh failed")
            except Exception:
                log.exception("M365 scanner poll error")

            self._stop.wait(self.poll_seconds)

    def start(self):
        """Start the scanner daemon thread."""
        if not self.configured:
            log.warning("M365 Mail Scanner: skipped (no config)")
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="M365MailScanner"
        )
        self._thread.start()
        log.info("M365 Mail Scanner started (poll=%ds)", self.poll_seconds)

    def stop(self):
        """Signal the scanner to stop."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def scan_once(self) -> list:
        """Manual single scan (for testing or on-demand check)."""
        if not self.configured:
            return []
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        return self._poll_once(headers)

    def status(self) -> dict:
        """Return scanner status for dashboard."""
        return {
            "configured": self.configured,
            "mailbox": self._config.get("mailbox_email", ""),
            "running": self._thread is not None and self._thread.is_alive(),
            "delta_token_saved": self._delta_path.exists(),
            "attachment_dir": str(self._attachment_dir),
            "poll_seconds": self.poll_seconds,
        }


# ── IMAP fallback (for tenants without Graph permissions) ────────────

class IMAPFallbackScanner:
    """Fallback scanner using raw IMAP + OAuth2 XOAUTH2."""

    def __init__(self, root: Path, on_bid_invite: Callable,
                 poll_seconds: int = 120):
        self.root = root
        self.on_bid_invite = on_bid_invite
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread = None
        self._config = self._load_imap_config(root)
        self._attachment_dir = root / "data" / "bid_attachments"
        self._attachment_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_imap_config(root: Path) -> dict:
        cfg_path = root / "API Keys" / "IMAP Config.txt"
        if not cfg_path.exists():
            return {}
        lines = [l.strip() for l in cfg_path.read_text().splitlines()
                 if l.strip()]
        if len(lines) < 3:
            return {}
        return {
            "username": lines[0],
            "server": lines[1],
            "password": lines[2],
        }

    @property
    def configured(self) -> bool:
        return bool(self._config.get("username"))

    def _scan_once(self) -> list:
        """Single IMAP scan for unseen bid invites."""
        import imaplib
        import email as email_mod

        cfg = self._config
        imap = imaplib.IMAP4_SSL(cfg["server"], 993)
        imap.login(cfg["username"], cfg["password"])
        imap.select("INBOX")

        _, data = imap.search(None, "UNSEEN")
        invites = []

        for num in data[0].split():
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email_mod.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")

            if not is_bid_invite(subject):
                continue

            from_addr = msg.get("From", "")
            received = msg.get("Date", "")
            paths = []

            # Save PDF attachments
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                fname = part.get_filename()
                if fname and fname.lower().endswith(".pdf"):
                    content = part.get_payload(decode=True)
                    safe_name = re.sub(r'[^\w\-.]', '_', fname)
                    target = self._attachment_dir / safe_name
                    target.write_bytes(content)
                    paths.append(str(target))

            invite = {
                "id": num.decode(),
                "subject": subject,
                "from_email": from_addr,
                "received": received,
                "attachment_paths": paths,
            }
            invites.append(invite)
            try:
                self.on_bid_invite(invite)
            except Exception:
                log.exception("on_bid_invite callback failed")

        imap.logout()
        return invites

    def _run(self):
        while not self._stop.is_set():
            try:
                self._scan_once()
            except Exception:
                log.exception("IMAP scanner error")
            self._stop.wait(self.poll_seconds)

    def start(self):
        if not self.configured:
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="IMAPScanner"
        )
        self._thread.start()

    def stop(self):
        self._stop.set()

    def status(self) -> dict:
        return {
            "configured": self.configured,
            "mailbox": self._config.get("username", ""),
            "running": self._thread is not None and self._thread.is_alive(),
            "method": "imap_basic_auth",
        }
