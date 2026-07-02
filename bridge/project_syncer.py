"""
Your Company Virtual Office - Project Syncer

Mirrors bid pipeline and compliance events to Project OS markdown files
in the 9-folder project structure.

On every bid event:  pipeline_score -> Project OS/State.md
On compliance event: compliance_grade -> Project OS/Compliance.md
On engagement event: record -> Project OS/Activity.md

Subscribes to event_bus at initialization. File writes are atomic
(write-to-temp then rename) so a crash mid-write never corrupts State.md.

Usage:
    from bridge.project_syncer import ProjectSyncer
    syncer = ProjectSyncer()
    syncer.start()   # registers event_bus subscriptions
    syncer.stop()    # removes subscriptions
"""

import json
import logging
import os
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_SYNCER_INSTANCE = None
_lock = threading.Lock()


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _project_root() -> Path:
    """Return configured project root, same logic as create_project.py."""
    try:
        from bridge.create_project import _project_root as _cp_root
        return _cp_root()
    except Exception:
        from vo_app._resources import resource_path
        return Path(resource_path("data/projects"))


def _find_project_dir(bid_id: int = 0, project_number: str = "") -> Path | None:
    """Find a project directory by bid_id (checked in _project_info.json) or project_number."""
    root = _project_root()
    if not root.exists():
        return None
    for child in root.iterdir():
        if not child.is_dir():
            continue
        # Match by project_number prefix in folder name
        if project_number and child.name.startswith(project_number):
            return child
        # Match by bid_id in _project_info.json
        if bid_id:
            info_file = child / "_project_info.json"
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text(encoding="utf-8"))
                    if int(info.get("bid_id", -1)) == bid_id:
                        return child
                except Exception:
                    pass
    return None


