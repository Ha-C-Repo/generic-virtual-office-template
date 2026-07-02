"""
CROSS DOC CONFLICTS - detect contradictions between bid documents.

Derived from Operum.io review (2026-05-28). Operum's sample analysis
spotted "Conflicting counts stated: 5 required items (Invitation to
Tender.pdf) and 7 required items (Tender Returnable Schedule.pdf)."
That is exactly the kind of error that bites Your Company when a sub-
trade scope items differs between the Scope of Works PDF and the BOQ.

This module ingests parallel extractions from multiple source
documents and emits a conflict list. Each conflict carries:
  - the conflicting fact (what the docs disagree on)
  - which sources said what
  - severity (HARD = price-blocker, SOFT = needs reconciliation)
  - suggested action (use newer addendum, raise RFI, ask Owner)

Currently the pipeline trusts the first extractor that fires and
silently uses its value. Cross-doc conflicts get missed and Ivan
catches them in verification. This module makes them explicit before
the bid goes out.

Rules:
  - Module-level only.
  - Pure stdlib.
  - _ok / _err for Bridge entry points.
  - When a conflict is found, we DO NOT pick a winner. Surface it for
    human decision. "Verify, do not generate" again.
"""

from __future__ import annotations
from datetime import datetime, timezone

# Severity levels
HARD = "HARD"      # different numbers, different scope inclusion - price impact
SOFT = "SOFT"      # different phrasing for same concept, low risk
INFO = "INFO"      # one doc adds a clarification the other lacks

SEVERITY_LEVELS = (HARD, SOFT, INFO)

# Suggested actions
ACTION_USE_ADDENDUM = "USE_ADDENDUM"        # if one source is an addendum, use it
ACTION_RAISE_RFI = "RAISE_RFI"              # auto_rfi.boq_vs_scope_conflict template
ACTION_ASK_OWNER = "ASK_OWNER"          # human judgment needed
ACTION_LOG_AND_PROCEED = "LOG_AND_PROCEED"  # SOFT conflicts that don't change price


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_id(seq_num):
    if not isinstance(seq_num, int) or seq_num < 1:
        raise ValueError("seq_num must be a positive integer")
    return f"CONFLICT-{seq_num:03d}"


def _values_disagree(values):
    """Return True if the values in the list disagree materially.
    Handles numbers (within 1% tolerance), strings (case-insensitive),
    and None (treated as 'absent')."""
    # Strip Nones; if all None or one value remains, no disagreement.
    real = [v for v in values if v is not None]
    if len(real) <= 1:
        return False
    # If any are None and others aren't, that's a disagreement (presence vs absence).
    if len(real) != len(values):
        return True
    # Try numeric comparison with 1% tolerance.
    try:
        nums = [float(v) for v in real]
        if not nums:
            return False
        mx = max(nums)
        mn = min(nums)
        if mx == 0 and mn == 0:
            return False
        if mx == 0:
            return True
        return ((mx - mn) / abs(mx)) > 0.01
    except (TypeError, ValueError):
        pass
    # Fallback to string comparison, case-insensitive, whitespace-collapsed.
    norm = set()
    for v in real:
        norm.add(" ".join(str(v).split()).lower())
    return len(norm) > 1


def compare_field(field_name, sources_values, severity=HARD, action=None):
    """Build a conflict record for a single named field.

    field_name: human label e.g. "structural tonnage"
    sources_values: dict mapping source_id -> value
        e.g. {"SP183_Scope.pdf": 547, "SP183_BOQ.xlsx": 580}
    severity: HARD / SOFT / INFO
    action: one of the ACTION_* constants. If None, auto-picks
            ACTION_RAISE_RFI for HARD, ACTION_LOG_AND_PROCEED for SOFT.

    Returns conflict dict if disagreement found, None otherwise.
    """
    if not isinstance(sources_values, dict) or len(sources_values) < 2:
        return None
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"severity must be one of {SEVERITY_LEVELS}")
    values = list(sources_values.values())
    if not _values_disagree(values):
        return None
    if action is None:
        action = ACTION_RAISE_RFI if severity == HARD else ACTION_LOG_AND_PROCEED
    return {
        "field": field_name,
        "severity": severity,
        "action": action,
        "sources": [
            {"source": k, "value": v}
            for k, v in sources_values.items()
        ],
    }


def detect_count_conflicts(project_id, count_facts):
    """Detect numeric-count disagreements across docs (Operum's flagship
    pattern: '5 vs 7 required items').

    count_facts: list of dicts like:
      [
        {"field": "required tender items",
         "sources": {"Invitation to Tender.pdf": 5,
                     "Tender Returnable Schedule.pdf": 7}},
        {"field": "anchor count",
         "sources": {"Drawings S-2.1": 480, "Anchor Schedule": 512}},
      ]

    Returns _ok({...}) with a conflict list.
    """
    if not isinstance(project_id, str) or not project_id:
        return _err("project_id must be a non-empty string")
    if not isinstance(count_facts, list):
        return _err("count_facts must be a list")
    conflicts = []
    for fact in count_facts:
        rec = compare_field(
            fact.get("field", "unknown"),
            fact.get("sources", {}),
            severity=fact.get("severity", HARD),
            action=fact.get("action"),
        )
        if rec:
            conflicts.append(rec)
    return _ok(_build_payload(project_id, conflicts))


