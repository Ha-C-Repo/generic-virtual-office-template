"""SupabaseBackend: Supabase Postgres as the authoritative system of record, with
the local SQLite file kept purely as an offline cache and write outbox.

The app keeps talking to one connection object (ctx.conn). PgConnection satisfies
the sqlite3.Connection contract the app and the db.* helpers rely on, and routes:

- online: reads and writes go to Postgres, so hard-block predicates see live
  cross-station state. INSERT lastrowid comes from RETURNING id.
- offline (Postgres unreachable): reads serve from the cache, writes apply to the
  cache where triggers queue them in the outbox. The floor never stops.

A daemon thread (its own connections) flushes the outbox to Postgres on reconnect,
last-write-wins with an audit row per change (shopqc/sync.py), and pulls Postgres
into the cache so offline reads stay current. A single lock serializes the two
threads' access to the shared cache file.
"""

import threading

from . import db, sync, pg_client
from .storage import StorageBackend, StorageError

SYNC_INTERVAL_SEC = 5.0


class Row:
    """A Postgres dict row that also answers positional access and iteration, so app
    code written for sqlite3.Row (row['col'] and row[0]) works unchanged."""

    __slots__ = ("_d",)

    def __init__(self, d):
        object.__setattr__(self, "_d", d)

    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self._d.values())[k]
        return self._d[k]

    def keys(self):
        return list(self._d.keys())

    def get(self, k, default=None):
        return self._d.get(k, default)

    def __contains__(self, k):
        return k in self._d

    def __iter__(self):
        return iter(self._d.values())

    def __len__(self):
        return len(self._d)


class PgCursor:
    """Cursor-shaped result the adapter hands back. Wraps either Postgres rows
    (online) or a real sqlite cursor (offline), and exposes lastrowid."""

    def __init__(self, rows=None, lastrowid=None, sqlite_cursor=None):
        self._sqlite = sqlite_cursor
        self._rows = rows
        self._i = 0
        self.lastrowid = (sqlite_cursor.lastrowid
                          if sqlite_cursor is not None else lastrowid)

    def fetchone(self):
        if self._sqlite is not None:
            return self._sqlite.fetchone()
        if self._rows is None or self._i >= len(self._rows):
            return None
        r = self._rows[self._i]
        self._i += 1
        return r

    def fetchall(self):
        if self._sqlite is not None:
            return self._sqlite.fetchall()
        if self._rows is None:
            return []
        r = self._rows[self._i:]
        self._i = len(self._rows)
        return r

    def __iter__(self):
        if self._sqlite is not None:
            return iter(self._sqlite)
        return iter(self._rows or [])


def _verb(sql: str) -> str:
    s = sql.lstrip().lstrip("(").lstrip()
    head = s[:6].upper()
    if head.startswith("SELECT") or head[:4] == "WITH":
        return "read"
    if head.startswith("INSERT"):
        return "insert"
    return "write"  # UPDATE / DELETE, and anything else routed to Postgres as-is


def _is_or_ignore(sql: str) -> bool:
    return sql.lstrip()[:15].upper().startswith("INSERT OR IGNOR")


class PgConnection:
    """The object the app uses as ctx.conn. Thread-affine to the UI thread; the
    background sync uses its own connections."""

    def __init__(self, backend, cache, pg):
        self.backend = backend
        self.cache = cache
        self.pg = pg
        self.row_factory = None  # accepted and ignored; rows already support names

    def execute(self, sql, params=()):
        if self.backend.is_online():
            try:
                return self._online(sql, params)
            except pg_client.PgUnavailable:
                self.backend.mark_offline()
        return self._offline(sql, params)

    def _online(self, sql, params):
        verb = _verb(sql)
        if verb == "read":
            return PgCursor(rows=[Row(d) for d in self.pg.execute(sql, params)])
        if verb == "insert" and not _is_or_ignore(sql):
            res = self.pg.execute(sql.rstrip().rstrip(";") + " RETURNING id", params)
            return PgCursor(rows=[], lastrowid=(res[0]["id"] if res else None))
        self.pg.execute(sql, params)
        return PgCursor(rows=[], lastrowid=None)

    def _offline(self, sql, params):
        with self.backend.db_lock:
            cur = self.cache.execute(sql, params)
            if _verb(sql) != "read":
                # Commit the write and its outbox trigger together, inside the lock,
                # so the background sync never rebuilds the cache mid-write.
                self.cache.commit()
            return PgCursor(sqlite_cursor=cur)

    def executescript(self, script):
        with self.backend.db_lock:
            self.cache.executescript(script)
        return PgCursor(rows=[])

    def commit(self):
        # Offline writes commit atomically inside _offline under the lock; online
        # writes autocommit on Postgres. Nothing is pending here, so this is a no-op
        # kept for the sqlite3.Connection contract; it also keeps the online write
        # path from contending for db_lock on every commit.
        pass

    def close(self):
        pass  # the backend owns connection lifetimes


