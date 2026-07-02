"""
Your Company Virtual Office - Code-Aware Document Intelligence

Reads project specs → extracts steel submittals → links to AWS/AISC clauses
→ cross-references with WPS/PQR/WPQ tracker → flags gaps

Competitive edge: Procore Submittal Builder + Pype AutoSpecs handle general
submittals but DON'T extract AWS D1.1 clause-level WPS essential variables
or AISC 207-25 audit evidence. That's our white space.
"""

import re, json
from datetime import datetime, timezone
from typing import List, Dict

# ═══ CSI MASTERFORMAT - STEEL DIVISIONS ═══════════════════════════

CSI_STEEL_SECTIONS = {
    "03 30 00": {"title": "Cast-in-Place Concrete", "steel_relevance": "embed plates, anchor bolts"},
    "05 00 00": {"title": "Metals", "steel_relevance": "parent division"},
    "05 10 00": {"title": "Structural Metal Framing", "steel_relevance": "primary scope"},
    "05 12 00": {"title": "Structural Steel Framing", "steel_relevance": "W/HSS/angles/channels"},
    "05 12 23": {"title": "Structural Steel for Buildings", "steel_relevance": "primary building steel"},
    "05 21 00": {"title": "Steel Joist Framing", "steel_relevance": "joists/joist girders"},
    "05 31 00": {"title": "Steel Decking", "steel_relevance": "roof/floor/form deck"},
    "05 31 13": {"title": "Steel Floor Decking", "steel_relevance": "composite deck"},
    "05 31 23": {"title": "Steel Roof Decking", "steel_relevance": "roof deck"},
    "05 40 00": {"title": "Cold-Formed Metal Framing", "steel_relevance": "light gauge/PEMB indicator"},
    "05 50 00": {"title": "Metal Fabrications", "steel_relevance": "misc metals/handrails/stairs"},
    "05 51 00": {"title": "Metal Stairs", "steel_relevance": "stair fabrication"},
    "05 52 00": {"title": "Metal Railings", "steel_relevance": "handrail fabrication"},
    "05 73 00": {"title": "Decorative Metal Railings", "steel_relevance": "ornamental"},
    "09 91 00": {"title": "Painting", "steel_relevance": "SSPC surface prep, coatings"},
    "13 34 00": {"title": "Fabricated Engineered Structures", "steel_relevance": "PEMB-disqualifier"},
}

# AWS/AISC code clause cross-reference
CODE_CLAUSES = {
    "welding": {
        "keywords": ["weld", "aws d1.1", "welding", "wps", "pqr", "wpq", "cwi"],
        "clauses": [
            {"code": "AWS D1.1:2025", "clause": "Clause 5", "topic": "Prequalified WPS"},
            {"code": "AWS D1.1:2025", "clause": "Clause 6", "topic": "Qualification"},
            {"code": "AWS D1.1:2025", "clause": "Clause 8", "topic": "Inspection"},
        ],
    },
    "bolting": {
        "keywords": ["bolt", "a325", "a490", "f3125", "slip-critical", "bearing"],
        "clauses": [
            {"code": "AISC 360-22", "clause": "Section J3", "topic": "Bolted Connections"},
            {"code": "RCSC 2020", "clause": "Ch. 8", "topic": "Pre-installation verification"},
        ],
    },
    "fabrication": {
        "keywords": ["fabricat", "shop drawing", "aisc cert", "quality"],
        "clauses": [
            {"code": "AISC 303-22", "clause": "Section 4", "topic": "Shop & Erection Drawings"},
            {"code": "AISC 207-25", "clause": "Ch. 1-6", "topic": "Certification Standard"},
        ],
    },
    "erection": {
        "keywords": ["erect", "plumb", "tolerance", "anchor bolt"],
        "clauses": [
            {"code": "AISC 303-22", "clause": "Section 7", "topic": "Erection Tolerances"},
            {"code": "OSHA 1926.756", "clause": "Subpart R", "topic": "Steel Erection Safety"},
        ],
    },
    "coatings": {
        "keywords": ["paint", "coat", "sspc", "galvaniz", "primer", "intumescent"],
        "clauses": [
            {"code": "SSPC-PA 1", "clause": "Section 4", "topic": "Shop Painting"},
            {"code": "AISC 360-22", "clause": "Appendix 4", "topic": "Structural Design for Fire"},
        ],
    },
    "inspection": {
        "keywords": ["inspect", "special inspect", "testing", "ndt", "ut", "mt", "pt", "rt"],
        "clauses": [
            {"code": "AWS D1.1:2025", "clause": "Clause 8", "topic": "Inspection Requirements"},
            {"code": "IBC 2024", "clause": "Section 1705", "topic": "Special Inspections"},
            {"code": "AISC 360-22", "clause": "Chapter N", "topic": "Quality Assurance"},
        ],
    },
}


