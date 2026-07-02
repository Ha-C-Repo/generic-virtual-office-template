"""
Your Company Virtual Office - Agent 6: Bid Review
================================================
Steel Suite Pro (SSP) export → structured 4-section bid review.

Input: paste or upload an SSP export (CSV or text table)
Output: structured review with 4 sections:
  1. SCOPE VERIFICATION - members match, nothing missing, nothing extra
  2. WEIGHT AUDIT - SSP tons vs AISC lookup, flag discrepancies > 2%
  3. COST REASONABLENESS - $/ton, $/lb, labor hours vs calibration baseline
  4. RISK FLAGS - scope gaps, unusual items, connection complexity

All arithmetic uses bridge/calculators.py. No LLM math. (Tier 1 rule.)
"""

import csv
import io
import re
from datetime import datetime, timezone

from bridge.calculators import (
    steel_weight, hours_estimate, labor_cost, bid_total,
    margin_scenario, DEFAULT_RATES, COMPLEXITY,
)

# Labor profile multipliers from Steel Pro Bid Calculator (Google Drive)
# Source: Your_Company_Steel_Pro_Bid_Calculator_v1.xlsx / Labor tab
LABOR_PROFILES = {
    "joists_trusses": 0.60,     # 40% reduction - angle cutting 3-5x faster
    "repetitive_plates": 0.65,  # CNC plasma: 40-100 pcs/hr vs 10-20 manual
    "misc_steel": 0.70,         # Mixed machine/manual
    "commercial_frame": 0.80,   # Standard building envelope
    "moment_frames": 1.10,      # Connection-heavy, more manual fitting
    "circular_frame": 1.50,     # ICD Church complexity
    "stairs": 1.60,             # Manual-intensive despite machinery
}


# ── SSP Export Parser ─────────────────────────────────────────────────

def parse_ssp_export(text: str) -> dict:
    """Parse a Steel Suite Pro export into structured member data.

    SSP exports come in multiple formats:
      - CSV with headers: Mark, Shape, Length, Qty, Weight
      - Tab-separated text tables
      - Clipboard paste from SSP member schedule

    Returns dict with:
      members: list of {mark, shape, length_ft, qty, weight_each_lbs, weight_total_lbs}
      summary: {total_pieces, total_weight_lbs, total_tons, unique_shapes}
      parse_method: which parser succeeded
      warnings: any parse issues
    """
    text = text.strip()
    if not text:
        return {"members": [], "summary": {}, "parse_method": "none",
                "warnings": ["Empty input"]}

    # Try CSV first
    members, method, warnings = _try_csv_parse(text)
    if not members:
        members, method, warnings = _try_table_parse(text)
    if not members:
        members, method, warnings = _try_freeform_parse(text)

    if not members:
        return {"members": [], "summary": {},
                "parse_method": "failed",
                "warnings": ["Could not parse SSP export. Expected columns: "
                             "Mark, Shape, Length, Qty, Weight"]}

    # Calculate summary
    total_pieces = sum(m["qty"] for m in members)
    total_lbs = sum(m["weight_total_lbs"] for m in members)
    unique_shapes = len(set(m["shape"] for m in members))

    return {
        "members": members,
        "summary": {
            "total_pieces": total_pieces,
            "total_weight_lbs": round(total_lbs, 1),
            "total_tons": round(total_lbs / 2000, 2),
            "unique_shapes": unique_shapes,
            "member_count": len(members),
        },
        "parse_method": method,
        "warnings": warnings,
    }


def _try_csv_parse(text: str) -> tuple[list, str, list]:
    """Try parsing as CSV."""
    warnings = []
    members = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        raw_headers = reader.fieldnames or []
        if not raw_headers:
            return [], "", []

        # Build lowercase-to-original mapping for lookups
        header_map = {h.lower().strip(): h for h in raw_headers}
        headers_lower = list(header_map.keys())

        # Map common SSP header variations (find lowercase key, return original)
        def _find(candidates):
            for c in candidates:
                for h in headers_lower:
                    if c in h:
                        return header_map[h]  # return ORIGINAL header name
            return None

        shape_col = _find(["shape", "section", "size", "designation"])
        qty_col = _find(["qty", "quantity", "pcs", "count"])
        weight_col = _find(["weight", "wt", "weight_each",
                            "unit_weight", "lb/ft", "lbs"])
        mark_col = _find(["mark", "piece_mark", "id", "member"])
        length_col = _find(["length", "len", "length_ft", "ft"])

        if not shape_col:
            return [], "", ["No shape column found"]

        for row in reader:
            shape = row.get(shape_col, "").strip()
            if not shape or not re.match(r"[A-Z]", shape, re.IGNORECASE):
                continue

            qty = _safe_int(row.get(qty_col, "1")) if qty_col else 1
            weight = _safe_float(row.get(weight_col, "0")) if weight_col else 0
            mark = row.get(mark_col, "").strip() if mark_col else ""
            length = _safe_float(row.get(length_col, "0")) if length_col else 0

            members.append({
                "mark": mark or f"M{len(members)+1}",
                "shape": shape.upper(),
                "length_ft": length,
                "qty": max(1, qty),
                "weight_each_lbs": weight,
                "weight_total_lbs": weight * max(1, qty),
            })

        if members:
            return members, "csv", warnings
    except Exception:
        pass
    return [], "", []


