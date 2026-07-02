"""Connection take-off / connection-material allowance pass (plan item 1.1).

VERIFY-DO-NOT-GENERATE. This pass sizes a connection-material allowance
deterministically from Ivan's locked calibration and the locked rates. It
NEVER invents or originates a number:

  - The percentage comes live from data/calibration/ivan_confirmed_2026Q2.json
    key connection_allowance_pct_of_structural_tonnage, by framing type. Never
    hardcoded or guessed.
  - The structural tonnage comes from bridge/aisc_validator.py only.
  - The rate comes from bridge/bid_rates.py only (locked fab + erection).

    connection_tons = structural_tons * pct / 100
    connection_allowance_cost = connection_tons * (fab_per_ton + erection_per_ton)

The connection allowance is always a ROM allowance and is flagged (AISC
doctrine: "treat any flat per-ton connection allowance as ROM only and flag
it"). It emits a Connections-bucket row in the canonical takeoff_row shape so
it flows through the same hub as the count-gap engine and the reconciliation
gate, plus a priced allowance summary with full provenance.

The framing-type selection (which percentage bucket) is the judgment point and
is supplied by the caller. If it is not determinable, the pass emits a
LOW-confidence flag and an RFI (reusing bridge/auto_rfi.py) and computes no
number; it never silently defaults.

Module-level only. resource_path() for the calibration file. PyInstaller-safe.
"""

from __future__ import annotations
import json

from vo_app._resources import resource_path
from bridge import auto_rfi, takeoff_row

_CALIB_RELATIVE = "data/calibration/ivan_confirmed_2026Q2.json"
_CALIB_KEY = "connection_allowance_pct_of_structural_tonnage"

_DISCLAIMER = (
    "Connection-material allowance is a ROM allowance, not a measured takeoff. "
    "The percentage is read live from Ivan's locked calibration, the structural "
    "tonnage from bridge/aisc_validator.py, and the rate from bridge/bid_rates.py. "
    "No number originates in the model. Verify against a measured connection "
    "takeoff before the number ships on a live bid."
)


def load_connection_pcts(calibration_path=None) -> dict:
    """Read the connection-allowance percentages live from Ivan's calibration.

    Returns {framing_type: {"pct": N, "confidence": str}} with metadata keys
    (those starting with '_') stripped. Never hardcodes a value. Raises
    FileNotFoundError if the calibration file is missing; we do not invent a
    fallback percentage.
    """
    path = calibration_path or resource_path(_CALIB_RELATIVE)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    block = data.get(_CALIB_KEY, {})
    return {k: v for k, v in block.items() if not str(k).startswith("_")}


def available_framing_types(calibration_path=None) -> list:
    """The framing-type buckets available in the live calibration."""
    return sorted(load_connection_pcts(calibration_path).keys())


def _structural_tonnage(structural_tons, members):
    """Return (tons, source, validator_report). Tonnage comes from
    aisc_validator only. The members path is strict (validate_takeoff, which
    validates each shape and sums weight). A caller-provided structural_tons is
    accepted but must already be sourced from aisc_validator.
    """
    if members:
        from bridge.aisc_validator import validate_takeoff
        report = validate_takeoff(members)
        return (report.get("total_tonnage", 0.0),
                "bridge/aisc_validator.py:validate_takeoff", report)
    if structural_tons not in (None, ""):
        return (float(structural_tons),
                "caller-provided (must be sourced from bridge/aisc_validator.py)",
                None)
    return (None, None, None)


