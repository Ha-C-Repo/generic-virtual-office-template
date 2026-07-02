"""
Drawing Intel: Connection Capacity Checker
=============================================
Validates connection details against AISC Table 10-1 (all-bolted
double-angle connections). If a PE specifies 5 bolts on a beam
where only 3 physically fit the web, flag a "Connection Conflict."

This catches errors that LIFT completely ignores.
No PE license required. This is dimensional feasibility only.

Usage:
    from bridge.drawing_intel.connection_check import check_bolt_connection
    result = check_bolt_connection("W14X82", num_bolts=5, bolt_dia=0.75)
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# AISC Table 10-1: Maximum number of rows of bolts in a double-angle connection
# Based on beam depth (d) and standard edge distances
# bolt_diameter: {min_depth_for_n_bolts: n}
# Using 3" bolt spacing + 1.25" edge distance top and bottom
BOLT_SPACING = 3.0       # Standard 3" vertical bolt spacing
EDGE_DISTANCE = 1.25     # Min edge distance per AISC
MIN_CLEARANCE_TOP = 0.5  # Clearance from beam fillet (k dimension)


def max_bolts_for_depth(d: float, k: float = 1.0,
                        bolt_spacing: float = 3.0) -> int:
    """Calculate maximum number of bolt rows for a given beam depth.

    Available connection depth = d - 2*k (inside the fillet zone)
    Each bolt row needs: bolt_spacing (3" typical)
    End distance: 1.25" each end minimum

    Args:
        d: Beam depth in inches
        k: k-dimension (fillet to outer flange) in inches
        bolt_spacing: Vertical spacing between bolt rows (default 3")

    Returns:
        Maximum number of bolt rows
    """
    available = d - 2 * k - 2 * EDGE_DISTANCE
    if available <= 0:
        return 0
    return int(available / bolt_spacing) + 1


def check_bolt_connection(
    shape: str,
    num_bolts: int,
    bolt_dia: float = 0.75,
    connection_type: str = "double_angle",
) -> dict:
    """Check if a bolt connection is physically feasible for a given shape.

    Args:
        shape: AISC shape designation (e.g., "W14X82")
        num_bolts: Number of bolt rows specified
        bolt_dia: Bolt diameter in inches (default 3/4")
        connection_type: Connection type (currently only double_angle)

    Returns:
        Consistent envelope (pass 10g normalization):
        {checked, feasible, shape, beam_depth, k_dimension, available_depth,
         max_bolt_rows, specified_bolts, bolt_dia, bolt_spacing,
         connection_type, warning, reason}

        On any early-exit (invalid input, shape lookup failure, no depth
        data), `checked=False`, `feasible=False`, `reason` populated, and
        all detail keys present with safe defaults so callers can do
        ``r["beam_depth"]`` without checking which branch ran.
    """
    # pass 10g: consistent envelope. Build defaults, then enrich on success.
    out = {
        "checked": False,
        "feasible": False,
        "shape": shape,
        "beam_depth": 0.0,
        "k_dimension": 0.0,
        "available_depth": 0.0,
        "max_bolt_rows": 0,
        "specified_bolts": num_bolts if isinstance(num_bolts, (int, float)) and not isinstance(num_bolts, bool) else 0,
        "bolt_dia": bolt_dia if isinstance(bolt_dia, (int, float)) and bolt_dia > 0 else 0.0,
        "bolt_spacing": BOLT_SPACING,
        "connection_type": connection_type,
        "warning": None,
        "reason": "",
    }

    # Input validation (P2 fix: rejects negative counts and non-integer types)
    if not isinstance(num_bolts, (int, float)) or isinstance(num_bolts, bool):
        out["reason"] = f"num_bolts must be a non-negative integer (got {num_bolts!r})"
        return out
    num_bolts = int(num_bolts)
    if num_bolts < 0:
        out["reason"] = f"num_bolts must be a non-negative integer (got {num_bolts})"
        return out
    if not isinstance(bolt_dia, (int, float)) or bolt_dia <= 0:
        out["reason"] = f"bolt_dia must be a positive number (got {bolt_dia!r})"
        return out
    out["specified_bolts"] = num_bolts
    out["bolt_dia"] = bolt_dia

    # Get shape dimensions
    try:
        from bridge.aisc_validator import AISCValidator
        v = AISCValidator()
        result = v.validate_shape(shape)
        if not result["valid"]:
            out["reason"] = f"Shape '{shape}' not found in AISC database"
            return out

        data = result.get("data", {})
        d = float(data.get("d_in", data.get("d", 0)))
        # kdes (v16 master) is the AISC design k-distance; fall back to legacy "k"
        k = float(data.get("kdes", data.get("k", 1.0)))

        if d <= 0:
            out["reason"] = f"No depth (d) data for {shape}"
            return out

    except Exception as e:
        out["reason"] = f"Lookup failed: {e}"
        return out

    # Calculate max bolts
    max_b = max_bolts_for_depth(d, k)

    feasible = num_bolts <= max_b
    warning = None
    if not feasible:
        warning = (
            f"CONNECTION CONFLICT: {shape} (d={d}\") can accommodate "
            f"max {max_b} bolt rows, but {num_bolts} were specified. "
            f"Available web depth after fillets: {d - 2*k:.1f}\". "
            f"Verify connection detail with PE."
        )

    out.update({
        "checked": True,
        "feasible": feasible,
        "beam_depth": d,
        "k_dimension": k,
        "available_depth": round(d - 2 * k, 2),
        "max_bolt_rows": max_b,
        "warning": warning,
        "reason": "" if feasible else "exceeds max bolt rows for available depth",
    })
    return out


def check_connection_table(connections: list[dict]) -> dict:
    """Validate an entire connection table from S-501/S-502.

    Each connection: {shape, num_bolts, bolt_dia, connection_id}

    Returns summary with all conflicts flagged.
    """
    results = []
    conflicts = []

    for conn in connections:
        shape = conn.get("shape", "")
        bolts = conn.get("num_bolts", 0)
        dia = conn.get("bolt_dia", 0.75)
        conn_id = conn.get("connection_id", "")

        check = check_bolt_connection(shape, bolts, dia)
        check["connection_id"] = conn_id
        results.append(check)

        if check.get("checked") and not check.get("feasible"):
            conflicts.append({
                "connection_id": conn_id,
                "shape": shape,
                "specified": bolts,
                "max_allowed": check["max_bolt_rows"],
                "warning": check["warning"],
            })

    return {
        "total_checked": len(results),
        "conflicts": len(conflicts),
        "conflict_details": conflicts,
        "all_feasible": len(conflicts) == 0,
        "results": results,
    }


# ---- T-Distance K-Zone Check (Gemini suggestion) ----
# The "T" dimension is the clear distance between flanges minus k.
# Bolts cannot be placed in the k-zone (where web meets flange fillet).
# If a bolt row falls within kdes of the flange face, it's a conflict.

# Standard bolt spacing: 3" typical, 2.667" minimum (AISC J3.3)
BOLT_SPACING_STD = 3.0    # inches between bolt rows
BOLT_EDGE_DIST = 1.25     # inches from flange face to first bolt center


def _lookup_t_and_kdes(shape: str) -> tuple[Optional[float], Optional[float]]:
    """Auto-fetch T-distance and kdes for a shape from the AISC master CSV.

    Lazy-imports the validator to avoid circular dependencies (validator
    is in bridge/, this module is in bridge/drawing_intel/). Returns
    (None, None) if the validator is unavailable, the shape is not in
    the master, or T/kdes columns are absent for that shape.

    Closes the v3.5.3 carry-forward gap where check_kzone_clearance()
    required callers to pass T+kdes explicitly even though the data was
    already loaded in aisc_master.csv after Phase 1 ingestion.
    """
    try:
        from bridge.aisc_validator import _get_validator  # lazy
    except Exception as e:
        log.debug("Validator import failed for T/kdes lookup: %s", e)
        return None, None

    try:
        result = _get_validator().validate_shape(shape)
    except Exception as e:
        log.debug("validate_shape failed for %s: %s", shape, e)
        return None, None

    if not result.get("valid"):
        return None, None

    data = result.get("data", {}) or {}
    t_raw = data.get("T")
    k_raw = data.get("kdes")

    def _f(v):
        try:
            f = float(v)
            return f if f > 0 else None
        except (TypeError, ValueError):
            return None

    return _f(t_raw), _f(k_raw)


def check_kzone_clearance(shape: str, num_bolt_rows: int,
                          T_distance: float = None,
                          kdes: float = None) -> dict:
    """Check if bolt rows fit within the T-distance without entering k-zone.

    The k-zone is the curved fillet where the web meets the flange.
    Bolts placed in this zone cannot develop full bearing capacity.

    Args:
        shape: AISC designation (e.g., W14X82)
        num_bolt_rows: Number of bolt rows in the connection
        T_distance: Optional. Clear web distance available for bolts. If
                    None or non-positive, auto-fetched from aisc_master.csv.
        kdes: Optional. Design k-distance. If None, auto-fetched from CSV.

    Returns:
        dict with feasible, max_rows, available_depth, required_depth,
        plus a 'source' field indicating whether T/kdes came from the
        caller or were looked up automatically.
    """
    # vj: parity-ok (pass 10g classified: dispatcher J=0.25; disjoint shapes)
    source = "caller"
    if T_distance is None or T_distance <= 0 or kdes is None:
        t_lookup, k_lookup = _lookup_t_and_kdes(shape)
        if T_distance is None or T_distance <= 0:
            T_distance = t_lookup
        if kdes is None:
            kdes = k_lookup
        if t_lookup is not None or k_lookup is not None:
            source = "aisc_master_csv"

    if T_distance is None or T_distance <= 0:
        return {
            "feasible": None,
            "shape": shape,
            "source": source,
            "note": (
                f"T-distance unavailable for {shape}. The shape may not be "
                f"in aisc_master.csv, or the family (e.g. HSS, L) does not "
                f"carry T data. Pass T_distance explicitly to override."
            ),
        }

    # Available depth for bolts = T - (2 * edge distance already accounted in T)
    # T already excludes the k-zone, so full T is available
    available = T_distance

    # Required depth for N bolt rows:
    # First bolt at BOLT_EDGE_DIST from top of T
    # Each subsequent bolt at BOLT_SPACING_STD below
    # Last bolt needs BOLT_EDGE_DIST clearance from bottom
    if num_bolt_rows <= 1:
        required = 2 * BOLT_EDGE_DIST
    else:
        required = 2 * BOLT_EDGE_DIST + (num_bolt_rows - 1) * BOLT_SPACING_STD

    max_rows = max(1, int((available - 2 * BOLT_EDGE_DIST) / BOLT_SPACING_STD) + 1)
    feasible = required <= available

    return {
        "feasible": feasible,
        "shape": shape,
        "source": source,
        "num_bolt_rows": num_bolt_rows,
        "T_distance": T_distance,
        "kdes": kdes,
        "available_depth": round(available, 2),
        "required_depth": round(required, 2),
        "max_bolt_rows": max_rows,
        "status": "CLEAR" if feasible else "K-ZONE CONFLICT",
        "action": (
            f"{shape}: {num_bolt_rows} bolt rows fit within T={T_distance}\" "
            f"({required:.1f}\" needed, {available:.1f}\" available)"
            if feasible else
            f"K-ZONE CONFLICT: {shape} T={T_distance}\" cannot fit {num_bolt_rows} bolt rows. "
            f"Max {max_rows} rows. Bolts would enter k-zone (kdes={kdes}\")."
        ),
    }
