"""
Your Company Virtual Office - Reminders & Follow-up Automation

Background checks:
- Bid in REVIEWING for 3+ days → reminder to Owner
- Bid deadline within 48 hours → urgent alert
- Blocker open 30+ days → escalation push
- Contact not reached in 30+ days → follow-up suggestion

Runs as background thread, fires SMS or toast.
"""
import threading, time
from datetime import datetime, timedelta, date

_running = False

def get_active_reminders():
    """Check all reminder sources and return pending items."""
    reminders = []

    # Stale bids
    try:
        from bridge.bid_pipeline import get_stale_bids
        stale = get_stale_bids(days=3)
        for b in stale:
            reminders.append({
                "type": "stale_bid", "priority": "high",
                "title": f"Bid stale: {b['name']}",
                "detail": f"In REVIEWING for 3+ days. Decide: pursue or pass.",
                "action": f"Review bid '{b['name']}' and decide to pursue or pass",
                "bid_id": b["id"],
            })
    except Exception:pass

    # Upcoming deadlines
    try:
        from bridge.bid_pipeline import get_pipeline
        active = get_pipeline()
        for b in active:
            if b.get("deadline"):
                try:
                    dl = date.fromisoformat(b["deadline"])
                    days_until = (dl - date.today()).days
                    if 0 <= days_until <= 2:
                        reminders.append({
                            "type": "deadline", "priority": "urgent",
                            "title": f"Deadline in {days_until}d: {b['name']}",
                            "detail": f"Due {b['deadline']}. State: {b['state']}.",
                            "action": f"Bid '{b['name']}' deadline is {b['deadline']}",
                            "bid_id": b["id"],
                        })
                except Exception:pass
    except Exception:pass

    # Escalated blockers (configurable threshold - v3.2)
    try:
        from bridge.blockers import get_all
        try:
            from bridge.notifications import get_escalation_days
            esc_days = get_escalation_days()
        except Exception:
            esc_days = 30  # fallback default
        for b in get_all():
            if b.get("days_open", 0) >= esc_days and b["status"] == "BLOCKED":
                reminders.append({
                    "type": "blocker_critical", "priority": "urgent",
                    "title": f"Blocker {esc_days}+ days: {b['name']}",
                    "detail": f"Open {b['days_open']} days. Action: {b['action'][:60]}",
                    "action": b["action"],
                })
    except Exception:pass

    # Stale contacts (uses same escalation threshold)
    try:
        from bridge.contacts import get_all as get_contacts
        try:
            from bridge.notifications import get_escalation_days
            stale_days = get_escalation_days()
        except Exception:
            stale_days = 30
        cutoff = (date.today() - timedelta(days=stale_days)).isoformat()
        for c in get_contacts():
            lc = c.get("last_contact")
            if lc and lc < cutoff and "internal" not in (c.get("tags") or ""):
                reminders.append({
                    "type": "follow_up", "priority": "low",
                    "title": f"Follow up: {c['name']} ({c['company']})",
                    "detail": f"Last contact: {lc}. Consider reaching out.",
                    "action": f"Draft a follow-up email to {c['name']} at {c['company']}",
                    "contact_id": c["id"],
                })
    except Exception:pass

    # Sort by priority
    pri_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    reminders.sort(key=lambda r: pri_order.get(r["priority"], 5))
    return reminders


def start_reminder_loop(sms_fn=None, toast_fn=None):
    """Background thread: check reminders every 30 minutes, push alerts."""
    global _running
    if _running: return
    _running = True

    def _loop():
        while _running:
            try:
                reminders = get_active_reminders()
                urgent = [r for r in reminders if r["priority"] in ("urgent", "high")]
                if urgent and sms_fn:
                    lines = [f"VO Reminder: {len(urgent)} item(s) need attention"]
                    for r in urgent[:3]:
                        lines.append(f"• {r['title']}")
                    try:
                        sms_fn("\n".join(lines))
                    except Exception:pass
                if urgent and toast_fn:
                    toast_fn("Your Company - Reminders", f"{len(urgent)} urgent item(s)")
            except Exception:pass
            time.sleep(1800)  # 30 minutes

    threading.Thread(target=_loop, daemon=True, name="reminder_loop").start()


def stop():
    global _running
    _running = False
