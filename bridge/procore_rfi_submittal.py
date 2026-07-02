"""
Your Company Virtual Office - Procore RFI & Submittal Client

REST API: developer.procore.com
Auto-classifies inbound RFIs by structural keyword (column splice,
base plate, bolt grade, embed location) and routes to the right
detailer with a draft answer from prior conversation history (RAG).

Submittal logs auto-built from spec-section keyword extraction.
"""

import os, json, httpx
from datetime import datetime, date, timedelta
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"

PROCORE_BASE = "https://api.procore.com/rest/v1.0"

# Structural keywords for RFI auto-classification
STRUCTURAL_KEYWORDS = {
    "connection": ["column splice", "base plate", "moment connection", "shear tab",
                   "clip angle", "end plate", "gusset", "bracket", "seat"],
    "bolt_grade": ["A325", "A490", "F1852", "F2280", "TC bolt", "DTI", "squirter"],
    "material": ["A992", "A572", "A500", "A36", "A913", "HSS", "WT", "angle"],
    "embed": ["embed", "anchor bolt", "nelson stud", "headed stud", "pour stop"],
    "weld": ["CJP", "PJP", "fillet", "plug weld", "slot weld", "backing bar"],
    "erection": ["plumb", "elevation", "column line", "grid", "field bolt", "shim"],
}


def _get_token():
    token = os.environ.get("PROCORE_TOKEN", "")
    if not token:
        try:
            from bridge.keyvault import load_keys
            token = load_keys().get("PROCORE_TOKEN", "")
        except Exception:pass
    return token


def _headers():
    token = _get_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def classify_rfi(subject: str, body: str = "") -> dict:
    """Auto-classify an RFI by structural keyword matching."""
    text = (subject + " " + body).lower()
    matches = {}
    for category, keywords in STRUCTURAL_KEYWORDS.items():
        found = [kw for kw in keywords if kw.lower() in text]
        if found:
            matches[category] = found

    priority = "normal"
    if "embed" in matches:
        priority = "urgent"  # embeds affect pour schedule
    elif "connection" in matches and "weld" in matches:
        priority = "high"

    return {
        "categories": list(matches.keys()),
        "keywords_matched": matches,
        "priority": priority,
        "route_to": _suggest_route(matches),
    }


def _suggest_route(matches):
    if "connection" in matches or "weld" in matches:
        return "Detailer / Connection Engineer"
    if "embed" in matches:
        return "Project Manager (pour coordination)"
    if "erection" in matches:
        return "Foreman / Superintendent"
    return "Estimator"


def fetch_rfis(project_id: str, status: str = "open") -> dict:
    """Fetch RFIs from Procore for a project."""
    token = _get_token()
    if not token:
        return {"error": "Procore token not configured. Set PROCORE_TOKEN."}

    try:
        resp = httpx.get(
            f"{PROCORE_BASE}/projects/{project_id}/rfis",
            headers=_headers(),
            params={"filters[status]": status},
            timeout=15)
        resp.raise_for_status()
        rfis = resp.json()

        # Auto-classify each
        classified = []
        for rfi in rfis:
            classification = classify_rfi(rfi.get("subject", ""), rfi.get("body", ""))
            classified.append({
                "id": rfi.get("id"),
                "number": rfi.get("number"),
                "subject": rfi.get("subject"),
                "status": rfi.get("status"),
                "due_date": rfi.get("due_date"),
                "classification": classification,
            })

        return {"rfis": classified, "count": len(classified)}
    except Exception as e:
        return {"error": str(e)[:200]}


def fetch_submittals(project_id: str, status: str = "open") -> dict:
    """Fetch submittals from Procore."""
    token = _get_token()
    if not token:
        return {"error": "Procore token not configured"}
    try:
        resp = httpx.get(
            f"{PROCORE_BASE}/projects/{project_id}/submittals",
            headers=_headers(),
            params={"filters[status]": status},
            timeout=15)
        resp.raise_for_status()
        return {"submittals": resp.json()}
    except Exception as e:
        return {"error": str(e)[:200]}


def draft_rfi_response(rfi_subject: str, rfi_body: str, project_context: str = "") -> dict:
    """Use conversation history (RAG) to draft an RFI response."""
    try:
        from bridge.memory import search_history
        # Search past conversations for relevant context
        keywords = rfi_subject.split()[:5]
        relevant = []
        for kw in keywords:
            results = search_history(kw, limit=3)
            relevant.extend(results)
        # Deduplicate
        seen = set()
        unique = []
        for r in relevant:
            key = r.get("content", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return {
            "rfi_subject": rfi_subject,
            "prior_context": [r.get("content", "")[:200] for r in unique[:5]],
            "classification": classify_rfi(rfi_subject, rfi_body),
            "draft_available": len(unique) > 0,
            "note": "AI will use this context + structural knowledge to draft response",
        }
    except Exception as e:
        return {"error": str(e)[:200]}


def get_status():
    """Get Procore integration status."""
    return {
        "configured": bool(_get_token()),
        "base_url": PROCORE_BASE,
        "structural_categories": len(STRUCTURAL_KEYWORDS),
        "total_keywords": sum(len(v) for v in STRUCTURAL_KEYWORDS.values()),
    }
