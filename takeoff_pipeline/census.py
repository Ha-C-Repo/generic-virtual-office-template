"""T2 member census: regex sweep over vector text objects.

Sweeps every non-scanned sheet for member designations (W, HSS, L, C,
MC, WT, PL, pipe, and K/LH/DLH joist callouts plus joist girders) and
stores every hit in SQLite (takeoff_pipeline/census.db, WAL mode) with
the Appendix A columns of TAKEOFF_SCHEMA_V2.md: designation, item_class,
sheet, bbox, raw_text, source_kind, primary_source, confidence,
conflict_group.

Schedule tables (pdfplumber) are the PRIMARY count for count classes
per P30; plan callouts are the cross-check. Counts that disagree become
CONFLICT rows in the conflicts table, logged, never resolved silently
(schema section 8). BEAM stays plan-primary per section 5.

Confidence (P24, schema section 6): high for schedule-table hits,
medium for plan-text designation hits, low for anything ambiguous
(keyword-context hits such as anchor rods, embeds, ladders, deck
phrases, SF figures - real evidence, not a designation grammar).

Counts only. No pricing (P25). No AISC weight math here (weights are
derived downstream per schema section 4). Standalone: no bridge/
imports. census.db lives next to this file; if promoted into bridge/,
paths switch to resource_path() at that time.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from takeoff_pipeline import sheet_router

log = logging.getLogger("takeoff_pipeline.census")

_PKG = Path(__file__).resolve().parent
DB_PATH = _PKG / "census.db"

# -- designation grammar ---------------------------------------------------
# Order matters: more specific families first so a joist girder is not
# half-eaten by the K-series pattern, and MC is tried before C.
_FRACTION = r"\d{1,2}/\d{1,2}"
_NUM = r"\d{1,3}(?:\.\d{1,3})?"
# Thickness: try the fraction form first ("1/4", "1 1/4"), else the
# decimal, or the greedy number alternative eats the "1" of "1/4".
_THICK = rf"(?:(?:\d{{1,2}}\s)?{_FRACTION}|{_NUM})"
# Separator: schedules routinely space the X ("C6 X 8.2"). The family
# letter stays glued to its first digit so grid text like "C 8" cannot
# false-positive.
_X = r"\s?[xX]\s?"
# One plate dimension leg: x10, X 13", x1'-2", X 0'-8 1/2".
_PL_DIM = (r"[xX]\s?\d[\d/]*(?:\s\d{1,2}/\d{1,2})?[\"']?"
           r"(?:-\d{1,2}(?:\s?\d{1,2}/\d{1,2})?[\"']?)?")

DESIGNATION_PATTERNS = (
    ("JST", re.compile(
        r"\b\d{2,3}G\d{1,2}N\d{1,2}(?:\.\d{1,2})?K?\b", re.I)),
    ("JST", re.compile(r"\b\d{1,3}(?:K|LH|DLH)\d{1,2}\b")),
    ("BEAM", re.compile(rf"\bW\d{{1,2}}{_X}{_NUM}\b")),
    ("BEAM", re.compile(rf"\bWT\d{{1,2}}(?:\.\d)?{_X}{_NUM}\b")),
    # Size legs are lazy so the wall-thickness branch claims the final
    # X1/4 instead of the size repetition eating its leading digit.
    ("BEAM", re.compile(
        rf"\bHSS\s?{_NUM}(?:{_X}{_NUM}){{1,2}}?"
        rf"(?:{_X}{_THICK})?\"?", re.I)),
    ("BEAM", re.compile(rf"\bMC\d{{1,2}}{_X}{_NUM}\b")),
    ("BEAM", re.compile(rf"\bC\d{{1,2}}{_X}{_NUM}\b")),
    ("BEAM", re.compile(
        rf"\bL\d{{1,2}}(?:\s?{_FRACTION})?"
        rf"(?:{_X}\d{{1,2}}(?:\s?{_FRACTION})?){{1,2}}"
        rf"{_X}{_THICK}\"?", re.I)),
    ("PLATE", re.compile(
        rf"\bPL\s?(?:{_NUM}\s?)?(?:{_FRACTION})\"?(?:\s?{_PL_DIM}){{0,3}}"
        rf"|\bPL\s?{_NUM}\"?(?:\s?{_PL_DIM}){{1,3}}", re.I)),
    ("BEAM", re.compile(
        rf"\bPIPE\s?{_NUM}(?:\s?{_FRACTION})?\s?"
        r"(?:STD|XS|XXS|X-?STRONG|SCH(?:EDULE)?\s?\d{2,3})?\b", re.I)),
    # Pipe written as a diameter plus SCHEDULE wall, e.g. the caged
    # ladder rails: 1 1/2" dia x SCHEDULE 40.
    ("BEAM", re.compile(
        rf"\b{_NUM}(?:\s?{_FRACTION})?\s?\"?\s?[ø⌀∅]?\s?"
        r"[xX]?\s?SCH(?:EDULE)?\s?\d{2,3}\b", re.I)),
)

# Keyword/context families. Real evidence the scoring set needs, but
# not a designation grammar, so confidence is LOW on plan text per the
# ambiguity rule (high when read out of a schedule table).
KEYWORD_PATTERNS = (
    ("ANCH", re.compile(r"\bANCHOR\s+(?:ROD|BOLT)S?\b", re.I)),
    ("MISC", re.compile(r"\bCAGED?\s+LADDER\b|\bLADDER\b", re.I)),
    ("MISC", re.compile(r"\bEMBED(?:MENT)?(?:\s?PL(?:ATE)?S?)?\b", re.I)),
    ("DECK", re.compile(
        r"\b(?:ROOF|FLOOR|COMPOSITE|METAL)\s+DECK\b|\b\d{1,2}\s?GA\.?\s?"
        r"(?:[A-Z0-9\s]{0,12})?DECK\b", re.I)),
    ("MISC", re.compile(r"\b\d{1,3}(?:,\d{3})+\s?SF\b|\b\d{4,7}\s?SF\b")),
    ("MISC", re.compile(r"\bCAMBER(?:ED)?\b", re.I)),
)

# Schedule heading: BEARING CHANNEL SCHEDULE yes, pipe SCHEDULE 40 no.
_SCHEDULE_HEADING = re.compile(
    r"\b([A-Z][A-Z &/.'-]{2,40}?\s+SCHEDULE)\b(?!\s*\d)")

_QTY_HEADER = re.compile(r"^(?:QTY|QUANTITY|NO\.?|COUNT|#|EA)\.?$", re.I)


def _reconstruct_row(cells) -> str:
    """Rebuild a schedule row whose tags pdfplumber split across cells,
    even mid-token ('P' + 'L1" X 13" X 1\'' + '-1" ...'). A short
    alphabetic fragment glues to the next cell; a cell starting with a
    dash or slash glues to the previous one. The result is swept for
    designations the cell-level pass could not see."""
    merged = []
    for c in cells:
        c = (c or "").strip()
        if not c:
            continue
        if merged and (
                (len(merged[-1]) <= 2 and merged[-1].isalpha())
                or c[0] in "-/"):
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    return " ".join(merged)

# Count classes per schema section 5 / Appendix A: schedule is primary,
# plan callouts are the cross-check. BEAM stays plan-primary.
COUNT_CLASSES = ("COL", "JST", "ANCH", "PLATE")


# A column type parses under the BEAM grammar family (W, HSS, pipe,
# WT). In a column-keyed schedule those shapes ARE the column types.
_COLUMN_SHAPE_HINTS = ("BEAM",)


def classify_hit(item_class_hint: str, source_name: str) -> str:
    """Appendix A deterministic class mapping. Any hit from a
    COLUMN/FOOTING SCHEDULE is COL regardless of its grammar family.

    A1 extension: a base-plate or column-size schedule is keyed by
    column (one base plate per column SIZE). Its shape entries (the
    BEAM grammar family) are the column types, so they promote to COL;
    its PL entries are the base plates and stay PLATE. Scoped to
    schedule sources only: a shape called out on a framing plan keeps
    its BEAM class, because member sizes are plan-primary and the
    schedule is the cross-check (P30, section 5). This fixes the SP183
    defect where base-plate-schedule HSS rows landed in the beam set."""
    src = (source_name or "").upper()
    if "COLUMN" in src and "SCHEDULE" in src:
        return "COL"
    if "FOOTING" in src and "SCHEDULE" in src:
        return "COL"
    if "COLUMN SIZE" in src or ("BASE PLATE" in src and "SCHEDULE" in src):
        if item_class_hint in _COLUMN_SHAPE_HINTS:
            return "COL"
        return item_class_hint or "MISC"
    return item_class_hint or "MISC"


def normalize_designation(text: str) -> str:
    """Normalization for MATCHING only. The stored designation stays
    raw per schema 3.2 (never an invented or normalized tag)."""
    return re.sub(r"[\s\"']", "", (text or "").upper())


# -- storage ---------------------------------------------------------------

def _conn(db_path=None) -> sqlite3.Connection:
    """WAL mode plus busy timeout per Hard Rule 11."""
    path = Path(db_path) if db_path else DB_PATH
    c = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.row_factory = sqlite3.Row
    return c


def init_db(db_path=None) -> None:
    c = _conn(db_path)
    try:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS census_hits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job TEXT NOT NULL,
                designation TEXT NOT NULL,
                item_class TEXT NOT NULL,
                sheet TEXT NOT NULL,
                bbox TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                source_kind TEXT NOT NULL
                    CHECK (source_kind IN ('SCHEDULE','PLAN')),
                primary_source TEXT NOT NULL,
                confidence TEXT NOT NULL
                    CHECK (confidence IN ('high','medium','low')),
                conflict_group TEXT,
                qty REAL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job TEXT NOT NULL,
                conflict_group TEXT NOT NULL,
                designation TEXT NOT NULL,
                item_class TEXT NOT NULL,
                schedule_qty REAL,
                plan_qty REAL,
                schedule_source TEXT,
                plan_source TEXT,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_hits_job
                ON census_hits(job, designation);
        """)
        c.commit()
    finally:
        c.close()


