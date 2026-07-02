"""
WhatsApp .txt chat export parser for the Your Company Site Diary.

Handles both export timestamp formats:
  12h:  [6/9/26, 7:14:02 AM] Mario Gutierrez: message
  12h:  6/9/26, 7:14 AM - Mario Gutierrez: message
  24h:  [09/06/2026, 07:14:02] Mario Gutierrez: message
  24h:  09/06/2026, 07:14 - Mario Gutierrez: message

Handles multiline messages (continuation lines without a timestamp) and
media markers ("<Media omitted>", "image omitted", "audio omitted").

Output rows match the RAW_MESSAGES schema:
  msg_id, timestamp, source, chat_name_or_user, sender, body,
  media_link, processed
msg_id is a stable sha1 of (timestamp, sender, body) so re-imports of
the same export never create duplicates.

Sandbox tool. No network, no Sheets access. Reads a .txt, emits CSV or
a list of dicts for the Apps Script / Cowork pipeline to append.
"""

import csv
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

# [6/9/26, 7:14:02 AM] Sender: body      (bracket style, iOS)
_RE_BRACKET = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*"
    r"(?P<sender>[^:]+):\s?(?P<body>.*)$", re.IGNORECASE)

# 6/9/26, 7:14 AM - Sender: body         (dash style, Android)
_RE_DASH = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*"
    r"(?P<sender>[^:]+):\s?(?P<body>.*)$", re.IGNORECASE)

_MEDIA_MARKERS = ("<media omitted>", "image omitted", "video omitted",
                  "audio omitted", "document omitted", "sticker omitted",
                  "<attached:")

_DATE_FORMATS = ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y", "%d/%m/%y")
_TIME_FORMATS = ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M")


def _parse_ts(date_s: str, time_s: str) -> str:
    """Return ISO timestamp.

    12h time (AM/PM) implies a US export: month-first dates.
    24h time implies a non-US export: day-first dates tried first.
    """
    date_s, time_s = date_s.strip(), time_s.strip().upper()
    date_formats = _DATE_FORMATS
    if "M" not in time_s:   # no AM/PM marker: 24h export, day-first
        date_formats = ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%y", "%m/%d/%Y")
    for df in date_formats:
        for tf in _TIME_FORMATS:
            try:
                dt = datetime.strptime(f"{date_s} {time_s}", f"{df} {tf}")
                return dt.isoformat()
            except ValueError:
                continue
    return f"UNPARSED {date_s} {time_s}"


def _msg_id(ts: str, sender: str, body: str) -> str:
    h = hashlib.sha1(f"{ts}|{sender}|{body}".encode("utf-8")).hexdigest()
    return f"exp-{h[:16]}"


def _is_media(body: str) -> bool:
    b = body.strip().lower()
    return any(m in b for m in _MEDIA_MARKERS)


def parse_export(path, chat_name: str = "") -> list:
    """Parse a WhatsApp .txt export into RAW_MESSAGES rows."""
    path = Path(path)
    chat = chat_name or path.stem
    rows = []
    current = None

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.rstrip("\n").replace("‎", "")  # strip LRM
        m = _RE_BRACKET.match(line) or _RE_DASH.match(line)
        if m:
            if current:
                rows.append(current)
            ts = _parse_ts(m.group("date"), m.group("time"))
            sender = m.group("sender").strip()
            body = m.group("body").strip()
            current = {
                "msg_id": "",          # filled at flush, body may grow
                "timestamp": ts,
                "source": "export",
                "chat_name_or_user": chat,
                "sender": sender,
                "body": body,
                "media_link": "MEDIA_OMITTED" if _is_media(body) else "",
                "processed": "FALSE",
            }
        elif current is not None and line.strip():
            current["body"] += "\n" + line.strip()      # multiline continuation
        # blank lines between messages are ignored

    if current:
        rows.append(current)

    for r in rows:
        r["msg_id"] = _msg_id(r["timestamp"], r["sender"], r["body"])
        if _is_media(r["body"]) and not r["media_link"]:
            r["media_link"] = "MEDIA_OMITTED"
    return rows


def dedupe(rows: list, existing_ids: set) -> list:
    """Drop rows whose msg_id is already in RAW_MESSAGES."""
    return [r for r in rows if r["msg_id"] not in existing_ids]


def to_csv(rows: list, out_path) -> None:
    cols = ["msg_id", "timestamp", "source", "chat_name_or_user",
            "sender", "body", "media_link", "processed"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: py whatsapp_parser.py <export.txt> [out.csv]")
        sys.exit(1)
    rows = parse_export(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else "raw_messages_out.csv"
    to_csv(rows, out)
    print(f"{len(rows)} messages -> {out}")
