"""
Local-First Document Intake
============================
Extract everything possible WITHOUT calling an AI. AI vision is a last resort.

Order of operations for a PDF:
  1. pdfplumber → text layer + tables (no AI)
  2. PyMuPDF    → embedded images, fonts, metadata (no AI)
  3. tesseract  → OCR for any rasterized page (no AI)
  4. AI vision  → ONLY if all of the above failed for that page

Output: FactsManifest - every extracted value tagged with (source, page, line).
This is the source of truth that the verifier checks AI responses against.
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Fact:
    """A single extracted value with provenance - never an AI guess."""
    key:        str            # e.g. "tonnage_estimate", "due_date", "owner_name"
    value:      Any
    source:     str            # "pdfplumber" | "pymupdf" | "tesseract" | "ai_vision"
    page:       int | None
    line:       int | None
    confidence: float          # 0.0-1.0
    raw_text:   str = ""       # the original substring this was pulled from


@dataclass
class FactsManifest:
    """The full local-extraction record for one document."""
    document_path:       str
    document_sha256:     str
    page_count:          int
    has_text_layer:      bool
    has_tables:          bool
    has_images:          bool
    needs_ai_vision:     bool       # True only if local extraction was insufficient
    facts:               list[Fact] = field(default_factory=list)
    raw_text_by_page:    dict[int, str] = field(default_factory=dict)
    extraction_log:      list[str] = field(default_factory=list)

    def find(self, key: str) -> Fact | None:
        """Look up an extracted fact by key."""
        for f in self.facts:
            if f.key == key:
                return f
        return None

    def has_provenance(self, value: Any, tolerance: float = 0.001) -> Fact | None:
        """Check whether a numeric value matches any extracted fact (within tolerance).

        This is the workhorse for the verifier - every AI-claimed number must
        either exactly match a Fact or be a derivation of Facts that we can
        recompute locally.
        """
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            # String match - exact only
            for f in self.facts:
                if str(f.value).strip().lower() == str(value).strip().lower():
                    return f
            return None
        for f in self.facts:
            try:
                if abs(float(f.value) - numeric) <= tolerance * max(1.0, abs(numeric)):
                    return f
            except (TypeError, ValueError):
                continue
        return None


# ── Local extraction primitives ───────────────────────────────────────

_NUMERIC_FIELD_PATTERNS = {
    # Bid/RFQ pattern matches with high-confidence anchors
    "tonnage_estimate":  r"(?:approx(?:imately)?\s+)?(\d{1,4}(?:,\d{3})*(?:\.\d+)?)\s*(?:tons?|st|short\s*tons?)\b",
    "square_footage":    r"(\d{1,3}(?:,\d{3})*)\s*(?:sq\.?\s*ft\.?|square\s+feet|s\.?f\.?)\b",
    "bid_due_date":      r"(?:bids?\s+due|due\s+date|submit\s+by)[:\s]+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
    "contract_value":    r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:M|million)?",
    "duration_weeks":    r"(\d{1,2})\s*(?:weeks?|wks?)\b",
}


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_with_pdfplumber(path: Path, manifest: FactsManifest) -> int:
    """Returns number of pages with text successfully extracted."""
    try:
        import pdfplumber
    except ImportError:
        manifest.extraction_log.append("pdfplumber not available - skipping text layer extraction")
        return 0

    pages_with_text = 0
    try:
        with pdfplumber.open(path) as pdf:
            manifest.page_count = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                if text.strip():
                    pages_with_text += 1
                    manifest.raw_text_by_page[i] = text
                    manifest.has_text_layer = True

                    # Extract structured facts via regex
                    for key, pattern in _NUMERIC_FIELD_PATTERNS.items():
                        for m in re.finditer(pattern, text, re.IGNORECASE):
                            raw = m.group(1).replace(",", "")
                            try:
                                value: Any = float(raw)
                                if value.is_integer():
                                    value = int(value)
                            except ValueError:
                                value = m.group(1).strip()
                            line_num = text[:m.start()].count("\n") + 1
                            manifest.facts.append(Fact(
                                key=key, value=value, source="pdfplumber",
                                page=i, line=line_num, confidence=0.95,
                                raw_text=m.group(0),
                            ))

                # Tables
                tables = page.extract_tables() or []
                if tables:
                    manifest.has_tables = True
                    for ti, tbl in enumerate(tables):
                        manifest.facts.append(Fact(
                            key=f"table_p{i}_{ti}", value=tbl, source="pdfplumber",
                            page=i, line=None, confidence=0.90,
                            raw_text=f"table with {len(tbl)} rows × {len(tbl[0]) if tbl else 0} cols",
                        ))
        manifest.extraction_log.append(f"pdfplumber: extracted {pages_with_text}/{manifest.page_count} pages")
    except Exception as e:
        manifest.extraction_log.append(f"pdfplumber error: {type(e).__name__}: {e}")
    return pages_with_text


def _extract_with_pymupdf(path: Path, manifest: FactsManifest) -> int:
    """Returns number of embedded images discovered."""
    try:
        import fitz   # PyMuPDF
    except ImportError:
        manifest.extraction_log.append("PyMuPDF not available - skipping image enumeration")
        return 0

    image_count = 0
    try:
        doc = fitz.open(str(path))
        for i, page in enumerate(doc, start=1):
            images = page.get_images(full=True)
            if images:
                manifest.has_images = True
                image_count += len(images)
        doc.close()
        manifest.extraction_log.append(f"pymupdf: found {image_count} embedded images")
    except Exception as e:
        manifest.extraction_log.append(f"pymupdf error: {type(e).__name__}: {e}")
    return image_count


def _ocr_pages_without_text(path: Path, manifest: FactsManifest) -> int:
    """Last-resort tesseract OCR for pages with no text layer. Returns pages OCR'd."""
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        manifest.extraction_log.append("tesseract chain unavailable - skipping OCR")
        return 0

    ocr_count = 0
    try:
        doc = fitz.open(str(path))
        for i, page in enumerate(doc, start=1):
            if i in manifest.raw_text_by_page:
                continue   # already have text
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img) or ""
            if text.strip():
                manifest.raw_text_by_page[i] = text
                ocr_count += 1
        doc.close()
        manifest.extraction_log.append(f"tesseract: OCR'd {ocr_count} additional pages")
    except Exception as e:
        manifest.extraction_log.append(f"tesseract error: {type(e).__name__}: {e}")
    return ocr_count


