"""Cost Flag Scanner - detects specification clauses that impact bid pricing.

13 flags per the Phase 5 roadmap:
  1. PREVAILING_WAGE - Davis-Bacon or state prevailing wage requirements
  2. BONDING_REQUIRED - Performance/payment bond language
  3. LIQUIDATED_DAMAGES - LD clauses with daily penalties
  4. RETAINAGE - Holdback percentages beyond standard
  5. CERTIFIED_WELDING - AWS D1.1 or special weld certifications
  6. SPECIAL_INSPECTION - Third-party inspection requirements
  7. SHOP_DRAWINGS_TIMELINE - Compressed shop drawing schedules
  8. GALVANIZING - Hot-dip galvanizing requirements
  9. FIRE_RATING - Fireproofing or intumescent coating
  10. SEISMIC_CATEGORY - SDC D/E/F requiring special detailing
  11. BLAST_LOADING - Progressive collapse or blast resistance
  12. OWNER_DIRECTED_SUPPLIER - Sole-source material requirements
  13. ORDER_OF_PRECEDENCE - Document hierarchy clause (Specs vs Drawings vs Addenda)
"""

import re
import logging
from typing import List, Dict

log = logging.getLogger("spec_auditor")

COST_FLAGS = [
    {"id": "PREVAILING_WAGE", "patterns": [r"prevailing\s+wage", r"davis[\-\s]bacon", r"certified\s+payroll"],
     "impact": "Labor rates increase 15-40%. Factor into erection cost."},
    {"id": "BONDING_REQUIRED", "patterns": [r"performance\s+bond", r"payment\s+bond", r"surety\s+bond", r"bond\s+required"],
     "impact": "Add 2-3% of contract value."},
    {"id": "LIQUIDATED_DAMAGES", "patterns": [r"liquidated\s+damages", r"\$\s*\d+.*per\s*(calendar|working)?\s*day"],
     "impact": "Schedule risk. Verify completion date feasibility."},
    {"id": "RETAINAGE", "patterns": [r"retainage\s+of\s+\d+", r"retain\s+\d+\s*%", r"holdback"],
     "impact": "Cash flow impact. Standard is 5-10%."},
    {"id": "CERTIFIED_WELDING", "patterns": [r"aws\s+d1\.1", r"certified\s+welder", r"cwi\s+required", r"weld\s+procedure\s+qualification"],
     "impact": "Already in Your Company scope. Verify WPS on file."},
    {"id": "SPECIAL_INSPECTION", "patterns": [r"special\s+inspection", r"third[- ]party\s+inspection", r"ibc\s+1705"],
     "impact": "Coordination cost. Inspector access to shop."},
    {"id": "SHOP_DRAWINGS_TIMELINE", "patterns": [r"shop\s+drawings?\s+within\s+\d+", r"submittal\s+schedule.*\d+\s*(calendar|working)?\s*days"],
     "impact": "Compressed timeline. Check Tekla capacity."},
    {"id": "GALVANIZING", "patterns": [r"hot[\-\s]dip\s+galvaniz", r"astm\s+a123", r"astm\s+a153", r"galvanized\s+steel"],
     "impact": "Material cost increase ~30%. Lead time +2-3 weeks."},
    {"id": "FIRE_RATING", "patterns": [r"fireproof", r"intumescent", r"fire[\-\s]rated\s+coating", r"spray[\-\s]applied\s+fire"],
     "impact": "Subcontract item. Exclude from steel scope unless directed."},
    {"id": "SEISMIC_CATEGORY", "patterns": [r"seismic\s+design\s+category\s+[d-f]", r"sdc\s+[d-f]", r"special\s+moment\s+frame"],
     "impact": "Connection complexity increase. Verify engineering scope."},
    {"id": "BLAST_LOADING", "patterns": [r"blast\s+(load|resist)", r"progressive\s+collapse", r"gsa\s+criteria"],
     "impact": "Specialty engineering. Major cost adder."},
    {"id": "OWNER_DIRECTED_SUPPLIER", "patterns": [r"sole\s+source", r"owner[\-\s]directed\s+(supplier|vendor)", r"approved\s+equal\s+not\s+accepted"],
     "impact": "Material pricing locked to one vendor. No competitive bids."},
    {"id": "ORDER_OF_PRECEDENCE", "patterns": [
        r"in\s+case\s+of\s+conflict", r"shall\s+govern", r"takes?\s+precedence",
        r"order\s+of\s+precedence", r"conflict.*specifications?\s+shall",
        r"drawings?\s+shall\s+govern", r"addenda?\s+shall\s+govern",
     ],
     "impact": "Document hierarchy established. Governs scope interpretation disputes."},
]


