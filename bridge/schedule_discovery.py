"""F25: Vision-based fallback for schedule page discovery.

When text-based sheet_sweep finds zero schedule pages (extracted page
sets, drawings without "MEMBER SCHEDULE" in title block text, or
text-stripped PDFs), this module asks Haiku per page "does this page
contain a member schedule?" using a tiny, cheap vision call.

Haiku is used (not Opus) because it's a one-shot binary classifier.
We don't ask Haiku to extract the schedule - that's still Opus territory.
We just need a yes/no per page so schedule_extractor knows where to look.

Falls back to "every framing-plan-adjacent page" heuristic if no API
key is available.
"""

from __future__ import annotations
from pathlib import Path
import os
import base64
import json
import logging

log = logging.getLogger(__name__)

_SCHEDULE_DISCOVERY_PROMPT = """You are looking at a structural construction drawing.
Does this page contain a MEMBER SCHEDULE - a table that lists steel members
with columns for mark, shape, length, and quantity?

Answer with ONLY a JSON object:
{"is_schedule": true, "confidence": 0.9, "schedule_type": "member|column|beam|joist|footing|anchor|none"}
"""


def _classify_page_via_haiku(image_path) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"is_schedule": False, "confidence": 0.0, "schedule_type": "none"}
    try:
        from anthropic import Anthropic
    except ImportError:
        return {"is_schedule": False, "confidence": 0.0, "schedule_type": "none"}
    client = Anthropic()
    b64 = base64.b64encode(open(image_path, "rb").read()).decode("ascii")
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                                                  "media_type": "image/png",
                                                  "data": b64}},
                    {"type": "text", "text": _SCHEDULE_DISCOVERY_PROMPT},
                ],
            }],
            temperature=0,
        )
        txt = (resp.content[0].text if resp.content else "{}").strip()
        if txt.startswith("```"):
            txt = txt.strip("`").lstrip("json").strip()
        return json.loads(txt)
    except Exception as e:
        log.warning(f"Haiku schedule classify failed: {e}")
        return {"is_schedule": False, "confidence": 0.0, "schedule_type": "none"}


def discover_schedule_pages(pdf_path, dpi=120, max_pages=30) -> list[int]:
    """Run Haiku per page to find schedule pages.

    Returns list of 0-indexed page numbers where Haiku thinks a schedule
    table is present.
    """
    try:
        import fitz
    except ImportError:
        return []
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    n = min(len(doc), max_pages)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    found: list[int] = []

    for i in range(n):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        tmp = Path(f"/tmp/_sched_disc_p{i:03d}.png")
        pix.save(tmp)
        try:
            r = _classify_page_via_haiku(tmp)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass
        if r.get("is_schedule") and float(r.get("confidence", 0)) >= 0.6:
            found.append(i)
    doc.close()
    return found


def combine_with_text_sweep(text_pages, vision_pages) -> list[int]:
    """Merge text-discovered + vision-discovered pages, deduped."""
    return sorted(set((text_pages or []) + (vision_pages or [])))
