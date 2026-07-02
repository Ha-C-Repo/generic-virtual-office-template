"""
CONFIDENCE TAGS - render explicit confidence and "Not stated" badges
on extracted values so the user can tell what is verified vs guessed.

Derived from Operum.io review (2026-05-28). Operum shows three visible
tags on every extracted item or section:

  Found & verified       (green)    - quoted directly from source
  Inferred / needs review (amber)    - derived from a related fact
  Not stated              (gray)     - source is silent, called out

These are governance-rule "verify, do not generate" rendered as UI.
Our pipeline tags confidence internally (see SKILL.md step 2 - high/
medium/low) but does not surface it in the markdown handoff or PDFs.
This module makes the tags first-class output.

Rules:
  - Module-level only.
  - Pure stdlib.
  - When source is silent, NEVER fabricate a value. Use NOT_STATED
    sentinel. Callers that ignore NOT_STATED get an exception.
  - _ok / _err shape for Bridge entry points.
"""

from __future__ import annotations

NOT_STATED = "__NOT_STATED__"   # Sentinel value for absent source data.

TAG_FOUND_VERIFIED = "FOUND_VERIFIED"
TAG_INFERRED = "INFERRED_NEEDS_REVIEW"
TAG_NOT_STATED = "NOT_STATED"
TAG_ASSUMED_DEFAULT = "ASSUMED_DEFAULT"
TAG_CONFLICT = "CONFLICT_BETWEEN_SOURCES"

ALL_TAGS = (
    TAG_FOUND_VERIFIED,
    TAG_INFERRED,
    TAG_NOT_STATED,
    TAG_ASSUMED_DEFAULT,
    TAG_CONFLICT,
)

# Display strings for human-readable output (markdown, email, PDF caption).
TAG_DISPLAY = {
    TAG_FOUND_VERIFIED:   "Found & verified",
    TAG_INFERRED:         "Inferred / needs review",
    TAG_NOT_STATED:       "Not stated",
    TAG_ASSUMED_DEFAULT:  "Assumed default (calibration)",
    TAG_CONFLICT:         "CONFLICT between sources",
}

# Severity ordering for sorting / prioritizing. Higher = more attention.
TAG_SEVERITY = {
    TAG_FOUND_VERIFIED:   0,
    TAG_ASSUMED_DEFAULT:  1,
    TAG_INFERRED:         2,
    TAG_NOT_STATED:       3,
    TAG_CONFLICT:         4,
}


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def tag_value(value, tag, source=None, note=None):
    """Wrap a value with a confidence tag.

    value: the extracted value (can be NOT_STATED if source is silent)
    tag: one of ALL_TAGS
    source: where this came from (e.g. "SP183_Scope.pdf p4")
    note: optional human-readable note

    Returns a dict like:
      {"value": 547, "tag": "FOUND_VERIFIED", "display": "Found & verified",
       "source": "SP183_Scope.pdf p4", "note": null}

    If you pass NOT_STATED as value, tag is forced to TAG_NOT_STATED.
    """
    if tag not in ALL_TAGS:
        raise ValueError(f"tag {tag!r} not in {ALL_TAGS}")
    if value == NOT_STATED:
        tag = TAG_NOT_STATED
    return {
        "value": (None if value == NOT_STATED else value),
        "tag": tag,
        "display": TAG_DISPLAY[tag],
        "severity": TAG_SEVERITY[tag],
        "source": source,
        "note": note,
    }


def is_not_stated(tagged_value):
    """Returns True if the tagged value is a NOT_STATED sentinel."""
    if not isinstance(tagged_value, dict):
        return False
    return tagged_value.get("tag") == TAG_NOT_STATED


def require_value(tagged_value, field_name="value"):
    """Use this when downstream code REQUIRES a real value. Raises
    if the value is NOT_STATED. Forces the caller to handle the
    absent-source case explicitly rather than fall through with a
    silent zero or None."""
    if is_not_stated(tagged_value):
        raise ValueError(
            f"{field_name} is NOT_STATED in source documents. "
            "Cannot proceed without explicit value. Either fix the "
            "extractor, raise an RFI, or apply a calibration default "
            "with tag_value(..., tag=TAG_ASSUMED_DEFAULT, source='calibration')."
        )
    return tagged_value["value"]