# -- extraction ------------------------------------------------------------

def sweep_text(text: str):
    """Regex sweep over one text object. Yields (family, class_hint,
    matched_text, span). Designation families first, then keywords.
    Overlapping designation matches are deduped by span."""
    taken = []
    for class_hint, pat in DESIGNATION_PATTERNS:
        for m in pat.finditer(text):
            span = m.span()
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            taken.append(span)
            yield ("designation", class_hint, m.group(0), span)
    for class_hint, pat in KEYWORD_PATTERNS:
        for m in pat.finditer(text):
            span = m.span()
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            yield ("keyword", class_hint, m.group(0), span)


def _page_spans(page):
    """Vector text objects with bboxes, via PyMuPDF span dicts."""
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = span.get("text", "")
                if txt.strip():
                    out.append((txt, tuple(span.get("bbox", (0, 0, 0, 0)))))
    return out


def _inside(bbox, regions) -> bool:
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in regions)


def _derotate(bbox, page):
    """Map a pdfplumber bbox (rotated-visual space) into PyMuPDF page
    coordinates. Schema 3.2 declares bbox as PyMuPDF page coordinates;
    on a /Rotate page the two producers disagree and every schedule
    rect would land on the wrong part of Ivan's QA overlay."""
    if not page.rotation:
        return tuple(bbox)
    import fitz
    r = fitz.Rect(bbox) * page.derotation_matrix
    r.normalize()
    return (r.x0, r.y0, r.x1, r.y1)


