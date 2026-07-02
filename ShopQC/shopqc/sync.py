"""Offline sync between the local SQLite cache and the authoritative Postgres.

Capture: in supabase mode the cache carries two extra columns on every table
(sync_uid, a stable cross-store identity, and updated_at, a last-write clock) plus
an _outbox table and AFTER INSERT/UPDATE/DELETE triggers. The triggers record one
outbox row per local change with no SQL parsing, and a control flag lets the pull
and flush write the cache without re-capturing their own work.

flush: drain the outbox to Postgres. Parents go first so a child can resolve its
foreign keys by the parent sync_uid. Each change is last-write-wins by updated_at
(the local change time), and every applied or superseded change writes an audit
row. After a clean flush the cache is rebuilt from Postgres so offline rows pick up
their server ids.

pull: mirror the Postgres tables into the cache so offline reads see recent state.

flush and pull are pure functions of (cache_conn, pg_client). The background thread
in supabase_backend calls them; the tests call them directly with a fake Postgres.
"""

import json

from . import db

# Topological order: a parent always precedes its children, so a flush upserts the
# parent (and learns its Postgres id) before any child that points at it, and a pull
# inserts parents first. reversed() is a safe delete order for the rebuild.
SYNC_TABLES = ["projects", "bol_items", "pieces", "rir_records", "fastener_lots",
               "traveler_fields", "ncrs", "weld_records", "release_records"]

# child table -> {foreign key column: parent table}. Used to remap a child's local
# parent id to the Postgres parent id by way of the parent natural key.
PARENTS = {
    "bol_items": {"project_id": "projects"},
    "pieces": {"project_id": "projects"},
    "rir_records": {"project_id": "projects"},
    "fastener_lots": {"project_id": "projects"},
    "traveler_fields": {"piece_pk": "pieces"},
    "ncrs": {"project_id": "projects", "piece_pk": "pieces"},
    "weld_records": {"piece_pk": "pieces"},
    "release_records": {"piece_pk": "pieces"},
}

# Last-write-wins is keyed on the natural key where one exists (per the brief:
# project code, piece_id), so two stations that created the same project or piece
# offline converge to one row instead of colliding on the UNIQUE constraint. The
# traveler field has the natural composite (its piece plus the field number). The
# remaining record tables have no natural key (each is a distinct receiving, NCR,
# weld, or release event), so they key on sync_uid and stay separate, which is
# correct. The two parent tables are the only ones referenced as foreign keys, and
# both carry a natural key, so a child resolves its parent by that key and is robust
# to a diverged sync_uid.
CONFLICT_KEYS = {
    "projects": ["code"],
    "pieces": ["piece_id"],
    "traveler_fields": ["piece_pk", "field_number"],
}
_DEFAULT_KEY = ["sync_uid"]
PARENT_NATKEY = {"projects": "code", "pieces": "piece_id"}

_TS = "strftime('%Y-%m-%d %H:%M:%f','now')"  # UTC, millisecond, lexically sortable

_CONTROL_DDL = """
CREATE TABLE IF NOT EXISTS _sync_control (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  applying INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO _sync_control (id, applying) VALUES (1, 0);
CREATE TABLE IF NOT EXISTS _outbox (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,
  row_id INTEGER,
  sync_uid TEXT,
  op TEXT NOT NULL,
  ts TEXT NOT NULL
);
"""


