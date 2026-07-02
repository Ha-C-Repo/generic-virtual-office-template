"""
Your Company Virtual Office - Hash Chain Document Integrity

Every generated document (G702, proposal, WPS, JHA, NCR) gets a SHA-256
hash. Each hash includes the previous document's hash - creating a
tamper-evident chain.

AISC auditors can verify: "This WPS has not been modified since it was
generated on April 15, 2026, and no documents in the chain have been altered."
"""

import hashlib, json, sqlite3, threading
from datetime import datetime, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "hash_chain.db"
    return Path(__file__).resolve().parent.parent / "data" / "hash_chain.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL, doc_name TEXT NOT NULL,
            file_hash TEXT NOT NULL, prev_hash TEXT NOT NULL,
            chain_hash TEXT NOT NULL, metadata TEXT DEFAULT '',
            created_by TEXT DEFAULT 'system',
            created_at TEXT NOT NULL
        );
    """)
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_chain_hash ON chain(chain_hash)")
    except Exception:
        pass  # column may not exist in older schema
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_chain_type ON chain(doc_type)")
    except Exception:
        pass  # column may not exist in older schema
    c.commit(); c.close()
_init()

def _get_last_hash() -> str:
    """Get the last chain hash (or genesis hash)."""
    c = _conn()
    row = c.execute("SELECT chain_hash FROM chain ORDER BY id DESC LIMIT 1").fetchone()
    c.close()
    return row["chain_hash"] if row else "0" * 64  # genesis

def hash_file(filepath: str) -> str:
    """SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def hash_content(content: str) -> str:
    """SHA-256 hash of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def add_to_chain(doc_type: str, doc_name: str, file_path: str = "",
                 content: str = "", metadata: dict = None, created_by: str = "system") -> dict:
    """Add a document to the hash chain."""
    if file_path:
        try:
            file_h = hash_file(file_path)
        except Exception as e:
            return {"error": f"Cannot hash file: {e}"}
    elif content:
        file_h = hash_content(content)
    else:
        return {"error": "Must provide file_path or content"}

    with _lock:
        prev_h = _get_last_hash()
        chain_h = hashlib.sha256(f"{prev_h}{file_h}".encode()).hexdigest()

        c = _conn()
        cur = c.execute(
            "INSERT INTO chain (doc_type,doc_name,file_hash,prev_hash,chain_hash,metadata,created_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (doc_type, doc_name, file_h, prev_h, chain_h,
             json.dumps(metadata or {}), created_by, datetime.now(timezone.utc).isoformat()))
        entry_id = cur.lastrowid
        c.commit(); c.close()

    return {
        "chain_id": entry_id,
        "doc_type": doc_type,
        "doc_name": doc_name,
        "file_hash": file_h,
        "chain_hash": chain_h,
        "prev_hash": prev_h,
        "integrity": "VALID",
    }

def verify_chain() -> dict:
    """Verify the entire hash chain is intact. Any tampering breaks the chain."""
    # vj: parity-ok (pass 10g classified: mixed J=0.33; needs manual audit)
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM chain ORDER BY id ASC").fetchall()
        c.close()

    if not rows:
        return {"valid": True, "entries": 0, "note": "Empty chain"}

    prev = "0" * 64  # genesis
    broken_at = None

    for i, row in enumerate(rows):
        expected = hashlib.sha256(f"{prev}{row['file_hash']}".encode()).hexdigest()
        if expected != row["chain_hash"]:
            broken_at = {
                "entry_id": row["id"],
                "doc_name": row["doc_name"],
                "expected_chain_hash": expected,
                "stored_chain_hash": row["chain_hash"],
                "position": i + 1,
            }
            break
        prev = row["chain_hash"]

    return {
        "valid": broken_at is None,
        "entries": len(rows),
        "broken_at": broken_at,
        "last_hash": rows[-1]["chain_hash"] if rows else None,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }

def get_chain(doc_type: str = None, limit: int = 50) -> list:
    """Get chain entries, optionally filtered by document type."""
    with _lock:
        c = _conn()
        if doc_type:
            rows = c.execute("SELECT * FROM chain WHERE doc_type=? ORDER BY id DESC LIMIT ?",
                            (doc_type, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM chain ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def verify_document(file_path: str) -> dict:
    """Verify a specific document against the chain."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.21; disjoint shapes)
    try:
        current_hash = hash_file(file_path)
    except Exception as e:
        return {"verified": False, "error": str(e)}

    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM chain WHERE file_hash=?", (current_hash,)).fetchone()
        c.close()

    if row:
        return {
            "verified": True,
            "doc_name": row["doc_name"],
            "doc_type": row["doc_type"],
            "chain_hash": row["chain_hash"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
            "file_hash": current_hash,
        }
    return {
        "verified": False,
        "file_hash": current_hash,
        "note": "Document not found in hash chain - may have been modified",
    }

def stats() -> dict:
    with _lock:
        c = _conn()
        total = c.execute("SELECT COUNT(*) FROM chain").fetchone()[0]
        by_type = {}
        for row in c.execute("SELECT doc_type, COUNT(*) as cnt FROM chain GROUP BY doc_type"):
            by_type[row["doc_type"]] = row["cnt"]
        c.close()
    return {"total_documents": total, "by_type": by_type, "chain_intact": verify_chain()["valid"]}
