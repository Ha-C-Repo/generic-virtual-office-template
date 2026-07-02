"""Hard block 6: an unauthorized-field-modification NCR cannot close without an
EOR sealed reference. This is the path the joist camber/deflection failure flows
into (the Elite Crossing case)."""

from shopqc import db
from support import make_project, seed_piece, open_ncr, close_ncr


def test_eor_block_rule():
    assert db.ncr_close_blocked_reason(db.EOR_CATEGORY, "")
    assert db.ncr_close_blocked_reason(db.EOR_CATEGORY, "   ")
    assert db.ncr_close_blocked_reason(db.EOR_CATEGORY, None)
    assert not db.ncr_close_blocked_reason(db.EOR_CATEGORY, "EOR-2428-SK-07")
    for cat in ("Welding", "Dimensional", "Material nonconformance", "Documentation"):
        assert not db.ncr_close_blocked_reason(cat, "")


def test_field_mod_ncr_needs_eor_end_to_end(conn):
    p = make_project(conn)
    pk, _, _ = seed_piece(conn, p, "30KCS4")
    n = open_ncr(conn, p, pk, category=db.EOR_CATEGORY,
                 desc="camber short under field modification per AISC")
    # close attempt without an EOR reference is blocked
    assert db.ncr_close_blocked_reason(n["category"], n["eor_reference"])
    # close with an EOR reference proceeds and clears the hold
    assert not db.ncr_close_blocked_reason(n["category"], "EOR-2428-SK-07")
    close_ncr(conn, n["id"], eor="EOR-2428-SK-07")
    assert db.open_ncr_count(conn, pk) == 0
    row = conn.execute("SELECT status, eor_reference FROM ncrs WHERE id=?",
                       (n["id"],)).fetchone()
    assert row["status"] == "CLOSED" and row["eor_reference"] == "EOR-2428-SK-07"
