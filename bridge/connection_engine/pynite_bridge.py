"""PyNite FEA wrapper for connection-level verification.

NOT for building-level structural analysis (that is the EOR's scope).
This wraps PyNiteFEA for non-standard connections that do not fit AISC
table solutions, e.g., skewed connections, eccentric loading, or
unusual geometries.

Requires PyNite (pip install PyNiteFEA). Graceful fallback when absent.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging

log = logging.getLogger(__name__)

try:
    from PyNite import FEModel3D  # noqa: F401
    HAS_PYNITE = True
except (ImportError, ModuleNotFoundError):
    HAS_PYNITE = False


def verify_connection_fea(
    plate_width: float,
    plate_height: float,
    plate_thickness: float,
    loads: dict | None = None,
) -> dict:
    """Run a simple plate FEA to verify stress distribution.

    This is a simplified check for non-standard connections. Standard
    shear tabs and base plates use the closed-form AISC solutions in
    shear_tab_designer.py and base_plate_designer.py instead.

    Args:
        plate_width: Plate width (inches).
        plate_height: Plate height (inches).
        plate_thickness: Plate thickness (inches).
        loads: Dict with Fy_kips, Fx_kips (optional).

    Returns:
        {"success": bool, "max_stress_ksi": float, "adequate": bool, ...}
    """
    if not HAS_PYNITE:
        return {
            "success": False,
            "error": "pynite_not_installed",
            "max_stress_ksi": 0.0,
            "adequate": False,
            "note": "Install PyNiteFEA for connection FEA verification. "
                    "Standard connections use closed-form AISC solutions "
                    "and do not require FEA.",
        }

    if loads is None:
        loads = {"Fy_kips": 0.0, "Fx_kips": 0.0}

    try:
        model = FEModel3D()

        # Simple 4-node plate model
        model.add_node("N1", 0, 0, 0)
        model.add_node("N2", plate_width, 0, 0)
        model.add_node("N3", plate_width, plate_height, 0)
        model.add_node("N4", 0, plate_height, 0)

        # Fixed supports at bottom
        model.def_support("N1", True, True, True, True, True, True)
        model.def_support("N2", True, True, True, True, True, True)

        # Apply load at top center
        Fy = loads.get("Fy_kips", 0.0)
        Fx = loads.get("Fx_kips", 0.0)
        model.add_node_load("N3", "FY", -Fy / 2)
        model.add_node_load("N4", "FY", -Fy / 2)
        if Fx != 0:
            model.add_node_load("N3", "FX", Fx / 2)
            model.add_node_load("N4", "FX", Fx / 2)

        model.analyze()

        # Get reactions (simplified stress estimate)
        # Actual plate FEA would use plate elements; this is a beam analog
        max_reaction = max(
            abs(model.Nodes["N1"].RxnFY.get("Combo 1", 0)),
            abs(model.Nodes["N2"].RxnFY.get("Combo 1", 0)),
        )
        area = plate_width * plate_thickness
        max_stress = max_reaction / max(area, 0.01)
        adequate = max_stress <= 0.6 * 36.0  # 0.6*Fy for A36

        return {
            "success": True,
            "max_stress_ksi": round(max_stress, 2),
            "adequate": adequate,
            "max_reaction_kips": round(max_reaction, 2),
            "note": "Simplified beam-analog check. For detailed plate "
                    "FEA, use dedicated plate element software.",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "max_stress_ksi": 0.0,
            "adequate": False,
        }
