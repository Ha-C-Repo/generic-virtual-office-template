"""bridge/tekla.py - Tekla Structures integration scaffolding.

Saturday-3: minimal but real scaffold for Tekla model exports.

Your Company does detailing in Tekla. The realistic interface is the
member-list CSV export (File > Export > CSV from the Tekla model browser).
This module:

  1. Parses that CSV into a normalized member list
  2. Computes total tonnage
  3. Compares Tekla tonnage to a bid pipeline record
  4. Surfaces discrepancies for Owner to review

Future work (out of scope this pass):
  - IFC import for full geometry
  - Two-way sync to push markups back into Tekla
  - Connection takeoff from Tekla bolt list

Voice: zero em-dashes. Hyphens or periods only.
"""

import csv
import re
from pathlib import Path
from typing import Iterable

# Common Tekla CSV column header variants. Tekla exports use different
# headers depending on template. Normalize on read.
_COLUMN_ALIASES = {
    "profile": ("profile", "section", "section size", "shape", "size"),
    "length": ("length", "length [mm]", "length_mm", "length [ft]", "length_in", "len"),
    "weight": ("weight", "weight [kg]", "weight_kg", "weight [lb]", "weight_lb",
               "unit weight", "weight per piece"),
    "quantity": ("quantity", "qty", "count", "no", "num"),
    "assembly": ("assembly", "assembly mark", "assembly position", "mark"),
    "part_mark": ("part mark", "part", "part position", "piece mark"),
    "grade": ("material", "grade", "steel grade"),
    "phase": ("phase", "lot", "sequence"),
}


def _normalize_header(h: str) -> str:
    """Map a Tekla header variant to a canonical field name."""
    h_low = h.strip().lower()
    for canonical, aliases in _COLUMN_ALIASES.items():
        if h_low in aliases:
            return canonical
    return h_low.replace(" ", "_")


def _parse_length_to_ft(raw: str) -> float:
    """Convert a length string from any Tekla unit to feet.

    Handles "12'-6"", "12.5 ft", "3810 mm", "150 in", or bare numbers.
    Bare numbers assumed inches (Tekla default for US export).
    """
    if not raw:
        return 0.0
    s = str(raw).strip().lower()
    if not s:
        return 0.0

    # 12'-6" format
    m = re.match(r"(\d+)\s*'\s*-?\s*(\d+(?:\.\d+)?)\s*\"?", s)
    if m:
        return float(m.group(1)) + float(m.group(2)) / 12.0

    # Number with explicit unit
    m = re.match(r"([\d.]+)\s*(mm|cm|m|in|ft)?$", s)
    if m:
        val = float(m.group(1))
        unit = m.group(2) or "in"  # default inches per Tekla US
        if unit == "mm": return val / 304.8
        if unit == "cm": return val / 30.48
        if unit == "m":  return val * 3.28084
        if unit == "in": return val / 12.0
        if unit == "ft": return val

    # Bare number: assume inches
    try:
        return float(s) / 12.0
    except ValueError:
        return 0.0


def _parse_weight_to_lb(raw: str) -> float:
    """Convert a weight string to pounds. Empty or 0 returns 0.0."""
    if not raw:
        return 0.0
    s = str(raw).strip().lower()
    m = re.match(r"([\d.]+)\s*(kg|lb|lbs)?$", s)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2) or "lb"
    if unit == "kg": return val * 2.20462
    return val


