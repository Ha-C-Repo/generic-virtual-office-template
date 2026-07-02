"""Cloud folder watchdog service (Phase 14, build slot 14, v4.5.0).

Background thread that polls OneDrive and Google Drive for new drawing
PDFs. When a new file lands, the service:
    1. Hashes it (SHA-256) and checks the dedup log.
    2. Downloads to local temp.
    3. Searches project memory for similar past projects (RAG-aware).
    4. Triggers the takeoff pipeline (v2 graph).
    5. Logs the result to data/watchdog_log.jsonl.
    6. Indexes the completed takeoff into project memory.

Joseph's role shifts from "operator" to "reviewer." By the time he opens
the app, draft bid cards are already waiting.

The service runs alongside the existing background pollers in main.py.
It is NOT a separate process. It is a daemon thread that sleeps between
polls and terminates when the main process exits.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import hashlib
import json
import logging
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


# Default poll interval. Joseph can override via configure_watchdog().
DEFAULT_POLL_INTERVAL_SECONDS = 300  # 5 minutes


def _default_log_path() -> Path:
    return Path("data") / "watchdog_log.jsonl"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


class DiscoveredFile:
    """A file detected by a cloud watcher."""

    def __init__(self, name: str, cloud_path: str, source: str,
                 download_fn: Optional[Callable] = None,
                 local_path: Optional[Path] = None,
                 metadata: Optional[dict] = None):
        self.name = name
        self.cloud_path = cloud_path
        self.source = source  # "onedrive" or "gdrive"
        self.download_fn = download_fn
        self.local_path = local_path
        self.metadata = metadata or {}

    def download_to(self, dest: Path) -> Path:
        """Download from cloud to a local path. Returns the path."""
        if self.local_path and self.local_path.exists():
            return self.local_path
        if self.download_fn:
            self.download_fn(dest)
            self.local_path = dest
            return dest
        raise RuntimeError(f"No download function for {self.name}")


class WatchdogLog:
    """Append-only JSONL log of processed files."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = Path(log_path) if log_path else _default_log_path()
        self._seen_hashes: set[str] = set()
        self._lock = threading.Lock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if not self.log_path.exists():
                return
            try:
                for line in self.log_path.read_text(
                        encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        h = rec.get("sha256", "")
                        if h:
                            self._seen_hashes.add(h)
                    except Exception:
                        continue
            except Exception as e:
                log.warning("watchdog log load failed: %s", e)

    def is_seen(self, sha256: str) -> bool:
        self._ensure_loaded()
        with self._lock:
            return sha256 in self._seen_hashes

    def record(self, entry: dict) -> None:
        self._ensure_loaded()
        h = entry.get("sha256", "")
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                if h:
                    self._seen_hashes.add(h)
        except Exception as e:
            log.warning("watchdog log write failed: %s", e)

    def count(self) -> int:
        self._ensure_loaded()
        with self._lock:
            return len(self._seen_hashes)

    def recent(self, n: int = 10) -> list[dict]:
        """Return the last N entries."""
        self._ensure_loaded()
        if not self.log_path.exists():
            return []
        try:
            lines = self.log_path.read_text(
                encoding="utf-8").strip().splitlines()
            entries = []
            for line in lines[-n:]:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
            return entries
        except Exception:
            return []


class WatchdogService:
    """Background polling service.

    Accepts a list of watcher callables. Each watcher returns a list of
    DiscoveredFile objects. The service deduplicates, downloads, runs the
    pipeline, and logs. It is NOT a separate process - it runs as a
    daemon thread.
    """

    def __init__(
        self,
        watchers: list[Callable[[], list[DiscoveredFile]]] | None = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        auto_process: bool = True,
        process_fn: Optional[Callable[[str], dict]] = None,
        log_path: Optional[Path] = None,
    ):
        self.watchers = list(watchers or [])
        self.poll_interval = float(poll_interval)
        self.auto_process = bool(auto_process)
        self.process_fn = process_fn
        self.log = WatchdogLog(log_path=log_path)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._last_poll: Optional[str] = None
        self._files_processed = 0
        self._errors: list[str] = []

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="yourco-watchdog",
            daemon=True,
        )
        self._running = True
        self._thread.start()
        log.info("watchdog service started (interval=%ds)",
                 self.poll_interval)

    def stop(self) -> None:
        """Signal the polling thread to stop."""
        self._stop_event.set()
        self._running = False
        log.info("watchdog service stop requested")

    def is_running(self) -> bool:
        return self._running and self._thread is not None \
               and self._thread.is_alive()

    def status(self) -> dict:
        return {
            "running": self.is_running(),
            "poll_interval_seconds": self.poll_interval,
            "last_poll": self._last_poll,
            "files_processed": self._files_processed,
            "files_in_log": self.log.count(),
            "auto_process": self.auto_process,
            "watcher_count": len(self.watchers),
            "recent_errors": self._errors[-5:],
        }

    def poll_once(self) -> list[dict]:
        """Run a single poll cycle. Returns list of results.

        Useful for manual triggering and tests.
        """
        results: list[dict] = []
        self._last_poll = datetime.now(timezone.utc).isoformat()

        for watcher in self.watchers:
            try:
                discovered = watcher()
            except Exception as e:
                self._errors.append(f"watcher_error: {e}")
                log.warning("watcher failed: %s", e)
                continue

            for df in discovered:
                if not df.name.lower().endswith(".pdf"):
                    continue  # only structural PDFs
                result = self._handle_file(df)
                results.append(result)

        return results

    def _handle_file(self, df: DiscoveredFile) -> dict:
        """Process a single discovered file."""
        entry: dict[str, Any] = {
            "name": df.name,
            "cloud_path": df.cloud_path,
            "source": df.source,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Download to temp
            with tempfile.TemporaryDirectory(
                    prefix="ncwatchdog_") as td:
                local = Path(td) / df.name
                if df.local_path and df.local_path.exists():
                    # Already local (for tests)
                    import shutil
                    shutil.copy2(df.local_path, local)
                elif df.download_fn:
                    df.download_to(local)
                else:
                    entry["status"] = "skipped"
                    entry["reason"] = "no_download_method"
                    return entry

                # SHA-256 dedup
                sha = _sha256_file(local)
                entry["sha256"] = sha

                if self.log.is_seen(sha):
                    entry["status"] = "duplicate"
                    return entry

                # RAG-aware: check project memory
                try:
                    from bridge.project_memory import \
                        search_similar_projects
                    text = local.stem.replace("_", " ").replace("-", " ")
                    matches = search_similar_projects(text, n_results=1)
                    if matches.get("results"):
                        m = matches["results"][0]
                        entry["similar_project"] = {
                            "bid_number": m.get("bid_number", ""),
                            "project_name": m.get("project_name", ""),
                            "similarity": m.get("similarity", 0),
                        }
                except Exception:
                    pass  # RAG is optional

                # Auto-process
                if self.auto_process and self.process_fn:
                    try:
                        takeoff = self.process_fn(str(local))
                        entry["status"] = "processed"
                        entry["stages"] = takeoff.get(
                            "stages_completed", [])
                        entry["total_tons"] = takeoff.get(
                            "total_tons", 0)
                        self._files_processed += 1

                        # Index into project memory
                        try:
                            from bridge.project_memory import \
                                index_takeoff_result
                            index_takeoff_result(
                                takeoff_result=takeoff,
                                bid_number=takeoff.get(
                                    "bid_number", df.name),
                                project_name=df.name,
                            )
                        except Exception:
                            pass
                    except Exception as e:
                        entry["status"] = "process_failed"
                        entry["error"] = str(e)
                        self._errors.append(f"process: {e}")
                else:
                    entry["status"] = "detected"

                self.log.record(entry)
                return entry

        except Exception as e:
            entry["status"] = "error"
            entry["error"] = str(e)
            self._errors.append(str(e))
            self.log.record(entry)
            return entry

    def _poll_loop(self) -> None:
        """Background loop. Runs until stop_event is set."""
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as e:
                self._errors.append(f"poll_loop: {e}")
                log.error("watchdog poll error: %s", e)
            self._stop_event.wait(timeout=self.poll_interval)
        self._running = False
