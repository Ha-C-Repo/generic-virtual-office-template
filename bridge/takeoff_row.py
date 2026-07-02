"""Canonical takeoff/BOQ row schema (plan item 1.3).

The row-level schema Ivan signed: Tag, Description, System, Qty, Unit,
Drawing, Method, Confidence, Basis, Notes. One row per measured or inferred
quantity. Every inferred line carries a written assumption string in Basis.

ADVISORY AND STRUCTURAL ONLY. This module defines a shape, builds rows, and
validates them. It never sets, changes, or generates a price, quantity,
weight, or rate. Member weights stay in bridge/aisc_validator.py and rates in
bridge/bid_rates.py. Qty is carried through verbatim from the takeoff; this
module never computes it.

Method-linked confidence (the house confidence doctrine, ConstructIQ 7.5):
  HIGH  - vector or text tag, or a stated schedule quantity
  MED   - measured from a scaled framing plan
  LOW   - vision read, or inferred-with-assumption

The canonical row is the hub between the count-gap engine and the
reconciliation advisory gate. The count-gap engine emits the eleven-column
TAKEOFF_SCHEMA_V2 row; from_schema_v2_row() maps it here. The reconciliation
gate (bridge/bid_sanity_gates.reconcile_advisory) reads estimate-line dicts;
to_estimate_line() maps a canonical row to that shape. Both consume the same
row.

Module-level only. Pure stdlib. PyInstaller-safe.
"""

from __future__ import annotations
import re
from typing import TypedDict

# Canonical field order: Tag, Description, System, Qty, Unit, Drawing,
# Method, Confidence, Basis, Notes.
TAKEOFF_ROW_FIELDS = (
    "tag", "description", "system", "qty", "unit",
    "drawing", "method", "confidence", "basis", "notes",
)

# Takeoff methods and the confidence each one earns. Confidence is
# method-linked, never free-typed.
METHOD_VECTOR_OR_TAG = "vector_or_text_tag"   # vector geometry or a text tag
METHOD_STATED_SCHEDULE = "stated_schedule"    # a quantity stated in a schedule
METHOD_SCALED_PLAN = "scaled_plan_measure"    # measured off a scaled framing plan
METHOD_VISION = "vision"                       # read from a rendered image
METHOD_INFERRED = "inferred"                    # inferred with a written assumption

METHODS = (
    METHOD_VECTOR_OR_TAG, METHOD_STATED_SCHEDULE, METHOD_SCALED_PLAN,
    METHOD_VISION, METHOD_INFERRED,
)

METHOD_CONFIDENCE = {
    METHOD_VECTOR_OR_TAG: "high",
    METHOD_STATED_SCHEDULE: "high",
    METHOD_SCALED_PLAN: "medium",
    METHOD_VISION: "low",
    METHOD_INFERRED: "low",
}

CONFIDENCES = ("high", "medium", "low")

# Methods whose rows MUST carry a written assumption string in Basis.
_BASIS_REQUIRED_METHODS = frozenset({METHOD_INFERRED, METHOD_VISION})

# Units a takeoff row may carry. Identity only; no conversion happens here.
UNITS = ("EA", "LF", "SF", "LB", "TON", "HR", "CY", "LS")

# Systems (the steel scope buckets) the count-gap item_class set maps into.
# Connections is a first-class system, not part of Misc Metals
# (Ivan and Owner confirmed 2026-06-29). The connection take-off pass
# (bridge/connection_takeoff.py) emits its rows under "Connections".
SYSTEMS = (
    "Structural Steel", "Joists", "Deck", "Connections", "Anchors",
    "Misc Metals", "Other",
)

_V2_CLASS_TO_SYSTEM = {
    "COL": "Structural Steel",
    "BEAM": "Structural Steel",
    "JST": "Joists",
    "DECK": "Deck",
    "PLATE": "Misc Metals",
    "ANCH": "Anchors",
    "MISC": "Misc Metals",
}

_V2_CONF_TO_METHOD = {
    "high": METHOD_VECTOR_OR_TAG,
    "medium": METHOD_SCALED_PLAN,
    "low": METHOD_INFERRED,
}