def parse_tekla_csv(path) -> list[dict]:
    """Read a Tekla member-list CSV and return a list of normalized members.

    Returns: list of dicts with keys: profile, length_ft, weight_lb,
    quantity, assembly, part_mark, grade, phase, total_lb (computed).

    Rows missing both profile AND weight are skipped (header noise).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Tekla CSV not found: {path}")

    members = []
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        # Sniff delimiter (Tekla uses comma OR semicolon depending on locale)
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            return []
        header_map = {h: _normalize_header(h) for h in reader.fieldnames}

        for raw_row in reader:
            row = {header_map[k]: v for k, v in raw_row.items() if k}
            profile = (row.get("profile") or "").strip()
            weight_raw = row.get("weight") or ""
            if not profile and not weight_raw:
                continue

            qty = 1
            try:
                qty = max(int(float(row.get("quantity") or 1)), 1)
            except (TypeError, ValueError):
                pass

            length_ft = _parse_length_to_ft(row.get("length") or "")
            weight_lb = _parse_weight_to_lb(weight_raw)
            members.append({
                "profile": profile.upper(),
                "length_ft": round(length_ft, 3),
                "weight_lb": round(weight_lb, 2),
                "quantity": qty,
                "assembly": (row.get("assembly") or "").strip(),
                "part_mark": (row.get("part_mark") or "").strip(),
                "grade": (row.get("grade") or "").strip(),
                "phase": (row.get("phase") or "").strip(),
                "total_lb": round(weight_lb * qty, 2),
            })
    return members


def tekla_summary(members: Iterable[dict]) -> dict:
    """Aggregate a parsed member list into a summary."""
    members = list(members)
    if not members:
        return {
            "member_count": 0, "total_pieces": 0,
            "total_lb": 0.0, "total_tons": 0.0,
            "by_profile": {}, "by_phase": {},
        }

    total_lb = sum(m["total_lb"] for m in members)
    by_profile: dict[str, dict] = {}
    by_phase: dict[str, dict] = {}

    for m in members:
        p = m["profile"] or "(unknown)"
        bp = by_profile.setdefault(p, {"pieces": 0, "lb": 0.0})
        bp["pieces"] += m["quantity"]
        bp["lb"] += m["total_lb"]

        ph = m["phase"] or "(no phase)"
        bph = by_phase.setdefault(ph, {"pieces": 0, "lb": 0.0})
        bph["pieces"] += m["quantity"]
        bph["lb"] += m["total_lb"]

    # Round for readability
    for d in (by_profile, by_phase):
        for k in d:
            d[k]["lb"] = round(d[k]["lb"], 2)
            d[k]["tons"] = round(d[k]["lb"] / 2000.0, 3)

    return {
        "member_count": len(members),
        "total_pieces": sum(m["quantity"] for m in members),
        "total_lb": round(total_lb, 2),
        "total_tons": round(total_lb / 2000.0, 3),
        "by_profile": by_profile,
        "by_phase": by_phase,
    }


def compare_to_bid(tekla_summary_data: dict, bid_estimated_tons: float,
                   tolerance_pct: float = 5.0) -> dict:
    """Compare Tekla model tonnage to an estimated bid tonnage.

    Returns a verdict: MATCH, UNDER, OVER, or INVALID.
    All return branches list the same 7 keys explicitly so static
    analysis confirms shape parity (VJ-MUST-FIX-03).
    """
    if bid_estimated_tons <= 0:
        return {
            "verdict": "INVALID",
            "tekla_tons": 0.0,
            "bid_tons": round(bid_estimated_tons, 3),
            "delta_tons": 0.0,
            "delta_pct": 0.0,
            "tolerance_pct": tolerance_pct,
            "note": "bid_estimated_tons must be > 0. Pass the estimated tons from the bid.",
        }

    tekla_tons = tekla_summary_data.get("total_tons", 0.0)
    delta_tons = tekla_tons - bid_estimated_tons
    delta_pct = (delta_tons / bid_estimated_tons) * 100.0

    if abs(delta_pct) <= tolerance_pct:
        verdict = "MATCH"
        note = f"Within {tolerance_pct}% tolerance."
    elif delta_tons < 0:
        verdict = "UNDER"
        note = (f"Tekla model is {abs(delta_tons):.2f} tons ({abs(delta_pct):.1f}%) "
                f"LIGHTER than bid. Either bid was over-estimated or detail "
                f"items are missing from the Tekla model. Review with Ivan.")
    else:
        verdict = "OVER"
        note = (f"Tekla model is {delta_tons:.2f} tons ({delta_pct:.1f}%) "
                f"HEAVIER than bid. Scope creep, missed items in bid takeoff, "
                f"or detail steel not previously priced. Flag for change order.")

    return {
        "verdict": verdict,
        "tekla_tons": tekla_tons,
        "bid_tons": round(bid_estimated_tons, 3),
        "delta_tons": round(delta_tons, 3),
        "delta_pct": round(delta_pct, 2),
        "tolerance_pct": tolerance_pct,
        "note": note,
    }


def import_and_compare(csv_path, bid_estimated_tons: float,
                       tolerance_pct: float = 5.0) -> dict:
    """One-shot: parse Tekla CSV, summarize, compare to bid. Returns combined report.

    Typical use:
        report = tekla.import_and_compare("ICD_Church_Tekla_export.csv", 105.0)
        if report["comparison"]["verdict"] != "MATCH":
            print(report["comparison"]["note"])
    """
    try:
        members = parse_tekla_csv(csv_path)
    except FileNotFoundError as e:
        return {"error": str(e), "members": [], "summary": {}, "comparison": {}}

    summary = tekla_summary(members)
    comparison = compare_to_bid(summary, bid_estimated_tons, tolerance_pct)
    return {
        "csv_path": str(csv_path),
        "members": members,
        "summary": summary,
        "comparison": comparison,
    }


def status() -> dict:
    """Module health check. Used by feature_status scanner."""
    return {
        "module": "bridge.tekla",
        "interface": "CSV import + tonnage comparison",
        "ready": True,
        "supports": ["Tekla member-list CSV export", "tonnage compare to bid"],
        "not_yet": ["IFC import", "two-way sync", "connection takeoff"],
    }
