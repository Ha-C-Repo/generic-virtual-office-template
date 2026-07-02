"""Bluebeam Markups Summary CSV importer.

The estimator marks up structural drawings in Bluebeam Revu with the
AISC tool set (ZenEstimate or in-house), then exports the Markups List
via Markups List > Summary > CSV Summary. This module accepts that
export and produces:

  1. A normalized member list (Cowork's internal BOQ format)
  2. An optional Assemblies BOQ.xlsx written to disk for archival

Bluebeam Markups Summary CSV columns of interest:
    Subject       e.g. "W12X26 BEAM"  -> resolves to AISC W12X26
    Comments      free-text annotation (mark, callout, location)
    Layer         tool-set name; doubles as a sanity check
    Page Label    sheet number (S2.0, S2.1, ...)
    Length        with units "24.5 ft" or "24'-6\""
    Area          with units (for plates that came in as Area Measure)
    Count         for Count tools (anchor rods, headed studs)
    Status        Bluebeam workflow flag (Verified / Tentative / Question)

Calibration sanity gate (F13): the importer warns if median Length on a
beam-like tool is below 2 ft or above 80 ft (typical structural range
4 to 60 ft). Below 2 ft usually means the page was not calibrated; above
80 ft usually means feet vs inches confusion.
"""

from __future__ import annotations
from pathlib import Path
from typing import Iterable
import csv
import re

_THIS = Path(__file__).resolve().parent
_TOOL_MAP_PATH = _THIS.parent / "data" / "bluebeam_tool_map.csv"

# Bluebeam Length text forms accepted:
#   '24.5 ft'  '24'-6"'  '24'-6 1/2"'  '294 in'  '294.0 in'  '24 ft 6 in'
_LEN_FORMATS = [
    re.compile(r"^([\d.]+)\s*ft$", re.IGNORECASE),
    re.compile(r"^([\d.]+)\s*in$", re.IGNORECASE),
    re.compile(r"^(\d+)'\s*(?:-\s*)?(\d+(?:\s+\d+/\d+)?(?:\.\d+)?)\"?$"),
    re.compile(r"^(\d+)\s*ft\s+(\d+(?:\.\d+)?)\s*in$", re.IGNORECASE),
    re.compile(r"^(\d+)'$"),
    re.compile(r"^([\d.]+)$"),  # bare number -> treat as feet
]


def _parse_length_text(s: str) -> float:
    """Return length in feet from a Bluebeam Length field."""
    if not s:
        return 0.0
    s = str(s).strip().replace("\xa0", " ")
    for rgx in _LEN_FORMATS:
        m = rgx.match(s)
        if not m:
            continue
        if rgx.pattern.endswith("in$"):
            return float(m.group(1)) / 12.0
        if rgx.pattern.endswith("ft$") or rgx.pattern == r"^([\d.]+)$":
            return float(m.group(1))
        if rgx.pattern.endswith("'$"):
            return float(m.group(1))
        # feet-inches forms
        ft = float(m.group(1))
        inch_part = m.group(2) if m.lastindex >= 2 else "0"
        # handle '6 1/2'
        if " " in inch_part and "/" in inch_part:
            whole, frac = inch_part.split(" ", 1)
            num, den = frac.split("/")
            inches = float(whole) + float(num) / float(den)
        elif "/" in inch_part:
            num, den = inch_part.split("/")
            inches = float(num) / float(den)
        else:
            inches = float(inch_part)
        return ft + inches / 12.0
    return 0.0


def _load_tool_map() -> dict[str, dict]:
    """Subject (uppercased, whitespace-normalized) -> {aisc, member_type}."""
    out: dict[str, dict] = {}
    if not _TOOL_MAP_PATH.exists():
        return out
    with _TOOL_MAP_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = re.sub(r"\s+", " ", (row.get("bluebeam_subject") or "")).strip().upper()
            if not key:
                continue
            out[key] = {
                "aisc": (row.get("aisc_designation") or "").strip(),
                "member_type": (row.get("member_type") or "structural").strip().lower(),
            }
    return out


def _resolve_subject(subject: str, tool_map: dict[str, dict]) -> dict | None:
    """Try exact match, then strip role suffix (BEAM/COLUMN/JOIST/ANGLE)."""
    if not subject:
        return None
    key = re.sub(r"\s+", " ", subject).strip().upper()
    if key in tool_map:
        return tool_map[key]
    # Fallback: shape-only token at start of subject
    m = re.match(r"^([A-Z0-9./\-]+)", key)
    if m:
        tok = m.group(1)
        # Try common role variants
        for role in (" BEAM", " COLUMN", " JOIST", " ANGLE", " CHANNEL", ""):
            cand = (tok + role).strip()
            if cand in tool_map:
                return tool_map[cand]
        return {"aisc": tok, "member_type": "structural"}
    return None


