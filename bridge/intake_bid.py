"""
Your Company Virtual Office - Remote Bid Intake

Parses an incoming bid invite from Cowork or MCP and creates:
  1. A bid record in the pipeline DB (or updates an existing one)
  2. A 9-folder project structure with populated CLAUDE.md

This is the entry point for /intake-bid from the Owner's phone via Cowork.

Input is flexible: plain text invite, JSON dict, or a minimal dict with just
project_name and gc_company. All fields except project_name are optional.
"""

import json
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Project number prefix and counter storage via bid_pipeline counter mechanism
_NC_PREFIX = "NC"

_NON_BID_KEYWORDS = (
    "master service agreement", "msa", "purchase order", " po ",
    "subcontract", "invoice", "change order", "profit margin",
    "internal", "moc erectors", "nda", "confidentiality",
    "work order", "lien waiver", "executed",
    "margin analysis", "profit analysis",
    "financial analysis", "financial report", "cost analysis",
    "p&l", "income statement", "balance sheet",
)

_NON_BID_LABEL = {
    "master service agreement": "master service agreement",
    "msa": "master service agreement",
    "purchase order": "purchase order",
    " po ": "purchase order",
    "subcontract": "subcontract",
    "invoice": "invoice",
    "change order": "change order",
    "profit margin": "internal document",
    "profit analysis": "internal document",
    "margin analysis": "internal document",
    "internal": "internal document",
    "moc erectors": "subcontract",
    "nda": "nondisclosure agreement",
    "confidentiality": "nondisclosure agreement",
    "work order": "work order",
    "lien waiver": "lien waiver",
    "executed": "executed contract",
    "financial analysis": "internal document",
    "financial report": "internal document",
    "cost analysis": "internal document",
    "p&l": "internal document",
    "income statement": "internal document",
    "balance sheet": "internal document",
}


def _detect_non_bid_type(name: str, notes: str = "") -> str | None:
    """Return a human label if the document looks like a non-bid, else None."""
    combined = " " + (name + " " + notes).lower() + " "
    for kw in _NON_BID_KEYWORDS:
        if kw in combined:
            return _NON_BID_LABEL.get(kw, "non-bid document")
    return None


def _next_project_number() -> str:
    """Generate next project number in format NC-YYYY-XXX."""
    try:
        from bridge.vm_bid_discovery import _next_bid_number
        raw = _next_bid_number()
        # raw is like "PRJ-2026-MAY-001" - normalize to NC-YYYY-NNN
        return raw
    except Exception:
        # Fallback: use timestamp-based number
        ts = datetime.now(timezone.utc)
        return f"{_NC_PREFIX}-{ts.strftime('%Y%m%d%H%M%S')}"


def _parse_invite_text(text: str) -> dict:
    """Extract structured fields from free-text bid invite.

    Looks for common patterns like "Project:", "GC:", "Due:", "Location:".
    Returns a dict of extracted fields. All fields are best-effort.
    """
    fields = {}
    patterns = {
        "project_name": [
            r"project[:\s]+([^\n]+)",
            r"project\s+name[:\s]+([^\n]+)",
            r"subject[:\s]+([^\n]+)",
        ],
        "gc_company": [
            r"(?:gc|general contractor|contractor)[:\s]+([^\n]+)",
            r"from[:\s]+([^\n]+)",
        ],
        "location": [
            r"location[:\s]+([^\n]+)",
            r"site[:\s]+([^\n]+)",
            r"address[:\s]+([^\n]+)",
        ],
        "deadline": [
            r"(?:due|deadline|bid due|due date)[:\s]+([^\n]+)",
            r"(?:bids due|bids by)[:\s]+([^\n]+)",
        ],
        "tonnage": [
            r"(\d+[\.,]?\d*)\s*(?:tons?|ton[s\b])",
        ],
        "estimated_value": [
            r"\$\s*([\d,]+(?:\.\d{2})?)",
        ],
    }
    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                fields[field] = m.group(1).strip().rstrip(".,;")
                break
    return fields