def _trigger_sql(t: str) -> str:
    """The three capture triggers for one table. The WHEN guard skips capture while
    the pull or flush is applying server state (_sync_control.applying = 1). The
    insert trigger assigns the sync_uid for a brand new local row (a pulled row
    already carries one, so its WHEN NEW.sync_uid IS NULL is false and it is not
    re-queued). The update trigger only fires for a genuine edit, identified by the
    row already having a sync_uid (OLD.sync_uid IS NOT NULL); the insert trigger's
    own sync_uid-fill update has OLD.sync_uid NULL, so it never double-queues, which
    holds whether or not this SQLite build recurses triggers."""
    return f"""
CREATE TRIGGER IF NOT EXISTS _ob_ins_{t} AFTER INSERT ON {t}
WHEN NEW.sync_uid IS NULL AND (SELECT applying FROM _sync_control WHERE id=1) = 0
BEGIN
  UPDATE {t} SET sync_uid = lower(hex(randomblob(16))), updated_at = {_TS}
    WHERE id = NEW.id;
  INSERT INTO _outbox (table_name, row_id, sync_uid, op, ts)
    VALUES ('{t}', NEW.id, (SELECT sync_uid FROM {t} WHERE id = NEW.id), 'upsert', {_TS});
END;
CREATE TRIGGER IF NOT EXISTS _ob_upd_{t} AFTER UPDATE ON {t}
WHEN OLD.sync_uid IS NOT NULL AND (SELECT applying FROM _sync_control WHERE id=1) = 0
BEGIN
  INSERT INTO _outbox (table_name, row_id, sync_uid, op, ts)
    VALUES ('{t}', NEW.id, NEW.sync_uid, 'upsert', {_TS});
END;
CREATE TRIGGER IF NOT EXISTS _ob_del_{t} AFTER DELETE ON {t}
WHEN OLD.sync_uid IS NOT NULL AND (SELECT applying FROM _sync_control WHERE id=1) = 0
BEGIN
  INSERT INTO _outbox (table_name, row_id, sync_uid, op, ts)
    VALUES ('{t}', OLD.id, OLD.sync_uid, 'delete', {_TS});
END;
"""


def ensure_cache_sync(conn) -> None:
    """Make a SqliteBackend-shaped cache ready for offline sync: add sync_uid and
    updated_at to every table, the control flag, the outbox, and the capture
    triggers. Additive and idempotent, safe to run on every startup. Recursive
    triggers must be off (the default) for the insert trigger's sync_uid fill."""
    conn.execute("PRAGMA recursive_triggers=OFF")
    conn.executescript(_CONTROL_DDL)
    for t in SYNC_TABLES:
        cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({t})")}
        if "sync_uid" not in cols:
            conn.execute(f"ALTER TABLE {t} ADD COLUMN sync_uid TEXT")
        if "updated_at" not in cols:
            conn.execute(f"ALTER TABLE {t} ADD COLUMN updated_at TEXT")
        conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{t}_sync_uid "
                     f"ON {t}(sync_uid) WHERE sync_uid IS NOT NULL")
    for t in SYNC_TABLES:
        conn.executescript(_trigger_sql(t))
    conn.commit()


def _set_applying(conn, on: int) -> None:
    conn.execute("UPDATE _sync_control SET applying=? WHERE id=1", (on,))
    conn.commit()


def _payload_columns(row_keys):
    # Everything the cache row carries except its local id and the local clock; the
    # flush sets updated_at explicitly to the change time. sync_uid is kept (it is
    # the cross-store identity and the conflict target).
    return [c for c in row_keys if c not in ("id", "updated_at")]


def _resolve_parent_id(cache, pg, parent_table, local_parent_id):
    """Local parent id -> parent natural key (from the cache) -> Postgres parent id.
    Resolving by natural key (project code, piece_id) rather than sync_uid means a
    child still finds its parent even if the parent already existed on the server
    under a different sync_uid. Returns None if the parent cannot be located."""
    natkey = PARENT_NATKEY[parent_table]
    r = cache.execute(f"SELECT {natkey} FROM {parent_table} WHERE id=?",
                      (local_parent_id,)).fetchone()
    if not r or r[natkey] is None:
        return None
    got = pg.execute(f"SELECT id FROM {parent_table} WHERE {natkey}=?", (r[natkey],))
    return got[0]["id"] if got else None


