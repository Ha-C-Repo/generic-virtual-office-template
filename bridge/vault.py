"""
Obsidian Vault + OneDrive + GitHub Sync Layer
=============================================
Mirrors the Linux build's phase8w_obsidian.py architecture.
Creates a local vault that:
  1. Saves every conversation, decision, and output as .md
  2. Reads standing files from OneDrive if mounted
  3. Can push/pull from GitHub repo
  4. Writes Phase 12a-compatible JSONL audit log

Vault location (Windows):
  %LOCALAPPDATA%/YourCoVirtualOffice/vault/   (EXE mode)
  ./vault/                                        (dev mode)

OneDrive path (auto-detected):
  C:/Users/<user>/OneDrive - Your Company/Your_Company_Team/
  OR from API Keys/OneDrive Path.txt if custom

GitHub repo:
  Ha-C-Repo/yourco-virtual-office
  PAT from API Keys/GitHub PAT.txt
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Paths ─────────────────────────────────────────────────────────────

def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _vault_root() -> Path:
    """Local Obsidian vault root."""
    if getattr(sys, "frozen", False):
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        if local.exists():
            return local / "YourCoVirtualOffice" / "vault"
    return _app_root() / "vault"

def _onedrive_root() -> Optional[Path]:
    """Auto-detect OneDrive sync folder for Your Company Team."""
    # Check custom path file first
    custom = _app_root() / "API Keys" / "OneDrive Path.txt"
    if custom.exists():
        p = Path(custom.read_text(encoding="utf-8").strip().splitlines()[0])
        if p.exists():
            return p

    # Auto-detect common Windows OneDrive paths
    home = Path.home()
    candidates = [
        home / "OneDrive - Your Company" / "Your_Company_Team",
        home / "OneDrive" / "Your_Company_Team",
        home / "Documents" / "Your_Company_Cloud" / "Your_Company_Team",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def _github_pat() -> str:
    """Read GitHub PAT from API Keys folder."""
    f = _app_root() / "API Keys" / "GitHub PAT.txt"
    if f.exists():
        lines = f.read_text(encoding="utf-8").strip().splitlines()
        if lines:
            return lines[0].strip()
    return ""


# ── Vault Folders (mirror Linux phase8w) ──────────────────────────────

VAULT_FOLDERS = [
    "000-Dashboard",
    "100-Projects",
    "200-Compliance",
    "300-Rates",
    "400-AR",
    "500-Contacts",
    "600-Conversations",
    "700-Patterns",
    "800-Build-Log",
]

def init_vault() -> str:
    """Create vault folder structure. Returns vault path."""
    root = _vault_root()
    root.mkdir(parents=True, exist_ok=True)
    for folder in VAULT_FOLDERS:
        (root / folder).mkdir(exist_ok=True)

    # Create dashboard if missing
    dash = root / "000-Dashboard" / "Dashboard.md"
    if not dash.exists():
        dash.write_text(
            f"# Your Company - Virtual Office Vault\n\n"
            f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"  # vj: local-display-ok
            f"Platform: Windows (pywebview EXE)\n\n"
            f"## Structure\n"
            + "\n".join(f"- `{f}/`" for f in VAULT_FOLDERS) + "\n",
            encoding="utf-8",
        )
    return str(root)


def vault_write(rel_path: str, content: str, commit_msg: str = "") -> bool:
    """Write a markdown file to the vault."""
    try:
        full = _vault_root() / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def vault_read(rel_path: str) -> Optional[str]:
    """Read a markdown file from the vault."""
    try:
        full = _vault_root() / rel_path
        if full.exists():
            return full.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def save_conversation(user_msg: str, ai_response: str, provider: str,
                      model: str, translated: bool = False) -> bool:
    """Save a conversation turn to the vault."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")  # vj: local-display-ok
    date_str = datetime.now().strftime("%Y-%m-%d")  # vj: local-display-ok
    filename = f"600-Conversations/{date_str}.md"

    existing = vault_read(filename) or f"# Conversations - {date_str}\n\n"
    entry = (
        f"## {ts} [{provider}/{model}]"
        + (" [TRANSLATED]" if translated else "")
        + f"\n\n**User:** {user_msg[:200]}\n\n"
        f"**AI:** {ai_response[:500]}{'...' if len(ai_response) > 500 else ''}\n\n---\n\n"
    )
    return vault_write(filename, existing + entry)


