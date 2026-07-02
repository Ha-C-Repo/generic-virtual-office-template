"""Piece ID generation and section validation.

Format: [PROJECT CODE]-[SECTION]-[SEQUENCE]   e.g. ICD-W14X90-001
Sequence auto-increments per (project, section).
"""

import csv
import os
import re

from . import config

_VALID_SECTIONS = None


def _load_sections() -> set:
    global _VALID_SECTIONS
    if _VALID_SECTIONS is None:
        _VALID_SECTIONS = set()
        path = config.resource_path(os.path.join("data", "aisc_sections.csv"))
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    _VALID_SECTIONS.add(normalize_section(row["shape"]))
        except Exception:
            pass  # validation degrades to format-only check
    return _VALID_SECTIONS


def normalize_section(section: str) -> str:
    """W14x90 -> W14X90. Strip spaces, uppercase, unify the x separator."""
    s = section.strip().upper().replace(" ", "")
    return s


SECTION_RE = re.compile(
    r"^(W|HP|HSS|PIPE|PL|C|MC|L|WT|MT|ST|S|M|2L)[0-9]"
)

# A complete SJI joist or joist-girder designation: depth + series + chord/size.
#   K / KCS open-web K-series carry a chord number (30K7, 22K9, 30KCS4)
#   LH / DLH / SLH longspan and deep-longspan (24LH06, 52DLH15)
#   G joist girders carry a space count and an optional N-load-K (60G8, 48G8N10K,
#     40G8N5.5K)
# The trailing digit after the series is REQUIRED. It is what separates a real
# mark from a bare series name (30K, 60G) or a common BOL token (50K capacity, 5G
# grid line, 250K budget, 600G coating), which previously mis-detected as joists.
# Bare series like "30K and 20K series" are scope language, found by
# bol_import.detect_scope, not treated as piece marks. Validated by format only;
# the app never invents or weighs a joist (weights stay in
# bridge/aisc_validator.py in the Virtual Office).
JOIST_RE = re.compile(r"^\d{1,3}(?:(?:KCS|SLH|DLH|LH|K)\d+|G\d+(?:N[\d.]+K)?)$")


def is_joist_section(section: str) -> bool:
    return bool(JOIST_RE.match(normalize_section(section)))


def traveler_type_for_section(section: str) -> str:
    """Pick the traveler variant from the section/mark at receiving. Joist marks
    get the SJI joist traveler; everything else gets the structural traveler."""
    return "JOIST" if is_joist_section(section) else "STRUCTURAL"


def section_format_ok(section: str) -> bool:
    """A section is acceptable if it is a recognized structural shape OR an SJI
    joist designation. Joist marks (30KCS4, 24LH06, 60G) do not match the
    structural pattern, so they are validated by the joist format here."""
    s = normalize_section(section)
    return bool(SECTION_RE.match(s)) or is_joist_section(s)


def section_in_aisc(section: str) -> bool:
    """True if the section appears in the bundled AISC list.
    A miss is a WARNING, not a block - the bundled list is not the full
    2,299-shape database. Source of truth for weights stays
    bridge/aisc_validator.py in the Virtual Office."""
    return normalize_section(section) in _load_sections()


def id_section_token(section: str) -> str:
    """Section as it appears inside a piece ID: no separators that break the ID."""
    return normalize_section(section).replace("-", "")


def next_piece_id(conn, project_code: str, section: str) -> str:
    token = id_section_token(section)
    prefix = f"{project_code.upper()}-{token}-"
    row = conn.execute(
        "SELECT piece_id FROM pieces WHERE piece_id LIKE ? ORDER BY piece_id DESC LIMIT 1",
        (prefix + "%",)).fetchone()
    seq = 1
    if row:
        try:
            seq = int(row["piece_id"].rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:03d}"


def qr_payload(piece_id: str, project_number: str, heat: str, received_date: str) -> str:
    """Full traceability encode (Owner-approved 2026-06-10):
    {piece_id}|{project_no}|{heat_no}|{received_date}"""
    clean = lambda v: (v or "").replace("|", "/").strip()
    return "|".join([clean(piece_id), clean(project_number), clean(heat), clean(received_date)])
