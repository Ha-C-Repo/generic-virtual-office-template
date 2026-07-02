"""Connection standardizer for value engineering.

Analyzes bolt patterns across a project and proposes standardizing to
fewer sizes. Every unique bolt size requires a different drill bit,
punch die, and stock. Reducing variety saves setup time.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from collections import Counter

log = logging.getLogger(__name__)


# Cost per unique bolt size (setup, tooling, inventory)
SETUP_COST_PER_SIZE = 250.0  # estimated $/size/project


def analyze_bolt_patterns(connections: list[dict]) -> dict:
    """Analyze bolt pattern variety and propose standardization.

    Args:
        connections: List of connection dicts with bolt_diameter,
            bolt_type, bolt_count.

    Returns:
        {
            "current_sizes": dict (size -> count),
            "dominant_size": float,
            "dominant_type": str,
            "standardizable_count": int,
            "savings_usd": float,
            "proposal": str,
            "details": list[dict],
        }
    """
    if not connections:
        return {
            "current_sizes": {},
            "dominant_size": 0.0,
            "dominant_type": "",
            "standardizable_count": 0,
            "savings_usd": 0.0,
            "proposal": "No connections to analyze.",
            "details": [],
        }

    # Count bolt sizes and types
    size_counter: Counter = Counter()
    type_counter: Counter = Counter()
    for c in connections:
        dia = float(c.get("bolt_diameter", 0.75) or 0.75)
        btype = str(c.get("bolt_type", "A325-N") or "A325-N")
        size_counter[dia] += 1
        type_counter[btype] += 1

    dominant_size = size_counter.most_common(1)[0][0]
    dominant_type = type_counter.most_common(1)[0][0]

    # Count connections that could be standardized
    non_dominant = sum(
        count for size, count in size_counter.items()
        if size != dominant_size
    )
    unique_sizes = len(size_counter)
    sizes_eliminated = max(0, unique_sizes - 1)
    savings = sizes_eliminated * SETUP_COST_PER_SIZE

    details = []
    for size, count in sorted(size_counter.items()):
        pct = count / len(connections) * 100
        details.append({
            "bolt_diameter": size,
            "count": count,
            "pct": round(pct, 1),
            "is_dominant": size == dominant_size,
        })

    if unique_sizes <= 1:
        proposal = ("Bolt patterns are already standardized. "
                     f"All {len(connections)} connections use "
                     f'{dominant_size}" {dominant_type}.')
    else:
        proposal = (
            f"Standardize from {unique_sizes} bolt sizes to 1. "
            f'Propose {dominant_size}" {dominant_type} for all '
            f"{len(connections)} connections. {non_dominant} connections "
            f"would change. Estimated setup savings: ${savings:.0f}. "
            f"Requires PE capacity check on upsized connections."
        )

    return {
        "current_sizes": dict(size_counter),
        "dominant_size": dominant_size,
        "dominant_type": dominant_type,
        "unique_sizes": unique_sizes,
        "standardizable_count": non_dominant,
        "savings_usd": round(savings, 2),
        "proposal": proposal,
        "details": details,
    }
