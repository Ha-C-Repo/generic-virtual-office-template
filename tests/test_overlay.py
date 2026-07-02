"""Tests for the QA overlay (Prompt 6). A synthetic one-page PDF plus
a synthetic census exercise the full path: rect annotations with popup
notes, conflict coloring, congestion zones, the appended exception
page, and independent-reader open (pdfplumber, which shares no code
with PyMuPDF)."""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from takeoff_pipeline import overlay
from takeoff_pipeline.overlay import (
    CONGESTION_THRESHOLD_PER_SQIN,
    PALETTE,
    _congestion_zones,
    _note_text,
    _page_map,
    build_overlay,
    sheet_key,
)


def test_palette_covers_classes_and_reserves_red():
    for cls in ("COL", "BEAM", "JST", "PLATE", "DECK", "ANCH", "MISC",
                "CONFLICT", "CONGESTION"):
        assert cls in PALETTE
    red = PALETTE["CONFLICT"]
    assert red[0] > 0.7 and red[1] < 0.3 and red[2] < 0.3
    for cls, color in PALETTE.items():
        if cls != "CONFLICT":
            assert color != red, f"{cls} reuses the conflict red"


def test_congestion_zone_math():
    def hit(x, y):
        return {"bbox": json.dumps([x, y, x + 4, y + 4])}

    # Threshold hits in one cell: no flag. One more: flag.
    hits = [hit(10 + i, 10) for i in range(CONGESTION_THRESHOLD_PER_SQIN)]
    assert _congestion_zones(hits, (0, 0, 720, 720)) == []
    hits.append(hit(40, 40))
    zones = _congestion_zones(hits, (0, 0, 720, 720))
    assert len(zones) == 1
    (rect, n) = zones[0]
    assert n == CONGESTION_THRESHOLD_PER_SQIN + 1
    assert rect[0] == 0.0 and rect[1] == 0.0  # the first 1-inch cell


def test_note_text_is_dash_clean():
    hit = {"designation": "W12X26", "item_class": "BEAM",
           "source_kind": "PLAN", "qty": None, "confidence": "medium",
           "primary_source": "S3.00 ROOF FRAMING PLAN",
           "conflict_group": "J:X"}
    note = _note_text(hit, {("W12X26", "PLAN"): 7})
    assert "W12X26" in note
    assert "plan callout 1 of 7" in note
    assert "confidence: medium" in note
    assert "CONFLICT" in note
    assert "—" not in note and "–" not in note


def test_sheet_key_natural_order():
    assert sheet_key("S2.1") < sheet_key("S10.1")


def _synthetic_pdf(path):
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 100), "W12X26")
    page.insert_text((300, 300), "28K7")
    doc.save(str(path))
    doc.close()
    return path


def _synthetic_db(path):
    c = sqlite3.connect(str(path))
    c.executescript("""
        CREATE TABLE census_hits (id INTEGER PRIMARY KEY AUTOINCREMENT,
            job TEXT, designation TEXT, item_class TEXT, sheet TEXT,
            bbox TEXT, raw_text TEXT, source_kind TEXT,
            primary_source TEXT, confidence TEXT, conflict_group TEXT,
            qty REAL, created_at TEXT);
        CREATE TABLE conflicts (id INTEGER PRIMARY KEY AUTOINCREMENT,
            job TEXT, conflict_group TEXT, designation TEXT,
            item_class TEXT, schedule_qty REAL, plan_qty REAL,
            schedule_source TEXT, plan_source TEXT, note TEXT,
            created_at TEXT);
    """)
    rows = [
        ("J", "W12X26", "BEAM", "PAGE-0", "[100.0, 92.0, 140.0, 104.0]",
         "W12X26", "PLAN", "PAGE-0", "medium", None, None, "t"),
        ("J", "28K7", "JST", "PAGE-0", "[300.0, 292.0, 330.0, 304.0]",
         "28K7", "PLAN", "PAGE-0", "medium", "J:JST:28K7", None, "t"),
        ("J", "EMBED PL", "MISC", "PAGE-0",
         "[400.0, 400.0, 440.0, 412.0]", "EMBED PL NOTE", "PLAN",
         "PAGE-0", "low", None, None, "t"),
        # A hit on a sheet absent from the PDF: must land on the
        # exception list, never vanish.
        ("J", "L3X3X1/4", "BEAM", "S9.99", "[10.0, 10.0, 20.0, 20.0]",
         "L3X3X1/4", "PLAN", "S9.99 GHOST SHEET", "medium", None,
         None, "t"),
    ]
    c.executemany(
        "INSERT INTO census_hits (job, designation, item_class, sheet,"
        " bbox, raw_text, source_kind, primary_source, confidence,"
        " conflict_group, qty, created_at) VALUES (?,?,?,?,?,?,?,?,?,"
        "?,?,?)", rows)
    c.execute(
        "INSERT INTO conflicts (job, conflict_group, designation,"
        " item_class, schedule_qty, plan_qty, schedule_source,"
        " plan_source, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("J", "J:JST:28K7", "28K7", "JST", 63.0, 60.0, "sched", "plan",
         "CONFLICT: sched 63 EA vs plan callouts 60 EA. RFI "
         "candidate.", "t"))
    c.commit()
    c.close()
    return path


