"""
Drawing Intel: PDF Preprocessor
=================================
Uses pymupdf4llm for layout-aware PDF extraction.
Two-pass strategy per Gemini research report:
  - Classification pass (150 DPI): Route S-sheets vs A-sheets
  - Analysis pass (300 DPI): Extract member callouts with full detail

pymupdf4llm is 10-250x cheaper than vision-based extraction and
runs with no GPU. F1 score: 0.8640.

Tesseract OCR is auto-triggered for scanned pages only.
"""

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

log = logging.getLogger(__name__)


def extract_drawing_set(pdf_path: str, pages: list[int] = None) -> dict:
    """Extract structured content from a PDF drawing set.

    Uses pymupdf4llm for layout-aware extraction with automatic OCR.
    Returns page-by-page content with metadata.

    Args:
        pdf_path: Path to PDF drawing file
        pages: Optional list of 0-based page numbers to process.
               If None, processes all pages.

    Returns:
        {pages: [{page_num, sheet_id, category, markdown, json_data,
                  hash, has_structural}], stats: {...}}
    """
    path = Path(pdf_path)
    if not path.exists():
        return {"error": f"File not found: {pdf_path}"}

    result_pages = []
    stats = {"total_pages": 0, "structural_pages": 0,
             "architectural_pages": 0, "other_pages": 0,
             "ocr_pages": 0}

    try:
        import pymupdf4llm
        import pymupdf

        doc = pymupdf.open(str(path))
        stats["total_pages"] = len(doc)

        # Determine which pages to process
        page_list = pages if pages is not None else list(range(len(doc)))

        # Extract markdown with layout analysis
        md_output = pymupdf4llm.to_markdown(
            str(path),
            pages=page_list,
            page_chunks=True,  # chunk by page with metadata
            write_images=False,  # don't write images to disk
        )

        # Also get JSON for bounding box data
        json_output = pymupdf4llm.to_json(str(path), pages=page_list)

        for i, chunk in enumerate(md_output):
            page_num = page_list[i] if i < len(page_list) else i
            page = doc[page_num]
            text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)

            # Hash for revision tracking
            page_hash = hashlib.sha256(text.encode()).hexdigest()

            # Classify this page
            sheet_id = _extract_sheet_id(text)
            category = _classify_page(text, sheet_id)

            if category == "structural":
                stats["structural_pages"] += 1
            elif category == "architectural":
                stats["architectural_pages"] += 1
            else:
                stats["other_pages"] += 1

            # Extract OCG layers if available
            layers = {}
            try:
                ocgs = doc.get_ocgs()
                if ocgs:
                    layers = {str(k): v.get("name", "") for k, v in ocgs.items()}
            except Exception:
                pass

            # Extract vector paths for scale detection
            paths = []
            try:
                drawings = page.get_drawings()
                paths = [{"type": d.get("type", ""), "rect": str(d.get("rect", ""))}
                         for d in drawings[:20]]  # first 20 only
            except Exception:
                pass

            result_pages.append({
                "page_num": page_num + 1,  # 1-based for users
                "sheet_id": sheet_id,
                "category": category,
                "markdown": text[:5000],  # cap for token management
                "hash": page_hash,
                "has_structural": category == "structural",
                "layers": layers,
                "vector_path_count": len(paths) if paths else 0,
                "metadata": chunk.get("metadata", {}) if isinstance(chunk, dict) else {},
            })

        doc.close()

    except ImportError as e:
        return {"error": f"pymupdf4llm not installed: {e}. Run: pip install pymupdf4llm"}
    except Exception as e:
        return {"error": f"Failed to process PDF: {e}"}

    return {
        "file": str(path),
        "pages": result_pages,
        "stats": stats,
        "structural_pages": [p["page_num"] for p in result_pages if p["has_structural"]],
    }


def rasterize_page(pdf_path: str, page_num: int, dpi: int = 300) -> dict:
    """Rasterize a single page at specified DPI for vision AI processing.

    Returns the image as bytes + metadata.

    Args:
        pdf_path: Path to PDF
        page_num: 0-based page number
        dpi: Resolution. 150 for classification, 300 for analysis.
    """
    try:
        import pymupdf

        doc = pymupdf.open(pdf_path)
        page = doc[page_num]

        # Grayscale saves tokens (per Gemini report)
        pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)

        # Save to temp file
        out_path = Path(pdf_path).parent / f"page_{page_num + 1}_{dpi}dpi.png"
        pix.save(str(out_path))

        doc.close()

        return {
            "path": str(out_path),
            "page_num": page_num + 1,
            "dpi": dpi,
            "width": pix.width,
            "height": pix.height,
            "size_bytes": len(pix.tobytes()),
        }
    except ImportError:
        return {"error": "PyMuPDF not installed"}
    except Exception as e:
        return {"error": f"Rasterization failed: {e}"}


