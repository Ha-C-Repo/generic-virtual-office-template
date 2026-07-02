"""Locked tests for whatsapp_parser.py. Run: python3 test_parser.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from whatsapp_parser import parse_export, dedupe

FIX = Path(__file__).parent / "fixtures"
FAILS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name} {detail}")
    if not cond:
        FAILS.append(name)


print("12h iOS export:")
r12 = parse_export(FIX / "export_12h_ios.txt", chat_name="Genius Kids Crew")
check("message count = 8", len(r12) == 8, f"(got {len(r12)})")
check("first timestamp parsed", r12[0]["timestamp"] == "2026-06-08T06:58:11")
check("PM time parsed", r12[2]["timestamp"] == "2026-06-08T12:40:55")
check("media flagged", r12[2]["media_link"] == "MEDIA_OMITTED")
check("multiline joined (3 lines)", r12[4]["body"].count("\n") == 2,
      f"(got {r12[4]['body'].count(chr(10))} newlines)")
check("multiline content kept", "All hands signed." in r12[4]["body"])
check("sender clean", r12[4]["sender"] == "Paul Guerrero")
check("chat name set", all(x["chat_name_or_user"] == "Genius Kids Crew" for x in r12))
check("source = export", all(x["source"] == "export" for x in r12))
check("all msg_ids unique", len({x["msg_id"] for x in r12}) == 8)

print("24h Android export:")
r24 = parse_export(FIX / "export_24h_android.txt")
check("message count = 5", len(r24) == 5, f"(got {len(r24)})")
check("24h timestamp parsed", r24[0]["timestamp"] == "2026-06-09T13:15:00")
check("image omitted flagged", r24[1]["media_link"] == "MEDIA_OMITTED")
check("multiline joined", "NCCER card copied." in r24[3]["body"])

print("dedupe:")
again = parse_export(FIX / "export_12h_ios.txt", chat_name="Genius Kids Crew")
existing = {x["msg_id"] for x in r12}
check("re-import yields zero new rows", len(dedupe(again, existing)) == 0)
check("fresh rows pass through", len(dedupe(r24, existing)) == 5)

print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILED: {FAILS}")
    sys.exit(1)
print(f"RESULT: ALL {16} TESTS PASS")