def ingest_document(path: str | Path) -> FactsManifest:
    """Local-first extraction. AI vision is only flagged as needed if all else fails."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Document not found: {p}")

    manifest = FactsManifest(
        document_path=str(p),
        document_sha256=_hash_file(p),
        page_count=0,
        has_text_layer=False,
        has_tables=False,
        has_images=False,
        needs_ai_vision=False,
    )

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        text_pages = _extract_with_pdfplumber(p, manifest)
        _extract_with_pymupdf(p, manifest)
        if text_pages < manifest.page_count:
            ocr_count = _ocr_pages_without_text(p, manifest)
            if (text_pages + ocr_count) < manifest.page_count:
                manifest.needs_ai_vision = True
                manifest.extraction_log.append(
                    f"AI vision needed: {manifest.page_count - text_pages - ocr_count} pages still unread"
                )
    elif suffix in (".txt", ".md"):
        text = p.read_text(encoding="utf-8", errors="ignore")
        manifest.page_count = 1
        manifest.has_text_layer = True
        manifest.raw_text_by_page[1] = text
        # Regex extraction on plain text
        for key, pattern in _NUMERIC_FIELD_PATTERNS.items():
            for m in re.finditer(pattern, text, re.IGNORECASE):
                raw = m.group(1).replace(",", "")
                try:
                    value: Any = float(raw)
                    if value.is_integer(): value = int(value)
                except ValueError:
                    value = m.group(1).strip()
                line_num = text[:m.start()].count("\n") + 1
                manifest.facts.append(Fact(
                    key=key, value=value, source="text_file",
                    page=1, line=line_num, confidence=0.95,
                    raw_text=m.group(0),
                ))
        manifest.extraction_log.append("plain text file: regex-extracted facts")
    else:
        manifest.extraction_log.append(f"unsupported file type: {suffix}")

    return manifest
