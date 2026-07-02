"""Project indexer.

After a successful takeoff or bid, this module converts the result into
a searchable document and upserts it into the memory store. Runs
automatically at the end of the takeoff pipeline (wired in Phase 8's
takeoff_graph Stage 6 tail) and can be called manually via the Bridge.

Document shape:
    A plain-English summary of the project, designed for both keyword
    and semantic search. Example:
        "Houston Logistics Hub. PRJ-2026-HOU-0042. 185 tons structural,
         12 tons misc steel. 28 W14X22 beams, 16 W10X49 columns.
         4 moment frames. $640,000 total at $3,459/ton.
         Client: Marathon Petroleum. Location: Baytown TX."

Metadata fields stored alongside the document:
    bid_number, project_name, client, location, total_tons,
    total_cost, cost_per_ton, member_count, moment_count,
    completion_date, stages_completed.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from .memory_store import get_memory_store

log = logging.getLogger(__name__)


def index_takeoff_result(
    takeoff_result: dict,
    bid_number: str = "",
    project_name: str = "",
    client: str = "",
    location: str = "",
    store=None,
) -> dict:
    """Index a takeoff result (v1 or v2 dict) into project memory.

    Returns:
        {"success": bool, "bid_number": str, "backend": str, "warnings": list}
    """
    warnings: list[str] = []

    bid = bid_number or takeoff_result.get("bid_number", "")
    if not bid:
        return {"success": False, "bid_number": "",
                "warnings": ["bid_number required for indexing"]}

    name = project_name or takeoff_result.get("project_name", "")

    # Extract key metrics from the takeoff result
    members = takeoff_result.get("valid_members",
                takeoff_result.get("members", []))
    member_count = len(members)
    total_tons = float(takeoff_result.get("total_tons", 0))
    total_cost = float(takeoff_result.get("total_cost", 0))
    cost_per_ton = float(takeoff_result.get("cost_per_ton", 0))
    misc_tons = float(takeoff_result.get("misc_tons", 0))
    moment_count = sum(1 for m in members if m.get("moment", False))

    # Build shape summary (top 5 shapes by count)
    shape_counter: Counter = Counter()
    for m in members:
        shape = m.get("shape") or m.get("normalized") or ""
        if shape:
            shape_counter[shape] += 1
    top_shapes = shape_counter.most_common(5)
    shape_summary = ", ".join(
        f"{count} {shape}" for shape, count in top_shapes
    ) if top_shapes else "no members extracted"

    # Build the document text for search
    parts = []
    if name:
        parts.append(f"{name}.")
    parts.append(f"{bid}.")
    if total_tons > 0:
        structural = total_tons - misc_tons
        parts.append(f"{structural:.1f} tons structural")
        if misc_tons > 0:
            parts.append(f"{misc_tons:.1f} tons misc steel")
    parts.append(f"{shape_summary}.")
    if moment_count > 0:
        parts.append(f"{moment_count} moment frames.")
    if total_cost > 0:
        parts.append(f"${total_cost:,.0f} total at ${cost_per_ton:,.0f}/ton.")
    if client:
        parts.append(f"Client: {client}.")
    if location:
        parts.append(f"Location: {location}.")

    document = " ".join(parts)

    metadata = {
        "bid_number": str(bid),
        "project_name": str(name),
        "client": str(client),
        "location": str(location),
        "type": "project",
        "total_tons": round(total_tons, 2),
        "misc_tons": round(misc_tons, 4),
        "total_cost": round(total_cost, 2),
        "cost_per_ton": round(cost_per_ton, 2),
        "member_count": int(member_count),
        "moment_count": int(moment_count),
        "shape_summary": shape_summary,
        "stages_completed": ",".join(
            takeoff_result.get("stages_completed", [])),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Upsert into the store
    if store is None:
        store = get_memory_store()

    ok = store.upsert(bid_number=bid, document=document, metadata=metadata)
    backend = type(store).__name__

    if not ok:
        warnings.append(f"upsert_failed: {backend}")

    log.info("indexed project %s (%s tons, $%s) into %s",
             bid, total_tons, total_cost, backend)

    return {
        "success": ok,
        "bid_number": bid,
        "backend": backend,
        "document_preview": document[:200],
        "warnings": warnings,
    }
