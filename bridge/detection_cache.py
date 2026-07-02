"""F29: Per-page detection cache + resume.

Vision is expensive and slow. When a run is interrupted (workspace
restart, API timeout, manual cancel), all completed page work is lost
unless we persist as we go.

This module wraps vision_detect calls with a JSON cache keyed by
(pdf_hash, page_idx, provider). Cache entries include detections,
provider, model, and a content hash so stale cache for a modified PDF
is detected and discarded.

Usage in auto_bid:

    cache = DetectionCache(out_dir / "_cache" / f"{bid_number}.json")
    detections = []
    for pi in pages:
        d = cache.get(pi)
        if d is None:
            d = vision_detect.detect_members_in_image(image)
            cache.set(pi, d, provider="anthropic")
        detections.extend(d)
"""

from __future__ import annotations
from pathlib import Path
import hashlib
import json
import time


def _pdf_fingerprint(pdf_path) -> str:
    """SHA-1 of (filename + size + mtime). Cheap, no file read."""
    p = Path(pdf_path)
    st = p.stat()
    s = f"{p.name}|{st.st_size}|{int(st.st_mtime)}"
    return hashlib.sha1(s.encode()).hexdigest()[:16]


class DetectionCache:
    def __init__(self, cache_path, pdf_path=None):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = _pdf_fingerprint(pdf_path) if pdf_path else "unknown"
        self.data = {"fingerprint": self.fp, "pages": {}}
        if self.cache_path.exists():
            try:
                old = json.loads(self.cache_path.read_text())
                if old.get("fingerprint") == self.fp:
                    self.data = old
            except (json.JSONDecodeError, OSError):
                pass

    def get(self, page_idx):
        """Returns cached detections for the page, or None."""
        entry = self.data["pages"].get(str(page_idx))
        if entry:
            return entry.get("detections", [])
        return None

    def set(self, page_idx, detections, provider="unknown", model=""):
        self.data["pages"][str(page_idx)] = {
            "detections": detections,
            "provider": provider,
            "model": model,
            "stored_at": int(time.time()),
            "count": len(detections),
        }
        self._flush()

    def has(self, page_idx) -> bool:
        return str(page_idx) in self.data["pages"]

    def covered_pages(self) -> list[int]:
        return sorted(int(k) for k in self.data["pages"].keys())

    def stats(self) -> dict:
        n = len(self.data["pages"])
        total_dets = sum(p.get("count", 0) for p in self.data["pages"].values())
        return {"cached_pages": n, "cached_detections": total_dets,
                "cache_path": str(self.cache_path)}

    def _flush(self):
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.cache_path)

    def clear(self):
        self.data = {"fingerprint": self.fp, "pages": {}}
        if self.cache_path.exists():
            self.cache_path.unlink()
