"""
Your Company Virtual Office - Google Drive Sync
=============================================
Bidirectional sync between local vault and Google Drive using
the Changes API delta queries. Replaces the status-only vault_sync.

Setup:
  1. API Keys/GDrive Credentials.json (OAuth2 client credentials)
  2. First run triggers browser auth, saves token to data/gdrive_token.json

Usage:
    from bridge.gdrive_sync import GDriveSync
    sync = GDriveSync(root, folder_id="1abc...")
    sync.pull()   # download new/changed files from Drive
    sync.push(Path("memory/bid-rules.md"))  # upload changed file
    sync.full_sync()  # bidirectional
"""

import hashlib
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)


def _md5(p: Path) -> str:
    """Compute MD5 hash of a local file."""
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GDriveSync:
    """Bidirectional sync between local folder and Google Drive."""

    def __init__(self, root, folder_id: str, local_dir: str = "vault"):
        # vj-fix: coerce root to Path so callers can pass str or Path freely.
        # Original signature only worked with Path, but external callers
        # (setup script, MCP dispatch) often pass strings.
        from pathlib import Path as _P
        self.root = _P(root)
        self.folder_id = folder_id
        self.local_root = self.root / local_dir
        self.local_root.mkdir(parents=True, exist_ok=True)

        self._creds_path = self.root / "API Keys" / "GDrive Credentials.json"
        self._token_path = self.root / "data" / "gdrive_token.json"
        self._db_path = self.root / "data" / "gdrive_sync.db"

        # Ensure data directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db = sqlite3.connect(str(self._db_path))
        self._db.execute("""CREATE TABLE IF NOT EXISTS sync_state(
            local_path TEXT PRIMARY KEY,
            drive_id TEXT,
            md5 TEXT,
            modified_time TEXT,
            direction TEXT
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY, value TEXT
        )""")
        self._db.commit()

        self._service = None

    @property
    def configured(self) -> bool:
        return self._creds_path.exists()

    def _get_service(self):
        """Lazy-initialize the Google Drive API service."""
        if self._service:
            return self._service

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "google-api-python-client + google-auth-oauthlib required. "
                "Run: pip install google-api-python-client google-auth-oauthlib"
            )

        SCOPES = ["https://www.googleapis.com/auth/drive"]
        creds = None

        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _get_page_token(self) -> str:
        """Get or initialize the changes page token."""
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='page_token'"
        ).fetchone()
        if row:
            return row[0]

        svc = self._get_service()
        token = svc.changes().getStartPageToken().execute()["startPageToken"]
        self._db.execute(
            "INSERT INTO meta(key, value) VALUES('page_token', ?)", (token,))
        self._db.commit()
        return token

    def _save_page_token(self, token: str):
        self._db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('page_token', ?)",
            (token,))
        self._db.commit()

    def pull(self) -> dict:
        """Pull new/changed files from Google Drive.

        Returns summary: {downloaded: int, conflicts: int, errors: []}
        """
        if not self.configured:
            return {"downloaded": 0, "conflicts": 0,
                    "errors": ["Not configured"]}

        svc = self._get_service()
        token = self._get_page_token()
        downloaded = 0
        conflicts = 0
        errors = []

        while token:
            try:
                resp = svc.changes().list(
                    pageToken=token,
                    includeRemoved=True,
                    fields=(
                        "changes(fileId,file(name,md5Checksum,modifiedTime,"
                        "trashed,parents,mimeType)),"
                        "newStartPageToken,nextPageToken"
                    ),
                ).execute()
            except Exception as e:
                errors.append(str(e))
                break

            for change in resp.get("changes", []):
                f = change.get("file", {})
                if not f or f.get("trashed"):
                    continue
                parents = f.get("parents", [])
                if self.folder_id not in parents:
                    continue

                name = f.get("name", "")
                drive_md5 = f.get("md5Checksum", "")
                drive_id = change["fileId"]
                local_path = self.local_root / name

                # Check for conflict
                row = self._db.execute(
                    "SELECT md5 FROM sync_state WHERE drive_id=?",
                    (drive_id,)).fetchone()

                if local_path.exists() and row:
                    local_md5 = _md5(local_path)
                    if local_md5 != row[0] and drive_md5 != row[0]:
                        # Both sides changed. Keep both.
                        conflict_name = f"{local_path.stem} (conflict){local_path.suffix}"
                        local_path.rename(local_path.parent / conflict_name)
                        conflicts += 1
                        log.warning("Conflict: %s", name)

                # Download
                try:
                    from googleapiclient.http import MediaIoBaseDownload
                    import io
                    request = svc.files().get_media(fileId=drive_id)
                    fh = io.BytesIO()
                    dl = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        _, done = dl.next_chunk()
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(fh.getvalue())
                    downloaded += 1

                    self._db.execute(
                        "INSERT OR REPLACE INTO sync_state"
                        "(local_path, drive_id, md5, modified_time, direction)"
                        " VALUES(?, ?, ?, ?, 'pull')",
                        (str(name), drive_id, drive_md5,
                         f.get("modifiedTime", "")))
                    self._db.commit()
                except Exception as e:
                    errors.append(f"{name}: {e}")

            if "newStartPageToken" in resp:
                self._save_page_token(resp["newStartPageToken"])
            token = resp.get("nextPageToken")

        return {"downloaded": downloaded, "conflicts": conflicts,
                "errors": errors}

    def push(self, local_path: Path) -> dict:
        """Push a local file to Google Drive.

        Returns: {uploaded: bool, drive_id: str, error: str}
        """
        if not self.configured:
            return {"uploaded": False, "error": "Not configured"}
        if not local_path.exists():
            return {"uploaded": False, "error": "File not found"}

        svc = self._get_service()
        rel = local_path.relative_to(self.local_root)
        local_md5 = _md5(local_path)

        # Check if already tracked
        row = self._db.execute(
            "SELECT drive_id, md5 FROM sync_state WHERE local_path=?",
            (str(rel),)).fetchone()

        if row and row[1] == local_md5:
            return {"uploaded": False, "error": "No changes"}

        try:
            from googleapiclient.http import MediaFileUpload
            media = MediaFileUpload(str(local_path), resumable=True)

            if row:
                # Update existing
                svc.files().update(
                    fileId=row[0], media_body=media).execute()
                drive_id = row[0]
            else:
                # Upload new
                metadata = {
                    "name": local_path.name,
                    "parents": [self.folder_id],
                }
                result = svc.files().create(
                    body=metadata, media_body=media,
                    fields="id,md5Checksum").execute()
                drive_id = result["id"]

            self._db.execute(
                "INSERT OR REPLACE INTO sync_state"
                "(local_path, drive_id, md5, modified_time, direction)"
                " VALUES(?, ?, ?, datetime('now'), 'push')",
                (str(rel), drive_id, local_md5))
            self._db.commit()

            return {"uploaded": True, "drive_id": drive_id}

        except Exception as e:
            return {"uploaded": False, "error": str(e)}

    def full_sync(self) -> dict:
        """Bidirectional sync: pull remote changes, push local changes."""
        pull_result = self.pull()

        # Push any local files that differ from last known state
        pushed = 0
        if self.local_root.exists():
            for local_file in self.local_root.rglob("*"):
                if local_file.is_dir():
                    continue
                rel = local_file.relative_to(self.local_root)
                row = self._db.execute(
                    "SELECT md5 FROM sync_state WHERE local_path=?",
                    (str(rel),)).fetchone()
                local_md5 = _md5(local_file)
                if not row or row[0] != local_md5:
                    result = self.push(local_file)
                    if result.get("uploaded"):
                        pushed += 1

        return {
            "pulled": pull_result["downloaded"],
            "pushed": pushed,
            "conflicts": pull_result["conflicts"],
            "errors": pull_result["errors"],
        }

    def status(self) -> dict:
        """Return sync status for dashboard."""
        tracked = self._db.execute(
            "SELECT COUNT(*) FROM sync_state WHERE local_path != '__pagetoken__'"
        ).fetchone()[0]
        return {
            "configured": self.configured,
            "folder_id": self.folder_id,
            "local_root": str(self.local_root),
            "tracked_files": tracked,
            "has_page_token": self._db.execute(
                "SELECT COUNT(*) FROM meta WHERE key='page_token'"
            ).fetchone()[0] > 0,
        }
