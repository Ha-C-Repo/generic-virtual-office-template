"""
SUBMIT VERDICT - SUBMIT / DO_NOT_SUBMIT roll-up for the bid pipeline.

Derived from Operum.io review (2026-05-28). Operum's Submission
Analysis emits a single SUBMIT / DO_NOT_SUBMIT verdict with financial
exposure and a top-3 reasons list.

Our existing bid_sanity_gates.run_gates() already emits a `decision`
field with three values:
  - "GO - READY TO SUBMIT"
  - "CAUTION - REVIEW RECOMMENDED"
  - "BLOCKED - MANUAL REVIEW"

That's close but not Operum-shaped. Owner has to read all five gate
results to decide. This module rolls them up into:
  - verdict: SUBMIT / SUBMIT_WITH_CAUTION / DO_NOT_SUBMIT
  - top_reasons: list of the 3 most-impactful gate findings
  - financial_exposure_usd: estimated $ impact of unresolved flags
  - one_line: terse Owner-voice summary

Built as a standalone WRAPPER around the existing run_gates() output
so this patch is purely additive. Once Owner has verified it on a
real bid, the wrapper can be folded into run_gates() itself.

Rules:
  - Module-level only.
  - Pure stdlib.
  - _ok / _err for Bridge entry points.
  - Financial exposure is an ESTIMATE based on default impact factors
    per gate flag type. Tagged TAG_INFERRED, never represented as
    precise.
  - No em-dashes in output strings (CLAUDE.md hard rule 7).
"""

from __future__ import annotations

VERDICT_SUBMIT = "SUBMIT"
VERDICT_SUBMIT_WITH_CAUTION = "SUBMIT_WITH_CAUTION"
VERDICT_DO_NOT_SUBMIT = "DO_NOT_SUBMIT"

ALL_VERDICTS = (VERDICT_SUBMIT, VERDICT_SUBMIT_WITH_CAUTION, VERDICT_DO_NOT_SUBMIT)

# Default dollar-impact factors per gate-flag class. These are rough
# heuristics until Owner tunes them against real win/loss data.
# All values in USD.
DEFAULT_IMPACT_USD = {
    "gate1_joist_low":           5_000,
    "gate1_joist_block":         15_000,
    "gate2_tonnage_flag":        25_000,
    "gate2_tonnage_block":       75_000,
    "gate2_tonnage_caution":     10_000,
    "gate3_price_flag":          30_000,
    "gate3_price_block":        100_000,
    "gate3_price_caution":       12_000,
    "gate4_scope_flag_per_item": 8_000,
    "gate4_scope_block":         50_000,
    "gate5_ratio_warn":          5_000,
    "gate5_ratio_corrected":     0,
    "rfi_high_unresolved":       10_000,
    "rfi_medium_unresolved":     3_000,
    "conflict_hard_unresolved":  20_000,
}


def _ok(payload):
    return {"ok": True, "data": payload}


def _err(message):
    return {"ok": False, "error": message}


def _impact_for_gate(gate_result):
    """Translate a gate result into a (reason_string, dollar_estimate)
    tuple. Returns (None, 0) for clean PASS results."""
    gate_num = gate_result.get("gate")
    status = gate_result.get("status", "PASS")
    name = gate_result.get("name", f"Gate {gate_num}")
    warn = gate_result.get("warning") or ""

    if status in ("PASS", "OK", "HIGH"):
        return (None, 0)

    if gate_num == 1:
        if status == "LOW":
            return (f"Gate 1 ({name}): joist count unverifiable from geometry. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate1_joist_low"])
        if status == "BLOCK":
            return (f"Gate 1 ({name}): BLOCK. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate1_joist_block"])

    if gate_num == 2:
        val = gate_result.get("value", "")
        if status == "BLOCK":
            return (f"Gate 2 ({name}): tonnage {val} below floor. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate2_tonnage_block"])
        if status == "FLAG":
            return (f"Gate 2 ({name}): tonnage {val} above ceiling. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate2_tonnage_flag"])
        if status == "CAUTION":
            return (f"Gate 2 ({name}): tonnage {val} near boundary. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate2_tonnage_caution"])

    if gate_num == 3:
        val = gate_result.get("value", "")
        if status == "BLOCK":
            return (f"Gate 3 ({name}): price {val} below floor. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate3_price_block"])
        if status == "FLAG":
            return (f"Gate 3 ({name}): price {val} above ceiling. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate3_price_flag"])
        if status == "CAUTION":
            return (f"Gate 3 ({name}): price {val} near boundary. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate3_price_caution"])

    if gate_num == 4:
        # Gate 4 reports missing scope items in `warning`. Try to count.
        missing_items = 0
        if warn:
            # Heuristic: count comma-separated items in the warning text.
            missing_items = max(1, warn.count(",") + 1)
        if status == "BLOCK":
            return (f"Gate 4 ({name}): BLOCK. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate4_scope_block"])
        if status == "FLAG":
            est = missing_items * DEFAULT_IMPACT_USD["gate4_scope_flag_per_item"]
            return (f"Gate 4 ({name}): {missing_items} scope items missing or unconfirmed. {warn}".strip(),
                    est)

    if gate_num == 5:
        if status == "CORRECTED":
            return (f"Gate 5 ({name}): auto-corrected ratio. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate5_ratio_corrected"])
        if status in ("FLAG", "WARN", "CAUTION"):
            return (f"Gate 5 ({name}): {status}. {warn}".strip(),
                    DEFAULT_IMPACT_USD["gate5_ratio_warn"])

    # Fallback for any other non-PASS status.
    return (f"Gate {gate_num} ({name}): {status}. {warn}".strip(), 5_000)


