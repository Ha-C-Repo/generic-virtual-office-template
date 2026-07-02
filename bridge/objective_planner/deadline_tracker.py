"""Deadline tracker (Phase 15 support module).

Calendar-aware deadline parsing and countdown. Converts natural language
dates ("by Friday," "end of next week," "March 15") into ISO dates and
tracks hours remaining. Warns when a deadline is tight.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)


# Business hours per day (for "hours remaining" calc)
HOURS_PER_DAY = 8


def parse_deadline(text: str, now: Optional[datetime] = None) -> dict:
    """Parse a natural-language deadline into an ISO date and metadata.

    Returns:
        {
            "deadline_iso": str (YYYY-MM-DD) or "",
            "deadline_display": str (human readable),
            "hours_remaining": float (business hours),
            "days_remaining": int (calendar days),
            "urgency": "CRITICAL"|"TIGHT"|"NORMAL"|"RELAXED",
            "parsed_from": str (original text fragment),
        }
    """
    if now is None:
        now = datetime.now(timezone.utc)

    text_lower = text.lower().strip()
    deadline: Optional[datetime] = None
    parsed_from = text_lower

    # Pattern: explicit date (YYYY-MM-DD or MM/DD/YYYY or Month DD)
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if iso_match:
        try:
            deadline = datetime.strptime(iso_match.group(1), "%Y-%m-%d")
            parsed_from = iso_match.group(1)
        except ValueError:
            pass

    if deadline is None:
        us_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if us_match:
            try:
                deadline = datetime(
                    int(us_match.group(3)),
                    int(us_match.group(1)),
                    int(us_match.group(2)),
                )
                parsed_from = us_match.group(0)
            except ValueError:
                pass

    # Pattern: "by Friday," "by Monday," etc.
    if deadline is None:
        day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        for name, dow in day_names.items():
            if name in text_lower:
                days_ahead = (dow - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # next occurrence
                deadline = now + timedelta(days=days_ahead)
                deadline = deadline.replace(hour=17, minute=0, second=0)
                parsed_from = name
                break

    # Pattern: "tomorrow," "today," "end of week," "next week"
    if deadline is None:
        if "tomorrow" in text_lower:
            deadline = now + timedelta(days=1)
            deadline = deadline.replace(hour=17, minute=0, second=0)
            parsed_from = "tomorrow"
        elif "today" in text_lower or "tonight" in text_lower:
            deadline = now.replace(hour=17, minute=0, second=0)
            parsed_from = "today"
        elif "end of week" in text_lower or "eow" in text_lower:
            days_to_friday = (4 - now.weekday()) % 7
            if days_to_friday == 0 and now.hour >= 17:
                days_to_friday = 7
            deadline = now + timedelta(days=days_to_friday)
            deadline = deadline.replace(hour=17, minute=0, second=0)
            parsed_from = "end of week"
        elif "next week" in text_lower:
            days_to_next_friday = (4 - now.weekday()) % 7 + 7
            deadline = now + timedelta(days=days_to_next_friday)
            deadline = deadline.replace(hour=17, minute=0, second=0)
            parsed_from = "next week"

    if deadline is None:
        return {
            "deadline_iso": "",
            "deadline_display": "no deadline detected",
            "hours_remaining": -1,
            "days_remaining": -1,
            "urgency": "NORMAL",
            "parsed_from": "",
        }

    # Set time to 5 PM if only date was parsed
    if deadline.hour == 0 and deadline.minute == 0:
        deadline = deadline.replace(hour=17)

    delta = deadline - now
    days_remaining = delta.days
    hours_remaining = max(0.0, days_remaining * HOURS_PER_DAY)

    if days_remaining <= 0:
        urgency = "CRITICAL"
    elif days_remaining <= 1:
        urgency = "TIGHT"
    elif days_remaining <= 3:
        urgency = "NORMAL"
    else:
        urgency = "RELAXED"

    return {
        "deadline_iso": deadline.strftime("%Y-%m-%d"),
        "deadline_display": deadline.strftime("%A %B %d, %Y at %I:%M %p"),
        "hours_remaining": round(hours_remaining, 1),
        "days_remaining": days_remaining,
        "urgency": urgency,
        "parsed_from": parsed_from,
    }
