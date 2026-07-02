"""
AUTO RFI - Generate RFI/clarification questions from extracted bid data.

Derived from Operum.io review (2026-05-28). Operum auto-generates a
list of clarifications for the GC, grouped by category, prioritized
High/Medium/Low. Their sample produced 28 RFIs for a single tender.

Our existing pipeline emits RFIs only from Gate 4 FLAGs (see
skills/cowork-bid-estimate/SKILL.md step 16). This module broadens
RFI generation across six categories Operum surfaced, and adds
priority tags so Owner knows which RFIs are price-blockers vs
nice-to-have.

Categories (Operum schema, US-adapted):
  - PRICING_COMMERCIAL    pricing structure, payment terms, escalation
  - SCOPE_CLARIFICATION   what's in vs out of our scope (steel sub)
  - DESIGN_RESPONSIBILITY who designs what, who certifies what
  - TECHNICAL_SPECS       materials, finishes, performance criteria
  - PROGRAM_ACCESS        site logistics, working hours, deliveries
  - DRAWING_DISCREPANCIES conflicts between sheets, sets, addenda

Priority:
  - HIGH    must answer before pricing locks
  - MEDIUM  affects price within +/- 5 percent
  - LOW     nice to know, no material price impact

Rules:
  - Module-level only.
  - Pure stdlib. PyInstaller-safe.
  - _ok / _err return shape for Bridge entry points.
  - Every RFI carries a source (which extractor or gate raised it)
    so Owner can trace it back. No anonymous RFIs.
"""

from __future__ import annotations
from datetime import datetime, timezone

CATEGORIES = (
    "PRICING_COMMERCIAL",
    "SCOPE_CLARIFICATION",
    "DESIGN_RESPONSIBILITY",
    "TECHNICAL_SPECS",
    "PROGRAM_ACCESS",
    "DRAWING_DISCREPANCIES",
)

PRIORITIES = ("HIGH", "MEDIUM", "LOW")


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_rfi(rfi):
    required = ("id", "category", "priority", "question", "source")
    for k in required:
        if k not in rfi:
            return (False, f"rfi missing required key: {k}")
    if rfi["category"] not in CATEGORIES:
        return (False, f"category {rfi['category']!r} not in {CATEGORIES}")
    if rfi["priority"] not in PRIORITIES:
        return (False, f"priority {rfi['priority']!r} not in {PRIORITIES}")
    if not isinstance(rfi["question"], str) or len(rfi["question"]) < 10:
        return (False, "question must be a string of >= 10 chars")
    return (True, None)


def normalize_id(seq_num):
    if not isinstance(seq_num, int) or seq_num < 1:
        raise ValueError("seq_num must be positive integer")
    return f"RFI-{seq_num:03d}"


