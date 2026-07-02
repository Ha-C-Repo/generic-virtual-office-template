"""
Scope checklist additions per Ivan 2026-05-27 Q7.

This file consolidates the building-type-specific scope items that
SCOPE_CHECKLIST in bid_sanity_gates.py references. Keeping them in their
own module lets templates and proposal renderers consume the same list
without re-importing the whole gates module.
"""

from __future__ import annotations


BASE_CHECKLIST = (
    "structural_columns", "beams_girders", "bar_joists",
    "joist_girders", "roof_deck", "base_plates_anchors",
    "bracing", "misc_angles_plates",
)

TILT_WALL_MUST_FLAG = (
    "embed_plates", "joist_embeds", "caged_ladders",
    "roof_hatches_and_surrounds", "deck_closures",
    "canopy_framing", "lintels", "sill_angles",
    "base_plate_templates", "leveling_nuts",
)

MULTISTORY_AND_MEZZANINE_MUST_INCLUDE = (
    "floor_deck", "stairs_handrails", "mezzanine_framing",
)

PEMB_MUST_FLAG = (
    "secondary_framing", "misc_steel",
    "canopies", "roof_screen_framing",
)


def expected_scope(building_type: str) -> list:
    """Return the union of base + building-type additions."""
    bt = building_type.strip().lower()
    items = list(BASE_CHECKLIST)
    if bt in ("tilt_up", "tilt_wall"):
        items.extend(TILT_WALL_MUST_FLAG)
    if bt in ("office_multistory", "hotel", "mixed_use", "school", "fitness"):
        items.extend(MULTISTORY_AND_MEZZANINE_MUST_INCLUDE)
    if bt == "pemb":
        items.extend(PEMB_MUST_FLAG)
    # Building types Ivan didn't call out get canopy_framing if low-rise
    # commercial (he treats this as a default add).
    if bt in ("retail_small", "retail_big_box", "dealership",
              "fire_station", "restaurant", "gas_station",
              "hangar", "medical"):
        if "canopy_framing" not in items:
            items.append("canopy_framing")
    return items


def missing_items(building_type: str, declared_scope: list) -> list:
    """Return the items expected for `building_type` that are NOT in
    `declared_scope`. Empty list means scope is complete.
    """
    expected = set(expected_scope(building_type))
    declared = set(item.strip().lower() for item in declared_scope)
    missing = sorted(expected - declared)
    return missing
