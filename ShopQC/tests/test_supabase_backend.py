"""SupabaseBackend adapter tests (Phase A2). The adapter must satisfy the
sqlite3.Connection contract: online it reads and writes Postgres (so hard blocks see
authoritative state) and returns rows that answer both name and position; when the
server drops it fails over to the cache and queues the write; on reconnect the queue
flushes. A FakePostgres stands in, so no live connection is needed."""

from shopqc import db, sync
from shopqc.supabase_backend import SupabaseBackend, PgConnection
from fakes import FakePostgres
from support import make_project, seed_piece, drive_gate2, open_ncr, close_ncr

_INS_PROJECT = ("INSERT INTO projects (code, job_number, name, created_date) "
                "VALUES (?,?,?,?)")


def _wire(tmp_path, online=True):
    """A SupabaseBackend with a FakePostgres injected, no background thread."""
    cfg = {"db_path": str(tmp_path / "cache.db"), "station_name": "GATE1",
           "storage_mode": "supabase"}
    b = SupabaseBackend(cfg, {"dsn": "fake"})
    b.cache = db.connect(cfg["db_path"])
    b.cache.execute("PRAGMA recursive_triggers=OFF")
    db.init_db(b.cache)
    sync.ensure_cache_sync(b.cache)
    b.pg = FakePostgres()
    if online:
        b._online.set()
    else:
        b._online.clear()
        b.pg.up = False
    b.adapter = PgConnection(b, b.cache, b.pg)
    return b


def test_online_write_goes_to_postgres_not_cache(tmp_path):
    b = _wire(tmp_path)
    cur = b.adapter.execute(_INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    assert cur.lastrowid is not None                       # RETURNING id
    assert b.pg.execute("SELECT code FROM projects")[0]["code"] == "ICD"
    # online writes go to the authoritative store, not the cache (pull refreshes it)
    assert b.cache.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
    assert b.cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 0


def test_online_read_named_and_positional(tmp_path):
    b = _wire(tmp_path)
    b.adapter.execute(_INS_PROJECT, ("ICD", "24-1", "ICD Church", db.now()))
    row = b.adapter.execute(
        "SELECT code, name FROM projects WHERE code=?", ("ICD",)).fetchone()
    assert row["code"] == "ICD" and row["name"] == "ICD Church"
    assert row[0] == "ICD"          # positional access, like sqlite3.Row
    count = b.adapter.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    assert count == 1               # COUNT(*)[0] pattern the app relies on


def test_failover_to_cache_when_server_drops(tmp_path):
    b = _wire(tmp_path)
    b.pg.up = False                 # network drops mid-session
    b.adapter.execute(_INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    b.adapter.commit()
    assert not b.is_online()        # the adapter noticed and went offline
    assert b.cache.execute(
        "SELECT code FROM projects WHERE code=?", ("ICD",)).fetchone()["code"] == "ICD"
    assert b.cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 1


def test_offline_reads_serve_from_cache(tmp_path):
    b = _wire(tmp_path, online=False)
    db.execute_write(b.cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    row = b.adapter.execute(
        "SELECT code FROM projects WHERE code=?", ("ICD",)).fetchone()
    assert row["code"] == "ICD"


def test_reconnect_flushes_queue(tmp_path):
    b = _wire(tmp_path)
    b.pg.up = False
    b.adapter.execute(_INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    b.adapter.commit()
    assert b.cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 1

    b.pg.up = True
    res = b.sync_now()
    assert res["applied"] == 1
    assert b.pg.execute("SELECT code FROM projects")[0]["code"] == "ICD"
    assert b.cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 0


def test_status_reports_online_and_pending(tmp_path):
    b = _wire(tmp_path)
    st = b.status()
    assert st["mode"] == "supabase" and st["online"] is True and st["pending"] == 0
    b.pg.up = False
    b.adapter.execute(_INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    b.adapter.commit()
    st = b.status()
    assert st["online"] is False and st["pending"] == 1


def test_hard_blocks_hold_through_adapter_online(tmp_path):
    # The whole point of online-authoritative reads: the hard-block predicates run
    # against Postgres through the adapter and behave exactly as on SQLite.
    b = _wire(tmp_path)
    conn = b.adapter
    p = make_project(conn)
    pk, _pid, t = seed_piece(conn, p, "W14X90")
    drive_gate2(conn, pk, t)
    assert db.release_blockers(conn, pk, t) == []           # releasable
    n = open_ncr(conn, p, pk)
    assert any("NCR" in r for r in db.release_blockers(conn, pk, t))   # frozen
    close_ncr(conn, n["id"])
    assert db.release_blockers(conn, pk, t) == []           # clean after close


def test_preweld_cwi_block_through_adapter_online(tmp_path):
    # Hard block 1 and 2 at the data layer, evaluated through the online adapter.
    b = _wire(tmp_path)
    conn = b.adapter
    p = make_project(conn)
    pk, _pid, t = seed_piece(conn, p, "W14X90")
    rows = db.traveler_rows(conn, pk)
    assert db.lowest_unsigned_floor(rows, t) == 5           # info 1-4 auto-signed
    from support import sign
    sign(conn, pk, 5); sign(conn, pk, 6); sign(conn, pk, 7)
    rows = db.traveler_rows(conn, pk)
    assert db.field_kind(8, t) == "cwi"
    assert db.lowest_unsigned_floor(rows, t) == 8           # pre-weld CWI is next