class TakeoffRow(TypedDict, total=False):
    """One canonical takeoff/BOQ row. qty is carried verbatim, never computed."""
    tag: str
    description: str
    system: str
    qty: object
    unit: str
    drawing: str
    method: str
    confidence: str
    basis: str
    notes: str


def confidence_for_method(method: str) -> str:
    """The method-linked confidence for a takeoff method."""
    return METHOD_CONFIDENCE.get(method, "low")


def make_row(tag, description, system, qty, unit, drawing, method,
             basis="", notes="", confidence=None) -> "TakeoffRow":
    """Build a canonical takeoff row.

    Confidence is derived from the method unless explicitly overridden.
    Inferred and vision rows must carry a written assumption string in
    basis; this helper records what you pass, it never invents one. Qty is
    carried through verbatim and never computed.
    """
    row: TakeoffRow = {
        "tag": str(tag or ""),
        "description": str(description or ""),
        "system": str(system or "Other"),
        "qty": qty,
        "unit": str(unit or ""),
        "drawing": str(drawing or ""),
        "method": str(method or ""),
        "confidence": str(confidence or confidence_for_method(method)),
        "basis": str(basis or ""),
        "notes": str(notes or ""),
    }
    return row



# Inline multiplier notation (plan item D2): a trailing " x2" / " X 2" on a
# tag or description hides a quantity in text (the "F10 x2" miscount case).
# Shape designations like W12X26 carry no space before the x and never match.
_INLINE_MULTIPLIER_RE = re.compile(r"(?i)\s+x\s*\d+\s*$")


def _validate_qty(qty, unit):
    """Integer-quantity rule (plan item D2, Owner-approved 2026-07-02).

    EA-unit rows: qty must be a plain non-negative integer. A string qty
    is an error even when it looks numeric; text quantities are how the
    "F10 x2" miscount class happens. A whole-number float earns a warning
    (coercible, but the emitter should fix it). Other units keep the
    verbatim-carry contract untouched. Never computes or changes a qty.
    """
    errors = []
    warnings = []
    if unit != "EA":
        return errors, warnings
    if isinstance(qty, bool):
        errors.append(f"EA qty must be a non-negative integer, got bool {qty!r}")
    elif isinstance(qty, int):
        if qty < 0:
            errors.append(f"EA qty must be non-negative, got {qty!r}")
    elif isinstance(qty, float):
        if qty.is_integer() and qty >= 0:
            warnings.append(
                f"EA qty {qty!r} is a whole-number float; emit it as an int")
        else:
            errors.append(f"EA qty must be a non-negative integer, got {qty!r}")
    elif isinstance(qty, str):
        errors.append(
            f"EA qty is text ({qty!r}); qty must be a plain non-negative "
            "integer, never a string")
    else:
        errors.append(
            f"EA qty must be a non-negative integer, got {type(qty).__name__}")
    return errors, warnings


def validate_row(row: dict) -> tuple:
    """Validate one canonical row.

    Returns (errors, warnings), both lists of strings. Errors mean the row
    is not schema-conformant. Warnings are advisory (a confidence that does
    not match the method, a non-standard unit). Never raises on content; it
    reports.
    """
    if not isinstance(row, dict):
        return (["row is not a dict"], [])
    errors = []
    warnings = []
    for f in ("tag", "system", "unit", "drawing", "method"):
        if not str(row.get(f) or "").strip():
            errors.append(f"missing required field: {f}")
    if "qty" not in row or row.get("qty") in (None, ""):
        errors.append("missing required field: qty")
    else:
        q_errs, q_warns = _validate_qty(row.get("qty"), str(row.get("unit") or ""))
        errors.extend(q_errs)
        warnings.extend(q_warns)
    for f in ("tag", "description"):
        if _INLINE_MULTIPLIER_RE.search(str(row.get(f) or "")):
            warnings.append(
                f"inline multiplier notation in {f} ({str(row.get(f))!r}); "
                "carry the count in qty, never in text")
    method = row.get("method")
    if method and method not in METHODS:
        errors.append(f"method {method!r} not in {METHODS}")
    unit = row.get("unit")
    if unit and unit not in UNITS:
        warnings.append(f"unit {unit!r} not in the standard set {UNITS}")
    system = row.get("system")
    if system and system not in SYSTEMS:
        warnings.append(f"system {system!r} not in the standard set {SYSTEMS}")
    conf = row.get("confidence")
    if conf and conf not in CONFIDENCES:
        errors.append(f"confidence {conf!r} not in {CONFIDENCES}")
    if method in METHOD_CONFIDENCE and conf and conf != METHOD_CONFIDENCE[method]:
        warnings.append(
            f"confidence {conf!r} does not match method {method!r} "
            f"(expected {METHOD_CONFIDENCE[method]!r})")
    if method in _BASIS_REQUIRED_METHODS and not str(row.get("basis") or "").strip():
        errors.append(
            f"method {method!r} requires a written assumption string in basis")
    return (errors, warnings)


