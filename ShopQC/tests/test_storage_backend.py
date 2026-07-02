"""Parity tests for the storage backend abstraction (Phase A1).

The SqliteBackend must behave exactly like the shipped single-file path: same eight
tables, same network-safe pragmas, same hard-block gate results. make_backend must
fall back to SqliteBackend when Supabase is not configured, so a dev box still runs.
These run headless, no Tkinter, like the rest of the suite."""

from shopqc import storage, db
from support import make_project, seed_piece, drive_gate2, open_ncr, close_ncr

EXPECTED_TABLES = {"projects", "bol_items", "pieces", "traveler_fields",
                   "ncrs", "rir_records", "weld_records", "release_records"}


def _cfg(tmp_path, mode="sqlite"):
    return {"db_path": str(tmp_path / "qc.db"), "storage_mode": mode}


def test_make_backend_default_is_sqlite(tmp_path):
    b = storage.make_backend(_cfg(tmp_path))
    assert isinstance(b, storage.SqliteBackend)
    assert b.status()["mode"] == "sqlite"


def test_make_backend_supabase_without_creds_falls_back_to_sqlite(tmp_path):
    # storage_mode=supabase but no connection keys present: must run on SQLite.
    b = storage.make_backend(_cfg(tmp_path, mode="supabase"))
    assert isinstance(b, storage.SqliteBackend)


def test_sqlite_backend_open_initializes_schema_and_pragmas(tmp_path):
    b = storage.make_backend(_cfg(tmp_path))
    conn = b.open()
    try:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert EXPECTED_TABLES.issubset(tables)
        # network-share-safe pragmas, exactly as the shipped db.connect sets them
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        # row_factory gives name-indexable rows, like sqlite3.Row
        p = make_project(conn)
        assert p["code"] == "ICD"
    finally:
        b.close()


def test_sqlite_backend_parity_drives_piece_through_gates(tmp_path):
    # Identical behavior to test_gates::ncr_hold_blocks_release, but through a piece
    # received and gated on a connection the backend opened.
    b = storage.make_backend(_cfg(tmp_path))
    conn = b.open()
    try:
        p = make_project(conn)
        pk, _pid, t = seed_piece(conn, p, "W14X90")
        drive_gate2(conn, pk, t)
        assert db.release_blockers(conn, pk, t) == []          # releasable
        n = open_ncr(conn, p, pk)
        assert any("NCR" in r for r in db.release_blockers(conn, pk, t))
        close_ncr(conn, n["id"])
        assert db.release_blockers(conn, pk, t) == []          # clean after close
    finally:
        b.close()


def test_sqlite_backend_creates_missing_db_dir(tmp_path):
    nested = tmp_path / "sub" / "dir"
    b = storage.SqliteBackend({"db_path": str(nested / "qc.db")})
    conn = b.open()
    try:
        assert nested.is_dir()
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        b.close()


def test_sqlite_backend_close_is_idempotent(tmp_path):
    b = storage.make_backend(_cfg(tmp_path))
    b.open()
    b.close()
    b.close()  # a second close must not raise