# Canned RFI templates indexed by trigger condition. Extractors call
# rfi_from_trigger("missing_embed_plates", context={...}) to get a
# pre-filled RFI rather than write the question from scratch every time.
RFI_TEMPLATES = {
    # SCOPE_CLARIFICATION
    "missing_embed_plates": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "HIGH",
        "question_template": (
            "Embed plates for tilt-wall connections are not visible "
            "in the drawings reviewed. Are embed plates in our steel "
            "scope or supplied by the wall panel subcontractor?"
        ),
    },
    "missing_canopy_framing": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "MEDIUM",
        "question_template": (
            "No canopy detail visible in extracted pages. Is canopy "
            "framing required, and if so is it in steel scope or by Others?"
        ),
    },
    "missing_caged_ladders": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "MEDIUM",
        "question_template": (
            "Caged ladders to roof not shown in drawings reviewed. "
            "Are caged roof-access ladders in our scope?"
        ),
    },
    "missing_lintels": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "MEDIUM",
        "question_template": (
            "No lintel schedule visible. Are masonry/overhead-door "
            "lintels in steel scope or by Others?"
        ),
    },
    "missing_deck_closures": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "MEDIUM",
        "question_template": (
            "Drawings do not show deck closure details at perimeter. "
            "Are perimeter deck closures, pour stops, and edge angles "
            "in our scope?"
        ),
    },
    # TECHNICAL_SPECS
    "joist_series_unclear": {
        "category": "TECHNICAL_SPECS",
        "priority": "HIGH",
        "question_template": (
            "Joist tags shown ({tags}) sit outside the expected series "
            "for {building_type}. Please confirm series and depth, "
            "or supply joist schedule."
        ),
    },
    "anchor_diameter_unclear": {
        "category": "TECHNICAL_SPECS",
        "priority": "HIGH",
        "question_template": (
            "Anchor rod schedule does not state diameter. We assume "
            "3/4 inch UNO per Ivan calibration. Please confirm or "
            "supply the schedule."
        ),
    },
    "deck_finish_unclear": {
        "category": "TECHNICAL_SPECS",
        "priority": "MEDIUM",
        "question_template": (
            "Roof deck finish (painted, galvanized, primed) is not "
            "stated. We assume painted Type B UNO. Please confirm."
        ),
    },
    # DESIGN_RESPONSIBILITY
    "connection_design_responsibility": {
        "category": "DESIGN_RESPONSIBILITY",
        "priority": "HIGH",
        "question_template": (
            "Please confirm whether connection design is by EOR or "
            "delegated to fabricator. Connection allowance assumes "
            "delegated design at {pct}% of structural tonnage."
        ),
    },
    "fire_protection_responsibility": {
        "category": "DESIGN_RESPONSIBILITY",
        "priority": "MEDIUM",
        "question_template": (
            "Fire protection / intumescent coating on steel - by Others "
            "(painter) or in our scope? Specification basis required."
        ),
    },
    # PRICING_COMMERCIAL
    "boq_lump_sum_or_remeasure": {
        "category": "PRICING_COMMERCIAL",
        "priority": "HIGH",
        "question_template": (
            "Please confirm whether quoted quantities are guaranteed "
            "and will be remeasured at close-out, or whether the "
            "contract is firm lump sum with contractor carrying full "
            "quantity risk."
        ),
    },
    "escalation_mechanism": {
        "category": "PRICING_COMMERCIAL",
        "priority": "MEDIUM",
        "question_template": (
            "Please confirm whether the contract includes rise/fall "
            "(material escalation) and the applicable mechanism/indices, "
            "and identify any provisional sums and their basis."
        ),
    },
    "retention_terms": {
        "category": "PRICING_COMMERCIAL",
        "priority": "MEDIUM",
        "question_template": (
            "Retention/retainage terms not stated in extracted documents. "
            "Please confirm percentage and release schedule."
        ),
    },
    # PROGRAM_ACCESS
    "site_access_constraints": {
        "category": "PROGRAM_ACCESS",
        "priority": "MEDIUM",
        "question_template": (
            "Please confirm site access constraints (working hours, "
            "delivery restrictions, crane permits, traffic management) "
            "that affect erection programme and preliminaries."
        ),
    },
    "erection_sequence_constraint": {
        "category": "PROGRAM_ACCESS",
        "priority": "MEDIUM",
        "question_template": (
            "Please confirm whether tilt-wall panel sequencing dictates "
            "structural steel erection sequence. Critical for crane mob "
            "and re-mob allowance."
        ),
    },
    # DRAWING_DISCREPANCIES
    "boq_vs_scope_conflict": {
        "category": "DRAWING_DISCREPANCIES",
        "priority": "HIGH",
        "question_template": (
            "BOQ and Scope of Works disagree on {item}: BOQ says "
            "{boq_value}, Scope says {scope_value}. Please confirm "
            "which governs for pricing."
        ),
    },
    "addendum_supersedes": {
        "category": "DRAWING_DISCREPANCIES",
        "priority": "HIGH",
        "question_template": (
            "Addendum {addendum_num} appears to modify {item} from "
            "{old_value} to {new_value}. Please confirm addendum is "
            "the controlling document."
        ),
    },
    # ── Connection-information completeness (plan items 2.1/2.3/2.4/2.5/2.6) ──
    # Source: docs/AISC-EDU-KB.md, Ivan's Takeoff Direct Callouts.
    "missing_transfer_forces": {
        "category": "DESIGN_RESPONSIBILITY",
        "priority": "HIGH",
        "question_template": (
            "The set shows bracing but the connection transfer forces are "
            "not provided. Transfer force does not equal member axial unless "
            "the bay is unbraced. Please provide the true transfer forces "
            "from the SER per COSP Section 3.1.2. Full member axial must not "
            "be substituted."
        ),
    },
    "seismic_system_unconfirmed": {
        "category": "TECHNICAL_SPECS",
        "priority": "HIGH",
        "question_template": (
            "Seismic Design Category and R value are not stated on the "
            "structural notes. Please confirm SDC, R, the seismic "
            "force-resisting system, demand-critical welds, protected zones, "
            "and the prequalified AISC 358 connection before pricing. Houston "
            "work is commonly SDC A or B with R=3 undetailed; confirm if this "
            "set differs."
        ),
    },
    "seismic_detailing_incomplete": {
        "category": "TECHNICAL_SPECS",
        "priority": "HIGH",
        "question_template": (
            "This set is seismic (SDC {sdc}, R={r}) but {missing} are not "
            "specified. Please confirm so connection labor and detailing "
            "(AISC 341/358, AWS D1.8) can be priced."
        ),
    },
    "aess_category_unspecified": {
        "category": "TECHNICAL_SPECS",
        "priority": "MEDIUM",
        "question_template": (
            "Drawings reference AESS but do not state the category per face "
            "per COSP Section 10.2 (category 1 within touch, 2 within 20 ft, "
            "3 above 20 ft). AESS escalates labor, not tonnage. Please confirm "
            "the category and the items (welds ground smooth, mill-mark "
            "removal, tighter coping) before any blast or finish line is priced."
        ),
    },
    "surface_prep_unconfirmed": {
        "category": "TECHNICAL_SPECS",
        "priority": "MEDIUM",
        "question_template": (
            "Surface-preparation class is not stated. Please confirm SP 6 "
            "commercial blast versus SP 10 near-white; this drives the blast "
            "line item. Carried LOW until confirmed."
        ),
    },
    "hidden_bracing_not_shown": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "MEDIUM",
        "question_template": (
            "Stair, platform, or drift bracing connections are not shown on "
            "the set reviewed. If it is not shown it is not in the price. "
            "Please confirm whether these are in our scope and provide details."
        ),
    },
    "sf_gross_area_confirmation": {
        "category": "SCOPE_CLARIFICATION",
        "priority": "HIGH",
        "question_template": (
            "Gross square footage is not stated on the set or GC-confirmed. "
            "SF is the controlling input that scales the bid. Please confirm "
            "the gross area; a structural-only subset rarely states it. Until "
            "confirmed the estimate is ROM only."
        ),
    },
    "connection_general_note_only": {
        "category": "DESIGN_RESPONSIBILITY",
        "priority": "HIGH",
        "question_template": (
            "Connections are given by general note or a blanket full-strength "
            "specification rather than designed connections with forces. "
            "Please provide connection forces or confirm delegated-design "
            "scope. We do not price general-note or blanket full-strength "
            "connections by silent assumption."
        ),
    },
    # ── Connection take-off / allowance (plan item 1.1) ──
    "connection_framing_type_undetermined": {
        "category": "DESIGN_RESPONSIBILITY",
        "priority": "HIGH",
        "question_template": (
            "The structural framing type is not clearly determinable from the "
            "set, so the connection-material allowance percentage cannot be "
            "selected. Please confirm the framing system (one of: {types}) so "
            "the connection allowance can be sized from the locked calibration."
        ),
    },
}