def _fmt_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class ProjectSyncer:
    """Subscribes to event_bus and keeps Project OS markdown files current."""

    def __init__(self):
        self._active = False
        self._callbacks = []  # list of (event_type, callback) tuples for cleanup

    # ── Lifecycle ────────────────────────────────────────────────────

    def start(self) -> None:
        """Register event_bus subscriptions."""
        if self._active:
            return
        from bridge.event_bus import subscribe
        pairs = [
            ("BID_SCANNED",          self._on_bid_event),
            ("BID_WON",              self._on_bid_event),
            ("BID_LOST",             self._on_bid_event),
            ("PROPOSAL_GENERATED",   self._on_bid_event),
            ("PROJECT_CREATED",      self._on_project_created),
            ("COMPLIANCE_FAIL",      self._on_compliance_event),
            ("BLOCKER_ESCALATED",    self._on_compliance_event),
            ("PRODUCTION_LOGGED",    self._on_activity_event),
            ("EMAIL_SENT",           self._on_activity_event),
            ("COST_LOGGED",          self._on_activity_event),
        ]
        for event_type, cb in pairs:
            subscribe(event_type, cb)
            self._callbacks.append((event_type, cb))
        self._active = True
        log.info("ProjectSyncer started (%d subscriptions)", len(self._callbacks))

    def stop(self) -> None:
        """Unregister event_bus subscriptions."""
        if not self._active:
            return
        from bridge.event_bus import unsubscribe
        for event_type, cb in self._callbacks:
            try:
                unsubscribe(event_type, cb)
            except Exception:
                pass
        self._callbacks.clear()
        self._active = False
        log.info("ProjectSyncer stopped")

    # ── Event handlers ───────────────────────────────────────────────

    def _on_bid_event(self, event_type: str, payload: dict) -> None:
        """Mirror pipeline score / state to Project OS/State.md."""
        bid_id = payload.get("bid_id", 0)
        project_number = payload.get("project_number", "")
        project_dir = _find_project_dir(bid_id=bid_id, project_number=project_number)
        if project_dir is None:
            return
        self._write_state_md(project_dir, event_type, payload)

    def _on_project_created(self, event_type: str, payload: dict) -> None:
        """On new project creation, initialize all three OS files."""
        project_number = payload.get("project_number", "")
        bid_id = payload.get("bid_id", 0)
        project_dir = _find_project_dir(bid_id=bid_id, project_number=project_number)
        if project_dir is None:
            return
        self._write_state_md(project_dir, event_type, payload)
        self._write_compliance_md(project_dir, event_type, payload)
        self._write_activity_md(project_dir, event_type, payload)

    def _on_compliance_event(self, event_type: str, payload: dict) -> None:
        """Mirror compliance grade to Project OS/Compliance.md."""
        bid_id = payload.get("bid_id", 0)
        project_number = payload.get("project_number", "")
        project_dir = _find_project_dir(bid_id=bid_id, project_number=project_number)
        if project_dir is None:
            # Fall back: write to all active projects if no specific project found
            self._broadcast_compliance(event_type, payload)
            return
        self._write_compliance_md(project_dir, event_type, payload)

    def _on_activity_event(self, event_type: str, payload: dict) -> None:
        """Append engagement record to Project OS/Activity.md."""
        bid_id = payload.get("bid_id", 0)
        project_number = payload.get("project_number", "")
        project_dir = _find_project_dir(bid_id=bid_id, project_number=project_number)
        if project_dir is None:
            return
        self._write_activity_md(project_dir, event_type, payload)

    # ── File writers ─────────────────────────────────────────────────

    def _write_state_md(self, project_dir: Path, event_type: str, payload: dict) -> None:
        state_file = project_dir / "Project OS" / "State.md"
        project_name = payload.get("project_name", project_dir.name)
        bid_state = payload.get("state", payload.get("bid_state", ""))
        score = payload.get("score", "")
        content = (
            f"# State - {project_name}\n\n"
            f"**Last updated:** {_fmt_ts()}\n"
            f"**Trigger:** {event_type}\n"
        )
        if bid_state:
            content += f"**Pipeline state:** {bid_state}\n"
        if score != "":
            content += f"**Score:** {score}\n"
        score_detail = payload.get("score_detail", payload.get("factors", {}))
        if score_detail:
            content += "\n## Score Factors\n\n"
            for k, v in score_detail.items():
                content += f"- {k}: {v}\n"
        payload_keys = {k: v for k, v in payload.items()
                        if k not in ("score_detail", "factors") and v}
        if payload_keys:
            content += "\n## Event Payload\n\n"
            content += "```json\n" + json.dumps(payload_keys, indent=2, default=str) + "\n```\n"
        try:
            _atomic_write(state_file, content)
            log.debug("ProjectSyncer wrote State.md: %s", state_file)
        except Exception as e:
            log.error("ProjectSyncer State.md write failed: %s", e)

    def _write_compliance_md(self, project_dir: Path, event_type: str, payload: dict) -> None:
        comp_file = project_dir / "Project OS" / "Compliance.md"
        project_name = payload.get("project_name", project_dir.name)
        grade = payload.get("compliance_grade", payload.get("grade", ""))
        content = (
            f"# Compliance - {project_name}\n\n"
            f"**Last updated:** {_fmt_ts()}\n"
            f"**Trigger:** {event_type}\n"
        )
        if grade:
            content += f"**Compliance grade:** {grade}\n"
        blockers = payload.get("blockers", [])
        if blockers:
            content += "\n## Blockers\n\n"
            for b in blockers:
                if isinstance(b, dict):
                    content += f"- [{b.get('severity','?')}] {b.get('item', b)}\n"
                else:
                    content += f"- {b}\n"
        items = payload.get("items", [])
        if items:
            content += "\n## Compliance Items\n\n"
            for item in items:
                if isinstance(item, dict):
                    status = item.get("status", "?")
                    name = item.get("item", "?")
                    content += f"- {status}: {name}\n"
        try:
            _atomic_write(comp_file, content)
            log.debug("ProjectSyncer wrote Compliance.md: %s", comp_file)
        except Exception as e:
            log.error("ProjectSyncer Compliance.md write failed: %s", e)

    def _write_activity_md(self, project_dir: Path, event_type: str, payload: dict) -> None:
        """Append a timestamped entry to Activity.md."""
        act_file = project_dir / "Project OS" / "Activity.md"
        project_name = payload.get("project_name", project_dir.name)
        ts = _fmt_ts()
        entry = f"\n## {ts} - {event_type}\n\n"
        summary = payload.get("summary", payload.get("description", ""))
        if summary:
            entry += f"{summary}\n\n"
        detail_keys = {k: v for k, v in payload.items()
                       if k not in ("summary", "description", "project_name") and v}
        if detail_keys:
            entry += "```json\n" + json.dumps(detail_keys, indent=2, default=str) + "\n```\n"

        # Append mode for activity log
        act_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not act_file.exists():
                act_file.write_text(
                    f"# Activity - {project_name}\n\nEngagement records (append-only).\n",
                    encoding="utf-8",
                )
            with open(act_file, "a", encoding="utf-8") as f:
                f.write(entry)
            log.debug("ProjectSyncer appended Activity.md: %s", act_file)
        except Exception as e:
            log.error("ProjectSyncer Activity.md write failed: %s", e)

    def _broadcast_compliance(self, event_type: str, payload: dict) -> None:
        """Write compliance update to all active project folders (fallback)."""
        root = _project_root()
        if not root.exists():
            return
        for child in root.iterdir():
            if child.is_dir() and (child / "Project OS").exists():
                self._write_compliance_md(child, event_type, payload)

    # ── Manual sync ──────────────────────────────────────────────────

    def sync_project(self, project_number: str = "", bid_id: int = 0) -> dict:
        """Manually trigger a sync for a specific project.

        Reads current pipeline state and writes State.md.
        Returns {"ok": bool, "project_dir": str, "files_written": list}.
        """
        project_dir = _find_project_dir(bid_id=bid_id, project_number=project_number)
        if project_dir is None:
            return {"ok": False, "error": f"Project not found: {project_number or bid_id}"}
        files_written = []
        try:
            if bid_id:
                from bridge.bid_pipeline import _conn
                c = _conn()
                row = c.execute(
                    "SELECT id, name, state, score, updated_at FROM bids WHERE id=?",
                    (bid_id,)
                ).fetchone()
                c.close()
                if row:
                    payload = {
                        "bid_id": bid_id,
                        "project_name": row["name"],
                        "state": row["state"],
                        "score": row["score"],
                    }
                    self._write_state_md(project_dir, "MANUAL_SYNC", payload)
                    files_written.append(str(project_dir / "Project OS" / "State.md"))
            return {"ok": True, "project_dir": str(project_dir), "files_written": files_written}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Health check (for VJ scan) ────────────────────────────────────

    def check_stale_state_files(self, max_age_hours: int = 48) -> list:
        """Return list of State.md files not updated in max_age_hours.

        Called by self_repair.py syncer health check category.
        """
        from datetime import timedelta
        stale = []
        root = _project_root()
        if not root.exists():
            return stale
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        for child in root.iterdir():
            if not child.is_dir():
                continue
            state_file = child / "Project OS" / "State.md"
            if state_file.exists():
                mtime = datetime.fromtimestamp(
                    state_file.stat().st_mtime, tz=timezone.utc
                )
                if mtime < cutoff:
                    stale.append({
                        "project_dir": child.name,
                        "state_md": str(state_file),
                        "last_updated": mtime.isoformat(),
                        "age_hours": round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 1),
                    })
        return stale


