"""FakePostgres: an in-memory stand-in for the Supabase Postgres used by the sync
and adapter tests. It is backed by SQLite so it runs the exact ON CONFLICT and
RETURNING statements the real path emits, and reuses the canonical db.SCHEMA so it
cannot drift from the app's tables. Flip .up to simulate the network dropping and
returning; while down, execute raises PgUnavailable exactly like the real client.

No live Supabase is needed to build or pass the ship gate."""

import sqlite3

from shopqc import db, sync
from shopqc.pg_client import PgUnavailable

_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,
  sync_uid TEXT NOT NULL,
  op TEXT NOT NULL,
  payload TEXT,
  source TEXT,
  station TEXT,
  applied_at TEXT NOT NULL,
  outcome TEXT NOT NULL
);
"""


class FakePostgres:
    def __init__(self):
        self.up = True
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        # Canonical eight tables, then the two sync columns and a server-side
        # sync_uid default (a trigger, since SQLite cannot ALTER in an expression
        # default) so an online INSERT that omits sync_uid still gets one, like
        # Postgres gen_random_uuid().
        db.init_db(self.conn)
        for t in sync.SYNC_TABLES:
            self.conn.execute(f"ALTER TABLE {t} ADD COLUMN sync_uid TEXT")
            self.conn.execute(f"ALTER TABLE {t} ADD COLUMN updated_at TEXT")
            # Full UNIQUE on sync_uid, mirroring the Postgres schema, so the sync's
            # ON CONFLICT (sync_uid) upsert matches it (SQLite multiple NULLs are
            # fine; the insert trigger fills the value right after).
            self.conn.execute(f"CREATE UNIQUE INDEX ux_{t}_uid ON {t}(sync_uid)")
            self.conn.execute(
                f"CREATE TRIGGER fake_uid_{t} AFTER INSERT ON {t} "
                f"WHEN NEW.sync_uid IS NULL BEGIN "
                f"UPDATE {t} SET sync_uid = lower(hex(randomblob(16))), "
                f"updated_at = strftime('%Y-%m-%d %H:%M:%f','now') "
                f"WHERE id = NEW.id; END;")
        self.conn.executescript(_AUDIT_DDL)
        self.conn.commit()

    def execute(self, sql, params=()):
        if not self.up:
            raise PgUnavailable("fake postgres is down")
        cur = self.conn.execute(sql, tuple(params))
        rows = [dict(r) for r in cur.fetchall()] if cur.description else []
        self.conn.commit()
        return rows

    def begin_sync(self):
        pass

    def end_sync(self):
        pass

    def is_alive(self) -> bool:
        return self.up

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