def render_inline(tagged_value):
    """One-liner display for a tagged value. Use in markdown tables.

    Returns strings like:
      "547 [Found & verified] (SP183_Scope.pdf p4)"
      "Not stated [Not stated] - see RFI-001"
      "8.0 [Assumed default (calibration)] (data/calibration/ivan_confirmed_2026Q2.json)"
    """
    if not isinstance(tagged_value, dict):
        return str(tagged_value)
    v = tagged_value.get("value")
    display = tagged_value.get("display", "")
    source = tagged_value.get("source") or ""
    note = tagged_value.get("note") or ""
    parts = []
    if v is None and tagged_value.get("tag") == TAG_NOT_STATED:
        parts.append("Not stated")
    else:
        parts.append(str(v))
    parts.append(f"[{display}]")
    if source:
        parts.append(f"({source})")
    if note:
        parts.append(f"- {note}")
    return " ".join(parts)


def section_tag(section_name, items_or_subtags):
    """Compute a section-level rollup tag from a list of item tags or
    sub-tag values. Returns the worst (highest-severity) tag in the
    group, so a section gets badged "Inferred / needs review" if any
    of its items are.

    section_name: human label (for the returned payload)
    items_or_subtags: list of tag strings or list of tag_value() dicts

    Returns {"section": ..., "rollup_tag": ..., "display": ...}
    """
    worst = TAG_FOUND_VERIFIED
    worst_sev = -1
    for item in items_or_subtags:
        if isinstance(item, dict):
            t = item.get("tag", TAG_FOUND_VERIFIED)
        else:
            t = item
        sev = TAG_SEVERITY.get(t, 0)
        if sev > worst_sev:
            worst = t
            worst_sev = sev
    return {
        "section": section_name,
        "rollup_tag": worst,
        "display": TAG_DISPLAY[worst],
        "severity": worst_sev if worst_sev >= 0 else 0,
    }


def filter_not_stated(items, value_key="value"):
    """Return only items whose value is NOT_STATED. Use this to drive
    RFI generation: every NOT_STATED in an extracted scope item should
    become an RFI."""
    out = []
    for item in items:
        if isinstance(item, dict):
            tv = item.get(value_key)
            if isinstance(tv, dict) and is_not_stated(tv):
                out.append(item)
            elif tv == NOT_STATED:
                out.append(item)
    return out


def coerce_to_tagged(raw_value, default_tag=TAG_FOUND_VERIFIED, source=None):
    """Idempotent helper. If raw_value is already a tagged dict, return
    it unchanged. Otherwise wrap with default_tag. Use during gradual
    migration of existing extractors to the tagged shape."""
    if isinstance(raw_value, dict) and "tag" in raw_value and raw_value.get("tag") in ALL_TAGS:
        return raw_value
    return tag_value(raw_value, default_tag, source=source)


# Smoke test
if __name__ == "__main__":
    examples = [
        tag_value(547, TAG_FOUND_VERIFIED, source="SP183_Scope.pdf p4"),
        tag_value(280, TAG_INFERRED, source="joist schedule",
                  note="estimated from grid spacing, no schedule found"),
        tag_value(NOT_STATED, TAG_FOUND_VERIFIED, source="SP183_Scope.pdf",
                  note="connection design responsibility silent"),
        tag_value(8, TAG_ASSUMED_DEFAULT,
                  source="data/calibration/ivan_confirmed_2026Q2.json",
                  note="connection allowance percent for tilt_wall + bar_joists + HSS"),
    ]
    for e in examples:
        print(render_inline(e))
    print()
    print("Section rollup:", section_tag("scope_completeness", examples))
    print()
    print("NOT_STATED filter result:")
    for n in filter_not_stated([{"value": e} for e in examples]):
        print("  ", n)
