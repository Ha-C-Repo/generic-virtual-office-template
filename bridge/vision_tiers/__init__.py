"""Three-tier vision package (Phase 7, v4.0.0).

Tier 1 (DocTR):    Local OCR. Free. Text extraction from schedules,
                   callouts, title blocks, piece marks. Runs on the Mac
                   Mini M4 with no network call.
Tier 2 (Gemini):   Production visual model. Identifies AISC shapes,
                   classifies sheets, parses connection details. Wraps
                   the existing Phase 1-5 pipeline.
Tier 3 (GPT-4o):   Cross-sheet reasoning and ambiguity resolution.
                   Reached through OpenRouter. Hard-disabled if the API
                   key is absent so the build never makes an unauthorized
                   paid call.

Routing is driven by the task type and the previous tier's confidence.
A text-only task starts at Tier 1. A structural task starts at Tier 2.
Tier 3 is only invoked when the upstream tier reports confidence below
the configured threshold (default 0.85) and tier-3 escalation is enabled
in `data/governance.json`.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .tier_router import (
    TierRouter, TierResult, TIER_NAMES,
    SUBTASK_ROUTING, classify_subtask,
)
from .doctr_wrapper import DocTRWrapper, HAS_DOCTR
from .cost_tracker import CostTracker, TIER_COST_PER_CALL
from .gpt4o_wrapper import (
    gpt4o_callable,
    HAS_OPENROUTER,
    get_openrouter_key,
)
from .gemini_adapter import make_gemini_callable
from .claude_adapter import make_claude_callable, get_claude_key

__all__ = [
    "TierRouter",
    "TierResult",
    "TIER_NAMES",
    "SUBTASK_ROUTING",
    "classify_subtask",
    "DocTRWrapper",
    "HAS_DOCTR",
    "CostTracker",
    "TIER_COST_PER_CALL",
    "gpt4o_callable",
    "HAS_OPENROUTER",
    "get_openrouter_key",
    "make_gemini_callable",
    "make_claude_callable",
    "get_claude_key",
]
