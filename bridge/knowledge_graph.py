"""
Your Company Virtual Office - Knowledge Graph

Every entity is connected:
  Project ↔ Bid ↔ Contact ↔ Compliance ↔ Cost ↔ Welder ↔ WPS

"Show me everything about Marathon" returns the bid, ISN status,
crew DISA, EMR gate, cost variance - all in one query.
"""

import json
from datetime import datetime, timezone


def query_entity(name: str) -> dict:
    """Cross-entity search. Returns everything related to a name/keyword."""
    results = {
        "query": name,
        "ts": datetime.now(timezone.utc).isoformat(),
        "entities": {},
    }
    q = name.lower()

    # Search bids
    try:
        from bridge.bid_pipeline import get_pipeline
        bids = get_pipeline()
        matched = [b for b in bids if q in b.get("name", "").lower() or q in b.get("gc_company", "").lower()]
        if matched:
            results["entities"]["bids"] = matched
    except Exception:pass

    # Search projects
    try:
        from bridge.cost_tracker import get_all_projects
        projects = get_all_projects()
        matched = [p for p in projects if q in p.get("name", "").lower() or q in p.get("client", "").lower()]
        if matched:
            results["entities"]["projects"] = matched
    except Exception:pass

    # Search contacts
    try:
        from bridge.contacts import search
        contacts = search(query=name)
        if contacts:
            results["entities"]["contacts"] = contacts
    except Exception:pass

    # Search compliance
    try:
        from bridge.blockers import get_all
        blockers = get_all()
        matched = [b for b in blockers if q in b.get("name", "").lower() or q in b.get("action", "").lower()]
        if matched:
            results["entities"]["blockers"] = matched
    except Exception:pass

    # Search conversation history
    try:
        from bridge.memory import search_history
        convos = search_history(name, limit=5)
        if convos:
            results["entities"]["conversations"] = [
                {"role": c["role"], "preview": c["content"][:150], "ts": c["ts"]}
                for c in convos
            ]
    except Exception:pass

    # Search audit log
    try:
        from bridge.audit import query as audit_query
        audits = audit_query(action=None, hours=720, limit=10)
        matched = [a for a in audits if q in a.get("detail", "").lower()]
        if matched:
            results["entities"]["audit_trail"] = matched[:5]
    except Exception:pass

    # ISN status
    try:
        from bridge.isnetworld_client import get_status
        isn = get_status()
        if isn.get("configured"):
            results["entities"]["isn_status"] = isn
    except Exception:pass

    # DISA crew
    try:
        from bridge.disa_status import get_all as disa_all
        employees = disa_all()
        matched = [e for e in employees if q in e.get("name", "").lower() or q in e.get("site_assignments", "").lower()]
        if matched:
            results["entities"]["disa_employees"] = matched
    except Exception:pass

    # EMR status
    try:
        from bridge.emr_predictor import get_bidding_gates
        results["entities"]["emr"] = get_bidding_gates()
    except Exception:pass

    # Count total entities found
    results["total_entities"] = sum(len(v) if isinstance(v, list) else 1
                                     for v in results["entities"].values())
    results["entity_types"] = list(results["entities"].keys())

    return results


def get_entity_connections(entity_type: str, entity_id: str) -> dict:
    """Get all connections for a specific entity."""
    # This would be expanded with explicit relationship tables
    # For now, use the cross-search approach
    return query_entity(entity_id)


def summary_for_ai(name: str) -> str:
    """Build a compact context block for the AI from the knowledge graph."""
    data = query_entity(name)
    lines = [f"Knowledge graph results for '{name}':"]

    for etype, entities in data.get("entities", {}).items():
        if isinstance(entities, list):
            lines.append(f"\n{etype.upper()} ({len(entities)}):")
            for e in entities[:3]:
                if isinstance(e, dict):
                    # Pick the most useful fields
                    preview = " | ".join(f"{k}: {str(v)[:50]}" for k, v in e.items()
                                        if k not in ("raw_header", "history", "entries") and v)
                    lines.append(f"  - {preview[:200]}")
        elif isinstance(entities, dict):
            lines.append(f"\n{etype.upper()}: {json.dumps(entities)[:200]}")

    return "\n".join(lines) if len(lines) > 1 else f"No entities found for '{name}'"
