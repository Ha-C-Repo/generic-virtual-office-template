"""
Your Company Virtual Office - Bid Pipeline State Machine

Tracks every bid from inbox scan to final outcome.
States: SCANNED → REVIEWING → PURSUING → SUBMITTED → WON | LOST | PASSED
Each transition logged with date, actor, and notes.
"""
import os, sqlite3, threading, json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

_DB = (Path(os.environ["LOCALAPPDATA"]) / "YourCompany" / "VirtualOffice" / "data" / "bid_pipeline.db") if os.environ.get("LOCALAPPDATA") else (Path(__file__).resolve().parent.parent / "data" / "bid_pipeline.db")
_lock = threading.Lock()

STATES = ["SCANNED", "REVIEWING", "PURSUING", "SUBMITTED", "WON", "LOST", "PASSED"]
VALID_TRANSITIONS = {
    "SCANNED": ["REVIEWING", "PASSED"],
    "REVIEWING": ["PURSUING", "PASSED"],
    "PURSUING": ["SUBMITTED", "PASSED"],
    "SUBMITTED": ["WON", "LOST"],
}

def _conn():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row; return c

def _init():
    c = _conn()
    # Create tables if they don't exist at all
    c.executescript("""
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, gc_company TEXT DEFAULT '', location TEXT DEFAULT '',
            tonnage TEXT DEFAULT '', estimated_value TEXT DEFAULT '',
            state TEXT DEFAULT 'SCANNED', score INTEGER DEFAULT 0,
            source TEXT DEFAULT 'scan', deadline TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bid_id INTEGER NOT NULL, from_state TEXT, to_state TEXT NOT NULL,
            actor TEXT DEFAULT 'system', notes TEXT DEFAULT '',
            ts TEXT NOT NULL, FOREIGN KEY (bid_id) REFERENCES bids(id)
        );
    """)
    # Schema migration - add any columns missing from older builds
    existing = {row[1] for row in c.execute("PRAGMA table_info(bids)").fetchall()}
    migrations = [
        ("name",            "TEXT DEFAULT ''"),  # may be missing if legacy schema used project_name
        ("state",           "TEXT DEFAULT 'SCANNED'"),
        ("score",           "INTEGER DEFAULT 0"),
        ("source",          "TEXT DEFAULT 'scan'"),
        ("deadline",        "TEXT"),
        ("gc_company",      "TEXT DEFAULT ''"),
        ("location",        "TEXT DEFAULT ''"),
        ("tonnage",         "TEXT DEFAULT ''"),
        ("estimated_value", "TEXT DEFAULT ''"),
        ("pdf_hash",        "TEXT DEFAULT ''"),  # SHA-256 of source PDF for dedup
        ("pdf_path",        "TEXT DEFAULT ''"),  # last processed PDF location
        ("boq_origin",      "TEXT DEFAULT ''"),  # planswift|bluebeam|manual_excel|synthetic - Ivan rule F
        ("boq_source_file", "TEXT DEFAULT ''"),  # path to the BOQ file actually used
        ("boq_resolved_at", "TEXT DEFAULT ''"),  # ISO timestamp of last resolve_boq() call
    ]
    for col, typedef in migrations:
        if col not in existing:
            c.execute(f"ALTER TABLE bids ADD COLUMN {col} {typedef}")
    c.commit()
    # If legacy schema had project_name and our new name column is empty, copy values across
    existing_after = {row[1] for row in c.execute("PRAGMA table_info(bids)").fetchall()}
    if "project_name" in existing_after and "name" in existing_after:
        c.execute("UPDATE bids SET name = COALESCE(name, '') WHERE name IS NULL")
        c.execute("UPDATE bids SET name = project_name WHERE (name IS NULL OR name = '') AND project_name IS NOT NULL")
        c.commit()
    # Now safe to create indexes on guaranteed-present columns
    c.execute("CREATE INDEX IF NOT EXISTS idx_bids_state ON bids(state)")
    c.commit(); c.close()
_init()