def _verdict_from_gates(gate_results, confidence):
    """Pick the verdict from gate results + confidence score."""
    if any(g.get("status") == "BLOCK" for g in gate_results):
        return VERDICT_DO_NOT_SUBMIT
    if confidence < 60:
        return VERDICT_DO_NOT_SUBMIT
    if confidence < 80:
        return VERDICT_SUBMIT_WITH_CAUTION
    if any(g.get("status") in ("FLAG", "LOW") for g in gate_results):
        return VERDICT_SUBMIT_WITH_CAUTION
    return VERDICT_SUBMIT


def _one_line(verdict, top_reasons, exposure_usd):
    """Owner voice. Short. Specific numbers. No filler."""
    if verdict == VERDICT_SUBMIT:
        return f"SUBMIT. Clean across all gates. Exposure estimate ${exposure_usd:,}."
    if verdict == VERDICT_SUBMIT_WITH_CAUTION:
        top = top_reasons[0] if top_reasons else "see gate results"
        return f"SUBMIT WITH CAUTION. Exposure ${exposure_usd:,}. Top issue: {top}"
    # DO NOT SUBMIT
    top = top_reasons[0] if top_reasons else "see gate results"
    return f"DO NOT SUBMIT. Exposure ${exposure_usd:,}. Top issue: {top}"


def from_run_gates(run_gates_output,
                   rfi_summary=None,
                   conflict_summary=None):
    """Wrap the existing bid_sanity_gates.run_gates() output with an
    Operum-style verdict.

    run_gates_output: the dict returned by run_gates(data). Must have
        keys 'gates', 'confidence', 'blocked', 'decision'.
    rfi_summary: optional dict like
        {"high": 2, "medium": 4, "low": 1, "unresolved_high": 1}
        from auto_rfi.build_rfi_list(...)["data"]["summary"]
    conflict_summary: optional dict like
        {"hard": 1, "soft": 0, "info": 2}
        from cross_doc_conflicts.merge_conflict_lists(...)["data"]["summary"]

    Returns _ok({...}) with verdict, top_reasons, financial_exposure_usd,
    one_line, and the original run_gates output preserved under
    `_underlying`.
    """
    if not isinstance(run_gates_output, dict):
        return _err("run_gates_output must be a dict")
    gates = run_gates_output.get("gates")
    if not isinstance(gates, list):
        return _err("run_gates_output missing 'gates' list")
    confidence = run_gates_output.get("confidence", 0)

    reasons_with_impact = []
    total_exposure = 0
    for g in gates:
        reason, impact = _impact_for_gate(g)
        if reason is None:
            continue
        reasons_with_impact.append((reason, impact))
        total_exposure += impact

    # Add RFI and conflict exposure if summaries provided
    if isinstance(rfi_summary, dict):
        unresolved_high = rfi_summary.get("unresolved_high", rfi_summary.get("high", 0))
        unresolved_medium = rfi_summary.get("unresolved_medium", rfi_summary.get("medium", 0))
        if unresolved_high:
            impact = unresolved_high * DEFAULT_IMPACT_USD["rfi_high_unresolved"]
            reasons_with_impact.append(
                (f"{unresolved_high} HIGH-priority RFI(s) unresolved.", impact)
            )
            total_exposure += impact
        if unresolved_medium:
            impact = unresolved_medium * DEFAULT_IMPACT_USD["rfi_medium_unresolved"]
            reasons_with_impact.append(
                (f"{unresolved_medium} MEDIUM-priority RFI(s) unresolved.", impact)
            )
            total_exposure += impact

    if isinstance(conflict_summary, dict):
        hard = conflict_summary.get("hard", 0)
        if hard:
            impact = hard * DEFAULT_IMPACT_USD["conflict_hard_unresolved"]
            reasons_with_impact.append(
                (f"{hard} HARD cross-document conflict(s) unresolved.", impact)
            )
            total_exposure += impact

    # Sort by dollar impact descending, take top 3
    reasons_with_impact.sort(key=lambda x: x[1], reverse=True)
    top_reasons = [r for (r, _) in reasons_with_impact[:3]]
    all_reasons = [{"reason": r, "estimated_impact_usd": i}
                   for (r, i) in reasons_with_impact]

    verdict = _verdict_from_gates(gates, confidence)
    # Force DO_NOT_SUBMIT if there's an unresolved HARD conflict
    if isinstance(conflict_summary, dict) and conflict_summary.get("hard", 0) > 0:
        if verdict == VERDICT_SUBMIT:
            verdict = VERDICT_SUBMIT_WITH_CAUTION

    payload = {
        "verdict": verdict,
        "verdict_display": verdict.replace("_", " "),
        "confidence_score": confidence,
        "financial_exposure_usd": total_exposure,
        "top_reasons": top_reasons,
        "all_reasons": all_reasons,
        "one_line": _one_line(verdict, top_reasons, total_exposure),
        "_underlying": run_gates_output,
    }
    return _ok(payload)


