"""Claude crosscheck adapter for Phase 3 subtask dual-model voting.

Roles in subtask routing:
    table_extract:   primary model, crosscheck = Gemini
    ocr_small_text:  crosscheck model, primary = GPT-4o

The adapter uses the anthropic SDK with claude-sonnet-4-6.
API key is sourced from ANTHROPIC_API_KEY env var or data/governance.json,
matching the pattern used by gpt4o_wrapper.py and the existing Bridge.

Cost estimate: $0.03 per call (conservative upper bound for image tasks).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import base64
import json
import logging
import os
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
CLAUDE_COST_PER_CALL = 0.03
MAX_TOKENS = 1024


def _read_governance_key() -> str:
    """Look up Anthropic key from data/governance.json if env not set."""
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        gov_path = repo_root / "data" / "governance.json"
        if not gov_path.exists():
            return ""
        gov = json.loads(gov_path.read_text(encoding="utf-8"))
        ak = gov.get("api_keys", {}) or {}
        if ak.get("anthropic"):
            return str(ak["anthropic"])
        return ""
    except Exception as e:
        log.warning("governance.json read failed: %s", e)
        return ""


def get_claude_key(api_key: Optional[str] = None) -> str:
    """Resolve Anthropic API key. Env var takes priority over governance.json."""
    if api_key:
        return api_key.strip()
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    return _read_governance_key()


def make_claude_callable(api_key: Optional[str] = None,
                          model: str = DEFAULT_MODEL) -> Callable:
    """Build a tier-router-compatible Claude callable.

    Args:
        api_key: Optional explicit Anthropic API key. If None, falls back
                 to ANTHROPIC_API_KEY env var then governance.json.
        model:   Anthropic model ID. Defaults to claude-sonnet-4-6.

    Returns:
        Callable matching the tier router contract:
            f(task, image_path, **kwargs) -> dict
            {"success", "confidence", "result", "cost_usd", "warnings"}
    """

    def _claude(task: str, image_path, **kwargs) -> dict:
        key = get_claude_key(api_key)
        if not key:
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0, "warnings": ["anthropic_key_not_configured"],
            }

        try:
            import anthropic
        except ImportError:
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0, "warnings": ["anthropic_sdk_not_installed"],
            }

        p = Path(image_path)
        if not p.exists():
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0, "warnings": [f"image_not_found: {p}"],
            }

        try:
            raw_bytes = p.read_bytes()
        except Exception as e:
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0, "warnings": [f"image_read_failed: {e}"],
            }

        suffix = p.suffix.lower().lstrip(".")
        media_type = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(suffix, "image/png")

        b64_data = base64.standard_b64encode(raw_bytes).decode("ascii")
        prompt_text = str(kwargs.get("prompt") or _build_prompt(task))

        try:
            client = anthropic.Anthropic(api_key=key)
            message = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64_data,
                                },
                            },
                            {"type": "text", "text": prompt_text},
                        ],
                    }
                ],
            )
        except Exception as e:
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0, "warnings": [f"claude_api_exception: {e}"],
            }

        text = ""
        try:
            text = message.content[0].text if message.content else ""
        except Exception:
            pass

        confidence = _confidence_from_text(text)
        parsed = _parse_json(text)

        return {
            "success": True,
            "confidence": confidence,
            "result": parsed,
            "cost_usd": CLAUDE_COST_PER_CALL,
            "warnings": [],
            "raw_text": text,
            "model": model,
        }

    return _claude


def _build_prompt(task: str) -> str:
    """Select the right extraction prompt for this task type."""
    task_lower = (task or "").strip().lower()
    if task_lower == "table_extract":
        return (
            "You are a structural steel schedule extractor. "
            "This is a cropped section of a structural drawing schedule or table. "
            "Extract every row exactly as printed: mark number, AISC shape designation, "
            "length, quantity, notes, connection type, weld or bolt callout. "
            "Return ONLY a JSON object with: "
            "rows (list of dicts, one per schedule row), "
            "confidence (float 0.0-1.0), "
            "notes (string with extraction uncertainties). "
            "Do not add data not visible in the image."
        )
    if task_lower == "ocr_small_text":
        return (
            "You are a structural drawing OCR specialist. "
            "This is a high-DPI crop of a dense region. "
            "Extract ALL text exactly as printed: piece marks, AISC member designations, "
            "weld symbols, bolt callouts, dimensions, and schedule entries. "
            "Return ONLY a JSON object with: "
            "extracted_text (list of strings, one per text element), "
            "confidence (float 0.0-1.0), "
            "notes (string with any uncertainties). "
            "Do not add text not visible in the image."
        )
    return (
        f"You are a structural steel drawing reviewer. Task: {task}. "
        f"Examine this drawing image and return ONLY a JSON object with: "
        f"finding (string), confidence (float 0.0-1.0), notes (string). "
        f"Do not include any prose outside the JSON."
    )


def _confidence_from_text(text: str) -> float:
    """Extract confidence float from the model JSON response."""
    try:
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            obj = json.loads(text[start:end + 1])
            c = float(obj.get("confidence", 0.80))
            return max(0.0, min(1.0, c))
    except Exception:
        pass
    return 0.80


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from model output."""
    try:
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            return json.loads(text[start:end + 1])
    except Exception:
        pass
    return {"text": text}
