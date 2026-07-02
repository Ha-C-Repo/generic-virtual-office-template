"""F17: Column height inference for foundation-plan detections.

Foundation plans show columns in plan view (looking down). Vision sees
the symbol and reads the shape designation but cannot read the column
height because the dimension is on the elevation or section sheet, not
on the foundation plan.

v14 Frutia lost 41 column detections (page 4 / S1.1) because
length_ft=0. This module rescues those by assigning a default column
height per building_type, with an override hook for cases where the
estimator knows the actual height.

The defaults are conservative: when in doubt, do not over-assume. The
estimator can always override per-bid. If a column appears on an
elevation sheet WITH a dimensioned length, that takes precedence over
the default - this module only fills the GAP.

Per Owner: never invent. The default heights below are documented
industry rule-of-thumb for one-story construction, not engineering
calculations. Used as a stand-in until elevations are read in the
schedule-extractor pass.
"""

from __future__ import annotations


# Conservative single-story defaults. Multi-story bumps via building_type.
# Source: Houston market norms for the project portfolio (retail, fitness,
# dealership, warehouse). Tunable per bid via override_height_ft kwarg.
DEFAULT_COLUMN_HEIGHTS_FT = {
    "retail_small":      14.0,
    "retail_big_box":    18.0,
    "fitness":           18.0,
    "warehouse":         20.0,
    "office_multistory": 12.5,   # PER STORY. Multiply by stories.
    "dealership":        16.0,
    "pemb_misc_only":    14.0,   # misc steel only; canopy/lintel only
    "industrial_heavy":  22.0,
}


def default_height_for(building_type: str, stories: int = 1) -> float:
    bt = (building_type or "retail_small").lower()
    base = DEFAULT_COLUMN_HEIGHTS_FT.get(bt, 14.0)
    if bt == "office_multistory":
        return base * max(1, stories)
    return base


def is_column_detection(d: dict) -> bool:
    """A detection is a column if family is HSS or W AND member_type is
    column, OR if shape family is a known column-typical family and
    member_type is empty."""
    mt = (d.get("member_type") or "").lower()
    fam = (d.get("family") or "").upper()
    if mt == "column":
        return True
    if mt in ("beam", "joist", "plate", "misc"):
        return False
    # Empty member_type: lean on family. HSS and W-shapes < W14 are
    # usually columns. Anything else stays a beam unless explicitly
    # marked.
    if fam == "HSS":
        return True
    return False


def infer_heights(detections: list[dict],
                  building_type: str,
                  override_height_ft: float | None = None,
                  stories: int = 1) -> dict:
    """Fill in length_ft for column detections that have length_ft=0.

    Mutates detections in place. Returns a report dict with counts.
    """
    height = override_height_ft or default_height_for(building_type, stories)
    inferred = 0
    skipped = 0
    for d in detections:
        if not is_column_detection(d):
            continue
        cur = float(d.get("length_ft") or 0)
        if cur > 0:
            skipped += 1
            continue
        d["length_ft"] = height
        d.setdefault("notes", [])
        if isinstance(d["notes"], list):
            d["notes"].append(f"column height inferred = {height:.1f} ft")
        d["height_inferred"] = True
        inferred += 1
    return {
        "column_height_used_ft": height,
        "columns_with_inferred_height": inferred,
        "columns_with_explicit_height": skipped,
        "source": "override" if override_height_ft else f"default[{building_type}]",
    }