def rfi_from_trigger(trigger_key, seq_num, source, context=None):
    """Build an RFI dict from a template trigger key.

    trigger_key: one of RFI_TEMPLATES keys
    seq_num: sequence number (gets formatted as RFI-NNN)
    source: which extractor / gate raised this (string)
    context: dict for template substitution (e.g. {"tags": "K10", "building_type": "tilt_wall"})

    Returns a single RFI dict, not _ok/_err wrapped. Caller assembles
    a list and then calls build_rfi_list().
    """
    if trigger_key not in RFI_TEMPLATES:
        raise KeyError(f"unknown trigger {trigger_key!r}, see RFI_TEMPLATES")
    tmpl = RFI_TEMPLATES[trigger_key]
    ctx = context or {}
    try:
        question = tmpl["question_template"].format(**ctx)
    except KeyError as e:
        question = tmpl["question_template"] + f"  [missing template var: {e}]"
    return {
        "id": normalize_id(seq_num),
        "category": tmpl["category"],
        "priority": tmpl["priority"],
        "question": question,
        "source": source,
        "trigger_key": trigger_key,
    }


def build_rfi_list(project_id, raw_rfis):
    """Assemble final RFI list, dedupe, sort by priority then category.

    project_id: PRJ-YYYY-XXX-NNN bid id
    raw_rfis: list of RFI dicts (from rfi_from_trigger or hand-crafted)

    Returns _ok({...}) with full payload, or _err on validation fail.
    """
    if not isinstance(project_id, str) or not project_id:
        return _err("project_id must be a non-empty string")
    if not isinstance(raw_rfis, list):
        return _err("raw_rfis must be a list")

    # Dedupe by (category, question) tuple. Same question raised by
    # two extractors only fires once.
    seen = set()
    deduped = []
    for r in raw_rfis:
        key = (r.get("category"), r.get("question"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    # Re-sequence after dedupe so IDs are gapless.
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    category_order = {c: i for i, c in enumerate(CATEGORIES)}
    deduped.sort(key=lambda r: (
        priority_order.get(r.get("priority", "LOW"), 99),
        category_order.get(r.get("category", "OTHER"), 99),
    ))
    items_out = []
    for i, r in enumerate(deduped, start=1):
        item = dict(r)
        item["id"] = normalize_id(i)
        ok, err = _validate_rfi(item)
        if not ok:
            return _err(f"rfi {item.get('id', '?')} invalid: {err}")
        items_out.append(item)

    summary = {
        "total": len(items_out),
        "high": sum(1 for r in items_out if r["priority"] == "HIGH"),
        "medium": sum(1 for r in items_out if r["priority"] == "MEDIUM"),
        "low": sum(1 for r in items_out if r["priority"] == "LOW"),
        "by_category": {
            cat: sum(1 for r in items_out if r["category"] == cat)
            for cat in CATEGORIES
        },
    }
    payload = {
        "rfi_list_id": f"RFI-LIST-{project_id}",
        "project_id": project_id,
        "generated_at": _utc_now_iso(),
        "recommended_submission_window_days": 7,
        "items": items_out,
        "summary": summary,
    }
    return _ok(payload)


def render_markdown(rfi_payload):
    """Pretty-print the RFI list as Markdown. Drops straight into the
    bid-intel handoff package or an email to the GC."""
    if not isinstance(rfi_payload, dict) or "items" not in rfi_payload:
        return "INVALID_RFI_LIST"
    lines = []
    lines.append(f"# RFIs and Clarifications: {rfi_payload.get('rfi_list_id', 'UNKNOWN')}")
    lines.append("")
    s = rfi_payload.get("summary", {})
    lines.append(
        f"- Total: {s.get('total', 0)} "
        f"({s.get('high', 0)} HIGH, {s.get('medium', 0)} MEDIUM, "
        f"{s.get('low', 0)} LOW)"
    )
    lines.append(
        f"- Recommended submission window: within "
        f"{rfi_payload.get('recommended_submission_window_days', 7)} days of tender release."
    )
    lines.append("")
    lines.append("> These clarifications should be submitted as formal "
                 "RFIs to the GC. Some items may significantly impact "
                 "pricing and program assumptions.")
    lines.append("")
    by_cat = {}
    for item in rfi_payload.get("items", []):
        by_cat.setdefault(item["category"], []).append(item)
    for cat in CATEGORIES:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat.replace('_', ' ').title()}")
        lines.append("")
        for it in items:
            lines.append(f"**{it['id']}** [{it['priority']}]  ")
            lines.append(f"{it['question']}")
            lines.append(f"_source: {it['source']}_")
            lines.append("")
    return "\n".join(lines)


# Smoke test
if __name__ == "__main__":
    raw = [
        rfi_from_trigger("missing_embed_plates", 1, source="gate4_scope"),
        rfi_from_trigger("missing_canopy_framing", 2, source="gate4_scope"),
        rfi_from_trigger("missing_embed_plates", 99, source="other"),  # dedupe test
        rfi_from_trigger("joist_series_unclear", 3, source="joist_check",
                          context={"tags": "K10, K12", "building_type": "tilt_wall"}),
        rfi_from_trigger("connection_design_responsibility", 4,
                          source="virtual_owner", context={"pct": 8}),
        rfi_from_trigger("boq_lump_sum_or_remeasure", 5, source="contract_extractor"),
    ]
    out = build_rfi_list("PRJ-2026-SOU-001", raw)
    if not out["ok"]:
        print("ERROR:", out["error"])
    else:
        print(render_markdown(out["data"]))
