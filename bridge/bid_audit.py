"""Fresh-instance bid audit.

Runs a cold review of the drafted proposal using a model that differs from
the estimate model. Goal: catch scope gaps, pricing errors, and voice
violations that the same model that generated the draft would miss.

MODEL SELECTION RATIONALE
--------------------------
Estimate model: T2 Sonnet 4.6 (DEFAULT_TASK_TIERS["takeoff_extract"] in
ai_model_router.py). Sonnet runs the takeoff, drafts the proposal text.

Audit model: T3 Opus 4.6 (AUDIT_TIER = "accurate"). Must differ from
estimate model because:
  1. Same model = confirmation bias. It will not flag its own output.
  2. Opus 4.6 is the T3/accurate tier used for compliance review and
     code review precisely because it is a second opinion on complex
     reasoning tasks.
  3. If Owner escalates estimate to T3, AUDIT_TIER escalates to T4 to
     maintain separation. pick_audit_model() encodes this logic.

SCOPE GAP RULE
--------------
If the audit finds a scope_gap it records blocking=True. The caller
(bridge/api.py generate_proposal or equivalent) must check result["blocking"]
before delivering the proposal. A blocked proposal must be surfaced to
Owner before any PDF is emailed.

OUTPUT FILES
------------
Per run (if bid_number is set and project folder exists):
  3.Estimate/Audit/fresh_instance_audit.md   (human-readable findings)
  3.Estimate/Audit/fresh_instance_audit.json  (machine-readable for scorecard)

Voice rules: zero em-dashes. Hyphens or periods only.
"""

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── Model selection ───────────────────────────────────────────────────────────

ESTIMATE_TIER = "default"   # Sonnet 4.6 - runs takeoff and drafts proposal
AUDIT_TIER = "accurate"     # Opus 4.6 - must differ from estimate tier

# If estimate is escalated to accurate, audit escalates to max.
_ESCALATION_MAP = {
    "fast":     "default",
    "default":  "accurate",
    "accurate": "max",
    "max":      "max",
}


def pick_audit_model(estimate_tier: str = ESTIMATE_TIER) -> str:
    """Return the model string for the audit, different from the estimate tier.

    If the estimate tier is the same as AUDIT_TIER (e.g. Owner escalated),
    escalate the audit one level higher.
    """
    from bridge.ai_model_router import TIERS
    audit_tier = _ESCALATION_MAP.get(estimate_tier, "accurate")
    if audit_tier == estimate_tier:
        audit_tier = _ESCALATION_MAP.get(audit_tier, "max")
    return TIERS.get(audit_tier, TIERS["accurate"])["model"]


# ── Audit prompt ──────────────────────────────────────────────────────────────

_AUDIT_SYSTEM = (
    "You are a senior structural steel estimator reviewing a bid proposal written "
    "by a junior estimator. You have no knowledge of how this proposal was created. "
    "Review it cold.\n\n"
    "Your job: find scope gaps, pricing inconsistencies, voice rule violations, "
    "and anything that would cause The Owner (CEO, Your Company) to revise the "
    "proposal before sending it to the client.\n\n"
    "SCOPE GAPS are the most critical finding. A scope gap is any work the client "
    "will expect Your Company to perform that is not explicitly stated in the proposal "
    "(deck installation omitted, erection not mentioned, anchor bolts missing, etc.).\n\n"
    "OUTPUT FORMAT - respond with valid JSON only, no prose:\n"
    "{\n"
    '  "scope_gaps": ["<description>", ...],\n'
    '  "pricing_flags": ["<description>", ...],\n'
    '  "voice_violations": ["<description>", ...],\n'
    '  "other_findings": ["<description>", ...],\n'
    '  "overall_risk": "LOW" | "MEDIUM" | "HIGH",\n'
    '  "blocking": true | false,\n'
    '  "summary": "<one sentence, no em-dashes>"\n'
    "}\n\n"
    "blocking must be true if scope_gaps is non-empty or overall_risk is HIGH."
)

_AUDIT_USER_TEMPLATE = (
    "Bid: {project_name}\n"
    "Tonnage: {tonnage} tons\n"
    "Total bid: ${total_bid:,.0f}\n"
    "Building type: {building_type}\n"
    "Building SF: {building_sf:,.0f}\n\n"
    "PROPOSAL TEXT:\n---\n{proposal_text}\n---\n\n"
    "Gate results from sanity check:\n{gate_summary}\n\n"
    "Review the proposal and return JSON only."
)


def _format_gate_summary(gate_results: list) -> str:
    """Summarize gate results for the audit prompt."""
    if not gate_results:
        return "(no gate results available)"
    lines = []
    for g in gate_results:
        status = g.get("status", "?")
        name = g.get("name", "?")
        warning = g.get("warning") or ""
        lines.append(f"Gate {g.get('gate','?')} {name}: {status}. {warning}".strip())
    return "\n".join(lines)


# ── Core audit function ───────────────────────────────────────────────────────

