"""Shared date-parse utilities. Accepts ISO date OR ISO datetime;
surfaces parse failures rather than silently masking them.

Extracted in v3.5.6 to DRY the pattern that v3.5.5 applied in
``bridge/bid_rates.py::check_material_volatility``. Same bug class
existed in ``bridge/bid_followup.py``: a bare ``except ValueError`` that
swallowed parse failures and silently reset to ``datetime.now()``.
"""

from datetime import datetime


def parse_bid_date(s):
    """Parse a bid date string. Returns ``(parsed_datetime, parse_failed_flag)``.

    Accepts:
      * ISO date (``YYYY-MM-DD``)
      * ISO datetime (``YYYY-MM-DDTHH:MM:SS[.ffffff]`` - what
        ``datetime.utcnow().isoformat()`` produces)

    On parse failure, returns ``(datetime.now(), True)`` so callers can
    surface the failure to the user instead of silently treating a bad
    input as "today".

    An empty/None input is *not* a parse failure - returns
    ``(datetime.now(), False)``. Absence of a date is a different signal
    from a malformed date.

    Tz convention (pass 10g audit): all returned datetimes are tz-naive
    local time. Callers must not subtract these from tz-aware datetimes.
    If the input ISO string includes a tz suffix (e.g. ``Z`` or ``+00:00``)
    ``datetime.fromisoformat`` returns a tz-aware result; the parse
    succeeds and the caller receives a tz-aware datetime in that case.
    This is the only path that produces a non-naive output from this
    function and is acceptable because the Owner's bid date strings do not
    carry tz suffixes in practice.
    """
    if not s:
        return datetime.now(), False  # vj: local-time-ok
    for parser in (
        lambda x: datetime.strptime(x, "%Y-%m-%d"),
        datetime.fromisoformat,
    ):
        try:
            return parser(s), False
        except (ValueError, TypeError):
            continue
    return datetime.now(), True  # vj: local-time-ok