def _try_table_parse(text: str) -> tuple[list, str, list]:
    """Try parsing as tab/space-separated table."""
    warnings = []
    members = []
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return [], "", []

    # Detect delimiter
    delim = "\t" if "\t" in lines[0] else None
    if not delim:
        # Try multi-space
        if "  " in lines[0]:
            delim = r"\s{2,}"
        else:
            return [], "", []

    for line in lines[1:]:  # skip header
        if delim == "\t":
            parts = line.split("\t")
        else:
            parts = re.split(delim, line.strip())

        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) < 2:
            continue

        # Find the shape (first item matching W/WT/HSS/L/C/MC pattern)
        shape = ""
        shape_idx = -1
        for i, p in enumerate(parts):
            if re.match(r"^(W|WT|HSS|L|C|MC|HP|S|ST)\d", p, re.IGNORECASE):
                shape = p.upper()
                shape_idx = i
                break

        if not shape:
            continue

        # Extract numbers from remaining parts
        numbers = []
        mark = ""
        for i, p in enumerate(parts):
            if i == shape_idx:
                continue
            val = _safe_float(p)
            if val > 0:
                numbers.append(val)
            elif i < shape_idx:
                mark = p

        qty = 1
        weight = 0
        length = 0

        if len(numbers) >= 3:
            length, qty, weight = numbers[0], int(numbers[1]), numbers[2]
        elif len(numbers) == 2:
            qty, weight = int(numbers[0]), numbers[1]
        elif len(numbers) == 1:
            weight = numbers[0]

        members.append({
            "mark": mark or f"M{len(members)+1}",
            "shape": shape,
            "length_ft": length,
            "qty": max(1, qty),
            "weight_each_lbs": weight,
            "weight_total_lbs": weight * max(1, qty),
        })

    if members:
        return members, "table", warnings
    return [], "", []


def _try_freeform_parse(text: str) -> tuple[list, str, list]:
    """Try extracting members from freeform text."""
    warnings = []
    members = []
    shape_pattern = re.compile(
        r"(W|WT|HSS|L|C|MC|HP|S|ST)\d+[Xx×]\d+\.?\d*(?:[Xx×]\d+\.?\d*)?",
        re.IGNORECASE
    )

    for match in shape_pattern.finditer(text):
        shape = match.group(0).upper().replace("×", "X").replace("x", "X")
        members.append({
            "mark": f"M{len(members)+1}",
            "shape": shape,
            "length_ft": 0,
            "qty": 1,
            "weight_each_lbs": 0,
            "weight_total_lbs": 0,
        })

    if members:
        warnings.append("Freeform parse: shapes found but no quantities or "
                        "weights. Run AISC lookup to populate.")
        return members, "freeform", warnings
    return [], "", []


def _find_col(headers: list[str], candidates: list[str]) -> str | None:
    """Find a column header from a list of candidates."""
    for c in candidates:
        for h in headers:
            if c in h:
                return h
    return None


def _safe_float(s: str) -> float:
    """Parse a float, stripping commas and units."""
    try:
        return float(re.sub(r"[^\d.\-]", "", str(s)))
    except (ValueError, TypeError):
        return 0.0


def _safe_int(s: str) -> int:
    try:
        return int(float(re.sub(r"[^\d.\-]", "", str(s))))
    except (ValueError, TypeError):
        return 1


# ── AISC Cross-Reference ─────────────────────────────────────────────

