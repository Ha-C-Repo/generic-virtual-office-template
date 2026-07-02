"""ASTM and AISC reference values surfaced as on-screen helper text and stored
with MTR capture at Gate 1.

These are QUICK REFERENCES for the inspector to confirm against the controlled
standard, not a substitute for it. Mechanical values are the specified ASTM
minimums for the grade; the inspector records the ACTUAL value off the MTR and
confirms it meets or exceeds the minimum. The app never invents a value and never
overrides the MTR. No em-dashes anywhere (user-facing).
"""

# Specified ASTM minimum mechanical properties, ksi. fy = yield, fu = tensile.
# Carbon equivalent (CE) is product-specific and supplementary, so it is recorded
# from the MTR rather than asserted here.
ASTM_MIN = {
    "A992":         {"fy": 50,  "fu": 65},   # W-shapes
    "A500 GR C":    {"fy": 50,  "fu": 62},   # HSS (rectangular; round Fy is 46)
    "A36":          {"fy": 36,  "fu": 58},   # plates, bars, angles
    "F1554 GR 36":  {"fy": 36,  "fu": 58},   # anchor rods
    "F1554 GR 55":  {"fy": 55,  "fu": 75},
    "F1554 GR 105": {"fy": 105, "fu": 125},
}

ASTM_GRADES = tuple(ASTM_MIN.keys())


def astm_minimum(grade):
    """Reference minimums (fy, fu) in ksi for a grade, or None if unknown.
    Grade match is case and space insensitive."""
    if not grade:
        return None
    return ASTM_MIN.get(grade.strip().upper())


def astm_reference_text(grade):
    """Helper-text line of the specified minimums for a grade, for on-screen
    display at Gate 1. Empty string when the grade is unknown."""
    m = astm_minimum(grade)
    if not m:
        return ""
    return (f"ASTM {grade.strip().upper()} specified minimum: Fy {m['fy']} ksi, "
            f"Fu {m['fu']} ksi. Record the actual MTR value and confirm it meets "
            f"or exceeds the minimum.")


def astm_shortfall(grade, fy, fu):
    """Flag (do not block) when a recorded Fy or Fu is below the specified ASTM
    minimum for the grade. Returns a warning string or '' . Verify-do-not-generate:
    this surfaces a possible nonconformance for a human to act on; it never edits
    the value or blocks on its own."""
    m = astm_minimum(grade)
    if not m:
        return ""
    short = []
    try:
        if fy is not None and fy != "" and float(fy) < m["fy"]:
            short.append(f"Fy {fy} ksi below A-min {m['fy']} ksi")
    except (ValueError, TypeError):
        pass
    try:
        if fu is not None and fu != "" and float(fu) < m["fu"]:
            short.append(f"Fu {fu} ksi below A-min {m['fu']} ksi")
    except (ValueError, TypeError):
        pass
    if not short:
        return ""
    return (f"MTR value below the specified ASTM minimum for {grade}: "
            + "; ".join(short) + ". Open a Material nonconformance NCR.")


# AISC 303-22 Code of Standard Practice, Section 6.4 fabrication tolerances.
# Quoted as a reference; the inspector confirms the controlling case against the
# controlled standard.
AISC_303_LENGTH_TOL = (
    "AISC 303-22 Sec 6.4.1 length tolerance: +/- 1/16 in for members 30 ft or "
    "less, +/- 1/8 in over 30 ft (framed or connected to other steel); 1/32 in "
    "when both ends are finished for contact bearing. Confirm the controlling case.")

AISC_303_STRAIGHTNESS_REF = (
    "AISC 303-22 Sec 6.4.2 / ASTM A6: member straightness (sweep and camber) is "
    "held to the ASTM A6 mill tolerance for the member type. Confirm the limit "
    "for this section and length.")


# High-strength structural bolting (RCSC Specification / ASTM F3125). The assembly
# types the shop receives. F1852 and F2280 are the twist-off tension-control
# equivalents of A325 and A490. Receiving records the assembly type, the ROCAP
# (rotational-capacity) test lot number, and the marking and cert checks; acceptance
# is enforced by db.fastener_receiving_blocked_reason. No em-dashes (user-facing).
FASTENER_ASSEMBLY_TYPES = ("A325", "A490", "F1852", "F2280")

RCSC_F3125_RECEIVING_REF = (
    "RCSC Spec / ASTM F3125 high-strength bolting: record the ROCAP test lot number "
    "and verify bolt, nut and washer head and nut markings. Galvanized assemblies "
    "require the lubrication check. Bolt, nut and washer must share the ROCAP lot "
    "number used in the connection. Confirm against the controlled standard.")