def add_bid(name, gc_company="", location="", tonnage="", estimated_value="",
            score=0, source="scan", deadline="", pdf_hash="", pdf_path=""):
    now = datetime.now(timezone.utc).isoformat()

    # Detect zero-tonnage + zero-value bids and mark INCOMPLETE so they
    # cannot be advanced without Owner providing real scope data.
    try:
        _ton_zero = not tonnage or float(tonnage) == 0
    except (ValueError, TypeError):
        _ton_zero = True
    try:
        _val_zero = not estimated_value or float(estimated_value) == 0
    except (ValueError, TypeError):
        _val_zero = True
    _initial_state = "INCOMPLETE" if (_ton_zero and _val_zero) else "SCANNED"

    with _lock:
        c = _conn()
        # Check for legacy schema with proposal_no NOT NULL
        cols = {row[1] for row in c.execute("PRAGMA table_info(bids)").fetchall()}
        has_legacy = "proposal_no" in cols
        has_pdf_hash = "pdf_hash" in cols
        has_pdf_path = "pdf_path" in cols

        if has_legacy:
            # Legacy schema has proposal_no NOT NULL + project_name + base_bid_total
            # Generate a synthetic proposal_no so the insert satisfies the constraint
            import uuid
            proposal_no = f"NC-{uuid.uuid4().hex[:8].upper()}"
            try:
                base_total = float(estimated_value) if estimated_value else 0
            except (ValueError, TypeError):
                base_total = 0
            try:
                t_num = float(tonnage) if tonnage else 0
            except (ValueError, TypeError):
                t_num = 0
            cur = c.execute(
                "INSERT INTO bids (proposal_no, project_name, name, gc_company, location, "
                "tonnage, base_bid_total, estimated_value, state, score, source, deadline, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (proposal_no, name, name, gc_company, location, t_num, base_total,
                 estimated_value, _initial_state, score, source, deadline, now, now)
            )
            bid_id = cur.lastrowid
            # Backfill pdf_hash + pdf_path columns if they exist
            if has_pdf_hash and pdf_hash:
                c.execute("UPDATE bids SET pdf_hash=? WHERE id=?", (pdf_hash, bid_id))
            if has_pdf_path and pdf_path:
                c.execute("UPDATE bids SET pdf_path=? WHERE id=?", (pdf_path, bid_id))
        else:
            cur = c.execute(
                "INSERT INTO bids (name,gc_company,location,tonnage,estimated_value,state,score,source,deadline,pdf_hash,pdf_path,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, gc_company, location, tonnage, estimated_value, _initial_state,
                 score, source, deadline, pdf_hash, pdf_path, now, now))
            bid_id = cur.lastrowid
        c.execute("INSERT INTO transitions (bid_id,from_state,to_state,actor,ts) VALUES (?,?,?,?,?)",
                  (bid_id, None, _initial_state, "system", now))
        c.commit(); c.close()
    try:
        from bridge.event_bus import emit
        emit("BID_SCANNED", {"bid_id": bid_id, "name": name,
                              "gc_company": gc_company, "state": _initial_state})
    except Exception:
        pass
    return bid_id


def find_bid_by_hash(pdf_hash: str):
    """Return the bid dict matching this PDF hash, or None.

    Used for dedup when Owner re-drops the same drawing.
    """
    if not pdf_hash:
        return None
    c = _conn()
    cols = {row[1] for row in c.execute("PRAGMA table_info(bids)").fetchall()}
    if "pdf_hash" not in cols:
        c.close()
        return None
    row = c.execute("SELECT * FROM bids WHERE pdf_hash=? ORDER BY id DESC LIMIT 1",
                    (pdf_hash,)).fetchone()
    c.close()
    return dict(row) if row else None


def find_bid_by_name(name: str):
    """Return the most recent bid matching this name (case-insensitive), or None.

    Secondary dedup path: catches re-drops where Owner renamed the PDF.
    """
    if not name or not name.strip():
        return None
    c = _conn()
    row = c.execute("SELECT * FROM bids WHERE LOWER(name)=LOWER(?) ORDER BY id DESC LIMIT 1",
                    (name.strip(),)).fetchone()
    c.close()
    return dict(row) if row else None