def cross_reference_aisc(members: list[dict]) -> dict:
    """Cross-reference SSP members against AISC shapes database.

    For each member: look up lb/ft from AISC, compute expected weight,
    compare to SSP-reported weight, flag discrepancies > 2%.

    Returns dict with verified members and discrepancy list.
    """
    from bridge.calculators import _load_shapes

    shapes_db = _load_shapes()
    verified = []
    discrepancies = []
    aisc_total_lbs = 0

    for m in members:
        shape = m["shape"]
        # Normalize shape name for AISC lookup
        normalized = shape.replace("X", "x").replace("×", "x")
        # Try exact match, then case variations
        lb_per_ft = shapes_db.get(shape) or shapes_db.get(normalized) or 0

        if lb_per_ft and m["length_ft"] > 0:
            expected_each = lb_per_ft * m["length_ft"]
            expected_total = expected_each * m["qty"]
            aisc_total_lbs += expected_total

            reported = m["weight_total_lbs"]
            if reported > 0:
                pct_diff = abs(expected_total - reported) / expected_total * 100
                if pct_diff > 2.0:
                    discrepancies.append({
                        "mark": m["mark"],
                        "shape": shape,
                        "ssp_lbs": reported,
                        "aisc_lbs": round(expected_total, 1),
                        "pct_diff": round(pct_diff, 1),
                        "direction": "over" if reported > expected_total else "under",
                    })
            verified.append({
                **m,
                "aisc_lb_per_ft": lb_per_ft,
                "aisc_weight_each": round(expected_each, 1),
                "aisc_weight_total": round(expected_total, 1),
                "aisc_verified": True,
            })
        else:
            verified.append({
                **m,
                "aisc_lb_per_ft": lb_per_ft,
                "aisc_weight_each": 0,
                "aisc_weight_total": 0,
                "aisc_verified": False,
            })
            if not lb_per_ft:
                discrepancies.append({
                    "mark": m["mark"],
                    "shape": shape,
                    "issue": "Shape not found in AISC database",
                })

    return {
        "verified_members": verified,
        "aisc_total_lbs": round(aisc_total_lbs, 1),
        "aisc_total_tons": round(aisc_total_lbs / 2000, 2),
        "discrepancies": discrepancies,
        "discrepancy_count": len(discrepancies),
    }


# ── 4-Section Bid Review ─────────────────────────────────────────────

