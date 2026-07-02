"""
Your Company Virtual Office - Event Bus

Every action emits a typed event. Any module can subscribe.
New chains created without modifying existing code.

Events: BID_SCANNED, BID_WON, BID_LOST, COST_LOGGED, CERT_EXPIRING,
EMR_CHANGED, PAY_APP_DUE, COMPLIANCE_FAIL, CONTACT_STALE, PROJECT_CREATED,
PROPOSAL_GENERATED, EMAIL_SENT, BLOCKER_ESCALATED, PRODUCTION_LOGGED

Subscribers receive (event_type, payload) and can trigger further events.
"""

import threading, json, traceback
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

_DATA = Path(__file__).resolve().parent.parent / "data"
_LOG = _DATA / "event_log.jsonl"
_lock = threading.Lock()
_subscribers = defaultdict(list)  # event_type → [callback, ...]
_event_history = []  # last 500 events in memory


# ═══ CORE ═══════════════════════════════════════════════════════════

def emit(event_type: str, payload: dict = None, source: str = "system"):
    """Emit an event. All subscribers for this type are called."""
    payload = payload or {}
    event = {
        "type": event_type,
        "payload": payload,
        "source": source,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # Log to disk (append-only JSONL)
    with _lock:
        _event_history.append(event)
        if len(_event_history) > 500:
            _event_history.pop(0)
        try:
            _DATA.mkdir(parents=True, exist_ok=True)
            with open(_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception:pass

    # Notify subscribers
    for callback in _subscribers.get(event_type, []):
        try:
            callback(event_type, payload)
        except Exception as e:
            _log_error(event_type, callback, e)

    # Also notify wildcard subscribers
    for callback in _subscribers.get("*", []):
        try:
            callback(event_type, payload)
        except Exception as e:
            _log_error(event_type, callback, e)


def subscribe(event_type: str, callback):
    """Register a callback for an event type. Use '*' for all events."""
    with _lock:
        if callback not in _subscribers[event_type]:
            _subscribers[event_type].append(callback)


def unsubscribe(event_type: str, callback):
    """Remove a callback."""
    with _lock:
        if callback in _subscribers[event_type]:
            _subscribers[event_type].remove(callback)


def _log_error(event_type, callback, error):
    try:
        from bridge.audit import log
        log("event_bus", "subscriber_error",
            f"Event {event_type} → {callback.__name__}: {error}")
    except Exception:pass


# ═══ EVENT TYPES ════════════════════════════════════════════════════

class Events:
    """Named constants for event types."""
    BID_SCANNED = "BID_SCANNED"
    BID_WON = "BID_WON"
    BID_LOST = "BID_LOST"
    BID_PURSUING = "BID_PURSUING"
    BID_SUBMITTED = "BID_SUBMITTED"
    BID_PASSED = "BID_PASSED"
    PROJECT_CREATED = "PROJECT_CREATED"
    COST_LOGGED = "COST_LOGGED"
    PAY_APP_GENERATED = "PAY_APP_GENERATED"
    PAY_APP_DUE = "PAY_APP_DUE"
    PROPOSAL_GENERATED = "PROPOSAL_GENERATED"
    CHANGE_ORDER_GENERATED = "CHANGE_ORDER_GENERATED"
    EMAIL_SENT = "EMAIL_SENT"
    SMS_SENT = "SMS_SENT"
    COMPLIANCE_FAIL = "COMPLIANCE_FAIL"
    COMPLIANCE_PASS = "COMPLIANCE_PASS"
    CERT_EXPIRING = "CERT_EXPIRING"
    EMR_CHANGED = "EMR_CHANGED"
    BLOCKER_ESCALATED = "BLOCKER_ESCALATED"
    BLOCKER_RESOLVED = "BLOCKER_RESOLVED"
    CONTACT_STALE = "CONTACT_STALE"
    STEEL_PRICE_ALERT = "STEEL_PRICE_ALERT"
    PRODUCTION_LOGGED = "PRODUCTION_LOGGED"
    API_INTEGRATED = "API_INTEGRATED"
    SYSTEM_BOOT = "SYSTEM_BOOT"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"


# ═══ QUERIES ════════════════════════════════════════════════════════

def recent(limit: int = 50, event_type: str = None) -> list:
    """Get recent events from memory."""
    with _lock:
        events = list(_event_history)
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    return events[-limit:]


def count_by_type(hours: int = 24) -> dict:
    """Count events by type in the last N hours."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()  # vj: duration-math
    counts = defaultdict(int)
    with _lock:
        for e in _event_history:
            if e["ts"] > cutoff:
                counts[e["type"]] += 1
    return dict(counts)


def get_subscribers() -> dict:
    """List all registered subscribers."""
    with _lock:
        return {
            event_type: [cb.__name__ for cb in callbacks]
            for event_type, callbacks in _subscribers.items()
            if callbacks
        }


def stats() -> dict:
    return {
        "events_in_memory": len(_event_history),
        "subscriber_count": sum(len(v) for v in _subscribers.values()),
        "event_types_with_subscribers": len([k for k, v in _subscribers.items() if v]),
    }
