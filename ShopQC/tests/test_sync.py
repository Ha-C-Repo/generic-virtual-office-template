"""Offline sync tests (Phase A2). No live Supabase: a FakePostgres stands in. These
cover the resilience contract: writes queue in the outbox while the server is down,
flush on reconnect, last-write-wins by the change clock, an audit row per applied or
superseded change, child foreign keys remapped to server ids, and the cache rebuilt
to server ids after a flush."""

from shopqc import db, sync
from fakes import FakePostgres

_INS_PROJECT = ("INSERT INTO projects (code, job_number, name, created_date) "
                "VALUES (?,?,?,?)")


def _cache(tmp_path):
    c = db.connect(str(tmp_path / "cache.db"))
    c.execute("PRAGMA recursive_triggers=OFF")
    db.init_db(c)
    sync.ensure_cache_sync(c)
    return c


def test_offline_insert_queues_then_flushes(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD Church", db.now()))
    assert cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 1

    res = sync.flush(cache, fake)
    assert res["applied"] == 1
    got = fake.execute("SELECT name FROM projects WHERE code=?", ("ICD",))
    assert got and got[0]["name"] == "ICD Church"
    assert cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 0
    audit = fake.execute("SELECT outcome FROM audit_log WHERE table_name='projects'")
    assert audit and audit[0]["outcome"] == "applied"


def test_outbox_accumulates_while_down_then_flushes(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    fake.up = False  # network down: the floor keeps capturing into the cache/outbox
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    db.execute_write(cache, _INS_PROJECT, ("ELC", "24-2", "Elite", db.now()))
    assert cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 2

    fake.up = True  # reconnect
    res = sync.flush(cache, fake)
    assert res["applied"] == 2
    assert len(fake.execute("SELECT 1 FROM projects")) == 2
    assert cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 0


def test_flush_remaps_child_foreign_keys(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    pcur = db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    db.execute_write(cache,
        "INSERT INTO pieces (project_id, piece_id, section, status, traveler_type, "
        "created_date) VALUES (?,?,?,?,?,?)",
        (pcur.lastrowid, "ICD-W14X90-001", "W14X90", "RECEIVED", "STRUCTURAL",
         db.now()))
    sync.flush(cache, fake)

    fproj = fake.execute("SELECT id FROM projects WHERE code=?", ("ICD",))[0]["id"]
    fpiece = fake.execute(
        "SELECT project_id FROM pieces WHERE piece_id=?", ("ICD-W14X90-001",))[0]
    # the child points at the SERVER project id, not the local cache id
    assert fpiece["project_id"] == fproj


def test_last_write_wins_keeps_newer_server_row(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "CACHE", db.now()))
    # the server already holds the same project (by code) under its OWN sync_uid,
    # strictly newer. Natural-key LWW must merge, not collide on UNIQUE(code).
    fake.execute(
        "INSERT INTO projects (code, job_number, name, created_date, sync_uid, "
        "updated_at) VALUES (?,?,?,?,?,?)",
        ("ICD", "24-1", "SERVER", db.now(), "server-uid", "2099-01-01 00:00:00.000"))

    res = sync.flush(cache, fake)
    assert res["superseded"] == 1 and res["applied"] == 0
    rows = fake.execute("SELECT name FROM projects WHERE code=?", ("ICD",))
    assert len(rows) == 1 and rows[0]["name"] == "SERVER"   # one row, server kept
    assert fake.execute(
        "SELECT outcome FROM audit_log ORDER BY id DESC")[0]["outcome"] == "superseded"


def test_last_write_wins_applies_newer_local_change(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "CACHE", db.now()))
    fake.execute(
        "INSERT INTO projects (code, job_number, name, created_date, sync_uid, "
        "updated_at) VALUES (?,?,?,?,?,?)",
        ("ICD", "24-1", "SERVER", db.now(), "server-uid", "2000-01-01 00:00:00.000"))

    res = sync.flush(cache, fake)
    assert res["applied"] == 1 and res["superseded"] == 0
    rows = fake.execute("SELECT name FROM projects WHERE code=?", ("ICD",))
    assert len(rows) == 1 and rows[0]["name"] == "CACHE"   # merged: newer local won


def test_natural_key_merge_no_duplicate_piece_on_collision(tmp_path):
    # Two stations created the same piece_id offline; reconnect must merge by
    # piece_id (no duplicate row, no UNIQUE(piece_id) error), newer local winning.
    cache, fake = _cache(tmp_path), FakePostgres()
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    sync.flush(cache, fake)  # project ICD now on the server, cache rebuilt
    fproj = fake.execute("SELECT id FROM projects WHERE code=?", ("ICD",))[0]["id"]
    fake.execute(
        "INSERT INTO pieces (project_id, piece_id, section, status, traveler_type, "
        "created_date, sync_uid, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (fproj, "ICD-W14X90-001", "W14X90", "IN_FAB", "STRUCTURAL", db.now(),
         "srv-piece", "2000-01-01 00:00:00.000"))
    cproj = cache.execute(
        "SELECT id FROM projects WHERE code=?", ("ICD",)).fetchone()["id"]
    db.execute_write(cache,
        "INSERT INTO pieces (project_id, piece_id, section, status, traveler_type, "
        "created_date) VALUES (?,?,?,?,?,?)",
        (cproj, "ICD-W14X90-001", "W14X90", "RECEIVED", "STRUCTURAL", db.now()))

    res = sync.flush(cache, fake)
    pieces = fake.execute("SELECT status FROM pieces WHERE piece_id=?",
                          ("ICD-W14X90-001",))
    assert len(pieces) == 1                       # merged, no duplicate
    assert res["applied"] == 1 and pieces[0]["status"] == "RECEIVED"  # newer won