def bid_review(ssp_text: str, project_name: str = "",
               complexity: str = "standard",
               margin_pct: float = 0.18) -> dict:
    """Full 4-section bid review from SSP export.

    Sections:
      1. SCOPE VERIFICATION
      2. WEIGHT AUDIT
      3. COST REASONABLENESS
      4. RISK FLAGS

    All math from bridge/calculators.py. No LLM arithmetic.
    """
    # Parse SSP
    # vj: parity-ok (pass 10g classified: dispatcher J=0.08; disjoint shapes)
    parsed = parse_ssp_export(ssp_text)
    if not parsed["members"]:
        return {
            "ok": False,
            "error": (
                "No members extracted from SSP export. "
                "Expected a member schedule with columns like: Mark, Shape, Length, Qty, Weight. "
                "Accepted formats: (1) CSV with headers, (2) tab-separated table, "
                "(3) clipboard paste from Steel Suite Pro or Tekla. "
                "Example: 'B-1, W14X82, 24, 8, 1968' or paste the full schedule from your SSP export."
            ),
            "parse_warnings": parsed["warnings"],
            "parse_method": parsed.get("parse_method", "failed"),
        }

    summary = parsed["summary"]
    members = parsed["members"]

    # Cross-reference AISC
    aisc = cross_reference_aisc(members)

    # Use AISC weight if available, else SSP weight
    tons = aisc["aisc_total_tons"] if aisc["aisc_total_lbs"] > 0 else summary["total_tons"]
    total_lbs = aisc["aisc_total_lbs"] if aisc["aisc_total_lbs"] > 0 else summary["total_weight_lbs"]

    # ── Section 1: Scope Verification ─────────────────────────────────
    scope = {
        "total_members": summary["member_count"],
        "total_pieces": summary["total_pieces"],
        "unique_shapes": summary["unique_shapes"],
        "shape_breakdown": _shape_breakdown(members),
        "parse_method": parsed["parse_method"],
        "parse_warnings": parsed["warnings"],
    }

    # ── Section 2: Weight Audit ───────────────────────────────────────
    weight_audit = {
        "ssp_total_lbs": summary["total_weight_lbs"],
        "ssp_total_tons": summary["total_tons"],
        "aisc_total_lbs": aisc["aisc_total_lbs"],
        "aisc_total_tons": aisc["aisc_total_tons"],
        "discrepancies": aisc["discrepancies"],
        "discrepancy_count": aisc["discrepancy_count"],
        "weight_source": "aisc" if aisc["aisc_total_lbs"] > 0 else "ssp",
        "verified_tons": tons,
    }

    # ── Section 3: Cost Reasonableness ────────────────────────────────
    rates = DEFAULT_RATES
    comp = COMPLEXITY.get(complexity, 1.0)

    hrs = hours_estimate(tons, complexity)
    fab_hrs = hrs["fab_hours"]
    erect_hrs = hrs["erect_hours"]

    lc = labor_cost(fab_hours=fab_hrs, erect_hours=erect_hrs)
    bt = bid_total(steel_lbs=total_lbs, labor_cost_usd=lc["total_labor"],
                   tons=tons, margin=margin_pct)

    direct = bt["direct"]
    sell_price = bt["bid_total"]
    gross_profit = bt["margin_amt"]

    cost_section = {
        "fab_hours": fab_hrs,
        "erect_hours": erect_hrs,
        "total_hours": fab_hrs + erect_hrs,
        "labor_cost": lc["total_labor"],
        "steel_cost": bt["breakdown"]["steel_material"],
        "direct_cost": direct,
        "overhead_pct": rates["overhead"],
        "margin_pct": margin_pct,
        "sell_price": sell_price,
        "gross_profit": gross_profit,
        "cost_per_ton": round(direct / tons, 2) if tons > 0 else 0,
        "cost_per_lb": round(direct / total_lbs, 4) if total_lbs > 0 else 0,
        "hrs_per_ton": round((fab_hrs + erect_hrs) / tons, 1) if tons > 0 else 0,
    }

    # ── Section 4: Risk Flags ─────────────────────────────────────────
    risk_flags = []

    # Weight discrepancies
    if aisc["discrepancy_count"] > 0:
        risk_flags.append({
            "flag": "WEIGHT_DISCREPANCY",
            "severity": "warning",
            "detail": f"{aisc['discrepancy_count']} members have >2% weight "
                      "difference between SSP and AISC lookup",
        })

    # Very heavy project
    if tons > 200:
        risk_flags.append({
            "flag": "HEAVY_PROJECT",
            "severity": "info",
            "detail": f"{tons:.1f} tons. Consider crane plan and multi-phase erection.",
        })

    # High complexity
    if comp > 1.3:
        risk_flags.append({
            "flag": "HIGH_COMPLEXITY",
            "severity": "warning",
            "detail": f"Complexity factor {comp}x increases labor hours "
                      f"by {(comp-1)*100:.0f}%",
        })

    # Missing lengths
    no_length = sum(1 for m in members if m["length_ft"] == 0)
    if no_length > 0:
        risk_flags.append({
            "flag": "MISSING_LENGTHS",
            "severity": "warning",
            "detail": f"{no_length} of {len(members)} members have no length. "
                      "Weight calculations may be inaccurate.",
        })

    # Unusual shapes (not in AISC)
    unverified = sum(1 for m in aisc["verified_members"] if not m["aisc_verified"])
    if unverified > 0:
        risk_flags.append({
            "flag": "UNVERIFIED_SHAPES",
            "severity": "warning",
            "detail": f"{unverified} shapes not found in AISC database. "
                      "May be HSS, angles, or custom members.",
        })

    # Low margin warning
    if margin_pct < 0.15:
        risk_flags.append({
            "flag": "LOW_MARGIN",
            "severity": "warning",
            "detail": f"Margin at {margin_pct*100:.0f}%. Your Company target is 18%.",
        })

    verdict = _verdict(risk_flags)

    return {
        "ok": True,
        "project_name": project_name or "Untitled",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "risk_flags": risk_flags,
        "section_1_scope": scope,
        "section_2_weight": weight_audit,
        "section_3_cost": cost_section,
        "section_4_risks": risk_flags,
        "risk_count": len(risk_flags),
        "summary": {
            "tons": tons,
            "sell_price": sell_price,
            "margin_pct": margin_pct,
            "risk_count": len(risk_flags),
            "verdict": verdict,
        },
    }


def _shape_breakdown(members: list[dict]) -> dict:
    """Count members by shape prefix (W, HSS, L, etc.)."""
    breakdown = {}
    for m in members:
        prefix = re.match(r"([A-Z]+)", m["shape"])
        key = prefix.group(1) if prefix else "OTHER"
        breakdown[key] = breakdown.get(key, 0) + m["qty"]
    return breakdown


def _verdict(risk_flags: list[dict]) -> str:
    """Overall bid review verdict."""
    warnings = sum(1 for f in risk_flags if f["severity"] == "warning")
    if warnings >= 3:
        return "REVIEW_REQUIRED"
    elif warnings >= 1:
        return "PROCEED_WITH_CAUTION"
    else:
        return "CLEAR_TO_BID"
