"""Piece ID sequencing, section validation, joist detection, QR payload."""

from shopqc import db, piece_ids as pid
from support import make_project


def test_sequencing_per_project_section(conn):
    p = make_project(conn)
    a = pid.next_piece_id(conn, p["code"], "W14x90")
    assert a == "ICD-W14X90-001"
    db.execute_write(conn, "INSERT INTO pieces (project_id, piece_id, section, "
                     "created_date) VALUES (?,?,?,?)", (p["id"], a, "W14X90", db.now()))
    assert pid.next_piece_id(conn, p["code"], "W14x90") == "ICD-W14X90-002"
    # a different section keeps its own sequence
    assert pid.next_piece_id(conn, p["code"], "HSS6X6X1/4").endswith("-001")


def test_normalize_and_token():
    assert pid.normalize_section("w14 x 90") == "W14X90"
    assert pid.id_section_token("HSS6X6X1/4") == "HSS6X6X1/4"


def test_section_format_ok():
    for s in ("W14X90", "HSS6X6X1/4", "C12X20.7", "L4X4X1/4", "PIPE4",
              "30KCS4", "60G8", "24LH06"):
        assert pid.section_format_ok(s), s
    # junk, and bare series / common tokens that are not complete marks
    for s in ("BANANA", "123", "XY", "", "30K", "50K", "60G"):
        assert not pid.section_format_ok(s), s


def test_joist_detection_truth_table():
    # complete joist and joist-girder marks (series + chord/size digit)
    for s in ("30KCS4", "30K7", "22K9", "24LH06", "52DLH15", "60G8",
              "48G8N10K", "40G8N5.5K"):
        assert pid.is_joist_section(s), s
        assert pid.traveler_type_for_section(s) == "JOIST", s
    # structural shapes, bare series names, and common BOL tokens are NOT joists
    for s in ("W14X90", "HSS6X6X1/4", "2L4X4X1/4", "C12X20.7", "S30X108", "PIPE4",
              "30K", "20K", "60G", "72G", "50K", "5G", "250K", "600G", "100K"):
        assert not pid.is_joist_section(s), s


def test_qr_payload_format_and_sanitize():
    pl = pid.qr_payload("ICD-W14X90-001", "24-101", "HT55", "2026-06-18")
    assert pl == "ICD-W14X90-001|24-101|HT55|2026-06-18"
    # embedded pipes are sanitized so the 4-field payload stays parseable
    pl2 = pid.qr_payload("A|B", "J", "H", "D")
    assert pl2.count("|") == 3
