"""Photo QC verification (Phase 26, v5.8.0).

After a piece is fabricated, the worker takes a photo. OpenCV detects
circular features (bolt holes) and compares against expected CNC
coordinates. Flags deviations > 1/16" (AISC tolerance).

A $50 rework in the shop becomes a $5,000 field fix if it ships wrong.

Uses OpenCV (already installed).

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# AISC bolt hole tolerance: 1/16" = 0.0625"
TOLERANCE_IN = 0.0625


def detect_holes_in_photo(
    photo_path: str,
    min_radius_px: int = 5,
    max_radius_px: int = 50,
) -> list[dict]:
    """Detect circular features (bolt holes) in a fabrication photo.

    Returns list of detected circles with center (x, y) and radius
    in pixel coordinates.
    """
    if not HAS_CV2:
        return []

    # pass 10i (R7): path-guard cv2.imread to silence the
    # "imread_(''): can't open/read file" libpng warnings that
    # were polluting the Owner's chat output. cv2.imread does NOT
    # raise on empty/missing paths - it returns None but still
    # prints a warning to stderr. Guard upstream.
    import os as _os
    if not photo_path or not _os.path.exists(photo_path):
        return []

    img = cv2.imread(photo_path)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (9, 9), 2)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_radius_px * 3,
        param1=100,
        param2=30,
        minRadius=min_radius_px,
        maxRadius=max_radius_px,
    )

    holes = []
    if circles is not None:
        circles = np.round(circles[0]).astype(int)
        for i, (cx, cy, r) in enumerate(circles):
            holes.append({
                "hole_num": i + 1,
                "center_x_px": int(cx),
                "center_y_px": int(cy),
                "radius_px": int(r),
            })

    return holes


def verify_holes(
    photo_path: str,
    expected_holes: list[dict],
    pixels_per_inch: float = 96.0,
) -> dict:
    """Compare detected holes against expected CNC coordinates.

    Args:
        photo_path: Path to fabrication photo.
        expected_holes: List of dicts with x_in, y_in, dia_in.
        pixels_per_inch: Photo resolution for coordinate mapping.

    Returns:
        {
            "result": "QC_PASS" or "QC_FAIL",
            "detected_count": int,
            "expected_count": int,
            "deviations": list of dicts with hole_num, delta_in,
            "max_deviation_in": float,
        }
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.52; needs manual audit)
    if not HAS_CV2:
        return {"result": "SKIP", "error": "cv2_not_installed",
                "detected_count": 0, "expected_count": len(expected_holes)}

    detected = detect_holes_in_photo(photo_path)

    if not detected:
        return {
            "result": "QC_FAIL",
            "reason": "no holes detected in photo",
            "detected_count": 0,
            "expected_count": len(expected_holes),
            "deviations": [],
            "max_deviation_in": 0.0,
        }

    # Convert detected pixel coords to inches
    detected_in = []
    for h in detected:
        detected_in.append({
            "x_in": h["center_x_px"] / pixels_per_inch,
            "y_in": h["center_y_px"] / pixels_per_inch,
        })

    # Match each expected hole to nearest detected hole
    deviations = []
    max_dev = 0.0
    for i, exp in enumerate(expected_holes):
        ex = float(exp.get("x_in", 0))
        ey = float(exp.get("y_in", 0))
        best_dist = float("inf")
        for det in detected_in:
            dist = ((det["x_in"] - ex) ** 2 + (det["y_in"] - ey) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
        deviations.append({
            "hole_num": i + 1,
            "expected_x": ex,
            "expected_y": ey,
            "delta_in": round(best_dist, 4),
            "within_tolerance": best_dist <= TOLERANCE_IN,
        })
        max_dev = max(max_dev, best_dist)

    all_pass = all(d["within_tolerance"] for d in deviations)
    count_match = abs(len(detected) - len(expected_holes)) <= 1

    result = "QC_PASS" if (all_pass and count_match) else "QC_FAIL"

    return {
        "result": result,
        "detected_count": len(detected),
        "expected_count": len(expected_holes),
        "deviations": deviations,
        "max_deviation_in": round(max_dev, 4),
        "tolerance_in": TOLERANCE_IN,
    }