def _schedule_tables(pdf_path: str, page_index: int, page_text: str):
    """Schedule tables on one page: (heading, bbox, rows, cell_bboxes).

    A table is a schedule ONLY when a clean schedule heading is
    geometrically adjacent: the heading line sits just above the table
    (or in its top band, since find_tables often swallows the title
    row) AND overlaps it horizontally. The heading line is rebuilt from
    words that overlap the table's x-range, never from the full page
    width, so rotated or distant text cannot splice into the name.
    A table with no qualifying heading is NOT a schedule: it is ignored
    entirely and never becomes a plan-sweep exclusion region."""
    if not _SCHEDULE_HEADING.search(page_text.upper()):
        return []
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        words = page.extract_words()
        anchor_words = [w for w in words
                        if w["text"].upper() == "SCHEDULE"
                        or w["text"].upper().rstrip(":") == "SCHEDULE"]
        for table in page.find_tables():
            rows = table.extract()
            if not rows:
                continue
            tx0, ttop, tx1, _tb = table.bbox
            name = ""
            best = None
            for hw in anchor_words:
                if not (ttop - 60 <= hw["top"] <= ttop + 40):
                    continue
                if hw["x1"] < tx0 - 10 or hw["x0"] > tx1 + 10:
                    continue
                line = sorted(
                    (w for w in words
                     if abs(w["top"] - hw["top"]) < 4
                     and w["x1"] >= tx0 - 30 and w["x0"] <= tx1 + 30),
                    key=lambda w: w["x0"])
                m = _SCHEDULE_HEADING.search(
                    " ".join(w["text"] for w in line).upper())
                if not m:
                    continue
                d = abs(ttop - hw["top"])
                if best is None or d < best:
                    best = d
                    name = m.group(1).strip()
            if not name:
                continue
            cell_bboxes = [r.cells for r in table.rows]
            out.append((name, tuple(table.bbox), rows, cell_bboxes))
    return out


