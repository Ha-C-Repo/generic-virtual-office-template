"""
Tiled Inference Pipeline for Small Text on Structural Drawings
===============================================================
Problem: 36"x48" blueprints at 300 DPI pixelate small text (weld symbols,
connection schedules, member callouts in congested areas).

Solution: Instead of one large image, crop high-density regions at 600 DPI
and send tiles with surrounding context to the Vision API.

Pipeline:
  1. Rasterize full page at 150 DPI for classification
  2. Detect high-density text regions from pymupdf4llm markdown
  3. Crop those regions at 600 DPI with context padding
  4. Send tiles to Gemini Vision with grid-line anchoring
  5. Stitch results back into the full page member list

Usage:
    from bridge.drawing_intel.tiled_inference import TiledInferencePipeline
    tip = TiledInferencePipeline()
    tiles = tip.identify_roi_regions(pdf_path, page_num, markdown_text)
    for tile in tiles:
        img_bytes = tip.extract_tile(pdf_path, page_num, tile['bbox'], dpi=600)
        # Send img_bytes to Gemini Vision with tile['context_prompt']
"""

import re
from dataclasses import dataclass

from bridge.drawing_intel.vote_consensus import (
    vote_members,
    build_vote_manifest,
)


@dataclass
class TileRegion:
    """A region of interest on a drawing page."""
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1) in points
    region_type: str       # "connection_schedule", "member_cluster", "weld_detail", "general_note"
    confidence: float      # 0.0-1.0, how likely this region has small text
    context_prompt: str    # Prompt fragment for the Vision API
    grid_anchor: str       # Nearest grid intersection (e.g., "C-3")


# Patterns that indicate high-density text regions
_DENSITY_PATTERNS = [
    (r"connection\s+schedule", "connection_schedule", 0.95),
    (r"weld\s+symbol|fillet\s+weld|CJP|PJP", "weld_detail", 0.90),
    (r"typical\s+detail|section\s+detail", "section_detail", 0.85),
    (r"bolt\s+schedule|anchor\s+bolt", "bolt_schedule", 0.90),
    (r"beam\s+schedule|member\s+schedule", "member_schedule", 0.95),
    (r"general\s+note|structural\s+note", "general_note", 0.80),
]

# Context padding around ROI (in points, 72 pts = 1 inch)
CONTEXT_PAD = 72  # 1 inch of surrounding context