def update_bid(bid_id: int, **fields):
    """Update existing bid record. Only the fields you pass are written.

    Allowed: name, gc_company, location, tonnage, estimated_value, score,
    source, deadline, pdf_hash, pdf_path. Updates updated_at automatically.
    Returns True on success, False if bid not found.

    NOTE: Do NOT call this with score= when you want to preserve the
    bid's updated_at timestamp (e.g., from pipeline_score). Use
    _update_bid_score() instead so staleness tracking is not disrupted.
    """
    allowed = {"name", "gc_company", "location", "tonnage", "estimated_value",
               "score", "source", "deadline", "pdf_hash", "pdf_path",
               "boq_origin", "boq_source_file", "boq_resolved_at"}
    pairs = {k: v for k, v in fields.items() if k in allowed}
    if not pairs:
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        c = _conn()
        # Check bid exists
        row = c.execute("SELECT id FROM bids WHERE id=?", (bid_id,)).fetchone()
        if not row:
            c.close()
            return False
        # Schema-aware: filter pairs to columns that actually exist
        existing_cols = {r[1] for r in c.execute("PRAGMA table_info(bids)").fetchall()}
        pairs = {k: v for k, v in pairs.items() if k in existing_cols}
        if not pairs:
            c.close()
            return True  # nothing to do, technically successful
        set_clause = ", ".join(f"{k}=?" for k in pairs.keys())
        values = list(pairs.values()) + [now, bid_id]
        c.execute(f"UPDATE bids SET {set_clause}, updated_at=? WHERE id=?", values)
        c.commit()
        c.close()
    return True


def resolve_and_record_boq(bid_id: int,
                           bid_folder: str = "",
                           explicit_path: str = "") -> dict:
    """Run the BOQ source resolver for a bid, and persist the chosen
    origin/source onto the bid row.

    Returns a dict with the resolution result. Adds boq_origin,
    boq_source_file, boq_resolved_at to the bids row so reconciliation
    Rule F can read them later.

    Added 2026-05-23 from Ivan's PlanSwift-as-takeoff-tool finding.
    """
    from pathlib import Path as _P
    try:
        from bridge.boq_resolver import resolve_boq
        from bridge.boq_sources import BoqContext
    except Exception as e:
        return {"error": f"BOQ resolver not available: {e}"}

    b = get_bid(bid_id)
    if not b:
        return {"error": f"Bid {bid_id} not found"}

    ctx = BoqContext(
        bid_id=bid_id,
        bid_name=b.get("name", ""),
        bid_folder=_P(bid_folder) if bid_folder else None,
        explicit_path=_P(explicit_path) if explicit_path else None,
    )
    result = resolve_boq(ctx)
    now = datetime.now(timezone.utc).isoformat()

    update_bid(
        bid_id,
        boq_origin=result.payload.boq_origin,
        boq_source_file=result.payload.source_file,
        boq_resolved_at=now,
    )
    return {
        "success": True,
        "bid_id": bid_id,
        "chosen": result.chosen_adapter,
        "boq_origin": result.payload.boq_origin,
        "source_file": result.payload.source_file,
        "row_count": result.payload.row_count,
        "fidelity_rank": result.payload.fidelity_rank,
        "probed": result.probed_adapters,
        "skipped": result.skipped_adapters,
        "notes": result.notes,
    }


def _update_bid_score(bid_id: int, score: int) -> bool:
    """Write ONLY the score column. Does NOT touch updated_at.

    pipeline_score and rescore_all must use this instead of update_bid so
    that a scoring pass doesn't reset the bid's staleness timestamp.
    If update_bid(score=N) is used, the recency penalty in _score_bid
    will never fire because the timestamp gets refreshed on every score call.
    """
    with _lock:
        c = _conn()
        row = c.execute("SELECT id FROM bids WHERE id=?", (bid_id,)).fetchone()
        if not row:
            c.close()
            return False
        c.execute("UPDATE bids SET score=? WHERE id=?", (score, bid_id))
        c.commit()
        c.close()
    return True

