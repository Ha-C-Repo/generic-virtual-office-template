"""Shared helpers for the Shop QC pytest suite. Drive pieces through the gates at
the data layer, exactly as the UI does, without Tkinter."""

import os

from shopqc import db, piece_ids

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PDF = os.path.join(_ROOT, "data", "test_fixtures",
                           "PRJ-2026-HILLCREST-STR-001.pdf")
FIXTURE_TXT = os.path.join(_ROOT, "data", "test_fixtures",
                           "PRJ-2026-HILLCREST-STR-001.txt")


def make_project(conn, code="ICD", job="24-101", name="ICD Church",
                 tonnage=0, ias=0, gc="GC Co"):
    db.execute_write(conn,
        "INSERT INTO projects (code, job_number, name, gc_name, tonnage, "
        "ias_required, created_date) VALUES (?,?,?,?,?,?,?)",
        (code, job, name, gc, tonnage, ias, db.now()))
    return conn.execute("SELECT * FROM projects WHERE code=?", (code,)).fetchone()


def seed_piece(conn, project, section, heat="HT55", lot="L1"):
    """Receive one piece (as receive() does): pick variant from the mark, create
    the piece, seed its traveler. Returns (piece_pk, piece_id, traveler_type)."""
    ttype = piece_ids.traveler_type_for_section(section)
    pid = piece_ids.next_piece_id(conn, project["code"], section)
    cur = db.execute_write(conn,
        "INSERT INTO pieces (project_id, piece_id, section, heat_number, "
        "traveler_type, created_date) VALUES (?,?,?,?,?,?)",
        (project["id"], pid, section, heat, ttype, db.now()))
    pk = cur.lastrowid
    db.seed_traveler(conn, pk, f"{project['name']} / {project['job_number']}",
                     pid, section, heat, lot, ttype)
    return pk, pid, ttype


def sign(conn, pk, num, by="Inspector", val="OK"):
    db.execute_write(conn,
        "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
        "WHERE piece_pk=? AND field_number=?", (val, by, db.now(), pk, num))


def drive_gate2(conn, pk, ttype, cwi="CWI: J. Inspector"):
    """Sign every floor field in order, recording a CWI name at the CWI steps so
    the pre-weld hard block is satisfied legitimately."""
    meta = db.spec_meta(ttype)
    for n in range(meta["floor_first"], meta["floor_last"] + 1):
        by = cwi if db.field_kind(n, ttype) == "cwi" else "Inspector"
        sign(conn, pk, n, by)


def open_ncr(conn, project, pk, category="Welding", desc="test", by="PG", gate=2):
    db.execute_write(conn,
        "INSERT INTO ncrs (project_id, piece_pk, gate, category, description, "
        "opened_by, opened_date) VALUES (?,?,?,?,?,?,?)",
        (project["id"], pk, gate, category, desc, by, db.now()))
    db.execute_write(conn, "UPDATE pieces SET status='NCR_HOLD' WHERE id=?", (pk,))
    return conn.execute("SELECT * FROM ncrs WHERE piece_pk=? ORDER BY id DESC "
                        "LIMIT 1", (pk,)).fetchone()


def close_ncr(conn, ncr_id, eor=None):
    db.execute_write(conn,
        "UPDATE ncrs SET disposition='REWORK', disposition_authority='SD', "
        "eor_reference=?, status='CLOSED', closed_by='SD', closed_date=? "
        "WHERE id=?", (eor, db.now(), ncr_id))
