"""Hard blocks 1-5 at the shared decision logic the UI runs: locked sequence
(lowest_unsigned_floor), pre-weld CWI (cwi_signature_ok), NCR hold + Gate 3
re-verify (release_blockers), CEO co-sign trigger and exact name."""

from shopqc import db
from support import (make_project, seed_piece, sign, drive_gate2,
                     open_ncr, close_ncr)


def test_locked_sequence_lowest_unsigned_is_preweld_cwi(conn):
    p = make_project(conn)
    pk, _, t = seed_piece(conn, p, "W14X90")
    rows = db.traveler_rows(conn, pk)
    # the first signable floor step is 5 (info 1-4 auto-signed at receiving)
    assert db.lowest_unsigned_floor(rows, t) == 5
    sign(conn, pk, 5); sign(conn, pk, 6); sign(conn, pk, 7)
    rows = db.traveler_rows(conn, pk)
    # next signable is the pre-weld CWI at field 8 (hard block 1 sits in sequence)
    assert db.field_kind(8, t) == "cwi"
    assert db.lowest_unsigned_floor(rows, t) == 8
    # and the data-layer completeness view agrees
    assert db.traveler_complete_through(conn, pk, 14)[0] == 8


def test_cwi_signature_required(conn):
    # hard block 1: the CWI handler advances only with a non-empty CWI name
    assert not db.cwi_signature_ok("")
    assert not db.cwi_signature_ok("   ")
    assert not db.cwi_signature_ok(None)
    assert db.cwi_signature_ok("J. Inspector")


def test_ncr_hold_blocks_release_even_when_floor_complete(conn):
    p = make_project(conn)
    pk, _, t = seed_piece(conn, p, "W14X90")
    drive_gate2(conn, pk, t)
    assert db.release_blockers(conn, pk, t) == []      # ready
    open_ncr(conn, p, pk)
    blk = db.release_blockers(conn, pk, t)
    assert blk and any("NCR" in r for r in blk)        # frozen by the open NCR
    n = conn.execute("SELECT id FROM ncrs WHERE piece_pk=?", (pk,)).fetchone()
    close_ncr(conn, n["id"])
    assert db.release_blockers(conn, pk, t) == []      # released after close


def test_gate3_reverify_reports_unsigned_and_open_ncr(conn):
    p = make_project(conn)
    pk, _, t = seed_piece(conn, p, "30KCS4")          # joist: completeness 1..16
    # incomplete floor -> blocked with an unsigned-fields reason
    blk = db.release_blockers(conn, pk, t)
    assert any("unsigned" in r for r in blk)
    drive_gate2(conn, pk, t)
    assert db.release_blockers(conn, pk, t) == []
    # a late NCR from another station re-blocks at sign time
    open_ncr(conn, p, pk)
    assert any("NCR" in r for r in db.release_blockers(conn, pk, t))


def test_release_reverify_runs_after_signoff_dialog(conn):
    # HB4 TOCTOU fix: release() re-verifies a SECOND time after the modal sign-off
    # dialog (at commit), so an NCR opened by another station while the dialog was
    # open still blocks. This models the sequence around that second db.release_blockers
    # call in ReleaseScreen.release; without the post-dialog re-check the piece would
    # release with an open NCR.
    p = make_project(conn)
    pk, _, t = seed_piece(conn, p, "W14X90")
    drive_gate2(conn, pk, t)
    assert db.release_blockers(conn, pk, t) == []     # pre-dialog check: clean
    open_ncr(conn, p, pk)                              # NCR opened during sign-off
    assert db.release_blockers(conn, pk, t)           # post-dialog check: blocked


def test_shipping_blocked_by_open_ncr(conn):
    # R1: a piece released clean can ship; once an NCR is opened on it the ship
    # action must refuse, mirroring the Gate 3 zero-open-NCR rule. Exercises the
    # actual ship gate (ReleaseScreen.open_ncr_piece_ids), which reuses
    # db.open_ncr_count.
    from shopqc.ui.release import ReleaseScreen
    p = make_project(conn)
    pk, pidv, t = seed_piece(conn, p, "W14X90")
    drive_gate2(conn, pk, t)
    db.execute_write(conn, "UPDATE pieces SET status='RELEASED' WHERE id=?", (pk,))
    assert ReleaseScreen.open_ncr_piece_ids(conn, [pk]) == []      # clean: shippable
    open_ncr(conn, p, pk)                                          # NCR after release
    assert db.open_ncr_count(conn, pk) > 0
    assert ReleaseScreen.open_ncr_piece_ids(conn, [pk]) == [pidv]  # ship gate refuses


def test_ceo_cosign_trigger_boundary():
    assert not db.needs_ceo_cosign(49.9, 0)
    assert db.needs_ceo_cosign(50, 0)         # exactly 50T
    assert db.needs_ceo_cosign(50.0001, 0)
    assert db.needs_ceo_cosign(0, 1)          # IAS regardless of tonnage
    assert not db.needs_ceo_cosign(0, 0)
    assert not db.needs_ceo_cosign(None, 0)


def test_ceo_name_exact_match():
    assert db.ceo_name_matches("The Owner")
    assert db.ceo_name_matches("  owner s. owner ")   # case/space tolerant
    assert not db.ceo_name_matches("M. Owner")
    assert not db.ceo_name_matches("")
    assert not db.ceo_name_matches(None)
