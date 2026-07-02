"""
Standard exclusions canned into every client proposal.
Authority: Ivan email 2026-05-27 Q8.

The proposal renderer (bridge/bid_documents.py and related) should call
get_standard_exclusions() and add any project-specific exclusions on top.
"""

from __future__ import annotations


STANDARD_EXCLUSIONS = (
    "Concrete foundations and anchor setting",
    "Rebar and embeds by others unless specifically noted",
    "Field welding inspections and special inspections",
    "Fireproofing",
    "Touch-up beyond standard erection touch-up",
    "Roofing and waterproofing",
    "Masonry embeds unless shown on structural drawings",
    "Mechanical, electrical, and plumbing supports unless specifically detailed",
    "Surveying and layout by others",
    "Permits and testing unless noted",
    "Temporary shoring by others",
    "Deck attachment to PEMB unless specifically included",
)


def get_standard_exclusions(extra: list | None = None) -> list:
    """Return the standard exclusions plus any project-specific extras.

    Args:
        extra: Optional list of project-specific exclusion strings.

    Returns:
        list of strings, in the order they appear on the proposal.
    """
    items = list(STANDARD_EXCLUSIONS)
    if extra:
        for s in extra:
            s = s.strip()
            if s and s not in items:
                items.append(s)
    return items


def render_exclusions_block() -> str:
    """Render the exclusions as a markdown bullet list."""
    lines = ["## Not in our scope", ""]
    for item in STANDARD_EXCLUSIONS:
        lines.append(f"- {item}")
    return "\n".join(lines)
