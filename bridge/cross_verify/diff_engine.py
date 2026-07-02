"""Cross-verification diff engine (Phase 20, v5.2.0).

Compares member extraction results from two or three AI providers.
Discrepancies are flagged for human review. Agreement increases
confidence. All comparisons are deterministic string/number ops.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging

log = logging.getLogger(__name__)


def normalize_shape(s: str) -> str:
    """Normalize shape string for comparison."""
    return s.upper().replace(" ", "").replace("X", "X")


def diff_extractions(
    results: dict[str, list[dict]],
) -> dict:
    """Compare extraction results from multiple providers.

    Args:
        results: Dict mapping provider name to list of member dicts.
            Each member dict should have at least "shape" and "mark".
            Example: {"gemini": [...], "claude": [...], "gpt4o": [...]}

    Returns:
        {
            "providers": list[str],
            "provider_counts": dict (provider -> member count),
            "agreed": list[dict] (members all providers agree on),
            "discrepancies": list[dict] (members with disagreement),
            "unique_to": dict (provider -> members only that provider found),
            "agreement_pct": float,
            "confidence_boost": float (0.0 to 0.2),
            "summary": str,
        }
    """
    providers = sorted(results.keys())
    if len(providers) < 2:
        return {
            "providers": providers,
            "provider_counts": {},
            "agreed": [],
            "discrepancies": [],
            "unique_to": {},
            "agreement_pct": 0.0,
            "confidence_boost": 0.0,
            "summary": "Need at least 2 providers for cross-verification.",
        }

    # Build shape sets per provider
    provider_shapes: dict[str, dict[str, dict]] = {}
    provider_counts = {}
    for prov, members in results.items():
        shape_map = {}
        for m in members:
            key = normalize_shape(
                str(m.get("mark", "")) + "_" +
                str(m.get("shape", "")) +
                str(m.get("size", ""))
            )
            shape_map[key] = m
        provider_shapes[prov] = shape_map
        provider_counts[prov] = len(members)

    # Find intersection (all providers agree)
    all_keys = [set(provider_shapes[p].keys()) for p in providers]
    agreed_keys = all_keys[0]
    for ks in all_keys[1:]:
        agreed_keys = agreed_keys & ks

    agreed = []
    for key in sorted(agreed_keys):
        # Use first provider's data as representative
        rep = provider_shapes[providers[0]][key]
        agreed.append({
            "key": key,
            "shape": rep.get("shape", "") + rep.get("size", ""),
            "mark": rep.get("mark", ""),
            "providers_agree": len(providers),
            "status": "AGREED",
        })

    # Find discrepancies (in some but not all)
    all_union = set()
    for ks in all_keys:
        all_union |= ks
    discrepancy_keys = all_union - agreed_keys

    discrepancies = []
    unique_to: dict[str, list] = {p: [] for p in providers}
    for key in sorted(discrepancy_keys):
        found_in = [p for p in providers if key in provider_shapes[p]]
        missing_from = [p for p in providers if key not in provider_shapes[p]]

        if len(found_in) == 1:
            # Unique to one provider
            prov = found_in[0]
            m = provider_shapes[prov][key]
            unique_to[prov].append({
                "key": key,
                "shape": m.get("shape", "") + m.get("size", ""),
                "mark": m.get("mark", ""),
            })
        else:
            # Found by some but not all
            rep = provider_shapes[found_in[0]][key]
            discrepancies.append({
                "key": key,
                "shape": rep.get("shape", "") + rep.get("size", ""),
                "mark": rep.get("mark", ""),
                "found_in": found_in,
                "missing_from": missing_from,
                "status": "VERIFY",
            })

    total_unique = len(all_union)
    agreement_pct = (len(agreed_keys) / max(total_unique, 1)) * 100

    # Confidence boost: 0.0 (no agreement) to 0.2 (full agreement)
    confidence_boost = round(min(0.2, agreement_pct / 500.0), 3)

    summary = (
        f"{len(providers)} providers compared. "
        f"{len(agreed_keys)} members agreed ({agreement_pct:.0f}%). "
        f"{len(discrepancies)} discrepancies flagged for review. "
        f"Confidence boost: +{confidence_boost:.1%}."
    )

    return {
        "providers": providers,
        "provider_counts": provider_counts,
        "agreed": agreed,
        "discrepancies": discrepancies,
        "unique_to": {k: v for k, v in unique_to.items() if v},
        "agreement_pct": round(agreement_pct, 1),
        "confidence_boost": confidence_boost,
        "summary": summary,
    }
