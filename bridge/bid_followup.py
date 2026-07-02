"""
Your Company Virtual Office - Bid Follow-Up Automator
====================================================
After a bid is submitted, auto-generates follow-up email drafts
at day 3, 7, and 14 in the Owner's voice.

Why this beats Sketchdeck: generic services end at delivery.
This continues the relationship. Every follow-up references the
specific project, tonnage, and timeline from the original bid.

Usage:
    from bridge.bid_followup import generate_followup_sequence
    emails = generate_followup_sequence(
        project_name="Hillwood Warehouse",
        gc_name="James Holder",
        gc_company="Holder Construction",
        bid_total=425000,
        tonnage=85.3,
        bid_date="2026-05-09",
    )
"""

from datetime import datetime, timedelta
from typing import Optional

from bridge._date_utils import parse_bid_date


def generate_followup_sequence(
    project_name: str,
    gc_name: str,
    gc_company: str = "",
    bid_total: float = 0,
    tonnage: float = 0,
    bid_date: str = "",
    bid_number: str = "",
    deck_included: bool = True,
    special_notes: str = "",
) -> dict:
    """Generate a 3-email follow-up sequence for a submitted bid.

    Returns:
      {
        emails: [
          {day: 3, subject, body, send_date},
          {day: 7, subject, body, send_date},
          {day: 14, subject, body, send_date},
        ],
        reminders: [...]
      }
    """
    # Parse bid date. Accepts ISO date OR ISO datetime; surfaces parse
    # failure in the result dict instead of silently resetting to today.
    base, bid_date_parse_failed = parse_bid_date(bid_date)

    first_name = gc_name.split()[0] if gc_name else "team"
    company_short = gc_company.split()[0] if gc_company else ""
    tonnage_str = f"{tonnage:.0f}-ton" if tonnage > 0 else ""

    emails = []

    # ── Day 3: Light touch ────────────────────────────────────────────
    day3_date = base + timedelta(days=3)
    day3_body = (
        f"{first_name},\n\n"
        f"Following up on the {project_name} structural steel proposal"
    )
    if bid_number:
        day3_body += f" ({bid_number})"
    day3_body += " we submitted on "
    day3_body += f"{base.strftime('%A, %B %d')}."
    day3_body += (
        "\n\n"
        "Let me know if you have any questions on scope or pricing. "
        "Happy to jump on a call to walk through the package."
        "\n\n"
        "Owner Steel\n"
        "Your Company\n"
        "[COMPANY PHONE]"
    )

    emails.append({
        "day": 3,
        "send_date": day3_date.strftime("%Y-%m-%d"),
        "subject": f"Following up: {project_name} structural steel",
        "body": day3_body,
        "tone": "light_touch",
    })

    # ── Day 7: Value add ──────────────────────────────────────────────
    day7_date = base + timedelta(days=7)
    day7_body = (
        f"{first_name},\n\n"
        f"Wanted to circle back on {project_name}. "
    )
    if tonnage > 0:
        day7_body += (
            f"Our {tonnage_str} package includes full fabrication, "
            "erection, and shop drawings with a 10-day turnaround "
            "from our overseas AISC engineering teams. "
        )
    if deck_included:
        day7_body += "Deck supply and install is included in our number. "

    day7_body += (
        "\n\n"
        "If you're comparing proposals, I'm happy to do a scope-to-scope "
        "review to make sure we're apples to apples."
        "\n\n"
        "Owner Steel\n"
        "Your Company\n"
        "[COMPANY PHONE]"
    )

    emails.append({
        "day": 7,
        "send_date": day7_date.strftime("%Y-%m-%d"),
        "subject": f"Re: {project_name} - scope review offer",
        "body": day7_body,
        "tone": "value_add",
    })

    # ── Day 14: Decision check ────────────────────────────────────────
    day14_date = base + timedelta(days=14)
    day14_body = (
        f"{first_name},\n\n"
        f"Checking in on {project_name}. Our proposal is valid for 30 days "
        f"from submission ({base.strftime('%B %d')}). "
    )
    day14_body += (
        "If the timeline has shifted or the scope has changed, "
        "we're happy to revise."
        "\n\n"
        "Either way, appreciate the opportunity to bid."
        "\n\n"
        "Owner Steel\n"
        "Your Company\n"
        "[COMPANY PHONE]"
    )

    emails.append({
        "day": 14,
        "send_date": day14_date.strftime("%Y-%m-%d"),
        "subject": f"Re: {project_name} - timeline check",
        "body": day14_body,
        "tone": "decision_check",
    })

    # Build reminder schedule
    reminders = [
        {
            "date": e["send_date"],
            "action": f"Send Day {e['day']} follow-up to {gc_name} ({gc_company})",
            "subject": e["subject"],
        }
        for e in emails
    ]

    result = {
        "project": project_name,
        "gc_name": gc_name,
        "gc_company": gc_company,
        "bid_date": base.strftime("%Y-%m-%d"),
        "bid_number": bid_number,
        "emails": emails,
        "reminders": reminders,
    }
    if bid_date_parse_failed:
        # Surface the parse failure so the caller knows the schedule was
        # built off a default date, not the requested one. Without this
        # flag, a bid sent 20 days ago with an ISO datetime input would
        # silently schedule its day-3 follow-up for 3 days from now.
        result["bid_date_parse_failed"] = True
        result["warning"] = (
            f"WARNING: bid_date '{bid_date}' could not be parsed. "
            f"Follow-up schedule defaulted to today; verify dates before sending."
        )
    return result


def get_followup_for_day(sequence: dict, day: int) -> Optional[dict]:
    """Get the follow-up email for a specific day from a sequence."""
    for email in sequence.get("emails", []):
        if email["day"] == day:
            return email
    return None
