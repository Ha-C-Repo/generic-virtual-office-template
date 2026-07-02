"""Vision tier router.

Decides which of the three vision tiers handles a given task and whether
to escalate when confidence is low. The router is the single entry point
the takeoff controller will call after Phase 7b integration.

Routing rules:
    text_extract, callout_parse, schedule_extract, title_block:
        Start at Tier 1 (DocTR). If DocTR is unavailable or returns
        success=False, fall through to Tier 2 (Gemini text mode).
    member_detect, sheet_classify, connection_classify:
        Start at Tier 2 (Gemini). If confidence < threshold AND
        Tier 3 escalation enabled AND under cost cap, escalate to
        GPT-4o for a second opinion.
    cross_reference, ambiguity_resolve:
        Start at Tier 3 directly. If Tier 3 disabled, return Tier 2
        result with a "tier3_unavailable" warning.

The router does NOT call Gemini or GPT-4o directly in Phase 7a. It owns
the routing logic and exposes hook points (gemini_callable,
gpt4o_callable) that are wired in Phase 7b. Tier 1 (DocTR) is wired
right now since it has no dependency on the existing pipeline.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import time
import logging

from .doctr_wrapper import DocTRWrapper, HAS_DOCTR
from .cost_tracker import CostTracker, TIER_COST_PER_CALL

log = logging.getLogger(__name__)


# Tier names. Order matters: index = escalation level.
TIER_NAMES = ("doctr", "gemini", "gpt4o", "claude")

# Phase 3 subtask routing: primary and crosscheck model per subtask type.
SUBTASK_ROUTING = {
    "ocr_small_text":   {"primary": "gpt4o",   "crosscheck": "claude"},
    "table_extract":    {"primary": "claude",   "crosscheck": "gemini"},
    "spatial_classify": {"primary": "gemini",   "crosscheck": "gpt4o"},
}

# Which task names map to which Phase 3 subtask type.
_SUBTASK_TASK_MAP = {
    "text_extract":        "ocr_small_text",
    "callout_parse":       "ocr_small_text",
    "piece_mark":          "ocr_small_text",
    "schedule_extract":    "table_extract",
    "title_block":         "table_extract",
    "member_detect":       "spatial_classify",
    "sheet_classify":      "spatial_classify",
    "connection_classify": "spatial_classify",
    "detail_vision":       "spatial_classify",
    "spatial_classify":    "spatial_classify",
    "cross_reference":     "table_extract",
    "ambiguity_resolve":   "table_extract",
}


def classify_subtask(task: str, hint: str = "") -> str:
    """Map a raw task name or keyword hint to a Phase 3 subtask type.

    Args:
        task:  Task name matching _TASK_TIER_MAP keys.
        hint:  Optional keyword hint (e.g., region_type from TiledInference).

    Returns:
        One of "ocr_small_text", "table_extract", "spatial_classify".
        Falls back to "ocr_small_text" when unknown (most conservative).
    """
    task_lower = (task or "").strip().lower()
    if task_lower in _SUBTASK_TASK_MAP:
        return _SUBTASK_TASK_MAP[task_lower]
    # Hint-based fallback for region_type strings from TiledInferencePipeline
    hint_lower = (hint or "").strip().lower()
    if any(k in hint_lower for k in ("schedule", "bolt", "member_schedule",
                                      "beam_schedule", "connection_schedule")):
        return "table_extract"
    if any(k in hint_lower for k in ("classify", "detect", "spatial",
                                      "section_detail", "weld_detail")):
        return "spatial_classify"
    return "ocr_small_text"

def _apply_pass_hint(tier_name: str, pass_hint: str) -> str:
    """Redirect gpt4o -> gemini when pass_hint is 'pass2_grid' (free tier)."""
    if pass_hint == "pass2_grid" and tier_name == "gpt4o":
        return "gemini"
    return tier_name


# Default confidence threshold below which Tier 2 results escalate.
DEFAULT_CONFIDENCE_THRESHOLD = 0.85

# Task -> starting tier. The router walks up the tier list from here.
_TASK_TIER_MAP = {
    "text_extract":       "doctr",
    "callout_parse":      "doctr",
    "schedule_extract":   "doctr",
    "title_block":        "doctr",
    "piece_mark":         "doctr",
    "member_detect":      "gemini",
    "sheet_classify":     "gemini",
    "connection_classify": "gemini",
    "detail_vision":      "gemini",
    "cross_reference":    "gpt4o",
    "ambiguity_resolve":  "gpt4o",
}


@dataclass
class TierResult:
    """Final result returned by TierRouter.route()."""
    success: bool
    tier_used: str
    task: str
    confidence: float
    result: Any = None
    fallback_used: bool = False
    escalated: bool = False
    duration_ms: float = 0.0
    cost_estimate_usd: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "tier_used": self.tier_used,
            "task": self.task,
            "confidence": self.confidence,
            "result": self.result,
            "fallback_used": self.fallback_used,
            "escalated": self.escalated,
            "duration_ms": self.duration_ms,
            "cost_estimate_usd": self.cost_estimate_usd,
            "warnings": self.warnings,
        }


class TierRouter:
    """Three-tier vision orchestrator.

    Hook callables are injected from Phase 7b wiring:
        gemini_callable(task, image_path, **kwargs) -> dict with
            {"success", "result", "confidence", "warnings"}
        gpt4o_callable(task, image_path, **kwargs) -> same shape.
    """

    def __init__(self,
                 cost_tracker: Optional[CostTracker] = None,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 tier3_enabled: bool = False,
                 doctr_wrapper: Optional[DocTRWrapper] = None,
                 gemini_callable: Optional[Callable] = None,
                 gpt4o_callable: Optional[Callable] = None,
                 claude_callable: Optional[Callable] = None):
        self.cost_tracker = cost_tracker or CostTracker()
        self.confidence_threshold = float(confidence_threshold)
        self.tier3_enabled = bool(tier3_enabled)
        self.doctr = doctr_wrapper or DocTRWrapper()
        self.gemini_callable = gemini_callable
        self.gpt4o_callable = gpt4o_callable
        self.claude_callable = claude_callable

    def route(self, task: str, image_path: str | Path,
              **kwargs) -> TierResult:
        """Route a vision task to the appropriate tier.

        kwargs are forwarded to the underlying tier callable. Common ones:
            page_number, dpi, prompt_override, force_tier (string),
            pass_hint (string, e.g. "pass2_grid" to redirect gpt4o -> gemini).
        """
        task = task.strip().lower()
        force_tier = kwargs.pop("force_tier", None)
        pass_hint = kwargs.pop("pass_hint", "")
        starting_tier = force_tier or _TASK_TIER_MAP.get(task, "gemini")
        starting_tier = _apply_pass_hint(starting_tier, pass_hint)

        if starting_tier == "doctr":
            return self._route_starting_at_doctr(task, image_path, **kwargs)
        if starting_tier == "gemini":
            return self._route_starting_at_gemini(task, image_path, **kwargs)
        # gpt4o
        return self._route_starting_at_gpt4o(task, image_path, **kwargs)

    # -- Per-tier entry points --------------------------------------------------

    def _route_starting_at_doctr(self, task: str, image_path,
                                 **kwargs) -> TierResult:
        warnings: list[str] = []
        t0 = time.perf_counter()
        if HAS_DOCTR:
            r = self.doctr.extract_text_regions(image_path)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            if r.get("success"):
                # DocTR's region confidences vary. We use the average of
                # word-level confidences if present, else a default.
                conf = self._doctr_confidence(r)
                self.cost_tracker.record(
                    tier="doctr", task=task, duration_ms=duration_ms,
                    confidence=conf, success=True)
                return TierResult(
                    success=True, tier_used="doctr", task=task,
                    confidence=conf, result=r, duration_ms=duration_ms,
                    cost_estimate_usd=TIER_COST_PER_CALL["doctr"],
                    warnings=r.get("warnings", []),
                )
            warnings.extend(r.get("warnings", []))
        else:
            warnings.append("doctr_not_installed")

        # Fall through to Gemini text mode
        warnings.append("fallback_to_gemini")
        gem_result = self._call_gemini(task, image_path, **kwargs)
        gem_result.fallback_used = True
        gem_result.warnings = warnings + gem_result.warnings
        return gem_result

    def _route_starting_at_gemini(self, task: str, image_path,
                                  **kwargs) -> TierResult:
        gem_result = self._call_gemini(task, image_path, **kwargs)

        # Escalate to Tier 3 if confidence is low and we are allowed
        if (gem_result.success
                and gem_result.confidence < self.confidence_threshold
                and self.tier3_enabled
                and self.cost_tracker.can_escalate_to_tier3()
                and self.gpt4o_callable is not None):
            log.info("Escalating task=%s to GPT-4o (confidence=%.2f)",
                     task, gem_result.confidence)
            gpt_result = self._call_gpt4o(task, image_path, **kwargs)
            if gpt_result.success and gpt_result.confidence > gem_result.confidence:
                gpt_result.escalated = True
                gpt_result.warnings = [
                    "escalated_from_gemini",
                    f"gemini_confidence={gem_result.confidence:.2f}",
                ] + gpt_result.warnings
                return gpt_result
            # GPT-4o did not improve - keep Gemini result
            gem_result.warnings.append("escalation_no_improvement")
        return gem_result

    def _route_starting_at_gpt4o(self, task: str, image_path,
                                 **kwargs) -> TierResult:
        if (self.tier3_enabled
                and self.cost_tracker.can_escalate_to_tier3()
                and self.gpt4o_callable is not None):
            return self._call_gpt4o(task, image_path, **kwargs)
        # Tier 3 unavailable. Fall back to Gemini with a warning.
        gem_result = self._call_gemini(task, image_path, **kwargs)
        gem_result.fallback_used = True
        gem_result.warnings = ["tier3_unavailable"] + gem_result.warnings
        return gem_result

    # -- Tier callables ---------------------------------------------------------

    def _call_gemini(self, task: str, image_path, **kwargs) -> TierResult:
        t0 = time.perf_counter()
        if self.gemini_callable is None:
            return TierResult(
                success=False, tier_used="gemini", task=task,
                confidence=0.0, duration_ms=0.0,
                warnings=["gemini_callable_not_wired"],
            )
        try:
            r = self.gemini_callable(task, image_path, **kwargs) or {}
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.cost_tracker.record(
                tier="gemini", task=task, duration_ms=duration_ms,
                confidence=0.0, success=False,
                notes=f"exception: {type(e).__name__}: {e}")
            return TierResult(
                success=False, tier_used="gemini", task=task,
                confidence=0.0, duration_ms=duration_ms,
                warnings=[f"gemini_exception: {e}"],
            )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        success = bool(r.get("success", False))
        confidence = float(r.get("confidence", 0.0))
        result_payload = r.get("result", r)
        self.cost_tracker.record(
            tier="gemini", task=task, duration_ms=duration_ms,
            confidence=confidence, success=success)
        return TierResult(
            success=success, tier_used="gemini", task=task,
            confidence=confidence, result=result_payload,
            duration_ms=duration_ms,
            cost_estimate_usd=TIER_COST_PER_CALL["gemini"],
            warnings=list(r.get("warnings", [])),
        )

    def _call_gpt4o(self, task: str, image_path, **kwargs) -> TierResult:
        t0 = time.perf_counter()
        if self.gpt4o_callable is None:
            return TierResult(
                success=False, tier_used="gpt4o", task=task,
                confidence=0.0, duration_ms=0.0,
                warnings=["gpt4o_callable_not_wired"],
            )
        try:
            r = self.gpt4o_callable(task, image_path, **kwargs) or {}
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.cost_tracker.record(
                tier="gpt4o", task=task, duration_ms=duration_ms,
                confidence=0.0, success=False,
                notes=f"exception: {type(e).__name__}: {e}")
            return TierResult(
                success=False, tier_used="gpt4o", task=task,
                confidence=0.0, duration_ms=duration_ms,
                warnings=[f"gpt4o_exception: {e}"],
            )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        success = bool(r.get("success", False))
        confidence = float(r.get("confidence", 0.0))
        result_payload = r.get("result", r)
        cost = float(r.get("cost_usd", TIER_COST_PER_CALL["gpt4o"]))
        self.cost_tracker.record(
            tier="gpt4o", task=task, duration_ms=duration_ms,
            confidence=confidence, success=success,
            cost_estimate_usd=cost)
        return TierResult(
            success=success, tier_used="gpt4o", task=task,
            confidence=confidence, result=result_payload,
            duration_ms=duration_ms, cost_estimate_usd=cost,
            warnings=list(r.get("warnings", [])),
        )

    def _call_claude(self, task: str, image_path, **kwargs) -> TierResult:
        t0 = time.perf_counter()
        if self.claude_callable is None:
            return TierResult(
                success=False, tier_used="claude", task=task,
                confidence=0.0, duration_ms=0.0,
                warnings=["claude_callable_not_wired"],
            )
        try:
            r = self.claude_callable(task, image_path, **kwargs) or {}
        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.cost_tracker.record(
                tier="claude", task=task, duration_ms=duration_ms,
                confidence=0.0, success=False,
                notes=f"exception: {type(e).__name__}: {e}")
            return TierResult(
                success=False, tier_used="claude", task=task,
                confidence=0.0, duration_ms=duration_ms,
                warnings=[f"claude_exception: {e}"],
            )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        success = bool(r.get("success", False))
        confidence = float(r.get("confidence", 0.0))
        result_payload = r.get("result", r)
        cost = float(r.get("cost_usd", TIER_COST_PER_CALL.get("claude", 0.03)))
        self.cost_tracker.record(
            tier="claude", task=task, duration_ms=duration_ms,
            confidence=confidence, success=success,
            cost_estimate_usd=cost)
        return TierResult(
            success=success, tier_used="claude", task=task,
            confidence=confidence, result=result_payload,
            duration_ms=duration_ms, cost_estimate_usd=cost,
            warnings=list(r.get("warnings", [])),
        )

    def _call_by_name(self, tier_name: str, task: str,
                      image_path, **kwargs) -> TierResult:
        """Dispatch to the right tier callable by name string."""
        if tier_name == "doctr":
            return self._route_starting_at_doctr(task, image_path, **kwargs)
        if tier_name == "gemini":
            return self._call_gemini(task, image_path, **kwargs)
        if tier_name == "gpt4o":
            return self._call_gpt4o(task, image_path, **kwargs)
        if tier_name == "claude":
            return self._call_claude(task, image_path, **kwargs)
        return TierResult(
            success=False, tier_used=tier_name, task=task,
            confidence=0.0, warnings=[f"unknown_tier: {tier_name}"],
        )

    def route_subtask(self, subtask: str, image_path,
                      **kwargs) -> TierResult:
        """Route by Phase 3 subtask type using the primary model only.

        Args:
            subtask: One of "ocr_small_text", "table_extract",
                     "spatial_classify". Use classify_subtask() to derive
                     this from a raw task name.
            image_path: Path to the image tile.
            **kwargs: Forwarded to the tier callable. Accepts pass_hint.

        Returns:
            TierResult from the primary model for this subtask.
        """
        pass_hint = kwargs.pop("pass_hint", "")
        config = SUBTASK_ROUTING.get(subtask,
                                     {"primary": "gemini", "crosscheck": "gemini"})
        primary = _apply_pass_hint(config["primary"], pass_hint)
        result = self._call_by_name(primary, subtask, image_path, **kwargs)
        self.cost_tracker.record(
            tier=primary, task=subtask, duration_ms=result.duration_ms,
            confidence=result.confidence, success=result.success,
            subtask=subtask,
            cost_estimate_usd=result.cost_estimate_usd,
        )
        return result

    def route_with_vote(self, subtask: str, image_path,
                        **kwargs) -> TierResult:
        """Dual-model vote for high-stakes extraction.

        Runs both the primary and crosscheck models for this subtask type,
        then returns the result with higher confidence. Both calls are
        logged to the cost tracker regardless of which wins.

        Args:
            subtask: One of "ocr_small_text", "table_extract",
                     "spatial_classify".
            image_path: Path to the image tile.
            **kwargs: Forwarded to both tier callables. Accepts pass_hint.

        Returns:
            Higher-confidence TierResult. The losing result's confidence
            is appended as a warning so callers can inspect the delta.
        """
        pass_hint = kwargs.pop("pass_hint", "")
        config = SUBTASK_ROUTING.get(subtask,
                                     {"primary": "gemini", "crosscheck": "gemini"})
        primary_name = _apply_pass_hint(config["primary"], pass_hint)
        cross_name = _apply_pass_hint(config["crosscheck"], pass_hint)

        primary_result = self._call_by_name(primary_name, subtask,
                                             image_path, **kwargs)
        cross_result = self._call_by_name(cross_name, subtask,
                                           image_path, **kwargs)

        # Tag both calls with the subtask for cost_by_subtask() rollup.
        for res, tier in ((primary_result, primary_name),
                          (cross_result, cross_name)):
            self.cost_tracker.record(
                tier=tier, task=subtask, duration_ms=res.duration_ms,
                confidence=res.confidence, success=res.success,
                subtask=subtask,
                cost_estimate_usd=res.cost_estimate_usd,
            )

        if cross_result.success and \
                cross_result.confidence > primary_result.confidence:
            cross_result.escalated = True
            cross_result.warnings = [
                f"vote_winner_{cross_name}_over_{primary_name}",
                f"primary_confidence={primary_result.confidence:.2f}",
            ] + cross_result.warnings
            return cross_result

        primary_result.warnings = [
            f"vote_winner_{primary_name}",
            f"crosscheck_confidence={cross_result.confidence:.2f}",
        ] + primary_result.warnings
        return primary_result

    # -- Helpers ----------------------------------------------------------------

    def _doctr_confidence(self, doctr_result: dict) -> float:
        """Average word confidence across all regions. 0.0 if empty."""
        regions = doctr_result.get("regions", [])
        if not regions:
            return 0.0
        scores = [float(r.get("confidence", 0.0)) for r in regions]
        return round(sum(scores) / len(scores), 4)

    def status(self) -> dict:
        """Snapshot of router config for the GUI status indicator."""
        return {
            "doctr_available": HAS_DOCTR,
            "gemini_wired": self.gemini_callable is not None,
            "gpt4o_wired": self.gpt4o_callable is not None,
            "claude_wired": self.claude_callable is not None,
            "tier3_enabled": self.tier3_enabled,
            "confidence_threshold": self.confidence_threshold,
            "cost_summary": self.cost_tracker.summary(),
        }
