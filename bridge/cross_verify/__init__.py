"""Cross-verification package (Phase 20, build slot 20, v5.2.0).

Run the same drawing through Gemini and Claude independently. Compare
results. Flag discrepancies for human review. Agreement boosts
confidence. No new subscriptions needed.

Voice rules: zero em-dashes. Hyphens or periods only.
"""

from .diff_engine import diff_extractions
from .dual_extract import cross_verify_page

__all__ = ["diff_extractions", "cross_verify_page"]
