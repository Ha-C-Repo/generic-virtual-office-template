"""BOL PDF import. pdfplumber text extraction + steel-line parsing.

Every parse result goes to a human review grid before commit (Operating Rule:
verify, do not generate). Each line carries a confidence tag.

The line parser is split out as parse_lines(text_lines) so it can be tested
against synthetic text without a PDF. extract_lines() and extract_scope() open the
PDF and call it.
"""

import re

from . import piece_ids

SECTION_PAT = re.compile(
    r"\b((?:W|HP|S|M)\s?\d{1,2}\s?[xX]\s?\d{1,3}(?:\.\d)?"
    r"|HSS\s?\d{1,2}(?:[-.]\d+)?\s?[xX]\s?\d{1,2}(?:[-.]\d+)?(?:\s?[xX]\s?[\d/.]+)?"
    r"|(?:C|MC)\s?\d{1,2}\s?[xX]\s?[\d.]+"
    r"|L\s?\d{1,2}\s?[xX]\s?\d{1,2}\s?[xX]\s?[\d/]+"
    r"|(?:WT|MT|ST)\s?\d{1,2}(?:\.\d)?\s?[xX]\s?[\d.]+"
    r"|PIPE\s?\d+(?:\.\d+)?"
    r")\b")
# Complete SJI joist / joist-girder marks searched within a line (30K7, 30KCS4,
# 24LH06, 52DLH15, 60G8, 48G8N10K). The chord digit after the series is required,
# so bare series and common tokens (50K, 5G, 250K, 600G) are not mis-detected.
# Each hit is confirmed with piece_ids.is_joist_section for one source of truth.
# Bare-series scope mentions (a proposal saying "30K and 20K series") are not
# per-piece marks; package scope is detected separately by detect_scope.
JOIST_PAT = re.compile(r"\b\d{1,3}(?:(?:KCS|SLH|DLH|LH|K)\d+|G\d+(?:N[\d.]+K)?)\b")
QTY_PAT = re.compile(r"\b(?:QTY[:\s]*)?(\d{1,4})\s*(?:PCS?|EA|EACH)?\b", re.I)
HEAT_PAT = re.compile(r"\b(?:HEAT|HT)[#:\s]*([A-Z0-9-]{4,15})\b", re.I)
# CSI MasterFormat codes (e.g. 05 21 00) carry small numbers that are not
# quantities; strip them before reading qty so a scope line does not mis-tag.
CSI_PAT = re.compile(r"\b\d{2}\s+\d{2}\s+\d{2}\b")


def _line_item(n, section, kind, raw, qty_text):
    """Build one parsed line with a confidence tag. qty is read from qty_text (the
    line with the section token and CSI codes removed, so their digits do not read
    as a quantity); heat is read from the raw line. high needs both qty and heat;
    medium has a qty; low has neither (typical of a scope proposal, where the
    inspector enters qty by hand)."""
    section = re.sub(r"\s+", "", section).upper()
    hm = HEAT_PAT.search(raw)
    heat = hm.group(1) if hm else ""
    qty, qconf = 0, "low"
    qm = QTY_PAT.search(qty_text)
    if qm:
        v = int(qm.group(1))
        if 1 <= v <= 2000:
            qty, qconf = v, "medium"
    confidence = "high" if (qty and heat) else qconf
    return {"line": n, "section": section, "kind": kind, "qty": qty,
            "heat": heat, "confidence": confidence, "raw": raw.strip()}


def _qty_text(raw, start, end):
    """Line text with the matched section span and any CSI codes blanked, so their
    digits are not read as a quantity."""
    return CSI_PAT.sub(" ", raw[:start] + " " + raw[end:])


def parse_lines(text_lines):
    """Parse BOL text lines into review items. Structural shapes are matched first
    (one per line, as a real shipper BOL reads); a line with no structural shape is
    scanned for SJI joist marks, each emitted as its own joist line. Returns a list
    of dicts: {line, section, kind, qty, heat, confidence, raw}."""
    items, n = [], 0
    for raw in text_lines:
        m = SECTION_PAT.search(raw)
        if m:
            n += 1
            items.append(_line_item(n, m.group(1), "structural", raw,
                                    _qty_text(raw, m.start(), m.end())))
            continue
        seen = set()
        for jm in JOIST_PAT.finditer(raw):
            mark = piece_ids.normalize_section(jm.group(0))
            if mark in seen or not piece_ids.is_joist_section(mark):
                continue
            seen.add(mark)
            n += 1
            items.append(_line_item(n, mark, "joist", raw,
                                    _qty_text(raw, jm.start(), jm.end())))
    return items


def detect_scope(text):
    """Coarse scope flags from the package text, by CSI code or keyword. Used to
    confirm a package carries the joist, deck, and anchor scope even when it is a
    scope/tonnage proposal rather than a per-piece schedule."""
    t = (text or "").upper()
    return {
        "structural": "05 12 00" in t or "STRUCTURAL STEEL" in t,
        "joists": "05 21 00" in t or "JOIST" in t,
        "deck": "05 31 00" in t or "DECK" in t,
        "anchors": "05 50 00" in t or "ANCHOR" in t or "F1554" in t,
    }


def _pdf_text_lines(pdf_path):
    import pdfplumber
    text_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text_lines.extend(t.splitlines())
    if not any(l.strip() for l in text_lines):
        raise RuntimeError(
            "No text layer in this PDF (scanned image). Use manual entry.")
    return text_lines


def extract_lines(pdf_path):
    """Returns list of line dicts. Raises RuntimeError with a clear message when no
    text layer exists (scanned BOL) so the UI can fall back to the manual grid."""
    return parse_lines(_pdf_text_lines(pdf_path))


def extract_scope(pdf_path):
    """Scope flags for a package PDF (joists/deck/anchors/structural)."""
    return detect_scope("\n".join(_pdf_text_lines(pdf_path)))