def render_markdown(verdict_payload):
    """Pretty-print the verdict block. Use this as the top of the
    bid-intel handoff package. Operum puts the verdict prominently;
    we should too."""
    if not isinstance(verdict_payload, dict):
        return "INVALID_VERDICT"
    v = verdict_payload.get("verdict", "UNKNOWN")
    badge = {
        VERDICT_SUBMIT: ":green_circle: SUBMIT",
        VERDICT_SUBMIT_WITH_CAUTION: ":yellow_circle: SUBMIT WITH CAUTION",
        VERDICT_DO_NOT_SUBMIT: ":red_circle: DO NOT SUBMIT",
    }.get(v, v)

    lines = []
    lines.append(f"# Bid Verdict: {badge}")
    lines.append("")
    lines.append(f"**{verdict_payload.get('one_line', '')}**")
    lines.append("")
    lines.append(f"- Verdict: **{v}**")
    lines.append(f"- Confidence score: {verdict_payload.get('confidence_score', 0)}/100")
    lines.append(f"- Financial exposure estimate: "
                 f"${verdict_payload.get('financial_exposure_usd', 0):,}")
    lines.append("")
    top = verdict_payload.get("top_reasons", [])
    if top:
        lines.append("## Top reasons")
        for i, r in enumerate(top, 1):
            lines.append(f"{i}. {r}")
        lines.append("")
    all_r = verdict_payload.get("all_reasons", [])
    if len(all_r) > len(top):
        lines.append("## All flagged reasons")
        for r in all_r:
            lines.append(f"- {r['reason']} (est. ${r['estimated_impact_usd']:,})")
        lines.append("")
    return "\n".join(lines)


# Smoke test
if __name__ == "__main__":
    # Simulated run_gates output
    sample_gates_out = {
        "gates": [
            {"gate": 1, "name": "Joist Count", "status": "LOW",
             "value": 0, "warning": "no EQ.SPA annotations found"},
            {"gate": 2, "name": "Tonnage/SF", "status": "FLAG",
             "value": "6.2 lbs/SF", "warning": "above tilt_wall ceiling 5.5"},
            {"gate": 3, "name": "$/SF Check", "status": "PASS",
             "value": "$18.50/SF", "warning": None},
            {"gate": 4, "name": "Scope Complete", "status": "FLAG",
             "warning": "missing: embed_plates, caged_ladders, canopy_framing"},
            {"gate": 5, "name": "Structural Ratios", "status": "PASS",
             "violations": [], "warning": None},
        ],
        "confidence": 65,
        "blocked": False,
        "decision": "CAUTION - REVIEW RECOMMENDED",
    }
    sample_rfi_summary = {"high": 2, "medium": 4, "low": 1}
    sample_conflict_summary = {"hard": 1, "soft": 0, "info": 2}

    out = from_run_gates(sample_gates_out,
                          rfi_summary=sample_rfi_summary,
                          conflict_summary=sample_conflict_summary)
    if not out["ok"]:
        print("ERROR:", out["error"])
    else:
        print(render_markdown(out["data"]))