def next_state(bid_id) -> dict:
    """Return the natural next forward state for a bid without advancing it.

    Item 2 fix: Owner should not need to know the pipeline order to move
    a bid forward. This helper surfaces the next state so callers can either
    display it or pass it to advance().

    Returns:
        {bid_id, current, next, valid_transitions}
        error key if bid not found or already terminal.
    """
    with _lock:
        c = _conn()
        row = c.execute("SELECT state FROM bids WHERE id=?", (bid_id,)).fetchone()
        c.close()
    if not row:
        return {"error": f"Bid {bid_id} not found"}
    current = row["state"]
    valid = VALID_TRANSITIONS.get(current, [])
    if not valid:
        return {"error": f"Bid is in terminal state {current}. No forward transitions.",
                "current": current}
    # Forward path is always index 0; PASSED (kill) is index 1 when present
    forward = valid[0]
    return {
        "bid_id": bid_id,
        "current": current,
        "next": forward,
        "all_valid": valid,
    }


def advance(bid_id, new_state=None, actor="Owner", notes="",
            bypass_artifact_gate=False, bypass_reason=""):
    """Advance a bid to new_state, or infer the next forward state.

    Item 2 fix: new_state is now optional. When omitted, the bid moves to
    its natural next state per VALID_TRANSITIONS (e.g. SCANNED -> REVIEWING).
    The caller can still pass new_state explicitly (e.g. 'PASSED') to override.

    Artifact gate (added 2026-05-23 from Cowork recon report finding):
    When new_state == SUBMITTED, the two-PDF pair (client + GP) must exist
    in output/ before the transition is allowed. Pass bypass_artifact_gate=
    True with a non-empty bypass_reason to override (e.g. when submission
    happened through a GC portal and the PDFs live outside output/). The
    bypass reason is appended to the transition notes for the audit trail.

    Examples:
        advance(4)                       # SCANNED -> REVIEWING automatically
        advance(4, 'PASSED')             # kill the bid
        advance(4, notes='Ivan signed')  # forward with a note, state inferred
        advance(4, 'SUBMITTED', bypass_artifact_gate=True,
                bypass_reason='Submitted via Procore portal')
    """
    with _lock:
        c = _conn()
        row = c.execute(
            "SELECT state, name FROM bids WHERE id=?", (bid_id,)
        ).fetchone()
        if not row: c.close(); return {"error": "Bid not found"}
        current = row["state"]
        bid_name = row["name"]
        valid = VALID_TRANSITIONS.get(current, [])

        # Infer forward state when caller omits new_state
        if new_state is None:
            if not valid:
                c.close()
                return {"error": f"Bid is in terminal state {current}. No forward transition available."}
            new_state = valid[0]  # natural forward step

        if new_state not in valid:
            c.close()
            return {"error": f"Cannot transition {current} → {new_state}. Valid: {valid}"}

        # Artifact gate: SUBMITTED requires the two-PDF pair on disk
        gate_audit = ""
        if new_state == "SUBMITTED":
            try:
                from bridge.bid_artifact_gate import gate_or_block
            except Exception as e:
                c.close()
                return {"error": f"Artifact gate module not available: {e}"}
            g = gate_or_block(
                bid_name=bid_name,
                new_state=new_state,
                bypass=bypass_artifact_gate,
                bypass_reason=bypass_reason,
            )
            if not g.get("ok"):
                c.close()
                return {
                    "error": g.get("error", "Artifact gate blocked the transition"),
                    "fix": g.get("fix", ""),
                    "missing": g.get("missing", []),
                }
            gate_audit = g.get("audit_note", "")

        now = datetime.now(timezone.utc).isoformat()
        merged_notes = notes
        if gate_audit:
            merged_notes = f"{notes} | {gate_audit}".strip(" |") if notes else gate_audit
        c.execute("UPDATE bids SET state=?, updated_at=? WHERE id=?", (new_state, now, bid_id))
        c.execute("INSERT INTO transitions (bid_id,from_state,to_state,actor,notes,ts) VALUES (?,?,?,?,?,?)",
                  (bid_id, current, new_state, actor, merged_notes, now))
        c.commit(); c.close()
    result = {"success": True, "bid_id": bid_id, "from": current, "to": new_state}
    try:
        from bridge.event_bus import emit
        event_map = {"WON": "BID_WON", "LOST": "BID_LOST"}
        etype = event_map.get(new_state, "BID_SCANNED")
        emit(etype, {"bid_id": bid_id, "state": new_state, "from": current, "actor": actor})
    except Exception:
        pass
    return result