def _schedule_hits(job, sheet_ref, sheet_number, tables, now):
    """Rows for matches inside schedule tables. Sweeps CELL BY CELL so
    raw_text and bbox are the matched cell, per Appendix A. When a row
    yields no cell-level designation (pdfplumber split the tag across
    cells), the joined row text is swept as a fallback and any hit is
    stored LOW confidence: a reconstructed tag is ambiguous evidence,
    never a clean schedule row. Keyword families (anchor rods, embeds)
    are recorded too, so count classes can have a schedule side.
    qty reads from a QTY-like column when one exists."""
    hits = []
    for name, bbox, rows, cell_bboxes in tables:
        if not rows:
            continue
        header = [str(c or "").strip() for c in rows[0]]
        qty_col = None
        for i, h in enumerate(header):
            if _QTY_HEADER.match(h):
                qty_col = i
                break
        for r_idx, row in enumerate(rows[1:], start=1):
            cells = [str(c or "").strip() for c in row]
            qty = None
            if qty_col is not None and qty_col < len(cells):
                qm = re.search(r"\d+(?:\.\d+)?", cells[qty_col])
                if qm:
                    qty = float(qm.group(0))
            bboxes = cell_bboxes[r_idx] if r_idx < len(cell_bboxes) \
                else []

            def emit(matched, hint, raw, cell_bbox, confidence):
                hits.append({
                    "job": job,
                    "designation": matched.strip(),
                    "item_class": classify_hit(hint, name),
                    "sheet": sheet_number,
                    "bbox": json.dumps(
                        [round(v, 1) for v in (cell_bbox or bbox)]),
                    "raw_text": raw[:300],
                    "source_kind": "SCHEDULE",
                    "primary_source": f"{sheet_ref} {name}".strip(),
                    "confidence": confidence,
                    "conflict_group": None,
                    "qty": qty,
                    "created_at": now,
                })

            seen = set()
            for c_idx, cell in enumerate(cells):
                if not cell:
                    continue
                cb = bboxes[c_idx] if c_idx < len(bboxes) else None
                for family, hint, matched, _ in sweep_text(cell):
                    if family == "designation":
                        seen.add(normalize_designation(matched))
                    emit(matched, hint, cell, cb, "high")
            # Second pass over the reconstructed row recovers tags that
            # pdfplumber split across cells. Anything found ONLY this
            # way is LOW confidence with the rebuilt row as raw_text: a
            # reconstructed tag is ambiguous evidence, never a clean
            # schedule row.
            recon = _reconstruct_row(cells)
            if recon:
                for family, hint, matched, _ in sweep_text(recon):
                    if family != "designation":
                        continue
                    key = normalize_designation(matched)
                    if key in seen or any(key in s or s in key
                                          for s in seen):
                        continue
                    seen.add(key)
                    emit(matched, hint, recon, None, "low")
    return hits