def detect_scope_inclusion_conflicts(project_id, scope_items_by_source):
    """Detect items present in one document but absent from another.

    scope_items_by_source: dict mapping source_id -> set of item names.
      e.g. {
          "SP183_Scope.pdf": {"columns", "joists", "deck", "embeds"},
          "SP183_BOQ.xlsx":  {"columns", "joists", "deck"},
      }

    Returns _ok({...}) with conflict records for every item present in
    one source but missing from another.
    """
    if not isinstance(project_id, str) or not project_id:
        return _err("project_id must be a non-empty string")
    if not isinstance(scope_items_by_source, dict):
        return _err("scope_items_by_source must be a dict")
    # Normalize sets
    norm = {}
    for src, items in scope_items_by_source.items():
        try:
            norm[src] = set(str(i).strip().lower() for i in items)
        except TypeError:
            return _err(f"items for {src!r} not iterable")
    all_items = set()
    for s in norm.values():
        all_items |= s
    conflicts = []
    for item in sorted(all_items):
        present_in = [src for src, items in norm.items() if item in items]
        absent_from = [src for src in norm if src not in present_in]
        if absent_from and present_in:
            sources_dict = {}
            for src in norm:
                sources_dict[src] = "PRESENT" if item in norm[src] else "ABSENT"
            conflicts.append({
                "field": f"scope item: {item}",
                "severity": HARD,
                "action": ACTION_RAISE_RFI,
                "sources": [{"source": k, "value": v} for k, v in sources_dict.items()],
                "note": (
                    f"Item '{item}' appears in {', '.join(present_in)} "
                    f"but is missing from {', '.join(absent_from)}. "
                    "Confirm whether it is in our scope."
                ),
            })
    return _ok(_build_payload(project_id, conflicts))


def _build_payload(project_id, conflicts):
    summary = {
        "total": len(conflicts),
        "hard": sum(1 for c in conflicts if c["severity"] == HARD),
        "soft": sum(1 for c in conflicts if c["severity"] == SOFT),
        "info": sum(1 for c in conflicts if c["severity"] == INFO),
    }
    items = []
    for i, c in enumerate(conflicts, start=1):
        rec = dict(c)
        rec["id"] = normalize_id(i)
        items.append(rec)
    return {
        "conflict_list_id": f"CONFLICTS-{project_id}",
        "project_id": project_id,
        "generated_at": _utc_now_iso(),
        "items": items,
        "summary": summary,
    }


def render_markdown(payload):
    """Pretty-print a conflict list."""
    if not isinstance(payload, dict) or "items" not in payload:
        return "INVALID_CONFLICT_LIST"
    lines = []
    lines.append(f"# Cross-Document Conflicts: {payload.get('conflict_list_id', 'UNKNOWN')}")
    lines.append("")
    s = payload.get("summary", {})
    lines.append(
        f"- Total conflicts: {s.get('total', 0)} "
        f"({s.get('hard', 0)} HARD, {s.get('soft', 0)} SOFT, {s.get('info', 0)} INFO)"
    )
    if s.get("total", 0) == 0:
        lines.append("")
        lines.append("No conflicts detected across source documents.")
        return "\n".join(lines)
    lines.append("")
    for item in payload["items"]:
        lines.append(f"## {item['id']} - {item['field']}")
        lines.append(f"- Severity: **{item['severity']}**")
        lines.append(f"- Suggested action: {item['action']}")
        lines.append("- Sources:")
        for src in item["sources"]:
            lines.append(f"  - {src['source']}: {src['value']}")
        if item.get("note"):
            lines.append(f"- Note: {item['note']}")
        lines.append("")
    return "\n".join(lines)


def merge_conflict_lists(*payloads):
    """Merge several conflict lists into one (e.g. count conflicts +
    scope inclusion conflicts). All payloads must be for the same
    project_id. Re-sequences IDs."""
    payloads = [p for p in payloads if isinstance(p, dict) and "items" in p]
    if not payloads:
        return _err("no valid payloads to merge")
    project_id = payloads[0].get("project_id", "UNKNOWN")
    for p in payloads[1:]:
        if p.get("project_id") != project_id:
            return _err("cannot merge: project_id mismatch")
    combined = []
    for p in payloads:
        for item in p["items"]:
            ci = dict(item)
            ci.pop("id", None)  # will be re-assigned
            combined.append(ci)
    return _ok(_build_payload(project_id, combined))


# Smoke test
if __name__ == "__main__":
    out1 = detect_count_conflicts("PRJ-2026-SOU-001", [
        {"field": "required tender items",
         "sources": {"Invitation to Tender.pdf": 5,
                     "Tender Returnable Schedule.pdf": 7}},
        {"field": "anchor count",
         "sources": {"Drawings S-2.1": 480, "Anchor Schedule": 512}},
        {"field": "structural tonnage",
         "sources": {"BOQ": 547, "Scope": 547}},  # no conflict, agreement
    ])
    out2 = detect_scope_inclusion_conflicts("PRJ-2026-SOU-001", {
        "SP183_Scope.pdf": {"columns", "joists", "deck", "embeds", "canopies"},
        "SP183_BOQ.xlsx":  {"columns", "joists", "deck"},
    })
    merged = merge_conflict_lists(out1["data"], out2["data"])
    print(render_markdown(merged["data"]))
