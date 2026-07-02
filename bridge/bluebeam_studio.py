"""
Your Company Virtual Office - Bluebeam Studio Client

Bluebeam is PDF-native. Studio APIs orchestrate review sessions.
Integration: launch a Studio Session from a Procore submittal,
pull the marked-up PDF back automatically.

Per Procore-Bluebeam Beta (Sept 2025): Procore Submittals + Bluebeam
without a Bluebeam Studio Prime license.

API: bluebeam.com/product/integrations/
"""

import os, json, httpx
from datetime import datetime, timezone
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"

BLUEBEAM_BASE = "https://studioapi.bluebeam.com/publicapi/v1"


def _get_token():
    token = os.environ.get("BLUEBEAM_TOKEN", "")
    if not token:
        try:
            from bridge.keyvault import load_keys
            token = load_keys().get("BLUEBEAM_TOKEN", "")
        except Exception:pass
    return token


def create_session(session_name: str, project_id: str = "",
                   notification_email: str = "") -> dict:
    """Create a Bluebeam Studio Session for document review."""
    token = _get_token()
    if not token:
        return {"error": "Bluebeam token not configured. Set BLUEBEAM_TOKEN.",
                "configured": False}
    try:
        payload = {
            "Name": session_name,
            "Notification": notification_email or "joseph@yourcompany.example.com",
            "Restricted": False,
            "DefaultPermission": 2,  # Markup & Copy
        }
        resp = httpx.post(f"{BLUEBEAM_BASE}/sessions",
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "session_id": data.get("Id"),
            "name": session_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "join_url": data.get("JoinUrl", ""),
        }
    except Exception as e:
        return {"error": str(e)[:200]}


def upload_to_session(session_id: str, file_path: str) -> dict:
    """Upload a PDF to a Studio Session for markup."""
    token = _get_token()
    if not token:
        return {"error": "Bluebeam token not configured"}
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        with open(path, "rb") as f:
            resp = httpx.post(
                f"{BLUEBEAM_BASE}/sessions/{session_id}/files",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (path.name, f, "application/pdf")},
                timeout=30)
        resp.raise_for_status()
        return {"uploaded": True, "filename": path.name, "session_id": session_id}
    except Exception as e:
        return {"error": str(e)[:200]}


def get_session_files(session_id: str) -> dict:
    """List files in a Studio Session (including marked-up versions)."""
    token = _get_token()
    if not token:
        return {"error": "Bluebeam token not configured"}
    try:
        resp = httpx.get(f"{BLUEBEAM_BASE}/sessions/{session_id}/files",
                         headers={"Authorization": f"Bearer {token}"},
                         timeout=15)
        resp.raise_for_status()
        return {"files": resp.json(), "session_id": session_id}
    except Exception as e:
        return {"error": str(e)[:200]}


def close_session(session_id: str) -> dict:
    """Close a Studio Session and flatten markups."""
    token = _get_token()
    if not token:
        return {"error": "Bluebeam token not configured"}
    try:
        resp = httpx.post(f"{BLUEBEAM_BASE}/sessions/{session_id}/snapshot",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=15)
        resp.raise_for_status()
        return {"closed": True, "session_id": session_id}
    except Exception as e:
        return {"error": str(e)[:200]}


def get_status():
    return {
        "configured": bool(_get_token()),
        "base_url": BLUEBEAM_BASE,
        "integration": "Procore-Bluebeam Beta compatible",
    }
