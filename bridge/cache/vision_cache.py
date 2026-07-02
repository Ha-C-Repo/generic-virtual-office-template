"""Deterministic vision-result cache.

Same crop bytes + same prompt = same answer. We hash the crop bytes and
the prompt to a SHA-256 key and persist the vision call result so a
re-run of the same drawing skips the LLM round-trip entirely. Joseph
sees this most when iterating: change a single member, re-process the
PDF, and 95 percent of the connection details are cache hits.

Storage format: JSONL on disk under
    ~/Documents/Your Company Bids/_cache/vision_cache.jsonl
Each line is one cache entry. New writes append; reads scan from end
backward (so the latest answer for a key wins). The cache is a
correctness-preserving optimization: if storage is unavailable, every
call falls through to the live tier and the bid is unaffected.

Per-bid cache scope: the cache key includes the bid_number so cross-bid
poisoning is impossible. A correction recorded by the Phase 3 workbench
on bid A will not silently change a result for bid B.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


# Default cache directory. Joseph can override via the env var
# YOURCO_VISION_CACHE_DIR if he wants the cache on a different volume.
def _default_cache_path() -> Path:
    import os
    override = os.environ.get("YOURCO_VISION_CACHE_DIR", "").strip()
    if override:
        return Path(override) / "vision_cache.jsonl"
    return (Path.home() / "Documents" / "Your Company Bids"
            / "_cache" / "vision_cache.jsonl")


def make_cache_key(crop_bytes: bytes,
                   prompt: str = "",
                   bid_number: str = "") -> str:
    """SHA-256 of (crop bytes || prompt || bid_number).

    Including bid_number scopes the cache per-bid so corrections for
    bid A cannot silently affect bid B. Including the prompt means a
    prompt-engineering change forces re-run automatically.
    """
    h = hashlib.sha256()
    h.update(crop_bytes or b"")
    h.update(b"\x00")
    h.update((prompt or "").encode("utf-8", errors="replace"))
    h.update(b"\x00")
    h.update((bid_number or "").encode("utf-8", errors="replace"))
    return h.hexdigest()


class VisionCache:
    """Append-only JSONL cache with in-memory index.

    Thread-safe via a single lock. The takeoff graph runs Stage 4 nodes
    in parallel, so concurrent gets and sets must not corrupt the index.

    The in-memory index stores latest-seen result per key. The disk file
    grows over time; periodic compaction is out of scope here (Joseph
    can rotate the file manually if it gets large).
    """

    def __init__(self, cache_path: Optional[Path] = None,
                 enabled: bool = True):
        self.cache_path = Path(cache_path) if cache_path \
                          else _default_cache_path()
        self.enabled = bool(enabled)
        self._index: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if not self.cache_path.exists():
                return
            try:
                for line in self.cache_path.read_text(
                        encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    k = rec.get("key")
                    if k:
                        # Latest entry wins. Iteration order = insertion
                        # order so this naturally keeps the most recent.
                        self._index[k] = rec
            except Exception as e:  # pragma: no cover (env)
                log.warning("vision cache load failed: %s", e)

    def get(self, key: str) -> Optional[dict]:
        """Return cached result dict or None on miss."""
        if not self.enabled:
            return None
        self._ensure_loaded()
        with self._lock:
            rec = self._index.get(key)
        if rec is None:
            return None
        return rec.get("result")

    def set(self, key: str, result: dict,
            metadata: Optional[dict] = None) -> bool:
        """Persist a result. Returns True on disk-write success."""
        if not self.enabled:
            return False
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "key": key,
                "result": result,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            line = json.dumps(entry) + "\n"
            with self._lock:
                with self.cache_path.open("a", encoding="utf-8") as f:
                    f.write(line)
                self._index[key] = entry
            return True
        except Exception as e:
            log.warning("vision cache write failed: %s", e)
            return False

    def stats(self) -> dict:
        self._ensure_loaded()
        with self._lock:
            n = len(self._index)
        return {
            "entries": n,
            "path": str(self.cache_path),
            "enabled": self.enabled,
        }

    def clear(self) -> None:
        """Reset in-memory index AND truncate disk file."""
        with self._lock:
            self._index = {}
            try:
                if self.cache_path.exists():
                    self.cache_path.unlink()
            except Exception as e:  # pragma: no cover
                log.warning("cache clear failed: %s", e)