def validate_rows(rows) -> dict:
    """Validate a list of canonical rows. Advisory summary, never raises."""
    findings = []
    n_err = 0
    n_warn = 0
    for i, row in enumerate(rows or []):
        errors, warnings = validate_row(row)
        n_err += len(errors)
        n_warn += len(warnings)
        if errors or warnings:
            findings.append({
                "index": i,
                "tag": (row or {}).get("tag", "") if isinstance(row, dict) else "",
                "errors": errors,
                "warnings": warnings,
            })
    return {
        "row_count": len(rows or []),
        "rows_with_findings": findings,
        "error_count": n_err,
        "warning_count": n_warn,
        "valid": n_err == 0,
        "fields": list(TAKEOFF_ROW_FIELDS),
    }


def from_schema_v2_row(v2: dict) -> "TakeoffRow":
    """Map a count-gap engine TAKEOFF_SCHEMA_V2 row into the canonical row.

    The v2 row carries item_class, designation, mode, qty, unit,
    primary_source, secondary_source, confidence, sheet, notes. Method is
    inferred from the v2 confidence semantics (schema section 6): high =
    schedule or tag (vector_or_text_tag), medium = plan callout
    (scaled_plan_measure), low = ambiguous (inferred). Qty is carried
    verbatim. A v2 row's assumption text lives in notes; it is carried into
    basis for inferred or vision rows so the canonical contract holds.
    """
    v2 = v2 or {}
    conf = str(v2.get("confidence") or "low").lower()
    method = _V2_CONF_TO_METHOD.get(conf, METHOD_INFERRED)
    system = _V2_CLASS_TO_SYSTEM.get(
        str(v2.get("item_class") or "").upper(), "Other")
    drawing = str(v2.get("primary_source") or v2.get("sheet") or "")
    notes = str(v2.get("notes") or "")
    basis = notes if method in _BASIS_REQUIRED_METHODS else ""
    return make_row(
        tag=v2.get("designation"),
        description=v2.get("designation"),
        system=system,
        qty=v2.get("qty"),
        unit=v2.get("unit"),
        drawing=drawing,
        method=method,
        basis=basis,
        notes=notes,
        confidence=conf if conf in CONFIDENCES else None,
    )


def to_estimate_line(row: dict, line_id=None, category="Direct",
                     requirement_refs=None) -> dict:
    """Map a canonical takeoff row to the estimate-line dict consumed by
    bridge.bid_sanity_gates.reconcile_advisory (the reconciliation advisory
    gate). Carries description, unit, qty, and the canonical drawing,
    method, and confidence as context. No price, rate, or weight is produced.
    """
    row = row or {}
    return {
        "line_id": str(line_id if line_id is not None else (row.get("tag") or "")),
        "description": str(row.get("description") or row.get("tag") or ""),
        "category": str(category or "Direct"),
        "discipline": str(row.get("system") or ""),
        "unit": str(row.get("unit") or ""),
        "qty": row.get("qty"),
        "requirement_refs": list(requirement_refs or []),
        "drawing": str(row.get("drawing") or ""),
        "method": str(row.get("method") or ""),
        "confidence": str(row.get("confidence") or ""),
        "notes": str(row.get("notes") or ""),
    }
