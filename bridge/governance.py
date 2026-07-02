"""
Your Company Virtual Office - Three-Tier Governance
=================================================
Ported from Linux build. Three layers, strict priority:

  Tier 1 (IMMUTABLE) - Compliance rules. Cannot be overridden by anyone.
    Examples: No LLM math, no supplier names on bids, TX FLSA OT rules,
    AISC weight authority, SHA-256 calibration integrity.

  Tier 2 (CEO) - the Owner's preferences, auto-logged from conversation.
    Examples: Navy/Gold brand, no em-dashes, PDF as final format,
    specific rate overrides, project-specific instructions.

  Tier 3 (DEFAULTS) - Joseph's operational defaults. Lowest priority.
    Examples: dev-mode settings, API routing preferences, logging levels,
    default bid template, UI display prefs.

Resolution: Tier 1 always wins. Tier 2 overrides Tier 3.
             Conflicts logged to audit trail for visibility.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_GOV_FILE = _DATA_DIR / "governance.json"
_AUDIT_FILE = _DATA_DIR / "governance_audit.jsonl"


# ── Tier 1: Compliance Immutable ──────────────────────────────────────
# the Owner's 20 hard rules (directives Section 2) + system integrity.
# Hard-coded. No file, no override, no exceptions.
COMPLIANCE_IMMUTABLE = {
    # the Owner's 20 hard rules (directives v4.0)
    "claude_owns_takeoff": {
        "rule": "Claude owns 100% of takeoff. No 'Ivan to verify.' "
                "No 'Owner to confirm.' No 'Pending review.' Ever.",
        "enforcement": "hard_block",
    },
    "read_general_notes_first": {
        "rule": "Read S-001/S-002 General Structural Notes before any "
                "plan sheet. General notes always govern.",
        "enforcement": "hard_block",
    },
    "scale_from_images": {
        "rule": "Scale areas from rasterized images. Never from text alone.",
        "enforcement": "hard_block",
    },
    "no_supplier_names_on_bids": {
        "rule": "No supplier names in any client-facing document. Use "
                "'qualified suppliers per ASTM/SDI specifications.'",
        "enforcement": "hard_block",
    },
    "no_pe_names": {
        "rule": "Never name individual PEs. Use 'PE-stamped per Texas "
                "registration.'",
        "enforcement": "hard_block",
    },
    "no_headcount_disclosure": {
        "rule": "Never disclose headcount. Say 'YOUR COMPANY ironworker "
                "crew' only. Never a number.",
        "enforcement": "hard_block",
    },
    "no_eng_line_item": {
        "rule": "Engineering costs folded into fab + erection rates "
                "(Shaw Ryan partnership). Never line-itemed.",
        "enforcement": "hard_block",
    },
    "no_alamo_heights_address": {
        "rule": "Never use Alamo Heights / 5600 Broadway addresses. "
                "Houston canonical address only.",
        "enforcement": "hard_block",
    },
    "payment_30_20_50": {
        "rule": "Payment terms always 30/20/50 (mobilization / first "
                "delivery / SOV). Never 40/20/40.",
        "enforcement": "hard_block",
    },
    "no_pemb_language": {
        "rule": "No Red Dot Buildings or PEMB-manufacturer language "
                "(Butler, VP, Nucor, Mueller, MBCI, Red Dot).",
        "enforcement": "hard_block",
    },
    "janus_excluded_self_storage": {
        "rule": "Janus storage system always excluded on self-storage "
                "bids as 'CSI 10 51 13 - by Others.'",
        "enforcement": "hard_block",
    },
    "structural_steel_only": {
        "rule": "Structural steel only. Never cold-formed metal framing "
                "(CFMF). Exclude as 'CSI 05 4000 - by Others.'",
        "enforcement": "hard_block",
    },
    "deck_always_in_scope": {
        "rule": "Deck supply and installation always in scope. Never "
                "optional.",
        "enforcement": "hard_block",
    },
    "porsche_plano_excluded": {
        "rule": "[FORBIDDEN PROJECT] is FORBIDDEN. Never list, never "
                "reference, never mention. Not a Your Company project.",
        "enforcement": "hard_block",
    },
    "two_pdfs_per_bid": {
        "rule": "Two PDFs per bid: client proposal + GP report "
                "(-GP suffix). Never one. Never three.",
        "enforcement": "soft_warn",
    },
    "pdf_only_final_output": {
        "rule": "PDF only as final output. Never .docx to clients.",
        "enforcement": "hard_block",
    },
    "designer_pdf_splice": {
        "rule": "Designer PDFs: never rebuild whole document. Use "
                "pypdf + reportlab splice. Preserve untouched pages.",
        "enforcement": "hard_block",
    },
    "literal_ampersand": {
        "rule": "Source strings always literal '&', never '&amp;'.",
        "enforcement": "hard_block",
    },
    "internal_info_stays_internal": {
        "rule": "Internal info stays internal. Client doc shows "
                "percentages and triggers only. No cash-flow rationale.",
        "enforcement": "hard_block",
    },
    "no_company_age_assertion": {
        "rule": "Never assert company maturity (Est. 2017) without "
                "confirming with Owner. The 2017 vs Feb 2025 LLC "
                "conflict is unresolved. Use 'led by a CEO with 9+ "
                "years in structural steel.'",
        "enforcement": "hard_block",
    },
    # System integrity rules (not from the Owner's 20 but critical)
    "no_llm_math": {
        "rule": "Weights from AISC CSV, costs from RSMeans/calibration. "
                "No LLM-computed estimates.",
        "enforcement": "hard_block",
    },
    "double_authority_seam": {
        "rule": "BidGuard handles weight (lbs), CostEngine handles "
                "cost ($). Formulas never shared between the two.",
        "enforcement": "hard_block",
    },
    "sha256_boot_integrity": {
        "rule": "App refuses to start if any calibration CSV is tampered.",
        "enforcement": "hard_block",
    },
    "outreach_preview_gate": {
        "rule": "MCP-exposed draft_refinery_outreach always forces "
                "preview_only=True.",
        "enforcement": "hard_block",
    },
    "five_input_outreach": {
        "rule": "company, contact_name, contact_role, hook, "
                "timing_reason all required for outreach.",
        "enforcement": "hard_block",
    },
    "tx_flsa_ot": {
        "rule": "OT at 40hr x 1.5. No double-time in Texas.",
        "enforcement": "hard_block",
    },
}


# ── Tier 3: Joseph Defaults ──────────────────────────────────────────
# Lowest priority. Overridden by CEO prefs and compliance rules.
JOSEPH_DEFAULTS = {
    "api_routing": "cost_optimized",       # Use cheapest model that works
    "log_level": "info",
    "default_bid_template": "STANDARD",
    "auto_save_conversations": True,
    "max_conversation_age_days": 90,
    "font_size": "medium",
    "sidebar_default": "collapsed",
    "theme": "navy_gold",
    "sms_morning_briefing": True,
    "sms_bid_alerts": True,
    "sms_compliance_alerts": True,
    "auto_process_short_circuit": True,     # pdfplumber short-circuit
    "dev_mode": False,
    "mcp_preview_lock": True,
}


# ── Storage ───────────────────────────────────────────────────────────

def _load_gov() -> dict:
    """Load governance state from disk."""
    if _GOV_FILE.exists():
        try:
            return json.loads(_GOV_FILE.read_text())
        except Exception:
            pass
    return {"ceo_prefs": {}, "joseph_overrides": {}}


def _save_gov(data: dict):
    """Persist governance state."""
    _DATA_DIR.mkdir(exist_ok=True)
    _GOV_FILE.write_text(json.dumps(data, indent=2, default=str))


def _audit_log(action: str, tier: str, key: str, value: Any,
               reason: str = ""):
    """Append to governance audit trail."""
    _DATA_DIR.mkdir(exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "tier": tier,
        "key": key,
        "value": str(value)[:200],
        "reason": reason,
    }
    with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Tier 2: CEO Preferences ──────────────────────────────────────────

def set_ceo_pref(key: str, value: Any, reason: str = "") -> dict:
    """Set a CEO preference. Blocked if it conflicts with Tier 1."""
    # Check compliance conflict
    # vj: parity-ok (pass 10g classified: dispatcher J=0.14; disjoint shapes)
    if key in COMPLIANCE_IMMUTABLE:
        _audit_log("BLOCKED", "tier1", key, value,
                   f"CEO pref blocked by compliance rule: "
                   f"{COMPLIANCE_IMMUTABLE[key]['rule']}")
        return {
            "ok": False,
            "error": f"Cannot override compliance rule: {key}",
            "rule": COMPLIANCE_IMMUTABLE[key]["rule"],
        }

    gov = _load_gov()
    old = gov["ceo_prefs"].get(key)
    gov["ceo_prefs"][key] = value
    _save_gov(gov)
    _audit_log("SET", "tier2_ceo", key, value, reason)

    return {"ok": True, "key": key, "value": value,
            "previous": old, "tier": "ceo"}


def get_ceo_pref(key: str) -> Any:
    """Get a CEO preference value, or None if not set."""
    gov = _load_gov()
    return gov["ceo_prefs"].get(key)


def clear_ceo_pref(key: str) -> dict:
    """Remove a CEO preference (falls back to Joseph default)."""
    gov = _load_gov()
    old = gov["ceo_prefs"].pop(key, None)
    _save_gov(gov)
    _audit_log("CLEAR", "tier2_ceo", key, old, "preference removed")
    return {"ok": True, "key": key, "removed": old}


# ── Resolution ────────────────────────────────────────────────────────

def resolve(key: str) -> dict:
    """Resolve a setting through all three tiers.

    Returns:
        tier: which tier provided the value
        value: the resolved value
        source: "compliance" | "ceo" | "default"
    """
    # Tier 1: compliance rules are not key-value settings, they're rules.
    # This resolver is for operational settings, not compliance checks.

    # Tier 2: CEO prefs
    gov = _load_gov()
    ceo_val = gov["ceo_prefs"].get(key)
    if ceo_val is not None:
        return {"tier": 2, "value": ceo_val, "source": "ceo"}

    # Tier 3: Joseph defaults
    default_val = JOSEPH_DEFAULTS.get(key)
    if default_val is not None:
        return {"tier": 3, "value": default_val, "source": "default"}

    return {"tier": 0, "value": None, "source": "not_found"}


def resolve_all() -> dict:
    """Resolve all known settings with tier attribution."""
    result = {}
    all_keys = set(JOSEPH_DEFAULTS.keys())
    gov = _load_gov()
    all_keys.update(gov.get("ceo_prefs", {}).keys())

    for key in sorted(all_keys):
        result[key] = resolve(key)
    return result


# ── Compliance Checks ─────────────────────────────────────────────────

def check_compliance(content: str, context: str = "bid") -> list[dict]:
    """Check content against Tier 1 compliance rules (Pass 3 leak scan).

    Implements directives Section 15: Forbidden items in client-facing
    documents. Returns list of violations found. Empty list = compliant.

    Context: "bid" (strictest), "email", "marketing", "internal" (relaxed).
    """
    import re
    violations = []
    content_lower = content.lower()

    # Only run client-facing checks for client-facing contexts
    client_facing = context in ("bid", "email", "marketing", "soq")

    # ── [FORBIDDEN PROJECT] (always, any context) ────────────────────────
    if "porsche" in content_lower and "plano" in content_lower:
        violations.append({
            "rule": "porsche_plano_excluded",
            "severity": "hard_block",
            "detail": "[FORBIDDEN PROJECT] referenced. Not a Your Company project.",
        })

    # ── Red Dot / PEMB-manufacturer language ──────────────────────────
    pemb_brands = ["red dot", "butler", "mueller", "mbci",
                   "red iron", "tapered built-up"]
    for brand in pemb_brands:
        if brand in content_lower:
            violations.append({
                "rule": "no_pemb_language",
                "severity": "hard_block",
                "detail": f"PEMB/manufacturer language '{brand}' detected.",
            })

    if not client_facing:
        return violations

    # ── Supplier names (directives Section 15 + anchor bolt vendors) ──
    supplier_patterns = [
        # Steel suppliers
        "nucor", "steel dynamics", "commercial metals",
        "worthington", "metals usa", "peyton",
        "triple-s steel", "triple-s", "brown strauss", "service steel",
        # Deck suppliers
        "vulcraft", "canam", "ayamsa",
        # Anchor bolt vendors
        "j.h. botts", "jh botts", "atlanta rod", "a&m nut",
        # Competitors (should not appear as suppliers)
        "schuff", "herrick", "cives",
    ]
    for supplier in supplier_patterns:
        if supplier in content_lower:
            violations.append({
                "rule": "no_supplier_names_on_bids",
                "severity": "hard_block",
                "detail": f"Supplier name '{supplier}' in client-facing doc. "
                          "Use 'qualified suppliers per ASTM/SDI specifications.'",
            })

    # ── Internal team names (never individually on client docs) ───────
    team_names = ["ivan", "mario", "amber", "paul", "joseph",
                  "paul guerrero", "john gil", "jesus juan"]
    for name in team_names:
        # Avoid false positives: require word boundary or context
        if re.search(rf"\b{re.escape(name)}\b", content_lower):
            violations.append({
                "rule": "no_pe_names",
                "severity": "hard_block",
                "detail": f"Internal team member '{name}' named in "
                          "client-facing document.",
            })

    # ── Generic PE name disclosure ────────────────────────────────────
    # Directives §15: "Never name individual PEs"
    if re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+,?\s*P\.?E\.?\b", content):
        violations.append({
            "rule": "no_pe_names",
            "severity": "hard_block",
            "detail": "Individual PE named. Use 'PE-stamped per Texas "
                      "registration.'",
        })

    # ── Headcount disclosure ──────────────────────────────────────────
    headcount_patterns = [
        r"\b\d+[\-\s]*person\s+crew\b",
        r"\b\d+\s+full[\-\s]time\b",
        r"\bour\s+team\s+of\s+\d+\b",
        r"\b12[\-\s]*person\b",
        r"\btwelve\s+(?:full|iron|fabricat)\b",
        r"\b\d+\s+employees?\b",            # "12 employees"
        r"\b\d+\s+(?:iron)?workers?\b",      # "12 ironworkers"
    ]
    for pat in headcount_patterns:
        if re.search(pat, content_lower):
            violations.append({
                "rule": "no_headcount_disclosure",
                "severity": "hard_block",
                "detail": "Headcount disclosure detected. Use 'YOUR COMPANY "
                          "ironworker crew' only.",
            })
            break

    # ── Wrong address ─────────────────────────────────────────────────
    if "5600 broadway" in content_lower or "alamo heights" in content_lower:
        violations.append({
            "rule": "no_alamo_heights_address",
            "severity": "hard_block",
            "detail": "Wrong address. Use Houston canonical address only.",
        })

    # ── Wrong phone ───────────────────────────────────────────────────
    if "(210) 971-6820" in content or "210-971-6820" in content:
        violations.append({
            "rule": "wrong_phone",
            "severity": "hard_block",
            "detail": "Wrong phone number. Use [COMPANY PHONE].",
        })

    # ── Payment terms 40/20/40 (dead) ─────────────────────────────────
    if "40/20/40" in content or "40-20-40" in content_lower:
        violations.append({
            "rule": "payment_30_20_50",
            "severity": "hard_block",
            "detail": "40/20/40 payment terms are dead. Use 30/20/50.",
        })

    # ── Engineering as line item ──────────────────────────────────────
    eng_patterns = [
        r"engineering\s*[\$\d]", r"engineering\s*cost",
        r"engineering\s*fee", r"eng\.\s*[\$\d]",
        r"engineering\s*[:\-]\s*[\$\d]",
    ]
    for pat in eng_patterns:
        if re.search(pat, content_lower):
            violations.append({
                "rule": "no_eng_line_item",
                "severity": "hard_block",
                "detail": "Engineering as separate line item. Fold into "
                          "fab + erection rate.",
            })
            break

    # ── Ivan to verify / Owner to confirm ───────────────────────────
    ownership_violations = [
        "ivan to verify", "ivan to review", "owner to confirm",
        "pending review", "pending verification",
    ]
    for phrase in ownership_violations:
        if phrase in content_lower:
            violations.append({
                "rule": "claude_owns_takeoff",
                "severity": "hard_block",
                "detail": f"'{phrase}' found. Claude owns 100% of takeoff.",
            })

    # ── Cash-flow rationale (internal only) ───────────────────────────
    cashflow_leaks = [
        "steel pos don't move", "steel pos do not move",
        "until cash is received", "until cash is in",
        "this payment funds", "30% covers phase",
        "deposits cover", "deposit covers",  # singular + plural
        "float the project", "funds the project",
        "covers phase 1", "covers all materials",
        "never out-of-pocket", "out of pocket",
    ]
    for phrase in cashflow_leaks:
        if phrase in content_lower:
            violations.append({
                "rule": "internal_info_stays_internal",
                "severity": "hard_block",
                "detail": f"Cash-flow rationale leaked: '{phrase}'. "
                          "Show percentages and triggers only.",
            })

    # ── Tilde on quantities ───────────────────────────────────────────
    if context == "bid" and re.search(r"~\s*\d", content):
        violations.append({
            "rule": "no_tilde_quantities",
            "severity": "hard_block",
            "detail": "Tilde (~) on a quantity. Use exact measured number.",
        })

    # ── Company age assertion ─────────────────────────────────────────
    if re.search(r"est\.?\s*2017\b", content_lower):
        violations.append({
            "rule": "no_company_age_assertion",
            "severity": "hard_block",
            "detail": "'Est. 2017' found. Use 'led by a CEO with 9+ years "
                      "in structural steel.' (LLC conflict unresolved.)",
        })

    # ── &amp; in source strings ───────────────────────────────────────
    if "&amp;" in content:
        violations.append({
            "rule": "literal_ampersand",
            "severity": "hard_block",
            "detail": "'&amp;' found. Use literal '&'.",
        })

    # ── Competitor lead time claims ───────────────────────────────────
    if "14-16" in content and "week" in content_lower:
        violations.append({
            "rule": "wrong_lead_time",
            "severity": "hard_block",
            "detail": "14-16 wks fabrication is a competitor's number. "
                      "Your Company: 2-3 wks shop drawings + 3-4 wks delivery.",
        })

    # ── Margin/GP/cost in client doc ──────────────────────────────────
    if context == "bid":
        margin_leaks = [
            r"\bgp\s*%", r"\bgross\s+profit", r"\bmargin\s*%",
            r"\bmargin\b.*\d+\s*%",   # "our margin is 25%"
            r"\d+\s*%\s*margin\b",    # "25% margin" (reversed)
            r"\bgp\s*:\s*\d",         # "GP: 28%" (bare abbreviation)
            r"\binternal\s+cost", r"\$\s*/\s*ton\b", r"\$\s*/\s*sf\b",
        ]
        for pat in margin_leaks:
            if re.search(pat, content_lower):
                violations.append({
                    "rule": "internal_info_stays_internal",
                    "severity": "hard_block",
                    "detail": "Internal cost/margin data in client document.",
                })
                break

    return violations


# ── Status / Summary ──────────────────────────────────────────────────

def governance_status() -> dict:
    """Full governance status for the STATUS tab."""
    gov = _load_gov()
    audit_count = 0
    if _AUDIT_FILE.exists():
        audit_count = sum(1 for _ in open(_AUDIT_FILE, encoding="utf-8"))

    return {
        "tier1_rules": len(COMPLIANCE_IMMUTABLE),
        "tier2_ceo_prefs": len(gov.get("ceo_prefs", {})),
        "tier3_defaults": len(JOSEPH_DEFAULTS),
        "audit_entries": audit_count,
        "ceo_prefs": gov.get("ceo_prefs", {}),
        "resolved": resolve_all(),
    }


def get_audit_trail(limit: int = 50) -> list[dict]:
    """Read recent governance audit entries."""
    if not _AUDIT_FILE.exists():
        return []
    entries = []
    for line in open(_AUDIT_FILE, encoding="utf-8"):
        try:
            entries.append(json.loads(line.strip()))
        except Exception:
            pass
    return entries[-limit:]
