"""
bid_artifact_gate.py

Two-PDF pair gate for bid state transitions.

Background
----------
The reconciliation pass on 2026-05-23 surfaced a gap: bids in
bid_pipeline.db were moving to SUBMITTED state without a corresponding
client+GP PDF pair on disk. Without the pair the audit trail cannot
link an estimated_value back to a versioned proposal document, and the
hard-rules validator (scripts/validate-bid-output.py R5) cannot run.

This module is the gate. It is called from bridge/bid_pipeline.py:advance()
whenever the target state is SUBMITTED. If both PDFs are present, the
transition proceeds. If either is missing, the transition is blocked
with a clear error message and a hint for how to generate the pair.

The gate also accepts an explicit bypass flag for emergency cases
(e.g. submission was made via external email and the PDFs live in the
GC's portal, not output/). Bypass is logged to the transitions audit
table so post-mortems can find it.

Hard rules respected
--------------------
- No supplier names introduced. No precedent project references.
- Voice rules: short sentences, no em-dashes, no filler.
- Tier 1: existing skills not disturbed. Pure addition.

Author: Joseph / Owner via Cowork reconciliation handoff, 2026-05-23.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

# -------- Filename pattern (matches existing convention) --------
#  NC_Proposal_<project>_<YYYY-MM-DD>.pdf         (client)
#  NC_Proposal_<project>_<YYYY-MM-DD>-GP.pdf      (GP report)

CLIENT_PDF_PATTERN = re.compile(
    r"^NC_Proposal_(?P<project>.+?)_(?P<date>\d{4}-\d{2}-\d{2})\.pdf$",
    re.IGNORECASE,
)
GP_PDF_PATTERN = re.compile(
    r"^NC_Proposal_(?P<project>.+?)_(?P<date>\d{4}-\d{2}-\d{2})-GP\.pdf$",
    re.IGNORECASE,
)


def _output_dir() -> Path:
    """Resolve the output folder using the resource-path helper.

    Falls back to a sibling 'output' directory if the helper is not
    available (e.g. during unit tests).
    """
    try:
        from vo_app._resources import resource_path  # type: ignore
        p = resource_path("output")
        if p:
            return Path(p)
    except Exception:
        pass
    # Fallback: walk up from this file to project root
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent, here.parent.parent.parent]:
        candidate = parent / "output"
        if candidate.is_dir():
            return candidate
    # Last resort
    return Path.cwd() / "output"


def _normalize(name: str) -> str:
    """Lowercase and strip non-alnum for comparison."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def find_pair_for_bid(bid_name: str,
                      output_dir: Optional[Path] = None
                      ) -> Tuple[Optional[Path], Optional[Path]]:
    """Locate the latest client+GP PDF pair for a bid by name.

    Match is fuzzy: the bid name is normalized (lowercase, alnum only)
    and compared against each PDF's project segment normalized the same
    way. The latest dated pair wins.

    Returns (client_pdf, gp_pdf). Either or both may be None if not
    found.
    """
    out = output_dir or _output_dir()
    if not out.is_dir():
        return (None, None)

    target = _normalize(bid_name)
    if not target:
        return (None, None)

    clients = []
    gps = []
    for p in out.glob("*.pdf"):
        m_gp = GP_PDF_PATTERN.match(p.name)
        if m_gp:
            proj = _normalize(m_gp.group("project"))
            if proj == target or target in proj or proj in target:
                gps.append((m_gp.group("date"), p))
            continue
        m_cl = CLIENT_PDF_PATTERN.match(p.name)
        if m_cl:
            proj = _normalize(m_cl.group("project"))
            if proj == target or target in proj or proj in target:
                clients.append((m_cl.group("date"), p))

    clients.sort(reverse=True)
    gps.sort(reverse=True)
    client = clients[0][1] if clients else None
    gp = gps[0][1] if gps else None
    return (client, gp)


def check_two_pdf_pair(bid_name: str,
                       output_dir: Optional[Path] = None
                       ) -> dict:
    """Hard gate. Returns {ok: bool, ...} dict matching Bridge convention.

    On success: {"ok": True, "client_pdf": str, "gp_pdf": str}.
    On failure: {"ok": False, "error": <msg>, "fix": <hint>,
                 "missing": ["client"] / ["gp"] / ["client","gp"]}.
    """
    if not bid_name:
        return {"ok": False, "error": "bid_name is required for gate check"}

    client, gp = find_pair_for_bid(bid_name, output_dir)

    missing = []
    if client is None:
        missing.append("client")
    if gp is None:
        missing.append("gp")

    if not missing:
        return {
            "ok": True,
            "client_pdf": str(client),
            "gp_pdf": str(gp),
        }

    fix_hint = (
        f"Run `generate proposal {bid_name}` then `generate gp report {bid_name}` "
        f"to produce the pair. Or call advance_bid_to_submitted with bypass=True "
        f"and a non-empty bypass_reason if submission happened externally."
    )
    return {
        "ok": False,
        "error": (
            f"Cannot move bid '{bid_name}' to SUBMITTED. "
            f"Missing PDF(s): {', '.join(missing)}. "
            f"Both <bid>.pdf and <bid>-GP.pdf must exist in output/ before submit."
        ),
        "fix": fix_hint,
        "missing": missing,
    }


def gate_or_block(bid_name: str,
                  new_state: str,
                  bypass: bool = False,
                  bypass_reason: str = "",
                  output_dir: Optional[Path] = None
                  ) -> dict:
    """Entry point called from bid_pipeline.advance().

    Returns:
        {"ok": True, "audit_note": "..."}                       if allowed
        {"ok": False, "error": ..., "fix": ..., "missing": ...} if blocked
    """
    if new_state != "SUBMITTED":
        return {"ok": True, "audit_note": ""}  # gate only fires on SUBMITTED

    if bypass:
        if not bypass_reason or len(bypass_reason.strip()) < 10:
            return {
                "ok": False,
                "error": "Bypass requested but bypass_reason is missing or too short.",
                "fix": "Supply a bypass_reason of at least 10 characters explaining "
                       "why the PDF pair is not on disk (e.g. 'submitted via GC portal "
                       "Procore, attachments uploaded directly').",
            }
        return {
            "ok": True,
            "audit_note": f"ARTIFACT_GATE_BYPASS: {bypass_reason.strip()}",
        }

    result = check_two_pdf_pair(bid_name, output_dir)
    if result["ok"]:
        result["audit_note"] = (
            f"artifact_gate=PASS client={Path(result['client_pdf']).name} "
            f"gp={Path(result['gp_pdf']).name}"
        )
    return result