# ═══ CSI SPEC PARSER ══════════════════════════════════════════════

def parse_spec_sections(text: str) -> List[Dict]:
    """Extract CSI MasterFormat sections from specification text."""
    found = []
    # Pattern: "05 12 00" or "051200" or "Section 05 12 00"
    pattern = re.compile(r'(?:section\s+)?(\d{2})\s*(\d{2})\s*(\d{2})', re.IGNORECASE)

    for match in pattern.finditer(text):
        code = f"{match.group(1)} {match.group(2)} {match.group(3)}"
        if code in CSI_STEEL_SECTIONS:
            info = CSI_STEEL_SECTIONS[code]
            # Get surrounding context (±200 chars)
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]

            found.append({
                "csi_code": code,
                "title": info["title"],
                "steel_relevance": info["steel_relevance"],
                "context_preview": context[:300],
                "is_pemb": code == "13 34 00",
            })

    return found


# ═══ SUBMITTAL EXTRACTOR ══════════════════════════════════════════

def extract_submittals(text: str, project_name: str = "") -> List[Dict]:
    """Extract submittal requirements from spec text.
    Returns structured submittal items with AWS/AISC clause links.
    """
    submittals = []
    sections = parse_spec_sections(text)

    # Keyword-based submittal detection
    submittal_patterns = [
        (r'submit(?:tal)?.*?(?:shop\s*draw|erection\s*draw)', "Shop/Erection Drawings"),
        (r'submit(?:tal)?.*?(?:wps|welding\s*procedure)', "Welding Procedure Specifications"),
        (r'submit(?:tal)?.*?(?:mill\s*cert|material\s*test)', "Mill Certificates / MTRs"),
        (r'submit(?:tal)?.*?(?:product\s*data|manufacturer)', "Product Data"),
        (r'submit(?:tal)?.*?(?:qualif|certif)', "Welder/Fabricator Qualifications"),
        (r'submit(?:tal)?.*?(?:sample|mock-?up)', "Samples / Mock-ups"),
        (r'submit(?:tal)?.*?(?:test\s*report|inspection)', "Test/Inspection Reports"),
        (r'submit(?:tal)?.*?(?:paint|coat|color)', "Coating/Paint Submittals"),
        (r'submit(?:tal)?.*?(?:bolt|connect)', "Connection/Bolt Submittals"),
        (r'submit(?:tal)?.*?(?:calc|design)', "Structural Calculations"),
    ]

    text_lower = text.lower()
    for pattern, sub_type in submittal_patterns:
        if re.search(pattern, text_lower):
            # Find related code clauses
            related_clauses = []
            for category, clause_info in CODE_CLAUSES.items():
                if any(kw in sub_type.lower() for kw in clause_info["keywords"]):
                    related_clauses.extend(clause_info["clauses"])

            submittals.append({
                "type": sub_type,
                "project": project_name,
                "csi_sections": [s["csi_code"] for s in sections],
                "related_clauses": related_clauses,
                "due_offset_days": _estimate_due_offset(sub_type),
                "status": "REQUIRED",
            })

    return submittals


def _estimate_due_offset(sub_type: str) -> int:
    """Estimate days from NTP to submittal due date."""
    offsets = {
        "Shop/Erection Drawings": 21,
        "Welding Procedure Specifications": 14,
        "Mill Certificates / MTRs": 28,
        "Product Data": 14,
        "Welder/Fabricator Qualifications": 14,
        "Coating/Paint Submittals": 21,
        "Connection/Bolt Submittals": 21,
        "Structural Calculations": 21,
    }
    return offsets.get(sub_type, 21)


# ═══ CODE CLAUSE LINKER ══════════════════════════════════════════