def test_overlay_end_to_end(tmp_path):
    import fitz

    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    info = build_overlay(pdf, "J", db_path=db)

    out = Path(info["out_path"])
    assert out.name == "set_QA.pdf"
    assert info["hits_drawn"] == 3
    assert info["hits_unmapped"] == 1
    assert info["conflicts_listed"] == 1
    assert info["summary_pages"] >= 1

    doc = fitz.open(str(out))
    assert len(doc) == 2  # original page plus the exception page
    page = doc[0]
    annots = list(page.annots())
    rects = [a for a in annots if a.type[1] == "Square"]
    assert len(rects) == 3
    colors = {tuple(round(v, 2) for v in a.colors["stroke"])
              for a in rects}
    assert tuple(round(v, 2) for v in PALETTE["CONFLICT"]) in colors
    assert tuple(round(v, 2) for v in PALETTE["BEAM"]) in colors
    notes = [a.info.get("content", "") for a in rects]
    assert any("confidence: medium" in n for n in notes)
    assert all("—" not in n and "–" not in n for n in notes)

    summary_text = doc[1].get_text()
    assert "QA EXCEPTION LIST - INTERNAL ONLY" in summary_text
    assert "28K7" in summary_text          # the conflict
    assert "EMBED PL" in summary_text      # the low row
    assert "L3X3X1/4" in summary_text      # the unmapped hit
    # Conflicts come first so Ivan works top to bottom.
    assert summary_text.find("28K7") < summary_text.find("EMBED PL")
    doc.close()

    # Independent reader: pdfplumber shares no code with PyMuPDF.
    import pdfplumber
    with pdfplumber.open(str(out)) as alt:
        assert len(alt.pages) == 2
        assert "QA EXCEPTION LIST" in (alt.pages[1].extract_text()
                                       or "")