class CostFlagScanner:
    """Scans specification text for clauses that impact bid pricing."""

    def __init__(self):
        self.flags = COST_FLAGS
        self._compiled = []
        for flag in self.flags:
            patterns = [re.compile(p, re.IGNORECASE) for p in flag["patterns"]]
            self._compiled.append({"id": flag["id"], "patterns": patterns,
                                    "impact": flag["impact"]})

    def scan(self, text: str) -> List[Dict]:
        """Scan specification text and return triggered cost flags."""
        results = []
        for flag in self._compiled:
            matches = []
            for pat in flag["patterns"]:
                for m in pat.finditer(text):
                    start = max(0, m.start() - 50)
                    end = min(len(text), m.end() + 50)
                    context = text[start:end].replace("\n", " ").strip()
                    matches.append({"match": m.group(), "context": context,
                                     "position": m.start()})
            if matches:
                results.append({"flag": flag["id"], "impact": flag["impact"],
                                 "occurrences": len(matches),
                                 "matches": matches[:3]})
        return results

    def scan_pages(self, pages: List[str]) -> List[Dict]:
        """Scan multiple pages and return flags with page numbers."""
        all_flags = {}
        for i, page_text in enumerate(pages):
            flags = self.scan(page_text)
            for f in flags:
                fid = f["flag"]
                if fid not in all_flags:
                    all_flags[fid] = {**f, "pages": [i + 1]}
                else:
                    all_flags[fid]["pages"].append(i + 1)
                    all_flags[fid]["occurrences"] += f["occurrences"]
        return list(all_flags.values())


# ---- Extended flags for scan_text / audit_spec_text (Phase 22 roadmap) ----
# These use the flag IDs from the POST_PARITY_ROADMAP and add severity +
# cost estimation that the original CostFlagScanner class does not carry.

_EXTENDED_FLAGS = [
    {"id": "GALVANIZE", "severity": "RED", "label": "Hot-dip galvanizing",
     "patterns": [r"galvaniz", r"ASTM\s*A123", r"\bHDG\b"],
     "cost_per_ton": 1000.0},
    {"id": "BLAST_SP10", "severity": "RED", "label": "Near-white blast (SSPC-SP10)",
     "patterns": [r"SSPC[\s-]*SP[\s-]*10", r"near[\s-]*white"],
     "cost_per_ton": 600.0},
    {"id": "BLAST_SP6", "severity": "AMBER", "label": "Commercial blast (SSPC-SP6)",
     "patterns": [r"SSPC[\s-]*SP[\s-]*6", r"commercial\s+blast"],
     "cost_per_ton": 300.0},
    {"id": "SPECIAL_INSPECT", "severity": "RED", "label": "Special inspection",
     "patterns": [r"special\s+inspection", r"IBC\s*1705"],
     "cost_flat": 10000.0},
    {"id": "NDT_FULL", "severity": "RED", "label": "Full NDT/UT testing",
     "patterns": [r"\bUT\b", r"ultrasonic", r"100\s*%\s*NDT"],
     "cost_flat": 5000.0},
    {"id": "INTUMESCENT", "severity": "RED", "label": "Intumescent fireproofing",
     "patterns": [r"intumescent", r"fire\s+rating", r"UL\s*263"],
     "cost_per_ton": 2000.0},
    {"id": "SEISMIC", "severity": "RED", "label": "Seismic connection requirements",
     "patterns": [r"AISC\s*341", r"\bseismic\b", r"demand\s+critical"],
     "cost_pct": 0.20},
    {"id": "AESS", "severity": "RED", "label": "Architecturally exposed steel",
     "patterns": [r"\bAESS\b", r"architecturally\s+exposed"],
     "cost_pct": 0.40},
    {"id": "PREVAILING_WAGE", "severity": "RED", "label": "Prevailing wage",
     "patterns": [r"Davis[\s-]*Bacon", r"prevailing\s+wage"],
     "cost_pct": 0.30},
    {"id": "BUY_AMERICA", "severity": "AMBER", "label": "Buy America",
     "patterns": [r"Buy\s+America", r"melted\s+and\s+poured"],
     "cost_pct": 0.05},
    {"id": "INORGANIC_ZINC", "severity": "AMBER", "label": "Inorganic zinc primer",
     "patterns": [r"inorganic\s+zinc", r"\bIOZ\b"],
     "cost_per_ton": 400.0},
    {"id": "NO_A36", "severity": "AMBER", "label": "No A36 substitution",
     "patterns": [r"A992\s+only", r"[Nn]o\s+A36"],
     "cost_flat": 0.0},
    {"id": "ORDER_OF_PRECEDENCE", "severity": "AMBER",
     "label": "Order of Precedence",
     "patterns": [
         r"in\s+case\s+of\s+conflict", r"shall\s+govern",
         r"takes?\s+precedence", r"order\s+of\s+precedence",
     ],
     "cost_flat": 0.0},
]


# ── Order of Precedence helper ────────────────────────────────────────────────

_OOP_PATTERNS = [
    # Specs govern
    (re.compile(
        r"(?:specifications?|specs?)\s+(?:shall\s+)?(?:govern|take\s+precedence|prevail)",
        re.IGNORECASE), "Specifications"),
    (re.compile(
        r"in\s+case\s+of\s+conflict.*specifications?\s+shall", re.IGNORECASE | re.DOTALL),
     "Specifications"),
    # Drawings govern
    (re.compile(
        r"(?:drawings?|plans?)\s+(?:shall\s+)?(?:govern|take\s+precedence|prevail)",
        re.IGNORECASE), "Drawings"),
    (re.compile(
        r"in\s+case\s+of\s+conflict.*drawings?\s+shall", re.IGNORECASE | re.DOTALL),
     "Drawings"),
    # Addenda govern
    (re.compile(
        r"(?:addenda?|addendum)\s+(?:shall\s+)?(?:govern|take\s+precedence|prevail)",
        re.IGNORECASE), "Addenda"),
    (re.compile(
        r"in\s+case\s+of\s+conflict.*addenda?\s+shall", re.IGNORECASE | re.DOTALL),
     "Addenda"),
]


