"""F18: Member schedule pre-pass (vision-driven).

Best industry practice (LIFT, SketchDeck, Togal): extract the
**member schedule table** before counting marks on the plan. The
schedule lists every unique member with its mark, shape, length, and
quantity. Once the schedule is locked, the plan-view pass is reduced
to confirming that each mark is present (sanity), not measuring.

Mark on the plan -> schedule lookup -> validated dimensions.

This module:
1. Identifies schedule sheets (text contains "SCHEDULE" / "MEMBER LIST")
2. Sends those pages to Opus vision with a schedule-specific prompt
3. Parses the response into {mark: {shape, length_ft, qty, notes}}
4. Cross-validates plan-pass detections against the schedule
5. When a plan mark matches a schedule entry, the schedule entry's
   length and qty win (and confidence is boosted to 0.95+)
6. When a plan mark is NOT in the schedule, flag it
7. When a schedule entry has zero plan matches, flag it (missing
   in plan or vision missed it)

The schedule is treated as ground truth because that is what the
human estimator does. The drawing is a cross-check, not a
substitute.
"""

from __future__ import annotations
from pathlib import Path
import json
import logging
import os
import base64

log = logging.getLogger(__name__)


_SCHEDULE_PROMPT = """You are reading a structural engineering MEMBER SCHEDULE
on a construction drawing. This is a routine commercial steel takeoff task.

A member schedule is a TABLE with columns like:
    MARK | SHAPE | SIZE | LENGTH | QTY | NOTES
or:
    PIECE MARK | DESIGNATION | LENGTH (FT) | QTY

For every row in every schedule visible on this page, return:
- mark: piece mark as printed (e.g. B-101, C-1, J-12, L-1)
- shape: AISC designation in canonical form (e.g. W12X26, HSS6X6X1/2)
- family: W, HSS, C, L, K, LH, DLH, PL, misc
- member_type: structural | joist | plate | misc
- length_ft: length in feet, decimal (e.g. 24.5 for 24'-6")
- qty: integer count
- notes: any printed notes (e.g. "TYP", "GALV", "FIELD WELD")

If a row has no length, return length_ft = 0.
If a row has no qty, return qty = 1.

Return ONLY a JSON object: {"schedule": [...]} with one entry per row.
If no schedule is visible on this page, return {"schedule": []}.
"""


_SCHEDULE_KEYWORDS = (
    "SCHEDULE", "MEMBER LIST", "BEAM SCHEDULE", "COLUMN SCHEDULE",
    "JOIST SCHEDULE", "FOOTING SCHEDULE", "MEMBER SCHEDULE",
)


def page_is_likely_schedule(page_text: str) -> bool:
    if not page_text:
        return False
    upper = page_text.upper()
    return any(k in upper for k in _SCHEDULE_KEYWORDS)


def find_schedule_pages(pdf_path: str | Path) -> list[int]:
    """Scan a PDF for pages whose text contains schedule keywords."""
    try:
        import fitz
    except ImportError:
        return []
    pages: list[int] = []
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        txt = doc[i].get_text() or ""
        if page_is_likely_schedule(txt):
            pages.append(i)
    doc.close()
    return pages


