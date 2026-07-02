"""BOL parser: confidence tagging, structural shapes, joist marks, and the
Hillcrest 380 fixture joist/deck/anchor scope."""

from shopqc import bol_import as b
from support import FIXTURE_PDF


def test_confidence_tagging():
    items = b.parse_lines(["W14X90 QTY 10 HEAT HT55", "HSS6X6X1/4 8 EA",
                           "C12X20.7", "just some words"])
    by = {i["section"]: i for i in items}
    assert by["W14X90"]["confidence"] == "high"
    assert by["W14X90"]["qty"] == 10 and by["W14X90"]["heat"] == "HT55"
    assert by["HSS6X6X1/4"]["confidence"] == "medium" and by["HSS6X6X1/4"]["qty"] == 8
    assert by["C12X20.7"]["confidence"] == "low" and by["C12X20.7"]["qty"] == 0
    assert "JUST" not in by and len(items) == 3


def test_structural_shape_detection():
    secs = {i["section"] for i in b.parse_lines(
        ["W14X90", "HSS6X6X1/4", "C12X20.7", "L4X4X1/4", "WT5X11",
         "PIPE4", "MC12X10.6"])}
    assert {"W14X90", "HSS6X6X1/4", "C12X20.7", "L4X4X1/4", "WT5X11",
            "PIPE4", "MC12X10.6"} <= secs


def test_joist_marks_detected_as_joist_kind():
    # complete per-piece marks (with chord/size digit), incl a joist girder
    items = b.parse_lines(
        ["Joists 30K7 22K9; girders 60G8 48G8N10K per schedule"])
    by = {i["section"] for i in items}
    assert {"30K7", "22K9", "60G8", "48G8N10K"} <= by
    assert all(i["kind"] == "joist" for i in items)


def test_bare_series_and_tokens_not_mis_detected():
    # bare series and common BOL tokens must NOT parse as joist line items
    items = b.parse_lines(["Crane 50K capacity", "Budget 250K", "grid line 5G",
                           "Galvanized 600G coating QTY 5", "(30K and 20K series)"])
    assert items == []


def test_hillcrest_fixture_joist_and_deck_scope():
    # scope/tonnage proposal: no per-piece marks, so scope is detected by keyword
    scope = b.extract_scope(FIXTURE_PDF)
    assert scope["joists"] and scope["deck"]
    assert scope["anchors"] and scope["structural"]
    # whatever lines a proposal yields are joist scope at most, never spurious shapes
    assert all(i["kind"] == "joist" for i in b.extract_lines(FIXTURE_PDF))


def test_empty_or_sectionless_text_yields_nothing():
    assert b.parse_lines([]) == []
    assert b.parse_lines(["   ", "no sections here at all"]) == []


def test_detect_scope_keywords():
    s = b.detect_scope("CSI 05 21 00 joists; CSI 05 31 00 deck; F1554 anchors")
    assert s["joists"] and s["deck"] and s["anchors"]
    assert not b.detect_scope("plain text")["joists"]
