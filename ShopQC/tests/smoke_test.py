"""Headless end-to-end logic test. Exercises the full Gate 1 -> 2 -> 3 path
including every hard block, without Tkinter. Run: python3 tests/smoke_test.py"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shopqc import db, piece_ids, labels, reports  # noqa: E402

tmp = tempfile.mkdtemp()
conn = db.connect(os.path.join(tmp, "test.db"))
db.init_db(conn)

# Gate 0: project (>=50T so CEO co-sign applies)
db.execute_write(conn,
    "INSERT INTO projects (code, job_number, name, gc_name, tonnage, "
    "ias_required, created_date) VALUES ('ICD','24-101','ICD Church','GC Co',"
    "60,0,?)", (db.now(),))
p = conn.execute("SELECT * FROM projects").fetchone()

# Gate 1: receive 2 pieces of W14X90
ids = []
for _ in range(2):
    pid = piece_ids.next_piece_id(conn, p["code"], "W14x90")
    cur = db.execute_write(conn,
        "INSERT INTO pieces (project_id, piece_id, section, heat_number, "
        "created_date) VALUES (?,?,?,?,?)", (p["id"], pid, "W14X90", "HT55", db.now()))
    db.seed_traveler(conn, cur.lastrowid, "ICD Church / 24-101", pid, "W14X90", "HT55", "L1")
    ids.append((cur.lastrowid, pid))
assert ids[0][1] == "ICD-W14X90-001" and ids[1][1] == "ICD-W14X90-002", ids

# label
payload = piece_ids.qr_payload(ids[0][1], "24-101", "HT55", db.today())
assert payload == f"{ids[0][1]}|24-101|HT55|{db.today()}"
zpl = labels.build_zpl(ids[0][1], "W14X90", "ICD Church", db.today(), payload)
assert "^BQN" in zpl and payload in zpl

# scanner wedge resolves full payload AND bare id
assert db.piece_by_scan(conn, payload)["piece_id"] == ids[0][1]
assert db.piece_by_scan(conn, ids[0][1].lower())["piece_id"] == ids[0][1]

pk = ids[0][0]
# Gate 2: locked sequence. Fields 1-4 auto-signed; 5..14 must go in order.
missing = db.traveler_complete_through(conn, pk, 14)
assert missing == [5, 6, 7, 8, 9, 10, 11, 12, 13, 14], missing

def sign(num, by, val="x"):
    db.execute_write(conn,
        "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
        "WHERE piece_pk=? AND field_number=?", (val, by, db.now(), pk, num))

for n in (5, 6, 7):
    sign(n, "Mario Gutierrez")
# pre-weld CWI hard block is sequence position 8: still missing -> release must fail
assert db.traveler_complete_through(conn, pk, 14)[0] == 8
sign(8, "CWI: J. Inspector", "PRE-WELD OK")
sign(9, "W-07", "pWPS00003")
sign(10, "CWI: J. Inspector", "ACCEPT")
for n in (11, 13):
    sign(n, "J. Inspector", "N/A")
sign(12, "Mario Gutierrez", "within AISC 303-22")
sign(14, "Coater", "4.2 mils")
assert db.traveler_complete_through(conn, pk, 14) == []

# NCR hold blocks release
db.execute_write(conn,
    "INSERT INTO ncrs (project_id, piece_pk, gate, category, description, "
    "opened_by, opened_date) VALUES (?,?,2,'Welding','test ncr','PG',?)",
    (p["id"], pk, db.now()))
assert db.open_ncr_count(conn, pk) == 1
# EOR rule check is UI-level; close normally here
db.execute_write(conn,
    "UPDATE ncrs SET disposition='REWORK', disposition_authority='SD', "
    "status='CLOSED', closed_by='SD', closed_date=? WHERE piece_pk=?",
    (db.now(), pk))
assert db.open_ncr_count(conn, pk) == 0

# Gate 3: release with CEO co-sign (project is 60T)
db.execute_write(conn,
    "INSERT INTO release_records (piece_pk, shop_director_sign, cwi_sign, "
    "ceo_sign, release_date) VALUES (?,?,?,?,?)",
    (pk, "Shop Director", "J. Inspector", "The Owner", db.now()))
db.execute_write(conn, "UPDATE pieces SET status='RELEASED' WHERE id=?", (pk,))

# PDFs all build
piece = conn.execute("SELECT * FROM pieces WHERE id=?", (pk,)).fetchone()
rel = conn.execute("SELECT * FROM release_records WHERE piece_pk=?", (pk,)).fetchone()
rows = db.traveler_rows(conn, pk)
out = lambda n: os.path.join(tmp, n)
reports.traveler_pdf(out("t.pdf"), p, piece, rows, [1])
reports.release_cert_pdf(out("c.pdf"), p, piece, rel)
ncr_rows = conn.execute(
    "SELECT n.*, pc.piece_id FROM ncrs n LEFT JOIN pieces pc ON pc.id=n.piece_pk").fetchall()
reports.ncr_pdf(out("n.pdf"), ncr_rows)
reports.manifest_pdf(out("m.pdf"), p, "LOAD-1",
                     [dict(piece) | {"release_date": rel["release_date"]}])
reports.project_summary_pdf(out("s.pdf"), p, {"RELEASED": 1, "RECEIVED": 1}, 0)
import json
rir_checks = json.dumps({"Heat number on steel matches MTR": True})
db.execute_write(conn, "INSERT INTO rir_records (project_id, signed_by, "
    "signed_date, all_checks_json) VALUES (?,?,?,?)", (p["id"], "RI", db.now(), rir_checks))
rir = conn.execute("SELECT * FROM rir_records").fetchone()
bol = conn.execute("SELECT * FROM bol_items").fetchall()
reports.rir_pdf(out("r.pdf"), p, rir, bol)
for f in ("t.pdf", "c.pdf", "n.pdf", "m.pdf", "s.pdf", "r.pdf"):
    assert os.path.getsize(out(f)) > 1000, f

# file-mode label print
cfg = {"printer_mode": "file", "label_output_dir": os.path.join(tmp, "lab")}
labels.print_batch([zpl, zpl], cfg)
assert len(os.listdir(os.path.join(tmp, "lab"))) == 2

# =====================================================================
# SJI joist traveler variant (additive). The 18-field structural path above
# is unchanged and still passes; everything below exercises the joist set.
# =====================================================================

# --- section detection: complete joist marks vs structural shapes ---
for mark in ("30KCS4", "30K7", "22K9", "24LH06", "52DLH15", "60G8", "48G8N10K"):
    assert piece_ids.traveler_type_for_section(mark) == "JOIST", mark
    assert piece_ids.section_format_ok(mark), mark
for shape in ("W14X90", "HSS6X6X1/4", "2L4X4X1/4", "C12X20.7"):
    assert piece_ids.traveler_type_for_section(shape) == "STRUCTURAL", shape

# --- additive migration: traveler_type column ---
assert "traveler_type" in {r["name"] for r in conn.execute(
    "PRAGMA table_info(pieces)")}
# a legacy DB (pieces without the column) gains it additively and idempotently
leg = db.connect(os.path.join(tmp, "legacy.db"))
leg.execute("CREATE TABLE pieces (id INTEGER PRIMARY KEY, piece_id TEXT)")
leg.commit()
db.migrate(leg)
db.migrate(leg)  # second run is a no-op, must not raise
assert "traveler_type" in {r["name"] for r in leg.execute(
    "PRAGMA table_info(pieces)")}

# --- canonical fixture (Hillcrest 380) carries the joist scope ---
fixture = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "test_fixtures", "PRJ-2026-HILLCREST-STR-001.txt")
ftext = open(fixture, encoding="utf-8").read()
assert "30K" in ftext and "60G" in ftext and "Bridging" in ftext, "fixture scope"

# --- seed a joist piece from the Hillcrest scope and run it through the gates ---
db.execute_write(conn,
    "INSERT INTO projects (code, job_number, name, gc_name, tonnage, "
    "ias_required, created_date) VALUES ('HILL','2428','Hillcrest 380 Bldg 1',"
    "'Crossland Construction',212,0,?)", (db.now(),))
jp = conn.execute("SELECT * FROM projects WHERE code='HILL'").fetchone()
jsec = "30KCS4"
jtype = piece_ids.traveler_type_for_section(jsec)
assert jtype == "JOIST"
jpid = piece_ids.next_piece_id(conn, jp["code"], jsec)
assert jpid == "HILL-30KCS4-001", jpid
cur = db.execute_write(conn,
    "INSERT INTO pieces (project_id, piece_id, section, heat_number, "
    "traveler_type, created_date) VALUES (?,?,?,?,?,?)",
    (jp["id"], jpid, jsec, "HTJ1", jtype, db.now()))
jpk = cur.lastrowid
# Pass a lot so field 4 (MTR/SJI mill cert) auto-signs, matching the structural
# path above. NOTE for K3/K4: info field 4 sits outside the floor range, so when
# received with an empty lot it cannot be signed later and lingers in the Gate 3
# completeness check. Pre-existing structural behavior, flagged not changed here.
db.seed_traveler(conn, jpk, "Hillcrest 380 Bldg 1 / 2428", jpid, jsec, "HTJ1",
                 "SJI-LOT-7", jtype)

# joist set is 20 fields; info 1-4 auto-signed, floor steps 5..16 open
jrows = db.traveler_rows(conn, jpk)
assert len(jrows) == 20, len(jrows)
jlast = db.gate3_last_field(jtype)
assert jlast == 16
assert db.traveler_complete_through(conn, jpk, jlast) == list(range(5, 17))


def jsign(num, by, val="x"):
    db.execute_write(conn,
        "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
        "WHERE piece_pk=? AND field_number=?", (val, by, db.now(), jpk, num))


# Gate 2 locked sequence: sign 5,6,7 then the pre-weld CWI block sits at 8
for n in (5, 6, 7):
    jsign(n, "Mario Gutierrez", "OK")
assert db.traveler_complete_through(conn, jpk, jlast)[0] == 8  # CWI pre-weld gate
jsign(8, "CWI: J. Inspector", "PRE-WELD OK")
jsign(9, "W-11", "pWPS00003")
jsign(10, "CWI: J. Inspector", "ACCEPT")
jsign(11, "QC Tech", "5.0 in / Underslung")        # bearing seat depth + type
jsign(12, "QC Tech", "3 rows / Diagonal")          # bridging rows + type
jsign(13, "QC Tech", "2 welds per SJI detail")     # end anchorage
jsign(14, "QC Tech", "0.75 in vs SJI 0.75 in")     # camber measured vs specified
jsign(15, "QC Tech", "N/A")                        # UT/MT optional
jsign(16, "Coater", "3.5 mils")                    # surface prep / DFT
assert db.traveler_complete_through(conn, jpk, jlast) == []

# --- hard block 6: unauthorized field modification NCR needs an EOR to close ---
assert db.ncr_close_blocked_reason("Unauthorized field modification", "")
assert db.ncr_close_blocked_reason("Unauthorized field modification", "   ")
assert not db.ncr_close_blocked_reason("Unauthorized field modification", "EOR-1")
assert not db.ncr_close_blocked_reason("Welding", "")  # other categories not gated

# exercise it on the joist piece: a field-modification deflection NCR
db.execute_write(conn,
    "INSERT INTO ncrs (project_id, piece_pk, gate, category, description, "
    "opened_by, opened_date) VALUES (?,?,2,?,?,?,?)",
    (jp["id"], jpk, "Unauthorized field modification",
     "Camber short of SJI under field modification per AISC", "PG", db.now()))
assert db.open_ncr_count(conn, jpk) == 1
nrow = conn.execute("SELECT * FROM ncrs WHERE piece_pk=? ORDER BY id DESC LIMIT 1",
                    (jpk,)).fetchone()
assert db.ncr_close_blocked_reason(nrow["category"], nrow["eor_reference"])  # blocked
db.execute_write(conn,
    "UPDATE ncrs SET disposition='REPAIR', disposition_authority='EOR', "
    "eor_reference='EOR-2428-SK-07', status='CLOSED', closed_by='SD', "
    "closed_date=? WHERE id=?", (db.now(), nrow["id"]))
assert db.open_ncr_count(conn, jpk) == 0

# --- Gate 3: release with CEO co-sign (Hillcrest is 212T) at joist positions ---
ts = db.now()
db.execute_write(conn,
    "INSERT INTO release_records (piece_pk, shop_director_sign, cwi_sign, "
    "ceo_sign, release_date) VALUES (?,?,?,?,?)",
    (jpk, "Shop Director", "J. Inspector", "The Owner", ts))
jmeta = db.spec_meta(jtype)
assert (jmeta["release_director"], jmeta["release_cwi"], jmeta["ship"]) == (17, 18, 19)
for num, by in ((jmeta["release_director"], "Shop Director"),
                (jmeta["release_cwi"], "CWI: J. Inspector")):
    db.execute_write(conn,
        "UPDATE traveler_fields SET value=?, signed_by=?, timestamp=? "
        "WHERE piece_pk=? AND field_number=?", (ts[:10], by, ts, jpk, num))
db.execute_write(conn, "UPDATE pieces SET status='RELEASED' WHERE id=?", (jpk,))
jpiece = conn.execute("SELECT * FROM pieces WHERE id=?", (jpk,)).fetchone()
assert jpiece["traveler_type"] == "JOIST"

# NCR-list substitution must target the variant NCR field (20 joist, 18 struct),
# never a literal 18 (which on a joist is the CWI Final-Release row). Regression
# for the field-18 corruption found in adversarial review.
jnf = db.spec_meta("JOIST")["ncr_auto"]
assert jnf == 20
rel18 = {"field_number": 18, "value": "2026-06-18"}   # joist CWI Final-Release row
ncr20 = {"field_number": 20, "value": "NCR-7"}         # joist NCR row
assert reports._traveler_cell_value(rel18, jnf, [7]) == "2026-06-18"  # not "7"
assert reports._traveler_cell_value(ncr20, jnf, [7]) == "7"
snf = db.spec_meta("STRUCTURAL")["ncr_auto"]
assert snf == 18
assert reports._traveler_cell_value({"field_number": 18, "value": "x"}, snf, [1]) == "1"

# joist PDFs build and reflect the variant; print WITH a non-empty NCR list so the
# substitution path is exercised (the piece carried NCR nrow earlier)
jrel = conn.execute("SELECT * FROM release_records WHERE piece_pk=?", (jpk,)).fetchone()
reports.traveler_pdf(out("jt.pdf"), jp, jpiece, db.traveler_rows(conn, jpk),
                     [nrow["id"]])
reports.release_cert_pdf(out("jc.pdf"), jp, jpiece, jrel)
for f in ("jt.pdf", "jc.pdf"):
    assert os.path.getsize(out(f)) > 1000, f

print("SMOKE TEST PASS: gates, hard blocks, IDs, scan parse, labels, all 6 PDFs")
print("JOIST VARIANT PASS: detection, migration, 20-field SJI traveler, camber + "
      "bridging + seat capture, CWI block, EOR-before-close, Gate 3 CEO co-sign")
