"""Visual drawing diff / ghost overlay (Phase 23, v5.5.0).

Generates a visual diff between two PDF drawing revisions.
Rev 0 in red, Rev 1 in green, unchanged in gray. Owner sees
at a glance exactly what moved, without reading markup.

Phase 5 extension: member-level semantic tags and machine-readable
diff manifest (JSON) written alongside the overlay PNG.

Tag format: "Member added: W14X82 at C-3, Rev 1"
            "Member removed: HSS6x6 at B-2"

Manifest written to same directory as output PNG with _manifest.json suffix.
Manifest is consumed by variation_prover as primary evidence source.

Uses OpenCV (already installed) and pymupdf (already installed).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import fitz  # pymupdf
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ── Member-level semantic tagging ─────────────────────────────────────────────

# AISC section prefix patterns for tagging. Ordered longest-prefix first
# so W14 matches before W1.
_SECTION_PATTERNS = re.compile(
    r"\b(W\d+X\d+|HSS\d+[Xx]\d+[Xx]\d+|HSS\d+[Xx]\d+|"
    r"MC?\d+X\d+|L\d+[Xx]\d+[Xx]\d+|C\d+X\d+|"
    r"WT\d+X\d+|ST\d+X\d+|MT\d+X\d+|"
    r"HP\d+X\d+|S\d+X\d+|PL\d+[Xx]\d+)\b",
    re.IGNORECASE,
)

# Grid label pattern: letter + digit (e.g. A-3, B-12, C.3)
_GRID_PATTERN = re.compile(r"\b([A-Z][-.]?\d+)\b")


def _extract_text_from_page(pdf_path: str, page_num: int = 0) -> str:
    """Extract plain text from a PDF page for member detection."""
    if not HAS_FITZ:
        return ""
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            return ""
        text = doc[page_num].get_text()
        doc.close()
        return text
    except Exception as e:
        log.warning("_extract_text_from_page failed: %s", e)
        return ""


def _extract_members(text: str) -> list[str]:
    """Return unique AISC section designations found in text, normalized to upper."""
    if not text:
        return []
    return sorted({m.upper() for m in _SECTION_PATTERNS.findall(text)})


def _extract_grids(text: str) -> list[str]:
    """Return grid label tokens found in text."""
    if not text:
        return []
    return sorted({g.upper() for g in _GRID_PATTERN.findall(text)})


def _tag_member_changes(
    text0: str,
    text1: str,
    rev0_label: str = "Rev 0",
    rev1_label: str = "Rev 1",
) -> dict:
    """Compute member-level add/remove tags from two pages' text content.

    Returns:
        {
            "added": list of str,   e.g. ["Member added: W14X82 at C-3, Rev 1"]
            "removed": list of str, e.g. ["Member removed: HSS6x6 at B-2"]
            "unchanged": list of str,
            "members_rev0": list of str,
            "members_rev1": list of str,
        }
    """
    m0 = set(_extract_members(text0))
    m1 = set(_extract_members(text1))
    g0 = _extract_grids(text0)
    g1 = _extract_grids(text1)

    added_shapes = m1 - m0
    removed_shapes = m0 - m1
    unchanged_shapes = m0 & m1

    # Pair each added/removed shape with a grid label hint if available
    def _grid_hint(grids: list[str]) -> str:
        if grids:
            return f" at {grids[0]}"
        return ""

    added_tags = [
        f"Member added: {s}{_grid_hint(g1)}, {rev1_label}"
        for s in sorted(added_shapes)
    ]
    removed_tags = [
        f"Member removed: {s}{_grid_hint(g0)}"
        for s in sorted(removed_shapes)
    ]

    return {
        "added": added_tags,
        "removed": removed_tags,
        "unchanged": sorted(unchanged_shapes),
        "members_rev0": sorted(m0),
        "members_rev1": sorted(m1),
    }


def write_diff_manifest(
    output_png_path: str | Path,
    ghost_result: dict,
    tags: dict,
    rev0_pdf: str,
    rev1_pdf: str,
    page_num: int,
) -> str:
    """Write machine-readable diff manifest JSON alongside the overlay PNG.

    Manifest path: same directory, same stem, suffix _manifest.json.
    Returns the manifest path, or "" if write fails.
    """
    png_path = Path(output_png_path)
    manifest_path = png_path.parent / (png_path.stem + "_manifest.json")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rev0_pdf": str(rev0_pdf),
        "rev1_pdf": str(rev1_pdf),
        "page_num": page_num,
        "overlay_png": str(png_path),
        "change_pct": ghost_result.get("change_pct", 0.0),
        "changed_pixels": ghost_result.get("changed_pixels", 0),
        "total_pixels": ghost_result.get("total_pixels", 0),
        "dimensions": ghost_result.get("dimensions", {}),
        "member_tags": tags,
    }

    try:
        manifest_path.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        log.info("write_diff_manifest: wrote %s", manifest_path)
        return str(manifest_path)
    except Exception as e:
        log.error("write_diff_manifest failed: %s", e)
        return ""


def _rasterize_page(pdf_path: str, page_num: int = 0,
                     dpi: int = 150) -> "np.ndarray | None":
    """Rasterize a PDF page to a numpy array."""
    if not HAS_FITZ:
        return None
    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        return None
    page = doc[page_num]
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3)
    doc.close()
    return img


def ghost_overlay(
    rev0_pdf: str,
    rev1_pdf: str,
    page_num: int = 0,
    dpi: int = 150,
    output_path: str | Path | None = None,
) -> dict:
    """Generate visual diff overlay of two drawing revisions.

    Args:
        rev0_pdf: Path to Rev 0 PDF.
        rev1_pdf: Path to Rev 1 PDF.
        page_num: Page index (0-based).
        dpi: Rasterization DPI.
        output_path: Write overlay PNG here if provided.

    Returns:
        {"success": bool, "output_path": str, "change_pct": float, ...}
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.58; needs manual audit)
    if not HAS_CV2 or not HAS_FITZ:
        missing = []
        if not HAS_CV2:
            missing.append("cv2")
        if not HAS_FITZ:
            missing.append("pymupdf")
        return {
            "success": False,
            "error": f"requires: {', '.join(missing)}",
            "output_path": "",
            "change_pct": 0.0,
        }

    img0 = _rasterize_page(rev0_pdf, page_num, dpi)
    img1 = _rasterize_page(rev1_pdf, page_num, dpi)

    if img0 is None or img1 is None:
        return {
            "success": False,
            "error": "could not rasterize one or both PDFs",
            "output_path": "",
            "change_pct": 0.0,
        }

    # Resize to match if dimensions differ
    h0, w0 = img0.shape[:2]
    h1, w1 = img1.shape[:2]
    if (h0, w0) != (h1, w1):
        img1 = cv2.resize(img1, (w0, h0))

    # Convert to grayscale for diff
    gray0 = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)

    # Compute absolute difference
    diff = cv2.absdiff(gray0, gray1)
    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

    # Change percentage
    total_pixels = thresh.shape[0] * thresh.shape[1]
    changed_pixels = int(np.count_nonzero(thresh))
    change_pct = round(changed_pixels / max(total_pixels, 1) * 100, 2)

    # Build color overlay
    # Gray = unchanged, Red = removed (in rev0 only), Green = added (in rev1 only)
    overlay = np.full_like(img0, 200, dtype=np.uint8)  # light gray base

    # Where changes exist, blend rev0 as red and rev1 as green
    mask = thresh > 0
    overlay[mask, 0] = np.clip(img0[mask, 0].astype(int) // 2, 0, 255)  # B
    overlay[mask, 1] = np.clip(img1[mask, 1].astype(int), 0, 255)       # G (added)
    overlay[mask, 2] = np.clip(img0[mask, 2].astype(int), 0, 255)       # R (removed)

    # Where no changes, show original in desaturated gray
    no_change = ~mask
    overlay[no_change] = cv2.cvtColor(gray0, cv2.COLOR_GRAY2BGR)[no_change]

    out_path = ""
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(p), overlay)
        out_path = str(p)

    base_result = {
        "success": True,
        "output_path": out_path,
        "change_pct": change_pct,
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "dimensions": {"width": w0, "height": h0},
        "summary": f"Page {page_num + 1}: {change_pct}% of pixels changed "
                   f"between revisions.",
    }

    # Phase 5: member-level semantic tags from text layers
    text0 = _extract_text_from_page(rev0_pdf, page_num)
    text1 = _extract_text_from_page(rev1_pdf, page_num)
    tags = _tag_member_changes(text0, text1)
    base_result["member_tags"] = tags

    # Write manifest JSON alongside PNG (only if PNG was written)
    manifest_path = ""
    if out_path:
        manifest_path = write_diff_manifest(
            out_path, base_result, tags, rev0_pdf, rev1_pdf, page_num
        )
    base_result["manifest_path"] = manifest_path

    return base_result
