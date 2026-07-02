"""Tests for the connection take-off / allowance pass (plan item 1.1).

VERIFY-DO-NOT-GENERATE. The pass sizes a ROM connection-material allowance
deterministically: the percentage is read live from Ivan's locked calibration,
the structural tonnage comes from bridge/aisc_validator.py, and the rate from
bridge/bid_rates.py. No number originates in the model. An undeterminable
framing type yields a flag and an RFI, never a silent default.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bridge import connection_takeoff as ct
from bridge import takeoff_row
from bridge.bid_rates import BID_RATES

BLENDED_RATE = BID_RATES["fab_per_ton"] + BID_RATES["erection_per_ton"]  # 4720


def _write_calib(tmp_path, pct_block):
    p = tmp_path / "calib.json"
    p.write_text(json.dumps({
        "connection_allowance_pct_of_structural_tonnage": pct_block
    }), encoding="utf-8")
    return str(p)


# -- percentages are read from the calibration file, never hardcoded ---------

def test_pct_is_read_from_calibration_file_not_hardcoded(tmp_path):
    # A deliberately wrong pct in a temp file must flow through unchanged.
    path = _write_calib(tmp_path, {
        "_format": "ignored metadata",
        "full_moment_frame": {"pct": 99, "confidence": "high"},
    })
    r = ct.connection_takeoff(framing_type="full_moment_frame",
                              structural_tons=100, calibration_path=path)
    assert r["connection_pct"] == 99               # from the file, not the locked 15
    assert r["connection_tons"] == 99.0            # 100 * 99 / 100
    assert r["connection_allowance_cost"] == round(99.0 * BLENDED_RATE, 2)


def test_real_calibration_file_carries_ivans_locked_percentages():
    pcts = ct.load_connection_pcts()  # reads the actual locked Ivan file
    assert pcts["tilt_wall_plus_bar_joists_plus_HSS_framing"]["pct"] == 8
    assert pcts["tilt_wall_plus_WF_beams_plus_bar_joists"]["pct"] == 10
    assert pcts["braced_frame_all_simple"]["pct"] == 8
    assert pcts["moment_frame_perimeter_simple_interior"]["pct"] == 12
    assert pcts["full_moment_frame"]["pct"] == 15
    # Metadata keys are stripped.
    assert not any(k.startswith("_") for k in pcts)


def test_load_pcts_raises_when_calibration_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        ct.load_connection_pcts(str(tmp_path / "nope.json"))


# -- undeterminable framing type -> flag + RFI, never a silent default -------

def test_empty_framing_type_flags_and_rfis_no_number():
    r = ct.connection_takeoff(framing_type="", structural_tons=100)
    assert r["framing_type_determinable"] is False
    assert r["connection_pct"] is None
    assert r["connection_tons"] is None
    assert r["connection_allowance_cost"] is None
    assert r["takeoff_rows"] == []
    items = {f["item"] for f in r["low_confidence_flags"]}
    assert "framing_type" in items
    triggers = {i["trigger_key"] for i in (r["rfis"] or {}).get("items", [])}
    assert "connection_framing_type_undetermined" in triggers


def test_unknown_framing_type_flags_and_rfis_no_number():
    r = ct.connection_takeoff(framing_type="exotic_space_frame", structural_tons=100)
    assert r["framing_type_determinable"] is False
    assert r["connection_tons"] is None
    assert "connection_framing_type_undetermined" in {
        i["trigger_key"] for i in (r["rfis"] or {}).get("items", [])}


# -- tonnage comes from aisc_validator only ---------------------------------

def test_tonnage_sourced_from_aisc_validator_members_path():
    # W12X26 at 26 lb/ft: 10 x 30 ft x 26 / 2000 = 3.9 tons (validator math).
    members = [{"shape": "W12X26", "qty": 10, "length_ft": 30}]
    r = ct.connection_takeoff(framing_type="braced_frame_all_simple",
                              members=members)
    assert r["structural_tons"] == pytest.approx(3.9)
    assert "aisc_validator.py" in r["tonnage_source"]
    assert r["connection_pct"] == 8
    assert r["connection_tons"] == pytest.approx(0.312)   # 3.9 * 8 / 100


def test_invalid_member_shapes_are_flagged_not_silently_priced():
    members = [{"shape": "W12X26", "qty": 10, "length_ft": 30},
               {"shape": "W14X81", "qty": 1, "length_ft": 10}]  # hallucinated
    r = ct.connection_takeoff(framing_type="braced_frame_all_simple",
                              members=members)
    assert "structural_tonnage" in {f["item"] for f in r["low_confidence_flags"]}


def test_zero_tonnage_flags_and_computes_no_number():
    r = ct.connection_takeoff(framing_type="full_moment_frame", structural_tons=0)
    assert r["connection_tons"] is None
    assert "structural_tonnage" in {f["item"] for f in r["low_confidence_flags"]}


# -- rate comes from bid_rates only; math is deterministic -------------------

def test_rate_is_locked_fab_plus_erection():
    r = ct.connection_takeoff(framing_type="full_moment_frame", structural_tons=100)
    assert r["rate_per_ton"] == BLENDED_RATE
    assert "bid_rates.py" in r["rate_source"]


def test_allowance_math_is_deterministic():
    r = ct.connection_takeoff(framing_type="full_moment_frame", structural_tons=100)
    assert r["connection_pct"] == 15
    assert r["connection_tons"] == 15.0                 # 100 * 15 / 100
    assert r["connection_allowance_cost"] == round(15.0 * BLENDED_RATE, 2)  # 70800


# -- emits a Connections-bucket canonical takeoff row ------------------------

def test_emits_connections_bucket_canonical_row():
    r = ct.connection_takeoff(framing_type="full_moment_frame", structural_tons=100,
                              drawing="S2.1")
    assert len(r["takeoff_rows"]) == 1
    row = r["takeoff_rows"][0]
    assert row["system"] == "Connections"
    assert row["unit"] == "TON"
    assert row["qty"] == 15.0
    assert row["method"] == takeoff_row.METHOD_INFERRED
    assert row["confidence"] == "low"            # ROM allowance, method-linked
    assert "ROM" in row["basis"] and "15" in row["basis"]
    assert "ivan_confirmed_2026Q2.json" in row["basis"]
    assert "bid_rates.py" in row["basis"]
    # The row is schema-valid (Connections is a first-class system, no warning).
    errors, warnings = takeoff_row.validate_row(row)
    assert errors == []
    assert not any("system" in w for w in warnings)


# -- provenance / no-number-origination contract ----------------------------

def test_every_number_is_sourced_not_originated():
    r = ct.connection_takeoff(framing_type="full_moment_frame", structural_tons=100)
    assert r["advisory"] is True
    assert r["generates_numbers"] is False
    assert r["verdict"] is None
    assert r["rom"] is True
    assert "ivan_confirmed_2026Q2.json" in r["pct_source"]
    assert "bid_rates.py" in r["rate_source"]
    assert "ROM allowance" in r["disclaimer"]


# -- Bridge method (GUI + MCP share this) -----------------------------------

def test_bridge_connection_takeoff_pass_tons():
    from bridge.api import Bridge
    b = Bridge()
    r = b.connection_takeoff_pass(framing_type="full_moment_frame",
                                  structural_tons="100")
    assert r["ok"] is True and r["success"] is True
    assert r["data"]["connection_pct"] == 15
    assert r["data"]["connection_tons"] == 15.0


def test_bridge_connection_takeoff_pass_members():
    from bridge.api import Bridge
    b = Bridge()
    members = json.dumps([{"shape": "W12X26", "qty": 10, "length_ft": 30}])
    r = b.connection_takeoff_pass(framing_type="braced_frame_all_simple",
                                  members=members)
    assert r["ok"] is True
    assert r["data"]["structural_tons"] == pytest.approx(3.9)
    assert "aisc_validator.py" in r["data"]["tonnage_source"]


def test_bridge_undetermined_framing_returns_flag_not_number():
    from bridge.api import Bridge
    b = Bridge()
    r = b.connection_takeoff_pass(framing_type="", structural_tons="100")
    assert r["ok"] is True
    assert r["data"]["framing_type_determinable"] is False
    assert r["data"]["connection_tons"] is None


def test_bridge_bad_members_json_errors():
    from bridge.api import Bridge
    b = Bridge()
    r = b.connection_takeoff_pass(framing_type="full_moment_frame", members="{bad")
    assert r["ok"] is False
    assert "json" in r["error"].lower()