def import_markups_csv(csv_path: str | Path) -> dict:
    """Read a Bluebeam Markups Summary CSV and return normalized members.

    Returns:
        {
            members: [{shape, length_ft, qty, member_type, mark, sheet, status, layer, _source}],
            rows_total, rows_with_shape, rows_skipped,
            calibration_warnings, status_breakdown, unmapped_subjects,
        }
    """
    csv_path = Path(csv_path)
    tool_map = _load_tool_map()
    members: list[dict] = []
    rows_total = 0
    rows_skipped = 0
    status_count: dict[str, int] = {}
    unmapped: list[str] = []
    cal_warn: list[str] = []

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Normalize header keys to lowercase no-punct
        norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
        # Build a per-row dict that maps logical keys to header names
        first_pass = list(reader)
        if not first_pass:
            return {"members": [], "rows_total": 0, "rows_with_shape": 0,
                    "rows_skipped": 0, "calibration_warnings": [],
                    "status_breakdown": {}, "unmapped_subjects": []}
        headers = {norm(h): h for h in first_pass[0].keys()}

        def col(*aliases):
            for a in aliases:
                k = norm(a)
                if k in headers:
                    return headers[k]
            return None

        c_subject = col("subject", "tool")
        c_comments = col("comments", "comment", "label")
        c_length = col("length")
        c_area = col("area")
        c_count = col("count")
        c_sheet = col("pagelabel", "page", "sheet", "pagenum")
        c_status = col("status")
        c_layer = col("layer")

        for row in first_pass:
            rows_total += 1
            subject = (row.get(c_subject) or "").strip() if c_subject else ""
            comments = (row.get(c_comments) or "").strip() if c_comments else ""
            length_txt = (row.get(c_length) or "").strip() if c_length else ""
            count_txt = (row.get(c_count) or "").strip() if c_count else ""
            sheet = (row.get(c_sheet) or "").strip().upper() if c_sheet else ""
            status = (row.get(c_status) or "").strip() if c_status else ""
            layer = (row.get(c_layer) or "").strip() if c_layer else ""

            resolved = _resolve_subject(subject, tool_map)
            if not resolved or not resolved.get("aisc"):
                rows_skipped += 1
                if subject:
                    unmapped.append(subject)
                continue

            length_ft = _parse_length_text(length_txt)
            qty = int(float(count_txt)) if count_txt else 1

            # Calibration sanity: structural members should be 2 ft to 80 ft
            if (resolved["member_type"] == "structural"
                    and length_ft and (length_ft < 2.0 or length_ft > 80.0)):
                cal_warn.append(
                    f"{subject} length {length_ft:.2f} ft outside 2-80 ft range "
                    f"on {sheet or 'unknown sheet'}. Verify calibration."
                )

            members.append({
                "shape": resolved["aisc"],
                "length_ft": length_ft,
                "qty": qty,
                "member_type": resolved["member_type"],
                "mark": comments,
                "sheet": sheet,
                "status": status,
                "layer": layer,
                "_source": "bluebeam",
            })
            status_count[status or "(none)"] = status_count.get(status or "(none)", 0) + 1

    return {
        "members": members,
        "rows_total": rows_total,
        "rows_with_shape": len(members),
        "rows_skipped": rows_skipped,
        "calibration_warnings": cal_warn,
        "status_breakdown": status_count,
        "unmapped_subjects": sorted(set(unmapped))[:50],
    }


def write_boq_xlsx(members: Iterable[dict], out_path: str | Path) -> Path:
    """Write the imported members to an Assemblies BOQ.xlsx file."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise RuntimeError("openpyxl required to write .xlsx")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append([
        "shape", "length_ft", "qty", "member_type",
        "mark", "sheet", "status", "layer",
    ])
    for m in members:
        ws.append([
            m.get("shape", ""),
            float(m.get("length_ft", 0) or 0),
            int(m.get("qty", 1) or 1),
            m.get("member_type", ""),
            m.get("mark", ""),
            m.get("sheet", ""),
            m.get("status", ""),
            m.get("layer", ""),
        ])
    wb.save(out_path)
    return out_path


def import_and_write_boq(csv_path: str | Path, xlsx_path: str | Path) -> dict:
    """One-shot: read Bluebeam CSV and write the matching BOQ.xlsx."""
    parsed = import_markups_csv(csv_path)
    write_boq_xlsx(parsed["members"], xlsx_path)
    parsed["boq_path"] = str(xlsx_path)
    return parsed