def test_pull_mirrors_server_into_cache_without_requeue(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    fake.execute(
        "INSERT INTO projects (code, job_number, name, created_date, sync_uid, "
        "updated_at) VALUES (?,?,?,?,?,?)",
        ("ICD", "24-1", "ICD", db.now(), "uid-1", "2026-01-01 00:00:00.000"))
    sync.pull(fake, cache)

    rows = cache.execute("SELECT code, sync_uid FROM projects").fetchall()
    assert len(rows) == 1 and rows[0]["code"] == "ICD" and rows[0]["sync_uid"] == "uid-1"
    # a pull applies server state; it must not re-queue that state as local changes
    assert cache.execute("SELECT COUNT(*) FROM _outbox").fetchone()[0] == 0


def test_flush_rebuilds_cache_to_server_ids(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    pcur = db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    db.execute_write(cache,
        "INSERT INTO pieces (project_id, piece_id, section, status, traveler_type, "
        "created_date) VALUES (?,?,?,?,?,?)",
        (pcur.lastrowid, "ICD-W14X90-001", "W14X90", "RECEIVED", "STRUCTURAL",
         db.now()))
    sync.flush(cache, fake)  # flush ends by rebuilding the cache from the server

    cproj = cache.execute(
        "SELECT id FROM projects WHERE code=?", ("ICD",)).fetchone()["id"]
    cpiece_fk = cache.execute(
        "SELECT project_id FROM pieces WHERE piece_id=?",
        ("ICD-W14X90-001",)).fetchone()["project_id"]
    fproj = fake.execute("SELECT id FROM projects WHERE code=?", ("ICD",))[0]["id"]
    assert cpiece_fk == cproj == fproj


def test_offline_delete_propagates(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    sync.flush(cache, fake)
    assert fake.execute("SELECT 1 FROM projects WHERE code=?", ("ICD",))
    db.execute_write(cache, "DELETE FROM projects WHERE code=?", ("ICD",))
    res = sync.flush(cache, fake)
    assert res["deleted"] == 1
    assert fake.execute("SELECT 1 FROM projects WHERE code=?", ("ICD",)) == []


def test_flush_empty_outbox_is_noop(tmp_path):
    cache, fake = _cache(tmp_path), FakePostgres()
    res = sync.flush(cache, fake)
    assert res == {"applied": 0, "superseded": 0, "deleted": 0, "unresolved": 0,
                   "pending": 0}


def test_fastener_lot_syncs_with_remapped_project(tmp_path):
    # Phase B: fastener_lots is in the sync map; an offline lot flushes with its
    # project foreign key remapped to the server id.
    cache, fake = _cache(tmp_path), FakePostgres()
    pcur = db.execute_write(cache, _INS_PROJECT, ("ICD", "24-1", "ICD", db.now()))
    db.execute_write(cache,
        "INSERT INTO fastener_lots (project_id, assembly_type, quantity, "
        "rocap_lot_no, markings_verified, mfr_cert_on_file, galvanized, "
        "lube_check_done, received_complete, received_date, created_date) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pcur.lastrowid, "A325", 200, "ROCAP-99", 1, 1, 0, 0, 1, db.today(),
         db.now()))
    sync.flush(cache, fake)

    fproj = fake.execute("SELECT id FROM projects WHERE code=?", ("ICD",))[0]["id"]
    lots = fake.execute(
        "SELECT project_id, assembly_type, rocap_lot_no FROM fastener_lots")
    assert len(lots) == 1 and lots[0]["project_id"] == fproj
    assert lots[0]["assembly_type"] == "A325" and lots[0]["rocap_lot_no"] == "ROCAP-99"