# ── Module-level singleton ────────────────────────────────────────────

def get_syncer() -> ProjectSyncer:
    """Return the module-level syncer singleton, creating it if needed."""
    global _SYNCER_INSTANCE
    with _lock:
        if _SYNCER_INSTANCE is None:
            _SYNCER_INSTANCE = ProjectSyncer()
    return _SYNCER_INSTANCE


def start_syncer() -> None:
    """Initialize and start the module-level syncer. Safe to call multiple times."""
    get_syncer().start()


def stop_syncer() -> None:
    """Stop the module-level syncer."""
    if _SYNCER_INSTANCE is not None:
        _SYNCER_INSTANCE.stop()


def write_vote_manifest(bid_number: str, manifest_data: dict) -> bool:
    """Write the three-pass vote manifest into the project folder.

    Thin wrapper around write_takeoff_json() for the canonical manifest path.
    """
    return write_takeoff_json(
        bid_number,
        "3.Estimate/Takeoff/vote_manifest.json",
        manifest_data,
    )


def write_takeoff_json(
    bid_number: str,
    subpath: str,
    data: dict | list,
) -> bool:
    """Write a JSON file into the project folder for a bid.

    Locates the project folder by bid_number (treated as project_number),
    then writes data atomically to <project_dir>/<subpath>.

    Returns True if written, False if project folder not found or write fails.

    Usage:
        write_takeoff_json("BID-04", "3.Estimate/Takeoff/validation_log.json", log)
        write_takeoff_json("BID-04", "3.Estimate/Audit/fresh_instance_audit.json", result)
    """
    project_dir = _find_project_dir(project_number=bid_number)
    if project_dir is None:
        log.debug("write_takeoff_json: no project dir for bid_number=%s", bid_number)
        return False
    target = project_dir / Path(subpath)
    try:
        _atomic_write(target, json.dumps(data, indent=2, default=str))
        log.info("write_takeoff_json: wrote %s", target)
        return True
    except Exception as e:
        log.error("write_takeoff_json failed %s: %s", target, e)
        return False


def write_audit_md(
    bid_number: str,
    subpath: str,
    content: str,
) -> bool:
    """Write a markdown file into the project folder for a bid.

    Same as write_takeoff_json but for text content. Atomic write.
    Returns True on success, False if project folder not found.

    Usage:
        write_audit_md("BID-04", "3.Estimate/Audit/fresh_instance_audit.md", text)
    """
    project_dir = _find_project_dir(project_number=bid_number)
    if project_dir is None:
        log.debug("write_audit_md: no project dir for bid_number=%s", bid_number)
        return False
    target = project_dir / Path(subpath)
    try:
        _atomic_write(target, content)
        log.info("write_audit_md: wrote %s", target)
        return True
    except Exception as e:
        log.error("write_audit_md failed %s: %s", target, e)
        return False
