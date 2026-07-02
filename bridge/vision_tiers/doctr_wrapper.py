"""DocTR Tier 1 wrapper.

DocTR (Document Text Recognition) by Mindee. CPU-friendly OCR. We use it
for tasks where the input is dense text and Gemini would be expensive
overkill: column/beam schedules, title blocks, callouts, piece-mark
labels. Models download on first run (~500 MB total).

Mac Mini M4 boot expectation:
    pip install python-doctr[torch]
    First call: model weights download to ~/.cache/doctr/. Slow once.
    Subsequent calls: ~250 ms per page on the M4 Pro CPU.

Sandbox / CI behavior:
    The wrapper imports `doctr` lazily. If the package is not installed,
    HAS_DOCTR is False and `extract_text_regions()` returns an empty
    result with an explicit "doctr_not_installed" warning. The tier
    router falls through to Tier 2 (Gemini) automatically.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from pathlib import Path
from typing import Any
import logging

log = logging.getLogger(__name__)

# Lazy import. The doctr package pulls in PyTorch which is multi-GB and
# may not be present in CI / sandbox. We probe at import time, store the
# flag, and never fail at module load.
try:
    import doctr  # noqa: F401
    HAS_DOCTR = True
except (ImportError, OSError, ModuleNotFoundError):
    HAS_DOCTR = False


# Confidence values DocTR returns. We map to a normalized float in
# [0.0, 1.0] for the tier router.
DOCTR_DEFAULT_CONFIDENCE = 0.92  # DocTR is quite accurate on printed text


class DocTRWrapper:
    """Tier 1 OCR wrapper.

    Stateless except for an optional cached predictor instance. The
    predictor is the expensive object (loads model weights once), so
    repeated calls reuse it.

    Public surface:
        extract_text_regions(image_path) -> list[dict]
        extract_text_only(image_path) -> str
        is_available() -> bool
    """

    def __init__(self, det_arch: str = "db_resnet50",
                 reco_arch: str = "crnn_vgg16_bn",
                 pretrained: bool = True):
        """Set up wrapper config. Predictor is lazy-loaded on first call."""
        self.det_arch = det_arch
        self.reco_arch = reco_arch
        self.pretrained = pretrained
        self._predictor = None
        self._available = HAS_DOCTR

    @staticmethod
    def is_available() -> bool:
        """True if the doctr package imported successfully."""
        return HAS_DOCTR

    def _get_predictor(self):
        """Lazy load. Avoids paying the model-download cost when the
        wrapper is constructed but never actually used."""
        if self._predictor is not None:
            return self._predictor
        if not HAS_DOCTR:
            return None
        try:
            from doctr.models import ocr_predictor
            self._predictor = ocr_predictor(
                det_arch=self.det_arch,
                reco_arch=self.reco_arch,
                pretrained=self.pretrained,
            )
            return self._predictor
        except Exception as e:  # pragma: no cover (env dependent)
            log.warning("DocTR predictor init failed: %s", e)
            self._available = False
            return None

    def extract_text_regions(self, image_path: str | Path) -> dict:
        """Extract text regions with bounding boxes.

        Returns:
            {
                "success": bool,
                "regions": list of {"text", "bbox", "confidence"},
                "full_text": str,
                "tier": "doctr",
                "warnings": list[str],
            }

        On a sandbox without doctr installed, returns success=False with
        warnings=["doctr_not_installed"] so the tier router can fall
        through to Gemini.
        """
        if not HAS_DOCTR:
            return self._unavailable_result()

        path = Path(image_path)
        if not path.exists():
            return {
                "success": False,
                "regions": [],
                "full_text": "",
                "tier": "doctr",
                "warnings": [f"image_not_found: {path}"],
            }

        predictor = self._get_predictor()
        if predictor is None:
            return self._unavailable_result()

        try:
            from doctr.io import DocumentFile
            doc = DocumentFile.from_images(str(path))
            result = predictor(doc)
            return self._format_result(result)
        except Exception as e:  # pragma: no cover (runtime dep)
            log.warning("DocTR inference failed: %s", e)
            return {
                "success": False,
                "regions": [],
                "full_text": "",
                "tier": "doctr",
                "warnings": [f"doctr_runtime_error: {e}"],
            }

    def extract_text_only(self, image_path: str | Path) -> str:
        """Convenience: return only the joined text string."""
        r = self.extract_text_regions(image_path)
        return r.get("full_text", "")

    def _unavailable_result(self) -> dict:
        return {
            "success": False,
            "regions": [],
            "full_text": "",
            "tier": "doctr",
            "warnings": ["doctr_not_installed"],
        }

    def _format_result(self, result: Any) -> dict:
        """Convert DocTR's nested page/block/line/word output into a flat
        list of regions the rest of the codebase can consume."""
        regions = []
        full_text_parts = []
        try:
            export = result.export()
        except AttributeError:  # pragma: no cover
            return {
                "success": False,
                "regions": [],
                "full_text": "",
                "tier": "doctr",
                "warnings": ["doctr_export_failed"],
            }

        for page in export.get("pages", []):
            for block in page.get("blocks", []):
                for line in block.get("lines", []):
                    line_text_parts = []
                    line_words = []
                    line_confs = []
                    for word in line.get("words", []):
                        text = word.get("value", "")
                        conf = float(word.get("confidence", 0.0))
                        bbox = word.get("geometry", [])
                        line_text_parts.append(text)
                        line_words.append({
                            "text": text,
                            "bbox": bbox,
                            "confidence": conf,
                        })
                        line_confs.append(conf)
                    if line_text_parts:
                        line_text = " ".join(line_text_parts)
                        line_conf = sum(line_confs) / len(line_confs) \
                                    if line_confs else 0.0
                        regions.append({
                            "text": line_text,
                            "bbox": line.get("geometry", []),
                            "confidence": line_conf,
                            "words": line_words,
                        })
                        full_text_parts.append(line_text)

        return {
            "success": True,
            "regions": regions,
            "full_text": "\n".join(full_text_parts),
            "tier": "doctr",
            "warnings": [],
        }