def extract_with_ocg_isolation(pdf_path: str, page_num: int,
                                layer_name: str = "Steel") -> dict:
    """Extract content from a specific CAD layer (OCG).

    Per Gemini report: isolate "Steel" layer to reduce visual noise
    before AI processing.
    """
    try:
        import pymupdf

        doc = pymupdf.open(pdf_path)
        ocgs = doc.get_ocgs()

        if not ocgs:
            return {"error": "No OCG layers found in this PDF",
                    "fallback": "Use standard extraction instead"}

        # Find matching layer
        target_xref = None
        available_layers = []
        for xref, info in ocgs.items():
            name = info.get("name", "")
            available_layers.append(name)
            if layer_name.lower() in name.lower():
                target_xref = xref

        if target_xref is None:
            return {
                "error": f"Layer '{layer_name}' not found",
                "available_layers": available_layers,
            }

        # Toggle visibility: hide all except target
        page = doc[page_num]
        for xref in ocgs:
            doc.set_ocg_state(xref, on=(xref == target_xref))

        # Extract text from isolated layer
        text = page.get_text()

        # Rasterize isolated layer
        pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        out_path = Path(pdf_path).parent / f"page_{page_num + 1}_{layer_name}.png"
        pix.save(str(out_path))

        # Restore all layers
        for xref in ocgs:
            doc.set_ocg_state(xref, on=True)

        doc.close()

        return {
            "layer": layer_name,
            "text": text,
            "image_path": str(out_path),
            "available_layers": available_layers,
        }
    except ImportError:
        return {"error": "PyMuPDF not installed"}
    except Exception as e:
        return {"error": f"OCG extraction failed: {e}"}


def _extract_sheet_id(text: str) -> Optional[str]:
    """Extract drawing sheet ID from page text."""
    m = re.search(r'([SAFME])-?(\d{1,3}(?:\.\d{1,2})?)', text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r'SHEET\s+(\d+)\s+OF\s+\d+', text, re.IGNORECASE)
    if m:
        return f"SHEET-{m.group(1)}"
    return None


def _classify_page(text: str, sheet_id: Optional[str]) -> str:
    """Classify a drawing page by type.

    Categories: structural, architectural, mechanical, electrical,
                plumbing, civil, general, cover
    """
    text_lower = text.lower()

    # Sheet ID prefix classification
    if sheet_id:
        prefix = sheet_id[0].upper()
        prefix_map = {
            "S": "structural", "A": "architectural",
            "M": "mechanical", "E": "electrical",
            "F": "fire_protection",
        }
        if prefix in prefix_map:
            return prefix_map[prefix]

    # Content-based classification
    structural_signals = [
        "w14x", "w12x", "w10x", "w16x", "w18x", "w21x", "w24x",
        "hss", "wide flange", "steel column", "steel beam",
        "moment frame", "brace frame", "aisc", "base plate",
        "structural steel", "erection plan", "framing plan",
        "column schedule", "beam schedule",
    ]
    if any(sig in text_lower for sig in structural_signals):
        return "structural"

    if "general notes" in text_lower or "abbreviations" in text_lower:
        return "general"

    if "title sheet" in text_lower or "cover" in text_lower:
        return "cover"

    return "other"


# ── Phase 3 Image Preprocessing (local compute, zero token cost) ─────────────
# All functions accept raw PNG bytes and return PNG bytes.
# If cv2 is unavailable, functions return the original bytes unchanged.
# No function is defined inside another function (PyInstaller hard rule).

_PREPROCESS_LOG = Path(__file__).resolve().parent.parent.parent / "drawing_intel" / "preprocess_log.json"


def _bytes_to_cv2(image_bytes: bytes):
    """Decode PNG bytes to a cv2 numpy array. Returns None on failure."""
    if not HAS_CV2:
        return None
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    return img


def _cv2_to_bytes(img) -> bytes:
    """Encode a cv2 numpy array back to PNG bytes."""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("cv2.imencode failed")
    return buf.tobytes()


def preprocess_grayscale(image_bytes: bytes) -> bytes:
    """Convert image to grayscale. Pass-through if already gray or cv2 absent."""
    if not HAS_CV2:
        return image_bytes
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return image_bytes
    if len(img.shape) == 2:
        return image_bytes  # already grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return _cv2_to_bytes(gray)


