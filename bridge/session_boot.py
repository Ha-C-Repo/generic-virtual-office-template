"""
Your Company Virtual Office - Session Boot
========================================
Runs once on app start (or session refresh). Loads canonical state from:
  1. OneDrive standing/ directory (company docs, certs, rates)
  2. OneDrive bid_kit/ directory (governance files)
  3. Three-tier governance state
  4. Obsidian vault (if detected)

Results cached in _SESSION_STATE. Subsequent calls return cache
unless force_refresh=True.
"""

import time
from datetime import datetime, timezone

from bridge.integrations import (
    detect_onedrive, read_standing_file, read_bid_kit_governance,
)
from bridge.governance import governance_status, resolve_all
from bridge.obsidian_sync import detect_vault, build_vault_context

_SESSION_STATE: dict | None = None
_BOOT_TIME: float = 0


def _load_project_claude_maps() -> dict:
    """Scan the configured project root for Project OS/CLAUDE.md files.

    Returns a dict keyed by project_number with CLAUDE.md content (first 2KB).
    Non-fatal: returns empty dict on any error.
    """
    try:
        from bridge.create_project import _project_root
        root = _project_root()
        if not root.exists():
            return {}
        maps = {}
        for child in root.iterdir():
            if not child.is_dir():
                continue
            claude_md = child / "Project OS" / "CLAUDE.md"
            if claude_md.exists():
                content = claude_md.read_text(encoding="utf-8", errors="replace")
                # Extract project number from folder name (first token before " - ")
                folder_parts = child.name.split(" - ", 1)
                project_num = folder_parts[0].strip() if folder_parts else child.name
                maps[project_num] = {
                    "project_dir": str(child),
                    "claude_md": content[:2048],
                }
        return maps
    except Exception:
        return {}


def _standing_file_list() -> list[str]:
    """Known standing files to attempt loading."""
    return [
        "company_profile.md",
        "rates_current.json",
        "isnetworld_status.json",
        "crew_roster.json",
        "equipment_list.md",
        "insurance_certs.json",
        "safety_programs_index.md",
        "emr_history.json",
    ]