def link_clauses(text: str) -> List[Dict]:
    """Scan text for code references and link to our compliance modules."""
    links = []
    text_lower = text.lower()

    for category, info in CODE_CLAUSES.items():
        if any(kw in text_lower for kw in info["keywords"]):
            links.append({
                "category": category,
                "matched_keywords": [kw for kw in info["keywords"] if kw in text_lower],
                "clauses": info["clauses"],
                "our_modules": _get_our_modules(category),
            })

    return links


def _get_our_modules(category: str) -> list:
    """Map code categories to our existing Virtual Office modules."""
    module_map = {
        "welding": ["aws_d11_2025", "aws_d11_2025_v2", "weld_consumable"],
        "bolting": ["calculators (bolt_torque)"],
        "fabrication": ["aisc_207_audit", "shop_floor", "documents"],
        "erection": ["shop_floor", "productivity_kpis"],
        "coatings": ["shop_floor (BLAST/PAINT stations)"],
        "inspection": ["aws_d11_2025", "aisc_207_audit", "houston_permits"],
    }
    return module_map.get(category, [])


# ═══ ADDENDUM DIFF ════════════════════════════════════════════════

def diff_documents(text_old: str, text_new: str) -> dict:
    """Compare two document versions and highlight steel-relevant changes."""
    old_lines = set(text_old.strip().split("\n"))
    new_lines = set(text_new.strip().split("\n"))

    added = new_lines - old_lines
    removed = old_lines - new_lines

    # Filter for steel-relevant changes
    steel_keywords = ["steel", "weld", "bolt", "connect", "erect", "fabricat",
                      "joist", "deck", "embed", "anchor", "brace", "column", "beam"]
    steel_added = [l for l in added if any(kw in l.lower() for kw in steel_keywords)]
    steel_removed = [l for l in removed if any(kw in l.lower() for kw in steel_keywords)]

    return {
        "total_added": len(added),
        "total_removed": len(removed),
        "steel_added": steel_added[:20],
        "steel_removed": steel_removed[:20],
        "steel_change_count": len(steel_added) + len(steel_removed),
        "needs_review": len(steel_added) + len(steel_removed) > 0,
    }


# ═══ SHOP DRAWING REVIEW CLASSIFIER ══════════════════════════════

def classify_review_comments(comments_text: str) -> dict:
    """Classify shop drawing review response.
    Categories: APPROVED, APPROVED_AS_NOTED, REVISE_RESUBMIT, REJECTED, INFO_ONLY
    """
    text = comments_text.lower()

    if "reject" in text:
        status = "REJECTED"
    elif "revise" in text and ("resubmit" in text or "re-submit" in text):
        status = "REVISE_RESUBMIT"
    elif "approved as noted" in text or "approved with comments" in text:
        status = "APPROVED_AS_NOTED"
    elif "no exceptions" in text or "approved" in text:
        status = "APPROVED"
    else:
        status = "INFO_ONLY"

    return {
        "status": status,
        "action_required": status in ("REVISE_RESUBMIT", "REJECTED"),
        "original_text": comments_text[:500],
    }


# ═══ FULL DOCUMENT ANALYSIS ══════════════════════════════════════

def analyze_document(text: str, doc_type: str = "spec",
                     project_name: str = "") -> dict:
    """Full document intelligence pipeline."""
    result = {
        "project": project_name,
        "doc_type": doc_type,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }

    if doc_type == "spec":
        result["csi_sections"] = parse_spec_sections(text)
        result["submittals"] = extract_submittals(text, project_name)
        result["code_links"] = link_clauses(text)
        result["is_pemb"] = any(s.get("is_pemb") for s in result["csi_sections"])

    elif doc_type == "shop_drawing_review":
        result["classification"] = classify_review_comments(text)

    elif doc_type == "addendum":
        result["code_links"] = link_clauses(text)
        result["submittals"] = extract_submittals(text, project_name)

    # Emit to event bus
    try:
        from bridge.event_bus import emit
        emit("DOC_ANALYZED", {
            "project": project_name, "doc_type": doc_type,
            "sections": len(result.get("csi_sections", [])),
            "submittals": len(result.get("submittals", [])),
        })
    except Exception:pass

    return result
