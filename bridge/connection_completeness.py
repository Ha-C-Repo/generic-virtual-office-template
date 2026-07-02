"""Connection-information completeness gate (plan items 2.1, 2.3, 2.4, 2.5, 2.6).

ADVISORY AND STRUCTURAL ONLY. Runs before pricing. It reads what the
structural notes and the set state about connection information, flags what is
missing or ambiguous, emits LOW-confidence flags and RFIs, and lists what must
be resolved before pricing. It never sets, changes, or generates a price,
quantity, weight, or rate, and never returns a go/no-go verdict on price.
Member weights stay in bridge/aisc_validator.py and rates in
bridge/bid_rates.py.

Rules: docs/AISC-EDU-KB.md, "Ivan's Takeoff Direct Callouts" and "Doctrine
Flags". The gate refuses to price incomplete connection information and routes
general-note or blanket full-strength connections to an RFI, never a silent
assumption.

Reuses the RFI engine in bridge/auto_rfi.py. Module-level only. Pure stdlib.
PyInstaller-safe.
"""

from __future__ import annotations

from bridge import auto_rfi

# SDC values that pull in AISC 341/358 seismic detailing as real cost adders.
# Seismic thresholds CONFIRMED by Owner 2026-06-29 as the code-standard
# defaults: high-seismic on SDC C through F or R greater than 3; Houston SDC A
# or B with R = 3 is treated as complete on seismic. No longer pending Ivan.
_HIGH_SEISMIC_SDC = frozenset({"C", "D", "E", "F"})

# Building-SF sources trustworthy enough not to require an RFI.
_TRUSTED_SF_SOURCES = frozenset({"stated", "stated_on_set", "gc_confirmed"})

_DISCLAIMER = (
    "Advisory and structural only. Flags missing or ambiguous connection "
    "information and generates RFIs before pricing. Does not set or change "
    "any price, quantity, weight, or rate, and gives no go/no-go verdict on "
    "price. Member weights come from bridge/aisc_validator.py and rates from "
    "bridge/bid_rates.py. A human resolves every flag and RFI before pricing."
)