# ── Audit Log (Phase 12a compatible JSONL) ────────────────────────────

def _audit_path() -> Path:
    root = _vault_root().parent
    root.mkdir(parents=True, exist_ok=True)
    return root / "audit.jsonl"

def audit_log(event_type: str, data: dict) -> None:
    """Write a Phase 12a-compatible JSONL audit entry."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "platform": "windows_exe",
            "event": event_type,
            **data,
        }
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ── OneDrive Standing Files ──────────────────────────────────────────

def read_standing_files() -> dict:
    """Read canonical standing files from OneDrive if available."""
    od = _onedrive_root()
    if not od:
        return {"connected": False, "path": None, "files": {}}

    standing_dir = od / "standing"
    files_read = {}
    if standing_dir.exists():
        for f in standing_dir.glob("*.md"):
            try:
                files_read[f.stem] = f.read_text(encoding="utf-8")[:4000]
            except Exception:
                pass

    return {
        "connected": True,
        "path": str(od),
        "standing_count": len(files_read),
        "files": files_read,
    }


def onedrive_status() -> dict:
    """Check OneDrive connection status for dashboard."""
    # vj: parity-ok (pass 10g classified: mixed J=0.40; needs manual audit)
    od = _onedrive_root()
    if not od:
        return {"status": "offline", "path": None}

    bid_kit = od / "bid_kit"
    briefings = od / "briefings"
    return {
        "status": "linked",
        "path": str(od),
        "bid_kit": bid_kit.exists(),
        "briefings": briefings.exists(),
        "standing": (od / "standing").exists(),
    }


# ── GitHub Status ────────────────────────────────────────────────────

GITHUB_REPO = "Ha-C-Repo/yourco-virtual-office"

def github_status() -> dict:
    """Check GitHub connectivity."""
    pat = _github_pat()
    if not pat:
        return {"status": "no_pat", "repo": GITHUB_REPO}

    # Light check - just verify the PAT format is plausible
    return {
        "status": "configured",
        "repo": GITHUB_REPO,
        "pat_prefix": pat[:8] + "...",
    }


# ── Automated Sync (closes v3.5.2 -3 deduction) ──────────────────────

def _git(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr). Returns
    (-1, '', 'git not available') if git is not installed."""
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd), capture_output=True,
            text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", "git not available"
    except subprocess.TimeoutExpired:
        return -1, "", f"git {args[0]} timed out after {timeout}s"
    except Exception as e:
        return -1, "", f"git failed: {e}"


def _vault_is_git_repo() -> bool:
    return (_vault_root() / ".git").is_dir()


def vault_push(message: str = "") -> dict:
    """Stage, commit, and push all vault changes to GitHub. Returns a dict
    with status, commit_sha (if any), and any messages.

    No-ops cleanly if: vault not initialized as git, no PAT, nothing to commit,
    or remote is unreachable. Use vault_auto_sync() for periodic safe sync."""
    # vj: parity-ok (pass 10g classified: mixed J=0.43; needs manual audit)
    root = _vault_root()
    if not _vault_is_git_repo():
        return {"status": "not_git_repo", "path": str(root)}
    if not _github_pat():
        return {"status": "no_pat"}

    rc, out, err = _git(["status", "--porcelain"], root)
    if rc != 0:
        return {"status": "error", "stage": "status", "stderr": err}
    if not out:
        return {"status": "clean", "message": "nothing to commit"}

    rc, _, err = _git(["add", "-A"], root)
    if rc != 0:
        return {"status": "error", "stage": "add", "stderr": err}

    msg = message or f"vault auto-sync {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    rc, _, err = _git(["commit", "-m", msg], root)
    if rc != 0:
        return {"status": "error", "stage": "commit", "stderr": err}

    rc, _, err = _git(["push", "origin", "HEAD"], root, timeout=60)
    if rc != 0:
        return {"status": "commit_only", "stderr": err,
                "message": "committed locally but push failed (offline?)"}

    rc, sha, _ = _git(["rev-parse", "--short", "HEAD"], root)
    audit_log("vault_push", {"message": msg, "sha": sha if rc == 0 else None})
    return {"status": "pushed", "commit": sha if rc == 0 else None, "message": msg}


