"""
Node Cropper - Connection Intersection Detection and High-Res Crop Generation
==============================================================================
Phase 2 of the Sketchdeck parity roadmap (v3.6.1).

Identifies where structural members intersect (beam-to-column, beam-to-beam,
column-to-foundation joints) and generates high-resolution crops for the
detail_vision.py symbol classifier.

Uses pymupdf (fitz) for PDF crops. No cv2 dependency. Graceful degradation
if fitz is not installed (returns intersection data without crops).

Integration:
    - Input: member bounding boxes from tiled_inference or auto_process_drawing
    - Output: list of node dicts with coordinates, framing codes, and crop bytes
    - Consumers: detail_vision.py (symbol classifier), connection_check.py

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("node_cropper")


# ---- Data structures --------------------------------------------------------

@dataclass
class ConnectionNode:
    """A structural connection point where two or more members intersect."""
    node_id: str                           # e.g., "N001"
    framing_code: str                      # B2B, B2C, C2F, B2F, UNKNOWN
    center: tuple[float, float]            # (x, y) center in PDF points
    bbox: tuple[float, float, float, float]  # crop region (x0, y0, x1, y1)
    members: list[str]                     # IDs of connected members
    confidence: float = 0.0                # 0.0-1.0 based on overlap quality
    crop_bytes: bytes = b""                # PNG bytes of the high-res crop
    detail: dict = field(default_factory=dict)  # populated by detail_vision


# ---- Framing code classification --------------------------------------------

_BEAM_PREFIXES = {"W", "S", "HP", "M"}       # wide flange, S-shape, HP, M
_HSS_PREFIXES = {"HSS", "PIPE"}               # tubes
_ANGLE_PREFIXES = {"L", "2L"}                 # angles (bracing)
_TEE_PREFIXES = {"WT", "MT", "ST"}            # tees (bracing)
_CHANNEL_PREFIXES = {"C", "MC"}               # channels

# Columns are typically W shapes oriented vertically. We infer from the
# member's "type" field if available, or from shape + orientation hints.
_COLUMN_INDICATORS = {"column", "col", "vertical", "pier"}
_BEAM_INDICATORS = {"beam", "joist", "girder", "horizontal", "bm", "grd"}
_BRACE_INDICATORS = {"brace", "bracing", "diagonal", "kicker", "sag"}
_FOUNDATION_INDICATORS = {"base", "foundation", "footing", "baseplate", "bp"}


def _classify_member_role(member: dict) -> str:
    """Classify a member as BEAM, COLUMN, BRACE, or FOUNDATION from its metadata."""
    mtype = (member.get("type") or member.get("member_type") or "").lower()
    mark = (member.get("mark") or "").lower()
    shape = (member.get("shape") or member.get("normalized") or "").upper()

    # Check explicit type field first
    for indicator in _COLUMN_INDICATORS:
        if indicator in mtype or indicator in mark:
            return "COLUMN"
    for indicator in _BEAM_INDICATORS:
        if indicator in mtype or indicator in mark:
            return "BEAM"
    for indicator in _BRACE_INDICATORS:
        if indicator in mtype or indicator in mark:
            return "BRACE"
    for indicator in _FOUNDATION_INDICATORS:
        if indicator in mtype or indicator in mark:
            return "FOUNDATION"

    # Infer from mark prefix conventions
    if mark.startswith("c") and not mark.startswith("ch"):
        return "COLUMN"
    if mark.startswith("b") or mark.startswith("g"):
        return "BEAM"

    # Default: if shape family is angle/tee, likely brace. Otherwise beam.
    family = ""
    for pfx in sorted((_ANGLE_PREFIXES | _TEE_PREFIXES | _HSS_PREFIXES |
                        _BEAM_PREFIXES | _CHANNEL_PREFIXES), key=len, reverse=True):
        if shape.startswith(pfx):
            family = pfx
            break
    if family in _ANGLE_PREFIXES or family in _TEE_PREFIXES:
        return "BRACE"
    return "BEAM"


def _framing_code(role_a: str, role_b: str) -> str:
    """Derive the framing code from two member roles."""
    roles = {role_a, role_b}
    if "FOUNDATION" in roles:
        if "COLUMN" in roles:
            return "C2F"
        return "B2F"
    if roles == {"BEAM"}:
        return "B2B"
    if "COLUMN" in roles and "BEAM" in roles:
        return "B2C"
    if "COLUMN" in roles and "BRACE" in roles:
        return "BR2C"
    if "BEAM" in roles and "BRACE" in roles:
        return "BR2B"
    if roles == {"COLUMN"}:
        return "C2C"  # column splice
    return "UNKNOWN"


# ---- AABB intersection logic ------------------------------------------------

def _aabb_intersects(bbox1: tuple, bbox2: tuple, padding: float = 10.0) -> bool:
    """Check if two axis-aligned bounding boxes overlap (with structural padding).

    Padding accounts for the fact that structural members shown on drawings
    don't overlap pixel-perfectly at connection points. A 10-point pad
    (roughly 0.14 inches at 72 dpi) catches adjacent-but-not-overlapping members.
    """
    x0a, y0a, x1a, y1a = bbox1
    x0b, y0b, x1b, y1b = bbox2
    return not (
        x1a < x0b - padding or
        x0a > x1b + padding or
        y1a < y0b - padding or
        y0a > y1b + padding
    )


def _intersection_center(bbox1: tuple, bbox2: tuple) -> tuple[float, float]:
    """Compute the center of the overlapping region between two bboxes."""
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])

    # If they don't actually overlap, use midpoint between centers
    if x0 > x1 or y0 > y1:
        cx = (bbox1[0] + bbox1[2] + bbox2[0] + bbox2[2]) / 4
        cy = (bbox1[1] + bbox1[3] + bbox2[1] + bbox2[3]) / 4
        return (cx, cy)

    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _overlap_ratio(bbox1: tuple, bbox2: tuple) -> float:
    """Fraction of smaller bbox that overlaps with the larger."""
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])

    if x0 >= x1 or y0 >= y1:
        return 0.0

    overlap_area = (x1 - x0) * (y1 - y0)
    area1 = max(1.0, (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1]))
    area2 = max(1.0, (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1]))
    smaller = min(area1, area2)
    return overlap_area / smaller


# ---- Crop generation ---------------------------------------------------------

# Crop size in points (1 point = 1/72 inch). 600x600 pts = 8.33" square.
# At 600 DPI this yields a 5000x5000 pixel crop. Large enough for Gemini
# to read bolt patterns and weld symbols.
DEFAULT_CROP_SIZE = 400  # points (5.5" square - balance between detail and token cost)
DEFAULT_CROP_DPI = 600


def _extract_crop(pdf_path: str, page_num: int, center: tuple[float, float],
                  crop_size: float = DEFAULT_CROP_SIZE,
                  dpi: int = DEFAULT_CROP_DPI) -> bytes:
    """Generate a high-res PNG crop centered on a connection node.

    Uses pymupdf (fitz). Returns empty bytes if fitz is not installed.
    """
    try:
        import fitz
    except ImportError:
        log.warning("pymupdf (fitz) not installed. Returning empty crop.")
        return b""

    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            doc.close()
            return b""
        page = doc[page_num]

        cx, cy = center
        half = crop_size / 2
        clip = fitz.Rect(
            max(0, cx - half),
            max(0, cy - half),
            min(page.rect.width, cx + half),
            min(page.rect.height, cy + half),
        )

        pix = page.get_pixmap(dpi=dpi, clip=clip)
        png_bytes = pix.tobytes("png")
        doc.close()
        return png_bytes
    except Exception as e:
        log.error(f"Crop extraction failed: {e}")
        return b""


# ---- Main API ----------------------------------------------------------------

def find_connection_nodes(
    members: list[dict],
    pdf_path: str = "",
    page_num: int = 0,
    padding: float = 10.0,
    crop_size: float = DEFAULT_CROP_SIZE,
    crop_dpi: int = DEFAULT_CROP_DPI,
    generate_crops: bool = True,
) -> list[ConnectionNode]:
    """Identify connection nodes from member bounding boxes.

    Args:
        members: List of member dicts. Each must have at minimum:
            - id or mark (str): unique identifier
            - bbox (tuple/list of 4 floats): (x0, y0, x1, y1) in PDF points
            Optional:
            - type or member_type (str): "beam", "column", "brace", etc.
            - shape or normalized (str): AISC designation (e.g., "W14X22")
        pdf_path: Path to the source PDF (for crop generation)
        page_num: 0-based page number for crops
        padding: AABB padding in points
        crop_size: Crop region size in points
        crop_dpi: Crop resolution in DPI
        generate_crops: If False, skip crop generation (faster, for analysis only)

    Returns:
        List of ConnectionNode objects sorted by confidence (highest first).
    """
    nodes: list[ConnectionNode] = []
    node_idx = 0

    # Filter members that have bounding boxes
    boxed = []
    for m in members:
        bbox = m.get("bbox")
        if bbox and len(bbox) == 4:
            try:
                bbox = tuple(float(v) for v in bbox)
                boxed.append((m, bbox))
            except (TypeError, ValueError):
                continue

    if len(boxed) < 2:
        log.info(f"find_connection_nodes: {len(boxed)} members with bboxes. Need >= 2.")
        return nodes

    # Pairwise intersection check
    for i, (m1, bb1) in enumerate(boxed):
        for j in range(i + 1, len(boxed)):
            m2, bb2 = boxed[j]

            if not _aabb_intersects(bb1, bb2, padding):
                continue

            node_idx += 1
            center = _intersection_center(bb1, bb2)
            overlap = _overlap_ratio(bb1, bb2)

            role1 = _classify_member_role(m1)
            role2 = _classify_member_role(m2)
            code = _framing_code(role1, role2)

            # Confidence: higher overlap = more certain intersection
            conf = min(1.0, 0.5 + overlap)

            # Crop bbox
            half = crop_size / 2
            crop_bbox = (center[0] - half, center[1] - half,
                         center[0] + half, center[1] + half)

            crop = b""
            if generate_crops and pdf_path:
                crop = _extract_crop(pdf_path, page_num, center,
                                     crop_size, crop_dpi)

            mid1 = m1.get("id") or m1.get("mark") or f"m{i}"
            mid2 = m2.get("id") or m2.get("mark") or f"m{j}"

            node = ConnectionNode(
                node_id=f"N{node_idx:03d}",
                framing_code=code,
                center=center,
                bbox=crop_bbox,
                members=[str(mid1), str(mid2)],
                confidence=conf,
                crop_bytes=crop,
            )
            nodes.append(node)

    # Sort highest confidence first
    nodes.sort(key=lambda n: n.confidence, reverse=True)

    log.info(f"find_connection_nodes: {len(nodes)} nodes from {len(boxed)} members "
             f"({sum(1 for n in nodes if n.crop_bytes)} with crops)")
    return nodes


def nodes_to_dicts(nodes: list[ConnectionNode]) -> list[dict]:
    """Convert ConnectionNode list to JSON-serializable dicts.

    Excludes crop_bytes (binary). Use for API responses and storage.
    """
    return [
        {
            "node_id": n.node_id,
            "framing_code": n.framing_code,
            "center": list(n.center),
            "bbox": list(n.bbox),
            "members": n.members,
            "confidence": round(n.confidence, 3),
            "has_crop": bool(n.crop_bytes),
            "detail": n.detail,
        }
        for n in nodes
    ]
