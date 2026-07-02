"""OpenHuman skill manifest (Phase 29, v6.1.0).

Registers the "Structural Steel Detective" skill with OpenHuman.
This lets OpenHuman's subconscious loop trigger our tools when
it detects relevant events (new bid invite, new drawing, etc.).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging

from .rpc_client import OpenHumanClient

log = logging.getLogger(__name__)


SKILL_MANIFEST = {
    "name": "Structural Steel Detective",
    "version": "6.1.0",
    "description": (
        "AISC-validated structural steel takeoff and bid engine. "
        "Extracts members from structural drawings, validates against "
        "2,299 AISC v16.0 shapes, generates bids with assembly costing, "
        "and produces CNC output for the shop floor."
    ),
    "triggers": [
        "new PDF in Bids folder",
        "email with keywords: ITB, Bid Invite, Structural Steel",
        "calendar event with keyword: bid deadline",
    ],
    "actions": [
        "run_takeoff",
        "generate_bid",
        "check_compliance",
        "export_tekla",
        "export_strumis",
        "generate_stop_list",
        "audit_spec_book",
        "run_value_engineering",
    ],
    "rpc_endpoint": "http://127.0.0.1:8080/mcp",
    "company": "Your Company, LLC",
    "contact": "Joseph Hasse, Director of I.T.",
}


def register_skill(
    client: OpenHumanClient | None = None,
) -> dict:
    """Register the Structural Steel Detective skill with OpenHuman."""
    c = client or OpenHumanClient()
    if not c.is_available():
        return {"success": False, "error": "openhuman_not_running",
                "manifest": SKILL_MANIFEST}

    result = c.call("skills.register", {"manifest": SKILL_MANIFEST})
    return {"success": "error" not in result,
            "manifest": SKILL_MANIFEST, **result}


def get_skill_status(
    client: OpenHumanClient | None = None,
) -> dict:
    """Check if our skill is registered with OpenHuman."""
    c = client or OpenHumanClient()
    if not c.is_available():
        return {"registered": False, "available": False,
                "error": "openhuman_not_running"}

    result = c.call("skills.get", {"name": SKILL_MANIFEST["name"]})
    return {
        "registered": "error" not in result,
        "available": True,
        "skill_name": SKILL_MANIFEST["name"],
        **result,
    }