def extract_schedule_from_image(image_path: str | Path) -> list[dict]:
    """Run Opus vision with the schedule-specific prompt."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set; cannot extract schedule.")
        return []
    try:
        from anthropic import Anthropic
    except ImportError:
        log.warning("anthropic SDK not installed; cannot extract schedule.")
        return []
    client = Anthropic()
    b64 = base64.b64encode(open(image_path, "rb").read()).decode("ascii")
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png",
                                             "data": b64}},
                {"type": "text", "text": _SCHEDULE_PROMPT},
            ],
        }],
        temperature=0,
    )
    txt = (resp.content[0].text if resp.content else "{}").strip()
    if txt.startswith("```"):
        txt = txt.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(txt)
    except json.JSONDecodeError as e:
        log.warning(f"Schedule JSON parse failed: {e}; raw[:120]={txt[:120]!r}")
        return []
    if isinstance(parsed, dict):
        return parsed.get("schedule", parsed.get("members", [])) or []
    if isinstance(parsed, list):
        return parsed
    return []


def extract_schedules_from_pdf(pdf_path: str | Path,
                                page_indices: list[int] | None = None,
                                dpi: int = 200) -> dict:
    """Run schedule extraction on all schedule-bearing pages."""
    try:
        import fitz
    except ImportError as e:
        raise RuntimeError("PyMuPDF required") from e

    pdf_path = Path(pdf_path)
    if page_indices is None:
        page_indices = find_schedule_pages(pdf_path)

    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    all_rows: list[dict] = []
    by_mark: dict[str, dict] = {}

    for pi in page_indices:
        page = doc[pi]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        tmp = Path(f"/tmp/_sched_p{pi:03d}.png")
        pix.save(tmp)
        try:
            rows = extract_schedule_from_image(tmp)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass
        for r in rows:
            r["source_page"] = pi
            all_rows.append(r)
            mk = (r.get("mark") or "").strip().upper()
            if mk:
                by_mark[mk] = r
    doc.close()
    return {
        "rows": all_rows,
        "by_mark": by_mark,
        "pages_scanned": page_indices,
        "row_count": len(all_rows),
        "mark_count": len(by_mark),
    }


def cross_validate(detections: list[dict], schedule: dict) -> dict:
    """Cross-check plan detections against the schedule.

    Mutates detections in place when a mark match is found:
      - length_ft <- schedule[mark].length_ft (if detection length was 0)
      - shape    <- schedule[mark].shape (if mismatch, prefer schedule)
      - confidence -> 0.95 (mark-confirmed)
      - schedule_validated = True

    Returns counts: matched, plan_only, schedule_only.
    """
    by_mark = schedule.get("by_mark") or {}
    matched: list[str] = []
    plan_only: list[dict] = []
    seen_marks: set[str] = set()
    for d in detections:
        mk = (d.get("mark") or "").strip().upper()
        if mk and mk in by_mark:
            sch = by_mark[mk]
            sch_len = float(sch.get("length_ft") or 0)
            if sch_len > 0 and float(d.get("length_ft") or 0) == 0:
                d["length_ft"] = sch_len
                d.setdefault("notes", []).append("length from schedule")
            sch_shape = (sch.get("shape") or "").strip()
            if sch_shape and sch_shape.upper() != (d.get("shape") or "").upper():
                d["shape"] = sch_shape
                d.setdefault("notes", []).append("shape corrected from schedule")
            d["confidence"] = max(float(d.get("confidence") or 0.0), 0.95)
            d["schedule_validated"] = True
            matched.append(mk)
            seen_marks.add(mk)
        else:
            plan_only.append(d)
    schedule_only = [mk for mk in by_mark if mk not in seen_marks]
    return {
        "matched_marks": sorted(set(matched)),
        "plan_only_count": len(plan_only),
        "schedule_only_marks": schedule_only,
        "matched_count": len(set(matched)),
    }


def schedule_to_detections(schedule: dict, page_idx: int = -1) -> list[dict]:
    """Convert schedule rows into detection dicts so they can be
    fed through the pricing pipeline directly when the plan-pass
    failed to find the mark.

    Used when cross_validate flags a schedule-only entry.
    """
    out: list[dict] = []
    for row in schedule.get("rows", []):
        out.append({
            "page": page_idx,
            "shape": row.get("shape"),
            "family": row.get("family"),
            "member_type": row.get("member_type"),
            "mark": row.get("mark"),
            "length_ft": float(row.get("length_ft") or 0),
            "qty": int(row.get("qty") or 1),
            "bbox": [0, 0, 0, 0],
            "confidence": 0.97,  # schedule-sourced
            "status": "FromSchedule",
            "schedule_validated": True,
            "notes": (row.get("notes") and [row.get("notes")]) or [],
        })
    return out
