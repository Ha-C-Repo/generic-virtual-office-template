"""DocTR OCR wrapper.

DocTR (Document Text Recognition) is a free, open-source OCR pipeline
from Mindee. Runs locally, supports CPU and CUDA. We use it as the
text-extraction half of Tier 1 in the three-tier vision pipeline:

    Tier 1 (this module + ollama_client): page triage + OCR locally
    Tier 2: Gemini Flash (cloud structural extraction)
    Tier 3: GPT-4o (cloud math verification)

DocTR shines on schedules, headers, title blocks, and any text-dense
region where Gemini's per-call cost would add up. The wrapper degrades
to None if DocTR is not installed, which lets the rest of the pipeline
fall through to Tier 2 untouched.

Install:
    pip install python-doctr[torch]   # CUDA path
    pip install python-doctr[tf]      # TensorFlow path
The installer's first-launch setup picks the right extra based on the
hardware profile written by hardware_detector.py.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from pathlib import Path
from typing import Any, Optional


def is_doctr_available() -> bool:
    """Cheap import probe. True if DocTR can be loaded."""
    try:
        import doctr  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class DocTRClient:
    """Lazy DocTR wrapper.

    Loads the pretrained model on first use, never at import time, so
    cold paths stay fast and the rest of the system can boot without
    DocTR installed.

    Usage:
        c = DocTRClient()
        if c.is_available():
            words = c.extract_text("/path/to/sheet.pdf")
    """

    def __init__(self,
                 detection_arch: str = "db_resnet50",
                 recognition_arch: str = "crnn_vgg16_bn",
                 use_gpu: Optional[bool] = None):
        self.detection_arch = detection_arch
        self.recognition_arch = recognition_arch
        self.use_gpu = use_gpu  # None -> auto-detect at load time
        self._model: Optional[Any] = None
        self._load_error: str = ""

    def is_available(self) -> bool:
        """Cheap check. True if DocTR is importable."""
        return is_doctr_available()

    def health_check(self) -> dict:
        """Detailed availability report for the GUI."""
        importable = is_doctr_available()
        loaded = self._model is not None
        return {
            "doctr_importable": importable,
            "model_loaded": loaded,
            "detection_arch": self.detection_arch,
            "recognition_arch": self.recognition_arch,
            "use_gpu": self.use_gpu,
            "load_error": self._load_error,
            "ready": importable and (loaded or not self._load_error),
        }

    def _ensure_model(self) -> bool:
        """Lazy-load. Returns True if model is ready."""
        if self._model is not None:
            return True
        if not is_doctr_available():
            self._load_error = "python-doctr is not installed"
            return False
        try:
            from doctr.models import ocr_predictor
            self._model = ocr_predictor(
                det_arch=self.detection_arch,
                reco_arch=self.recognition_arch,
                pretrained=True,
            )
            return True
        except Exception as e:
            self._load_error = f"DocTR load failed: {e}"
            self._model = None
            return False

    def extract_text(self, file_path: str | Path) -> dict:
        """OCR a PDF or image file.

        Returns:
            {
              "success": bool,
              "pages": [{"page": int, "text": str, "words": [...]}],
              "error": str,
            }
        """
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "pages": [],
                    "error": f"File not found: {path}"}

        if not self._ensure_model():
            return {"success": False, "pages": [], "error": self._load_error}

        try:
            from doctr.io import DocumentFile
            if path.suffix.lower() == ".pdf":
                doc = DocumentFile.from_pdf(str(path))
            else:
                doc = DocumentFile.from_images(str(path))
            result = self._model(doc)
        except Exception as e:
            return {"success": False, "pages": [],
                    "error": f"OCR failed: {e}"}

        pages_out: list[dict] = []
        try:
            export = result.export()
            for p_idx, page in enumerate(export.get("pages", [])):
                page_text_lines: list[str] = []
                words: list[dict] = []
                for block in page.get("blocks", []):
                    for line in block.get("lines", []):
                        line_words = []
                        for word in line.get("words", []):
                            value = word.get("value", "")
                            if value:
                                line_words.append(value)
                                words.append({
                                    "value": value,
                                    "confidence": word.get("confidence", 0.0),
                                    "geometry": word.get("geometry", []),
                                })
                        if line_words:
                            page_text_lines.append(" ".join(line_words))
                pages_out.append({
                    "page": p_idx,
                    "text": "\n".join(page_text_lines),
                    "words": words,
                })
        except Exception as e:
            return {"success": False, "pages": [],
                    "error": f"OCR result parse failed: {e}"}

        return {"success": True, "pages": pages_out, "error": ""}

    def extract_schedule_text(self, file_path: str | Path,
                              page_num: int = 0) -> str:
        """Convenience helper. Returns plain text for a single page,
        the way the takeoff controller's Stage 2 expects it."""
        r = self.extract_text(file_path)
        if not r["success"]:
            return ""
        for p in r["pages"]:
            if p["page"] == page_num:
                return p["text"]
        return ""
