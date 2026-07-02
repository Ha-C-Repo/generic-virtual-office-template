#!/usr/bin/env python3
"""
validate-bid-output.py

Hard-rules validator for Your Company bid outputs. Runs before any PDF
export. Exits 0 on pass, nonzero on fail. Each failure prints the
offending file, line, and rule violated.

Rules enforced (from constitution delta and CLAUDE.md):
  R1  No supplier names in client proposal (Vulcraft, Canam, Nucor, Ayamsa).
  R2  No precedent project names in client proposal.
  R3  No engineering shown as its own line item.
  R4  Deck supply AND deck install present in Inclusions.
  R5  Two-PDF pair complete: <bid>.pdf and <bid>-GP.pdf.
  R6  No em-dash characters anywhere in output.
  R7  No three-adjective sequences, "Great question", or filler openers.
  R8  [FORBIDDEN PROJECT] never referenced.

Usage:
  python validate-bid-output.py --bid-dir <path>

Exit codes:
  0   all rules pass
  1   one or more rules failed
  2   bad arguments or missing files
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------- Rule data ----------

SUPPLIER_NAMES = [
    "Vulcraft", "Canam", "Nucor", "Ayamsa",
]

# Precedent projects that may appear only on capability statements, never on bids.
PRECEDENT_PROJECTS = [
    "ICD Church",
    "Elite Crossing",
    "Topgolf New Braunfels",
    "Carvana",
]

# Never anywhere
FORBIDDEN_PROJECTS = [
    "[FORBIDDEN PROJECT]",
]

# Filler openers and bad constructions
FILLER_PATTERNS = [
    r"\bGreat question\b",
    r"\bIt's not just\b.+?\bit's\b",
    r"\bleverage\b",
    r"\bsynergy\b",
    r"\bseamless\w*\b",
]

THREE_ADJ_PATTERN = re.compile(
    r"\b([A-Za-z]+ly|[A-Za-z]+(?:ous|ive|ent|ant|ful|ic|al|ed|ing)),\s+"
    r"([A-Za-z]+ly|[A-Za-z]+(?:ous|ive|ent|ant|ful|ic|al|ed|ing)),\s+"
    r"and\s+([A-Za-z]+ly|[A-Za-z]+(?:ous|ive|ent|ant|ful|ic|al|ed|ing))\b",
    re.IGNORECASE,
)

EM_DASH = "—"

REQUIRED_INCLUSIONS_KEYWORDS = [
    ("deck supply", "Inclusion missing: deck supply"),
    ("deck install", "Inclusion missing: deck installation"),
]


# ---------- Helpers ----------

def fail(violations, rule, file, detail):
    violations.append({"rule": rule, "file": str(file), "detail": detail})


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ""


def check_supplier_names(text, file, violations):
    for name in SUPPLIER_NAMES:
        if re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
            fail(violations, "R1", file, f"Supplier name '{name}' present.")


def check_precedent_projects(text, file, violations):
    for proj in PRECEDENT_PROJECTS:
        if re.search(r"\b" + re.escape(proj) + r"\b", text, re.IGNORECASE):
            fail(violations, "R2", file, f"Precedent project '{proj}' present on bid.")


def check_engineering_line_item(text, file, violations):
    # Heuristic: a price line that has "engineering" plus a dollar sign or LF/HR.
    bad = re.findall(
        r"^.*\bengineering\b.*[$\d].*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    # Filter out the standard fold-in language.
    bad = [b for b in bad if "folded" not in b.lower() and "included in" not in b.lower()]
    if bad:
        fail(violations, "R3", file, f"Engineering appears as a priced line: '{bad[0].strip()[:120]}'")


def check_inclusions(text, file, violations):
    low = text.lower()
    for kw, msg in REQUIRED_INCLUSIONS_KEYWORDS:
        if kw not in low:
            fail(violations, "R4", file, msg)


def check_em_dash(text, file, violations):
    if EM_DASH in text:
        n = text.count(EM_DASH)
        fail(violations, "R6", file, f"Em-dash present ({n} occurrence(s)).")


def check_filler(text, file, violations):
    for pat in FILLER_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            fail(violations, "R7", file, f"Filler/bad construction matched: {pat}")
    m = THREE_ADJ_PATTERN.search(text)
    if m:
        fail(violations, "R7", file, f"Three-adjective sequence: '{m.group(0)}'")


def check_forbidden_projects(text, file, violations):
    for proj in FORBIDDEN_PROJECTS:
        if re.search(r"\b" + re.escape(proj) + r"\b", text, re.IGNORECASE):
            fail(violations, "R8", file, f"Forbidden project '{proj}' referenced.")


def check_two_pdf_pair(bid_dir: Path, violations):
    pdfs = list(bid_dir.glob("*.pdf"))
    client = [p for p in pdfs if not p.stem.endswith("-GP")]
    gp = [p for p in pdfs if p.stem.endswith("-GP")]
    if not client:
        fail(violations, "R5", bid_dir, "Client proposal PDF missing (<bid>.pdf).")
    if not gp:
        fail(violations, "R5", bid_dir, "GP report PDF missing (<bid>-GP.pdf).")
    # Pairing check
    client_stems = {p.stem for p in client}
    gp_stems_unpaired = [p for p in gp if p.stem[:-3] not in client_stems]
    for p in gp_stems_unpaired:
        fail(violations, "R5", p, "GP report has no matching client proposal.")


# ---------- Driver ----------

def validate_bid_dir(bid_dir: Path):
    violations = []

    # Client proposal text (HTML or rendered text). Validator runs on the
    # source HTML before PDF export.
    client_html = list(bid_dir.glob("*client-proposal*.html")) + \
                  list(bid_dir.glob("client_proposal*.html"))
    gp_html = list(bid_dir.glob("*gp-report*.html")) + \
              list(bid_dir.glob("gp_report*.html"))

    for f in client_html:
        text = read_text(f)
        check_supplier_names(text, f, violations)
        check_precedent_projects(text, f, violations)
        check_engineering_line_item(text, f, violations)
        check_inclusions(text, f, violations)
        check_em_dash(text, f, violations)
        check_filler(text, f, violations)
        check_forbidden_projects(text, f, violations)

    for f in gp_html:
        text = read_text(f)
        # GP report can reference suppliers internally; still no em-dash, no filler.
        check_em_dash(text, f, violations)
        check_filler(text, f, violations)
        check_forbidden_projects(text, f, violations)

    # Check inclusions/exclusions JSON if present
    iej = bid_dir / "inclusions-exclusions.json"
    if iej.exists():
        try:
            data = json.loads(read_text(iej))
            incl_text = " ".join(i.get("text", "") for i in data.get("inclusions", []))
            check_inclusions(incl_text, iej, violations)
            check_supplier_names(incl_text, iej, violations)
        except Exception as e:
            fail(violations, "PARSE", iej, f"Could not parse JSON: {e}")

    # Two-PDF pair check
    check_two_pdf_pair(bid_dir, violations)

    return violations


def main():
    ap = argparse.ArgumentParser(description="Your Company bid output validator")
    ap.add_argument("--bid-dir", required=True, help="Path to the bid project folder")
    args = ap.parse_args()

    bid_dir = Path(args.bid_dir)
    if not bid_dir.is_dir():
        print(f"ERROR: not a directory: {bid_dir}", file=sys.stderr)
        return 2

    violations = validate_bid_dir(bid_dir)

    if not violations:
        print(f"PASS: {bid_dir} clean. All rules satisfied.")
        return 0

    print(f"FAIL: {bid_dir} has {len(violations)} violation(s).")
    for v in violations:
        print(f"  [{v['rule']}] {v['file']}: {v['detail']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
