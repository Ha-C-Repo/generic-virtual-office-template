"""Google Drive watcher via changes.list API.

Detects new PDF files in a configurable folder using the Drive API
changes endpoint with pageToken. Follows the same auth pattern as
bridge/gdrive_sync.py (Google Premium subscription). If the Drive
service is not configured, returns an empty list.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from pathlib import Path
from typing import Any, Optional

from .watchdog_service import DiscoveredFile

log = logging.getLogger(__name__)


DEFAULT_FOLDER_NAME = "Bids/Incoming"


def make_gdrive_watcher(
    folder_id: str = "",
    folder_name: str = DEFAULT_FOLDER_NAME,
    drive_service: Any = None,
) -> callable:
    """Return a watcher callable for the WatchdogService.

    The returned callable takes no args and returns list[DiscoveredFile].
    If drive_service is None, returns an empty list on every call.
    """
    _page_token: dict[str, str] = {"token": ""}

    def _discover() -> list[DiscoveredFile]:
        if drive_service is None:
            return []

        try:
            # Get start page token if we don't have one
            if not _page_token["token"]:
                resp = drive_service.changes().getStartPageToken().execute()
                _page_token["token"] = resp.get("startPageToken", "")
                return []  # first call just sets the baseline

            changes = drive_service.changes().list(
                pageToken=_page_token["token"],
                spaces="drive",
                fields="nextPageToken,newStartPageToken,changes("
                       "fileId,file(name,mimeType,parents,trashed))",
            ).execute()

            # Update token for next poll
            new_token = changes.get("newStartPageToken", "")
            if new_token:
                _page_token["token"] = new_token
            elif changes.get("nextPageToken"):
                _page_token["token"] = changes["nextPageToken"]

            results = []
            for change in changes.get("changes", []):
                f = change.get("file", {})
                name = f.get("name", "")
                if not name.lower().endswith(".pdf"):
                    continue
                if f.get("trashed"):
                    continue
                # Optional: filter by folder_id
                parents = f.get("parents", [])
                if folder_id and folder_id not in parents:
                    continue

                file_id = change.get("fileId", "")

                def _make_downloader(fid):
                    def _dl(dest: Path):
                        request = drive_service.files().get_media(
                            fileId=fid)
                        content = request.execute()
                        dest.write_bytes(content)
                    return _dl

                results.append(DiscoveredFile(
                    name=name,
                    cloud_path=f"gdrive://{file_id}/{name}",
                    source="gdrive",
                    download_fn=_make_downloader(file_id),
                    metadata={"file_id": file_id,
                              "parents": parents},
                ))
            return results

        except Exception as e:
            log.warning("gdrive watcher error: %s", e)
            return []

    return _discover
