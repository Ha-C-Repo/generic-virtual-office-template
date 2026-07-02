"""
Misc Steel Detection Package
============================
Phase 5 of the post-parity roadmap (v3.9.0). Detects miscellaneous steel
items that the structural-only pipeline misses: stairs, railings, lintels,
and connection/base plates. Houston-area projects typically include
5-15 percent misc steel by tonnage. On a 200-ton job that is 10-30 tons
of unbilled work without this module.

Public entry points:

    detect_railings(text_or_pages)   -> list[dict]
    detect_stairs(text_or_pages)     -> list[dict]
    detect_lintels(text_or_pages)    -> list[dict]
    detect_plates(text_or_pages)     -> list[dict]
    detect_misc_steel(text_or_pages) -> dict   # all four plus rollup

Voice rules: zero em-dashes. Hyphens or periods only.
"""


from bridge.misc_steel.railing_detector import detect_railings
from bridge.misc_steel.stair_detector import detect_stairs
from bridge.misc_steel.lintel_detector import detect_lintels
from bridge.misc_steel.plate_detector import detect_plates
from bridge.misc_steel.misc_calculator import (
    aggregate_misc_steel,
    detect_misc_steel,
    misc_to_tekla_items,
)

__all__ = [
    "detect_railings",
    "detect_stairs",
    "detect_lintels",
    "detect_plates",
    "aggregate_misc_steel",
    "detect_misc_steel",
    "misc_to_tekla_items",
]
