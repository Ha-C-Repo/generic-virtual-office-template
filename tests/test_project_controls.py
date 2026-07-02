"""Tests for bridge/project_controls.py (PC4 + PC5, Prompt 12).

All expected values are hand-computed from the fixture data so the
earned value arithmetic is verified, not trusted. Fixtures build a
temp PC1 baseline xlsx and a temp PC3 progress_log SQLite db; the
real data/ stores are never touched.
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bridge.project_controls import (
    CLIENT_CAUSE_NOTE,
    PC6_HIERARCHY,
    _control_status,
    _line_metrics,
    _rollup,
    forecast_to_complete,
    spi_cpi,
    variance_by_cost_code,
)

AS_OF = "2026-05-11"

WBS_HEADER = ["WBS Line", "Scope", "Cost Code", "Progress Type",
              "Planned Units", "Unit", "Planned Hours", "Budget Cost",
              "Start", "End", "Schedule Activity", "Quality Check",
              "Risk Note"]

WBS_ROWS = [
    # FAB-S1: planned_pct 10/20 = 0.5, PV 187500. 40 of 100 tons done,
    # EV 150000. 450 hr at 375/hr, AC 168750. SPI 0.8, CPI 0.889.
    ["FAB-S1", "Fab sequence 1", "fab", "production", 100, "tons",
     1000, 375000, date(2026, 5, 1), date(2026, 5, 21), "FAB1", "weld QC",
     ""],
    # SD-01: milestone, credit reaches 75 -> EV 15000. 100 hr at 100/hr,
    # AC 10000. planned_pct 1.0 (as_of = end), PV 20000. SPI 0.75,
    # CPI 1.5. Client-caused via CLIENT tag.
    ["SD-01", "Shop drawings", "shop drawings", "milestone", "", "",
     200, 20000, date(2026, 5, 1), date(2026, 5, 11), "SD", "checker",
     ""],
    # ERECT-S1: planned_pct 7/20 = 0.35, PV 27160. 28 of 80 tons,
    # EV 27160. 150 hr at 129.3333/hr, AC 19400. SPI 1.0, CPI 1.4.
    ["ERECT-S1", "Erection sequence 1", "erection", "production", 80,
     "tons", 600, 77600, date(2026, 5, 4), date(2026, 5, 24), "ER1",
     "plumb survey", ""],
    # DECK-R1: planned units and dates missing -> low confidence data flag.
    ["DECK-R1", "Roof deck", "roof deck", "production", "", "SF",
     200, 30000, "", "", "DECK", "", ""],
]

PROGRESS_ROWS = [
    ("2026-05-05", "Mario", "FAB-S1", 200, 0, 20, ""),
    ("2026-05-10", "Mario", "FAB-S1", 250, 0, 20, ""),
    ("2026-05-03", "Joseph", "SD-01", 40, 20, 0, ""),
    ("2026-05-09", "Joseph", "SD-01", 60, 75, 0,
     "CLIENT: GC revised anchor layout"),
    ("2026-05-06", "Mario", "ERECT-S1", 70, 0, 10, ""),
    ("2026-05-10", "Mario", "ERECT-S1", 80, 0, 18, ""),
    # Row after as_of: must be excluded from every metric at AS_OF.
    ("2026-05-15", "Mario", "FAB-S1", 500, 0, 50, ""),
]


def _write_baseline(path: Path, flag_text="BASELINE", wbs_rows=None) -> Path:
    import openpyxl
    wb = openpyxl.Workbook()
    budget = wb.active
    budget.title = "Budget"
    budget.append(["Asian City Plaza cost baseline"])
    if flag_text:
        budget.append([flag_text, date(2026, 5, 1)])
    budget.append(["fab", 375000])
    wbs = wb.create_sheet("WBS")
    wbs.append(WBS_HEADER)
    for row in (WBS_ROWS if wbs_rows is None else wbs_rows):
        wbs.append(row)
    wb.save(str(path))
    return path


def _write_progress(path: Path, rows=None) -> Path:
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE progress_log (date TEXT, person TEXT, "
              "wbs_line TEXT, hours REAL, pieces_done REAL, "
              "tons_done REAL, issues_text TEXT)")
    c.executemany("INSERT INTO progress_log VALUES (?,?,?,?,?,?,?)",
                  PROGRESS_ROWS if rows is None else rows)
    c.commit()
    c.close()
    return path


@pytest.fixture
def sources(tmp_path):
    return {
        "baseline_path": _write_baseline(tmp_path / "budget_baseline.xlsx"),
        "db_path": _write_progress(tmp_path / "shop_floor.db"),
    }


def _by_line(result):
    return {m["wbs_line"]: m for m in result["lines"]}


def test_spi_cpi_math(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    assert "error" not in r
    lines = _by_line(r)

    fab = lines["FAB-S1"]
    assert fab["pv"] == 187500.0
    assert fab["ev"] == 150000.0
    assert fab["ac"] == 168750.0
    assert fab["spi"] == 0.8
    assert fab["cpi"] == 0.889
    assert fab["flagged"] is True
    assert fab["confidence"] == "high"

    erect = lines["ERECT-S1"]
    assert erect["pv"] == 27160.0
    assert erect["ev"] == 27160.0
    assert erect["spi"] == 1.0
    assert erect["cpi"] == 1.4
    assert erect["flagged"] is False

    # Project rollup sums only computable lines.
    proj = r["project"]
    assert proj["pv"] == 187500.0 + 20000.0 + 27160.0
    assert proj["ev"] == 150000.0 + 15000.0 + 27160.0
    assert proj["ac"] == 168750.0 + 10000.0 + 19400.0
    assert r["classification"] == "CONFIDENTIAL - INTERNAL"


def test_milestone_rule_of_credit(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    sd = _by_line(r)["SD-01"]
    assert sd["pct_complete"] == 0.75
    assert sd["ev"] == 15000.0
    assert sd["ac"] == 10000.0
    assert sd["spi"] == 0.75
    assert sd["cpi"] == 1.5
    assert sd["flagged"] is True
    assert sd["client_caused"] is True


def test_rows_after_as_of_excluded(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    fab = _by_line(r)["FAB-S1"]
    # The 2026-05-15 row (500 hr, 50 tons) must not be counted at AS_OF.
    assert fab["actual_hours"] == 450.0
    assert fab["units_done"] == 40.0


def test_low_confidence_data_flag(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    deck = _by_line(r)["DECK-R1"]
    assert deck["confidence"] == "low"
    data_flags = [f for f in r["flags"] if f["type"] == "data"]
    assert any(f["wbs_line"] == "DECK-R1" for f in data_flags)


def test_flags_carry_pc6_and_client_note(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    flags = {f["wbs_line"]: f for f in r["flags"]}
    assert PC6_HIERARCHY in flags["FAB-S1"]["notes"]
    assert CLIENT_CAUSE_NOTE not in flags["FAB-S1"]["notes"]
    assert CLIENT_CAUSE_NOTE in flags["SD-01"]["notes"]
    assert "SPI 0.8 below 0.95" in flags["FAB-S1"]["reason"]


def test_flag_threshold_is_strictly_below():
    line = {"wbs_line": "X-1", "scope": "", "cost_code": "fab",
            "progress_type": "production", "planned_units": 100.0,
            "unit": "tons", "planned_hours": 100.0, "budget_cost": 1000.0,
            "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 21),
            "schedule_activity": "", "quality_check": "", "risk_note": ""}
    rows = [{"date": date(2026, 5, 10), "person": "", "wbs_line": "X-1",
             "hours": 47.5, "pieces_done": 0.0, "tons_done": 47.5,
             "issues_text": ""}]
    m = _line_metrics(line, rows, date(2026, 5, 11))
    assert m["spi"] == 0.95
    assert m["cpi"] == 1.0
    assert m["flagged"] is False


def test_forecast_to_complete(sources):
    r = forecast_to_complete("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    assert "error" not in r
    proj = r["project"]
    # EAC per line from the raw EV/AC ratio (EAC = BAC * AC / EV), not the
    # display-rounded CPI: 375000*168750/150000 = 421875.00,
    # 20000*10000/15000 = 13333.33, 77600*19400/27160 = 55428.57,
    # plus DECK-R1 held at BAC 30000. Total 520636.90.
    assert proj["bac"] == 502600.0
    assert proj["eac"] == 520636.90
    # (520636.90 - 502600) / 502600 * 100 = 3.5887 -> 3.59
    assert proj["forecast_variance_pct"] == 3.59
    assert proj["status"] == "WITHIN LIMITS"
    assert proj["control_limits"]["low_pct"] == -1.7
    assert proj["control_limits"]["high_pct"] == 7.3
    fab = next(l for l in r["lines"] if l["wbs_line"] == "FAB-S1")
    assert fab["eac"] == 421875.0
    deck = next(l for l in r["lines"] if l["wbs_line"] == "DECK-R1")
    assert deck["eac"] == 30000
    assert deck["confidence"] == "low"


def test_section_07_control_limits():
    assert _control_status(0.0) == "WITHIN LIMITS"
    assert _control_status(-1.7) == "WITHIN LIMITS"
    assert _control_status(7.3) == "WITHIN LIMITS"
    assert _control_status(-1.71) == "INVESTIGATE"
    assert _control_status(7.31) == "INVESTIGATE"
    assert _control_status(-25.0) == "INVESTIGATE"


def test_variance_by_cost_code(sources):
    r = variance_by_cost_code("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    assert "error" not in r
    codes = {c["cost_code"]: c for c in r["codes"]}
    fab = codes["fab"]
    assert fab["schedule_variance"] == -37500.0
    assert fab["cost_variance"] == -18750.0
    assert fab["flagged"] is True
    assert PC6_HIERARCHY in fab["notes"]
    sd = codes["shop drawings"]
    assert sd["client_caused"] is True
    assert CLIENT_CAUSE_NOTE in sd["notes"]
    erect = codes["erection"]
    assert erect["flagged"] is False
    assert erect["notes"] == []


def test_scurve_series(sources):
    r = spi_cpi("PRJ-2026-ACP-001", as_of=AS_OF, **sources)
    s = r["scurve"]
    assert s, "scurve series should not be empty"
    planned = [p["planned"] for p in s]
    assert planned == sorted(planned), "planned curve must be cumulative"
    # Dated lines total 375000 + 20000 + 77600.
    assert planned[-1] == pytest.approx(472600.0, abs=0.05)
    future = [p for p in s if p["week_ending"] > AS_OF]
    assert future and all(p["earned"] is None and p["actual"] is None
                          for p in future)


def test_unfrozen_baseline_is_rejected(tmp_path, sources):
    unfrozen = _write_baseline(tmp_path / "draft.xlsx", flag_text=None)
    r = spi_cpi("PRJ-2026-ACP-001", baseline_path=unfrozen,
                db_path=sources["db_path"], as_of=AS_OF)
    assert "error" in r
    assert "BASELINE" in r["error"]
    assert "P14" in r["fix"]


def test_baseline_label_word_does_not_freeze(tmp_path, sources):
    # P14 fail-closed: a "Baseline Hours" column label is not a flag cell.
    draft = _write_baseline(tmp_path / "label.xlsx",
                            flag_text="Baseline Hours")
    r = spi_cpi("PRJ-2026-ACP-001", baseline_path=draft,
                db_path=sources["db_path"], as_of=AS_OF)
    assert "error" in r


def test_baseline_frozen_with_date_accepted(tmp_path, sources):
    frozen = _write_baseline(tmp_path / "frozen.xlsx",
                             flag_text="BASELINE frozen 2026-05-01")
    r = spi_cpi("PRJ-2026-ACP-001", baseline_path=frozen,
                db_path=sources["db_path"], as_of=AS_OF)
    assert "error" not in r


def test_missing_progress_table(tmp_path, sources):
    empty_db = tmp_path / "empty.db"
    sqlite3.connect(str(empty_db)).close()
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"],
                db_path=empty_db, as_of=AS_OF)
    assert "error" in r
    assert "progress_log" in r["error"]
    assert "PC3" in r["fix"]


def test_blank_project_id(sources):
    r = spi_cpi("", as_of=AS_OF, **sources)
    assert "error" in r


def test_unknown_wbs_rows_warn(tmp_path, sources):
    rows = list(PROGRESS_ROWS) + [
        ("2026-05-08", "Mario", "GHOST-9", 10, 0, 1, "")]
    db = _write_progress(tmp_path / "ghost.db", rows)
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"],
                db_path=db, as_of=AS_OF)
    assert any("GHOST-9" in w for w in r["warnings"])


def test_rollup_matched_pairs_exclude_partial_lines():
    # A line with EV but no AC must not inflate the project CPI: its
    # earned value would enter the numerator with nothing opposite.
    a = {"wbs_line": "A", "budget_cost": 100000.0, "pv": 50000.0,
         "ev": 40000.0, "ac": 60000.0}
    b = {"wbs_line": "B", "budget_cost": 200000.0, "pv": None,
         "ev": 180000.0, "ac": None}
    roll = _rollup([a, b])
    assert roll["cpi"] == 0.667
    assert roll["spi"] == 0.8
    assert roll["excluded_from_spi"] == ["B"]
    assert roll["excluded_from_cpi"] == ["B"]


def test_rollup_excludes_units_without_hours():
    # EV earned against zero recorded hours is missing data, not free
    # work; the line must not enter the CPI denominator as a zero.
    a = {"wbs_line": "A", "budget_cost": 100000.0, "pv": 50000.0,
         "ev": 40000.0, "ac": 60000.0}
    b = {"wbs_line": "B", "budget_cost": 200000.0, "pv": 100000.0,
         "ev": 180000.0, "ac": 0.0}
    roll = _rollup([a, b])
    assert roll["cpi"] == 0.667
    assert roll["excluded_from_cpi"] == ["B"]
    # SPI keeps B: pv 0 vs ev is real schedule data, both present here.
    assert roll["spi"] == round(220000 / 150000, 3)


def _write_progress_with_project(path: Path, rows) -> Path:
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE progress_log (date TEXT, person TEXT, "
              "wbs_line TEXT, hours REAL, pieces_done REAL, "
              "tons_done REAL, issues_text TEXT, project TEXT)")
    c.executemany("INSERT INTO progress_log VALUES (?,?,?,?,?,?,?,?)",
                  rows)
    c.commit()
    c.close()
    return path


def test_project_filter_exact_match_only(tmp_path, sources):
    db = _write_progress_with_project(tmp_path / "multi.db", [
        ("2026-05-05", "Mario", "FAB-S1", 100, 0, 10, "",
         "PRJ-2026-ACP-001"),
        # Near-miss code: substring of/superset of the queried id.
        ("2026-05-05", "Mario", "FAB-S1", 999, 0, 99, "",
         "PRJ-2026-ACP-0012"),
        # Unattributed row: must be excluded, not double-counted.
        ("2026-05-06", "Mario", "FAB-S1", 55, 0, 5, "", None),
    ])
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"], db_path=db,
                as_of=AS_OF)
    fab = _by_line(r)["FAB-S1"]
    assert fab["actual_hours"] == 100.0
    assert fab["units_done"] == 10.0
    assert any("no project attribution" in w for w in r["warnings"])


def test_project_filter_mismatch_warns(tmp_path, sources):
    db = _write_progress_with_project(tmp_path / "othername.db", [
        ("2026-05-05", "Mario", "FAB-S1", 100, 0, 10, "",
         "Asian City Plaza"),
    ])
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"], db_path=db,
                as_of=AS_OF)
    assert _by_line(r)["FAB-S1"]["actual_hours"] == 0.0
    assert any("none match project" in w for w in r["warnings"])


def test_undated_rows_excluded(tmp_path, sources):
    rows = list(PROGRESS_ROWS) + [(None, "Mario", "FAB-S1", 77, 0, 7, "")]
    db = _write_progress(tmp_path / "undated.db", rows)
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"], db_path=db,
                as_of=AS_OF)
    fab = _by_line(r)["FAB-S1"]
    assert fab["actual_hours"] == 450.0
    assert fab["units_done"] == 40.0
    assert fab["confidence"] == "medium"
    assert any("no parseable date" in i for i in fab["issues"])


def test_forecast_zero_earned_line_excluded(tmp_path, sources):
    # GHOST-HRS burns 100 hours with zero units: EAC = BAC / 0 is
    # undefined and holding it at BAC would hide the worst case.
    rows = [
        ("2026-05-05", "Mario", "FAB-S1", 200, 0, 20, ""),
        ("2026-05-10", "Mario", "FAB-S1", 250, 0, 20, ""),
        ("2026-05-06", "Mario", "GHOST-HRS", 100, 0, 0, ""),
    ]
    wbs = [
        WBS_ROWS[0],
        ["GHOST-HRS", "Stalled line", "fab", "production", 50, "tons",
         500, 50000, date(2026, 5, 1), date(2026, 5, 21), "", "", ""],
    ]
    baseline = _write_baseline(tmp_path / "ghost.xlsx", wbs_rows=wbs)
    db = _write_progress(tmp_path / "ghost.db", rows)
    r = forecast_to_complete("PRJ-2026-ACP-001", baseline_path=baseline,
                             db_path=db, as_of=AS_OF)
    ghost = next(l for l in r["lines"] if l["wbs_line"] == "GHOST-HRS")
    assert ghost["eac"] is None
    assert "zero earned value" in ghost["note"]
    # Project forecast covers only FAB-S1; the exclusion is named.
    assert r["project"]["bac"] == 375000.0
    assert r["project"]["eac"] == 421875.0
    assert any("excludes lines" in w and "GHOST-HRS" in w
               for w in r["warnings"])


def test_scurve_earned_capped_at_line_budget(tmp_path, sources):
    # 200 extra tons against a 100-ton line: the earned curve must cap at
    # the line budget, agreeing with the capped line EV.
    rows = list(PROGRESS_ROWS) + [
        ("2026-05-08", "Mario", "FAB-S1", 0, 0, 200, "")]
    db = _write_progress(tmp_path / "overrun.db", rows)
    r = spi_cpi("PRJ-2026-ACP-001",
                baseline_path=sources["baseline_path"], db_path=db,
                as_of=AS_OF)
    earned = [p["earned"] for p in r["scurve"] if p["earned"] is not None]
    # FAB-S1 capped at 375000 plus SD-01 15000 plus ERECT-S1 27160.
    assert max(earned) == pytest.approx(417160.0, abs=0.05)


def test_placeholder_dates_ignored(tmp_path, sources):
    wbs = [
        WBS_ROWS[0],
        ["FOREVER-1", "Placeholder dates", "misc", "production", 10,
         "tons", 100, 10000, date(2026, 5, 1), date(9999, 12, 31), "",
         "", ""],
    ]
    baseline = _write_baseline(tmp_path / "placeholder.xlsx", wbs_rows=wbs)
    r = spi_cpi("PRJ-2026-ACP-001", baseline_path=baseline,
                db_path=sources["db_path"], as_of=AS_OF)
    forever = _by_line(r)["FOREVER-1"]
    assert forever["planned_pct"] is None
    assert any("placeholder" in w for w in r["warnings"])


def test_client_tag_is_explicit():
    base = {"wbs_line": "X-1", "scope": "", "cost_code": "fab",
            "progress_type": "production", "planned_units": 10.0,
            "unit": "tons", "planned_hours": 10.0, "budget_cost": 100.0,
            "start_date": date(2026, 5, 1), "end_date": date(2026, 5, 21),
            "schedule_activity": "", "quality_check": "", "risk_note": ""}
    row = {"date": date(2026, 5, 5), "person": "", "wbs_line": "X-1",
           "hours": 1.0, "pieces_done": 0.0, "tons_done": 1.0,
           "issues_text": "client asked about paint color"}
    m = _line_metrics(base, [row], date(2026, 5, 11))
    assert m["client_caused"] is False
    row2 = dict(row, issues_text="delay was client-caused per GC email")
    m2 = _line_metrics(base, [row2], date(2026, 5, 11))
    assert m2["client_caused"] is True
