"""F13: Drawing tagger - auto-markup a structural PDF with detected members.

LIFT/Sketchdeck-parity layer for Cowork. Given a list of detected
members (each with a bounding box and a Subject string), this writes
native PDF annotations that Bluebeam Revu picks up in its Markups List
without any import step.

Annotation strategy:
- Each beam/profile member: rectangle annotation tinted by family
  (W = red, HSS = blue, C = orange, L = green, K = teal, plate = grey).
- The Subject of the annotation is set to the AISC designation (e.g.
  'W12X26 BEAM'). This is exactly the value Cowork's bluebeam_import.py
  maps back, so the round-trip is byte-stable.
- Comments / Content carry the mark, length, and confidence.
- A second layer of pale-yellow rectangles shows LOW confidence
  detections (< 0.7) so the estimator can verify those first.

Coordinates are PDF page space (points, 1pt = 1/72 in). Caller supplies
a `scale_ft_per_pt` to convert pixel bboxes into structural lengths
when needed.
"""

from __future__ import annotations
from pathlib import Path

# Family-color map. RGB tuples in 0-1 range (PyMuPDF convention).
FAMILY_COLORS = {
    "W":     (0.85, 0.25, 0.25),   # red
    "HSS":   (0.20, 0.40, 0.85),   # blue
    "C":     (0.95, 0.55, 0.10),   # orange
    "MC":    (0.95, 0.55, 0.10),
    "L":     (0.30, 0.70, 0.30),   # green
    "K":     (0.20, 0.70, 0.70),   # teal joist
    "LH":    (0.20, 0.70, 0.70),
    "DLH":   (0.20, 0.70, 0.70),
    "PL":    (0.55, 0.55, 0.55),   # grey plate
    "misc":  (0.65, 0.25, 0.75),   # purple
}
LOW_CONFIDENCE_COLOR = (0.95, 0.85, 0.10)  # yellow


def _family_color(family: str) -> tuple:
    """Return RGB color tuple for a family code."""
    if not family:
        return (0.5, 0.5, 0.5)
    fam = family.upper()
    # Specific keys first
    if fam in FAMILY_COLORS:
        return FAMILY_COLORS[fam]
    # Fall back by prefix
    for k, v in FAMILY_COLORS.items():
        if fam.startswith(k.upper()):
            return v
    return (0.4, 0.4, 0.4)


def write_tagged_pdf(in_pdf: str | Path, out_pdf: str | Path,
                     detections: list[dict]) -> Path:
    """Annotate a PDF with detected members and write to out_pdf.

    Each detection dict:
        {
            page: 0-indexed page number,
            shape: AISC designation, e.g. "W12X26",
            family: e.g. "W", "HSS", "L", "K", "PL", "misc",
            bbox: [x0, y0, x1, y1] in PDF points,
            subject: Bluebeam Subject string, e.g. "W12X26 BEAM",
            mark: piece mark / callout (Comments field),
            length_ft: float, length in feet,
            confidence: 0-1 float,
        }
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PyMuPDF (pymupdf) required for drawing_tagger") from e

    in_pdf = Path(in_pdf)
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(in_pdf)
    annotated = 0

    for det in detections:
        page_idx = int(det.get("page", 0) or 0)
        if page_idx < 0 or page_idx >= len(doc):
            continue
        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        page = doc[page_idx]
        rect = fitz.Rect(*bbox)
        # Clamp to page rect
        rect = rect & page.rect
        if rect.is_empty:
            continue

        confidence = float(det.get("confidence", 1.0) or 1.0)
        if confidence < 0.7:
            color = LOW_CONFIDENCE_COLOR
        else:
            color = _family_color(det.get("family") or "")

        annot = page.add_rect_annot(rect)
        # Subject is the field Bluebeam shows as the tool / type name
        subject = det.get("subject") or det.get("shape", "")
        # Bluebeam writes Subject into the annotation /Subj field
        annot.set_info(
            title="Cowork Auto-Tagger",
            subject=subject,
            content=(
                f"Mark: {det.get('mark') or '-'}\n"
                f"Length: {(det.get('length_ft') or 0):.2f} ft\n"
                f"Confidence: {confidence:.2f}"
            ),
        )
        annot.set_colors(stroke=color)
        annot.set_border(width=1.5)
        annot.set_opacity(0.55 if confidence < 0.7 else 0.85)
        annot.update()
        annotated += 1

    doc.save(out_pdf, garbage=4, deflate=True)
    doc.close()
    return out_pdf


def write_review_overlay(in_pdf: str | Path, out_png_dir: str | Path,
                         detections: list[dict], dpi: int = 144) -> list[Path]:
    """Render each page of the tagged PDF to PNG for human review.

    Writes one PNG per page that has at least one detection. Returns
    the list of PNG paths in page order.
    """
    try:
        import fitz
    except ImportError as e:
        raise RuntimeError("PyMuPDF required for review overlay") from e

    in_pdf = Path(in_pdf)
    out_dir = Path(out_png_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages_with_detections = sorted({int(d.get("page", 0) or 0) for d in detections})
    doc = fitz.open(in_pdf)
    out_pngs: list[Path] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for idx in pages_with_detections:
        if 0 <= idx < len(doc):
            pix = doc[idx].get_pixmap(matrix=mat, alpha=False)
            path = out_dir / f"review_p{idx+1:03d}.png"
            pix.save(path)
            out_pngs.append(path)
    doc.close()
    return out_pngs


def detections_to_boq_members(detections: list[dict]) -> list[dict]:
    """Convert detections (with bbox) into BOQ-pipeline member dicts."""
    members = []
    for d in detections:
        if not d.get("shape") or not d.get("length_ft"):
            continue
        members.append({
            "shape": d["shape"],
            "length_ft": float(d.get("length_ft", 0) or 0),
            "qty": int(d.get("qty", 1) or 1),
            "member_type": d.get("member_type", "structural"),
            "mark": d.get("mark", ""),
            "sheet": d.get("sheet", ""),
            "status": d.get("status", "Tentative"),
            "layer": "AutoTag",
            "confidence": float(d.get("confidence", 1.0) or 1.0),
            "_source": "auto_tag",
        })
    return members
