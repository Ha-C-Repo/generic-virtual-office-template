"""Tests for the provenance-validation gate (plan item D1, advisory).

The gate re-checks every canonical takeoff row against the extracted
vector-text layer of the sheet the row cites. Strict for text-claiming
methods, informational for the rest. Advisory and read-only: it never
mutates a row and never produces a price, quantity, weight, or rate.
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bridge import takeoff_provenance as tp
from bridge.takeoff_row import (
    make_row, METHOD_STATED_SCHEDULE, METHOD_VECTOR_OR_TAG, METHOD_VISION,
)

SHEETS = {
    "S-501": "FOUNDATION PLAN\nF10 TYP\nB12 GIRDER\nHSS6X6X1/4",
    "S-201": "FRAMING PLAN\nW12X26\nB1 BEAM\nCU5 CU5 CU5",
}


def _row(tag, drawing, method=METHOD_STATED_SCHEDULE, basis="b"):
    return make_row(tag, tag, "Structural Steel", 1, "EA", drawing, method,
                    basis=basis)


# -- confirmation ------------------------------------------------------------

def test_confirmed_row_produces_no_finding():
    r = tp.check_provenance([_row("F10", "S-501")], SHEETS)
    assert r["findings"] == []
    assert r["summary"]["confirmed"] == 1
    assert r["summary"]["strict_checked"] == 1
    assert r["summary"]["validated_counts"] == "confirmed 1/1 strict-checked rows"


def test_tag_boundary_b1_does_not_match_b12():
    r = tp.check_provenance([_row("B1", "S-501")], SHEETS)
    # B12 is on S-501; B1 is only on S-201. Must NOT count B12 as B1.
    f = r["findings"][0]
    assert f["type"] == tp.FINDING_CONFIRMED_ELSEWHERE
    assert f["suggested_drawings"] == ["S-201"]


def test_sheet_name_matching_is_case_and_extension_insensitive():
    sheets = {"s-501.txt": "F10 TYP"}
    r = tp.check_provenance([_row("F10", "S-501")], sheets)
    assert r["summary"]["confirmed"] == 1


# -- failures on strict (text-claiming) rows ---------------------------------

def test_mislocated_tag_gets_relocation_suggestion_only():
    rows = [_row("W12X26", "S-501", METHOD_VECTOR_OR_TAG)]
    before = copy.deepcopy(rows)
    r = tp.check_provenance(rows, SHEETS)
    f = r["findings"][0]
    assert f["type"] == tp.FINDING_CONFIRMED_ELSEWHERE
    assert f["suggested_drawings"] == ["S-201"]
    assert f["needs_judgment"] is True
    assert rows == before  # read-only, never relocates


def test_unsourced_tag_is_flagged_for_human_check():
    r = tp.check_provenance([_row("ZZ99", "S-501")], SHEETS)
    f = r["findings"][0]
    assert f["type"] == tp.FINDING_UNSOURCED
    assert f["needs_judgment"] is True
    assert r["summary"]["unsourced"] == 1


def test_missing_sheet_text_is_flagged_never_assumed():
    r = tp.check_provenance([_row("F10", "S-999")], SHEETS)
    f = r["findings"][0]
    assert f["type"] == tp.FINDING_UNKNOWN_SHEET
    assert f["needs_judgment"] is True


def test_empty_tag_is_flagged():
    row = _row("F10", "S-501")
    row["tag"] = ""
    r = tp.check_provenance([row], SHEETS)
    assert r["findings"][0]["type"] == tp.FINDING_EMPTY_TAG


# -- non-text methods are informational only ---------------------------------

def test_vision_row_absent_everywhere_is_informational():
    r = tp.check_provenance([_row("ZZ99", "S-501", METHOD_VISION)], SHEETS)
    f = r["findings"][0]
    assert f["type"] == tp.FINDING_INFO_ABSENT
    assert f["needs_judgment"] is False
    assert r["summary"]["strict_checked"] == 0


def test_vision_row_found_elsewhere_produces_no_finding():
    r = tp.check_provenance([_row("W12X26", "S-501", METHOD_VISION)], SHEETS)
    assert r["findings"] == []


# -- advisory contract --------------------------------------------------------

def test_advisory_contract_no_numbers_no_verdict():
    r = tp.check_provenance([_row("F10", "S-501")], SHEETS)
    assert r["advisory"] is True
    assert r["generates_numbers"] is False
    assert r["verdict"] is None
    assert "disclaimer" in r


def test_empty_inputs_are_tolerated():
    r = tp.check_provenance([], {})
    assert r["summary"]["row_count"] == 0
    assert r["findings"] == []
    r2 = tp.check_provenance(None, None)
    assert r2["summary"]["row_count"] == 0


# -- load_sheet_texts ----------------------------------------------------------

def test_load_sheet_texts_reads_txt_stems(tmp_path):
    (tmp_path / "sheet_001.txt").write_text("F10 TYP", encoding="utf-8")
    (tmp_path / "sheet_001.png").write_bytes(b"\x89PNG")
    texts = tp.load_sheet_texts(tmp_path)
    assert texts == {"sheet_001": "F10 TYP"}


def test_load_sheet_texts_missing_dir_returns_empty():
    assert tp.load_sheet_texts("/nonexistent/dir/xyz") == {}
