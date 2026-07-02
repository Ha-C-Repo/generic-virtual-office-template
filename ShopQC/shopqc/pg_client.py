"""Postgres client seam.

The whole app and the sync speak the app's native SQLite dialect (qmark
placeholders, INSERT OR IGNORE) to a PostgresClient. Only this module knows how to
turn that into Postgres: it swaps ? for %s, rewrites INSERT OR IGNORE to ON CONFLICT
DO NOTHING, and pins the connection to the shopqc schema. Keeping the one
translation here means the adapter, the sync, and the tests stay dialect-neutral,
and a fake client backed by SQLite can run the exact same statements.

A connection problem raises PgUnavailable so the caller can fail over to the local
cache; a real SQL error propagates as itself. psycopg2 is imported lazily so a dev
box without it still imports the app and runs on SQLite.
"""

import re


class PgUnavailable(Exception):
    """The Postgres server could not be reached. The adapter treats this as "go
    offline and use the cache", never as a data error."""


_INSERT_OR_IGNORE = re.compile(r"(?is)^(\s*)INSERT\s+OR\s+IGNORE\s+INTO\b")


def translate_sql(sql: str) -> str:
    """Translate one app SQLite statement to Postgres. Bounded on purpose: the app
    only ever issues qmark placeholders and a single INSERT OR IGNORE (the traveler
    seed). A literal percent is escaped first so it survives psycopg2 formatting,
    then qmark placeholders become %s."""
    ignore = bool(_INSERT_OR_IGNORE.match(sql))
    s = _INSERT_OR_IGNORE.sub(r"\1INSERT INTO", sql) if ignore else sql
    s = s.replace("%", "%%").replace("?", "%s")
    if ignore:
        s = s.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return s


class PostgresClient:
    """Interface the adapter and the sync use. execute runs one statement in the
    app's SQLite dialect and returns a list of dict rows (empty for non-selects).
    begin_sync / end_sync bracket the outbox flush so the server keeps the supplied
    updated_at instead of stamping a fresh one."""

    def execute(self, sql, params=()):
        raise NotImplementedError

    def begin_sync(self):
        pass

    def end_sync(self):
        pass

    def is_alive(self) -> bool:
        return False

    def close(self):
        pass


class Psycopg2Client(PostgresClient):
    """Direct Postgres via psycopg2. One connection pinned to the shopqc schema,
    dict rows, autocommit per statement to match the app's commit-per-write habit.
    Resilient: it constructs even when the server is down (so the app opens offline)
    and reconnects on demand. Never logs the connection params."""

    def __init__(self, params: dict):
        import psycopg2
        import psycopg2.extras
        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras
        self._params = params
        self.conn = None
        try:
            self.connect()
        except Exception:
            self.conn = None  # start offline; the sync loop will reconnect

    def connect(self):
        if "dsn" in self._params:
            self.conn = self._psycopg2.connect(self._params["dsn"])
        else:
            self.conn = self._psycopg2.connect(**self._params)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute("SET search_path TO shopqc")

    def _ensure(self):
        if self.conn is None or getattr(self.conn, "closed", 1):
            self.connect()

    def execute(self, sql, params=()):
        try:
            self._ensure()
            cur = self.conn.cursor(cursor_factory=self._extras.RealDictCursor)
            try:
                cur.execute(translate_sql(sql), tuple(params))
                rows = [dict(r) for r in cur.fetchall()] if cur.description else []
            finally:
                cur.close()
            return rows
        except (self._psycopg2.OperationalError,
                self._psycopg2.InterfaceError) as e:
            self.conn = None
            raise PgUnavailable(str(e))

    def begin_sync(self):
        self._ensure()
        with self.conn.cursor() as cur:
            cur.execute("SET shopqc.sync_apply = 'on'")

    def end_sync(self):
        try:
            with self.conn.cursor() as cur:
                cur.execute("RESET shopqc.sync_apply")
        except Exception:
            pass

    def is_alive(self) -> bool:
        try:
            self._ensure()
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True
        except Exception:
            self.conn = None
            return False

    def close(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass
