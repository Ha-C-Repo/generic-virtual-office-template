"""
Your Company Virtual Office - Obsidian Vault Sync (v3.2)
======================================================

The Linux virtual office uses an Obsidian vault (which IS the GitHub repo)
as its long-term memory layer. This module reads from the same vault on
Windows so both platforms share persistent context.

Three memory layers (from the Linux handoff doc):
  L1: Obsidian (.md files) - human-readable, editable
  L2: MemPalace - semantic search (ChromaDB on Linux, not ported)
  L3: NotebookLM - deep archive (Google, not ported)

This module implements L1 read-only on Windows:
  - Reads key vault files on boot
  - Returns context snippets for system prompt supplement
  - Watches for changes (file mtime comparison)

The vault is typically at:
  Windows: %USERPROFILE%\\yourco-virtual-office\\  (GitHub clone)
  Linux:   ~/yourco-virtual-office/

Files of interest:
  - bid_kit/*.md           (governance rules - also on OneDrive)
  - agents/*.md            (agent playbooks)
  - templates/*.md         (prompt templates)
  - conversations/recent/  (recent conversation summaries)
  - memory/ceo_prefs.md    (CEO learned preferences)
  - memory/projects.md     (active project summaries)
"""

import os
from datetime import datetime, timezone
from pathlib import Path


# ── Vault detection ──────────────────────────────────────────────────

_VAULT_CANDIDATES = [
    Path(os.environ.get("USERPROFILE", "")) / "yourco-virtual-office",
    Path(os.environ.get("USERPROFILE", "")) / "yourco",
    Path.home() / "yourco-virtual-office",
    Path.home() / "yourco",
]


def detect_vault() -> dict:
    """Detect the Obsidian vault (GitHub repo) on this machine."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.25; disjoint shapes)
    for candidate in _VAULT_CANDIDATES:
        # Must have .obsidian/ or .git/ to be the vault
        is_obsidian = (candidate / ".obsidian").exists()
        is_git = (candidate / ".git").exists()
        if candidate.exists() and (is_obsidian or is_git):
            return {
                "found": True,
                "path": str(candidate),
                "is_obsidian": is_obsidian,
                "is_git": is_git,
                "has_bid_kit": (candidate / "bid_kit").exists(),
                "has_agents": (candidate / "agents").exists(),
                "has_templates": (candidate / "templates").exists(),
                "has_memory": (candidate / "memory").exists(),
            }
    return {"found": False, "path": None}


def read_vault_file(relative_path: str) -> str | None:
    """Read a single file from the vault by relative path."""
    info = detect_vault()
    if not info["found"]:
        return None
    fpath = Path(info["path"]) / relative_path
    if fpath.exists() and fpath.is_file():
        try:
            return fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    return None


def read_vault_directory(relative_dir: str, extension: str = ".md",
                         max_files: int = 20, max_chars_per_file: int = 3000) -> dict:
    """Read all files of a given extension from a vault subdirectory.

    Returns dict of {filename: content} with size limits to prevent prompt bloat.
    """
    info = detect_vault()
    if not info["found"]:
        return {}

    target = Path(info["path"]) / relative_dir
    if not target.exists() or not target.is_dir():
        return {}

    files = {}
    for f in sorted(target.glob(f"*{extension}"))[:max_files]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars_per_file:
                content = content[:max_chars_per_file] + "\n[... truncated ...]"
            files[f.name] = content
        except Exception:
            continue
    return files


# ── Context builder for system prompt ────────────────────────────────

def build_vault_context() -> dict:
    """Build a context summary from the vault for system prompt supplement.

    Reads priority files and returns structured data that can be appended
    to the system prompt or used by the AI for context.
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.50; needs manual audit)
    info = detect_vault()
    if not info["found"]:
        return {"found": False, "context": "", "files_read": 0}

    sections = []
    files_read = 0
    total_chars = 0

    # Priority 1: CEO preferences (most important for personalization)
    ceo_prefs = read_vault_file("memory/ceo_prefs.md")
    if ceo_prefs:
        sections.append("CEO PREFERENCES (from Obsidian vault):\n" + ceo_prefs[:2000])
        files_read += 1
        total_chars += len(ceo_prefs[:2000])

    # Priority 2: Active project summaries
    projects = read_vault_file("memory/projects.md")
    if projects:
        sections.append("ACTIVE PROJECTS (from Obsidian vault):\n" + projects[:2000])
        files_read += 1
        total_chars += len(projects[:2000])

    # Priority 3: Agent playbooks (brief summaries only)
    if info.get("has_agents"):
        agents = read_vault_directory("agents", max_files=10, max_chars_per_file=500)
        if agents:
            agent_summary = "AGENT PLAYBOOKS AVAILABLE:\n"
            for name, content in agents.items():
                # Extract just the first line (title/description)
                first_line = content.split('\n')[0].strip('# ').strip()
                agent_summary += f"  - {name}: {first_line}\n"
            sections.append(agent_summary)
            files_read += len(agents)
            total_chars += len(agent_summary)

    # Priority 4: Recent conversation summaries (last 5)
    recent = read_vault_directory("conversations/recent", max_files=5, max_chars_per_file=800)
    if recent:
        sections.append("RECENT CONVERSATIONS (from vault):")
        for name, content in list(recent.items())[-5:]:
            sections.append(f"  [{name}] {content[:400]}")
            files_read += 1
            total_chars += min(len(content), 400)

    context_text = "\n\n".join(sections) if sections else ""

    return {
        "found": True,
        "vault_path": info["path"],
        "context": context_text,
        "files_read": files_read,
        "total_chars": total_chars,
        "sections": len(sections),
    }


# ── Vault status for dashboard ───────────────────────────────────────

def get_vault_status() -> dict:
    """Get vault status for the integration dashboard panel."""
    # vj: parity-ok (pass 10g classified: dispatcher J=0.22; disjoint shapes)
    info = detect_vault()
    if not info["found"]:
        return {
            "status": "not_found",
            "message": "Obsidian vault not detected. Clone the repo to ~/yourco-virtual-office/",
        }

    vault_path = Path(info["path"])
    # Count files
    md_count = len(list(vault_path.rglob("*.md")))
    # Get last modified
    try:
        latest = max(vault_path.rglob("*.md"), key=lambda f: f.stat().st_mtime)
        last_mod = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()[:16]
        last_file = str(latest.relative_to(vault_path))
    except (ValueError, Exception):
        last_mod = "unknown"
        last_file = ""

    return {
        "status": "linked",
        "path": str(vault_path),
        "is_obsidian": info["is_obsidian"],
        "md_files": md_count,
        "last_modified": last_mod,
        "last_modified_file": last_file,
        "has_bid_kit": info.get("has_bid_kit", False),
        "has_memory": info.get("has_memory", False),
        "message": f"Vault linked: {md_count} .md files, last modified {last_mod}",
    }


# ── Write-back (v3.4: cross-platform sync) ───────────────────────────

def write_vault_file(relative_path: str, content: str,
                     create_dirs: bool = True) -> dict:
    """Write a file to the Obsidian vault.

    Used by the Windows EXE to sync memory back to the vault so the
    Linux build and Claude Project can read it.

    Only writes to memory/ and conversations/ directories.
    Refuses to write to bid_kit/ or agents/ (those are governance files
    managed manually).

    Args:
        relative_path: path relative to vault root (e.g. "memory/ceo_prefs.md")
        content: text content to write
        create_dirs: create parent directories if they don't exist

    Returns a consistent envelope (pass 10g normalization):
        {ok, error, path, chars, wrote_at}
    Where error="" on success, and path/chars/wrote_at are populated on
    success or carry empty/zero defaults on failure. This lets callers
    do ``r["chars"]`` without checking which branch ran.
    """
    out = {"ok": False, "error": "", "path": "", "chars": 0, "wrote_at": ""}
    info = detect_vault()
    if not info["found"]:
        out["error"] = "Vault not found"
        return out

    # Safety: only write to allowed directories
    allowed_prefixes = ("memory/", "conversations/", "sync/")
    if not any(relative_path.startswith(p) for p in allowed_prefixes):
        out["error"] = (
            f"Write denied. Only {', '.join(allowed_prefixes)} "
            "directories are writable. Governance files are read-only."
        )
        return out

    # Defense-in-depth: resolve path and verify it stays inside an
    # allowed directory. Blocks memory/../bid_kit/x.md traversal.
    vault_root = Path(info["path"]).resolve()
    fpath = (vault_root / relative_path).resolve()
    allowed_dirs = [vault_root / p.rstrip("/") for p in allowed_prefixes]

    if not fpath.is_relative_to(vault_root):
        out["error"] = "Path escapes vault root"
        return out

    if not any(fpath.is_relative_to(a) for a in allowed_dirs):
        out["error"] = (
            "Write denied. Resolved path lands outside writable "
            "directories (path traversal blocked)."
        )
        return out

    if create_dirs:
        fpath.parent.mkdir(parents=True, exist_ok=True)

    try:
        fpath.write_text(content, encoding="utf-8")
        out.update({
            "ok": True,
            "path": str(fpath),
            "chars": len(content),
            "wrote_at": datetime.now(timezone.utc).isoformat(),
        })
        return out
    except Exception as e:
        out["error"] = str(e)
        return out


def sync_session_summary(session_summary: str, session_id: str = "") -> dict:
    """Write a session summary to the vault for cross-platform continuity.

    Creates a timestamped file in conversations/recent/ so the Linux
    build and Claude Project can see what happened in the Windows session.
    """
    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok

    filename = f"conversations/recent/{session_id}_win.md"
    header = (
        f"---\n"
        f"source: windows_exe\n"
        f"version: 3.4.0\n"
        f"timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"---\n\n"
    )
    return write_vault_file(filename, header + session_summary)


def sync_ceo_preferences(prefs_text: str) -> dict:
    """Sync CEO preferences to the vault.

    Appends to memory/ceo_prefs.md with a datestamp so cross-platform
    builds see the latest CEO preferences learned from Windows sessions.
    """
    existing = read_vault_file("memory/ceo_prefs.md") or ""
    datestamp = f"\n\n## Windows sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
    updated = existing + datestamp + prefs_text
    return write_vault_file("memory/ceo_prefs.md", updated)


def sync_project_state(project_data: dict) -> dict:
    """Sync active project state to the vault.

    Writes a structured markdown file that both Linux and Claude Project
    can parse for project status context.
    """
    content = f"# Active Projects (synced from Windows EXE)\n\n"
    content += f"_Last synced: {datetime.now(timezone.utc).isoformat()}_\n\n"

    for name, data in project_data.items():
        content += f"## {name}\n"
        for k, v in data.items():
            content += f"- **{k}**: {v}\n"
        content += "\n"

    return write_vault_file("memory/projects.md", content)


def get_sync_status() -> dict:
    """Get the cross-platform sync status.

    Checks for sync markers from other platforms to show what's been
    synced and when.
    """
    info = detect_vault()
    if not info["found"]:
        return {"synced": False, "platforms": {}}

    vault_path = Path(info["path"])
    platforms = {}

    # Check for Windows sync markers
    win_files = list((vault_path / "conversations" / "recent").glob("*_win.md")) \
        if (vault_path / "conversations" / "recent").exists() else []
    if win_files:
        latest = max(win_files, key=lambda f: f.stat().st_mtime)
        platforms["windows"] = {
            "last_sync": datetime.fromtimestamp(
                latest.stat().st_mtime).isoformat()[:16],
            "session_count": len(win_files),
        }

    # Check for Linux sync markers
    linux_files = list((vault_path / "conversations" / "recent").glob("*_linux.md")) \
        if (vault_path / "conversations" / "recent").exists() else []
    if linux_files:
        latest = max(linux_files, key=lambda f: f.stat().st_mtime)
        platforms["linux"] = {
            "last_sync": datetime.fromtimestamp(
                latest.stat().st_mtime).isoformat()[:16],
            "session_count": len(linux_files),
        }

    # Check for Claude Project sync markers
    claude_files = list((vault_path / "conversations" / "recent").glob("*_claude.md")) \
        if (vault_path / "conversations" / "recent").exists() else []
    if claude_files:
        latest = max(claude_files, key=lambda f: f.stat().st_mtime)
        platforms["claude_project"] = {
            "last_sync": datetime.fromtimestamp(
                latest.stat().st_mtime).isoformat()[:16],
            "session_count": len(claude_files),
        }

    return {
        "synced": bool(platforms),
        "platforms": platforms,
        "vault_path": str(vault_path),
    }
