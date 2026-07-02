"""Tests for the canonical takeoff/BOQ row schema (plan item 1.3).

The row is Tag, Description, System, Qty, Unit, Drawing, Method, Confidence,
Basis, Notes. Confidence is method-linked. Inferred and vision rows must carry
a written assumption string in Basis. The row is the hub between the count-gap
engine (from_schema_v2_row) and the reconciliation advisory gate
(to_estimate_line). The schema is advisory and structural only: it never
produces a price, quantity, weight, or rate.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bridge import takeoff_row as tr
from bridge.bid_sanity_gates import reconcile_advisory


# -- method-linked confidence ----------------------------------------------

def test_confidence_is_derived_from_method():
    assert tr.confidence_for_method(tr.METHOD_VECTOR_OR_TAG) == "high"
    assert tr.confidence_for_method(tr.METHOD_STATED_SCHEDULE) == "high"
    assert tr.confidence_for_method(tr.METHOD_SCALED_PLAN) == "medium"
    assert tr.confidence_for_method(tr.METHOD_VISION) == "low"
    assert tr.confidence_for_method(tr.METHOD_INFERRED) == "low"


def test_make_row_sets_method_linked_confidence():
    row = tr.make_row("W12X26", "Steel beam", "Structural Steel", 12, "EA",
                      "S2.1", tr.METHOD_STATED_SCHEDULE)
    assert row["confidence"] == "high"
    assert tuple(row.keys()) == tr.TAKEOFF_ROW_FIELDS


def test_make_row_carries_qty_verbatim():
    row = tr.make_row("DECK", "Roof deck", "Deck", 12345, "SF", "S2.1",
                      tr.METHOD_SCALED_PLAN)
    assert row["qty"] == 12345  # carried through, never recomputed


# -- validation -------------------------------------------------------------

def test_valid_row_has_no_errors():
    row = tr.make_row("28K7", "Joist", "Joists", 63, "EA", "S2.1 JOIST SCHED",
                      tr.METHOD_STATED_SCHEDULE)
    errors, warnings = tr.validate_row(row)
    assert errors == []


def test_inferred_row_requires_basis():
    row = tr.make_row("L3X3", "Angle", "Misc Metals", 4, "EA", "S2.1",
                      tr.METHOD_INFERRED, basis="")
    errors, _ = tr.validate_row(row)
    assert any("requires a written assumption" in e for e in errors)
    row2 = tr.make_row("L3X3", "Angle", "Misc Metals", 4, "EA", "S2.1",
                       tr.METHOD_INFERRED,
                       basis="assumed 4 per typical detail 5/S5.0, RFI pending")
    errors2, _ = tr.validate_row(row2)
    assert errors2 == []


def test_vision_row_requires_basis():
    row = tr.make_row("MISC", "Bent plate", "Misc Metals", 2, "EA", "A3.1",
                      tr.METHOD_VISION, basis="")
    errors, _ = tr.validate_row(row)
    assert any("requires a written assumption" in e for e in errors)


def test_missing_required_fields_are_errors():
    errors, _ = tr.validate_row({"tag": "", "qty": None})
    joined = " ".join(errors)
    for f in ("tag", "system", "unit", "drawing", "method", "qty"):
        assert f in joined


def test_bad_method_and_confidence_are_errors():
    row = tr.make_row("X", "d", "Other", 1, "EA", "S1", "guesswork",
                      confidence="probably")
    errors, _ = tr.validate_row(row)
    assert any("method" in e for e in errors)
    assert any("confidence" in e for e in errors)


def test_confidence_method_mismatch_is_a_warning_not_error():
    row = tr.make_row("X", "d", "Other", 1, "EA", "S1",
                      tr.METHOD_STATED_SCHEDULE, confidence="low")
    errors, warnings = tr.validate_row(row)
    assert errors == []
    assert any("does not match method" in w for w in warnings)


def test_validate_rows_summary():
    rows = [
        tr.make_row("W12X26", "beam", "Structural Steel", 1, "EA", "S2.1",
                    tr.METHOD_VECTOR_OR_TAG),
        tr.make_row("L3X3", "angle", "Misc Metals", 1, "EA", "S2.1",
                    tr.METHOD_INFERRED, basis=""),  # error: no basis
    ]
    out = tr.validate_rows(rows)
    assert out["row_count"] == 2
    assert out["valid"] is False
    assert out["error_count"] >= 1
    assert out["fields"] == list(tr.TAKEOFF_ROW_FIELDS)


# -- wiring: count-gap engine -> canonical ----------------------------------

def test_from_schema_v2_row_maps_count_gap_engine_output():
    # The exact row shape grid_geometry._area_row / census emit.
    v2 = {
        "item_class": "DECK",
        "designation": "ROOF DECK",
        "mode": "AREA",
        "qty": 21930,
        "unit": "SF",
        "primary_source": "S2.1 ROOF FRAMING PLAN",
        "secondary_source": "",
        "confidence": "medium",
        "sheet": "S2.1",
        "bbox": "[0,0,1,1]",
        "notes": "grid footprint 200 x 110 ft = 22000 SF (Engine B)",
    }
    row = tr.from_schema_v2_row(v2)
    assert row["tag"] == "ROOF DECK"
    assert row["system"] == "Deck"
    assert row["qty"] == 21930          # carried verbatim
    assert row["unit"] == "SF"
    assert row["drawing"] == "S2.1 ROOF FRAMING PLAN"
    assert row["method"] == tr.METHOD_SCALED_PLAN
    assert row["confidence"] == "medium"
    assert tr.validate_row(row)[0] == []


def test_from_schema_v2_low_row_carries_notes_into_basis():
    v2 = {"item_class": "MISC", "designation": "BENT PL", "mode": "COUNT",
          "qty": 2, "unit": "EA", "primary_source": "A3.1",
          "confidence": "low", "sheet": "A3.1",
          "notes": "vision read, assumed 2 from elevation, RFI"}
    row = tr.from_schema_v2_row(v2)
    assert row["method"] == tr.METHOD_INFERRED
    assert row["basis"]  # populated from notes so the inferred contract holds
    assert tr.validate_row(row)[0] == []


def test_real_grid_geometry_rows_convert_and_validate():
    # Drive the actual count-gap engine row builder with a synthetic
    # measurement (no PDF needed) and convert its output.
    from takeoff_pipeline import grid_geometry
    measurement = {
        "deck": {"area_sf": 21930, "length_ft": 200, "width_ft": 110,
                 "confidence": "medium", "rectangular": True,
                 "primary_source": "S2.1 ROOF FRAMING PLAN", "sheet": "S2.1",
                 "bbox": "[0,0,1,1]", "flags": []},
        "building": None,
    }
    v2_rows = grid_geometry.to_takeoff_rows(measurement)
    assert v2_rows, "engine should emit at least one row"
    for v2 in v2_rows:
        row = tr.from_schema_v2_row(v2)
        assert row["qty"] == v2["qty"]            # verbatim, no recompute
        assert tr.validate_row(row)[0] == []


# -- wiring: canonical -> reconciliation advisory gate ----------------------

def test_to_estimate_line_flows_through_reconcile_advisory():
    rows = [
        tr.make_row("W12X26", "Structural steel framing", "Structural Steel",
                    40, "TON", "S2.1", tr.METHOD_STATED_SCHEDULE),
        tr.make_row("ROOF DECK", "Roof deck supply and install", "Deck",
                    21930, "SF", "S2.1", tr.METHOD_SCALED_PLAN),
    ]
    est = [
        tr.to_estimate_line(rows[0], line_id="L1", requirement_refs=["REQ-1"]),
        tr.to_estimate_line(rows[1], line_id="L2", requirement_refs=["REQ-2"]),
    ]
    register = [
        {"req_id": "REQ-1", "requirement_text": "steel framing", "category": "Direct"},
        {"req_id": "REQ-2", "requirement_text": "roof deck", "category": "Direct"},
    ]
    result = reconcile_advisory(est, register)
    assert result["coverage"]["priceable_total"] == 2
    assert result["coverage"]["coverage_rate"] == 1.0
    assert result["findings"] == []  # everything linked, nothing flagged


def test_estimate_line_shape_matches_what_the_gate_reads():
    row = tr.make_row("28K7", "Open web steel joists", "Joists", 63, "EA",
                      "S2.1", tr.METHOD_STATED_SCHEDULE)
    line = tr.to_estimate_line(row, line_id="L9")
    for k in ("line_id", "description", "category", "unit", "requirement_refs"):
        assert k in line
    assert line["requirement_refs"] == []  # orphan until linked


# -- advisory / no-number contract ------------------------------------------

def test_schema_never_emits_a_bid_number():
    row = tr.make_row("W12X26", "beam", "Structural Steel", 40, "TON", "S2.1",
                      tr.METHOD_STATED_SCHEDULE)
    blob = json.dumps(tr.validate_rows([row]))
    assert "$" not in blob
    for token in ('"price"', '"unit_rate"', '"rate"', '"weight"', '"extended"',
                  '"amount"'):
        assert token not in blob


# -- integer-quantity rule (plan item D2, Owner-approved 2026-07-02) -------

def test_ea_string_qty_is_an_error():
    row = tr.make_row("F10", "Anchor", "Anchors", "2", "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    errors, _ = tr.validate_row(row)
    assert any("never a string" in e for e in errors)


def test_ea_negative_qty_is_an_error():
    row = tr.make_row("F10", "Anchor", "Anchors", -1, "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    errors, _ = tr.validate_row(row)
    assert any("non-negative" in e for e in errors)


def test_ea_whole_float_qty_is_a_warning_not_error():
    row = tr.make_row("F10", "Anchor", "Anchors", 2.0, "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    errors, warnings = tr.validate_row(row)
    assert errors == []
    assert any("whole-number float" in w for w in warnings)


def test_ea_fractional_float_qty_is_an_error():
    row = tr.make_row("F10", "Anchor", "Anchors", 2.5, "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    errors, _ = tr.validate_row(row)
    assert errors


def test_ea_bool_qty_is_an_error():
    row = tr.make_row("F10", "Anchor", "Anchors", True, "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    errors, _ = tr.validate_row(row)
    assert errors


def test_non_ea_float_and_string_qty_stay_verbatim_legal():
    row = tr.make_row("DECK", "Roof deck", "Deck", 12500.5, "SF", "S-201",
                      tr.METHOD_STATED_SCHEDULE)
    assert tr.validate_row(row) == ([], [])


def test_inline_multiplier_in_tag_is_flagged():
    row = tr.make_row("F10 x2", "Anchor", "Anchors", 2, "EA", "S-501",
                      tr.METHOD_STATED_SCHEDULE)
    _, warnings = tr.validate_row(row)
    assert any("inline multiplier" in w for w in warnings)


def test_shape_designation_is_not_flagged_as_multiplier():
    row = tr.make_row("W12X26", "W12X26 beam", "Structural Steel", 4, "EA",
                      "S-201", tr.METHOD_STATED_SCHEDULE)
    _, warnings = tr.validate_row(row)
    assert not any("inline multiplier" in w for w in warnings)
