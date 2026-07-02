"""
Joist series expectations per building type. Authority: Ivan 2026-05-27 Q5.

When the takeoff extracts joist tags from drawing text, this module checks
whether the series matches what Ivan expects for that building type. A
mismatch triggers a FLAG for verification instead of silently feeding the
pricing pipeline.
"""

from __future__ import annotations
import re
from typing import Iterable


# Per Ivan Q5
EXPECTED_SERIES = {
    "retail_small":      {"primary": ["K"], "depth_range": (18, 30), "notes": "K-series 18K to 30K"},
    "retail_big_box":    {"primary": ["K", "G", "LH"], "notes": "K-series + joist girders (48G, 54G). LH on larger spans."},
    "warehouse":         {"primary": ["K", "G", "LH"], "notes": "K + joist girders. LH on larger spans."},
    "tilt_wall":         {"primary": ["K", "G", "LH"], "notes": "K + joist girders. LH on larger spans."},
    "tilt_up":           {"primary": ["K", "G", "LH"], "notes": "K + joist girders. LH on larger spans."},
    "medical":           {"primary": [],               "joists_possible_in": ["roof", "mechanical_penthouse"],
                          "notes": "WF framing mostly. Joists possible in roof + mechanical penthouses."},
    "office_multistory": {"primary": [],               "joists_possible_in": ["mechanical_roof"],
                          "notes": "WF + composite deck. Joists uncommon except mechanical roofs."},
    "dealership":        {"primary": ["K", "G"],       "notes": "K + joist girders. Long-span showroom framing."},
    "church":            {"primary": ["LH", "DLH"],    "notes": "LH/DLH due to long clear spans + high roof geometry."},
    "hangar":            {"primary": ["LH", "DLH"],    "notes": "LH/DLH. Very large clear spans."},
}


_TAG_RE = re.compile(r"^(\d+)(K|LH|DLH|G)(\d+[A-Z]?)?", re.IGNORECASE)


def parse_joist_tag(tag: str) -> dict:
    """Parse a joist tag like '24K10', '28LH09', '54G8N' into parts.

    Returns:
        dict with depth (int), series (str), chord (str), raw (str).
        depth=0 if unparseable.
    """
    s = tag.strip().upper()
    m = _TAG_RE.match(s)
    if not m:
        return {"depth": 0, "series": "", "chord": "", "raw": tag}
    return {
        "depth": int(m.group(1)),
        "series": m.group(2),
        "chord": m.group(3) or "",
        "raw": tag,
    }


def flag_unexpected_joists(building_type: str, tags: Iterable[str]) -> list:
    """Compare extracted joist tags to expected series for building type.

    Returns a list of flags. Empty list means everything matches expectation.
    """
    expected = EXPECTED_SERIES.get(building_type)
    if not expected:
        return [{"flag": "no_expected_series_defined",
                 "building_type": building_type,
                 "message": f"No expected joist series defined for {building_type}. "
                            "Verify takeoff manually."}]
    flags = []
    primary = set(s.upper() for s in expected.get("primary", []))
    for tag in tags:
        parsed = parse_joist_tag(tag)
        series = parsed["series"]
        if not series:
            flags.append({"flag": "unparseable_tag", "tag": tag,
                          "message": f"Could not parse joist tag '{tag}'."})
            continue
        if primary and series not in primary:
            flags.append({
                "flag": "unexpected_series_for_building_type",
                "tag": tag,
                "series": series,
                "expected": sorted(primary),
                "building_type": building_type,
                "message": f"Tag '{tag}' is {series}-series; expected one of "
                           f"{sorted(primary)} for {building_type}. {expected.get('notes','')}",
            })
        # Depth range check (where defined)
        if "depth_range" in expected and parsed["depth"]:
            lo, hi = expected["depth_range"]
            if not (lo <= parsed["depth"] <= hi):
                flags.append({
                    "flag": "depth_outside_expected_range",
                    "tag": tag,
                    "depth": parsed["depth"],
                    "expected_range": [lo, hi],
                    "building_type": building_type,
                    "message": f"Tag '{tag}' depth {parsed['depth']}in outside expected "
                               f"{lo}-{hi}in for {building_type}.",
                })
    return flags