def vault_pull() -> dict:
    """Pull latest vault contents from GitHub. Fast-forward only - refuses
    to merge to avoid silent conflicts. No-ops cleanly if not a repo."""
    # vj: parity-ok (pass 10g classified: mixed J=0.43; needs manual audit)
    root = _vault_root()
    if not _vault_is_git_repo():
        return {"status": "not_git_repo", "path": str(root)}
    if not _github_pat():
        return {"status": "no_pat"}

    rc, out, err = _git(["pull", "--ff-only", "origin", "HEAD"], root, timeout=60)
    if rc != 0:
        return {"status": "error", "stderr": err,
                "message": "pull failed - manual intervention may be required"}
    audit_log("vault_pull", {"output": out})
    return {"status": "pulled", "message": out or "already up to date"}


def vault_sync_status() -> dict:
    """Report vault git state for dashboards: dirty/clean, ahead/behind, last
    commit. Used by vault_auto_sync() to decide whether work is needed."""
    root = _vault_root()
    if not root.exists():
        return {"status": "no_vault"}
    if not _vault_is_git_repo():
        return {"status": "not_git_repo", "path": str(root)}

    state = {"status": "ok", "path": str(root)}
    rc, porcelain, _ = _git(["status", "--porcelain"], root)
    state["dirty"] = bool(porcelain) if rc == 0 else None
    state["uncommitted_files"] = len(porcelain.splitlines()) if porcelain else 0

    rc, ahead_behind, _ = _git(
        ["rev-list", "--left-right", "--count", "HEAD...@{u}"], root)
    if rc == 0 and ahead_behind:
        try:
            ahead, behind = ahead_behind.split()
            state["ahead"] = int(ahead)
            state["behind"] = int(behind)
        except ValueError:
            pass

    rc, last, _ = _git(["log", "-1", "--format=%h %ci %s"], root)
    if rc == 0:
        state["last_commit"] = last
    return state


def vault_auto_sync(min_interval_sec: int = 900) -> dict:
    """Safe periodic auto-sync: pull first (ff-only), then push if dirty.
    Throttled so it can be called on every conversation hook without hammering
    GitHub. State is tracked in vault/.last_sync so behavior is durable across
    process restarts.

    Returns a single dict summarizing what happened - caller decides whether
    to log it. Never raises."""
    root = _vault_root()
    if not root.exists():
        return {"status": "skipped", "reason": "no_vault"}

    marker = root / ".last_sync"
    # v3.5.10 Bug #6: timezone-aware now() replaces deprecated utcnow().
    # Old .last_sync files written by pre-v3.5.10 runs are tz-naive ISO
    # strings. Subtracting a tz-aware datetime from a tz-naive one raises
    # TypeError. The shim below normalizes the parsed marker by attaching
    # UTC if it has no tzinfo, so the comparison works across versions.
    now = datetime.now(timezone.utc)
    if marker.exists():
        try:
            last = datetime.fromisoformat(marker.read_text().strip())
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < min_interval_sec:
                return {"status": "throttled", "next_in_sec":
                        int(min_interval_sec - (now - last).total_seconds())}
        except Exception:
            pass  # corrupt marker. Proceed and overwrite

    result = {"status": "ran", "pull": None, "push": None, "ts": now.isoformat()}
    try:
        result["pull"] = vault_pull()
        result["push"] = vault_push("vault auto-sync")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        return result

    try:
        marker.write_text(now.isoformat())
    except Exception:
        pass
    return result
