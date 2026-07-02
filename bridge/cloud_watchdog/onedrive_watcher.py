"""OneDrive watcher via M365 Graph API.

Uses delta queries to detect new files in a configurable folder. Follows
the same auth pattern as bridge/m365_mail_scanner.py (M365 Business
subscription). If the Graph API client is not configured, the watcher
returns an empty list and the watchdog service skips it silently.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from pathlib import Path
from typing import Any, Optional

from .watchdog_service import DiscoveredFile

log = logging.getLogger(__name__)


DEFAULT_FOLDER = "Bids/Incoming"


def make_onedrive_watcher(
    folder_path: str = DEFAULT_FOLDER,
    graph_client: Any = None,
) -> callable:
    """Return a watcher callable for the WatchdogService.

    The returned callable takes no args and returns list[DiscoveredFile].
    If graph_client is None, it returns an empty list on every call.
    """
    _delta_token: dict[str, str] = {"token": ""}

    def _discover() -> list[DiscoveredFile]:
        if graph_client is None:
            return []

        try:
            # Build delta query URL
            folder = folder_path.replace("\\", "/").strip("/")
            base = f"/me/drive/root:/{folder}:/delta"
            params = {}
            if _delta_token["token"]:
                params["token"] = _delta_token["token"]

            response = graph_client.get(base, params=params)
            if not response or not isinstance(response, dict):
                return []

            # Update delta token for next poll
            new_token = response.get("@odata.deltaLink", "")
            if new_token:
                # Extract token from the URL
                if "token=" in new_token:
                    _delta_token["token"] = new_token.split(
                        "token=")[-1].split("&")[0]

            items = response.get("value", [])
            results = []
            for item in items:
                name = item.get("name", "")
                if not name.lower().endswith(".pdf"):
                    continue
                # Skip deleted items
                if item.get("deleted"):
                    continue

                file_id = item.get("id", "")
                cloud_path = item.get(
                    "parentReference", {}).get(
                    "path", "") + "/" + name

                def _make_downloader(fid):
                    def _dl(dest: Path):
                        content = graph_client.get(
                            f"/me/drive/items/{fid}/content")
                        dest.write_bytes(content)
                    return _dl

                results.append(DiscoveredFile(
                    name=name,
                    cloud_path=cloud_path,
                    source="onedrive",
                    download_fn=_make_downloader(file_id),
                    metadata={"file_id": file_id},
                ))
            return results

        except Exception as e:
            log.warning("onedrive watcher error: %s", e)
            return []

    return _discover
