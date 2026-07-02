"""
bluebeam_boq_adapter.py

Bluebeam markup adapter for the BOQ source registry.

Bluebeam Revu exports markup data as either CSV (Markups List export)
or XML. This adapter probes the bid folder for those exports and yields
rows in the estimate-line shape.

Fidelity rank is BLUEBEAM (2), below PlanSwift but above manual_excel
and synthetic. Per Ivan's 2026-05-23 feedback, Bluebeam is markup-only
for Your Company; PlanSwift is the BOQ tool of record. This adapter lets
Bluebeam data still feed the pipeline when no PlanSwift export exists,
but the boq_origin field flags it as Bluebeam so reconciliation can
surface the lower-fidelity source.

Where the adapter looks
-----------------------
  1. ctx.bid_folder / "bluebeam" / *.csv | *.xml
  2. ctx.bid_folder / *bluebeam*.csv | *bluebeam*.xml
  3. ctx.bid_folder / "markups" / *.csv

Recognized CSV headers (Bluebeam Markups List default export)
-------------------------------------------------------------
  Subject / Comments / Label / Layer  -> description
  Length / Area / Count               -> qty
  (unit derived from column: LF for Length, SF for Area, EA for Count)
  Page                                -> sheet

Hard rules respected
--------------------
- No supplier names introduced. Description text passes through the
  same supplier scrub as the PlanSwift adapter.
- boq_origin="bluebeam" so Ivan-rule F can flag it.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from bridge.boq_sources import (
    BoqContext,
    BoqPayload,
    BoqSourceAdapter,
    FIDELITY_BLUEBEAM,
    register,
)

SCRUB_SUPPLIERS = [
    r"\bvulcraft\b", r"\bcanam\b", r"\bnucor\b", r"\bayamsa\b",
]

QTY_COLS_AND_UNITS = [
    ("count",  "EA"),
    ("length", "LF"),
    ("area",   "SF"),
]


def _scrub(text: str) -> str:
    out = text or ""
    for pat in SCRUB_SUPPLIERS:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", out).strip()


def _candidate_files(ctx: BoqContext) -> List[Path]:
    out: List[Path] = []
    if ctx.bid_folder and ctx.bid_folder.is_dir():
        bb_dir = ctx.bid_folder / "bluebeam"
        if bb_dir.is_dir():
            for p in sorted(bb_dir.iterdir()):
                if p.suffix.lower() in (".csv", ".xml"):
                    out.append(p)
        for p in sorted(ctx.bid_folder.glob("*bluebeam*")):
            if p.suffix.lower() in (".csv", ".xml") and p not in out:
                out.append(p)
        markups_dir = ctx.bid_folder / "markups"
        if markups_dir.is_dir():
            for p in sorted(markups_dir.iterdir()):
                if p.suffix.lower() == ".csv" and p not in out:
                    out.append(p)
    return out


def _read_csv(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _has_bluebeam_shape(rows: List[Dict[str, Any]]) -> bool:
    if not rows:
        return False
    headers_low = {h.strip().lower() for h in rows[0].keys()}
    # Must have at least one description-ish column and one qty-ish column
    desc_ok = any(k in headers_low for k in ("subject", "comments", "label", "layer"))
    qty_ok  = any(k in headers_low for k in ("count", "length", "area"))
    return desc_ok and qty_ok


def _normalize_rows(rows: List[Dict[str, Any]], source: Path) -> List[Dict[str, Any]]:
    out = []
    for idx, r in enumerate(rows, start=1):
        low = {k.strip().lower(): v for k, v in r.items()}
        desc = (low.get("subject") or low.get("comments")
                or low.get("label") or low.get("layer") or "").strip()
        desc = _scrub(desc)
        if not desc:
            continue
        qty = 0.0
        unit = "EA"
        for col, u in QTY_COLS_AND_UNITS:
            if col in low and low[col] not in (None, "", "None"):
                try:
                    qty = float(low[col])
                    unit = u
                    break
                except (TypeError, ValueError):
                    pass
        sheet = (low.get("page") or low.get("sheet") or "").strip()
        out.append({
            "line_id": f"LINE-BB-{idx:04d}",
            "description": desc,
            "category": "Direct",
            "discipline": "Structural",
            "unit": unit,
            "qty": qty,
            "unit_rate": 0.0,
            "extended": 0.0,
            "requirement_refs": [],
            "rate_basis": f"Bluebeam markup export: {source.name}",
            "markup_applied": False,
            "notes": f"sheet={sheet}" if sheet else None,
        })
    return out


def bluebeam_probe(ctx: BoqContext) -> bool:
    for p in _candidate_files(ctx):
        if p.suffix.lower() != ".csv":
            continue  # only CSV supported for now
        try:
            rows = _read_csv(p)
        except Exception:
            continue
        if _has_bluebeam_shape(rows):
            return True
    return False


def bluebeam_load(ctx: BoqContext) -> BoqPayload:
    for p in _candidate_files(ctx):
        if p.suffix.lower() != ".csv":
            continue
        try:
            rows = _read_csv(p)
        except Exception:
            continue
        if not _has_bluebeam_shape(rows):
            continue
        normalized = _normalize_rows(rows, p)
        return BoqPayload(
            rows=normalized,
            boq_origin="bluebeam",
            source_file=str(p),
            row_count=len(normalized),
            fidelity_rank=FIDELITY_BLUEBEAM,
            notes=(
                f"Bluebeam markup read from {p.name}. Quantities measured "
                f"in Bluebeam; unit rates not present (pricing engine will "
                f"compute from production-rates.yaml)."
            ),
        )
    return BoqPayload(
        rows=[],
        boq_origin="bluebeam",
        source_file="",
        row_count=0,
        fidelity_rank=FIDELITY_BLUEBEAM,
        notes="probe returned True but no Bluebeam CSV could be read.",
    )


BLUEBEAM_ADAPTER = BoqSourceAdapter(
    name="bluebeam",
    fidelity_rank=FIDELITY_BLUEBEAM,
    probe=bluebeam_probe,
    load=bluebeam_load,
    description=(
        "Bluebeam markup CSV export. Lower fidelity than PlanSwift "
        "per Ivan's 2026-05-23 feedback. Looks in bid_folder/bluebeam/, "
        "bid_folder/*bluebeam*, or bid_folder/markups/."
    ),
)

register(BLUEBEAM_ADAPTER)
