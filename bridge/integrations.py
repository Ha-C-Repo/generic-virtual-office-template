"""
Your Company Virtual Office - Integration Modules
OneDrive detection, CEO preferences logger, bid pipeline database.
Ported from the Linux build (Ha-C-Repo/yourco-virtual-office).
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, date, timezone


# ── OneDrive Detection ─────────────────────────────────────────────────

# Windows OneDrive paths to check (in priority order)
_ONEDRIVE_CANDIDATES = [
    Path(os.environ.get("USERPROFILE", "")) / "Documents" / "Your_Company_Cloud" / "Your_Company_Team",
    Path(os.environ.get("USERPROFILE", "")) / "OneDrive" / "Your_Company_Team",
    Path(os.environ.get("USERPROFILE", "")) / "OneDrive - Your Company" / "Your_Company_Team",
    Path.home() / "OneDrive" / "Your_Company_Team",
    Path.home() / "Documents" / "Your_Company_Cloud" / "Your_Company_Team",
]


def detect_onedrive() -> dict:
    """Detect the OneDrive Your_Company_Team folder on this machine.

    Returns dict with:
      found: bool
      path: str or None
      bid_kit: bool - does bid_kit/ subfolder exist
      standing: bool - does standing/ subfolder exist
      active_bids: list of bid folder names
    """
    for candidate in _ONEDRIVE_CANDIDATES:
        if candidate.exists() and candidate.is_dir():
            result = {
                "found": True,
                "path": str(candidate),
                "bid_kit": (candidate / "bid_kit").exists(),
                "standing": (candidate / "standing").exists(),
                "bids_active": (candidate / "bids" / "active").exists(),
                "bids_awarded": (candidate / "bids" / "awarded").exists(),
                "briefings": (candidate / "briefings").exists(),
                "active_bids": [],
            }
            # List active bids
            active_dir = candidate / "bids" / "active"
            if active_dir.exists():
                result["active_bids"] = sorted([
                    d.name for d in active_dir.iterdir()
                    if d.is_dir() and d.name.startswith("NC-")
                ])
            return result

    return {"found": False, "path": None, "bid_kit": False,
            "standing": False, "active_bids": []}


def read_standing_file(filename: str) -> str | None:
    """Read a file from the OneDrive standing/ directory."""
    info = detect_onedrive()
    if not info["found"] or not info["standing"]:
        return None
    fpath = Path(info["path"]) / "standing" / filename
    if fpath.exists():
        return fpath.read_text(encoding="utf-8", errors="replace")
    return None


# ── v3.2: OneDrive Bid Kit Governance Sync (C1) ──────────────────────

def read_bid_kit_governance() -> dict:
    """Read all bid kit governance files from OneDrive for system prompt supplement.

    Reads from: Your_Company_Team/bid_kit/*.md
    Files expected:
      - bid_kit_governance.md   (Three-tier governance rules)
      - bid_kit_rules.md        (Bid submission rules)
      - bid_kit_placeholders.md (Template variable definitions)
      - ceo_preferences_owner.md (CEO learned preferences)
      - compliance_immutable.md (Tier 1 immutable rules)

    Returns dict with file contents and metadata.
    Called at boot to supplement the system prompt.
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.57; needs manual audit)
    info = detect_onedrive()
    if not info["found"] or not info["bid_kit"]:
        return {"found": False, "path": "", "files": {}, "file_count": 0,
                "total_chars": 0, "errors": [],
                "message": "OneDrive bid_kit/ not found. Using built-in governance only."}

    bid_kit_dir = Path(info["path"]) / "bid_kit"
    files = {}
    total_chars = 0
    errors = []

    # Read all .md files in bid_kit/
    for md_file in sorted(bid_kit_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            # Truncate very large files to prevent prompt bloat (max 4KB each)
            if len(content) > 4096:
                content = content[:4096] + "\n\n[... truncated at 4KB for prompt size ...]"
            files[md_file.name] = content
            total_chars += len(content)
        except Exception as e:
            errors.append(f"{md_file.name}: {e}")

    return {
        "found": True,
        "path": str(bid_kit_dir),
        "files": files,
        "file_count": len(files),
        "total_chars": total_chars,
        "errors": errors,
        "message": f"Loaded {len(files)} governance files ({total_chars:,} chars) from OneDrive bid_kit/",
    }


def build_governance_supplement() -> str:
    """Build a system prompt supplement from OneDrive bid kit governance files.

    Returns a string to append to the system prompt. Empty string if nothing found.
    Called once at boot and cached.
    """
    kit = read_bid_kit_governance()
    if not kit["found"] or not kit["files"]:
        return ""

    sections = []
    sections.append("\n═══════════════════════════════════════════════════════════════")
    sections.append("ONEDRIVE GOVERNANCE SUPPLEMENT (synced from Your_Company_Team/bid_kit/)")
    sections.append("═══════════════════════════════════════════════════════════════")

    # Priority order: immutable first, then governance, then CEO prefs
    priority_order = [
        "compliance_immutable.md",
        "bid_kit_governance.md",
        "bid_kit_rules.md",
        "ceo_preferences_owner.md",
        "bid_kit_placeholders.md",
    ]

    loaded_names = set()
    for fname in priority_order:
        if fname in kit["files"]:
            sections.append(f"\n--- {fname} ---")
            sections.append(kit["files"][fname])
            loaded_names.add(fname)

    # Any remaining files not in priority list
    for fname, content in kit["files"].items():
        if fname not in loaded_names:
            sections.append(f"\n--- {fname} ---")
            sections.append(content)

    return "\n".join(sections)


def write_briefing_to_onedrive(content: str, filename: str = None) -> dict:
    """Write a briefing file to OneDrive briefings/ folder.

    Used by the morning brief to persist briefings for cross-device access.
    """
    from datetime import datetime
    info = detect_onedrive()
    if not info["found"]:
        return {"written": False, "message": "OneDrive not found"}

    briefings_dir = Path(info["path"]) / "briefings"
    try:
        briefings_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            now = datetime.now(timezone.utc)
            week = now.isocalendar()
            filename = f"{now.year}-W{week[1]:02d}-briefing.md"
        out_path = briefings_dir / filename
        out_path.write_text(content, encoding="utf-8")
        return {"written": True, "path": str(out_path), "filename": filename}
    except Exception as e:
        return {"written": False, "message": str(e)}


# ── v3.2: Enhanced GitHub Status (C2) ────────────────────────────────

def detect_github_repo() -> dict:
    """Check if the yourco-virtual-office repo is cloned locally.

    Returns dict with:
      found: bool
      path: str or None
      branch: str or None
      last_commit_date: str or None
      last_commit_author: str or None
      last_commit_message: str or None
      has_uncommitted: bool - any modified/untracked files
      remote_url: str or None
    """
    candidates = [
        Path(os.environ.get("USERPROFILE", "")) / "yourco",
        Path(os.environ.get("USERPROFILE", "")) / "yourco-virtual-office",
        Path.home() / "yourco",
        Path.home() / "yourco-virtual-office",
    ]
    for candidate in candidates:
        git_dir = candidate / ".git"
        if git_dir.exists():
            result = {"found": True, "path": str(candidate),
                      "last_commit_date": None, "last_commit_author": None,
                      "last_commit_message": None, "branch": None,
                      "has_uncommitted": False, "remote_url": None}
            # Read branch from HEAD
            head_file = git_dir / "HEAD"
            if head_file.exists():
                head = head_file.read_text().strip()
                if head.startswith("ref: refs/heads/"):
                    result["branch"] = head.replace("ref: refs/heads/", "")

            # Full commit info via git CLI
            try:
                import subprocess
                # Last commit: date, author, message
                out = subprocess.run(
                    ["git", "log", "-1", "--format=%ci|%an|%s"],
                    cwd=str(candidate), capture_output=True, text=True, timeout=5
                )
                if out.returncode == 0 and "|" in out.stdout:
                    parts = out.stdout.strip().split("|", 2)
                    result["last_commit_date"] = parts[0][:10] if len(parts) > 0 else None
                    result["last_commit_author"] = parts[1] if len(parts) > 1 else None
                    result["last_commit_message"] = parts[2][:80] if len(parts) > 2 else None

                # Uncommitted changes
                status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(candidate), capture_output=True, text=True, timeout=5
                )
                if status.returncode == 0:
                    result["has_uncommitted"] = bool(status.stdout.strip())

                # Remote URL
                remote = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=str(candidate), capture_output=True, text=True, timeout=5
                )
                if remote.returncode == 0:
                    result["remote_url"] = remote.stdout.strip()

            except Exception:
                pass
            return result

    return {"found": False, "path": None, "last_commit_date": None,
            "last_commit_author": None, "last_commit_message": None,
            "branch": None, "has_uncommitted": False, "remote_url": None}


# ── CEO Preferences Auto-Logger ────────────────────────────────────────

class CEOLogger:
    """Logs the Owner's interactions for Tier 2 preference mining.

    Writes to a JSONL file next to the EXE (or in the project root).
    Monthly review promotes patterns to Standing Preferences.
    """

    def __init__(self, log_dir: Path | None = None):
        if log_dir is None:
            import sys
            if getattr(sys, "frozen", False):
                log_dir = Path(sys.executable).parent / "data"
            else:
                log_dir = Path(__file__).resolve().parent.parent / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / "ceo_interactions.jsonl"

    def log_interaction(self, message: str, mode: str,
                        translated: bool = False,
                        original: str = "", provider: str = "",
                        model: str = "") -> None:
        """Append a Owner interaction to the log."""
        if mode != "owner":
            return  # Only log the Owner's interactions
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "message": message[:500],
            "translated": translated,
            "original": original[:200] if translated else "",
            "provider": provider,
            "model": model,
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def recent(self, n: int = 20) -> list[dict]:
        """Return the last N interactions."""
        try:
            lines = self.log_path.read_text(encoding="utf-8").strip().split("\n")
            return [json.loads(line) for line in lines[-n:]]
        except Exception:
            return []

    def count(self) -> int:
        """Total logged interactions."""
        try:
            return sum(1 for _ in open(self.log_path, encoding="utf-8"))
        except Exception:
            return 0


# ── Bid Pipeline Database ──────────────────────────────────────────────

class BidPipeline:
    """SQLite-backed bid pipeline tracker.

    Schema matches the Linux build's conversations.db bids table.
    Powers the KPI counters with real data.
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            import sys
            if getattr(sys, "frozen", False):
                data_dir = Path(sys.executable).parent / "data"
            else:
                data_dir = Path(__file__).resolve().parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            # NOTE: This is the legacy proposal-tracking pipeline (proposal_no
            # based). The MODERN state-machine pipeline lives in
            # bridge/bid_pipeline.py and uses data/bid_pipeline.db with a
            # different schema (name/state/tonnage as TEXT). They are
            # separated into different DB files to avoid schema conflicts
            # where the legacy NOT NULL proposal_no column blocks inserts
            # from the new state-machine code path.
            db_path = data_dir / "bid_pipeline_legacy.db"
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_no TEXT UNIQUE NOT NULL,
                    project_name TEXT,
                    gc_name TEXT,
                    gc_contact TEXT,
                    city TEXT DEFAULT 'HOU',
                    status TEXT DEFAULT 'RECEIVED',
                    base_bid_total REAL,
                    tonnage REAL,
                    submission_date TEXT,
                    deadline TEXT,
                    drawing_stage TEXT DEFAULT 'IFC',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    rendering_status TEXT DEFAULT 'placeholder',
                    rendering_path TEXT,
                    notes TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bid_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bid_id INTEGER REFERENCES bids(id),
                    event_type TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def next_number(self, city: str = "HOU") -> str:
        """Generate next sequential proposal number: NC-YYYY-CITY-###"""
        year = date.today().year
        prefix = f"NC-{year}-{city.upper()[:3]}-"
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT proposal_no FROM bids WHERE proposal_no LIKE ? ORDER BY proposal_no DESC LIMIT 1",
                (prefix + "%",)
            ).fetchone()
            if row:
                last_num = int(row[0].split("-")[-1])
                return f"{prefix}{str(last_num + 1).zfill(3)}"
            return f"{prefix}001"

    def add_bid(self, proposal_no: str, project_name: str,
                gc_name: str = "", city: str = "HOU",
                base_bid_total: float = 0, deadline: str = "",
                drawing_stage: str = "IFC", **kwargs) -> int:
        """Insert a new bid. Returns the bid id."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO bids (proposal_no, project_name, gc_name, city,
                   base_bid_total, deadline, drawing_stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (proposal_no, project_name, gc_name, city,
                 base_bid_total, deadline, drawing_stage)
            )
            bid_id = cur.lastrowid
            conn.execute(
                "INSERT INTO bid_events (bid_id, event_type, details) VALUES (?, ?, ?)",
                (bid_id, "CREATED", f"Bid {proposal_no} created for {project_name}")
            )
            return bid_id

    def update_status(self, proposal_no: str, status: str, notes: str = "") -> bool:
        """Update bid status. Valid: RECEIVED, PRE-SCREEN, TAKEOFF, PRICED, SUBMITTED, WON, LOST, EXPIRED."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT id FROM bids WHERE proposal_no = ?", (proposal_no,)).fetchone()
            if not row:
                return False
            conn.execute(
                "UPDATE bids SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE proposal_no = ?",
                (status, proposal_no)
            )
            conn.execute(
                "INSERT INTO bid_events (bid_id, event_type, details) VALUES (?, ?, ?)",
                (row[0], f"STATUS→{status}", notes or f"Status changed to {status}")
            )
            return True

    def get_kpis(self) -> dict:
        """Return KPI data for the dashboard counters."""
        with sqlite3.connect(self.db_path) as conn:
            open_bids = conn.execute(
                "SELECT COUNT(*) FROM bids WHERE status IN ('RECEIVED','PRE-SCREEN','TAKEOFF','PRICED','SUBMITTED')"
            ).fetchone()[0]
            ar_total = conn.execute(
                "SELECT COALESCE(SUM(base_bid_total), 0) FROM bids WHERE status = 'SUBMITTED'"
            ).fetchone()[0]
            active_projects = conn.execute(
                "SELECT COUNT(*) FROM bids WHERE status = 'WON'"
            ).fetchone()[0]
            total_bids = conn.execute("SELECT COUNT(*) FROM bids").fetchone()[0]
            # Days since last bid submitted
            last_sub = conn.execute(
                "SELECT MAX(submission_date) FROM bids WHERE status IN ('SUBMITTED','WON','LOST')"
            ).fetchone()[0]
            days_no_bid = 0
            if last_sub:
                try:
                    last_dt = datetime.strptime(last_sub[:10], "%Y-%m-%d")
                    days_no_bid = (datetime.now() - last_dt).days  # vj: local-time-ok
                except Exception:
                    pass

            return {
                "open_bids": open_bids,
                "ar_balance": round(ar_total / 1000),  # in K
                "active_projects": active_projects,
                "total_bids": total_bids,
                "days_no_bid": days_no_bid,
            }

    def list_bids(self, status: str | None = None, limit: int = 20) -> list[dict]:
        """List bids, optionally filtered by status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM bids WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bids ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def pipeline_summary(self) -> dict:
        """Kanban-style pipeline counts by status."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM bids GROUP BY status"
            ).fetchall()
            return {row[0]: row[1] for row in rows}
