"""Dual/triple extraction orchestrator (Phase 20, v5.2.0).

Sends the same structural drawing page to multiple AI providers for
independent extraction, then runs diff_engine to compare results.

The extraction prompts are identical across providers so differences
in output reflect genuine model disagreement, not prompt variance.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Any, Callable, Optional

from .diff_engine import diff_extractions

log = logging.getLogger(__name__)


EXTRACT_PROMPT = (
    "Extract all structural steel members from this drawing page. "
    "For each member, return: mark (piece mark), shape (W/HSS/L/C/WT), "
    "size (e.g., 14X22), length_ft, qty, grade. "
    "Return JSON array only. No commentary."
)


def cross_verify_page(
    page_image_b64: str = "",
    providers: dict[str, Callable] | None = None,
    pre_extracted: dict[str, list[dict]] | None = None,
) -> dict:
    """Run cross-verification on a single drawing page.

    Two modes:
    1. Live mode: pass providers dict mapping name to callable.
       Each callable receives (prompt, image_b64) and returns list[dict].
    2. Pre-extracted mode: pass pre_extracted dict mapping provider
       name to already-extracted member lists (for testing or when
       extraction was done in a prior step).

    Returns diff_extractions result.
    """
    if pre_extracted:
        return diff_extractions(pre_extracted)

    if not providers:
        return {
            "providers": [],
            "summary": "No providers configured. Pass providers dict "
                       "or pre_extracted results.",
            "agreed": [],
            "discrepancies": [],
            "agreement_pct": 0.0,
            "confidence_boost": 0.0,
        }

    results: dict[str, list[dict]] = {}
    for name, extract_fn in providers.items():
        try:
            members = extract_fn(EXTRACT_PROMPT, page_image_b64)
            if isinstance(members, list):
                results[name] = members
            else:
                log.warning("provider %s returned non-list: %s",
                           name, type(members))
                results[name] = []
        except Exception as e:
            log.warning("provider %s failed: %s", name, e)
            results[name] = []

    return diff_extractions(results)
