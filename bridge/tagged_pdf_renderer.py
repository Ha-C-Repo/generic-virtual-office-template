"""
Your Company Virtual Office - Tagged PDF Renderer
===============================================
Produces annotated structural drawing PDFs with:
  - Color-coded shape highlights (W=blue, HSS=green, L=orange, C=red, PL=purple)
  - Weight annotations per member
  - Mark number labels
  - Summary table on the last page
  - Tonnage totals in header

Two rendering paths:
  Path A (text PDFs): PyMuPDF text search for exact coordinates. Free, instant.
  Path B (scanned PDFs): Gemini extraction + OpenAI spatial pass. Accuracy-first.

Output: annotated PDF saved to bid folder.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False


# ── COLOR SCHEME (shape family -> RGB) ────────────────────────────

SHAPE_COLORS = {
    "W":    (0.15, 0.35, 0.75),   # blue
    "HP":   (0.15, 0.35, 0.75),   # blue (same family)
    "S":    (0.20, 0.40, 0.70),   # steel blue
    "M":    (0.20, 0.40, 0.70),   # steel blue
    "HSS":  (0.10, 0.60, 0.30),   # green
    "PIPE": (0.10, 0.60, 0.30),   # green
    "L":    (0.85, 0.50, 0.10),   # orange
    "C":    (0.75, 0.15, 0.15),   # red
    "MC":   (0.75, 0.15, 0.15),   # red
    "WT":   (0.50, 0.30, 0.70),   # purple
    "MT":   (0.50, 0.30, 0.70),   # purple
    "ST":   (0.50, 0.30, 0.70),   # purple
    "PL":   (0.60, 0.20, 0.60),   # magenta
}

SHAPE_LABELS = {
    "W": "Wide Flange", "HP": "H-Pile", "S": "S-Shape", "M": "M-Shape",
    "HSS": "Hollow Structural", "PIPE": "Pipe", "L": "Angle",
    "C": "Channel", "MC": "Misc Channel", "WT": "WT-Shape",
    "PL": "Plate",
}


def _get_shape_family(shape: str) -> str:
    """Extract shape family prefix from AISC notation."""
    m = re.match(r'^([A-Z]+)', shape.upper())
    return m.group(1) if m else "W"


def _color_for_shape(shape: str) -> tuple:
    """Get RGB color tuple for a shape."""
    family = _get_shape_family(shape)
    return SHAPE_COLORS.get(family, (0.4, 0.4, 0.4))


def _fitz_color(rgb: tuple) -> tuple:
    """Convert to fitz-compatible color."""
    return rgb


# ── PATH A: TEXT-BASED PDF ANNOTATION ─────────────────────────────

def annotate_text_pdf(source_pdf: str, members: list,
                      output_path: str = "",
                      summary: dict = None) -> dict:
    """Annotate a text-based PDF with shape highlights and weight labels.

    Uses PyMuPDF text search for exact coordinate matching.
    No AI calls. Free. Instant. Works on vector PDFs from Revit/AutoCAD.

    Args:
        source_pdf: path to the original structural drawing PDF
        members: list of dicts from AISC match, each with:
            shape, mark, qty, weight_per_ft, length_ft, weight_tons, page
        output_path: where to save the annotated PDF (auto-generated if empty)
        summary: dict with total_tonnage, matched_count, etc.

    Returns:
        dict with output_path, annotations_placed, pages_annotated
    """
    if not HAS_FITZ:
        return {"error": "PyMuPDF (fitz) not installed. Run: pip install pymupdf"}

    src = Path(source_pdf)
    if not src.exists():
        return {"error": f"Source PDF not found: {source_pdf}"}

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
        output_path = str(src.parent / f"{src.stem}_TAGGED_{ts}.pdf")

    doc = fitz.open(str(src))
    annotations_placed = 0
    pages_annotated = set()
    legend_items = {}  # family -> color for legend

    for member in members:
        shape = member.get("shape", "")
        mark = member.get("mark", "")
        qty = member.get("qty", 1)
        weight_tons = member.get("weight_tons", 0) or member.get("line_weight_tons", 0)
        weight_per_ft = member.get("weight_per_ft", 0)
        length_ft = member.get("length_ft", 0)
        target_page = member.get("page", 0) - 1  # 0-indexed

        if not shape:
            continue

        color = _color_for_shape(shape)
        family = _get_shape_family(shape)
        legend_items[family] = color

        # Search for shape text on the target page (or all pages)
        pages_to_search = [target_page] if 0 <= target_page < len(doc) else range(len(doc))

        for page_idx in pages_to_search:
            if page_idx < 0 or page_idx >= len(doc):
                continue
            page = doc[page_idx]

            # Search for the shape designation
            rects = page.search_for(shape, quads=False)
            if not rects and mark:
                # Try searching for the mark number
                rects = page.search_for(mark, quads=False)

            for rect in rects:
                # Draw highlight rectangle behind text
                highlight = fitz.Rect(
                    rect.x0 - 2, rect.y0 - 1,
                    rect.x1 + 2, rect.y1 + 1
                )
                # Semi-transparent colored background
                shape_annot = page.draw_rect(
                    highlight,
                    color=color,
                    fill=(*color, 0.15),  # 15% opacity fill
                    width=0.8,
                )

                # Weight annotation to the right of the shape text
                label_text = ""
                if weight_tons > 0:
                    label_text = f" {weight_tons:.2f}T"
                elif weight_per_ft > 0 and length_ft > 0:
                    t = (weight_per_ft * length_ft * qty) / 2000
                    label_text = f" {t:.2f}T"

                if label_text:
                    label_point = fitz.Point(rect.x1 + 4, rect.y1 - 1)
                    page.insert_text(
                        label_point,
                        label_text,
                        fontsize=6,
                        color=color,
                        fontname="helv",
                    )

                # Mark number annotation above
                if mark and rects.index(rect) == 0:
                    mark_point = fitz.Point(rect.x0, rect.y0 - 3)
                    page.insert_text(
                        mark_point,
                        f"[{mark}]",
                        fontsize=5,
                        color=(0.3, 0.3, 0.3),
                        fontname="helv",
                    )

                annotations_placed += 1
                pages_annotated.add(page_idx)

    # ── ADD SUMMARY PAGE ──────────────────────────────────────────
    if members:
        _add_summary_page(doc, members, summary, legend_items)

    doc.save(output_path)
    doc.close()

    return {
        "output_path": output_path,
        "annotations_placed": annotations_placed,
        "pages_annotated": len(pages_annotated),
        "total_pages": len(doc) if not doc.is_closed else 0,
        "legend": {SHAPE_LABELS.get(k, k): list(v) for k, v in legend_items.items()},
    }


def _add_summary_page(doc, members: list, summary: dict, legend: dict):
    """Add a summary/legend page at the end of the document."""
    page = doc.new_page(width=612, height=792)  # Letter size

    y = 50
    # Header
    page.insert_text(fitz.Point(50, y), "YOUR COMPANY - STRUCTURAL STEEL SUMMARY",
                     fontsize=14, fontname="helv", color=(0.1, 0.1, 0.3))
    y += 20
    page.insert_text(fitz.Point(50, y), f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}",  # vj: local-display-ok
                     fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))
    y += 5
    page.draw_line(fitz.Point(50, y), fitz.Point(562, y), color=(0.7, 0.7, 0.7), width=0.5)
    y += 15

    # Tonnage summary
    total_tons = summary.get("total_weight_tons", 0) if summary else sum(m.get("weight_tons", 0) for m in members)
    matched = summary.get("matched_count", len(members)) if summary else len(members)
    page.insert_text(fitz.Point(50, y), f"Total Verified Tonnage: {total_tons:.2f} tons",
                     fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
    y += 15
    page.insert_text(fitz.Point(50, y), f"Members Matched: {matched}",
                     fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
    y += 20

    # Color legend
    page.insert_text(fitz.Point(50, y), "SHAPE FAMILY LEGEND",
                     fontsize=10, fontname="helv", color=(0.1, 0.1, 0.3))
    y += 15

    for family, color in sorted(legend.items()):
        label = SHAPE_LABELS.get(family, family)
        # Color swatch
        swatch = fitz.Rect(50, y - 8, 62, y)
        page.draw_rect(swatch, color=color, fill=color)
        # Label
        page.insert_text(fitz.Point(68, y), f"{family} - {label}",
                         fontsize=8, fontname="helv", color=(0.2, 0.2, 0.2))
        y += 14

    y += 10
    page.draw_line(fitz.Point(50, y), fitz.Point(562, y), color=(0.7, 0.7, 0.7), width=0.5)
    y += 15

    # Member table
    page.insert_text(fitz.Point(50, y), "MEMBER SCHEDULE",
                     fontsize=10, fontname="helv", color=(0.1, 0.1, 0.3))
    y += 15

    # Table header
    cols = [50, 100, 200, 260, 310, 370, 440, 520]
    headers = ["Mark", "Shape", "Length", "Qty", "lb/ft", "Weight (lbs)", "Weight (tons)"]
    for i, h in enumerate(headers):
        page.insert_text(fitz.Point(cols[i], y), h,
                         fontsize=7, fontname="helv", color=(0.1, 0.1, 0.3))
    y += 3
    page.draw_line(fitz.Point(50, y), fitz.Point(562, y), color=(0.5, 0.5, 0.5), width=0.5)
    y += 10

    # Table rows
    for m in sorted(members, key=lambda x: x.get("mark", "")):
        if y > 740:
            page = doc.new_page(width=612, height=792)
            y = 50

        color = _color_for_shape(m.get("shape", ""))
        mark = m.get("mark", "-")
        shape = m.get("shape", "-")
        length = m.get("length_ft", 0)
        qty = m.get("qty", 1)
        wt_ft = m.get("weight_per_ft", 0)
        wt_lbs = m.get("weight_lbs", 0) or m.get("line_weight_lbs", 0) or (wt_ft * length * qty)
        wt_tons = m.get("weight_tons", 0) or m.get("line_weight_tons", 0) or (wt_lbs / 2000 if wt_lbs else 0)

        row_data = [
            mark, shape, f"{length:.0f} ft" if length else "-",
            str(qty), f"{wt_ft:.1f}" if wt_ft else "-",
            f"{wt_lbs:,.0f}" if wt_lbs else "-",
            f"{wt_tons:.3f}" if wt_tons else "-",
        ]
        for i, val in enumerate(row_data):
            page.insert_text(fitz.Point(cols[i], y), val,
                             fontsize=7, fontname="helv", color=color)
        y += 11

    # Footer
    y += 10
    page.draw_line(fitz.Point(50, y), fitz.Point(562, y), color=(0.7, 0.7, 0.7), width=0.5)
    y += 12
    page.insert_text(fitz.Point(50, y),
                     "Weights verified against AISC Shapes Database v16.0 (2,299 shapes)",
                     fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4))
    y += 10
    page.insert_text(fitz.Point(50, y),
                     "Your Company, LLC | [COMPANY ADDRESS], Houston TX 77064 | [COMPANY PHONE]",
                     fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4))


# ── PATH B: SCANNED PDF (AI VISION CASCADE) ──────────────────────

def annotate_scanned_pdf(source_pdf: str, members: list,
                         gemini_key: str = "", openai_key: str = "",
                         output_path: str = "",
                         summary: dict = None) -> dict:
    """Annotate a scanned/raster PDF using AI vision for spatial coordinates.

    Two-pass cascade (accuracy over cost):
      Pass 1 (Gemini 2.5 Flash): extract shapes + approximate positions
      Pass 2 (GPT-4o): refine spatial coordinates for each detected shape

    Merged result: Gemini's verified data + OpenAI's precise coordinates.
    """
    if not HAS_FITZ:
        return {"error": "PyMuPDF (fitz) not installed. Run: pip install pymupdf"}

    src = Path(source_pdf)
    if not src.exists():
        return {"error": f"Source PDF not found: {source_pdf}"}

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
        output_path = str(src.parent / f"{src.stem}_TAGGED_{ts}.pdf")

    doc = fitz.open(str(src))
    annotations_placed = 0
    pages_annotated = set()
    legend_items = {}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_width = page.rect.width
        page_height = page.rect.height

        # Render page to image for AI vision
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")

        # ── PASS 1: Gemini extraction + approximate positions ─────
        gemini_results = []
        if gemini_key:
            gemini_results = _gemini_spatial_pass(img_bytes, gemini_key,
                                                   page_width, page_height)

        # ── PASS 2: OpenAI spatial refinement ─────────────────────
        if openai_key and gemini_results:
            refined = _openai_spatial_pass(img_bytes, openai_key,
                                           gemini_results, page_width, page_height)
            if refined:
                gemini_results = refined

        # ── DRAW ANNOTATIONS ──────────────────────────────────────
        for item in gemini_results:
            shape = item.get("shape", "")
            x = item.get("x", 0)
            y_pos = item.get("y", 0)
            w = item.get("w", 60)
            h = item.get("h", 12)
            confidence = item.get("confidence", 0)

            if not shape or confidence < 0.3:
                continue

            color = _color_for_shape(shape)
            legend_items[_get_shape_family(shape)] = color

            # Draw bounding box
            rect = fitz.Rect(x, y_pos, x + w, y_pos + h)
            page.draw_rect(rect, color=color, fill=(*color, 0.12), width=0.6)

            # Shape label above
            page.insert_text(fitz.Point(x, y_pos - 2), shape,
                             fontsize=5, color=color, fontname="helv")

            # Weight label if matched
            matched = _find_matching_member(shape, members)
            if matched and (matched.get("weight_tons") or matched.get("line_weight_tons")):
                wt = matched.get("weight_tons") or matched.get("line_weight_tons", 0)
                page.insert_text(fitz.Point(x + w + 2, y_pos + h - 2),
                                 f"{wt:.2f}T",
                                 fontsize=5, color=color, fontname="helv")

            annotations_placed += 1
            pages_annotated.add(page_idx)

    # Summary page
    if members:
        _add_summary_page(doc, members, summary, legend_items)

    doc.save(output_path)
    doc.close()

    return {
        "output_path": output_path,
        "annotations_placed": annotations_placed,
        "pages_annotated": len(pages_annotated),
        "method": "ai_vision_cascade",
        "legend": {SHAPE_LABELS.get(k, k): list(v) for k, v in legend_items.items()},
    }


def _gemini_spatial_pass(img_bytes: bytes, api_key: str,
                          page_width: float, page_height: float) -> list:
    """Gemini 2.5 Flash: extract shapes with approximate bounding boxes."""
    try:
        from bridge.gemini_compat import make_client, get_sdk_version
        client = make_client(api_key)
        if client is None:
            return []

        prompt = (
            "You are analyzing a structural steel framing plan drawing. "
            "Find every structural steel shape callout on this drawing "
            "(W-shapes, HSS, angles, channels, pipes, plates). "
            "For each one, return a JSON array of objects with:\n"
            "  shape: the AISC designation (e.g. W24X55, HSS8X8X.500)\n"
            "  x: left edge x-coordinate in pixels\n"
            "  y: top edge y-coordinate in pixels\n"
            "  w: width of the text bounding box in pixels\n"
            "  h: height of the text bounding box in pixels\n"
            "  confidence: 0.0-1.0 how confident you are\n"
            f"Image is {page_width:.0f}x{page_height:.0f} points. "
            "Return ONLY the JSON array, no other text."
        )

        import PIL.Image
        import io
        img = PIL.Image.open(io.BytesIO(img_bytes))
        # Handle both SDK variants
        if get_sdk_version() == "google-genai":
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=[prompt, img],
            )
        else:
            model = client.GenerativeModel("gemini-2.5-flash-preview-05-20")
            response = model.generate_content([prompt, img])
        text = response.text.strip()
        # Strip markdown fences if present
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception as e:
        return []


def _openai_spatial_pass(img_bytes: bytes, api_key: str,
                          gemini_results: list,
                          page_width: float, page_height: float) -> list:
    """GPT-4o: refine spatial coordinates for shapes found by Gemini."""
    try:
        import base64
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        b64_img = base64.b64encode(img_bytes).decode()
        shapes_list = ", ".join(r.get("shape", "?") for r in gemini_results[:20])

        prompt = (
            f"On this structural drawing, locate the exact pixel positions of "
            f"these shape callouts: {shapes_list}. "
            f"Image is {page_width:.0f}x{page_height:.0f} points. "
            f"Return a JSON array with one object per shape found:\n"
            f"  shape: AISC designation\n"
            f"  x: left edge x in pixels\n"
            f"  y: top edge y in pixels\n"
            f"  w: text width in pixels\n"
            f"  h: text height in pixels\n"
            f"  confidence: 0.0-1.0\n"
            f"Return ONLY the JSON array."
        )

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{b64_img}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=2000,
        )

        text = response.choices[0].message.content.strip()
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text)
    except Exception:
        return None  # Fall back to Gemini results


def _find_matching_member(shape: str, members: list) -> Optional[dict]:
    """Find a member in the verified list that matches this shape."""
    shape_upper = shape.upper().replace(" ", "")
    for m in members:
        if m.get("shape", "").upper().replace(" ", "") == shape_upper:
            return m
    return None


# ── COMBINED ENTRY POINT ──────────────────────────────────────────

def render_tagged_pdf(source_pdf: str, members: list,
                      output_path: str = "",
                      summary: dict = None,
                      gemini_key: str = "",
                      openai_key: str = "",
                      force_ai: bool = False) -> dict:
    """Smart entry point: auto-detects text vs scanned PDF.

    Text PDF -> Path A (PyMuPDF search, free, instant)
    Scanned PDF -> Path B (Gemini + OpenAI cascade, accurate)
    force_ai=True -> always use Path B (for quality verification)
    """
    if not HAS_FITZ:
        return {"error": "PyMuPDF (fitz) not installed. Run: pip install pymupdf"}

    src = Path(source_pdf)
    if not src.exists():
        return {"error": f"Source PDF not found: {source_pdf}"}

    # Detect: is this a text PDF or scanned?
    doc = fitz.open(str(src))
    total_text = ""
    for page in doc:
        total_text += page.get_text()
    doc.close()

    is_text_pdf = len(total_text.strip()) > 50
    method = "text_search"

    if force_ai or not is_text_pdf:
        if gemini_key or openai_key:
            method = "ai_vision"
            return annotate_scanned_pdf(source_pdf, members, gemini_key,
                                         openai_key, output_path, summary)
        elif not is_text_pdf:
            return {"error": "Scanned PDF detected but no API keys provided. "
                    "Need Gemini or OpenAI key for raster drawing annotation."}

    # Text PDF: use local search
    result = annotate_text_pdf(source_pdf, members, output_path, summary)
    result["method"] = method
    result["is_text_pdf"] = is_text_pdf
    return result
