#!/usr/bin/env python3
"""Deterministic pre-export checks for a Your Company client bid proposal.

Hard checks fail the export. The supplier-name and precedent-project checks
become deterministic when a local list is supplied, and stay MANUAL when it is
not. Those lists hold commercial data, so they live outside the repo (or as
*.local.txt, which .gitignore blocks). Point to them by flag, env var, or the
default local path.

Usage:
    python validate_bid_output.py CLIENT_PROPOSAL.md \
        [--gp GP_REPORT.md] [--suppliers PATH] [--precedents PATH]

Resolution order for each list: flag, then env var
(YOURCO_SUPPLIER_LIST / YOURCO_PRECEDENT_LIST), then the default local path
data/<name>.local.txt next to the governance skill. List format: one entry per
line, blank lines and # comments ignored, matching case-insensitive whole-word.

Exit code 0 only if no FAIL.
"""
import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
ROOT = HERE.parents[3]  # project root (…/.claude/skills/governance/scripts)
BRAND_TOKENS = ROOT / "brand" / "brand-tokens.json"


def load_brand_donts():
    """Banned/warn strings from the canonical brand token spec.

    brand/brand-tokens.json is the machine-readable half of the Tier 1
    brand rules (see brand/LOGO_RULES.md). Missing or unparsable file
    degrades to a MANUAL note, never a crash.
    """
    try:
        import json
        d = json.loads(BRAND_TOKENS.read_text(encoding="utf-8"))
        donts = d.get("donts", {})
        return (donts.get("banned_strings") or [],
                donts.get("warn_strings") or [],
                f"brand-tokens.json v{d.get('version', '?')}")
    except Exception as e:
        return None, None, f"brand-tokens.json unavailable ({e})"


def load_list(path):
    if not path:
        return None, "no list provided"
    p = Path(path)
    if not p.exists():
        return None, f"list not found at {p}"
    items = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.split("#", 1)[0].strip()
        if len(s) >= 3:
            items.append(s)
    return items, f"{len(items)} entries from {p.name}"


def found(names, text):
    return [n for n in names if re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", text, re.I)]


def resolve(flag, env, default_name):
    if flag:
        return flag
    if os.environ.get(env):
        return os.environ[env]
    cand = DATA / default_name
    return str(cand) if cand.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proposal")
    ap.add_argument("--gp", default=None, help="path to the matching -GP report")
    ap.add_argument("--suppliers", default=None, help="path to the supplier-name list")
    ap.add_argument("--precedents", default=None, help="path to the precedent-project list")
    args = ap.parse_args()

    text = Path(args.proposal).read_text(encoding="utf-8", errors="replace")
    low = text.lower()
    oks, fails, manual = [], [], []

    if chr(0x2014) in text:
        fails.append("em-dash present (voice rule)")

    banned, warn_strings, brand_note = load_brand_donts()
    warns = []
    if banned is None:
        manual.append(f"brand DON'Ts: check PEMB language and retired lines by hand ({brand_note})")
    else:
        hits = found(banned, text)
        if hits:
            fails.append("Tier 1 brand DON'T in client proposal: " + ", ".join(hits) + f" ({brand_note})")
        else:
            oks.append(f"brand DON'Ts check passed ({brand_note})")
        for w in found(warn_strings, text):
            warns.append(f"voice filler present: {w!r} (brand-voice.md kill list)")

    if re.search(r"(?im)^\s*[-*\d.)]*\s*engineering\b.*(\$|\d)", text):
        fails.append("engineering appears as its own priced line item (fold into fab and erection)")

    if "deck" not in low:
        fails.append("no mention of deck (deck supply and install must be in scope)")

    if args.gp:
        if not Path(args.gp).exists():
            fails.append(f"-GP report not found at {args.gp}")
    else:
        manual.append("confirm the matching -GP report exists (pass --gp to check)")

    sup, sup_note = load_list(resolve(args.suppliers, "YOURCO_SUPPLIER_LIST", "suppliers.local.txt"))
    if sup is None:
        manual.append(f"supplier names: confirm none appear ({sup_note}; pass --suppliers PATH to automate)")
    else:
        hits = found(sup, text)
        fails.append("supplier name(s) in client proposal: " + ", ".join(hits)) if hits else oks.append(f"supplier-name check passed ({sup_note})")

    prec, prec_note = load_list(resolve(args.precedents, "YOURCO_PRECEDENT_LIST", "precedents.local.txt"))
    if prec is None:
        manual.append(f"precedent projects: confirm none are referenced ({prec_note}; pass --precedents PATH to automate)")
    else:
        hits = found(prec, text)
        fails.append("precedent project(s) on a bid: " + ", ".join(hits) + " (capability statements only)") if hits else oks.append(f"precedent-project check passed ({prec_note})")

    manual.append("three-adjective lists and filler openers: confirm none (human review)")

    for o in oks:
        print(f"OK     {o}")
    for w in warns:
        print(f"WARN   {w}")
    for f in fails:
        print(f"FAIL   {f}")
    for m in manual:
        print(f"MANUAL {m}")

    if fails:
        print(f"\n{len(fails)} hard check(s) failed. Do not export.")
        sys.exit(1)
    print("\nNo hard check failed. Complete the MANUAL items before export.")


if __name__ == "__main__":
    main()
