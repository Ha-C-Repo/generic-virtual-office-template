"""Production tracker (Phase 26, v5.8.0).

Every piece mark goes through a state machine:
ORDERED -> CUT -> FIT_UP -> WELD -> FINISH -> QC_PASS -> SHIPPED -> ERECTED -> INSPECTED

State transitions recorded with timestamp, worker name, and optional
photo. Storage: JSONL file per job in data/production/{job_number}.jsonl.

Owner sees: "127/164 members complete (77%). 3 stuck in WELD >48 hrs."

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)


STATES = [
    "ORDERED", "CUT", "FIT_UP", "WELD", "FINISH",
    "QC_PASS", "SHIPPED", "ERECTED", "INSPECTED",
]

STATE_ORDER = {s: i for i, s in enumerate(STATES)}


def _prod_dir() -> Path:
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            base = Path(local) / "YourCompany" / "VirtualOffice" / "data"
        else:
            base = Path(sys.executable).parent / "data"
    else:
        base = Path(__file__).resolve().parent.parent.parent / "data"
    return base / "production"


_PROD_DIR = _prod_dir()


def _job_path(job_number: str) -> Path:
    _PROD_DIR.mkdir(parents=True, exist_ok=True)
    safe = job_number.replace("/", "_").replace("\\", "_")
    return _PROD_DIR / f"{safe}.jsonl"


def _load_events(job_number: str) -> list[dict]:
    p = _job_path(job_number)
    if not p.exists():
        return []
    events = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _append_event(job_number: str, event: dict) -> None:
    p = _job_path(job_number)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def get_piece_status(job_number: str, piece_mark: str) -> dict:
    """Get the current status of a single piece."""
    events = _load_events(job_number)
    latest = None
    for e in events:
        if e.get("piece_mark") == piece_mark:
            latest = e
    if latest is None:
        return {"piece_mark": piece_mark, "status": "UNKNOWN",
                "job_number": job_number}
    return latest


def update_piece_status(
    job_number: str,
    piece_mark: str,
    new_status: str,
    worker_name: str = "",
    photo_path: str | None = None,
    notes: str = "",
) -> dict:
    """Record a piece status transition.

    Returns dict with piece_mark, previous_status, new_status,
    timestamp, worker, duration_in_stage_hrs.
    """
    new_status = new_status.upper()
    if new_status not in STATE_ORDER:
        return {"success": False,
                "error": f"invalid status: {new_status}. "
                         f"Valid: {', '.join(STATES)}"}

    current = get_piece_status(job_number, piece_mark)
    prev_status = current.get("status", "UNKNOWN")

    # Calculate time in previous stage
    prev_ts = current.get("timestamp")
    duration_hrs = 0.0
    if prev_ts:
        try:
            prev_dt = datetime.fromisoformat(prev_ts)
            duration_hrs = (datetime.now() - prev_dt).total_seconds() / 3600  # vj: duration-math
        except (ValueError, TypeError):
            pass

    event = {
        "job_number": job_number,
        "piece_mark": piece_mark,
        "previous_status": prev_status,
        "status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "worker": worker_name,
        "photo_path": photo_path or "",
        "notes": notes,
        "duration_in_stage_hrs": round(duration_hrs, 2),
    }

    _append_event(job_number, event)
    event["success"] = True
    return event


def get_job_status(job_number: str) -> dict:
    """Get aggregated status for all pieces in a job.

    Returns dict with per-stage counts, completion percentage,
    and pieces stuck > 48 hours.
    """
    events = _load_events(job_number)

    # Build latest status per piece
    latest: dict[str, dict] = {}
    for e in events:
        pm = e.get("piece_mark", "")
        if pm:
            latest[pm] = e

    total = len(latest)
    by_stage: dict[str, int] = {s: 0 for s in STATES}
    by_stage["UNKNOWN"] = 0
    stuck: list[dict] = []

    now = datetime.now(timezone.utc)
    for pm, ev in latest.items():
        st = ev.get("status", "UNKNOWN")
        if st in by_stage:
            by_stage[st] += 1
        else:
            by_stage["UNKNOWN"] += 1

        # Check for stuck pieces (>48 hrs in same stage)
        ts = ev.get("timestamp")
        if ts and st not in ("QC_PASS", "SHIPPED", "ERECTED", "INSPECTED"):
            try:
                dt = datetime.fromisoformat(ts)
                hrs = (now - dt).total_seconds() / 3600
                if hrs > 48:
                    stuck.append({
                        "piece_mark": pm,
                        "status": st,
                        "hours_in_stage": round(hrs, 1),
                    })
            except (ValueError, TypeError):
                pass

    completed = by_stage.get("INSPECTED", 0)
    shipped = sum(by_stage.get(s, 0) for s in
                  ["SHIPPED", "ERECTED", "INSPECTED"])
    fab_done = sum(by_stage.get(s, 0) for s in
                   ["QC_PASS", "SHIPPED", "ERECTED", "INSPECTED"])

    return {
        "job_number": job_number,
        "total_pieces": total,
        "by_stage": by_stage,
        "fabricated": fab_done,
        "fabricated_pct": round(fab_done / max(total, 1) * 100, 1),
        "shipped": shipped,
        "shipped_pct": round(shipped / max(total, 1) * 100, 1),
        "erected": by_stage.get("ERECTED", 0) + completed,
        "erected_pct": round(
            (by_stage.get("ERECTED", 0) + completed) /
            max(total, 1) * 100, 1),
        "completed": completed,
        "stuck_pieces": stuck,
        "stuck_count": len(stuck),
    }
