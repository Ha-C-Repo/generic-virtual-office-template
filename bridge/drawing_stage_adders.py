"""
Drawing-stage adders. Authority: Ivan email 2026-05-27 Q6.

Applies a risk premium to the base bid based on drawing completeness.
The adder covers the risk that quantities shift between bid stage and
construction.
"""

from __future__ import annotations
import re


STAGE_ADDERS_PCT = {
    "schematic":  18,
    "DD":         18,
    "schematic_or_DD": 18,
    "50_CD":      12,
    "50_pct_CD":  12,
    "50pctCD":    12,
    "90_CD":       5,
    "90_pct_CD":   5,
    "90pctCD":     5,
    "100_IFC":     0,
    "IFC":         0,
    "100_pct_IFC": 0,
    "IFB":         3,
    "bid_set":     3,
    "IFB_bid_set": 3,
}


def normalize_stage(label: str) -> str:
    """Normalize a free-text drawing stage label to a canonical key."""
    s = label.strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = s.replace("percent", "pct").replace("%", "pct")
    # Common aliases
    if "schem" in s or s == "dd":
        return "schematic_or_DD"
    if "50" in s and "cd" in s:
        return "50_pct_CD"
    if "90" in s and "cd" in s:
        return "90_pct_CD"
    if "ifc" in s:
        return "100_pct_IFC"
    if "ifb" in s or "bid_set" in s:
        return "IFB_bid_set"
    return s


def adder_pct_for_stage(label: str) -> dict:
    """Look up the adder percent for a drawing stage label.

    Returns:
        dict with keys:
            pct: int, the adder percentage
            normalized: str, the canonical key
            confidence: "high" if matched, "low" if defaulted
    """
    key = normalize_stage(label)
    if key in STAGE_ADDERS_PCT:
        return {"pct": STAGE_ADDERS_PCT[key], "normalized": key, "confidence": "high"}
    return {"pct": 0, "normalized": key, "confidence": "low"}


def apply_adder(base_bid_dollars: float, stage_label: str) -> dict:
    """Apply the stage adder to a base bid total.

    Returns:
        dict with keys:
            base: float, input base bid
            adder_pct: int
            adder_dollars: float
            adjusted_total: float
            stage_normalized: str
            confidence: str
    """
    lookup = adder_pct_for_stage(stage_label)
    adder_dollars = base_bid_dollars * (lookup["pct"] / 100.0)
    return {
        "base": base_bid_dollars,
        "adder_pct": lookup["pct"],
        "adder_dollars": round(adder_dollars, 2),
        "adjusted_total": round(base_bid_dollars + adder_dollars, 2),
        "stage_normalized": lookup["normalized"],
        "confidence": lookup["confidence"],
    }
