"""Tests for the connection-information completeness gate (plan items
2.1, 2.3, 2.4, 2.5, 2.6).

The gate is advisory and structural only. It flags missing or ambiguous
connection information, emits LOW-confidence flags and RFIs, and lists what
must be resolved before pricing. It never sets, changes, or generates a price,
quantity, weight, or rate, and never returns a go/no-go verdict on price.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bridge.connection_completeness import check_connection_completeness
from bridge import auto_rfi


# A fully-resolved set: nothing missing, nothing ambiguous.
COMPLETE = {
    "bracing_present": True,
    "transfer_forces_provided": True,
    "tekla_substituting_axial": False,
    "sdc": "B",
    "r_value": 3,
    "aess_present": False,
    "surface_prep_class": "SP6",
    "stairs_present": True,
    "stairs_bracing_shown": True,
    "building_sf_source": "stated",
    "connection_design": "delegated",
}


def _flag_items(result):
    return {f["item"] for f in result["low_confidence_flags"]}


def _rfi_triggers(result):
    return {i["trigger_key"] for i in (result["rfis"] or {}).get("items", [])}


# -- 2.1 transfer forces ----------------------------------------------------

def test_bracing_without_transfer_forces_flags_and_rfis():
    r = check_connection_completeness({"bracing_present": True,
                                       "transfer_forces_provided": False,
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "transfer_forces" in _flag_items(r)
    assert "missing_transfer_forces" in _rfi_triggers(r)
    assert "transfer_forces" in r["must_resolve_before_pricing"]
    assert r["connection_info_complete"] is False


def test_unbraced_bay_does_not_raise_transfer_force_rfi():
    r = check_connection_completeness({"bracing_present": False,
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "transfer_forces" not in _flag_items(r)


def test_tekla_axial_substitution_is_flagged():
    r = check_connection_completeness({"tekla_substituting_axial": True,
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "axial_substitution" in _flag_items(r)
    assert "axial_substitution" in r["must_resolve_before_pricing"]


# -- 2.3 seismic ------------------------------------------------------------

def test_missing_sdc_raises_seismic_rfi_and_blocks():
    r = check_connection_completeness({"surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "seismic_system" in _flag_items(r)
    assert "seismic_system_unconfirmed" in _rfi_triggers(r)
    assert "seismic_system" in r["must_resolve_before_pricing"]


def test_houston_low_seismic_default_is_complete_on_seismic():
    # SDC B, R=3 stated: no seismic detailing RFI.
    r = check_connection_completeness(COMPLETE)
    assert "seismic_system" not in _flag_items(r)
    assert "seismic_detailing" not in _flag_items(r)


def test_high_seismic_missing_detailing_flags_and_blocks():
    r = check_connection_completeness({"sdc": "D", "r_value": 8,
                                       "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "seismic_detailing" in _flag_items(r)
    assert "seismic_detailing_incomplete" in _rfi_triggers(r)
    # The RFI question lists the specific missing items.
    item = next(i for i in r["rfis"]["items"]
                if i["trigger_key"] == "seismic_detailing_incomplete")
    assert "SFRS" in item["question"]
    assert "demand-critical welds" in item["question"]


def test_high_seismic_with_full_detailing_is_complete():
    r = check_connection_completeness({
        "sdc": "D", "r_value": 8, "sfrs": "SCBF",
        "demand_critical_welds_specified": True,
        "protected_zones_specified": True,
        "prequalified_358_connection": True,
        "bracing_present": True, "transfer_forces_provided": True,
        "surface_prep_class": "SP10", "building_sf_source": "gc_confirmed",
        "connection_design": "delegated",
    })
    assert "seismic_detailing" not in _flag_items(r)


# -- 2.4 AESS ---------------------------------------------------------------

def test_aess_without_category_per_face_flags():
    r = check_connection_completeness({"aess_present": True,
                                       "aess_category_per_face": False,
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "aess_category" in _flag_items(r)
    assert "aess_category_unspecified" in _rfi_triggers(r)
    # AESS escalates labor, not tonnage: not a hard pricing blocker.
    assert "aess_category" not in r["must_resolve_before_pricing"]


# -- 2.5 surface prep + hidden bracing --------------------------------------

def test_missing_surface_prep_flags_low():
    r = check_connection_completeness({"sdc": "B", "building_sf_source": "stated"})
    assert "surface_prep" in _flag_items(r)
    assert "surface_prep_unconfirmed" in _rfi_triggers(r)


def test_present_surface_prep_does_not_flag():
    r = check_connection_completeness(COMPLETE)
    assert "surface_prep" not in _flag_items(r)


def test_hidden_stair_bracing_flags():
    r = check_connection_completeness({"stairs_present": True,
                                       "stairs_bracing_shown": False,
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "hidden_bracing" in _flag_items(r)
    assert "hidden_bracing_not_shown" in _rfi_triggers(r)


# -- 2.6 SF + drawing completeness ------------------------------------------

def test_unconfirmed_sf_blocks():
    r = check_connection_completeness({"sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "assumed"})
    assert "gross_sf" in _flag_items(r)
    assert "sf_gross_area_confirmation" in _rfi_triggers(r)
    assert "gross_sf" in r["must_resolve_before_pricing"]


def test_stated_sf_does_not_block():
    r = check_connection_completeness(COMPLETE)
    assert "gross_sf" not in _flag_items(r)


def test_general_note_connections_refused_and_routed_to_rfi():
    r = check_connection_completeness({"connection_design": "general_note",
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "connection_information" in _flag_items(r)
    assert "connection_general_note_only" in _rfi_triggers(r)
    assert "connection_information" in r["must_resolve_before_pricing"]
    assert r["connection_info_complete"] is False


def test_blanket_full_strength_connections_refused():
    r = check_connection_completeness({"connection_design": "blanket_full_strength",
                                       "sdc": "B", "surface_prep_class": "SP6",
                                       "building_sf_source": "stated"})
    assert "connection_information" in r["must_resolve_before_pricing"]


# -- complete set + contract ------------------------------------------------

def test_complete_set_is_complete_with_no_blockers():
    r = check_connection_completeness(COMPLETE)
    assert r["connection_info_complete"] is True
    assert r["must_resolve_before_pricing"] == []
    assert r["summary"]["rfi_count"] == 0


def test_advisory_contract_and_no_price_verdict():
    r = check_connection_completeness({})
    assert r["advisory"] is True
    assert r["structural_only"] is True
    assert r["generates_numbers"] is False
    assert r["verdict"] is None


def test_never_emits_a_bid_number():
    r = check_connection_completeness({"sdc": "D", "r_value": 8,
                                       "bracing_present": True})
    blob = json.dumps(r)
    assert "$" not in blob
    for token in ('"price"', '"unit_rate"', '"rate"', '"weight"', '"extended"',
                  '"total_bid"', '"amount"'):
        assert token not in blob


def test_rfis_are_well_formed_and_deduped():
    r = check_connection_completeness({})  # empty: several RFIs fire
    payload = r["rfis"]
    assert payload is not None
    for item in payload["items"]:
        ok, err = auto_rfi._validate_rfi(item)
        assert ok, err
    # IDs are gapless after dedupe/resequence.
    ids = [i["id"] for i in payload["items"]]
    assert ids == [auto_rfi.normalize_id(i) for i in range(1, len(ids) + 1)]


# -- Bridge method (GUI + MCP share this) -----------------------------------

def test_bridge_connection_info_check_json():
    from bridge.api import Bridge
    b = Bridge()
    r = b.connection_info_check(context=json.dumps({"bracing_present": True,
                                                    "transfer_forces_provided": False}),
                                project_id="PRJ-2026-TEST-001")
    assert r["ok"] is True and r["success"] is True
    assert "transfer_forces" in {f["item"] for f in r["data"]["low_confidence_flags"]}


def test_bridge_connection_info_check_bad_json():
    from bridge.api import Bridge
    b = Bridge()
    r = b.connection_info_check(context="{nope")
    assert r["ok"] is False
    assert "json" in r["error"].lower()


def test_bridge_takeoff_rows_validate():
    from bridge.api import Bridge
    b = Bridge()
    rows = [{"tag": "W12X26", "description": "beam", "system": "Structural Steel",
             "qty": 12, "unit": "EA", "drawing": "S2.1",
             "method": "stated_schedule", "confidence": "high", "basis": "",
             "notes": ""}]
    r = b.takeoff_rows_validate(rows=json.dumps(rows))
    assert r["ok"] is True
    assert r["data"]["valid"] is True
    assert r["data"]["row_count"] == 1
