"""SJI joist traveler variant: shape, field kinds, gate path, NCR-field targeting.
The structural sequence stays unchanged (asserted alongside)."""

from shopqc import db, reports
from support import make_project, seed_piece, drive_gate2


def test_joist_traveler_shape(conn):
    p = make_project(conn, tonnage=212)
    pk, pidv, t = seed_piece(conn, p, "30KCS4")
    assert t == "JOIST"
    assert pidv == "ICD-30KCS4-001"
    assert len(db.traveler_rows(conn, pk)) == 20
    m = db.spec_meta("JOIST")
    assert (m["floor_first"], m["floor_last"], m["gate3_last"]) == (5, 16, 16)
    assert (m["release_director"], m["release_cwi"], m["ship"], m["ncr_auto"]) == (
        17, 18, 19, 20)


def test_field_kinds_joist_vs_structural():
    assert db.field_kind(8, "JOIST") == "cwi"
    assert db.field_kind(11, "JOIST") == "seat"
    assert db.field_kind(12, "JOIST") == "bridging"
    assert db.field_kind(14, "JOIST") == "camber"
    assert db.field_kind(16, "JOIST") == "dft"
    # structural field kinds are untouched
    assert db.field_kind(12, "STRUCTURAL") == "op"
    assert db.field_kind(14, "STRUCTURAL") == "op"
    assert len(db.traveler_spec("STRUCTURAL")) == 18


def test_joist_drives_through_all_floor_steps(conn):
    p = make_project(conn, tonnage=212)
    pk, _, t = seed_piece(conn, p, "30KCS4")
    drive_gate2(conn, pk, t)  # signs 5..16 including seat, bridging, camber, dft
    assert db.traveler_complete_through(conn, pk, db.gate3_last_field(t)) == []


def test_ncr_substitution_targets_variant_field():
    jnf = db.spec_meta("JOIST")["ncr_auto"]
    snf = db.spec_meta("STRUCTURAL")["ncr_auto"]
    assert (jnf, snf) == (20, 18)
    # joist field 18 is the CWI Final-Release row; the NCR list must NOT land there
    assert reports._traveler_cell_value(
        {"field_number": 18, "value": "2026-06-18"}, jnf, [7]) == "2026-06-18"
    assert reports._traveler_cell_value(
        {"field_number": 20, "value": "NCR-7"}, jnf, [7]) == "7"
    # structural field 18 is the NCR row, so it is the correct target there
    assert reports._traveler_cell_value(
        {"field_number": 18, "value": "x"}, snf, [1]) == "1"
