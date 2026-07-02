"""Tests for the member census spike: regex patterns and the router.

No PDF dependency: these exercise the pure functions. The live-set
numbers come from score_spike runs and land in the accuracy ledger,
not here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from takeoff_pipeline.census import (
    _find_conflicts,
    _reconstruct_row,
    classify_hit,
    normalize_designation,
    sweep_text,
)
from takeoff_pipeline.scale_check import parse_feet_token, parse_scale
from takeoff_pipeline.score_spike import partition_scoring_rows
from takeoff_pipeline.sheet_router import (
    CATEGORY_DETAILS,
    CATEGORY_FOUNDATION,
    CATEGORY_FRAMING,
    CATEGORY_GENERAL_NOTES,
    CATEGORY_UNKNOWN,
    SCANNED_TEXT_THRESHOLD,
    classify_sheet_number,
    is_scanned,
    title_category_hint,
)


def _designations(text):
    return [m for f, _, m, _ in sweep_text(text) if f == "designation"]


def _families(text):
    return [(f, c, m) for f, c, m, _ in sweep_text(text)]


# -- designation grammar ---------------------------------------------------

def test_w_shapes():
    assert _designations("W12X26 TYP") == ["W12X26"]
    assert _designations("W36x150") == ["W36x150"]
    assert _designations("SWX10") == []


def test_hss_shapes():
    assert _designations("HSS10X10X1/4") == ["HSS10X10X1/4"]
    assert _designations("HSS8x8x1/4 COLUMN") == ["HSS8x8x1/4"]
    assert _designations("HSS6X6X3/8") == ["HSS6X6X3/8"]


def test_angles_and_channels():
    assert _designations('L3x3x1/4"') == ['L3x3x1/4"']
    assert _designations("L2x2x1/4") == ["L2x2x1/4"]
    assert _designations("C12X20.7") == ["C12X20.7"]
    assert _designations("MC8X22.8") == ["MC8X22.8"]
    assert _designations("WT5X11") == ["WT5X11"]


def test_joists_and_girders():
    assert _designations("28K7 @ 5'-0\" O.C.") == ["28K7"]
    assert _designations("32LH07") == ["32LH07"]
    assert _designations("16DLH13") == ["16DLH13"]
    got = _designations("54G8N12.5K JOIST GIRDER")
    assert got == ["54G8N12.5K"]
    assert _designations("36G8N11.5K") == ["36G8N11.5K"]


def test_plate_requires_size_not_words():
    assert _designations('PL 1/2" x 6"') != []
    assert _designations("PL3/8") != []
    # The classic PL false positives must NOT match.
    for word in ("PLAN", "PLACEMENT", "PLATE WASHER NOTES", "APPLIED",
                 "PLANS"):
        assert _designations(word) == [], word


def test_pipe_and_schedule_40_rail():
    assert _designations("PIPE 3 STD") == ["PIPE 3 STD"]
    hits = _designations('1 1/2" X SCHEDULE 40 PIPE RAIL')
    assert any("SCHEDULE 40" in h for h in hits)


def test_schedule_40_is_not_a_schedule_table_heading():
    from takeoff_pipeline.census import _SCHEDULE_HEADING
    assert _SCHEDULE_HEADING.search("FOOTING SCHEDULE")
    assert _SCHEDULE_HEADING.search("BEARING CHANNEL SCHEDULE")
    assert not _SCHEDULE_HEADING.search('1 1/2" X SCHEDULE 40')


def test_keyword_families_are_low_signal_not_designations():
    fams = _families("ANCHOR RODS 3/4 IN DIA")
    assert ("keyword", "ANCH") in [(f, c) for f, c, _ in fams]
    fams = _families("CAGED LADDER, RE: 5/S5.02")
    assert any(c == "MISC" and "LADDER" in m for f, c, m in fams)
    fams = _families("TILT WALL EMBED PLATE")
    assert any(c == "MISC" and "EMBED" in m.upper() for f, c, m in fams)
    fams = _families("61,621 SF GROSS")
    assert any("SF" in m for f, c, m in fams)


def test_no_overlap_double_hits():
    # The girder pattern wins over K-series inside one tag.
    fams = _families("54G8N12.5K")
    assert len([m for f, _, m, in fams if f == "designation"]) == 1


def test_normalize_designation_for_matching_only():
    assert normalize_designation('hss 8x8x1/4"') == "HSS8X8X1/4"
    assert normalize_designation("32LH07") == "32LH07"


def test_classify_hit_schedule_overrides():
    assert classify_hit("BEAM", "S4.00 COLUMN SCHEDULE") == "COL"
    assert classify_hit("BEAM", "FOOTING SCHEDULE") == "COL"
    assert classify_hit("BEAM", "S2.00 FOUNDATION PLAN") == "BEAM"
    assert classify_hit("", "") == "MISC"


# -- router ----------------------------------------------------------------

def test_classify_sheet_number_scheme():
    assert classify_sheet_number("S0.1") == CATEGORY_GENERAL_NOTES
    assert classify_sheet_number("S1.01") == CATEGORY_FOUNDATION
    assert classify_sheet_number("S2.00") == CATEGORY_FRAMING
    assert classify_sheet_number("S3.00") == CATEGORY_DETAILS
    assert classify_sheet_number("S5.02") == CATEGORY_DETAILS
    assert classify_sheet_number("S12.1") == CATEGORY_DETAILS
    assert classify_sheet_number("A1.1") == CATEGORY_UNKNOWN
    assert classify_sheet_number("") == CATEGORY_UNKNOWN


def test_title_hint():
    assert title_category_hint("GENERAL NOTES") == CATEGORY_GENERAL_NOTES
    assert title_category_hint("FOUNDATION PLAN") == CATEGORY_FOUNDATION
    assert title_category_hint("ROOF FRAMING PLAN") == CATEGORY_FRAMING
    assert title_category_hint("FOUNDATION DETAILS") == CATEGORY_DETAILS
    assert title_category_hint("") == CATEGORY_UNKNOWN


def test_scanned_threshold():
    assert is_scanned(0)
    assert is_scanned(SCANNED_TEXT_THRESHOLD - 1)
    assert not is_scanned(SCANNED_TEXT_THRESHOLD)
    assert not is_scanned(116)  # leanest real vector sheet on SP183 B1


# -- review regressions ------------------------------------------------------

def test_spaced_designations_match():
    # Schedules space the X: the S6.00 BEARING CHANNEL SCHEDULE writes
    # C6 X 8.2. These were invisible before the review fix.
    assert _designations("C6 X 8.2") == ["C6 X 8.2"]
    assert _designations("C12 X 20.7") == ["C12 X 20.7"]
    assert _designations("W12 X 26") == ["W12 X 26"]
    assert _designations("MC8 X 22.8") == ["MC8 X 22.8"]
    assert _designations("WT5 X 11") == ["WT5 X 11"]
    assert _designations("HSS 6 X 6 X 1/4") == ["HSS 6 X 6 X 1/4"]
    assert _designations("L3 X 3 X 1/4") == ["L3 X 3 X 1/4"]
    # Grid text must not false-positive: no digit glued to the letter.
    assert _designations("GRID C 8 AND LINE 9") == []


def test_plate_multi_dimension_tags_complete():
    # Schema 3.2: the tag as written, never truncated.
    assert _designations("PL 3/4x10x1'-2\"") == ["PL 3/4x10x1'-2\""]
    assert _designations('PL1" X 13" X 1\'-1"') == ['PL1" X 13" X 1\'-1"']
    assert _designations('PL 3/8" X 7" X 0\'-8"') \
        == ['PL 3/8" X 7" X 0\'-8"']


def test_conflicts_fire_across_schedule_class_rewrite():
    # A COLUMN SCHEDULE hit is COL while the same tag on a plan is
    # BEAM. Conflict grouping must still pair them (grouping by
    # designation only), or COL conflicts are structurally impossible.
    sched = {"designation": "HSS6X6X1/4", "item_class": "COL",
             "source_kind": "SCHEDULE", "qty": 16.0,
             "primary_source": "S4.00 COLUMN SCHEDULE",
             "confidence": "high", "conflict_group": None}
    plan_hits = [{"designation": "HSS6X6X1/4", "item_class": "BEAM",
                  "source_kind": "PLAN", "qty": None,
                  "primary_source": "S2.00 FOUNDATION PLAN",
                  "confidence": "medium", "conflict_group": None}
                 for _ in range(14)]
    conflicts = _find_conflicts("J", [sched] + plan_hits, "now")
    assert len(conflicts) == 1
    cf = conflicts[0]
    assert cf["schedule_qty"] == 16.0
    assert cf["plan_qty"] == 14.0
    assert cf["item_class"] == "COL"
    # Section 8: both values AND both sources in the note.
    assert "COLUMN SCHEDULE" in cf["note"]
    assert "FOUNDATION PLAN" in cf["note"]
    # All hits in the group drop to low and share the conflict key.
    assert sched["confidence"] == "low"
    assert sched["conflict_group"] == cf["conflict_group"]


def test_reconstruct_row_bridges_split_tags():
    # The live S4.00 BASE PLATE SCHEDULE splits its heaviest plates
    # across cells, mid-token. The reconstruction must recover them.
    cells = ["", "", "HSS 6x6", "P", "", "L1\" X 13\" X 1'",
             "-1\" PL 3/8\" X 7\" X 0"]
    recon = _reconstruct_row(cells)
    assert "PL1\" X 13\" X 1'-1\"" in recon
    tags = [m for f, _, m, _ in __import__(
        "takeoff_pipeline.census", fromlist=["sweep_text"]
    ).sweep_text(recon) if f == "designation"]
    assert any(t.startswith("PL1\" X 13\"") for t in tags)
    assert any(t.startswith("HSS 6x6") for t in tags)


def test_partition_reports_unrecognized_scoring():
    rows = [{"scoring": "presence"}, {"scoring": "attribute"},
            {"scoring": "value"}, {"scoring": "count"}]
    attr, pres, val, unrec = partition_scoring_rows(rows)
    assert len(attr) == 1 and len(pres) == 1 and len(val) == 1
    assert unrec == [{"scoring": "count"}]


def test_parse_feet_token_accepts_inches():
    assert parse_feet_token("413'") == 413.0
    assert parse_feet_token('413\'-4"') == 413.0 + 4 / 12
    assert parse_feet_token('45\'-10"') == 45.0 + 10 / 12
    assert parse_feet_token('22\'-2 1/2"') is not None
    assert parse_feet_token("26") is None
    assert parse_feet_token("S4.00") is None


# -- scale parsing ---------------------------------------------------------

def test_parse_scale():
    assert parse_scale('SCALE: 1" = 20\'-0"') == 20.0
    assert parse_scale('3/4" = 1\'-0"') == 1.0 / 0.75
    assert parse_scale('1 1/2" = 1\'-0"') == 1.0 / 1.5
    assert parse_scale('1/8" = 1\'-0"') == 8.0
    assert parse_scale("NOT TO SCALE") is None
    assert parse_scale("") is None
