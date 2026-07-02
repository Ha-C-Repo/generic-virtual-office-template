"""
Your Company Virtual Office - Audit Log

Append-only record of every significant action:
- AI responses (provider, model, token count)
- Emails sent/drafted
- Bid decisions (pursue/pass/win/loss)
- Document generations
- SMS sent/received
- Blocker state changes

Queryable via bridge. Never modified, never deleted.
"""
import sqlite3, threading, hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

def _resolve_db_path() -> Path:
    """Frozen EXE writes to LOCALAPPDATA (Program Files is read-only)."""
    import os
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data" / "audit.db"
    return Path(__file__).resolve().parent.parent / "data" / "audit.db"

_DB = _resolve_db_path()
_lock = threading.Lock()

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
            detail TEXT DEFAULT '', content_hash TEXT DEFAULT '',
            provider TEXT DEFAULT '', model TEXT DEFAULT '',
            metadata TEXT DEFAULT ''
        )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit(action)")
    c.commit(); c.close()
_init()

def log(actor, action, detail="", content="", provider="", model="", metadata=""):
    """Append an audit entry. Content is hashed, not stored in full."""
    h = hashlib.sha256(content.encode()).hexdigest()[:16] if content else ""
    with _lock:
        c = _conn()
        c.execute("INSERT INTO audit (ts,actor,action,detail,content_hash,provider,model,metadata) VALUES (?,?,?,?,?,?,?,?)",
                  (datetime.now(timezone.utc).isoformat(), actor, action, detail[:2000], h, provider, model, metadata[:1000]))
        c.commit(); c.close()

def query(action=None, actor=None, hours=24, limit=100):
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()  # vj: duration-math
    with _lock:
        c = _conn()
        sql = "SELECT * FROM audit WHERE ts > ?"
        params = [cutoff]
        if action:
            sql += " AND action LIKE ?"; params.append(f"%{action}%")
        if actor:
            sql += " AND actor = ?"; params.append(actor)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = c.execute(sql, params).fetchall()
        c.close()
    return [dict(r) for r in rows]

def stats(hours=24):
    entries = query(hours=hours, limit=10000)
    by_action = {}
    for e in entries:
        by_action[e["action"]] = by_action.get(e["action"], 0) + 1
    return {"total": len(entries), "by_action": by_action, "hours": hours}

# Convenience loggers
def log_ai(message, response, provider, model):
    log("system", "ai_response", f"Q: {message[:100]}", response, provider, model)

def log_email(to, subject, method="outlook"):
    log("owner", "email_sent", f"To: {to} | Subj: {subject}", "", "", "", method)

def log_bid_decision(bid_name, decision, actor="owner"):
    log(actor, f"bid_{decision}", bid_name)

def log_document(doc_type, filename):
    log("system", f"doc_{doc_type}", filename)

def log_sms(direction, number, body_preview):
    log("system", f"sms_{direction}", f"{number}: {body_preview[:80]}")


def prune(retain_days: int = 30) -> int:
    """Delete old audit entries. Returns count deleted.

    Strategy:
    - self_test entries: cap at 100 rows total (high-volume, diagnostic noise)
    - all other entries: retain for retain_days (30 days default)

    Called automatically after each self-test run.
    """
    cutoff_all = (datetime.now(timezone.utc) - timedelta(days=retain_days)).isoformat()
    with _lock:
        c = _conn()
        # Cap self_test at 100 most recent entries
        keep_ids = [r[0] for r in c.execute(
            "SELECT id FROM audit WHERE actor='self_test' ORDER BY ts DESC LIMIT 100"
        ).fetchall()]
        if keep_ids:
            marks = ",".join("?" * len(keep_ids))
            n_test = c.execute(
                f"DELETE FROM audit WHERE actor='self_test' AND id NOT IN ({marks})",
                keep_ids
            ).rowcount
        else:
            n_test = 0
        # Date-prune all other entries
        n_old = c.execute(
            "DELETE FROM audit WHERE actor != 'self_test' AND ts < ?",
            (cutoff_all,)
        ).rowcount
        c.commit(); c.close()
    return n_test + n_old
