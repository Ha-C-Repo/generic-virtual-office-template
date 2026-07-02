"""
REQUIREMENTS REGISTER - REQ-001..N output schema and emitter.

Derived from Operum.io tender-analysis review (2026-05-28). Operum
extracts every priceable requirement from a tender package, numbers
them REQ-001..N, groups by trade category, and source-cites each one.
Our bid pipeline currently emits prose under "Scope summary"; this
module replaces that with a structured register.

Goal: a checklist Owner and Ivan can verify line by line before
pricing locks. Every row tied back to a source document + page.

Rules (Tier 1 + project CLAUDE.md):
  - Module-level only. No classes inside functions.
  - Pure Python stdlib. No new deps. Compatible with PyInstaller frozen
    Python 3.13 build.
  - All Bridge-facing entry points return _ok({...}) or _err("...").
  - Source citations: filename + page. If page unknown, emit "page TBD"
    not "page 1" (per "verify, do not generate" rule).
  - Confidence per row: "EXPLICIT" (text directly quoted), "INFERRED"
    (derived from a related fact), "ASSUMED" (default applied because
    nothing in source). Never silently default.

Output schema (JSON-serializable):

{
    "register_id": "REG-PRJ-2026-XXX-NNN",
    "project_id": "PRJ-2026-XXX-NNN",
    "generated_at": "2026-05-28T15:42:00Z",
    "source_documents": [
        {"file": "SP183_Scope_of_Works.pdf", "pages": 12},
        {"file": "SP183_BOQ.xlsx", "pages": null}
    ],
    "categories": [
        "PRELIMINARIES",
        "STRUCTURAL_STEEL",
        "JOISTS",
        "DECK",
        "MISC_METALS",
        "ANCHORS",
        "CONNECTIONS",
        "STAIRS_RAILS",
        "EMBEDS",
        "CANOPIES",
        "DRAWINGS_STAGE_ADDER",
        "COMMERCIAL_CONTRACT"
    ],
    "items": [
        {
            "id": "REQ-001",
            "category": "PRELIMINARIES",
            "description": "Mobilization and site setup",
            "quantity_basis": "Lump sum",
            "confidence": "EXPLICIT",
            "source_citations": [
                {"file": "SP183_Scope_of_Works.pdf", "page": 2, "section": "1.2"}
            ]
        }
    ],
    "summary": {
        "total_items": 44,
        "explicit_count": 38,
        "inferred_count": 4,
        "assumed_count": 2,
        "categories_used": 8
    }
}

Use it as a JSON sibling to the bid-intel package, NOT inside the
client proposal PDF. Internal artifact for Ivan's verification gate.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Iterable

# Canonical category list. Order = display order on the register output.
# Add to this list when Ivan signs off on a new trade category.
CATEGORIES_CANONICAL = [
    "PRELIMINARIES",
    "STRUCTURAL_STEEL",
    "JOISTS",
    "DECK",
    "MISC_METALS",
    "ANCHORS",
    "CONNECTIONS",
    "STAIRS_RAILS",
    "EMBEDS",
    "CANOPIES",
    "BRACING",
    "BASE_PLATES",
    "DRAWINGS_STAGE_ADDER",
    "COMMERCIAL_CONTRACT",
    "OTHER",
]

# Confidence values. Order = severity ascending.
CONFIDENCE_VALUES = ("EXPLICIT", "INFERRED", "ASSUMED")


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_item(item):
    """Returns (is_valid, error_message_or_None)."""
    required = ("id", "category", "description", "quantity_basis",
                "confidence", "source_citations")
    for k in required:
        if k not in item:
            return (False, f"item missing required key: {k}")
    if item["confidence"] not in CONFIDENCE_VALUES:
        return (False, f"confidence must be one of {CONFIDENCE_VALUES}, got {item['confidence']!r}")
    if item["category"] not in CATEGORIES_CANONICAL:
        return (False, f"category {item['category']!r} not in CATEGORIES_CANONICAL. Add to list first.")
    if not isinstance(item["source_citations"], list):
        return (False, "source_citations must be a list")
    for cit in item["source_citations"]:
        if "file" not in cit:
            return (False, "every source_citation needs a 'file' key")
    return (True, None)


def normalize_id(seq_num):
    """Return REQ-001 for 1, REQ-044 for 44, etc. Pads to 3 digits."""
    if not isinstance(seq_num, int) or seq_num < 1:
        raise ValueError("seq_num must be a positive integer")
    return f"REQ-{seq_num:03d}"


def build_register(project_id, source_documents, raw_items):
    """Construct a requirements register from a list of raw extracted items.

    project_id: PRJ-YYYY-XXX-NNN bid id
    source_documents: list of {"file": str, "pages": int|None}
    raw_items: list of dicts. Each must have:
        category, description, quantity_basis, confidence, source_citations.
        id is auto-assigned in REG sequence order, ignore any caller-supplied id.

    Returns the canonical _ok/_err shape.
    """
    if not isinstance(project_id, str) or not project_id:
        return _err("project_id must be a non-empty string")
    if not isinstance(source_documents, list):
        return _err("source_documents must be a list")
    if not isinstance(raw_items, list):
        return _err("raw_items must be a list")

    # Group items by canonical category order, then sequence within group.
    by_cat = {cat: [] for cat in CATEGORIES_CANONICAL}
    for raw in raw_items:
        cat = raw.get("category", "OTHER")
        if cat not in by_cat:
            cat = "OTHER"
        by_cat[cat].append(raw)

    seq = 0
    items_out = []
    for cat in CATEGORIES_CANONICAL:
        for raw in by_cat[cat]:
            seq += 1
            item = {
                "id": normalize_id(seq),
                "category": cat,
                "description": raw.get("description", ""),
                "quantity_basis": raw.get("quantity_basis", "Not stated"),
                "confidence": raw.get("confidence", "ASSUMED"),
                "source_citations": raw.get("source_citations", []),
            }
            ok, err = _validate_item(item)
            if not ok:
                return _err(f"item {item['id']} invalid: {err}")
            items_out.append(item)

    summary = {
        "total_items": len(items_out),
        "explicit_count": sum(1 for i in items_out if i["confidence"] == "EXPLICIT"),
        "inferred_count": sum(1 for i in items_out if i["confidence"] == "INFERRED"),
        "assumed_count": sum(1 for i in items_out if i["confidence"] == "ASSUMED"),
        "categories_used": sum(1 for cat in CATEGORIES_CANONICAL if by_cat[cat]),
    }

    register = {
        "register_id": f"REG-{project_id}",
        "project_id": project_id,
        "generated_at": _utc_now_iso(),
        "source_documents": source_documents,
        "categories": [c for c in CATEGORIES_CANONICAL if by_cat[c]],
        "items": items_out,
        "summary": summary,
    }
    return _ok(register)


def render_markdown(register):
    """Pretty-print a register as Markdown for inclusion in the bid-intel
    package. Use this for the human-readable handoff to Ivan; keep the
    JSON for machine consumption.
    """
    if not isinstance(register, dict) or "items" not in register:
        return "INVALID_REGISTER"
    lines = []
    lines.append(f"# Requirements Register: {register.get('register_id', 'UNKNOWN')}")
    lines.append("")
    lines.append(f"- Project: {register.get('project_id', 'UNKNOWN')}")
    lines.append(f"- Generated: {register.get('generated_at', 'UNKNOWN')}")
    s = register.get("summary", {})
    lines.append(f"- Total items: {s.get('total_items', 0)} "
                 f"({s.get('explicit_count', 0)} explicit, "
                 f"{s.get('inferred_count', 0)} inferred, "
                 f"{s.get('assumed_count', 0)} assumed)")
    lines.append("")
    lines.append("## Source Documents")
    for doc in register.get("source_documents", []):
        pages = doc.get("pages")
        page_part = f" ({pages} pages)" if pages else ""
        lines.append(f"- {doc.get('file', 'unknown')}{page_part}")
    lines.append("")

    by_cat = {}
    for item in register.get("items", []):
        by_cat.setdefault(item["category"], []).append(item)

    for cat in register.get("categories", []):
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat} ({len(items)})")
        lines.append("")
        lines.append("| ID | Description | Quantity Basis | Confidence | Source |")
        lines.append("|----|-------------|----------------|------------|--------|")
        for item in items:
            cites = "; ".join(
                f"{c.get('file', '?')} p{c.get('page', 'TBD')}"
                for c in item.get("source_citations", [])
            ) or "_no source_"
            desc = item["description"].replace("|", "\\|")
            qb = item["quantity_basis"].replace("|", "\\|")
            lines.append(f"| {item['id']} | {desc} | {qb} | {item['confidence']} | {cites} |")
        lines.append("")
    return "\n".join(lines)


def to_json(register, indent=2):
    """JSON-serialize a register. Wraps json.dumps with stable defaults."""
    return json.dumps(register, indent=indent, sort_keys=False)


def empty_register(project_id):
    """Return an empty but valid register for use when no items have
    been extracted yet. Useful as a stub Cowork writes early in the
    pipeline before extractors run."""
    return _ok({
        "register_id": f"REG-{project_id}",
        "project_id": project_id,
        "generated_at": _utc_now_iso(),
        "source_documents": [],
        "categories": [],
        "items": [],
        "summary": {
            "total_items": 0,
            "explicit_count": 0,
            "inferred_count": 0,
            "assumed_count": 0,
            "categories_used": 0,
        }
    })


# Smoke-test entry point. Not called by the Bridge.
if __name__ == "__main__":
    sample = build_register(
        project_id="PRJ-2026-SOU-001",
        source_documents=[
            {"file": "SP183_Scope.pdf", "pages": 12},
            {"file": "SP183_BOQ.xlsx", "pages": None},
        ],
        raw_items=[
            {
                "category": "STRUCTURAL_STEEL",
                "description": "Columns, beams, girders to AISC v16.0",
                "quantity_basis": "547 tons (from drawing schedule)",
                "confidence": "EXPLICIT",
                "source_citations": [{"file": "SP183_Scope.pdf", "page": 4}],
            },
            {
                "category": "JOISTS",
                "description": "Bar joists, K-series",
                "quantity_basis": "280 tons",
                "confidence": "EXPLICIT",
                "source_citations": [{"file": "SP183_Scope.pdf", "page": 5}],
            },
            {
                "category": "DECK",
                "description": "Type B roof deck, painted",
                "quantity_basis": "231,400 SF",
                "confidence": "INFERRED",
                "source_citations": [{"file": "SP183_Scope.pdf", "page": 6}],
            },
            {
                "category": "EMBEDS",
                "description": "Embed plates for tilt-wall connections",
                "quantity_basis": "Not stated in drawings reviewed",
                "confidence": "ASSUMED",
                "source_citations": [],
            },
        ]
    )
    if not sample["ok"]:
        print("ERROR:", sample["error"])
    else:
        reg = sample["data"]
        print(render_markdown(reg))
        print()
        print("--- JSON ---")
        print(to_json(reg))
