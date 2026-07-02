"""Gemini Tier 2 adapter.

Bridges the tier router to the existing Phase 1-5 Gemini pipeline. The
router's `gemini_callable` signature is `(task, image_path, **kwargs) ->
dict`. The existing modules expect different shapes (PDF paths, crop
bytes, configured providers), so this adapter normalizes the call.

Adapter strategy by task:
    detail_vision, connection_classify
        -> read image bytes from path, call analyze_crop_with_vision
    member_detect, sheet_classify
        -> NOT implemented in Phase 7b. Returns success=False with
           "adapter_task_not_routed" so the router warns and the
           takeoff_controller keeps using its existing direct calls.
           Phase 8 (LangGraph) will reroute these.

The adapter does not call Gemini directly. It receives a `call_provider`
callable injected by `bridge/api.py` (which knows how to authenticate
against the Premium Gemini account). This keeps secrets out of this
file and matches the existing Phase 2 pattern.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from pathlib import Path
from typing import Any, Callable, Optional
import logging

log = logging.getLogger(__name__)


def make_gemini_callable(call_provider: Optional[Callable] = None) -> Callable:
    """Build a tier-router-compatible Gemini callable.

    Args:
        call_provider: The same provider callable used by Phase 2's
            analyze_crop_with_vision. Signature:
                call_provider(provider_name, model_name, envelope) -> dict
            Pass None to get an adapter that always returns
            success=False with "gemini_provider_not_wired".

    Returns:
        Callable matching the tier router's gemini_callable contract:
            f(task, image_path, **kwargs) -> dict
    """

    def _gemini(task: str, image_path: str | Path, **kwargs) -> dict:
        task_lower = (task or "").strip().lower()

        if call_provider is None:
            return {
                "success": False,
                "confidence": 0.0,
                "result": None,
                "warnings": ["gemini_provider_not_wired"],
            }

        if task_lower in ("detail_vision", "connection_classify",
                          "member_detect", "sheet_classify",
                          "spatial_classify"):
            return _route_detail_vision(call_provider, image_path, **kwargs)

        # Text-only and cross-reference tasks remain with existing direct
        # calls in preprocessor.py until Phase 8 LangGraph reroutes them.
        return {
            "success": False,
            "confidence": 0.0,
            "result": None,
            "warnings": [f"adapter_task_not_routed: {task_lower}"],
        }

    return _gemini


def _route_detail_vision(call_provider, image_path, **kwargs) -> dict:
    """Read the crop image and hand it to the existing Phase 2 pipeline."""
    p = Path(image_path)
    if not p.exists():
        return {
            "success": False, "confidence": 0.0, "result": None,
            "warnings": [f"image_not_found: {p}"],
        }
    try:
        crop_bytes = p.read_bytes()
    except Exception as e:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "warnings": [f"image_read_failed: {e}"],
        }

    try:
        from bridge.drawing_intel.detail_vision import \
            analyze_crop_with_vision
    except ImportError as e:  # pragma: no cover (env)
        return {
            "success": False, "confidence": 0.0, "result": None,
            "warnings": [f"detail_vision_import_failed: {e}"],
        }

    try:
        framing_hint = str(kwargs.get("framing_code_hint", "")).strip()
        detail = analyze_crop_with_vision(
            crop_bytes=crop_bytes,
            framing_code_hint=framing_hint,
            call_provider=call_provider,
        )
    except Exception as e:
        return {
            "success": False, "confidence": 0.0, "result": None,
            "warnings": [f"detail_vision_exception: {e}"],
        }

    # ConnectionDetail object. Pull confidence and convert to dict.
    confidence = float(getattr(detail, "confidence", 0.0))
    try:
        result_payload = detail.to_dict() \
            if hasattr(detail, "to_dict") else {}
    except Exception as e:
        result_payload = {"_to_dict_failed": str(e)}

    success = confidence > 0.0 and \
              getattr(detail, "source", "none") != "none"

    return {
        "success": success,
        "confidence": confidence,
        "result": result_payload,
        "warnings": [] if success else ["detail_vision_no_result"],
    }
