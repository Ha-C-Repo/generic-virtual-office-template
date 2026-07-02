"""
Your Company Virtual Office - Blocker Tracker

Stores blocker open dates and calculates live age in days.
Drives the pulse escalation system in the frontend:
  0-6 days  → static red border
  7-13 days → pulse-slow (2.5s)
  14+ days  → pulse-fast (1.2s) + ESCALATED badge

Data stored in data/blockers.json - survives restarts.
"""

import json
from datetime import date, datetime
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BLOCKERS_PATH = _DATA_DIR / "blockers.json"

# Default blockers - seeded from known Your Company compliance state
# MC-07: severity drives compliance grade penalty (high=-15, med=-7, low=-3)
_DEFAULT_BLOCKERS = [
    {
        "id": "emr-letter",
        "name": "EMR Letter",
        "status": "BLOCKED",
        "open_date": "2026-04-09",
        "action": "Call Texas Mutual: 800-859-5995 · Policy [POLICY NUMBER] · Request current EMR letter for ISNetworld",
        "owner": "Owner",
        "severity": "critical",
        "depends_on": None,
    },
    {
        "id": "isn-marathon",
        "name": "ISN [ISN ID] → Marathon",
        "status": "BLOCKED",
        "open_date": "2026-04-09",
        "action": "Dependent on EMR letter. Cannot submit to ISNetworld until EMR clears.",
        "owner": "Joseph",
        "severity": "high",
        "depends_on": "emr-letter",
    },
    {
        "id": "auto-liability",
        "name": "Auto Liability - $2M CSL",
        "status": "PENDING",
        "open_date": "2026-04-20",
        "action": "Amber handling carrier upgrade. Currently $50K/$100K. Awaiting carrier response.",
        "owner": "Amber",
        "severity": "med",
        "depends_on": None,
    },
    {
        "id": "ravs-gap",
        "name": "RAVS Coverage Gap",
        "status": "OPEN",
        "open_date": "2026-04-15",
        "action": "16 of 18 on disk. Missing: Crane Operations + HAZCOM. Upload to ISNetworld.",
        "owner": "Joseph",
        "severity": "low",
        "depends_on": None,
    },
]


# MC-07: severity-to-penalty mapping for compliance grade adjustment
# 4 tiers per Owner: critical (revenue-blocking), high (access-blocking),
# med (operational), low (paperwork)
SEVERITY_PENALTY = {
    "critical": 15.0,
    "high": 10.0,
    "med": 7.0,
    "low": 3.0,
}


def severity_penalty(blocker: dict) -> float:
    """Return percentage-point penalty for an escalated blocker.

    Defaults to medium (7pp) when severity is missing or unknown.
    """
    sev = (blocker.get("severity") or "med").lower()
    return SEVERITY_PENALTY.get(sev, 7.0)


def _load() -> list:
    """Load blockers from JSON file, or seed defaults."""
    try:
        if _BLOCKERS_PATH.exists():
            return json.loads(_BLOCKERS_PATH.read_text())
    except Exception:
        pass
    # Seed defaults
    _save(_DEFAULT_BLOCKERS)
    return _DEFAULT_BLOCKERS


def _save(blockers: list):
    """Persist blockers to JSON."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _BLOCKERS_PATH.write_text(json.dumps(blockers, indent=2))


def get_all(include_resolved: bool = False) -> list:
    """Get all blockers with calculated ages and escalation levels.

    By default excludes RESOLVED blockers. Pass include_resolved=True
    to see the full history.
    """
    blockers = _load()
    today = date.today()
    result = []
    for b in blockers:
        if not include_resolved and b.get("status") == "RESOLVED":
            continue
        open_date = date.fromisoformat(b["open_date"])
        days_open = (today - open_date).days
        # Determine escalation level
        if b["status"] == "BLOCKED":
            if days_open >= 14:
                pulse = "fast"
                escalated = True
            elif days_open >= 7:
                pulse = "slow"
                escalated = False
            else:
                pulse = "none"
                escalated = False
        else:
            pulse = "none"
            escalated = False

        result.append({
            **b,
            "days_open": days_open,
            "pulse": pulse,
            "escalated": escalated,
            "css_class": f"bk {'red fast' if pulse == 'fast' else 'red pulse' if pulse == 'slow' else 'red' if b['status'] == 'BLOCKED' else 'amb'}",
            "days_label": f"{days_open} DAYS" if b["status"] == "BLOCKED" else b["status"].upper(),
        })
    return result


def get_blocked() -> list:
    """Get only BLOCKED items."""
    return [b for b in get_all() if b["status"] == "BLOCKED"]


def get_escalated() -> list:
    """Get blockers that are 14+ days old."""
    return [b for b in get_all() if b.get("escalated")]


def has_escalated() -> bool:
    """Returns True if any blocker is 14+ days (for KPI pulse)."""
    return len(get_escalated()) > 0


def add_blocker(name: str, action: str, owner: str = "Owner",
                status: str = "BLOCKED", depends_on: str = None,
                severity: str = "med") -> dict:
    """Add a new blocker. Returns the new blocker with calculated age."""
    blockers = _load()
    bid = name.lower().replace(" ", "-").replace("-", "-")[:30]
    new = {
        "id": bid,
        "name": name,
        "status": status,
        "open_date": date.today().isoformat(),
        "action": action,
        "owner": owner,
        "depends_on": depends_on,
        "severity": severity,
    }
    blockers.append(new)
    _save(blockers)
    return get_all()[-1]


def resolve_blocker(blocker_id: str) -> bool:
    """Mark a blocker as RESOLVED. Returns True if found."""
    blockers = _load()
    for b in blockers:
        if b["id"] == blocker_id:
            b["status"] = "RESOLVED"
            b["resolved_date"] = date.today().isoformat()
            _save(blockers)
            return True
    return False


def update_blocker(blocker_id: str, **kwargs) -> bool:
    """Update fields on a blocker."""
    blockers = _load()
    for b in blockers:
        if b["id"] == blocker_id:
            for k, v in kwargs.items():
                if k in ("name", "action", "owner", "status", "depends_on"):
                    b[k] = v
            _save(blockers)
            return True
    return False


def summary_for_briefing() -> str:
    """Build a compact blocker summary for the morning briefing SMS.

    Format (MC-01 fix): name - <days_open>d open [ESCALATED]
    Disambiguates "age since logged" from "days until deadline".
    """
    blocked = get_blocked()
    if not blocked:
        return "No active blockers."
    lines = []
    for b in blocked:
        badge = " [ESCALATED]" if b.get("escalated") else ""
        lines.append(f"⛔ {b['name']} - {b['days_open']}d open{badge}")
    return "\n".join(lines)