def preprocess_adaptive_threshold(image_bytes: bytes,
                                   block_size: int = 31,
                                   c_const: int = 7) -> bytes:
    """Apply adaptive thresholding to enhance piece marks on scanned drawings.

    Uses Gaussian weighting over block_size x block_size neighborhood.
    c_const is subtracted from the weighted mean before thresholding.
    Pass-through if cv2 absent.
    """
    if not HAS_CV2:
        return image_bytes
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return image_bytes
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        img, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c_const,
    )
    return _cv2_to_bytes(thresh)


def preprocess_bilateral_filter(image_bytes: bytes,
                                  diameter: int = 9,
                                  sigma_color: float = 75.0,
                                  sigma_space: float = 75.0) -> bytes:
    """Denoise while preserving edges using bilateral filter.

    Preserves line work and text edges while reducing scan noise.
    Pass-through if cv2 absent.
    """
    if not HAS_CV2:
        return image_bytes
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return image_bytes
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    filtered = cv2.bilateralFilter(img, diameter, sigma_color, sigma_space)
    return _cv2_to_bytes(filtered)


def preprocess_contrast_normalize(image_bytes: bytes,
                                   clip_limit: float = 2.0,
                                   tile_grid: tuple = (8, 8)) -> bytes:
    """Normalize contrast using CLAHE for scanned PDFs.

    CLAHE (Contrast Limited Adaptive Histogram Equalization) improves
    legibility of faded or unevenly lit scanned drawings without blowing
    out dark regions. Pass-through if cv2 absent.
    """
    if not HAS_CV2:
        return image_bytes
    img = _bytes_to_cv2(image_bytes)
    if img is None:
        return image_bytes
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    enhanced = clahe.apply(img)
    return _cv2_to_bytes(enhanced)


def preprocess_pipeline(image_bytes: bytes,
                         run_bilateral: bool = True,
                         run_threshold: bool = False) -> bytes:
    """Run the standard preprocessing pipeline on a vision tile.

    Order: grayscale -> bilateral filter -> contrast normalize.
    Adaptive threshold is opt-in (run_threshold=True) for piece mark
    tiles where binary output is preferred over grayscale.

    Returns enhanced bytes. Pass-through if cv2 absent.
    """
    result = preprocess_grayscale(image_bytes)
    if run_bilateral:
        result = preprocess_bilateral_filter(result)
    result = preprocess_contrast_normalize(result)
    if run_threshold:
        result = preprocess_adaptive_threshold(result)
    return result


def compute_quality_metrics(before_bytes: bytes, after_bytes: bytes) -> dict:
    """Compute before/after quality metrics for a preprocessed tile.

    Metrics:
        contrast_before/after: standard deviation of pixel intensities
        edge_density_before/after: fraction of pixels that are edges (Canny)
        size_bytes_before/after: raw byte count
        improvement_pct: relative contrast gain

    Returns empty dict if cv2 unavailable.
    """
    if not HAS_CV2:
        return {}
    try:
        def _metrics(img_bytes: bytes) -> dict:
            img = _bytes_to_cv2(img_bytes)
            if img is None:
                return {}
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            contrast = float(np.std(gray))
            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.count_nonzero(edges)) / max(edges.size, 1)
            return {"contrast": round(contrast, 2),
                    "edge_density": round(edge_density, 4),
                    "size_bytes": len(img_bytes)}

        bef = _metrics(before_bytes)
        aft = _metrics(after_bytes)
        if not bef or not aft:
            return {}
        improvement = (
            (aft["contrast"] - bef["contrast"]) / max(bef["contrast"], 0.001) * 100.0
        )
        return {
            "contrast_before": bef["contrast"],
            "contrast_after": aft["contrast"],
            "edge_density_before": bef["edge_density"],
            "edge_density_after": aft["edge_density"],
            "size_bytes_before": bef["size_bytes"],
            "size_bytes_after": aft["size_bytes"],
            "contrast_improvement_pct": round(improvement, 2),
        }
    except Exception as e:
        return {"error": str(e)}


def log_preprocess_metrics(tile_id: str, page_num: int,
                            metrics: dict,
                            log_path: Optional[Path] = None) -> None:
    """Append one tile's quality metrics to preprocess_log.json.

    Log file: drawing_intel/preprocess_log.json (JSONL format).
    Non-fatal: silently skips on any I/O error.
    """
    if not metrics:
        return
    path = log_path or _PREPROCESS_LOG
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tile_id": tile_id,
            "page_num": page_num,
            **metrics,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
