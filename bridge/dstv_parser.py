"""
Your Company Virtual Office - DSTV/NC1 Parser

Parses DSTV (.nc / .nc1) files from Tekla Structures, SDS2, and Advance Steel.
DSTV is the universal exchange format for beams, plates, angles, and channels.

Extracts: mark numbers, profiles, lengths, hole patterns, copes, beveling.
Drives: nesting, shop-floor barcoding, weight totals, surface-area calcs.

Reference: DSTV format specification (Stahlbau-Verlags-GmbH)
"""

import re, os
from pathlib import Path

# Steel density: 0.2836 lb/in³ = 490 lb/ft³
STEEL_DENSITY_LB_IN3 = 0.2836

# Common AISC profiles to unit weight (lb/ft) - subset for quick lookup
_PROFILE_WEIGHTS = {
    "W8X10": 10, "W8X13": 13, "W8X18": 18, "W8X21": 21, "W8X24": 24,
    "W10X12": 12, "W10X15": 15, "W10X22": 22, "W10X26": 26, "W10X33": 33,
    "W12X14": 14, "W12X16": 16, "W12X19": 19, "W12X22": 22, "W12X26": 26,
    "W12X30": 30, "W12X35": 35, "W12X40": 40, "W12X50": 50, "W12X65": 65,
    "W14X22": 22, "W14X26": 26, "W14X30": 30, "W14X34": 34, "W14X38": 38,
    "W14X43": 43, "W14X48": 48, "W14X53": 53, "W14X61": 61, "W14X68": 68,
    "W16X26": 26, "W16X31": 31, "W16X36": 36, "W16X40": 40, "W16X45": 45,
    "W18X35": 35, "W18X40": 40, "W18X46": 46, "W18X50": 50, "W18X55": 55,
    "W21X44": 44, "W21X50": 50, "W21X57": 57, "W21X62": 62, "W21X68": 68,
    "W24X55": 55, "W24X62": 62, "W24X68": 68, "W24X76": 76, "W24X84": 84,
    "W27X84": 84, "W27X94": 94, "W30X90": 90, "W30X99": 99, "W33X118": 118,
    "W36X135": 135, "W36X150": 150, "W36X160": 160, "W36X170": 170,
}


def parse_nc1(filepath: str) -> dict:
    """Parse a single DSTV NC1 file.
    
    Returns: {mark, profile, length_mm, length_in, holes, copes, weight_lb, operations}
    """
    path = Path(filepath)
    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    except Exception as e:
        return {"error": str(e)}

    result = {
        "filename": path.name,
        "mark": "",
        "profile": "",
        "material": "",
        "length_mm": 0,
        "length_in": 0,
        "weight_lb": 0,
        "holes": [],
        "copes": [],
        "operations": [],
        "raw_header": [],
    }

    # DSTV header block (ST record)
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # ST block - header identification
        if line.startswith("ST"):
            if i + 1 < len(lines):
                result["mark"] = lines[i + 1].strip()
            if i + 2 < len(lines):
                result["profile"] = lines[i + 2].strip().upper().replace(" ", "")
            if i + 3 < len(lines):
                result["material"] = lines[i + 3].strip()
            if i + 4 < len(lines):
                try:
                    result["length_mm"] = float(lines[i + 4].strip())
                    result["length_in"] = round(result["length_mm"] / 25.4, 2)
                except Exception:pass

        # BO block - holes/borings
        elif line.startswith("BO"):
            hole_block = {"type": "hole", "positions": []}
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith(("BO", "AK", "IK", "SI", "EN")):
                parts = lines[j].strip().split()
                if len(parts) >= 3:
                    try:
                        hole_block["positions"].append({
                            "x": float(parts[0]),
                            "y": float(parts[1]),
                            "diameter": float(parts[2]),
                        })
                    except Exception:pass
                j += 1
            if hole_block["positions"]:
                result["holes"].append(hole_block)
                result["operations"].append(f"HOLES: {len(hole_block['positions'])} holes")

        # AK block - copes/notches
        elif line.startswith("AK"):
            result["copes"].append({"line": i, "data": line})
            result["operations"].append(f"COPE at line {i}")

        # IK block - contour cuts
        elif line.startswith("IK"):
            result["operations"].append(f"CONTOUR CUT at line {i}")

        # SI block - slotted holes
        elif line.startswith("SI"):
            result["operations"].append(f"SLOT at line {i}")

        # EN block - end of piece
        elif line.startswith("EN"):
            break

        result["raw_header"].append(line)
        i += 1

    # Calculate weight
    profile_key = result["profile"].upper().replace(" ", "")
    plf = _PROFILE_WEIGHTS.get(profile_key, 0)
    if plf > 0 and result["length_in"] > 0:
        result["weight_lb"] = round(plf * result["length_in"] / 12, 1)
    
    result["hole_count"] = sum(len(h["positions"]) for h in result["holes"])
    result["cope_count"] = len(result["copes"])
    result["operation_count"] = len(result["operations"])

    return result


def parse_directory(dirpath: str) -> dict:
    """Parse all NC1 files in a directory. Returns BOM summary."""
    path = Path(dirpath)
    if not path.is_dir():
        return {"error": f"Not a directory: {dirpath}"}

    pieces = []
    total_weight = 0
    total_holes = 0
    profiles = {}

    for f in sorted(path.glob("*.nc1")) + sorted(path.glob("*.nc")):
        p = parse_nc1(str(f))
        if "error" not in p:
            pieces.append(p)
            total_weight += p.get("weight_lb", 0)
            total_holes += p.get("hole_count", 0)
            prof = p.get("profile", "UNKNOWN")
            profiles[prof] = profiles.get(prof, 0) + 1

    return {
        "directory": str(path),
        "piece_count": len(pieces),
        "total_weight_lb": round(total_weight, 1),
        "total_weight_tons": round(total_weight / 2000, 2),
        "total_holes": total_holes,
        "profiles": profiles,
        "pieces": pieces,
    }


def bom_summary(pieces: list) -> str:
    """Generate a text BOM from parsed pieces."""
    if not pieces:
        return "No pieces parsed."
    lines = [f"{'Mark':<12} {'Profile':<14} {'Length(in)':<12} {'Weight(lb)':<12} {'Holes':<6}"]
    lines.append("-" * 60)
    for p in pieces:
        lines.append(f"{p.get('mark',''):<12} {p.get('profile',''):<14} "
                     f"{p.get('length_in',0):<12.1f} {p.get('weight_lb',0):<12.1f} "
                     f"{p.get('hole_count',0):<6}")
    total_w = sum(p.get("weight_lb", 0) for p in pieces)
    lines.append("-" * 60)
    lines.append(f"TOTAL: {len(pieces)} pieces, {total_w:.0f} lbs ({total_w/2000:.2f} tons)")
    return "\n".join(lines)
