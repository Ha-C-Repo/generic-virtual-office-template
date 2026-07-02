"""High-strength bolt receiving acceptance (Phase B, RCSC / ASTM F3125). The pure
rule db.fastener_receiving_blocked_reason is the single source the receiving UI and
these tests share, like the other gate predicates. Receiving acceptance, not an NCR
category."""

from shopqc import db, standards

# (rocap_lot_no, markings_verified, mfr_cert_on_file, galvanized, lube_check_done)
_COMPLETE = ("ROCAP-7781", 1, 1, 0, 0)
_KEYS = ("rocap_lot_no", "markings_verified", "mfr_cert_on_file", "galvanized",
         "lube_check_done")


def _reason(**kw):
    args = dict(zip(_KEYS, _COMPLETE))
    args.update(kw)
    return db.fastener_receiving_blocked_reason(**args)


def test_accepts_when_complete_non_galvanized():
    assert _reason() == ""


def test_rejects_missing_rocap_lot():
    assert "ROCAP" in _reason(rocap_lot_no="")
    assert _reason(rocap_lot_no="   ") != ""        # whitespace is not a lot number


def test_rejects_missing_markings():
    assert "markings" in _reason(markings_verified=0)


def test_rejects_missing_cert():
    assert "cert" in _reason(mfr_cert_on_file=0)


def test_lube_required_only_when_galvanized():
    assert _reason(galvanized=0, lube_check_done=0) == ""       # not galvanized: ok
    assert "lubrication" in _reason(galvanized=1, lube_check_done=0).lower()  # blocked
    assert _reason(galvanized=1, lube_check_done=1) == ""       # galvanized + lube: ok


def test_multiple_missing_listed_together():
    r = _reason(rocap_lot_no="", markings_verified=0, mfr_cert_on_file=0)
    assert "ROCAP" in r and "markings" in r and "cert" in r


def test_assembly_types_and_reference():
    assert standards.FASTENER_ASSEMBLY_TYPES == ("A325", "A490", "F1852", "F2280")
    assert "F3125" in standards.RCSC_F3125_RECEIVING_REF


def test_fastener_lots_table_created_idempotently(conn):
    # init_db is run by the fixture; running it again must not error (IF NOT EXISTS)
    db.init_db(conn)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(fastener_lots)")}
    assert {"project_id", "assembly_type", "rocap_lot_no", "received_complete",
            "lube_check_done"}.issubset(cols)


def test_no_em_dashes_in_fastener_strings():
    em, en = chr(0x2014), chr(0x2013)
    for s in (standards.RCSC_F3125_RECEIVING_REF,
              db.fastener_receiving_blocked_reason("", 0, 0, 1, 0)):
        assert em not in s and en not in s