def flush(cache, pg, station="?") -> dict:
    """Drain the outbox to Postgres with last-write-wins and an audit row per change,
    then rebuild the cache from Postgres. Returns counts. Safe to call when the
    outbox is empty (no-op)."""
    rows = cache.execute(
        "SELECT seq, table_name, sync_uid, op, ts FROM _outbox ORDER BY seq").fetchall()
    if not rows:
        return {"applied": 0, "superseded": 0, "deleted": 0, "unresolved": 0,
                "pending": 0}

    # Collapse to the latest op per (table, sync_uid); the highest seq is newest.
    latest = {}
    for r in rows:
        latest[(r["table_name"], r["sync_uid"])] = {
            "table": r["table_name"], "sync_uid": r["sync_uid"],
            "op": r["op"], "ts": r["ts"]}

    applied = superseded = deleted = unresolved = 0
    pg.begin_sync()
    try:
        for table in SYNC_TABLES:  # parents before children
            for key, e in latest.items():
                if e["table"] != table:
                    continue
                uid, ts, op = e["sync_uid"], e["ts"], e["op"]
                if op == "delete":
                    pg.execute(f"DELETE FROM {table} WHERE sync_uid=?", (uid,))
                    _audit(pg, table, uid, "delete", None, station, "applied")
                    deleted += 1
                    continue
                row = cache.execute(f"SELECT * FROM {table} WHERE sync_uid=?",
                                    (uid,)).fetchone()
                if row is None:
                    continue  # created then deleted locally; nothing to upsert
                payload = {c: row[c] for c in _payload_columns(row.keys())}
                missing_parent = False
                for fk_col, parent in PARENTS.get(table, {}).items():
                    if payload.get(fk_col) is not None:
                        resolved = _resolve_parent_id(cache, pg, parent,
                                                      payload[fk_col])
                        if resolved is None:
                            missing_parent = True
                            break
                        payload[fk_col] = resolved
                if missing_parent:
                    # A non-NULL parent did not resolve on the server. Do not write a
                    # corrupt NULL foreign key; record it so the gap is traceable.
                    _audit(pg, table, uid, "upsert", payload, station, "fk_unresolved")
                    unresolved += 1
                    continue
                ck = CONFLICT_KEYS.get(table, _DEFAULT_KEY)
                where = " AND ".join(f"{c}=?" for c in ck)
                existing = pg.execute(
                    f"SELECT updated_at FROM {table} WHERE {where}",
                    [payload[c] for c in ck])
                if existing and existing[0]["updated_at"] is not None \
                        and ts < existing[0]["updated_at"]:
                    _audit(pg, table, uid, "upsert", payload, station, "superseded")
                    superseded += 1
                    continue
                _upsert(pg, table, payload, ts, ck)
                _audit(pg, table, uid, "upsert", payload, station, "applied")
                applied += 1
    finally:
        pg.end_sync()

    _set_applying(cache, 1)
    try:
        cache.execute("DELETE FROM _outbox")
        cache.commit()
        pull(pg, cache, _applying_held=True)
    finally:
        _set_applying(cache, 0)
    return {"applied": applied, "superseded": superseded, "deleted": deleted,
            "unresolved": unresolved, "pending": 0}


def _upsert(pg, table, payload: dict, ts: str, conflict_cols) -> None:
    cols = list(payload.keys()) + ["updated_at"]
    values = [payload[c] for c in payload] + [ts]
    placeholders = ",".join("?" * len(cols))
    # On a natural-key conflict, keep the server's surrogate id and sync_uid (its
    # existing identity) and update only the data columns plus the clock.
    skip = set(conflict_cols) | {"sync_uid"}
    set_clause = ",".join(f"{c}=excluded.{c}" for c in cols if c not in skip)
    pg.execute(
        f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({','.join(conflict_cols)}) DO UPDATE SET {set_clause}", values)


def _audit(pg, table, uid, op, payload, station, outcome) -> None:
    pg.execute(
        "INSERT INTO audit_log (table_name, sync_uid, op, payload, source, station, "
        "applied_at, outcome) VALUES (?,?,?,?,?,?,?,?)",
        (table, uid, op, json.dumps(payload) if payload is not None else None,
         "outbox", station, db.now(), outcome))


def pull(pg, cache, _applying_held=False) -> int:
    """Replace the cache contents with the current Postgres state so offline reads
    see recent cross-station data. Children are deleted first and parents inserted
    first to respect the cache foreign keys. Returns the row count pulled."""
    if not _applying_held:
        _set_applying(cache, 1)
    try:
        for t in reversed(SYNC_TABLES):
            cache.execute(f"DELETE FROM {t}")
        total = 0
        for t in SYNC_TABLES:
            server = pg.execute(f"SELECT * FROM {t}")
            for r in server:
                cols = list(r.keys())
                placeholders = ",".join("?" * len(cols))
                cache.execute(
                    f"INSERT INTO {t} ({','.join(cols)}) VALUES ({placeholders})",
                    [r[c] for c in cols])
                total += 1
        cache.commit()
        return total
    finally:
        if not _applying_held:
            _set_applying(cache, 0)