def intake_bid_from_invite(
    invite_text: str = "",
    invite_json: str = "",
    project_name: str = "",
    gc_company: str = "",
    gc_contact_email: str = "",
    location: str = "",
    deadline: str = "",
    estimated_value: str = "",
    tonnage: str = "",
    notes: str = "",
    source: str = "cowork",
    project_root: str = "",
) -> dict:
    """Parse a bid invite and create project folder + pipeline record.

    Accepts input in three ways (first non-empty wins):
      1. invite_json - JSON string with any of the named fields
      2. invite_text - free-text bid invite to parse
      3. Named keyword arguments directly

    Returns:
        {
            "bid_id": int,
            "project_number": str,
            "project_name": str,
            "folder_path": str,
            "claude_md_path": str,
            "pipeline_state": str,
        }
    """
    # ── 1. Parse input ────────────────────────────────────────────────
    fields: dict = {}

    if invite_json:
        try:
            parsed = json.loads(invite_json) if isinstance(invite_json, str) else invite_json
            if isinstance(parsed, dict):
                fields.update(parsed)
        except (json.JSONDecodeError, ValueError) as e:
            log.warning("intake_bid: bad invite_json: %s", e)

    if invite_text and not fields:
        fields.update(_parse_invite_text(invite_text))

    # Named args override parsed fields
    if project_name:
        fields["project_name"] = project_name
    if gc_company:
        fields["gc_company"] = gc_company
    if gc_contact_email:
        fields["gc_contact_email"] = gc_contact_email
    if location:
        fields["location"] = location
    if deadline:
        fields["deadline"] = deadline
    if estimated_value:
        fields["estimated_value"] = estimated_value
    if tonnage:
        fields["tonnage"] = tonnage
    if notes:
        fields["notes"] = notes

    name = fields.get("project_name", "").strip()
    if not name:
        # VJ-FIX-001: branch_dict_key_parity. Return uniform shape so
        # frontend/callers can rely on dict keys regardless of branch.
        return {
            "ok": False,
            "error": "project_name is required",
            "fix": "pass project_name= or include 'Project: ...' in invite_text",
            "bid_id": 0,
            "project_number": "",
            "project_name": "",
            "folder_path": "",
            "claude_md_path": "",
            "pipeline_state": "",
            "gc_company": "",
            "location": "",
            "deadline": "",
            "source": source,
        }

    gc = fields.get("gc_company", "")
    gc_email = fields.get("gc_contact_email", "")
    loc = fields.get("location", "")
    due = fields.get("deadline", "")
    est_val = fields.get("estimated_value", "")
    tons = fields.get("tonnage", "")
    note = fields.get("notes", notes)

    # ── 1b. Non-bid document filter ───────────────────────────────────
    doc_type = _detect_non_bid_type(name, note)
    if doc_type:
        log.info("intake_bid: non-bid detected (%s): %s", doc_type, name)
        return {
            "ok": False,
            "routed_as": "non_bid",
            "doc_type": doc_type,
            "project_name": name,
            "message": (
                f"This looks like a {doc_type}. "
                f"Not added to bid pipeline. "
                f"Say 'add as bid' to override."
            ),
            "bid_id": 0,
            "project_number": "",
            "folder_path": "",
            "claude_md_path": "",
            "pipeline_state": "",
            "gc_company": gc,
            "location": loc,
            "deadline": due,
            "source": source,
        }

    # ── 2. Add to bid pipeline ────────────────────────────────────────
    bid_id = 0
    bid_state = "SCANNED"
    try:
        from bridge.bid_pipeline import add_bid
        bid_id = add_bid(
            name=name,
            gc_company=gc,
            location=loc,
            tonnage=tons,
            estimated_value=est_val,
            source=source,
            deadline=due,
        )
        log.info("intake_bid: added bid_id=%d name=%s", bid_id, name)
    except Exception as e:
        log.error("intake_bid: pipeline add failed: %s", e)
        # Non-fatal - still create the project folder

    # ── 3. Generate project number ────────────────────────────────────
    project_number = _next_project_number()

    # ── 4. Create project folder ──────────────────────────────────────
    try:
        from bridge.create_project import create_project
        result = create_project(
            project_number=project_number,
            project_name=name,
            gc_company=gc,
            gc_contact_email=gc_email,
            location=loc,
            deadline=due,
            estimated_value=est_val,
            tonnage=tons,
            bid_id=bid_id,
            bid_state=bid_state,
            notes=note,
            project_root=project_root,
        )
        folder_path = result["folder_path"]
        claude_md_path = result["claude_md_path"]
    except Exception as e:
        log.error("intake_bid: create_project failed: %s", e)
        folder_path = ""
        claude_md_path = ""

    # ── 5. Save invite text to 1.Bid-Invite/ if provided ─────────────
    if invite_text and folder_path:
        try:
            from pathlib import Path
            invite_dir = Path(folder_path) / "1.Bid-Invite"
            invite_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            (invite_dir / f"invite_{ts}.txt").write_text(invite_text, encoding="utf-8")
        except Exception as e:
            log.warning("intake_bid: could not save invite text: %s", e)

    return {
        "ok": True,
        "bid_id": bid_id,
        "project_number": project_number,
        "project_name": name,
        "folder_path": folder_path,
        "claude_md_path": claude_md_path,
        "pipeline_state": bid_state,
        "gc_company": gc,
        "location": loc,
        "deadline": due,
        "source": source,
    }