def run_fresh_instance_audit(
    proposal_text: str,
    project_name: str = "",
    tonnage: float = 0.0,
    total_bid: float = 0.0,
    building_type: str = "",
    building_sf: float = 0.0,
    gate_results: list | None = None,
    bid_number: str = "",
    estimate_tier: str = ESTIMATE_TIER,
    dry_run: bool = False,
) -> dict:
    """Run the fresh-instance cold review.

    Args:
        proposal_text:  Full text of the drafted proposal.
        project_name:   Project name for context.
        tonnage:        Total steel tonnage (tons).
        total_bid:      Total bid value in USD.
        building_type:  Building type string (e.g. "retail_small").
        building_sf:    Building footprint SF.
        gate_results:   Sanity gate results from run_gates() for context.
        bid_number:     Bid identifier. Used to write output files.
        estimate_tier:  Tier used by the estimate model. Audit uses a different tier.
        dry_run:        If True, skip the AI call and return a placeholder result.

    Returns:
        {
            "scope_gaps": list[str],
            "pricing_flags": list[str],
            "voice_violations": list[str],
            "other_findings": list[str],
            "overall_risk": str,
            "blocking": bool,
            "summary": str,
            "audit_model": str,
            "estimate_model": str,
            "bid_number": str,
            "timestamp": str,
            "dry_run": bool,
            "error": str or None,
        }
    """
    from bridge.ai_model_router import TIERS
    estimate_model = TIERS.get(estimate_tier, TIERS["default"])["model"]
    audit_model = pick_audit_model(estimate_tier)

    timestamp = datetime.now(timezone.utc).isoformat()

    result: dict = {
        "scope_gaps": [],
        "pricing_flags": [],
        "voice_violations": [],
        "other_findings": [],
        "overall_risk": "LOW",
        "blocking": False,
        "summary": "",
        "audit_model": audit_model,
        "estimate_model": estimate_model,
        "bid_number": bid_number,
        "timestamp": timestamp,
        "dry_run": dry_run,
        "error": None,
    }

    if dry_run:
        result["summary"] = "dry_run: audit skipped, no AI call made"
        result["other_findings"] = ["dry_run mode - no findings"]
        _write_audit_files(bid_number, result)
        return result

    if not proposal_text.strip():
        result["error"] = "proposal_text empty"
        result["overall_risk"] = "HIGH"
        result["blocking"] = True
        result["summary"] = "Audit blocked: proposal text is empty."
        _write_audit_files(bid_number, result)
        return result

    gate_summary = _format_gate_summary(gate_results or [])
    user_msg = _AUDIT_USER_TEMPLATE.format(
        project_name=project_name or "(unknown)",
        tonnage=tonnage,
        total_bid=total_bid,
        building_type=building_type or "(unknown)",
        building_sf=building_sf,
        proposal_text=proposal_text[:6000],
        gate_summary=gate_summary,
    )

    raw_json = _call_audit_model(audit_model, user_msg)
    if raw_json is None:
        result["error"] = "audit_model_call_failed"
        result["overall_risk"] = "HIGH"
        result["blocking"] = True
        result["summary"] = "Audit model call failed. Manual review required before delivery."
        _write_audit_files(bid_number, result)
        return result

    try:
        parsed = json.loads(raw_json)
        result.update({
            "scope_gaps": parsed.get("scope_gaps", []),
            "pricing_flags": parsed.get("pricing_flags", []),
            "voice_violations": parsed.get("voice_violations", []),
            "other_findings": parsed.get("other_findings", []),
            "overall_risk": parsed.get("overall_risk", "LOW"),
            "blocking": bool(parsed.get("blocking", False)),
            "summary": parsed.get("summary", ""),
        })
        if result["scope_gaps"] or result["overall_risk"] == "HIGH":
            result["blocking"] = True
    except (json.JSONDecodeError, ValueError) as e:
        result["error"] = f"audit_parse_failed:{e}"
        result["other_findings"] = [f"Raw audit output (parse failed): {raw_json[:500]}"]
        result["overall_risk"] = "MEDIUM"
        result["summary"] = "Audit output could not be parsed. Manual review recommended."

    _write_audit_files(bid_number, result)
    return result


def _call_audit_model(model: str, user_msg: str) -> str | None:
    """Call the audit model and return raw text, or None on failure."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_AUDIT_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return msg.content[0].text if msg.content else None
    except Exception as e:
        log.error("bid_audit._call_audit_model failed: %s", e)
        return None


def _write_audit_files(bid_number: str, result: dict) -> None:
    """Write audit results to the project folder."""
    if not bid_number:
        return
    try:
        from bridge.project_syncer import write_takeoff_json, write_audit_md
        write_takeoff_json(
            bid_number,
            "3.Estimate/Audit/fresh_instance_audit.json",
            result,
        )
        write_audit_md(
            bid_number,
            "3.Estimate/Audit/fresh_instance_audit.md",
            _render_audit_md(result),
        )
    except Exception as e:
        log.error("bid_audit._write_audit_files failed: %s", e)


def _render_audit_md(result: dict) -> str:
    """Render audit result as a Markdown report."""
    ts = result.get("timestamp", "")
    bn = result.get("bid_number", "(unknown)")
    risk = result.get("overall_risk", "?")
    blocking = result.get("blocking", False)
    audit_model = result.get("audit_model", "?")
    estimate_model = result.get("estimate_model", "?")
    summary = result.get("summary", "")

    block_line = "BLOCKED - do not deliver until scope gaps resolved." if blocking else "Not blocked."

    lines = [
        f"# Fresh-Instance Audit - {bn}",
        "",
        f"**Date:** {ts}",
        f"**Risk:** {risk}",
        f"**Delivery:** {block_line}",
        f"**Audit model:** {audit_model}",
        f"**Estimate model:** {estimate_model}",
        "",
        f"**Summary:** {summary}",
        "",
    ]

    def _section(title: str, items: list) -> list:
        if not items:
            return [f"## {title}", "", "None.", ""]
        out = [f"## {title}", ""]
        for item in items:
            out.append(f"- {item}")
        out.append("")
        return out

    lines += _section("Scope Gaps", result.get("scope_gaps", []))
    lines += _section("Pricing Flags", result.get("pricing_flags", []))
    lines += _section("Voice Violations", result.get("voice_violations", []))
    lines += _section("Other Findings", result.get("other_findings", []))

    if result.get("error"):
        lines += ["## Error", "", f"```", result["error"], "```", ""]

    return "\n".join(lines)