def restore(bid_id, target_state=None, actor="Owner", notes=""):
    """Restore a terminal bid (PASSED only) to its prior active state.

    Bypasses the FSM intentionally - restore is an exception path, not a
    normal flow. Looks up the most recent transition INTO PASSED to find
    what state to restore to, unless target_state is given explicitly.
    Logs the restore in the transitions table for full audit trail.

    Only PASSED bids can be restored. WON and LOST are intentionally
    permanent - if a "won" bid actually fell through, that's a different
    record entirely.
    """
    TERMINAL_RESTORABLE = {"PASSED"}
    ACTIVE_STATES = {"SCANNED", "REVIEWING", "PURSUING", "SUBMITTED"}
    with _lock:
        c = _conn()
        row = c.execute("SELECT state FROM bids WHERE id=?", (bid_id,)).fetchone()
        if not row:
            c.close()
            return {"error": "Bid not found"}
        current = row["state"]
        if current not in TERMINAL_RESTORABLE:
            c.close()
            return {"error": f"Bid {bid_id} is {current}, not PASSED. "
                             f"Only PASSED bids can be restored. WON/LOST are permanent."}
        # Find the state we came from when we got killed
        if target_state is None:
            prev = c.execute(
                "SELECT from_state FROM transitions WHERE bid_id=? AND to_state='PASSED' "
                "ORDER BY ts DESC LIMIT 1",
                (bid_id,)
            ).fetchone()
            if prev and prev["from_state"] in ACTIVE_STATES:
                target_state = prev["from_state"]
            else:
                target_state = "SCANNED"  # safe default
        if target_state not in ACTIVE_STATES:
            c.close()
            return {"error": f"Cannot restore to {target_state}; must be one of {ACTIVE_STATES}"}
        now = datetime.now(timezone.utc).isoformat()
        c.execute("UPDATE bids SET state=?, updated_at=? WHERE id=?",
                  (target_state, now, bid_id))
        c.execute(
            "INSERT INTO transitions (bid_id,from_state,to_state,actor,notes,ts) "
            "VALUES (?,?,?,?,?,?)",
            (bid_id, current, target_state, f"{actor} (restore)",
             notes or "restored from terminal state", now)
        )
        c.commit()
        c.close()
    return {"success": True, "bid_id": bid_id, "from": current, "to": target_state}


def get_bid(bid_id):
    with _lock:
        c = _conn()
        row = c.execute("SELECT * FROM bids WHERE id=?", (bid_id,)).fetchone()
        if not row: c.close(); return None
        hist = c.execute("SELECT * FROM transitions WHERE bid_id=? ORDER BY ts", (bid_id,)).fetchall()
        c.close()
    return {**dict(row), "history": [dict(h) for h in hist]}

def get_pipeline(state=None, limit=50):
    with _lock:
        c = _conn()
        if state:
            rows = c.execute("SELECT * FROM bids WHERE state=? ORDER BY updated_at DESC LIMIT ?",
                            (state, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM bids WHERE state NOT IN ('WON','LOST','PASSED') ORDER BY updated_at DESC LIMIT ?",
                            (limit,)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def get_stale_bids(days=3):
    """Bids sitting in REVIEWING for more than N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()  # vj: duration-math
    with _lock:
        c = _conn()
        rows = c.execute("SELECT * FROM bids WHERE state='REVIEWING' AND updated_at < ? ORDER BY updated_at",
                        (cutoff,)).fetchall()
        c.close()
    return [dict(r) for r in rows]

def pipeline_summary():
    with _lock:
        c = _conn()
        counts = {}
        for s in STATES:
            counts[s] = c.execute("SELECT COUNT(*) FROM bids WHERE state=?", (s,)).fetchone()[0]
        total_value = c.execute(
            "SELECT COUNT(*) FROM bids WHERE state IN ('PURSUING','SUBMITTED')").fetchone()[0]
        c.close()
    return {"states": counts, "active_count": sum(counts.get(s,0) for s in ["SCANNED","REVIEWING","PURSUING","SUBMITTED"])}

def stats():
    with _lock:
        c = _conn()
        total = c.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
        won = c.execute("SELECT COUNT(*) FROM bids WHERE state='WON'").fetchone()[0]
        c.close()
    return {"total_bids": total, "won": won, "win_rate": f"{won*100//max(total,1)}%"}
