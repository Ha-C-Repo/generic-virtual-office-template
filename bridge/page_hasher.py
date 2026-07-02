"""
Your Company Virtual Office - Drawing Page Hash Engine
=====================================================
When a revised drawing set arrives, hash each page and compare
against the previous version. Only re-process pages that changed.

Cost savings: A 60-page drawing set where 8 pages changed means
52 pages skip Gemini API calls entirely. At ~$0.07/page for
300 DPI vision processing, that's $3.64 saved per revision.

Usage:
    from bridge.page_hasher import hash_drawing_set, compare_revisions
    
    # First time: hash all pages
    hashes = hash_drawing_set("path/to/drawings.pdf")
    
    # Revision arrives: find what changed
    changes = compare_revisions("path/to/rev1.pdf", "path/to/rev2.pdf")
    # {"changed_pages": [3, 7, 14], "unchanged_pages": [1,2,4,5,...]}
"""

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def hash_drawing_set(pdf_path: str, dpi: int = 150) -> dict:
    """Hash each page of a PDF drawing set.

    Uses 150 DPI rasterization for hashing (fast, sufficient for
    change detection). Analysis uses 300 DPI separately.

    Returns:
      {
        file: str,
        page_count: int,
        pages: [{page_num, hash, sheet_id}],
        set_hash: str (hash of all page hashes combined),
      }
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.67; needs manual audit)
    path = Path(pdf_path)
    # v3.5.10 Bug #1: tighten validation. path.exists() returns True for
    # /dev/null (a character device) and other non-regular files, which
    # then crash inside fitz.open with FileDataError. Use is_file() plus
    # a PDF magic-byte check so the dispatcher returns a clean error
    # instead of a Python exception.
    if not path.is_file():
        return {"ok": False, "error": f"Not a regular file: {pdf_path}"}
    try:
        with open(path, "rb") as _fh:
            magic = _fh.read(5)
    except OSError as _e:
        return {"ok": False, "error": f"Cannot read file: {pdf_path} ({_e})"}
    if not magic.startswith(b"%PDF-"):
        return {"ok": False, "error": f"Not a PDF (bad magic bytes): {pdf_path}"}

    pages = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))

        for i in range(len(doc)):
            page = doc[i]
            # Rasterize at classification DPI
            pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
            page_bytes = pix.tobytes()
            page_hash = hashlib.sha256(page_bytes).hexdigest()

            # Try to extract sheet ID from text
            text = page.get_text()
            sheet_id = _extract_sheet_id(text)

            pages.append({
                "page_num": i + 1,
                "hash": page_hash,
                "sheet_id": sheet_id,
            })

        doc.close()

    except ImportError:
        # Fallback: hash raw PDF page content (less precise but works)
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    page_hash = hashlib.sha256(text.encode()).hexdigest()
                    sheet_id = _extract_sheet_id(text)
                    pages.append({
                        "page_num": i + 1,
                        "hash": page_hash,
                        "sheet_id": sheet_id,
                    })
        except Exception as e:
            return {"ok": False, "error": f"Cannot hash PDF: {e}"}

    # Combined set hash
    combined = "".join(p["hash"] for p in pages)
    set_hash = hashlib.sha256(combined.encode()).hexdigest()

    # Store in database
    _store_hashes(str(path), pages, set_hash)

    return {
        "ok": True,
        "file": str(path),
        "page_count": len(pages),
        "pages": pages,
        "set_hash": set_hash,
    }


def compare_revisions(old_pdf: str, new_pdf: str,
                      dpi: int = 150) -> dict:
    """Compare two PDF drawing sets page-by-page.

    Returns which pages changed, which are new, and which were removed.
    Only changed/new pages need to be re-processed through vision AI.
    """
    old_hashes = hash_drawing_set(old_pdf, dpi)
    new_hashes = hash_drawing_set(new_pdf, dpi)

    if "error" in old_hashes:
        return old_hashes
    if "error" in new_hashes:
        return new_hashes

    # Build lookup by sheet_id first, then by page_num
    old_by_sheet = {}
    old_by_page = {}
    for p in old_hashes["pages"]:
        if p["sheet_id"]:
            old_by_sheet[p["sheet_id"]] = p
        old_by_page[p["page_num"]] = p

    changed = []
    unchanged = []
    added = []

    for p in new_hashes["pages"]:
        # Try matching by sheet_id first
        old_page = None
        if p["sheet_id"] and p["sheet_id"] in old_by_sheet:
            old_page = old_by_sheet[p["sheet_id"]]
        elif p["page_num"] in old_by_page:
            old_page = old_by_page[p["page_num"]]

        if old_page is None:
            added.append(p["page_num"])
        elif p["hash"] != old_page["hash"]:
            changed.append({
                "page_num": p["page_num"],
                "sheet_id": p["sheet_id"],
                "old_hash": old_page["hash"][:12],
                "new_hash": p["hash"][:12],
            })
        else:
            unchanged.append(p["page_num"])

    # Detect removed pages
    new_sheets = {p["sheet_id"] for p in new_hashes["pages"] if p["sheet_id"]}
    removed = []
    for p in old_hashes["pages"]:
        if p["sheet_id"] and p["sheet_id"] not in new_sheets:
            removed.append({"page_num": p["page_num"], "sheet_id": p["sheet_id"]})

    # Cost estimate
    pages_to_process = len(changed) + len(added)
    pages_skipped = len(unchanged)
    cost_per_page = 0.07  # approximate Gemini 300 DPI cost
    savings = pages_skipped * cost_per_page

    return {
        "ok": True,
        "old_file": old_pdf,
        "new_file": new_pdf,
        "changed_pages": changed,
        "unchanged_pages": unchanged,
        "added_pages": added,
        "removed_pages": removed,
        "summary": {
            "total_new_pages": new_hashes["page_count"],
            "pages_changed": len(changed),
            "pages_added": len(added),
            "pages_removed": len(removed),
            "pages_unchanged": len(unchanged),
            "pages_to_process": pages_to_process,
            "pages_skipped": pages_skipped,
            "estimated_savings": f"${savings:.2f}",
        },
    }


def _extract_sheet_id(text: str) -> Optional[str]:
    """Extract drawing sheet ID from page text.

    Looks for patterns like "S-001", "S-101", "S1.1", "A-201", etc.
    """
    import re
    # Standard patterns: S-001, S-101, A-201, etc.
    # v6.1.1 fix: restored \d{1,3} (v3.5.12 had \d{1,2} which blocked 3-digit sheets).
    # The \b word boundary prevents the original MA1234 false positive.
    m = re.search(r'\b([SAFME])-?(\d{1,3}(?:\.\d{1,2})?)\b', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # "SHEET 3 OF 12" pattern
    m = re.search(r'SHEET\s+(\d+)\s+OF\s+\d+', text, re.IGNORECASE)
    if m:
        return f"SHEET-{m.group(1)}"

    return None


def _store_hashes(filepath: str, pages: list, set_hash: str):
    """Store page hashes in SQLite for future comparisons."""
    db_path = Path(__file__).parent.parent / "data" / "page_hashes.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS drawing_hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT, page_num INTEGER, sheet_id TEXT,
            page_hash TEXT, set_hash TEXT, created_at TEXT
        )""")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for p in pages:
            conn.execute(
                "INSERT INTO drawing_hashes VALUES (NULL,?,?,?,?,?,?)",
                (filepath, p["page_num"], p["sheet_id"],
                 p["hash"], set_hash, now)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning(f"Could not store page hashes: {e}")
