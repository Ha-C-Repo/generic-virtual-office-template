"""CoworkScheduler - automated task scheduling for the Virtual Office.

Runs 5 recurring tasks on a fixed CT (America/Chicago) schedule using
stdlib threading.Timer only. No new pip dependencies.

Tasks:
  1. morning_brief    - 6 AM CT daily, send SMS summary to Owner
  2. bid_lead_check   - 8 AM CT weekdays, scan for new bid leads
  3. marathon_status  - 10 AM CT Mon/Wed/Fri, check marathon prequal status
  4. ar_reminder      - 4 PM CT weekdays, check outstanding AR invoices
  5. eod_summary      - 5 PM CT weekdays, send end-of-day SMS summary

SMS goes to 7133001865@vtext.com via Gmail draft.
Notifications to Owner: 3 lines max, no em-dashes.

Voice rules: zero em-dashes. Hyphens or periods only.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from vo_app._resources import resource_path

log = logging.getLogger(__name__)

_TZ_CT = ZoneInfo("America/Chicago")
_SCHEDULE_PATH = Path(resource_path("data/cowork_schedule.json"))
_VTEXT_ADDRESS = "7133001865@vtext.com"


def _load_schedule() -> list[dict]:
    try:
        with open(_SCHEDULE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tasks", [])
    except Exception as e:
        log.warning("cowork_scheduler: could not load schedule: %s", e)
        return []


def _seconds_until_next(hour: int, minute: int,
                         days: list[int] | None) -> float:
    """Return seconds until the next firing of (hour, minute) on given weekdays.

    days: list of weekday numbers (0=Mon, 6=Sun). None means every day.
    """
    now = datetime.now(_TZ_CT)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)

    # Advance to next allowed weekday
    for _ in range(8):
        if days is None or candidate.weekday() in days:
            break
        candidate += timedelta(days=1)

    delta = (candidate - now).total_seconds()
    return max(delta, 1.0)


def _send_sms_via_gmail(subject: str, body: str) -> bool:
    """Send a 3-line-max SMS via Gmail draft to the Owner's Verizon gateway."""
    lines = [ln for ln in body.strip().splitlines() if ln.strip()][:3]
    text = "\n".join(lines)
    try:
        from bridge.gmail_sender import create_draft
        create_draft(
            to=_VTEXT_ADDRESS,
            subject=subject,
            body=text,
        )
        log.info("cowork_scheduler: SMS draft created: %s", subject)
        return True
    except Exception as e:
        log.warning("cowork_scheduler: SMS draft failed: %s", e)
        return False


# ── Task implementations ───────────────────────────────────────────────────

def _task_morning_brief():
    """6 AM CT - brief Owner on blockers and deadlines."""
    try:
        from bridge.notifications import _build_morning_briefing
        text = _build_morning_briefing()
        _send_sms_via_gmail("Your Company - Morning Brief", text)
    except Exception as e:
        log.warning("cowork morning_brief error: %s", e)


def _task_bid_lead_check():
    """8 AM CT weekdays - scan for new bid leads and notify if found."""
    try:
        from bridge.bid_scanner import get_leads
        high = get_leads(tier="HIGH", limit=5)
        if high:
            lines = [
                f"Bid leads: {len(high)} high-priority items.",
                high[0].get("title", "")[:80],
                "Open Virtual Office to review.",
            ]
            _send_sms_via_gmail("Your Company - Bid Leads", "\n".join(lines))
    except Exception as e:
        log.warning("cowork bid_lead_check error: %s", e)


def _task_marathon_status():
    """10 AM CT Mon/Wed/Fri - check marathon prequal blocker status."""
    try:
        from bridge.api_integrator import call_claude
        prompt = (
            "marathon status - check current blocker status and "
            "summarize in 3 lines max, no em-dashes."
        )
        result = call_claude(prompt)
        text = str(result)[:240]
        _send_sms_via_gmail("Your Company - Marathon Status", text)
    except Exception as e:
        log.warning("cowork marathon_status error: %s", e)


