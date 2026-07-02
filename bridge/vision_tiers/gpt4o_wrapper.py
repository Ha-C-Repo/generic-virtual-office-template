"""GPT-4o Tier 3 wrapper. Routed through OpenRouter.

Why OpenRouter, not direct OpenAI:
    The "no paid dependencies beyond the stack" rule blocks direct
    OpenAI accounts. OpenRouter provides a proxy with a single API
    key that routes to many models, billed per call. We use it as
    a controlled, capped escalation path for Tier 3.

Hard-disabled by default:
    The wrapper reads OPENROUTER_API_KEY from the environment first,
    falling back to data/governance.json. If neither is set,
    HAS_OPENROUTER is False, the callable returns success=False with
    "openrouter_not_configured" warnings, and the tier router treats
    it as if Tier 3 were disabled.

Cost tracking:
    Each call returns cost_usd in the result so the cost tracker can
    record actual spend. We approximate from token count using the
    OpenRouter pricing for openai/gpt-4o (current rate captured in
    GPT4O_INPUT_USD_PER_1K and GPT4O_OUTPUT_USD_PER_1K below).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# Lazy import. requests is in the existing stack but we still guard.
try:
    import requests  # noqa: F401
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"

# OpenRouter pricing for openai/gpt-4o, May 2026 snapshot. Joseph can
# update governance.json without touching code.
GPT4O_INPUT_USD_PER_1K = 0.0025
GPT4O_OUTPUT_USD_PER_1K = 0.01

# Default per-request safety cap. The cost_tracker has its own per-bid
# cap; this is a per-call sanity check.
MAX_OUTPUT_TOKENS = 1500

# OCR-specific prompt for high-density structural drawing crops.
# Used when task == "ocr_small_text" to maximize text extraction accuracy.
_OCR_SMALL_TEXT_PROMPT = (
    "You are a structural drawing OCR specialist. "
    "This is a high-DPI crop of a dense region from a structural steel drawing. "
    "Extract ALL text exactly as printed, including: piece marks, member "
    "designations (W-shapes, HSS, angles), weld symbols, bolt callouts, "
    "dimensions, and schedule entries. "
    "Return ONLY a JSON object with: "
    "extracted_text (list of strings, one per text element), "
    "confidence (float 0.0-1.0), "
    "notes (string with any uncertainties). "
    "Do not add any text not visible in the image."
)


def _read_governance_key() -> str:
    """Look up OpenRouter key from data/governance.json if env not set."""
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent
        gov_path = repo_root / "data" / "governance.json"
        if not gov_path.exists():
            return ""
        gov = json.loads(gov_path.read_text(encoding="utf-8"))
        # Possible nesting: vision_tiers.openrouter_api_key OR
        # api_keys.openrouter
        vt = gov.get("vision_tiers", {}) or {}
        if vt.get("openrouter_api_key"):
            return str(vt["openrouter_api_key"])
        ak = gov.get("api_keys", {}) or {}
        if ak.get("openrouter"):
            return str(ak["openrouter"])
        return ""
    except Exception as e:  # pragma: no cover (env dependent)
        log.warning("governance.json read failed: %s", e)
        return ""


def get_openrouter_key() -> str:
    """Resolve API key. Env var takes priority over governance.json."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    return _read_governance_key()


HAS_OPENROUTER = bool(get_openrouter_key())


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated USD cost for the call."""
    in_usd = (prompt_tokens / 1000.0) * GPT4O_INPUT_USD_PER_1K
    out_usd = (completion_tokens / 1000.0) * GPT4O_OUTPUT_USD_PER_1K
    return round(in_usd + out_usd, 5)


def _read_image_as_data_url(image_path: str | Path) -> str:
    """Encode an image file as a data: URL the GPT-4o vision API accepts."""
    p = Path(image_path)
    suffix = p.suffix.lower().lstrip(".")
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(suffix, "image/png")
    raw = p.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _confidence_from_response(text: str) -> float:
    """Try to recover an explicit confidence value from the model output.

    GPT-4o is prompted to return JSON with a "confidence" field. If
    parsing fails, we fall back to a conservative 0.80 - lower than
    Gemini's typical 0.92, since Tier 3 was reached precisely because
    Tier 2 confidence was already in question.
    """
    try:
        # Find the first JSON object in the text
        start = text.find("{")
        if start < 0:
            return 0.80
        end = text.rfind("}")
        if end <= start:
            return 0.80
        snippet = text[start:end + 1]
        obj = json.loads(snippet)
        c = float(obj.get("confidence", 0.80))
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, c))
    except Exception:
        return 0.80


def gpt4o_callable(
    task: str,
    image_path: str | Path,
    prompt: str | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 60.0,
    referer: str = "https://yourco.local",
    title: str = "Your Company Virtual Office",
    **kwargs,
) -> dict:
    """Tier 3 vision callable. Same return shape as the Gemini adapter.

    Returns:
        {
            "success": bool,
            "confidence": float in [0, 1],
            "result": dict (parsed JSON if available, else {"text": str}),
            "cost_usd": float,
            "warnings": list[str],
        }
    """
    if not HAS_REQUESTS:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0, "warnings": ["requests_not_installed"],
        }

    key = api_key or get_openrouter_key()
    if not key:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0, "warnings": ["openrouter_not_configured"],
        }

    p = Path(image_path)
    if not p.exists():
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0,
            "warnings": [f"image_not_found: {p}"],
        }

    if prompt is None:
        task_lower = (task or "").strip().lower()
        if task_lower == "ocr_small_text":
            prompt = _OCR_SMALL_TEXT_PROMPT
        else:
            prompt = (
                f"You are a structural steel detail reviewer. Task: {task}. "
                f"Examine the image and return ONLY a JSON object with keys: "
                f"finding (string), confidence (0.0 to 1.0), notes (string). "
                f"Do not include any prose outside the JSON."
            )

    try:
        data_url = _read_image_as_data_url(p)
    except Exception as e:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0,
            "warnings": [f"image_encode_failed: {e}"],
        }

    payload = {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": data_url}},
                ],
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": referer,
        "X-Title": title,
    }

    import requests as _r

    try:
        resp = _r.post(OPENROUTER_URL, headers=headers,
                       json=payload, timeout=timeout)
    except Exception as e:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0,
            "warnings": [f"openrouter_request_failed: {e}"],
        }

    if resp.status_code != 200:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0,
            "warnings": [
                f"openrouter_http_{resp.status_code}",
                resp.text[:300],
            ],
        }

    try:
        body = resp.json()
        choices = body.get("choices", [])
        if not choices:
            return {
                "success": False, "confidence": 0.0, "result": None,
                "cost_usd": 0.0,
                "warnings": ["openrouter_empty_choices"],
            }
        text = choices[0].get("message", {}).get("content", "") or ""
        usage = body.get("usage", {}) or {}
        cost_usd = _estimate_cost(
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
        )
        confidence = _confidence_from_response(text)

        # Try to parse the model's JSON response. If it fails, keep the
        # raw text in the result so callers can inspect.
        parsed: dict[str, Any]
        try:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                parsed = json.loads(text[start:end + 1])
            else:
                parsed = {"text": text}
        except Exception:
            parsed = {"text": text}

        return {
            "success": True,
            "confidence": confidence,
            "result": parsed,
            "cost_usd": cost_usd,
            "warnings": [],
            "raw_text": text,
            "model": model,
        }
    except Exception as e:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "cost_usd": 0.0,
            "warnings": [f"openrouter_response_parse_failed: {e}"],
        }