def connection_takeoff(framing_type="", structural_tons=None, members=None,
                       project_id="", drawing="", calibration_path=None) -> dict:
    """Size the connection-material allowance. ADVISORY, verify-do-not-generate.

    Args:
        framing_type: the judgment input. One of the calibration framing-type
            buckets (see available_framing_types). Empty or unknown -> flag+RFI.
        structural_tons: structural tonnage already sourced from aisc_validator.
        members: alternatively, a member list to run through aisc_validator
            (the strict tonnage path; each is {shape, qty, length_ft}).
        project_id: bid id for the RFI list.
        drawing: drawing reference recorded on the takeoff row.
        calibration_path: override for testing; defaults to the locked file.

    Returns an advisory dict. No number originates in the model.
    """
    flags = []
    raw_rfis = []
    seq = [0]

    def add_rfi(trigger, source, ctxsub=None):
        seq[0] += 1
        raw_rfis.append(auto_rfi.rfi_from_trigger(trigger, seq[0], source, ctxsub))

    def add_flag(item, reason):
        flags.append({"item": item, "reason": reason, "confidence": "LOW"})

    def finalize(result):
        rfi_result = auto_rfi.build_rfi_list(project_id or "CONN-TAKEOFF", raw_rfis)
        payload = rfi_result.get("data") if rfi_result.get("ok") else None
        result["rfis"] = payload
        result["rfi_markdown"] = auto_rfi.render_markdown(payload) if payload else ""
        return result

    pcts = load_connection_pcts(calibration_path)
    ft = str(framing_type or "").strip()
    determinable = ft in pcts
    tons, tonnage_source, validator_report = _structural_tonnage(structural_tons, members)

    result = {
        "advisory": True,
        "generates_numbers": False,
        "framing_type": ft,
        "framing_type_determinable": determinable,
        "available_framing_types": sorted(pcts.keys()),
        "structural_tons": tons,
        "tonnage_source": tonnage_source,
        "rom": True,
        "pct_source": f"{_CALIB_RELATIVE} :: {_CALIB_KEY}",
        "rate_source": "bridge/bid_rates.py BID_RATES fab_per_ton + erection_per_ton",
        "connection_pct": None,
        "connection_pct_confidence": None,
        "connection_tons": None,
        "rate_per_ton": None,
        "connection_allowance_cost": None,
        "takeoff_rows": [],
        "low_confidence_flags": flags,
        "rfis": None,
        "rfi_markdown": "",
        "verdict": None,
        "disclaimer": _DISCLAIMER,
    }

    # Judgment point: the framing type must be determinable. Never default.
    if not determinable:
        if not ft:
            reason = ("Framing type not determined. The connection-allowance "
                      "percentage bucket cannot be selected without it. No "
                      "allowance computed.")
        else:
            reason = (f"Framing type {ft!r} is not one of Ivan's calibration "
                      f"buckets. No allowance computed.")
        add_flag("framing_type", reason)
        add_rfi("connection_framing_type_undetermined", "connection_takeoff:1.1",
                {"types": ", ".join(sorted(pcts.keys()))})
        return finalize(result)

    pct_entry = pcts[ft]
    result["connection_pct"] = pct_entry.get("pct")
    result["connection_pct_confidence"] = pct_entry.get("confidence")
    pct = pct_entry.get("pct")

    # Surface invalid shapes rather than pricing off them.
    if validator_report and validator_report.get("invalid_count", 0) > 0:
        add_flag("structural_tonnage",
                 f"{validator_report['invalid_count']} member shape(s) failed "
                 "aisc_validator. Tonnage may be understated; verify before pricing.")

    if tons in (None, "") or tons <= 0:
        add_flag("structural_tonnage",
                 "Structural tonnage from aisc_validator is missing or zero. "
                 "Provide validated tonnage or a member list. No allowance computed.")
        return finalize(result)

    if pct in (None, ""):
        add_flag("connection_pct",
                 f"Calibration bucket {ft!r} carries no pct value. No allowance computed.")
        return finalize(result)

    # Deterministic sizing. Every input is sourced; none originates here.
    from bridge.bid_rates import BID_RATES
    rate_per_ton = BID_RATES["fab_per_ton"] + BID_RATES["erection_per_ton"]
    connection_tons = round(tons * float(pct) / 100.0, 3)
    connection_cost = round(connection_tons * rate_per_ton, 2)

    result["rate_per_ton"] = rate_per_ton
    result["connection_tons"] = connection_tons
    result["connection_allowance_cost"] = connection_cost

    basis = (
        f"ROM connection allowance: {pct} percent of {tons} structural tons per "
        f"Ivan calibration framing type '{ft}' ({_CALIB_RELATIVE}); tonnage from "
        f"{tonnage_source}; priced at fab plus erection {rate_per_ton} per ton "
        f"from bridge/bid_rates.py. Flagged ROM, verify against a measured "
        f"connection takeoff."
    )
    row = takeoff_row.make_row(
        tag="CONN-ALLOW",
        description=f"Connection material allowance ({pct} percent of structural tonnage)",
        system="Connections",
        qty=connection_tons,
        unit="TON",
        drawing=drawing or "calibration",
        method=takeoff_row.METHOD_INFERRED,   # ROM allowance, low confidence by schema
        basis=basis,
        notes=f"framing_type={ft}; pct_confidence={pct_entry.get('confidence')}",
    )
    result["takeoff_rows"] = [row]

    # The allowance is always ROM; flag it (KB doctrine).
    add_flag("connection_allowance",
             "Connection material carried as a ROM percentage allowance, not a "
             "measured takeoff. Verify before it ships on a live bid.")
    return finalize(result)
