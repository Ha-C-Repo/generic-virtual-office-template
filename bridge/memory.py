"""
Your Company Virtual Office - Conversation Persistence

SQLite-backed conversation memory. Survives app restarts.

Owner can say "what did you tell me about ICD yesterday?"
and the system has the context.

Schema:
  sessions(id, started_at, ended_at)
  messages(id, session_id, role, content, provider, model, ts)

Retention: 30 days. Auto-prunes on boot.
"""

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "conversations.db"
    return Path(__file__).resolve().parent.parent / "data" / "conversations.db"

_DB_PATH = _resolve_db_path()
_lock = threading.Lock()
_current_session_id: Optional[int] = None
_RETENTION_DAYS = 30


def _conn():
    """Thread-safe connection with WAL mode."""
    c = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row
    return c


def _init_db():
    """Create tables if they don't exist."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = _conn()
    try:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider TEXT DEFAULT '',
                model TEXT DEFAULT '',
                ts TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        except Exception:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts)")
        except Exception:
            pass
        c.commit()
    finally:
        c.close()


_initialized = False

def _ensure_db():
    """Initialize DB once, thread-safe."""
    global _initialized
    if _initialized:
        return
    _init_db()
    _initialized = True


def start_session() -> int:
    """Start a new conversation session. Returns session_id."""
    global _current_session_id
    with _lock:
        _ensure_db()
        c = _conn()
        try:
            cur = c.execute("INSERT INTO sessions (started_at) VALUES (?)", (datetime.now(timezone.utc).isoformat(),))
            _current_session_id = cur.lastrowid
            c.commit()
            return _current_session_id
        finally:
            c.close()


def end_session():
    """Mark the current session as ended."""
    global _current_session_id
    if _current_session_id is None:
        return
    with _lock:
        c = _conn()
        c.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), _current_session_id)
        )
        c.commit()
        c.close()
        _current_session_id = None


def save_message(role: str, content: str, provider: str = "", model: str = ""):
    """Persist a message to the current session."""
    global _current_session_id
    if _current_session_id is None:
        start_session()
    with _lock:
        c = _conn()
        c.execute(
            "INSERT INTO messages (session_id, role, content, provider, model, ts) VALUES (?,?,?,?,?,?)",
            (_current_session_id, role, content[:10000], provider, model, datetime.now(timezone.utc).isoformat())
        )
        c.commit()
        c.close()


def get_last_session_history(limit: int = 20) -> list:
    """Load the last session's conversation history for context restoration.
    Returns list of {role, content, ts} dicts.
    """
    with _lock:
        _ensure_db()
        c = _conn()
        # Find the most recent session with messages
        row = c.execute("""
            SELECT s.id FROM sessions s
            JOIN messages m ON m.session_id = s.id
            ORDER BY s.started_at DESC LIMIT 1
        """).fetchone()
        if not row:
            c.close()
            return []
        session_id = row["id"]
        rows = c.execute(
            "SELECT role, content, provider, model, ts FROM messages WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        c.close()
        return [dict(r) for r in reversed(rows)]


def get_recent_messages(hours: int = 24, limit: int = 50) -> list:
    """Get messages from the last N hours across all sessions."""
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()  # vj: duration-math
    with _lock:
        _ensure_db()
        c = _conn()
        rows = c.execute(
            "SELECT role, content, provider, model, ts FROM messages WHERE ts > ? ORDER BY ts DESC LIMIT ?",
            (cutoff, limit)
        ).fetchall()
        c.close()
        return [dict(r) for r in reversed(rows)]


def search_history(query: str, limit: int = 10) -> list:
    """Search conversation history by keyword."""
    with _lock:
        _ensure_db()
        c = _conn()
        rows = c.execute(
            "SELECT role, content, ts FROM messages WHERE content LIKE ? ORDER BY ts DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]


def prune_old(days: int = None):
    """Delete messages older than retention period. Returns count of deleted messages."""
    days = days or _RETENTION_DAYS
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()  # vj: duration-math
    with _lock:
        c = _conn()
        cur = c.execute("DELETE FROM messages WHERE ts < ?", (cutoff,))
        msg_count = cur.rowcount
        c.execute("DELETE FROM sessions WHERE ended_at IS NOT NULL AND ended_at < ?", (cutoff,))
        c.execute("VACUUM")
        c.commit()
        c.close()
    return msg_count


def stats() -> dict:
    """Return conversation statistics."""
    with _lock:
        _ensure_db()
        c = _conn()
        total_msgs = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        total_sessions = c.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        oldest = c.execute("SELECT MIN(ts) FROM messages").fetchone()[0]
        c.close()
        return {
            "total_messages": total_msgs,
            "total_sessions": total_sessions,
            "oldest_message": oldest,
            "retention_days": _RETENTION_DAYS,
            "current_session": _current_session_id,
        }


# Lazy initialization - _ensure_db() is called on first use