def test_congestion_catches_straddling_clusters():
    # 22 hits in a half-inch knot centered on the corner of four grid
    # cells: a single fixed grid splits them about 5 per cell and sees
    # nothing. The half-offset grids must flag it.
    def hit(x, y):
        return {"bbox": json.dumps([x, y, x + 2, y + 2])}

    hits = [hit(54.0 + (i % 5) * 7, 54.0 + (i // 5) * 7)
            for i in range(22)]
    zones = _congestion_zones(hits, (0, 0, 720, 720))
    assert zones, "boundary-straddling cluster must be flagged"
    assert max(n for _, n in zones) > CONGESTION_THRESHOLD_PER_SQIN


def test_page_map_flags_duplicate_sheet_numbers():
    router_result = {"sheets": [
        {"sheet_number": "S2.1", "page_index": 0},
        {"sheet_number": "S2.1", "page_index": 1},
        {"sheet_number": "S3.0", "page_index": 2},
    ]}
    mapping, ambiguous = _page_map(None, router_result)
    assert ambiguous == {"S2.1"}
    assert "S2.1" not in mapping  # never silently first-page-wins
    assert mapping["S3.0"] == 2


def test_ambiguous_sheet_hits_route_to_exception_list(tmp_path,
                                                      monkeypatch):
    import fitz

    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    # A router result reporting the same sheet number on two pages:
    # the S9.99 hit must route to the exception list, never first-page.
    monkeypatch.setattr(overlay.sheet_router, "route", lambda p: {
        "sheets": [
            {"sheet_number": "S9.99", "page_index": 0},
            {"sheet_number": "S9.99", "page_index": 1},
        ]})
    info = build_overlay(pdf, "J", db_path=db)
    assert info["hits_ambiguous_sheet"] == 1  # the S9.99 hit
    assert info["ambiguous_sheets"] == ["S9.99"]
    doc = fitz.open(info["out_path"])
    summary = doc[len(doc) - 1].get_text()
    doc.close()
    assert "appears on more than one page" in summary


def test_conflict_note_never_truncated(tmp_path):
    import fitz

    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = tmp_path / "census.db"
    _synthetic_db(db)
    c = sqlite3.connect(str(db))
    long_note = ("CONFLICT: S4.00 FOUNDATION DETAILS BASE PLATE "
                 "SCHEDULE 63 EA vs S3.00 ROOF FRAMING PLAN plan "
                 "callouts 60 EA. RFI candidate. Never resolved "
                 "silently.")
    c.execute("UPDATE conflicts SET note = ?", (long_note,))
    c.commit()
    c.close()
    info = build_overlay(pdf, "J", db_path=db)
    doc = fitz.open(info["out_path"])
    summary = doc[len(doc) - 1].get_text()
    doc.close()
    # Both quantities survive: the comparison is what Ivan adjudicates.
    assert "63 EA" in summary and "60 EA" in summary


def test_cross_check_wording_follows_class_primacy():
    # A schedule row of a plan-primary class (BEAM) is the cross-check,
    # never the count basis; the popup must say so.
    hit = {"designation": "HSS 8x8", "item_class": "BEAM",
           "source_kind": "SCHEDULE", "qty": None,
           "confidence": "high", "primary_source": "BASE PLATE SCHEDULE",
           "conflict_group": None}
    note = _note_text(hit, {})
    assert "cross-check only" in note
    plan_anch = {"designation": "ANCHOR RODS", "item_class": "ANCH",
                 "source_kind": "PLAN", "qty": None,
                 "confidence": "low", "primary_source": "S1.00",
                 "conflict_group": None}
    note2 = _note_text(plan_anch, {("ANCHORRODS", "PLAN"): 3})
    assert "cross-check only" in note2


def test_refuses_overlay_of_an_overlay(tmp_path):
    pdf = _synthetic_pdf(tmp_path / "set_QA.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    with pytest.raises(ValueError, match="already a QA overlay"):
        build_overlay(pdf, "J", db_path=db)


def test_rerun_backs_up_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(overlay, "HANDOFF_ROOT", tmp_path / "_handoff")
    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    first = build_overlay(pdf, "J", db_path=db)
    assert first["previous_backed_up"] == ""
    second = build_overlay(pdf, "J", db_path=db)
    backup = Path(second["previous_backed_up"])
    assert backup.exists() and backup.name == "set_QA.pdf"
    log = (tmp_path / "_handoff" / "changelog.md").read_text(
        encoding="utf-8")
    assert "backed up" in log


def test_census_db_opened_read_only(tmp_path):
    import os
    import stat

    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    os.chmod(db, stat.S_IREAD)
    try:
        info = build_overlay(pdf, "J", db_path=db)
        assert info["hits_drawn"] == 3
    finally:
        os.chmod(db, stat.S_IREAD | stat.S_IWRITE)


def test_overlay_refuses_empty_job(tmp_path):
    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    with pytest.raises(ValueError, match="no hits for job"):
        build_overlay(pdf, "NOPE", db_path=db)


def test_manual_low_rows_join_summary(tmp_path):
    import openpyxl

    pdf = _synthetic_pdf(tmp_path / "set.pdf")
    db = _synthetic_db(tmp_path / "census.db")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TAKEOFF"
    ws.append([])
    ws.append(["item_id", "designation", "mode", "qty", "unit",
               "primary_source", "secondary_source", "confidence",
               "sheet", "bbox", "notes", "lb_per_ft", "weight_lb",
               "tons", "formula_ref"])
    ws.append(["MISC-001", "CAGED LADDER", "COUNT", 1, "EA",
               "plans / details", "", "low", "S5.02", "MANUAL",
               "from Ivan email"])
    xlsx = tmp_path / "takeoff.xlsx"
    wb.save(str(xlsx))

    import fitz
    info = build_overlay(pdf, "J", db_path=db, takeoff_xlsx=xlsx)
    doc = fitz.open(info["out_path"])
    summary_text = doc[1].get_text()
    doc.close()
    assert "CAGED LADDER" in summary_text
    assert "manual-entry row" in summary_text
