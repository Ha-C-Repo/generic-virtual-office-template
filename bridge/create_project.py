"""
Your Company Virtual Office - Project Folder Creator

Creates the 9-folder project structure for a bid being tracked.
Populates CLAUDE.md from template with bid-specific data.

9-folder structure (adapted from ConstructIQ 7-folder for US trade contractor):
  1.Bid-Invite/     original invite, scope narrative, RFI
  2.Drawings/       structural PDFs and revision log
  3.Estimate/       takeoff, pricing, sanity gate outputs
  4.Proposal/       client PDF + GP report (-GP suffix)
  5.Compliance/     ISN, DISA, EMR, certs
  6.Execution/      shop drawings, fab packages, AISC certs
  7.Field/          erection, inspection, QC records
  8.Financial/      AIA G702/G703, payment apps, invoices
  Project OS/       CLAUDE.md, State.md, Compliance.md, Activity.md
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from vo_app._resources import resource_path

log = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(resource_path("data/templates/CLAUDE_TEMPLATE.md"))

_SUBFOLDERS = [
    "1.Bid-Invite",
    "2.Drawings",
    "3.Estimate/Takeoff",
    "3.Estimate/Pricing",
    "3.Estimate/Sanity-Gate",
    "4.Proposal",
    "5.Compliance",
    "6.Execution",
    "7.Field",
    "8.Financial",
    "Project OS",
]


def _project_root() -> Path:
    """Return the configured project root directory.

    Reads project_root from config.json if present; falls back to
    data/projects/ relative to the repo root.
    """
    try:
        cfg_path = Path(resource_path("data/config.json"))
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            pr = cfg.get("project_root", "")
            if pr:
                return Path(pr)
    except Exception:
        pass
    return Path(resource_path("data/projects"))


def _load_template() -> str:
    if _TEMPLATE_PATH.exists():
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    # Minimal inline fallback so create_project works even before template exists
    return "# CLAUDE.md - {{PROJECT_NUMBER}} {{PROJECT_NAME}}\nBid ID: {{BID_ID}}\n"


def _fill_template(template: str, values: dict) -> str:
    result = template
    for key, val in values.items():
        result = result.replace("{{" + key + "}}", str(val) if val is not None else "")
    return result


def create_project(
    project_number: str,
    project_name: str,
    gc_company: str = "",
    gc_contact_email: str = "",
    location: str = "",
    deadline: str = "",
    estimated_value: str = "",
    tonnage: str = "",
    bid_id: int = 0,
    bid_state: str = "SCANNED",
    notes: str = "",
    project_root: str = "",
) -> dict:
    """Create the 9-folder project structure and populate CLAUDE.md.

    Returns:
        {
            "project_number": str,
            "project_name": str,
            "folder_path": str,
            "claude_md_path": str,
            "folders_created": list[str],
        }
    """
    root = Path(project_root) if project_root else _project_root()
    root.mkdir(parents=True, exist_ok=True)

    folder_name = f"{project_number} - {project_name}"
    project_dir = root / folder_name
    if project_dir.exists():
        log.info("Project folder already exists: %s", project_dir)

    folders_created = []
    for sub in _SUBFOLDERS:
        d = project_dir / sub
        d.mkdir(parents=True, exist_ok=True)
        folders_created.append(str(d))

    # Populate and write CLAUDE.md inside Project OS/
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    template_values = {
        "PROJECT_NUMBER": project_number,
        "PROJECT_NAME": project_name,
        "GC_COMPANY": gc_company,
        "GC_CONTACT_EMAIL": gc_contact_email,
        "LOCATION": location,
        "DEADLINE": deadline,
        "ESTIMATED_VALUE": estimated_value,
        "TONNAGE": tonnage,
        "BID_ID": str(bid_id) if bid_id else "",
        "BID_STATE": bid_state,
        "CREATED_AT": created_at,
        "NOTES": notes,
    }
    claude_md_content = _fill_template(_load_template(), template_values)
    claude_md_path = project_dir / "Project OS" / "CLAUDE.md"
    claude_md_path.write_text(claude_md_content, encoding="utf-8")

    # Write placeholder syncer files
    (project_dir / "Project OS" / "State.md").write_text(
        f"# State - {project_name}\n\nPipeline state will be written here by project_syncer.\n",
        encoding="utf-8",
    )
    (project_dir / "Project OS" / "Compliance.md").write_text(
        f"# Compliance - {project_name}\n\nCompliance grade will be written here by project_syncer.\n",
        encoding="utf-8",
    )
    (project_dir / "Project OS" / "Activity.md").write_text(
        f"# Activity - {project_name}\n\nEngagement records will be written here by project_syncer.\n",
        encoding="utf-8",
    )

    # Write _project_info.json at project root
    project_info = {
        "project_number": project_number,
        "project_name": project_name,
        "gc_company": gc_company,
        "gc_contact_email": gc_contact_email,
        "location": location,
        "deadline": deadline,
        "estimated_value": estimated_value,
        "tonnage": tonnage,
        "bid_id": bid_id,
        "bid_state": bid_state,
        "created_at": created_at,
        "notes": notes,
    }
    (project_dir / "_project_info.json").write_text(
        json.dumps(project_info, indent=2), encoding="utf-8"
    )

    log.info("Project created: %s (%d subfolders)", project_dir, len(folders_created))
    return {
        "project_number": project_number,
        "project_name": project_name,
        "folder_path": str(project_dir),
        "claude_md_path": str(claude_md_path),
        "folders_created": folders_created,
    }


def get_project_path(project_number: str, project_root: str = "") -> str:
    """Return the folder path for an existing project, or empty string if not found."""
    root = Path(project_root) if project_root else _project_root()
    if not root.exists():
        return ""
    for child in root.iterdir():
        if child.is_dir() and child.name.startswith(project_number):
            return str(child)
    return ""


def read_project_claude_md(project_number: str, project_root: str = "") -> str:
    """Read the CLAUDE.md for a project. Returns empty string if not found."""
    folder = get_project_path(project_number, project_root)
    if not folder:
        return ""
    claude_md = Path(folder) / "Project OS" / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text(encoding="utf-8")
    return ""