def _to_float(v):
    """Best-effort float, or None. Never raises."""
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def check_connection_completeness(context, project_id="") -> dict:
    """Inspect a connection-information context and report completeness.

    context keys (all optional; absent or None means 'not stated'):
        bracing_present: bool          - the set has braced bays / bracing scope
        transfer_forces_provided: bool
        tekla_substituting_axial: bool - forces look like full member axial
        eccentric_work_points: bool    - offset work lines with no moment listed
        sdc: str                       - Seismic Design Category (A..F)
        r_value: number
        sfrs: str                      - seismic force-resisting system
        demand_critical_welds_specified: bool
        protected_zones_specified: bool
        prequalified_358_connection: bool
        aess_present: bool
        aess_category_per_face: bool   - categories named per face per COSP 10.2
        surface_prep_class: str        - e.g. "SP6", "SP10"
        stairs_present / platforms_present / drift_bracing_present: bool
        stairs_bracing_shown: bool     - stair/platform/drift bracing detailed
        building_sf_source: str        - "stated" | "gc_confirmed" | "measured" | "assumed"
        connection_design: str         - "designed" | "delegated" | "general_note" | "blanket_full_strength"

    Returns an advisory findings dict. verdict is always None; no price is set.
    """
    ctx = context if isinstance(context, dict) else {}
    flags = []          # LOW-confidence flags
    raw_rfis = []
    blocking = []       # items that must be resolved before pricing
    seq = [0]

    def add_rfi(trigger, source, ctxsub=None):
        seq[0] += 1
        raw_rfis.append(auto_rfi.rfi_from_trigger(trigger, seq[0], source, ctxsub))

    def add_flag(item, reason, blocks):
        flags.append({"item": item, "reason": reason, "confidence": "LOW",
                      "blocks_pricing": bool(blocks)})
        if blocks:
            blocking.append(item)

    # 2.1 Transfer forces.
    if ctx.get("bracing_present") and not ctx.get("transfer_forces_provided"):
        add_rfi("missing_transfer_forces", "connection_completeness:2.1")
        add_flag("transfer_forces",
                 "Bracing present but EOR transfer forces not provided. "
                 "Transfer force does not equal member axial unless the bay is "
                 "unbraced. Request from the SER per COSP 3.1.2.", True)
    if ctx.get("tekla_substituting_axial") is True:
        add_rfi("missing_transfer_forces", "connection_completeness:2.1:axial")
        add_flag("axial_substitution",
                 "Connection forces look like full member axial. Tekla must not "
                 "substitute full member axial for EOR transfer forces.", True)
    if ctx.get("eccentric_work_points") is True:
        add_flag("eccentric_work_points",
                 "Eccentric work lines present with no moment listed. Confirm "
                 "true forces; a member up-size may be required.", False)

    # 2.3 Seismic system confirmation.
    sdc = ctx.get("sdc")
    if not sdc:
        add_rfi("seismic_system_unconfirmed", "connection_completeness:2.3")
        add_flag("seismic_system",
                 "SDC and R not stated on the structural notes. Confirm SDC, R, "
                 "SFRS, demand-critical welds, protected zones, and the AISC 358 "
                 "prequalified connection. Houston default is SDC A/B, R=3 "
                 "undetailed.", True)
    else:
        sdc_u = str(sdc).strip().upper()
        r_num = _to_float(ctx.get("r_value"))
        high_seismic = sdc_u in _HIGH_SEISMIC_SDC or (r_num is not None and r_num > 3)
        if high_seismic:
            missing = []
            if not ctx.get("sfrs"):
                missing.append("SFRS")
            if not ctx.get("demand_critical_welds_specified"):
                missing.append("demand-critical welds")
            if not ctx.get("protected_zones_specified"):
                missing.append("protected zones")
            if not ctx.get("prequalified_358_connection"):
                missing.append("AISC 358 prequalified connection")
            if missing:
                add_rfi("seismic_detailing_incomplete",
                        "connection_completeness:2.3",
                        {"sdc": sdc_u,
                         "r": ctx.get("r_value") if ctx.get("r_value") not in (None, "") else "?",
                         "missing": ", ".join(missing)})
                add_flag("seismic_detailing",
                         f"Seismic set (SDC {sdc_u}) missing: {', '.join(missing)}. "
                         "Real cost adders (AISC 341/358, AWS D1.8).", True)

    # 2.4 AESS category per face.
    if ctx.get("aess_present") and not ctx.get("aess_category_per_face"):
        add_rfi("aess_category_unspecified", "connection_completeness:2.4")
        add_flag("aess_category",
                 "AESS referenced but category per face not stated per COSP 10.2. "
                 "AESS escalates labor, not tonnage; confirm before any blast or "
                 "finish line is priced.", False)

    # 2.5 Surface-prep class.
    if not ctx.get("surface_prep_class"):
        add_rfi("surface_prep_unconfirmed", "connection_completeness:2.5")
        add_flag("surface_prep",
                 "Surface-prep class not stated. SP 6 commercial vs SP 10 "
                 "near-white drives the blast line. LOW until confirmed.", False)

    # 2.5 Stair / platform / drift bracing not shown.
    has_secondary = any(ctx.get(k) for k in
                        ("stairs_present", "platforms_present", "drift_bracing_present"))
    if has_secondary and not ctx.get("stairs_bracing_shown"):
        add_rfi("hidden_bracing_not_shown", "connection_completeness:2.5")
        add_flag("hidden_bracing",
                 "Stair, platform, or drift bracing not shown. If it is not "
                 "shown it is not in the price. Confirm scope and details.", False)

    # 2.6 SF and gross-area confirmation.
    sf_src = str(ctx.get("building_sf_source") or "").strip().lower()
    if sf_src not in _TRUSTED_SF_SOURCES:
        add_rfi("sf_gross_area_confirmation", "connection_completeness:2.6")
        add_flag("gross_sf",
                 "Gross SF not stated on the set or GC-confirmed. SF is the "
                 "controlling input. Estimate is ROM only until confirmed.", True)

    # 2.6 Drawing-completeness: general-note / blanket full-strength connections.
    cd = str(ctx.get("connection_design") or "").strip().lower()
    if cd in ("general_note", "blanket_full_strength"):
        add_rfi("connection_general_note_only", "connection_completeness:2.6")
        add_flag("connection_information",
                 "Connections given by general note or blanket full-strength "
                 "spec, not designed connections with forces. Do not price by "
                 "silent assumption; route to RFI.", True)

    rfi_result = auto_rfi.build_rfi_list(project_id or "CONN-CHECK", raw_rfis)
    rfi_payload = rfi_result.get("data") if rfi_result.get("ok") else None
    rfi_total = (rfi_payload or {}).get("summary", {}).get("total", 0)

    return {
        "advisory": True,
        "structural_only": True,
        "generates_numbers": False,
        "connection_info_complete": len(blocking) == 0,
        "must_resolve_before_pricing": blocking,
        "low_confidence_flags": flags,
        "rfis": rfi_payload,
        "rfi_markdown": auto_rfi.render_markdown(rfi_payload) if rfi_payload else "",
        "summary": {
            "flag_count": len(flags),
            "blocking_count": len(blocking),
            "rfi_count": rfi_total,
        },
        "verdict": None,
        "disclaimer": _DISCLAIMER,
    }
