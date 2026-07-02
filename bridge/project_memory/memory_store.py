"""Project memory store.

Two backends, same interface:

ChromaDB (preferred when installed):
    pip install chromadb
    Sentence-transformer embeddings, semantic similarity search.
    Collection: "your_company_projects"
    ~500 MB disk for model + DB. Runs on the Mac Mini M4 locally.

JSONL fallback (always available):
    Keyword overlap scoring. No embeddings, no model download.
    Data in ~/Documents/Your Company Bids/_memory/projects.jsonl.
    Covers the 80 percent case (project names, bid numbers, clients)
    without the 500 MB model.

Both backends upsert by bid_number so indexing the same project twice
updates rather than duplicates.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


# Probe for ChromaDB at import time.
try:
    import chromadb  # noqa: F401
    HAS_CHROMADB = True
except (ImportError, ModuleNotFoundError):
    HAS_CHROMADB = False


COLLECTION_NAME = "your_company_projects"

# Phase 5: type-based score multipliers.
# Applied after raw similarity so ranking favors structured knowledge.
# wiki = bid kit files, skill docs, agent knowledge bases (high signal)
# project = bid folders, estimate data (standard signal)
# raw = log files, raw text, misc exports (lower signal)
# Unknown type defaults to project (1.0) so weights never zero out results.
TYPE_WEIGHTS: dict[str, float] = {
    "wiki": 1.5,
    "project": 1.0,
    "raw": 0.7,
}


def _default_memory_dir() -> Path:
    override = os.environ.get("YOURCO_MEMORY_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / "Documents" / "Your Company Bids" / "_memory"


# ── ChromaDB backend ──────────────────────────────────────────────────────

class ChromaMemoryStore:
    """Vector-search backend using ChromaDB."""

    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = Path(persist_dir) if persist_dir \
                           else _default_memory_dir() / "chromadb"
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._client is not None:
            return
        import chromadb as _cdb
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = _cdb.PersistentClient(path=str(self.persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, bid_number: str, document: str,
               metadata: dict) -> bool:
        try:
            self._ensure_client()
            self._collection.upsert(
                ids=[bid_number],
                documents=[document],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            log.warning("chromadb upsert failed: %s", e)
            return False

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        try:
            self._ensure_client()
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
            )
            out = []
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            for i, bid_id in enumerate(ids):
                meta = metas[i] if i < len(metas) else {}
                raw_sim = (1.0 - float(dists[i])) if i < len(dists) else 0.0
                weight = TYPE_WEIGHTS.get(
                    str(meta.get("type", "project")), TYPE_WEIGHTS["project"])
                out.append({
                    "bid_number": bid_id,
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": meta,
                    "similarity": round(raw_sim * weight, 4),
                })
            out.sort(key=lambda x: x["similarity"], reverse=True)
            return out
        except Exception as e:
            log.warning("chromadb search failed: %s", e)
            return []

    def get(self, bid_number: str) -> Optional[dict]:
        try:
            self._ensure_client()
            r = self._collection.get(ids=[bid_number])
            if not r.get("ids"):
                return None
            return {
                "bid_number": r["ids"][0],
                "document": r["documents"][0] if r.get("documents") else "",
                "metadata": r["metadatas"][0] if r.get("metadatas") else {},
            }
        except Exception as e:
            log.warning("chromadb get failed: %s", e)
            return None

    def count(self) -> int:
        try:
            self._ensure_client()
            return self._collection.count()
        except Exception:
            return 0

    def delete(self, bid_number: str) -> bool:
        try:
            self._ensure_client()
            self._collection.delete(ids=[bid_number])
            return True
        except Exception as e:
            log.warning("chromadb delete failed: %s", e)
            return False


# ── JSONL fallback backend ────────────────────────────────────────────────

class JSONLMemoryStore:
    """Keyword-overlap search fallback. No embeddings required."""

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = Path(store_path) if store_path \
                          else _default_memory_dir() / "projects.jsonl"
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
            if not self.store_path.exists():
                return
            try:
                for line in self.store_path.read_text(
                        encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        bid = rec.get("bid_number", "")
                        if bid:
                            self._index[bid] = rec
                    except Exception:
                        continue
            except Exception as e:
                log.warning("JSONL memory load failed: %s", e)

    def upsert(self, bid_number: str, document: str,
               metadata: dict) -> bool:
        self._ensure_loaded()
        rec = {
            "bid_number": bid_number,
            "document": document,
            "metadata": metadata,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                self._index[bid_number] = rec
                # Rewrite entire file (small dataset, ~12 employees)
                with self.store_path.open("w", encoding="utf-8") as f:
                    for r in self._index.values():
                        f.write(json.dumps(r) + "\n")
            return True
        except Exception as e:
            log.warning("JSONL memory upsert failed: %s", e)
            return False

    def search(self, query: str, n_results: int = 3) -> list[dict]:
        self._ensure_loaded()
        if not self._index:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scored = []
        for bid, rec in self._index.items():
            doc_tokens = self._tokenize(rec.get("document", ""))
            meta_tokens = self._tokenize(
                json.dumps(rec.get("metadata", {})))
            all_tokens = doc_tokens + meta_tokens
            if not all_tokens:
                continue
            # Jaccard-like overlap score, weighted by document type
            q_set = set(query_tokens)
            d_set = set(all_tokens)
            overlap = len(q_set & d_set)
            union = len(q_set | d_set)
            base_score = overlap / union if union > 0 else 0.0
            weight = TYPE_WEIGHTS.get(
                str(rec.get("metadata", {}).get("type", "project")),
                TYPE_WEIGHTS["project"],
            )
            score = base_score * weight
            if base_score > 0:
                scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "bid_number": rec["bid_number"],
                "document": rec.get("document", ""),
                "metadata": rec.get("metadata", {}),
                "similarity": round(score, 4),
            }
            for score, rec in scored[:n_results]
        ]

    def get(self, bid_number: str) -> Optional[dict]:
        self._ensure_loaded()
        return self._index.get(bid_number)

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._index)

    def delete(self, bid_number: str) -> bool:
        self._ensure_loaded()
        with self._lock:
            if bid_number in self._index:
                del self._index[bid_number]
                try:
                    with self.store_path.open("w", encoding="utf-8") as f:
                        for r in self._index.values():
                            f.write(json.dumps(r) + "\n")
                except Exception:
                    pass
                return True
        return False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple lowercase word tokenizer."""
        return re.findall(r"[a-z0-9]+", (text or "").lower())


# ── Factory ───────────────────────────────────────────────────────────────

def get_memory_store(persist_dir: Optional[Path] = None):
    """Return the best available store. ChromaDB if installed, else JSONL."""
    if HAS_CHROMADB:
        return ChromaMemoryStore(persist_dir=persist_dir)
    return JSONLMemoryStore(
        store_path=(Path(persist_dir) / "projects.jsonl")
        if persist_dir else None,
    )
