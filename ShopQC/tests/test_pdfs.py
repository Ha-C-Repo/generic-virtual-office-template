"""Every PDF the app produces builds for structural and joist pieces, carries the
approved logo, and contains no em-dashes."""

import os

from reportlab.lib.units import inch

from shopqc import db, reports
from support import make_project, seed_piece, drive_gate2


def _release(conn, pk):
    db.execute_write(conn,
        "INSERT INTO release_records (piece_pk, shop_director_sign, cwi_sign, "
        "ceo_sign, release_date) VALUES (?,?,?,?,?)",
        (pk, "Shop Director", "J. Inspector", db.CEO_NAME, db.now()))
    db.execute_write(conn, "UPDATE pieces SET status='RELEASED' WHERE id=?", (pk,))


def test_all_generators_build(conn, tmp_path):
    p = make_project(conn, tonnage=60)
    out = lambda n: str(tmp_path / n)
    built = []
    for sec in ("W14X90", "30KCS4"):   # structural and joist
        pk, _, t = seed_piece(conn, p, sec)
        drive_gate2(conn, pk, t)
        _release(conn, pk)
        piece = conn.execute("SELECT * FROM pieces WHERE id=?", (pk,)).fetchone()
        rel = conn.execute("SELECT * FROM release_records WHERE piece_pk=?",
                           (pk,)).fetchone()
        rows = db.traveler_rows(conn, pk)
        reports.traveler_pdf(out(f"{sec}_t.pdf"), p, piece, rows, [])
        reports.release_cert_pdf(out(f"{sec}_c.pdf"), p, piece, rel)
        built += [f"{sec}_t.pdf", f"{sec}_c.pdf"]
    db.execute_write(conn,
        "INSERT INTO bol_items (project_id, line_number, section, "
        "quantity_ordered, quantity_received, heat_number, lot_number, astm_grade, "
        "fy, fu, ce, received_date) VALUES (?,1,'W14X90',10,10,'HT55','L1','A992',"
        "50,65,0.41,?)", (p["id"], db.today()))
    db.execute_write(conn, "INSERT INTO rir_records (project_id, signed_by, "
        "signed_date, all_checks_json) VALUES (?,?,?,'{}')", (p["id"], "RI", db.now()))
    rir = conn.execute("SELECT * FROM rir_records").fetchone()
    bol = conn.execute("SELECT * FROM bol_items").fetchall()
    reports.rir_pdf(out("rir.pdf"), p, rir, bol)
    ncr_rows = conn.execute("SELECT n.*, pc.piece_id FROM ncrs n LEFT JOIN pieces "
                            "pc ON pc.id=n.piece_pk").fetchall()
    reports.ncr_pdf(out("ncr.pdf"), ncr_rows)
    pieces = conn.execute("SELECT pc.*, rr.release_date FROM pieces pc LEFT JOIN "
                          "release_records rr ON rr.piece_pk=pc.id WHERE "
                          "pc.status='RELEASED'").fetchall()
    reports.manifest_pdf(out("man.pdf"), p, "LOAD-1", pieces)
    reports.project_summary_pdf(out("sum.pdf"), p, {"RELEASED": 2}, 0)
    built += ["rir.pdf", "ncr.pdf", "man.pdf", "sum.pdf"]
    for f in built:
        assert os.path.getsize(out(f)) > 1000, f
    assert len(built) == 8  # 6 generators, two of them run for both variants


def test_logo_embeds_in_pdf(tmp_path):
    assert reports._logo(reports.LOGO_DARK, 0.5 * inch) is not None
    piece = {"piece_id": "X", "section": "W14X90", "heat_number": "H",
             "status": "RELEASED", "traveler_type": "STRUCTURAL"}
    rel = {"shop_director_sign": "SD", "cwi_sign": "CWI", "ceo_sign": None,
           "release_date": "2026-06-18"}
    out = str(tmp_path / "c.pdf")
    reports.release_cert_pdf(out, {"name": "P", "job_number": "1"}, piece, rel)
    assert b"/Image" in open(out, "rb").read()


def test_no_em_dashes_in_pdf_text(tmp_path):
    import fitz
    piece = {"piece_id": "X", "section": "30KCS4", "heat_number": "H",
             "status": "RELEASED", "traveler_type": "JOIST"}
    rel = {"shop_director_sign": "SD", "cwi_sign": "CWI", "ceo_sign": db.CEO_NAME,
           "release_date": "2026-06-18"}
    out = str(tmp_path / "c.pdf")
    reports.release_cert_pdf(out, {"name": "P", "job_number": "1"}, piece, rel)
    text = "".join(pg.get_text() for pg in fitz.open(out))
    assert chr(0x2014) not in text and chr(0x2013) not in text  # em / en dash