def session_boot(force_refresh: bool = False) -> dict:
    """Run session boot sequence. Returns cached state if already booted.

    Boot sequence:
      1. Detect OneDrive → load standing files
      2. Load bid_kit governance supplements
      3. Load three-tier governance state
      4. Detect Obsidian vault
      5. Build session context summary

    All operations are non-blocking and fail-safe.
    Missing files or disconnected OneDrive just produce warnings.
    """
    global _SESSION_STATE, _BOOT_TIME

    if _SESSION_STATE and not force_refresh:
        return _SESSION_STATE

    start = time.time()
    boot_log = []
    warnings = []

    # ── 1. OneDrive standing files ────────────────────────────────────
    onedrive = detect_onedrive()
    standing_files = {}

    if onedrive["found"] and onedrive.get("standing"):
        boot_log.append(f"OneDrive found: {onedrive['path']}")
        for fname in _standing_file_list():
            content = read_standing_file(fname)
            if content:
                standing_files[fname] = content
                boot_log.append(f"  Loaded standing/{fname} ({len(content)} chars)")
            # Missing files are normal - not all will exist
        if not standing_files:
            warnings.append("OneDrive standing/ exists but no known files found")
    else:
        boot_log.append("OneDrive not detected. Using built-in data only.")
        if not onedrive["found"]:
            warnings.append("OneDrive sync folder not found on this machine")

    # ── 2. Bid kit governance ─────────────────────────────────────────
    bid_kit = read_bid_kit_governance()
    if bid_kit["found"]:
        boot_log.append(bid_kit["message"])
    else:
        boot_log.append("Bid kit governance: using built-in rules only")

    # ── 3. Three-tier governance ──────────────────────────────────────
    gov = governance_status()
    boot_log.append(
        f"Governance: {gov['tier1_rules']} immutable rules, "
        f"{gov['tier2_ceo_prefs']} CEO prefs, "
        f"{gov['tier3_defaults']} defaults"
    )

    # ── 4. Obsidian vault ─────────────────────────────────────────────
    vault = detect_vault()
    if vault.get("found"):
        vault_context = build_vault_context()
        boot_log.append(
            f"Obsidian vault: {vault_context.get('file_count', 0)} files "
            f"at {vault.get('path', 'unknown')}"
        )
    else:
        vault_context = {"found": False}
        boot_log.append("Obsidian vault not detected")

    # ── 5. Active bids from OneDrive ──────────────────────────────────
    active_bids = onedrive.get("active_bids", [])
    if active_bids:
        boot_log.append(f"Active bids on OneDrive: {', '.join(active_bids)}")

    # ── 6. Project CLAUDE.md routing maps + syncer ───────────────────
    project_claude_maps = _load_project_claude_maps()
    if project_claude_maps:
        boot_log.append(f"Project CLAUDE.md: {len(project_claude_maps)} project(s) loaded")
    else:
        boot_log.append("Project CLAUDE.md: no project folders found (normal on first run)")

    try:
        from bridge.project_syncer import start_syncer
        start_syncer()
        boot_log.append("Project syncer: started")
    except Exception as e:
        warnings.append(f"Project syncer failed to start: {e}")

    elapsed = time.time() - start
    boot_log.append(f"Session boot completed in {elapsed:.2f}s")

    _SESSION_STATE = {
        "booted_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(elapsed, 2),
        "onedrive": {
            "found": onedrive["found"],
            "path": onedrive.get("path"),
            "standing_files_loaded": len(standing_files),
            "standing_files": standing_files,
            "active_bids": active_bids,
            "bid_kit_loaded": bid_kit["found"],
        },
        "governance": gov,
        "vault": {
            "found": vault.get("found", False),
            "path": vault.get("path"),
        },
        "project_claude_maps": project_claude_maps,
        "boot_log": boot_log,
        "warnings": warnings,
    }
    _BOOT_TIME = time.time()

    return _SESSION_STATE


def get_session_state() -> dict | None:
    """Return current session state without re-booting."""
    return _SESSION_STATE


def get_standing_file(filename: str) -> str | None:
    """Get a standing file from the cached session state."""
    if _SESSION_STATE:
        return _SESSION_STATE["onedrive"]["standing_files"].get(filename)
    return read_standing_file(filename)


def session_age_seconds() -> float:
    """How long since last boot."""
    if not _BOOT_TIME:
        return -1
    return time.time() - _BOOT_TIME


def build_boot_context_for_prompt() -> str:
    """Build a concise context block from boot state for the system prompt.

    Only includes data that was actually loaded. Avoids prompt bloat
    from empty sections.
    """
    state = _SESSION_STATE
    if not state:
        return ""

    parts = []

    # Standing files summary
    standing = state["onedrive"]["standing_files"]
    if standing:
        parts.append("## OneDrive Standing Files (live)")
        for fname, content in standing.items():
            # Truncate each to 1KB for prompt
            truncated = content[:1024]
            if len(content) > 1024:
                truncated += "\n[truncated]"
            parts.append(f"### {fname}\n{truncated}")

    # Active bids
    bids = state["onedrive"]["active_bids"]
    if bids:
        parts.append(f"## Active Bids on OneDrive: {', '.join(bids)}")

    # Governance CEO prefs
    ceo_prefs = state["governance"].get("ceo_prefs", {})
    if ceo_prefs:
        parts.append("## CEO Preferences (learned)")
        for k, v in ceo_prefs.items():
            parts.append(f"- {k}: {v}")

    # Project CLAUDE.md routing maps (Phase 2)
    proj_maps = state.get("project_claude_maps", {})
    if proj_maps:
        parts.append(f"## Active Projects ({len(proj_maps)})")
        for proj_num, pdata in list(proj_maps.items())[:5]:  # cap at 5 for prompt size
            parts.append(f"### {proj_num}\n{pdata.get('claude_md', '')[:512]}")

    return "\n\n".join(parts)
