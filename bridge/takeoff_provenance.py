"""Provenance-validation gate (plan item D1, advisory).

After a takeoff, this deterministic pass re-checks every canonical row:
does the tag string in the row's ``tag`` field actually appear in the
extracted vector-text layer of the sheet named in the row's ``drawing``
field? Rows that fail earn a relocation SUGGESTION when the tag appears
on another sheet, or a human-check flag when it appears nowhere.

ADVISORY AND READ-ONLY. This module never mutates a row, never sets or
changes a qty, weight, or rate, and never returns a go/no-go verdict.
Member weights stay in bridge/aisc_validator.py and rates in
bridge/bid_rates.py. Relocation is a suggestion only; auto-relocation
(a takeoff attribution change) is gated on Ivan's sign-off of the
relocation-versus-flag rules and on Owner promoting this gate to
blocking (decision log, docs/DRAWING-ANALYZER-IMPROVEMENT-PLAN-2026-07-02.md).

Inputs already exist in the pipeline: the drawing-analyzer skill's
split_and_extract.py writes one ``<stem>.txt`` vector-text file per
sheet, and bridge/takeoff_row.py rows carry ``tag`` and ``drawing``.

Method awareness: only text-claiming methods (vector_or_text_tag,
stated_schedule) are held to the strict check. A scaled-plan, vision, or
inferred row does not claim the vector-text layer as its source, so a
missing tag there is an informational note, never a strict failure.

Module-level only. Pure stdlib. PyInstaller-safe.
"""

from __future__ import annotations
import os
import re

from bridge.takeoff_row import (
    METHOD_VECTOR_OR_TAG, METHOD_STATED_SCHEDULE,
)

# Methods whose rows CLAIM the vector-text layer as their source. Only
# these are held to the strict provenance check.
TEXT_CLAIMING_METHODS = frozenset({
    METHOD_VECTOR_OR_TAG, METHOD_STATED_SCHEDULE,
})

# Finding types, in the reconcile_advisory house style.
FINDING_CONFIRMED_ELSEWHERE = "TAG_FOUND_ON_OTHER_SHEET"   # relocation suggestion
FINDING_UNSOURCED = "TAG_FOUND_NOWHERE"                     # human check
FINDING_UNKNOWN_SHEET = "SHEET_TEXT_MISSING"                # no text layer for the named sheet
FINDING_EMPTY_TAG = "EMPTY_TAG"                             # nothing to check
FINDING_INFO_ABSENT = "TAG_ABSENT_NONTEXT_METHOD"           # informational only

_PROV_DISCLAIMER = (
    "Advisory provenance check only. Verifies that each row's tag string "
    "appears in the extracted vector-text layer of the sheet the row cites. "
    "Does not set or change any price, quantity, weight, or rate, and does "
    "not relocate rows; relocation findings are suggestions for human "
    "review. Member weights come from bridge/aisc_validator.py and rates "
    "from bridge/bid_rates.py."
)


def load_sheet_texts(text_dir) -> dict:
    """Load per-sheet vector-text extracts from a directory of ``*.txt``
    files (the split_and_extract.py output layout). Returns a dict of
    sheet name (file stem) to text. Missing directory returns {}.
    Deterministic file read only; no parsing, no inference.
    """
    texts: dict = {}
    try:
        names = sorted(os.listdir(text_dir))
    except OSError:
        return texts
    for name in names:
        if not name.lower().endswith(".txt"):
            continue
        path = os.path.join(text_dir, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                texts[os.path.splitext(name)[0]] = fh.read()
        except OSError:
            continue
    return texts


def _tag_pattern(tag: str):
    """Compile a boundary-aware pattern for a literal tag.

    Alphanumeric boundaries on both sides so 'B1' never matches inside
    'B12' or 'AB1'. The tag itself is escaped verbatim; 'W12X26' matches
    only the full designation. Case-insensitive because sheet text case
    varies by CAD export.
    """
    return re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(tag) + r"(?![A-Za-z0-9])",
        re.IGNORECASE)


def _count_in(pattern, text: str) -> int:
    if not text:
        return 0
    return len(pattern.findall(text))


def _norm_sheet(name: str) -> str:
    """Normalize a sheet name for dict lookup: strip, uppercase, drop a
    trailing '.txt'/'.pdf' if a caller passed a filename. Identity
    normalization only."""
    s = str(name or "").strip()
    for ext in (".txt", ".pdf", ".png"):
        if s.lower().endswith(ext):
            s = s[: -len(ext)]
    return s.upper()


