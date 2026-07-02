"""Scanner wedge parse (full payload and bare id) and ZPL label build."""

import os

from shopqc import db, piece_ids, labels
from support import make_project, seed_piece


def test_scan_full_payload_and_bare_id(conn):
    p = make_project(conn)
    pk, pidv, _ = seed_piece(conn, p, "W14X90")
    payload = piece_ids.qr_payload(pidv, p["job_number"], "HT55", db.today())
    assert db.piece_by_scan(conn, payload)["piece_id"] == pidv
    assert db.piece_by_scan(conn, pidv.lower())["piece_id"] == pidv
    assert db.piece_by_scan(conn, f"  {pidv}  ")["piece_id"] == pidv
    assert db.piece_by_scan(conn, "NOPE-1") is None


def test_zpl_build_contains_qr_and_payload():
    payload = "ICD-W14X90-001|24-101|HT55|2026-06-18"
    z = labels.build_zpl("ICD-W14X90-001", "W14X90", "ICD Church",
                         "2026-06-18", payload)
    assert "^XA" in z and "^XZ" in z and "^BQN" in z and payload in z


def test_print_batch_file_mode(tmp_path):
    out = str(tmp_path / "lab")
    labels.print_batch(["^XA^XZ", "^XA^XZ"],
                       {"printer_mode": "file", "label_output_dir": out})
    assert len(os.listdir(out)) == 2
