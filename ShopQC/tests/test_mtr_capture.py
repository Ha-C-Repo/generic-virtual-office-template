"""Gate 1 MTR structured capture, and the lot-signs-field-4 fix that lets a
real received piece clear Gate 3 (info fields sit outside the floor range)."""

from shopqc import db
from support import make_project, seed_piece


def _field4(conn, pk):
    return conn.execute("SELECT signed_by FROM traveler_fields WHERE piece_pk=? "
                        "AND field_number=4", (pk,)).fetchone()["signed_by"]


def test_lot_signs_field4(conn):
    p = make_project(conn)
    pk, _, _ = seed_piece(conn, p, "W14X90", lot="SJI-LOT-7")
    assert _field4(conn, pk)  # MTR lot present -> field 4 auto-signed at receiving


def test_empty_lot_leaves_field4_unsigned(conn):
    p = make_project(conn)
    pk, _, _ = seed_piece(conn, p, "W14X90", lot="")
    assert not _field4(conn, pk)  # documents why receiving must capture the lot


def test_bol_items_store_structured_mtr(conn):
    p = make_project(conn)
    db.execute_write(conn,
        "INSERT INTO bol_items (project_id, line_number, section, "
        "quantity_ordered, quantity_received, heat_number, lot_number, "
        "astm_grade, fy, fu, ce, received_date) "
        "VALUES (?,1,'W14X90',10,10,'HT55','L1','A992',50,65,0.41,?)",
        (p["id"], db.today()))
    r = conn.execute("SELECT * FROM bol_items").fetchone()
    assert r["astm_grade"] == "A992"
    assert r["fy"] == 50 and r["fu"] == 65 and r["ce"] == 0.41
