"""Additive, idempotent schema migration; no destructive ALTERs on the share."""

from shopqc import db


def test_fresh_db_has_new_columns(conn):
    pcols = {r["name"] for r in conn.execute("PRAGMA table_info(pieces)")}
    assert "traveler_type" in pcols
    bcols = {r["name"] for r in conn.execute("PRAGMA table_info(bol_items)")}
    assert {"astm_grade", "fy", "fu", "ce"} <= bcols


def test_legacy_db_migrates_additively(tmp_path):
    c = db.connect(str(tmp_path / "legacy.db"))
    # old shape: pieces without traveler_type, bol_items without the MTR columns
    c.execute("CREATE TABLE pieces (id INTEGER PRIMARY KEY, piece_id TEXT)")
    c.execute("CREATE TABLE bol_items (id INTEGER PRIMARY KEY, section TEXT)")
    c.execute("INSERT INTO pieces (piece_id) VALUES ('P1')")
    c.execute("INSERT INTO bol_items (section) VALUES ('W14X90')")
    c.commit()
    db.migrate(c)
    db.migrate(c)  # idempotent: a second run must not raise
    pcols = {r["name"] for r in c.execute("PRAGMA table_info(pieces)")}
    bcols = {r["name"] for r in c.execute("PRAGMA table_info(bol_items)")}
    assert "traveler_type" in pcols
    assert {"astm_grade", "fy", "fu", "ce"} <= bcols
    # existing rows preserved; new column defaulted, nothing dropped
    assert c.execute("SELECT traveler_type FROM pieces").fetchone()[0] == "STRUCTURAL"
    assert c.execute("SELECT section FROM bol_items").fetchone()[0] == "W14X90"
    c.close()


def test_migrate_on_db_missing_tables_is_safe(tmp_path):
    c = db.connect(str(tmp_path / "empty.db"))
    db.migrate(c)  # no tables at all: must not raise
    c.close()


def test_spec_meta_fallback():
    assert db.spec_meta(None)["floor_last"] == 14         # legacy/NULL -> structural
    assert db.spec_meta("WEIRD")["floor_last"] == 14      # unknown -> structural
    assert db.spec_meta("JOIST")["floor_last"] == 16
