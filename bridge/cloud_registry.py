"""
Your Company Virtual Office - Cloud Document Registry
====================================================
Google Drive file IDs for canonical operational documents.
Discovered during v3.4.1 cloud drive audit.

These IDs are stable (Google Drive does not change file IDs).
The session_boot module can use these to verify cloud connectivity
and load canonical documents on startup.

Owner: yourcompanyjoseph@gmail.com
Last verified: 2026-05-08
"""

# ── Google Drive File Registry ────────────────────────────────────────

GDRIVE_REGISTRY = {
    # Bid Kit (templates and forms)
    "bid_proposal_template": {
        "id": "127Bn_448NClrvLRvh4DAYnKfQBGjGx9I",
        "title": "Bid_Proposal_Template.pdf",
        "purpose": "Standard bid proposal template. Deck always in scope.",
    },
    "bid_decline_letter": {
        "id": "11CfP0_1_VlcZTKN63bOv91ZOCHtsUwQy",
        "title": "Bid_Decline_Letter.pdf",
        "purpose": "Graceful pass letter that maintains GC relationship.",
    },
    "insurance_coi_cover": {
        "id": "1-Uo42-drfFaMeFHUAHOS24rAPMTKYul9",
        "title": "Insurance_Certificate_COI_Cover.pdf",
        "purpose": "COI transmittal cover. WC: Texas Mutual [POLICY NUMBER].",
    },
    "engineering_compliance": {
        "id": "1Hro8wUmcLyq8qvbaXiuy8IZtooju5o9x",
        "title": "Engineering_Letter_of_Compliance.pdf",
        "purpose": "AHJ submission letter for code compliance certification.",
    },
    "safety_starter_pack": {
        "id": "1f5KAowvL44mHQDWOVy-uRo28m1EEpI_0",
        "title": "Gumroad_Safety_Programs_Starter_Pack_Cover.pdf",
        "purpose": "5-program RAVS starter pack for Gumroad ($149).",
    },
    "pre_task_plan": {
        "id": "1eLXesXV-Q7PUEkVVBZPjyCmtWdAt6kmt",
        "title": "Pre_Task_Plan_Daily_Safety_Briefing.pdf",
        "purpose": "Daily safety briefing form. Filed with DFR.",
    },

    # Spreadsheets (operational tools)
    "steel_pro_calculator": {
        "id": "104o0vSjCLLGTVLhjgbVL6ZYqIKNggOqf",
        "title": "Your_Company_Steel_Pro_Bid_Calculator_v1.xlsx",
        "purpose": "Master bid calculator. 11 hrs/ton, 7 labor profiles.",
    },
    "bid_quote_builder": {
        "id": "1cNH3ibLguMAEHS5HGi82FSogTnQNm-Hz",
        "title": "Your_Company_Bid_Quote.xlsx",
        "purpose": "Line-item bid builder with inclusions/exclusions.",
    },
    "bid_tracker": {
        "id": "1Ku29vdMc5YLJobJJ0sqx18RBdplZ67Mv",
        "title": "Your_Company_Bid_Tracker.xlsx",
        "purpose": "Full pipeline: lead to paid. Win rate tracking.",
    },
    "bid_nobid": {
        "id": "1AVYzwh56V7Jjjut4SoeeC9TkJPKhlM0u",
        "title": "Your_Company_Bid_NoBid.xlsx",
        "purpose": "5 hard filters + 7 scored criteria bid screening.",
    },
    "crew_time": {
        "id": "1SaQzRjBLtpEStcZheEhrvxyMJmkDDlAl",
        "title": "Your_Company_Crew_Time.xlsx",
        "purpose": "12-person roster, daily time entry, hrs/ton tracking.",
    },
    "job_cost_tracker": {
        "id": "1PBOCTO3tQtd5ZviqRGaMYdYdYIo-yMR-",
        "title": "Your_Company_Job_Cost_Tracker.xlsx",
        "purpose": "Per-job cost tracker: material + labor by phase.",
    },

    # Governance
    "compliance_immutable": {
        "id": "1ANVzLgeNFljMS5XdlpvZ0N-cmJID2fA9",
        "title": "compliance_immutable.md",
        "purpose": "Tier 1 rules v1.1.0 with refusal language.",
    },
}


def get_gdrive_url(key: str) -> str | None:
    """Get the Google Drive view URL for a registered document."""
    entry = GDRIVE_REGISTRY.get(key)
    if entry:
        return f"https://drive.google.com/file/d/{entry['id']}/view"
    return None


def get_gdrive_id(key: str) -> str | None:
    """Get the Google Drive file ID for a registered document."""
    entry = GDRIVE_REGISTRY.get(key)
    return entry["id"] if entry else None


def list_registry() -> list[dict]:
    """List all registered cloud documents."""
    return [
        {"key": k, "title": v["title"], "purpose": v["purpose"]}
        for k, v in GDRIVE_REGISTRY.items()
    ]
