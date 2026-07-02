"""Storage backend selection.

The app talks to one connection object (ctx.conn) that behaves like a
sqlite3.Connection. Two backends sit behind that single contract:

- SqliteBackend: the shipped behavior. One SQLite file (journal_mode=DELETE, WAL
  off) opened by db.connect, schema applied by db.init_db. Used for local and
  shared-folder deployments, and as the fallback whenever Supabase is not
  configured so a dev box still runs.
- SupabaseBackend: Supabase Postgres as the authoritative shared system of record,
  with a local SQLite cache plus a write outbox for offline resilience. It lands in
  a later phase; make_backend already routes to it and falls back to SqliteBackend
  when it is unavailable or its credentials are absent.

storage_mode in config.json selects the backend ("sqlite" default, "supabase").
The connection object a backend returns from open() must satisfy the
sqlite3.Connection contract the app and the db.* helpers rely on: execute(sql,
params), executescript, commit, close, row_factory, and cursors that expose
fetchone / fetchall / lastrowid with name-indexable rows.
"""

import os

from . import config, db


class StorageError(Exception):
    """A backend could not be opened. The message is user-facing (shown verbatim in
    the startup error dialog), so it carries no em-dashes and names the fix."""


class StorageBackend:
    """Common surface the app uses. Subclasses own connection creation, schema
    init, and (for networked backends) the offline sync. open() returns the object
    used as ctx.conn. The base methods are the inert defaults a local backend
    needs; a networked backend overrides status / sync_now / the background sync."""

    mode = "base"

    def open(self):
        raise NotImplementedError

    def status(self) -> dict:
        return {"mode": self.mode, "online": True, "pending": 0,
                "last_sync": None, "last_error": None}

    def sync_now(self) -> dict:
        return {"flushed": 0, "pending": 0}

    def start_background_sync(self) -> None:
        pass

    def stop_background_sync(self) -> None:
        pass

    def close(self) -> None:
        pass


class SqliteBackend(StorageBackend):
    """The shipped single-file behavior. open() does exactly what app.run() did
    before (ensure the database folder exists, db.connect, db.init_db) and returns
    the same sqlite3.Connection, so every screen, db.* helper, and test behaves
    identically. This is also the offline fallback for an unconfigured Supabase."""

    mode = "sqlite"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.db_path = cfg["db_path"]
        self.conn = None

    def open(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.isdir(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError:
                raise StorageError(
                    f"Cannot reach database folder:\n{db_dir}\n\n"
                    "Check the network drive, then restart. See DEPLOY_JOSEPH.md.")
        try:
            self.conn = db.connect(self.db_path)
            db.init_db(self.conn)
        except Exception as e:
            raise StorageError(f"Database error:\n{e}")
        return self.conn

    def status(self) -> dict:
        return {"mode": "sqlite", "online": True, "pending": 0,
                "last_sync": None, "last_error": None}

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass


def _make_supabase_backend(cfg: dict):
    """Build a SupabaseBackend when it is available and configured, else return None
    so the caller falls back to SqliteBackend. Returns None when the connection keys
    are absent or the psycopg2 driver is not installed, which is the documented
    'fall back to sqlite so a dev box still runs' behavior. A server that is merely
    unreachable does NOT fall back: the backend opens in offline mode and the floor
    keeps working from the local cache and outbox."""
    params = config.supabase_connection_params(cfg)
    if not params:
        return None
    try:
        import psycopg2  # noqa: F401  - the direct Postgres backend needs the driver
    except Exception:
        return None
    try:
        from .supabase_backend import SupabaseBackend
        return SupabaseBackend(cfg, params)
    except Exception:
        return None


def make_backend(cfg: dict) -> StorageBackend:
    """Select the storage backend from config. 'supabase' uses Supabase Postgres as
    the system of record when it is available and its credentials are present;
    anything else, or a missing or unavailable Supabase, falls back to the shipped
    SqliteBackend."""
    mode = (cfg.get("storage_mode") or "sqlite").strip().lower()
    if mode == "supabase":
        backend = _make_supabase_backend(cfg)
        if backend is not None:
            return backend
    return SqliteBackend(cfg)
