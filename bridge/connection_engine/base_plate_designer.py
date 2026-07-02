"""Base plate designer per AISC Design Guide 1.

Sizes column base plates for axial load. Checks concrete bearing
(ACI 318), plate bending (AISC Chapter J), and anchor bolt tension.
All math is deterministic. No LLM arithmetic.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
import math

log = logging.getLogger(__name__)


# Concrete bearing capacity (ACI 318-19 Section 22.8.3.2)
# phi_c * 0.85 * f'c for A1 = A2
PHI_BEARING = 0.65
FC_DEFAULT = 4.0  # ksi (4000 psi typical)

# Plate bending phi
PHI_PLATE = 0.90

# Anchor bolt (F1554 Gr. 36)
ANCHOR_FU = 58.0   # ksi
ANCHOR_FY = 36.0   # ksi
PHI_ANCHOR = 0.75

ANCHOR_AREAS = {
    0.500: 0.1963,
    0.625: 0.3068,
    0.750: 0.4418,
    0.875: 0.6013,
    1.000: 0.7854,
    1.250: 1.2272,
    1.500: 1.7671,
}


def design_base_plate(
    axial_kips: float,
    column_depth_in: float = 14.0,
    column_flange_in: float = 8.0,
    plate_grade: str = "A36",
    fc_ksi: float = 4.0,
    anchor_diameter: float = 0.75,
    num_anchors: int = 4,
) -> dict:
    """Design a column base plate for axial compression.

    Args:
        axial_kips: Factored axial load (kips, compression positive).
        column_depth_in: Column depth d (inches).
        column_flange_in: Column flange width bf (inches).
        plate_grade: A36 or A572.
        fc_ksi: Concrete compressive strength (ksi).
        anchor_diameter: Anchor bolt diameter (inches).
        num_anchors: Number of anchor bolts (typically 4).

    Returns:
        Dict with plate_width, plate_length, plate_thickness,
        capacity, dcr, status, report_lines.
    """
    report: list[str] = []
    report.append(f"BASE PLATE DESIGN - Column d={column_depth_in}in, "
                  f"bf={column_flange_in}in")
    report.append(f"Axial load Pu = {axial_kips:.1f} kips")

    Fy = 36.0 if plate_grade == "A36" else 50.0
    Fu = 58.0 if plate_grade == "A36" else 65.0

    # Plate dimensions: column + clearance
    overhang = 3.0  # inches each side
    B = round(column_flange_in + 2 * overhang, 1)  # plate width
    N = round(column_depth_in + 2 * overhang, 1)    # plate length

    # Concrete bearing capacity
    A1 = B * N
    qp = PHI_BEARING * 0.85 * fc_ksi  # ksi on A1
    bearing_cap = qp * A1
    report.append(f"Plate: {B}in x {N}in, A1 = {A1:.1f} in2")
    report.append(f"Bearing: phi*0.85*f'c = {qp:.2f} ksi, "
                  f"Cap = {bearing_cap:.1f} kips")

    # Required plate thickness per AISC DG1
    # m = (N - 0.95*d) / 2
    # n = (B - 0.80*bf) / 2
    m = (N - 0.95 * column_depth_in) / 2.0
    n = (B - 0.80 * column_flange_in) / 2.0
    fp = axial_kips / max(A1, 0.01)  # actual bearing pressure
    ell = max(m, n)

    # t_req = ell * sqrt(2*fp / (phi*Fy))
    t_req = ell * math.sqrt(2.0 * fp / max(PHI_PLATE * Fy, 0.01))
    report.append(f"m = {m:.2f}in, n = {n:.2f}in, ell = {ell:.2f}in")
    report.append(f"fp = {fp:.3f} ksi, t_req = {t_req:.3f}in")

    # Snap to standard thicknesses
    std = [0.500, 0.625, 0.750, 0.875, 1.000, 1.250, 1.500, 2.000]
    plate_t = 0.500
    for t in std:
        if t >= t_req:
            plate_t = t
            break
    else:
        plate_t = 2.000
    report.append(f"Plate thickness = {plate_t}in")

    # Check capacity
    fp_cap = PHI_PLATE * Fy * plate_t ** 2 / (2.0 * max(ell ** 2, 0.01))
    plate_cap = fp_cap * A1
    dcr_bearing = round(axial_kips / max(bearing_cap, 0.01), 3)
    dcr_plate = round(axial_kips / max(plate_cap, 0.01), 3)
    dcr = max(dcr_bearing, dcr_plate)

    # Anchor bolts (for uplift and shear)
    Ab_anchor = ANCHOR_AREAS.get(anchor_diameter, 0.4418)
    anchor_tension_cap = PHI_ANCHOR * num_anchors * ANCHOR_FU * Ab_anchor
    report.append(f"Anchors: {num_anchors} x {anchor_diameter}in F1554, "
                  f"tension cap = {anchor_tension_cap:.1f} kips")

    if dcr <= 1.0:
        status = "GREEN"
        msg = "Adequate per AISC DG1."
    elif dcr <= 1.05:
        status = "YELLOW"
        msg = "Marginal. PE review recommended."
    else:
        status = "RED"
        msg = "Overstressed. Increase plate size."

    report.append(f"DCR = {dcr:.3f}. Status: {status} - {msg}")

    return {
        "success": True,
        "plate_width_in": B,
        "plate_length_in": N,
        "plate_thickness_in": plate_t,
        "bearing_capacity_kips": round(bearing_cap, 1),
        "plate_capacity_kips": round(plate_cap, 1),
        "anchor_tension_cap_kips": round(anchor_tension_cap, 1),
        "dcr": dcr,
        "status": status,
        "status_msg": msg,
        "aisc_clause": "AISC DG1 + ACI 318-19 22.8.3.2",
        "report_lines": report,
    }