def run_census(pdf_path, job, db_path=None, router_result=None) -> dict:
    """Sweep one drawing set into census.db. Idempotent per job: prior
    rows for the job are replaced. Scanned sheets are skipped (T1 owns
    that routing; the 4x rasterization procedure is external)."""
    import fitz

    pdf_path = str(pdf_path)
    router_result = router_result or sheet_router.route(pdf_path)
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    hits = []

    doc = fitz.open(pdf_path)
    try:
        for entry in router_result["sheets"]:
            if entry["is_scanned"]:
                continue
            i = entry["page_index"]
            page = doc[i]
            sheet_number = entry["sheet_number"] or f"PAGE-{i}"
            sheet_ref = " ".join(
                x for x in (entry["sheet_number"], entry["sheet_title"])
                if x).strip() or f"PAGE-{i}"
            page_text = page.get_text()

            tables = _schedule_tables(pdf_path, i, page_text)
            if page.rotation:
                tables = [
                    (name, _derotate(bbox, page), rows,
                     [[(_derotate(cb, page) if cb else cb)
                       for cb in row] for row in cell_bboxes])
                    for name, bbox, rows, cell_bboxes in tables]
            hits.extend(
                _schedule_hits(job, sheet_ref, sheet_number, tables, now))
            table_regions = [bbox for _, bbox, _, _ in tables]

            for txt, bbox in _page_spans(page):
                if table_regions and _inside(bbox, table_regions):
                    continue
                for family, hint, matched, _ in sweep_text(txt):
                    confidence = "medium" if family == "designation" \
                        else "low"
                    hits.append({
                        "job": job,
                        "designation": matched.strip(),
                        "item_class": classify_hit(hint, ""),
                        "sheet": sheet_number,
                        "bbox": json.dumps(
                            [round(v, 1) for v in bbox]),
                        "raw_text": txt[:300],
                        "source_kind": "PLAN",
                        "primary_source": sheet_ref,
                        "confidence": confidence,
                        "conflict_group": None,
                        "qty": None,
                        "created_at": now,
                    })
    finally:
        doc.close()

    conflicts = _find_conflicts(job, hits, now)

    c = _conn(db_path)
    try:
        c.execute("DELETE FROM census_hits WHERE job = ?", (job,))
        c.execute("DELETE FROM conflicts WHERE job = ?", (job,))
        c.executemany(
            "INSERT INTO census_hits (job, designation, item_class, sheet,"
            " bbox, raw_text, source_kind, primary_source, confidence,"
            " conflict_group, qty, created_at) VALUES"
            " (:job, :designation, :item_class, :sheet, :bbox, :raw_text,"
            "  :source_kind, :primary_source, :confidence, :conflict_group,"
            "  :qty, :created_at)", hits)
        c.executemany(
            "INSERT INTO conflicts (job, conflict_group, designation,"
            " item_class, schedule_qty, plan_qty, schedule_source,"
            " plan_source, note, created_at) VALUES"
            " (:job, :conflict_group, :designation, :item_class,"
            "  :schedule_qty, :plan_qty, :schedule_source, :plan_source,"
            "  :note, :created_at)", conflicts)
        c.commit()
    finally:
        c.close()

    for cf in conflicts:
        log.warning("CONFLICT %s: %s", cf["conflict_group"], cf["note"])

    return {
        "job": job,
        "pdf": pdf_path,
        "hits": len(hits),
        "schedule_hits": sum(
            1 for h in hits if h["source_kind"] == "SCHEDULE"),
        "plan_hits": sum(1 for h in hits if h["source_kind"] == "PLAN"),
        "conflicts": len(conflicts),
        "scanned_sheets": [e["sheet_number"] or f"PAGE-{e['page_index']}"
                           for e in router_result["scanned"]],
        "db_path": str(Path(db_path) if db_path else DB_PATH),
    }


