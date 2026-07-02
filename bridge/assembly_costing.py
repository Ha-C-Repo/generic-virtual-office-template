"""Assembly-based costing (Phase 10, build slot 10, v4.3.0).

Maps each connection type from Phase 2's detail_vision output to a
hardware cost assembly: bolts, plates, welding hours, and a total
dollar figure. This closes the gap where the bid-total calculator
treats all connections identically via tons * rate_per_ton.

Reality: a W14X82 with a full moment connection costs $800-1,200 more
in connection hardware than the same beam with a simple shear tab. On
a 200-ton project with 20 moment frames, that is $16,000-24,000 of
unbilled cost without this module.

All arithmetic stays in bridge/calculators.py. This module only maps
connection_type to a cost table and sums the results. No LLM math.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging

log = logging.getLogger(__name__)


# Hardware cost assemblies per connection type. Keyed on connection_type
# from Phase 2 detail_vision. "total" is the pre-computed bottom line
# so callers do not need to re-derive it.
#
# Joseph can override these by passing a custom table to
# compute_assembly_costs(). The defaults below are Houston-market
# averages as of May 2026 calibration round.

ASSEMBLY_COSTS: dict[str, dict] = {
    "B2B": {
        "label": "Simple shear (beam to beam)",
        "bolts": {"type": "A325", "dia_in": 0.75, "qty": 3, "cost_ea": 2.50},
        "plates": [
            {"desc": "clip angle L4X3X1/4", "qty": 2, "cost_ea": 12.00},
        ],
        "welding_hrs": 0.5,
        "total": 145.00,
    },
    "B2C": {
        "label": "Beam to column (shear default)",
        "bolts": {"type": "A325", "dia_in": 0.75, "qty": 4, "cost_ea": 2.50},
        "plates": [
            {"desc": "shear tab PL 3/8x4x12", "qty": 1, "cost_ea": 18.00},
        ],
        "welding_hrs": 0.75,
        "total": 175.00,
    },
    "B2C_MOMENT": {
        "label": "Moment frame (beam to column)",
        "bolts": {"type": "A325", "dia_in": 0.875, "qty": 10, "cost_ea": 3.20},
        "plates": [
            {"desc": "end plate 1in thick", "qty": 1, "cost_ea": 85.00},
            {"desc": "stiffener plate", "qty": 2, "cost_ea": 45.00},
        ],
        "welding_hrs": 5.0,
        "total": 970.00,
    },
    "C2F": {
        "label": "Base plate (column to foundation)",
        "bolts": {"type": "F1554", "dia_in": 1.0, "qty": 4, "cost_ea": 8.50},
        "plates": [
            {"desc": "base plate", "qty": 1, "cost_ea": 95.00},
        ],
        "grout": {"cost": 35.00},
        "welding_hrs": 2.5,
        "total": 498.00,
    },
    "SPLICE": {
        "label": "Splice (column or beam)",
        "bolts": {"type": "A325", "dia_in": 0.875, "qty": 12, "cost_ea": 3.20},
        "plates": [
            {"desc": "splice plate", "qty": 2, "cost_ea": 55.00},
        ],
        "welding_hrs": 3.5,
        "total": 755.00,
    },
    "C2C": {
        "label": "Column splice",
        "bolts": {"type": "A325", "dia_in": 0.875, "qty": 12, "cost_ea": 3.20},
        "plates": [
            {"desc": "splice plate", "qty": 2, "cost_ea": 55.00},
        ],
        "welding_hrs": 3.5,
        "total": 755.00,
    },
    "BR2C": {
        "label": "Brace to column (gusset)",
        "bolts": {"type": "A325", "dia_in": 0.75, "qty": 8, "cost_ea": 2.50},
        "plates": [
            {"desc": "gusset plate", "qty": 1, "cost_ea": 65.00},
        ],
        "welding_hrs": 2.5,
        "total": 425.00,
    },
    "BR2B": {
        "label": "Brace to beam (gusset)",
        "bolts": {"type": "A325", "dia_in": 0.75, "qty": 8, "cost_ea": 2.50},
        "plates": [
            {"desc": "gusset plate", "qty": 1, "cost_ea": 65.00},
        ],
        "welding_hrs": 2.5,
        "total": 425.00,
    },
}

# Default for any connection_type not in the table. Conservative
# at $200 because unknown connections tend to be non-trivial.
DEFAULT_ASSEMBLY_COST = 200.00


def _resolve_connection_key(detail: dict) -> str:
    """Derive the ASSEMBLY_COSTS key from a detail_vision result dict.

    A moment frame on B2C is keyed separately as "B2C_MOMENT" because
    its cost is 5x a standard B2C shear tab. Everything else maps
    directly by connection_type.
    """
    conn = str(detail.get("connection_type", "")).strip().upper()
    is_moment = bool(detail.get("moment", False))

    if conn == "B2C" and is_moment:
        return "B2C_MOMENT"
    return conn


def cost_single_connection(
    detail: dict,
    cost_table: dict[str, dict] | None = None,
) -> dict:
    """Return the assembly cost for one connection detail.

    Args:
        detail: Dict from Phase 2 detail_vision (must have
            connection_type; moment is optional).
        cost_table: Override the default ASSEMBLY_COSTS.

    Returns:
        {
            "connection_type": str,
            "assembly_key": str,
            "cost_usd": float,
            "label": str,
            "bolt_count": int,
            "welding_hrs": float,
            "matched": bool,
        }
    """
    table = cost_table or ASSEMBLY_COSTS
    key = _resolve_connection_key(detail)
    entry = table.get(key)
    if entry is None:
        return {
            "connection_type": key,
            "assembly_key": key,
            "cost_usd": DEFAULT_ASSEMBLY_COST,
            "label": f"Unknown ({key})",
            "bolt_count": int(detail.get("bolt_count", 0)),
            "welding_hrs": 0.0,
            "matched": False,
        }
    return {
        "connection_type": key,
        "assembly_key": key,
        "cost_usd": float(entry.get("total", DEFAULT_ASSEMBLY_COST)),
        "label": str(entry.get("label", key)),
        "bolt_count": int(
            entry.get("bolts", {}).get("qty", 0)
            or detail.get("bolt_count", 0)
        ),
        "welding_hrs": float(entry.get("welding_hrs", 0)),
        "matched": True,
    }


def compute_assembly_costs(
    details: list[dict],
    cost_table: dict[str, dict] | None = None,
) -> dict:
    """Compute total connection hardware cost for a project.

    Args:
        details: List of Phase 2 detail_vision result dicts.
        cost_table: Override the default ASSEMBLY_COSTS.

    Returns:
        {
            "total_connection_cost_usd": float,
            "connection_count": int,
            "moment_count": int,
            "moment_cost_usd": float,
            "shear_cost_usd": float,
            "other_cost_usd": float,
            "total_welding_hrs": float,
            "total_bolt_count": int,
            "per_connection": list of cost_single_connection results,
            "unmatched_count": int,
            "warnings": list[str],
        }
    """
    warnings: list[str] = []
    per_conn = []
    total = 0.0
    moment_cost = 0.0
    shear_cost = 0.0
    other_cost = 0.0
    total_weld = 0.0
    total_bolts = 0
    moment_count = 0
    unmatched = 0

    for d in details:
        c = cost_single_connection(d, cost_table=cost_table)
        per_conn.append(c)
        cost = float(c["cost_usd"])
        total += cost
        total_weld += float(c["welding_hrs"])
        total_bolts += int(c["bolt_count"])

        if not c["matched"]:
            unmatched += 1
            other_cost += cost
            warnings.append(
                f"unmatched_connection: {c['connection_type']} "
                f"(used default ${DEFAULT_ASSEMBLY_COST:.0f})"
            )
        elif "MOMENT" in c["assembly_key"]:
            moment_count += 1
            moment_cost += cost
        elif c["assembly_key"] in ("B2B", "B2C"):
            shear_cost += cost
        else:
            other_cost += cost

    return {
        "total_connection_cost_usd": round(total, 2),
        "connection_count": len(details),
        "moment_count": moment_count,
        "moment_cost_usd": round(moment_cost, 2),
        "shear_cost_usd": round(shear_cost, 2),
        "other_cost_usd": round(other_cost, 2),
        "total_welding_hrs": round(total_weld, 2),
        "total_bolt_count": total_bolts,
        "per_connection": per_conn,
        "unmatched_count": unmatched,
        "warnings": warnings,
    }