class TiledInferencePipeline:
    """Manages tiled extraction of high-density drawing regions."""
    
    def __init__(self, low_dpi: int = 150, high_dpi: int = 600):
        self.low_dpi = low_dpi
        self.high_dpi = high_dpi
    
    def identify_roi_regions(self, pdf_path: str, page_num: int,
                             markdown_text: str) -> list[TileRegion]:
        """Scan pymupdf4llm markdown output to find high-density regions.
        
        Looks for connection schedules, weld symbols, bolt schedules, etc.
        Returns list of TileRegion objects with bounding boxes for 600 DPI crops.
        """
        regions = []
        
        for pattern, region_type, confidence in _DENSITY_PATTERNS:
            matches = list(re.finditer(pattern, markdown_text, re.IGNORECASE))
            if matches:
                for match in matches:
                    # Estimate bbox from text position in markdown
                    # In production, use pymupdf text search to get actual coordinates
                    region = TileRegion(
                        bbox=self._estimate_bbox_from_text(pdf_path, page_num, 
                                                           match.group()),
                        region_type=region_type,
                        confidence=confidence,
                        context_prompt=self._build_context_prompt(region_type),
                        grid_anchor=self._find_nearest_grid(pdf_path, page_num,
                                                            match.start()),
                    )
                    regions.append(region)
        
        # Sort by confidence (highest first)
        regions.sort(key=lambda r: r.confidence, reverse=True)
        return regions
    
    def extract_tile(self, pdf_path: str, page_num: int,
                     bbox: tuple, dpi: int = 600) -> bytes:
        """Crop a specific Region of Interest at high DPI.
        
        Adds CONTEXT_PAD points of surrounding context so the Vision API
        can anchor the text to nearby grid lines.
        """
        try:
            import fitz
        except ImportError:
            return b""
        
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        
        # Expand bbox by context padding
        x0, y0, x1, y1 = bbox
        padded = fitz.Rect(
            max(0, x0 - CONTEXT_PAD),
            max(0, y0 - CONTEXT_PAD),
            min(page.rect.width, x1 + CONTEXT_PAD),
            min(page.rect.height, y1 + CONTEXT_PAD),
        )
        
        pix = page.get_pixmap(dpi=dpi, clip=padded)
        doc.close()
        return pix.tobytes("png")
    
    def extract_all_tiles(self, pdf_path: str, page_num: int,
                          markdown_text: str) -> list[dict]:
        """Full pipeline: identify regions, extract tiles, build prompts.
        
        Returns list of dicts with:
            image_bytes, region_type, confidence, context_prompt, grid_anchor
        """
        regions = self.identify_roi_regions(pdf_path, page_num, markdown_text)
        results = []
        
        for region in regions:
            img = self.extract_tile(pdf_path, page_num, region.bbox)
            if img:
                results.append({
                    "image_bytes": img,
                    "region_type": region.region_type,
                    "confidence": region.confidence,
                    "context_prompt": region.context_prompt,
                    "grid_anchor": region.grid_anchor,
                    "bbox": region.bbox,
                    "dpi": self.high_dpi,
                })
        
        return results
    
    def _estimate_bbox_from_text(self, pdf_path: str, page_num: int,
                                  search_text: str) -> tuple:
        """Use pymupdf text search to find actual coordinates of text."""
        try:
            import fitz
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            instances = page.search_for(search_text)
            doc.close()
            if instances:
                r = instances[0]
                return (r.x0, r.y0, r.x1, r.y1)
        except Exception:
            pass
        # Fallback: center of page, 4"x4" region
        return (144, 144, 432, 432)
    
    def _find_nearest_grid(self, pdf_path: str, page_num: int,
                            text_offset: int) -> str:
        """Estimate nearest grid intersection from text position."""
        # In production: cross-reference with grid line detection
        # from the multi-pass vision strategy
        return "unknown"
    
    def _build_context_prompt(self, region_type: str) -> str:
        """Build a Vision API prompt fragment for this region type."""
        prompts = {
            "connection_schedule": (
                "This is a cropped connection schedule from a structural drawing. "
                "Extract every connection type, bolt size, bolt count, and weld symbol. "
                "List each connection with its grid location and member designation."
            ),
            "weld_detail": (
                "This is a cropped weld detail. Identify: weld type (fillet/CJP/PJP), "
                "weld size, length, electrode specification, and which members are joined."
            ),
            "member_schedule": (
                "This is a cropped beam/member schedule. Extract every row: "
                "mark number, AISC shape designation, length, quantity, and notes."
            ),
            "bolt_schedule": (
                "This is a cropped bolt schedule. Extract: bolt diameter, grade, "
                "quantity per connection, hole type, and torque requirements."
            ),
            "section_detail": (
                "This is a cropped section detail. Identify: member shapes, "
                "connection hardware, stiffener plates, and dimensional callouts."
            ),
            "general_note": (
                "This is a cropped general notes section. Extract every note "
                "that affects fabrication: steel grade, coating, inspection, "
                "special requirements, and code references."
            ),
        }
        return prompts.get(region_type, "Extract all text from this cropped region.")

    # ── Phase 3: Deterministic 4x4 grid tiling ────────────────────────────────

    def generate_deterministic_grid(self,
                                     page_width_pts: float,
                                     page_height_pts: float,
                                     cols: int = 4,
                                     rows: int = 4,
                                     overlap_pct: float = 0.15) -> list[TileRegion]:
        """Divide a page into a deterministic cols x rows grid with overlap.

        Tile naming: columns A-D (left to right), rows 1-4 (top to bottom).
        Each tile extends overlap_pct of its width/height into adjacent tiles.

        Args:
            page_width_pts:  page width in PDF points (1 pt = 1/72 inch)
            page_height_pts: page height in PDF points
            cols:            number of columns (default 4 -> A-D)
            rows:            number of rows (default 4 -> 1-4)
            overlap_pct:     fractional overlap between tiles (default 0.15)

        Returns:
            List of TileRegion objects, one per cell, named "Tile A1" etc.
        """
        base_w = page_width_pts / cols
        base_h = page_height_pts / rows
        pad_w = base_w * overlap_pct
        pad_h = base_h * overlap_pct

        tiles = []
        col_labels = [chr(ord("A") + c) for c in range(cols)]

        for r in range(rows):
            for c in range(cols):
                x0 = max(0.0, c * base_w - pad_w)
                y0 = max(0.0, r * base_h - pad_h)
                x1 = min(page_width_pts, (c + 1) * base_w + pad_w)
                y1 = min(page_height_pts, (r + 1) * base_h + pad_h)
                tile_id = f"Tile {col_labels[c]}{r + 1}"
                prompt = (
                    f"This is {tile_id} of a {cols}x{rows} grid "
                    f"covering a structural steel drawing. "
                    f"Extract all member designations, piece marks, "
                    f"dimensions, and callouts visible in this tile."
                )
                tiles.append(TileRegion(
                    bbox=(x0, y0, x1, y1),
                    region_type="grid_tile",
                    confidence=1.0,
                    context_prompt=prompt,
                    grid_anchor=tile_id,
                ))
        return tiles

    def extract_grid_tiles(self, pdf_path: str, page_num: int,
                            dpi: int = 600) -> list[dict]:
        """Rasterize all 16 grid tiles from a page at high DPI.

        Thin wrapper around extract_grid_tiles_nxn() with 4x4 defaults.
        """
        return self.extract_grid_tiles_nxn(pdf_path, page_num,
                                            cols=4, rows=4, dpi=dpi)

    def extract_grid_tiles_nxn(self, pdf_path: str, page_num: int,
                                cols: int, rows: int,
                                dpi: int = 600) -> list[dict]:
        """Rasterize an NxN deterministic grid of tiles from a page.

        Args:
            pdf_path: path to the PDF file
            page_num: zero-based page index
            cols:     number of grid columns (A-Z, max 26)
            rows:     number of grid rows (1-N)
            dpi:      rasterization resolution

        Returns list of dicts with image_bytes, tile_id, bbox, region_type,
        context_prompt, pdf_coords, and dpi.
        """
        try:
            import fitz
            doc = fitz.open(pdf_path)
            page = doc[page_num]
            w = page.rect.width
            h = page.rect.height
            doc.close()
        except Exception:
            return []

        tiles = self.generate_deterministic_grid(w, h, cols=cols, rows=rows)
        results = []
        for tile in tiles:
            img = self.extract_tile(pdf_path, page_num, tile.bbox, dpi=dpi)
            if img:
                results.append({
                    "image_bytes": img,
                    "tile_id": tile.grid_anchor,
                    "bbox": tile.bbox,
                    "region_type": tile.region_type,
                    "context_prompt": tile.context_prompt,
                    "pdf_coords": {
                        "page": page_num + 1,
                        "x0_pts": round(tile.bbox[0], 2),
                        "y0_pts": round(tile.bbox[1], 2),
                        "x1_pts": round(tile.bbox[2], 2),
                        "y1_pts": round(tile.bbox[3], 2),
                    },
                    "dpi": dpi,
                })
        return results

    def merge_roi_and_grid(self, roi_results: list[dict],
                            grid_results: list[dict],
                            overlap_tolerance_pts: float = 72.0) -> list[dict]:
        """Merge ROI and grid tile results, deduplicating overlapping regions.

        When a finding from both ROI and grid covers the same PDF coordinates
        (centers within overlap_tolerance_pts of each other), keep the one
        with higher confidence. Log which was kept.

        Args:
            roi_results:   output of extract_all_tiles() (ROI-based)
            grid_results:  output of extract_grid_tiles() (deterministic grid)
            overlap_tolerance_pts: bounding box center proximity threshold

        Returns:
            Merged list with method="roi", "grid", or "dedup_kept_roi" /
            "dedup_kept_grid" on each entry.
        """
        def _center(item: dict) -> tuple:
            b = item.get("bbox", (0, 0, 0, 0))
            return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)

        def _dist(a: tuple, b: tuple) -> float:
            return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

        tagged_roi = [{"method": "roi", **r} for r in roi_results]
        tagged_grid = [{"method": "grid", **r} for r in grid_results]

        merged = list(tagged_roi)
        for g_item in tagged_grid:
            g_center = _center(g_item)
            duplicate = False
            for m_item in merged:
                if _dist(_center(m_item), g_center) < overlap_tolerance_pts:
                    roi_conf = m_item.get("confidence", 0.0)
                    grid_conf = g_item.get("confidence", 0.0)
                    if grid_conf > roi_conf:
                        m_item.update(g_item)
                        m_item["method"] = "dedup_kept_grid"
                    else:
                        m_item["method"] = "dedup_kept_roi"
                    duplicate = True
                    break
            if not duplicate:
                merged.append(g_item)
        return merged

    def run_three_pass(self, pdf_path: str, page_num: int,
                       markdown_text: str) -> dict:
        """Extract tiles from three vision passes and build a vote manifest.

        Pass 1 - ROI (high-density regions, 600 DPI, GPT-4o routing)
        Pass 2 - 4x4 grid (uniform coverage, 300 DPI, Gemini routing via pass_hint)
        Pass 3 - 6x6 grid (fine resolution, 600 DPI, GPT-4o routing)

        Vision inference is NOT performed here. The returned tile batches are
        consumed by detail_vision_node() (task 1.7) to run per-tile inference.
        vote_members() is called on tile_id coverage to identify regions
        confirmed by 2+ passes (threshold=2).

        Args:
            pdf_path:      path to the PDF file
            page_num:      zero-based page index
            markdown_text: pymupdf4llm markdown for ROI detection (Pass 1)

        Returns dict with keys:
            pass1_tiles:          list of tile dicts from Pass 1
            pass2_tiles:          list of tile dicts from Pass 2
            pass3_tiles:          list of tile dicts from Pass 3
            pass_metadata:        list of per-pass info dicts
            accepted:             tile coverage in 2+ passes
            flagged:              tile coverage in only 1 pass
            disagreement_report:  details on flagged tiles
            cost_estimate_usd:    estimated vision API cost for this page
        """
        pass1 = self.extract_all_tiles(pdf_path, page_num, markdown_text)
        pass2 = self.extract_grid_tiles(pdf_path, page_num, dpi=300)
        pass3 = self.extract_grid_tiles_nxn(pdf_path, page_num,
                                             cols=6, rows=6, dpi=600)

        pass_metadata = [
            {"pass_id": 1, "strategy": "roi", "dpi": 600,
             "tile_count": len(pass1), "model_hint": "gpt4o"},
            {"pass_id": 2, "strategy": "grid_4x4", "dpi": 300,
             "tile_count": len(pass2), "model_hint": "gemini_pass2_grid"},
            {"pass_id": 3, "strategy": "grid_6x6", "dpi": 600,
             "tile_count": len(pass3), "model_hint": "gpt4o"},
        ]

        def _tiles_to_members(tiles: list[dict], pass_idx: int) -> list[dict]:
            return [
                {"shape": t.get("tile_id", ""), "mark": "",
                 "grid_anchor": t.get("tile_id", ""), "_pass": pass_idx,
                 "bbox": t.get("bbox"), "region_type": t.get("region_type")}
                for t in tiles
            ]

        member_batches = [
            _tiles_to_members(pass1, 0),
            _tiles_to_members(pass2, 1),
            _tiles_to_members(pass3, 2),
        ]
        vote_result = vote_members(member_batches, threshold=2)

        # Tiles: Pass 2 is Gemini (free). Passes 1 and 3 use gpt4o at $0.05/tile.
        # One shared crosscheck at $0.03 per page.
        cost_usd = (len(pass1) * 0.05
                    + len(pass2) * 0.00
                    + len(pass3) * 0.05
                    + 0.03)

        manifest = build_vote_manifest(
            accepted=vote_result["accepted"],
            flagged=vote_result["flagged"],
            report=vote_result["disagreement_report"],
            pass_metadata=pass_metadata,
        )

        return {
            "pass1_tiles": pass1,
            "pass2_tiles": pass2,
            "pass3_tiles": pass3,
            "pass_metadata": pass_metadata,
            "accepted": vote_result["accepted"],
            "flagged": vote_result["flagged"],
            "disagreement_report": vote_result["disagreement_report"],
            "cost_estimate_usd": round(cost_usd, 4),
            "manifest": manifest,
        }


def tile_to_pdf_coords(tile_bbox: tuple,
                        local_x_px: float,
                        local_y_px: float,
                        dpi: int,
                        pad_pts: float = CONTEXT_PAD) -> tuple:
    """Convert pixel coordinates within a tile back to PDF point coordinates.

    Args:
        tile_bbox:     (x0, y0, x1, y1) of the tile in PDF points, BEFORE
                       context padding was added by extract_tile().
        local_x_px:   x pixel offset within the extracted tile image.
        local_y_px:   y pixel offset within the extracted tile image.
        dpi:           DPI used to rasterize the tile.
        pad_pts:       context padding added by extract_tile() (default 72).

    Returns:
        (pdf_x_pts, pdf_y_pts) - coordinates in PDF point space.
    """
    px_per_pt = dpi / 72.0
    pdf_x = (tile_bbox[0] - pad_pts) + local_x_px / px_per_pt
    pdf_y = (tile_bbox[1] - pad_pts) + local_y_px / px_per_pt
    return (round(pdf_x, 2), round(pdf_y, 2))