def _find_conflicts(job, hits, now):
    """Schedule qty vs plan callout count, count classes only (P30:
    schedule is the primary for count classes; plan is the cross-check).
    Disagreement is logged, never resolved silently (section 8).

    Grouping is by normalized designation ONLY, never (designation,
    class): classify_hit rewrites the class on the schedule side (a
    COLUMN/FOOTING SCHEDULE hit becomes COL) while the same tag on a
    plan stays BEAM, and a class-keyed grouping would make COL conflicts
    structurally impossible. The schedule side's class decides whether
    the designation is a count class."""
    conflicts = []
    by_key = {}
    for h in hits:
        by_key.setdefault(normalize_designation(h["designation"]),
                          []).append(h)
    for norm, group in sorted(by_key.items()):
        sched = [h for h in group if h["source_kind"] == "SCHEDULE"]
        plan = [h for h in group if h["source_kind"] == "PLAN"]
        if not sched or not plan:
            continue
        item_class = sched[0]["item_class"]
        if item_class not in COUNT_CLASSES:
            continue
        sched_qty = sum(h["qty"] for h in sched if h["qty"] is not None)
        if not sched_qty:
            continue
        plan_qty = float(len(plan))
        if sched_qty == plan_qty:
            continue
        group_key = f"{job}:{item_class}:{norm}"
        for h in group:
            h["conflict_group"] = group_key
            h["confidence"] = "low"
        conflicts.append({
            "job": job,
            "conflict_group": group_key,
            "designation": group[0]["designation"],
            "item_class": item_class,
            "schedule_qty": sched_qty,
            "plan_qty": plan_qty,
            "schedule_source": sched[0]["primary_source"],
            "plan_source": plan[0]["primary_source"],
            "note": (f"CONFLICT: {sched[0]['primary_source']} "
                     f"{sched_qty:g} EA vs {plan[0]['primary_source']} "
                     f"plan callouts {plan_qty:g} EA."
                     " RFI candidate. Never resolved silently."),
            "created_at": now,
        })
    return conflicts


def aggregate(job, db_path=None) -> list:
    """Per-designation aggregates for scoring: schedule qty, plan hit
    count, sheets, worst-case confidence, conflict flag."""
    c = _conn(db_path)
    try:
        rows = c.execute(
            "SELECT * FROM census_hits WHERE job = ?", (job,)).fetchall()
    finally:
        c.close()
    by_key = {}
    for r in rows:
        key = (normalize_designation(r["designation"]), r["item_class"])
        by_key.setdefault(key, []).append(r)
    out = []
    rank = {"low": 0, "medium": 1, "high": 2}
    for (norm, item_class), group in sorted(by_key.items()):
        sched_qty = sum(r["qty"] for r in group
                        if r["source_kind"] == "SCHEDULE"
                        and r["qty"] is not None)
        plan_count = sum(1 for r in group if r["source_kind"] == "PLAN")
        out.append({
            "designation_norm": norm,
            "designation": group[0]["designation"],
            "item_class": item_class,
            "schedule_qty": sched_qty or None,
            "plan_count": plan_count,
            "sheets": sorted({r["sheet"] for r in group}),
            "confidence": min((r["confidence"] for r in group),
                              key=lambda v: rank[v]),
            "conflict": any(r["conflict_group"] for r in group),
            "raw_samples": [r["raw_text"] for r in group[:3]],
        })
    return out