class SupabaseBackend(StorageBackend):
    """Build the cache and the Postgres client, hand back the adapter, and run the
    background sync. Constructed only when credentials are present; it opens even if
    the server is unreachable (offline mode), so a network blip never blocks startup
    or the floor."""

    mode = "supabase"

    def __init__(self, cfg: dict, params: dict):
        self.cfg = cfg
        self.params = params
        self.cache_path = cfg["db_path"]
        self.station = cfg.get("station_name", "?")
        self.cache = None
        self.pg = None
        self.adapter = None
        self.db_lock = threading.RLock()
        self._online = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._last_sync = None
        self._last_error = None

    def open(self):
        import os
        db_dir = os.path.dirname(self.cache_path)
        if db_dir and not os.path.isdir(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError:
                raise StorageError(
                    f"Cannot reach the local cache folder:\n{db_dir}\n\n"
                    "Check the path in config.json, then restart. See "
                    "DEPLOY_JOSEPH.md.")
        try:
            self.cache = db.connect(self.cache_path)
            self.cache.execute("PRAGMA recursive_triggers=OFF")
            db.init_db(self.cache)
            sync.ensure_cache_sync(self.cache)
        except Exception as e:
            raise StorageError(f"Local cache error:\n{e}")
        self.pg = pg_client.Psycopg2Client(self.params)
        if self.pg.is_alive():
            self._online.set()
        self.adapter = PgConnection(self, self.cache, self.pg)
        return self.adapter

    def is_online(self) -> bool:
        return self._online.is_set()

    def mark_offline(self):
        self._online.clear()

    def start_background_sync(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._sync_loop, daemon=True,
                                        name="shopqc-sync")
        self._thread.start()

    def stop_background_sync(self):
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=10)  # let an in-flight flush finish before we close

    def _sync_loop(self):
        # The sync thread owns its own connections; the lock guards the shared cache
        # file against the UI thread's offline reads and writes.
        cache = db.connect(self.cache_path)
        cache.execute("PRAGMA recursive_triggers=OFF")
        pg = pg_client.Psycopg2Client(self.params)
        try:
            while not self._stop.is_set():
                try:
                    if pg.is_alive():
                        self._online.set()
                        with self.db_lock:
                            pending = cache.execute(
                                "SELECT COUNT(*) FROM _outbox").fetchone()[0]
                            if pending:
                                sync.flush(cache, pg, self.station)
                            else:
                                sync.pull(pg, cache)
                        self._last_sync = db.now()
                        self._last_error = None
                    else:
                        self._online.clear()
                except pg_client.PgUnavailable:
                    self._online.clear()
                except Exception as e:
                    self._last_error = str(e)
                self._stop.wait(SYNC_INTERVAL_SEC)
        finally:
            cache.close()
            pg.close()

    def sync_now(self) -> dict:
        if not self.pg.is_alive():
            self._online.clear()
            return {"applied": 0, "superseded": 0, "deleted": 0, "pending": -1}
        self._online.set()
        with self.db_lock:
            res = sync.flush(self.cache, self.pg, self.station)
        self._last_sync = db.now()
        return res

    def status(self) -> dict:
        pending = 0
        try:
            with self.db_lock:
                pending = self.cache.execute(
                    "SELECT COUNT(*) FROM _outbox").fetchone()[0]
        except Exception:
            pass
        return {"mode": "supabase", "online": self._online.is_set(),
                "pending": pending, "last_sync": self._last_sync,
                "last_error": self._last_error}

    def close(self):
        self._stop.set()
        try:
            if self.pg is not None:
                self.pg.close()
        except Exception:
            pass
        try:
            if self.cache is not None:
                self.cache.close()
        except Exception:
            pass