def detect_order_of_precedence(text: str) -> dict:
    """Detect which document wins in case of conflict.

    Returns:
        {
            "found": bool,
            "governing_document": str or None,
            "section_ref": str,
            "match_text": str,
            "go_no_go_note": str,
        }

    governing_document is one of: "Specifications", "Drawings", "Addenda",
    or None if a precedence clause was found but the governing doc is unclear.
    """
    if not text:
        return {"found": False, "governing_document": None,
                "section_ref": "", "match_text": "", "go_no_go_note": ""}

    for pat, doc_name in _OOP_PATTERNS:
        m = pat.search(text)
        if m:
            section = _find_section_ref(text, m.start())
            note = f"{doc_name} override Drawings per {section}" if section else \
                   f"{doc_name} govern in case of conflict."
            return {
                "found": True,
                "governing_document": doc_name,
                "section_ref": section,
                "match_text": m.group(0)[:120].strip(),
                "go_no_go_note": note,
            }

    # Precedence clause found but governing doc not deterministic
    generic = re.search(
        r"(?:order\s+of\s+precedence|in\s+case\s+of\s+conflict|shall\s+govern)",
        text, re.IGNORECASE)
    if generic:
        section = _find_section_ref(text, generic.start())
        return {
            "found": True,
            "governing_document": None,
            "section_ref": section,
            "match_text": generic.group(0).strip(),
            "go_no_go_note": "Order of precedence clause found. Review section to determine governing document.",
        }

    return {"found": False, "governing_document": None,
            "section_ref": "", "match_text": "", "go_no_go_note": ""}


def _find_section_ref(text: str, position: int) -> str:
    """Walk backward from match to find nearest CSI section header."""
    preceding = text[:position]
    m = list(re.finditer(
        r"SECTION\s+\d{2}\s*\d{2}\s*\d{2}[^\n]*",
        preceding, re.IGNORECASE,
    ))
    return m[-1].group(0).strip() if m else ""


def scan_text(text: str) -> list:
    """Scan spec text for cost-impacting flags.

    Returns list sorted RED-first, each entry:
        {"id", "severity", "label", "impact_desc", "section_ref", "match_text"}
    """
    if not text or not text.strip():
        return []

    findings = []
    seen = set()

    for flag in _EXTENDED_FLAGS:
        for pattern in flag["patterns"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and flag["id"] not in seen:
                seen.add(flag["id"])
                findings.append({
                    "id": flag["id"],
                    "severity": flag["severity"],
                    "label": flag["label"],
                    "impact_desc": flag.get("label", ""),
                    "section_ref": _find_section_ref(text, m.start()),
                    "match_text": m.group(0).strip(),
                })
                break

    sev_order = {"RED": 0, "AMBER": 1}
    findings.sort(key=lambda f: sev_order.get(f["severity"], 2))
    return findings


def audit_spec_text(text: str, tonnage: float = 0.0) -> dict:
    """Full spec audit with estimated dollar impact."""
    if not text or not text.strip():
        return {"success": True, "findings": [], "red_count": 0,
                "amber_count": 0, "estimated_impact_usd": 0.0,
                "order_of_precedence": None,
                "summary": "No spec text provided."}

    findings = scan_text(text)
    oop = detect_order_of_precedence(text)

    red_count = sum(1 for f in findings if f["severity"] == "RED")
    amber_count = sum(1 for f in findings if f["severity"] == "AMBER")

    total_impact = 0.0
    for finding in findings:
        flag = next((fl for fl in _EXTENDED_FLAGS
                     if fl["id"] == finding["id"]), None)
        if not flag:
            continue
        if flag.get("cost_flat", 0) > 0:
            total_impact += flag["cost_flat"]
        if flag.get("cost_per_ton", 0) > 0 and tonnage > 0:
            total_impact += flag["cost_per_ton"] * tonnage
        if flag.get("cost_pct", 0) > 0 and tonnage > 0:
            total_impact += 3750.0 * tonnage * flag["cost_pct"]

    parts = []
    if red_count:
        parts.append(f"{red_count} RED flags")
    if amber_count:
        parts.append(f"{amber_count} AMBER flags")
    if total_impact > 0:
        parts.append(f"Estimated impact: ${total_impact:,.0f}")

    if oop["found"] and oop["go_no_go_note"]:
        parts.append(oop["go_no_go_note"])

    return {
        "success": True,
        "findings": findings,
        "red_count": red_count,
        "amber_count": amber_count,
        "estimated_impact_usd": total_impact,
        "order_of_precedence": oop if oop["found"] else None,
        "summary": ". ".join(parts) if parts else "No cost flags found.",
    }
