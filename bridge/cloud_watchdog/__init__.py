"""Cloud folder watchdog (Phase 14, build slot 14, v4.5.0).

Monitors OneDrive and Google Drive for new drawing PDFs. When a new
file is detected, the service auto-processes it through the takeoff
pipeline and indexes the result into project memory. RAG-aware: checks
for returning projects before processing.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .watchdog_service import (
    WatchdogService,
    WatchdogLog,
    DiscoveredFile,
    DEFAULT_POLL_INTERVAL_SECONDS,
)
from .onedrive_watcher import make_onedrive_watcher
from .gdrive_watcher import make_gdrive_watcher

__all__ = [
    "WatchdogService",
    "WatchdogLog",
    "DiscoveredFile",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "make_onedrive_watcher",
    "make_gdrive_watcher",
]