def check_provenance(rows, sheet_texts) -> dict:
    """ADVISORY provenance pass over canonical takeoff rows.

    Args:
        rows: list of canonical takeoff row dicts (bridge/takeoff_row.py
            shape). Read-only; never mutated.
        sheet_texts: dict of sheet name -> extracted vector text, as
            produced by load_sheet_texts() or built by the caller from a
            sheet index. Keys are matched case-insensitively.

    Returns:
        A plain advisory dict (the Bridge wrapper adds the _ok/_err
        envelope): advisory, generates_numbers (False), findings[...],
        summary{...} including a 'validated_counts' line of the form
        'confirmed N/M strict-checked rows', verdict (None), disclaimer.
    """
    texts = {_norm_sheet(k): (v or "") for k, v in (sheet_texts or {}).items()}
    findings: list = []
    n_rows = 0
    n_strict = 0
    n_confirmed = 0
    n_relocate = 0
    n_unsourced = 0
    n_unknown_sheet = 0
    n_info = 0

    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        n_rows += 1
        tag = str(row.get("tag") or "").strip()
        drawing = _norm_sheet(row.get("drawing"))
        method = str(row.get("method") or "")
        strict = method in TEXT_CLAIMING_METHODS

        if not tag:
            findings.append({
                "type": FINDING_EMPTY_TAG,
                "index": i,
                "drawing": drawing,
                "confidence": "high",
                "needs_judgment": True,
                "method": "row carries no tag string to check",
                "note": "No tag to verify. Row cannot be provenance-checked.",
            })
            continue

        pattern = _tag_pattern(tag)

        if drawing not in texts:
            if strict:
                n_strict += 1
                n_unknown_sheet += 1
                findings.append({
                    "type": FINDING_UNKNOWN_SHEET,
                    "index": i,
                    "tag": tag,
                    "drawing": drawing,
                    "confidence": "medium",
                    "needs_judgment": True,
                    "method": "no extracted text layer for the cited sheet",
                    "note": ("The cited sheet has no vector-text extract. "
                             "Raster sheet, outlined text, or a naming "
                             "mismatch. Verify by hand; never assume."),
                })
            continue

        hits_here = _count_in(pattern, texts[drawing])
        if hits_here > 0:
            if strict:
                n_strict += 1
                n_confirmed += 1
            continue

        # Tag not on the cited sheet. Where does it appear?
        elsewhere = sorted(
            s for s, t in texts.items()
            if s != drawing and _count_in(pattern, t) > 0)

        if strict:
            n_strict += 1
            if elsewhere:
                n_relocate += 1
                findings.append({
                    "type": FINDING_CONFIRMED_ELSEWHERE,
                    "index": i,
                    "tag": tag,
                    "drawing": drawing,
                    "suggested_drawings": elsewhere,
                    "confidence": "high",
                    "needs_judgment": True,
                    "method": ("tag absent from the cited sheet's text layer "
                               "but present on another sheet's"),
                    "note": ("Suggest relocating this row's drawing "
                             "attribution. Suggestion only; a human confirms "
                             "before any attribution change."),
                })
            else:
                n_unsourced += 1
                findings.append({
                    "type": FINDING_UNSOURCED,
                    "index": i,
                    "tag": tag,
                    "drawing": drawing,
                    "confidence": "high",
                    "needs_judgment": True,
                    "method": "tag absent from every extracted sheet text layer",
                    "note": ("Tag appears nowhere in the vector text. The row "
                             "claims a text-based method, so this is a "
                             "possible fabrication or OCR-less sheet. Human "
                             "check required before pricing."),
                })
        else:
            if not elsewhere:
                n_info += 1
                findings.append({
                    "type": FINDING_INFO_ABSENT,
                    "index": i,
                    "tag": tag,
                    "drawing": drawing,
                    "confidence": "low",
                    "needs_judgment": False,
                    "method": ("tag absent from the text layer; row method "
                               f"{method!r} does not claim the text layer"),
                    "note": ("Informational. Scaled-plan, vision, and "
                             "inferred rows are not held to the text check."),
                })

    summary = {
        "row_count": n_rows,
        "sheet_count": len(texts),
        "strict_checked": n_strict,
        "confirmed": n_confirmed,
        "relocation_suggestions": n_relocate,
        "unsourced": n_unsourced,
        "sheet_text_missing": n_unknown_sheet,
        "informational": n_info,
        "needs_judgment_count": sum(1 for f in findings if f.get("needs_judgment")),
        "validated_counts": f"confirmed {n_confirmed}/{n_strict} strict-checked rows",
    }

    return {
        "advisory": True,
        "generates_numbers": False,
        "findings": findings,
        "summary": summary,
        "verdict": None,
        "disclaimer": _PROV_DISCLAIMER,
    }
