"""Tests for the reconciliation advisory gate (plan item 1.2).

The gate diffs a finished estimate against a requirements-and-exclusions
register and reports a coverage rate plus named gaps. It is advisory and
read-only: it must never produce, set, or change a price, quantity, weight,
or rate, and never return a go/no-go verdict on price. These tests pin that
contract and the deterministic identity matching.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bridge.bid_sanity_gates import reconcile_advisory


# A register in the skill-doc shape: four priceable requirements and one
# excluded requirement.
REGISTER = [
    {"req_id": "REQ-0001", "requirement_text": "Structural steel framing per S2.1",
     "category": "Direct", "status": "Gap", "source_doc": "Scope.pdf", "source_page": 3},
    {"req_id": "REQ-0002", "requirement_text": "Roof deck supply and install",
     "category": "Direct", "status": "Gap"},
    {"req_id": "REQ-0003", "requirement_text": "Open web steel joists",
     "category": "Direct", "status": "Gap"},
    {"req_id": "REQ-0004", "requirement_text": "Anchor bolts, F1554 Gr 55",
     "category": "Direct", "status": "Gap"},
    {"req_id": "REQ-0050", "requirement_text": "Electrical conduit and wiring",
     "category": "Excluded", "status": "ExcludedByDesign"},
]

# An estimate that covers REQ-0001 (twice: a double link), covers REQ-0002,
# prices an excluded requirement (REQ-0050), leaves REQ-0003 and REQ-0004
# unpriced, and carries one orphan line.
ESTIMATE = [
    {"line_id": "LINE-0001", "description": "Structural steel fabrication",
     "category": "Direct", "unit": "TON", "requirement_refs": ["REQ-0001"]},
    {"line_id": "LINE-0002", "description": "Structural steel erection",
     "category": "Direct", "unit": "TON", "requirement_refs": ["REQ-0001"]},
    {"line_id": "LINE-0003", "description": "Roof deck supply and install",
     "category": "Direct", "unit": "SF", "requirement_refs": ["REQ-0002"]},
    {"line_id": "LINE-0004", "description": "Electrical conduit and wiring",
     "category": "Direct", "unit": "LS", "requirement_refs": ["REQ-0050"]},
    {"line_id": "LINE-0005", "description": "Temporary site fencing",
     "category": "Direct", "unit": "LS", "requirement_refs": []},
]


def _by_type(result, t):
    return [f for f in result["findings"] if f["type"] == t]


# -- coverage ---------------------------------------------------------------

def test_coverage_rate_counts_only_linked_priceable():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    # Four priceable requirements; REQ-0001 and REQ-0002 are linked.
    assert r["coverage"]["priceable_total"] == 4
    assert r["coverage"]["linked_matched"] == 2
    assert r["coverage"]["coverage_rate"] == 0.5


def test_coverage_rate_is_none_when_no_priceable_requirements():
    only_excluded = [{"req_id": "REQ-0050", "requirement_text": "MEP",
                      "category": "Excluded"}]
    r = reconcile_advisory(ESTIMATE, only_excluded)
    assert r["coverage"]["priceable_total"] == 0
    assert r["coverage"]["coverage_rate"] is None


# -- named gaps -------------------------------------------------------------

def test_unpriced_requirements_named():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    unpriced = _by_type(r, "UNPRICED_REQUIREMENT")
    ids = {f["req_id"] for f in unpriced}
    assert ids == {"REQ-0003", "REQ-0004"}
    # Excluded requirement is not reported as an unpriced gap.
    assert "REQ-0050" not in ids
    for f in unpriced:
        assert f["confidence"] == "medium"
        assert f["needs_judgment"] is True


def test_excluded_but_priced_is_high_confidence():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    ex = _by_type(r, "EXCLUDED_BUT_PRICED")
    assert len(ex) == 1
    assert ex[0]["req_id"] == "REQ-0050"
    assert ex[0]["line_ids"] == ["LINE-0004"]
    assert ex[0]["confidence"] == "high"
    assert ex[0]["needs_judgment"] is False


def test_double_link_double_count_candidate():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    dl = _by_type(r, "DOUBLE_LINK")
    assert len(dl) == 1
    assert dl[0]["req_id"] == "REQ-0001"
    assert dl[0]["line_ids"] == ["LINE-0001", "LINE-0002"]
    assert dl[0]["confidence"] == "medium"


def test_duplicate_line_double_count_candidate():
    est = [
        {"line_id": "LINE-A", "description": "Roof deck supply and install",
         "category": "Direct", "unit": "SF", "requirement_refs": []},
        {"line_id": "LINE-B", "description": "Roof  deck   supply and install",
         "category": "Direct", "unit": "SF", "requirement_refs": []},
    ]
    r = reconcile_advisory(est, [])
    dup = _by_type(r, "DUPLICATE_LINE")
    assert len(dup) == 1
    assert sorted(dup[0]["line_ids"]) == ["LINE-A", "LINE-B"]
    assert dup[0]["confidence"] == "medium"


def test_orphan_line_named():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    orphans = _by_type(r, "ORPHAN_LINE")
    ids = {f["line_id"] for f in orphans}
    # LINE-0005 has no refs and nothing links to it.
    assert "LINE-0005" in ids
    # LINE-0004 links to the excluded requirement, so it is not an orphan.
    assert "LINE-0004" not in ids


def test_summary_counts_match_findings():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    s = r["summary"]
    assert s["unpriced_count"] == 2
    assert s["excluded_but_priced_count"] == 1
    assert s["double_count_candidates"] == 1  # one DOUBLE_LINK, no duplicate lines
    assert s["orphan_count"] == 1
    assert s["needs_judgment_count"] == sum(
        1 for f in r["findings"] if f.get("needs_judgment"))


# -- the advisory, read-only contract ---------------------------------------

def test_advisory_contract_flags():
    r = reconcile_advisory(ESTIMATE, REGISTER)
    assert r["advisory"] is True
    assert r["generates_numbers"] is False
    assert r["verdict"] is None
    assert "does not set or change any price" in r["disclaimer"].lower()


def test_never_emits_a_bid_number():
    # Feed an estimate line carrying real money and quantity values. None of
    # those values, and no dollar sign, may appear in the advisory payload.
    # The only numbers it emits are diagnostic counts and a coverage ratio.
    est = [{"line_id": "L1", "description": "Structural steel fabrication",
            "category": "Direct", "unit": "TON", "qty": 65.0,
            "unit_rate": 3750.0, "extended": 243750.0,
            "requirement_refs": ["REQ-0001"]}]
    reg = [{"req_id": "REQ-0001", "requirement_text": "steel framing",
            "category": "Direct"}]
    blob = json.dumps(reconcile_advisory(est, reg))
    assert "$" not in blob
    for leaked in ("3750", "243750", "65.0"):
        assert leaked not in blob, f"advisory payload leaked the value {leaked}"
    # The money and quantity field keys are never echoed into the output.
    for key in ('"unit_rate"', '"extended"', '"qty"', '"unit_price"',
                '"amount"', '"total_bid"'):
        assert key not in blob, f"advisory payload echoed the field {key}"


def test_inputs_are_not_mutated():
    est = copy.deepcopy(ESTIMATE)
    reg = copy.deepcopy(REGISTER)
    reconcile_advisory(est, reg)
    assert est == ESTIMATE
    assert reg == REGISTER


# -- robustness -------------------------------------------------------------

def test_empty_inputs_are_safe():
    r = reconcile_advisory([], [])
    assert r["coverage"]["coverage_rate"] is None
    assert r["findings"] == []
    assert r["advisory"] is True


def test_none_inputs_are_safe():
    r = reconcile_advisory(None, None)
    assert r["summary"]["estimate_line_count"] == 0
    assert r["summary"]["register_row_count"] == 0


def test_emitter_shape_register_is_accepted():
    # bridge/requirements_register.py emitter shape: id/description/category.
    reg = [
        {"id": "REQ-001", "description": "Structural steel framing",
         "category": "STRUCTURAL_STEEL", "confidence": "EXPLICIT",
         "source_citations": [{"file": "S2.1.pdf", "page": 1}]},
    ]
    est = [{"line_id": "L1", "description": "steel", "category": "Direct",
            "unit": "TON", "requirement_refs": ["REQ-001"]}]
    r = reconcile_advisory(est, reg)
    assert r["coverage"]["priceable_total"] == 1
    assert r["coverage"]["linked_matched"] == 1


def test_malformed_rows_are_skipped_not_fatal():
    est = [None, "junk", {"line_id": "L1", "description": "steel",
                          "requirement_refs": ["REQ-0001"]}]
    reg = [None, 42, {"req_id": "REQ-0001", "requirement_text": "steel",
                      "category": "Direct"}]
    r = reconcile_advisory(est, reg)
    assert r["summary"]["estimate_line_count"] == 1
    assert r["summary"]["register_row_count"] == 1


# -- Bridge method wiring (GUI + MCP share this) ----------------------------

def test_bridge_method_parses_json_strings():
    from bridge.api import Bridge
    b = Bridge()
    r = b.bid_reconciliation_check(estimate=json.dumps(ESTIMATE),
                                   register=json.dumps(REGISTER))
    assert r["ok"] is True and r["success"] is True
    data = r["data"]
    assert data["advisory"] is True
    assert data["coverage"]["coverage_rate"] == 0.5


def test_bridge_method_accepts_wrappers_and_exclusions():
    from bridge.api import Bridge
    b = Bridge()
    est = {"rows": ESTIMATE}
    reg = {"requirements": REGISTER[:4],
           "exclusions": [{"list_id": "IE-0050", "req_id": "REQ-0050",
                           "text": "Electrical conduit and wiring"}]}
    r = b.bid_reconciliation_check(estimate=json.dumps(est),
                                   register=json.dumps(reg))
    assert r["ok"] is True
    ex = [f for f in r["data"]["findings"] if f["type"] == "EXCLUDED_BUT_PRICED"]
    assert len(ex) == 1 and ex[0]["req_id"] == "REQ-0050"


def test_bridge_method_reads_file_paths(tmp_path):
    from bridge.api import Bridge
    b = Bridge()
    ep = tmp_path / "est.json"
    rp = tmp_path / "reg.json"
    ep.write_text(json.dumps(ESTIMATE), encoding="utf-8")
    rp.write_text(json.dumps(REGISTER), encoding="utf-8")
    r = b.bid_reconciliation_check(estimate_path=str(ep), register_path=str(rp))
    assert r["ok"] is True
    assert r["data"]["coverage"]["priceable_total"] == 4


def test_bridge_method_rejects_bad_json():
    from bridge.api import Bridge
    b = Bridge()
    r = b.bid_reconciliation_check(estimate="{not json", register="[]")
    assert r["ok"] is False
    assert "json" in r["error"].lower()


def test_bridge_method_reports_missing_path():
    from bridge.api import Bridge
    b = Bridge()
    r = b.bid_reconciliation_check(estimate_path="does/not/exist.json",
                                   register="[]")
    assert r["ok"] is False
    assert "not found" in r["error"].lower()