def _task_ar_reminder():
    """4 PM CT weekdays - check outstanding AR invoices."""
    try:
        from bridge.ar_tracker import get_overdue_invoices
        overdue = get_overdue_invoices(days_past_due=30)
        if overdue:
            lines = [
                f"AR: {len(overdue)} invoices past 30 days.",
                overdue[0].get("client", "")[:60],
                "Review in Virtual Office.",
            ]
            _send_sms_via_gmail("Your Company - AR Reminder", "\n".join(lines))
    except Exception as e:
        log.warning("cowork ar_reminder error: %s", e)


def _task_eod_summary():
    """5 PM CT weekdays - end-of-day SMS summary."""
    try:
        from bridge.bid_scanner import get_leads
        high = get_leads(tier="HIGH", limit=3)
        lines = [
            "Your Company - End of Day.",
            f"High bids: {len(high)}.",
            "Have a good evening.",
        ]
        _send_sms_via_gmail("Your Company - EOD", "\n".join(lines))
    except Exception as e:
        log.warning("cowork eod_summary error: %s", e)


_TASK_MAP = {
    "morning_brief":  _task_morning_brief,
    "bid_lead_check": _task_bid_lead_check,
    "marathon_status": _task_marathon_status,
    "ar_reminder":    _task_ar_reminder,
    "eod_summary":    _task_eod_summary,
}


# ── Scheduler class ────────────────────────────────────────────────────────

class CoworkScheduler:
    """Lightweight stdlib-only scheduler for the 5 cowork tasks.

    Uses threading.Timer, not APScheduler or Celery. Zero new pip deps.
    """

    def __init__(self):
        self._timers: dict[str, threading.Timer] = {}
        self._running = False
        self._schedule: list[dict] = []

    def start(self) -> None:
        self._running = True
        self._schedule = _load_schedule()
        for task_cfg in self._schedule:
            if task_cfg.get("enabled", True):
                self._schedule_next(task_cfg)
        log.info("CoworkScheduler started with %d tasks", len(self._timers))

    def stop(self) -> None:
        self._running = False
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        log.info("CoworkScheduler stopped")

    def _schedule_next(self, task_cfg: dict) -> None:
        task_id = task_cfg["id"]
        hour = int(task_cfg.get("hour_ct", 8))
        minute = int(task_cfg.get("minute_ct", 0))
        days = task_cfg.get("days")  # None = every day

        delay = _seconds_until_next(hour, minute, days)
        fn = _TASK_MAP.get(task_id)
        if fn is None:
            log.warning("CoworkScheduler: unknown task id=%s", task_id)
            return

        def _run():
            if not self._running:
                return
            try:
                log.info("CoworkScheduler: running task=%s", task_id)
                fn()
            except Exception as e:
                log.error("CoworkScheduler task=%s error: %s", task_id, e)
            finally:
                if self._running:
                    self._schedule_next(task_cfg)

        timer = threading.Timer(delay, _run)
        timer.daemon = True
        timer.name = f"cowork_{task_id}"
        timer.start()
        self._timers[task_id] = timer
        fire_at = datetime.now(_TZ_CT) + timedelta(seconds=delay)
        log.debug("CoworkScheduler: %s scheduled at %s CT",
                  task_id, fire_at.strftime("%H:%M"))

    def status(self) -> dict:
        """Return current scheduler status."""
        now_ct = datetime.now(_TZ_CT)
        task_statuses = []
        for task_cfg in self._schedule:
            task_id = task_cfg["id"]
            timer = self._timers.get(task_id)
            if timer and timer.is_alive():
                remaining = max(0.0, timer.interval - (
                    timer.interval - (timer._args[0] if timer._args else 0.0)
                    if timer._args else 0.0
                ))
                task_statuses.append({
                    "id": task_id,
                    "enabled": task_cfg.get("enabled", True),
                    "scheduled": True,
                })
            else:
                task_statuses.append({
                    "id": task_id,
                    "enabled": task_cfg.get("enabled", True),
                    "scheduled": False,
                })
        return {
            "running": self._running,
            "now_ct": now_ct.strftime("%Y-%m-%d %H:%M %Z"),
            "tasks": task_statuses,
        }


# Module-level singleton created by main.py startup.
_scheduler: CoworkScheduler | None = None


def get_scheduler() -> CoworkScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = CoworkScheduler()
    return _scheduler
