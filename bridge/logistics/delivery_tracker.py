"""Delivery and erection tracking (Phase 28, v6.0.0).

Truck load planning with weight limits, BOL generation, and erection
sequencing. The GC calls Owner: "Where's the steel for Grid C-D?"
Owner has the answer on his dashboard.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


DEFAULT_TRUCK_CAPACITY_LBS = 45000


def plan_truck_loads(
    pieces_ready: list[dict],
    truck_capacity_lbs: float = DEFAULT_TRUCK_CAPACITY_LBS,
    erection_priority: list[str] | None = None,
) -> dict:
    """Optimize truck loading by weight and erection sequence.

    Args:
        pieces_ready: List of dicts with piece_mark, weight_lbs,
            erection_zone (optional).
        truck_capacity_lbs: Max weight per truck.
        erection_priority: Piece marks needed first on site.

    Returns:
        {
            "trucks": list of truck dicts,
            "total_trucks": int,
            "total_weight_lbs": float,
        }
    """
    if not pieces_ready:
        return {"trucks": [], "total_trucks": 0, "total_weight_lbs": 0.0}

    # Sort: priority pieces first, then by erection zone, then by weight
    priority_set = set(erection_priority or [])

    def sort_key(p):
        is_priority = 0 if p.get("piece_mark") in priority_set else 1
        zone = p.get("erection_zone", "Z99")
        return (is_priority, zone)

    sorted_pieces = sorted(pieces_ready, key=sort_key)

    trucks = []
    current_truck: list[dict] = []
    current_weight = 0.0

    for piece in sorted_pieces:
        w = float(piece.get("weight_lbs", 0) or 0)
        if w <= 0:
            continue

        if current_weight + w > truck_capacity_lbs and current_truck:
            # Close current truck
            trucks.append(_make_truck(len(trucks) + 1, current_truck,
                                       current_weight, truck_capacity_lbs))
            current_truck = []
            current_weight = 0.0

        current_truck.append(piece)
        current_weight += w

    # Close final truck
    if current_truck:
        trucks.append(_make_truck(len(trucks) + 1, current_truck,
                                   current_weight, truck_capacity_lbs))

    total_weight = sum(t["total_weight_lbs"] for t in trucks)

    return {
        "trucks": trucks,
        "total_trucks": len(trucks),
        "total_weight_lbs": round(total_weight, 1),
    }


def _make_truck(num: int, pieces: list[dict], weight: float,
                cap: float) -> dict:
    marks = [p.get("piece_mark", "") for p in pieces]
    zones = list(set(p.get("erection_zone", "") for p in pieces
                     if p.get("erection_zone")))
    return {
        "truck_number": num,
        "pieces": marks,
        "piece_count": len(pieces),
        "total_weight_lbs": round(weight, 1),
        "utilization_pct": round(weight / max(cap, 1) * 100, 1),
        "erection_zones": zones or ["unassigned"],
    }


def generate_bol(
    job_number: str,
    truck: dict,
    destination: str = "",
) -> dict:
    """Generate a Bill of Lading record for a truck load.

    Returns a BOL dict (PDF generation deferred to reportlab).
    """
    return {
        "success": True,
        "bol_number": f"BOL-{job_number}-T{truck.get('truck_number', 0):02d}",
        "job_number": job_number,
        "truck_number": truck.get("truck_number", 0),
        "piece_count": truck.get("piece_count", 0),
        "total_weight_lbs": truck.get("total_weight_lbs", 0),
        "destination": destination,
        "pieces": truck.get("pieces", []),
        "status": "LOADING",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def recommend_erection_sequence(
    members: list[dict],
) -> list[dict]:
    """Recommend erection order: columns first, beams, then bracing.

    Args:
        members: List of member dicts with mark, shape, erection_zone.

    Returns:
        Ordered list of member dicts with sequence_number.
    """
    # Priority: columns (C, W columns) -> beams (B) -> bracing (BR) -> misc
    def priority(m):
        mark = str(m.get("mark", "")).upper()
        shape = str(m.get("shape", "")).upper()
        if mark.startswith("C") or "COLUMN" in shape:
            return (0, mark)
        if mark.startswith("B") and not mark.startswith("BR"):
            return (1, mark)
        if mark.startswith("BR"):
            return (2, mark)
        return (3, mark)

    ordered = sorted(members, key=priority)
    for i, m in enumerate(ordered):
        m["sequence_number"] = i + 1

    return ordered
