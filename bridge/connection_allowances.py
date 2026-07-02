"""
Connection allowance lookup. Authority: Ivan email 2026-05-27 Q3.

Maps a detected structural system to a default connection allowance
expressed as percent of structural tonnage. Used by the bid pricing
pipeline to compute the connection-material line automatically instead
of estimators picking a number by feel.

The percentages cover clip angles, plates, shear tabs, stiffeners,
gussets, and bolts. They do not cover anchor rods (see anchor_rules.py).
"""

from __future__ import annotations
import json
import logging
from pathlib import Path

log = logging.getLogger("bridge.connection_allowances")


CONNECTION_ALLOWANCES_PCT = {
    "tilt_wall_plus_bar_joists_plus_HSS_framing": 8,
    "tilt_wall_plus_WF_beams_plus_bar_joists":    10,
    "braced_frame_all_simple":                    8,
    "moment_frame_perimeter_simple_interior":     12,
    "full_moment_frame":                          15,
    "PEMB_primary_with_conventional_secondary":   6,
    "standard_low_rise_commercial":               10,
}


def _load_from_ivan() -> dict:
    """Refresh the table from data/calibration/ivan_confirmed_2026Q2.json."""
    p = Path(__file__).resolve().parent.parent / "data" / "calibration" / "ivan_confirmed_2026Q2.json"
    if not p.exists():
        return CONNECTION_ALLOWANCES_PCT
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        src = data.get("connection_allowance_pct_of_structural_tonnage", {})
        merged = dict(CONNECTION_ALLOWANCES_PCT)
        for k, v in src.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and "pct" in v:
                merged[k] = v["pct"]
        return merged
    except Exception as e:
        log.warning("Could not load Ivan calibration: %s", e)
        return CONNECTION_ALLOWANCES_PCT


CONNECTION_ALLOWANCES_PCT = _load_from_ivan()


def lookup_allowance(structural_system: str) -> dict:
    """Return the default connection allowance for a structural system.

    Args:
        structural_system: The structural system key. Must match one of
            the keys in CONNECTION_ALLOWANCES_PCT, or be passed as
            free text and we will try to match.

    Returns:
        dict with keys:
            pct: int, the percentage of structural tonnage
            matched_key: str, the key we looked up
            confidence: "high" if exact match, "low" if fuzzy

    The result is never None. Unknown systems fall back to
    standard_low_rise_commercial at 10% with confidence=low.
    """
    key = structural_system.strip().lower().replace(" ", "_").replace("-", "_")
    # Exact match
    if key in CONNECTION_ALLOWANCES_PCT:
        return {"pct": CONNECTION_ALLOWANCES_PCT[key], "matched_key": key, "confidence": "high"}
    # Substring match (best effort)
    for k, v in CONNECTION_ALLOWANCES_PCT.items():
        if k in key or key in k:
            return {"pct": v, "matched_key": k, "confidence": "low"}
    # Fallback
    return {
        "pct": CONNECTION_ALLOWANCES_PCT["standard_low_rise_commercial"],
        "matched_key": "standard_low_rise_commercial",
        "confidence": "low",
    }
