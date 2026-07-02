"""
Virtual Owner (VM) - CEO Bid Review Agent
=============================================
Reviews every bid before PDF generation using the Owner's documented
decision patterns. Either APPROVES (proceed to PDF) or REJECTS
(returns specific corrections).

This is NOT a general assistant. VM does ONE thing: review bids
the way Owner reviews bids. His patterns come from:
  - owner-operating-style.md (iteration pattern, pre-submission checks)
  - bidding-rules.md (structural steel bid rules)
  - Real corrections from email (TSC Sumter, Planet Fitness, King Soopers)

Sits between Sanity Gates (Stage 6.5) and PDF generation.
"""

import logging
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field

log = logging.getLogger("virtual_owner")


# ============================================================
# THE OWNER'S BID REVIEW RULES
# ============================================================
# Extracted from owner-operating-style.md and real bid corrections.

# Rule 1: "Are you sure you have everything?"
# Rule 2: "Is this 100% accurate?"
# Rule 3: "Am I truly covered on all items, to make substantial profit?"
# Rule 4: "Ready to submit to client with confidence and complete takeoff done?"

# From TSC Sumter correction: joist/girder tonnage was undercounted.
# From Planet Fitness correction: wrong deck type, wrong mezzanine SF.
# From his email: "I found enough to look complete and deliver before the work is done."


# ============================================================
# REAL SUPPLIER LIST (internal only - NEVER on client docs)
# ============================================================
# Source: owner-directives-v4.md Section 25.
# Vulcraft and Canam are also forbidden even though they are not
# Your Company's direct suppliers - they must not appear in proposals.
YOUR_COMPANY_SUPPLIERS = [
    # (canonical_display_name, [lowercase_match_variants])
    ("AYAMSA",                   ["ayamsa"]),
    ("Peyton",                   ["peyton"]),
    ("Atlanta Rod",              ["atlanta rod", "atlantarod"]),
    ("J.H. Botts",               ["j.h. botts", "jh botts", "botts"]),
    ("A&M Nut & Bolt",           ["a&m nut", "a&m nut & bolt"]),
    ("Service Steel Warehouse",  ["service steel warehouse", "service steel"]),
    ("Triple-S Steel",           ["triple-s steel", "triple s steel"]),
    ("Brown Strauss",            ["brown strauss"]),
    # Still forbidden (PEMB/structural competitors)
    ("Vulcraft",                 ["vulcraft"]),
    ("Canam",                    ["canam"]),
]


@dataclass
class VMReview:
    """Result of Virtual the Owner's bid review."""
    approved: bool = False
    confidence: int = 0          # 0-100, the Owner's gut check
    verdict: str = ""            # One-line summary
    issues: List[Dict] = field(default_factory=list)  # [{severity, rule, detail}]
    corrections: List[str] = field(default_factory=list)
    owner_would_say: str = ""  # What Owner would actually say seeing this bid

    @property
    def violations(self) -> List[Dict]:
        """Map issues to violations list for test/API compatibility."""
        return [
            {"rule": i.get("rule", ""), "passed": False,
             "violation": i.get("detail", ""), "severity": i.get("severity", "")}
            for i in self.issues
        ]

    def get(self, key: str, default=None):
        """Dict-style get for test code that calls result.get('violations', [])."""
        try:
            return getattr(self, key, default)
        except Exception:
            return default

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "issues": self.issues,
            "violations": self.violations,
            "corrections": self.corrections,
            "owner_would_say": self.owner_would_say,
        }


class VirtualOwner:
    """CEO bid review agent. Reviews bids using the Owner's patterns."""

    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict]:
        """the Owner's bid review checklist. Each rule has a check function."""
        return [
            {"id": "R01", "name": "No engineering line item",
             "severity": "BLOCK",
             "check": self._check_no_engineering_line},
            {"id": "R02", "name": "Deck in scope",
             "severity": "BLOCK",
             "check": self._check_deck_in_scope},
            {"id": "R03", "name": "No supplier names",
             "severity": "BLOCK",
             "check": self._check_no_supplier_names},
            {"id": "R04", "name": "Two PDFs (proposal + GP)",
             "severity": "WARN",
             "check": self._check_two_pdfs},
            {"id": "R05", "name": "Tonnage sanity",
             "severity": "BLOCK",
             "check": self._check_tonnage_sanity},
            {"id": "R06", "name": "Rate consistency",
             "severity": "BLOCK",
             "check": self._check_rates},
            {"id": "R07", "name": "Dollar per SF check",
             "severity": "BLOCK",
             "check": self._check_dollar_per_sf},
            {"id": "R08", "name": "Freight included",
             "severity": "WARN",
             "check": self._check_freight},
            {"id": "R09", "name": "Overhead applied",
             "severity": "WARN",
             "check": self._check_overhead},
            {"id": "R10", "name": "GP margin minimum",
             "severity": "WARN",
             "check": self._check_gp_margin},
            {"id": "R11", "name": "No [FORBIDDEN PROJECT]",
             "severity": "BLOCK",
             "check": self._check_no_porsche_plano},
            {"id": "R12", "name": "No PEMB language",
             "severity": "BLOCK",
             "check": self._check_no_pemb},
            {"id": "R13", "name": "Standard exclusions present",
             "severity": "WARN",
             "check": self._check_exclusions},
            {"id": "R14", "name": "Joist tonnage vs building SF",
             "severity": "BLOCK",
             "check": self._check_joist_tonnage},
            {"id": "R15", "name": "Deck type matches spec",
             "severity": "BLOCK",
             "check": self._check_deck_type},
            {"id": "R16", "name": "PEMB scope separation",
             "severity": "BLOCK",
             "check": self._check_pemb_scope},
            {"id": "R17", "name": "Total SF vs scope SF",
             "severity": "BLOCK",
             "check": self._check_sf_mismatch},
            {"id": "R18", "name": "Mezzanine SF verification",
             "severity": "BLOCK",
             "check": self._check_mezzanine_sf},
            {"id": "R19", "name": "GC comparison flag",
             "severity": "BLOCK",
             "check": self._check_gc_comparison},
            # R20-R26: pilot fixes 2026-05-16
            {"id": "R20", "name": "No internal names in proposal",
             "severity": "BLOCK",
             "check": self._check_names_in_text},
            {"id": "R21", "name": "No Est.2017 claim",
             "severity": "WARN",
             "check": self._check_no_est_2017},
            {"id": "R22", "name": "No headcount disclosure",
             "severity": "BLOCK",
             "check": self._check_no_headcount},
            {"id": "R23", "name": "No 40/20/40 payment terms",
             "severity": "BLOCK",
             "check": self._check_no_forbidden_payment_terms},
            {"id": "R24", "name": "No precedent projects in bids",
             "severity": "BLOCK",
             "check": self._check_no_precedent_projects},
            {"id": "R25", "name": "No em-dash in proposal",
             "severity": "WARN",
             "check": self._check_no_em_dash},
            {"id": "R26", "name": "No three-adjective list",
             "severity": "WARN",
             "check": self._check_no_three_adj_list},
            # R27-R29: Ivan calibration 2026-05-27/28 rules
            {"id": "R27", "name": "Anchor count vs column count",
             "severity": "BLOCK",
             "check": self._check_anchor_count},
            {"id": "R28", "name": "Connection allowance vs structural system",
             "severity": "WARN",
             "check": self._check_connection_allowance},
            {"id": "R29", "name": "Joist series matches building type",
             "severity": "WARN",
             "check": self._check_joist_series},
        ]

    def review(self, bid: Dict) -> VMReview:
        """Run the Owner's full review on a bid.

        Args:
            bid: dict with keys:
                project_name, gc_name, building_sf, building_type,
                struct_tons, joist_tons, total_bid, total_cost (hard cost),
                line_items (list of dicts with name, amount),
                exclusions (list of strings),
                deck_sf, deck_type, distance_mi, freight,
                overhead_mult, gp_margin,
                text_content (full text of proposal for scanning)

        Returns:
            VMReview with approved/rejected + specific issues
        """
        # R3: accept any common text field alias; raise loud on missing text
        bid = dict(bid)  # don't mutate caller's dict
        _TEXT_KEYS = ("text_content", "proposal_text", "body", "bid_text", "text")
        _proposal_text = None
        for _k in _TEXT_KEYS:
            if _k in bid and bid[_k]:
                _proposal_text = bid[_k]
                break
        if not _proposal_text:
            raise ValueError(
                "VirtualOwner.review() requires a non-empty text field. "
                f"Accepted keys: {_TEXT_KEYS}. Got keys: {list(bid.keys())}"
            )
        bid["text_content"] = _proposal_text  # normalize for all check methods

        review = VMReview()
        issues = []

        for rule in self.rules:
            try:
                result = rule["check"](bid)
                if result:
                    issues.append({
                        "severity": rule["severity"],
                        "rule": f'{rule["id"]}: {rule["name"]}',
                        "detail": result,
                    })
            except Exception as e:
                log.warning(f'VM rule {rule["id"]} error: {e}')

        review.issues = issues
        blockers = [i for i in issues if i["severity"] == "BLOCK"]
        warnings = [i for i in issues if i["severity"] == "WARN"]

        # Confidence scoring
        score = 100
        score -= len(blockers) * 25
        score -= len(warnings) * 5
        review.confidence = max(0, min(100, score))

        # Decision
        if blockers:
            review.approved = False
            review.verdict = f"REJECTED: {len(blockers)} blocker(s), {len(warnings)} warning(s)"
            review.corrections = [b["detail"] for b in blockers]
            review.owner_would_say = self._generate_owner_response(bid, blockers, warnings)
        elif warnings:
            review.approved = True
            review.verdict = f"APPROVED WITH NOTES: {len(warnings)} warning(s)"
            review.owner_would_say = f"Looks solid. {len(warnings)} note(s) to check before sending."
        else:
            review.approved = True
            review.verdict = "APPROVED: Clean bid"
            review.confidence = 100
            review.owner_would_say = "Good to go. Send it."

        log.info(f"VM Review: {review.verdict} (confidence {review.confidence}/100)")
        return review

    # ── RULE IMPLEMENTATIONS ──────────────────────────────────

    def _check_no_engineering_line(self, bid: Dict) -> Optional[str]:
        """Engineering costs folded into fab+erection. Never a line item."""
        for item in bid.get("line_items", []):
            name = (item.get("name") or item.get("desc") or "").lower()
            if "engineering" in name and "erection" not in name and "fab" not in name:
                return f'Engineering is a separate line item (${item.get("amount",0):,.0f}). Fold into fab+erection rates.'
        text = (bid.get("text_content") or "").lower()
        if "engineering fee" in text or "engineering cost" in text:
            return "Engineering fee/cost mentioned in proposal text. Remove."
        return None

    def _check_deck_in_scope(self, bid: Dict) -> Optional[str]:
        """Deck supply and installation always in scope."""
        deck_sf = bid.get("deck_sf", 0)
        if bid.get("building_sf", 0) > 5000 and deck_sf == 0:
            # Building is big enough to need deck but none included
            # Check both 'name' and 'desc' keys (different callers use different keys)
            items = [(i.get("name", "") or i.get("desc", "")).lower() for i in bid.get("line_items", [])]
            if not any("deck" in i for i in items):
                return "No deck line item. Deck supply+install is always in scope for buildings >5,000 SF."
        return None

    def _check_no_supplier_names(self, bid: Dict) -> Optional[str]:
        """No supplier names in client-facing documents. Uses YOUR_COMPANY_SUPPLIERS."""
        text_lower = (bid.get("text_content") or "").lower()
        for canonical, variants in YOUR_COMPANY_SUPPLIERS:
            for variant in variants:
                if variant in text_lower:
                    return f'Supplier name "{canonical}" found in proposal text. Remove.'
        for item in bid.get("line_items", []):
            desc = (item.get("name") or item.get("desc") or "").lower()
            for canonical, variants in YOUR_COMPANY_SUPPLIERS:
                for variant in variants:
                    if variant in desc:
                        return f'Supplier name "{canonical}" in line item. Remove from client-facing docs.'
        pname = (bid.get("project_name") or "").lower()
        for canonical, variants in YOUR_COMPANY_SUPPLIERS:
            for variant in variants:
                if variant in pname:
                    return f'Supplier name "{canonical}" in project name. Remove.'
        return None

    def _check_two_pdfs(self, bid: Dict) -> Optional[str]:
        """Two PDFs per bid: client proposal + GP report."""
        # This is checked at the output stage, not content
        return None

    def _check_tonnage_sanity(self, bid: Dict) -> Optional[str]:
        """Tonnage should be reasonable for building size."""
        sf = bid.get("building_sf", 0)
        tons = bid.get("struct_tons", 0) + bid.get("joist_tons", 0)
        if sf > 0 and tons > 0:
            lbs_sf = (tons * 2000) / sf
            if lbs_sf < 2.0:
                return f"Steel intensity {lbs_sf:.1f} lbs/SF is suspiciously low. Typical minimum 3.5 lbs/SF for retail."
            if lbs_sf > 20.0:
                return f"Steel intensity {lbs_sf:.1f} lbs/SF is unusually high. Verify tonnage."
        return None

    def _check_rates(self, bid: Dict) -> Optional[str]:
        """Rates should match current Q2 2026 rates."""
        from bridge.bid_rates import BID_RATES
        for item in bid.get("line_items", []):
            name = (item.get("name") or item.get("desc") or "").lower()
            if "fab" in name and item.get("rate"):
                if abs(item["rate"] - BID_RATES["fab_per_ton"]) > 500:
                    return f'Fab rate ${item["rate"]:,.0f}/ton differs from current ${BID_RATES["fab_per_ton"]:,.0f}/ton. Verify.'
            if "erect" in name and item.get("rate"):
                if abs(item["rate"] - BID_RATES["erection_per_ton"]) > 200:
                    return f'Erection rate ${item["rate"]:,.0f}/ton differs from current ${BID_RATES["erection_per_ton"]:,.0f}/ton. Verify.'
        return None

    def _check_dollar_per_sf(self, bid: Dict) -> Optional[str]:
        """Total bid should be reasonable on a $/SF basis."""
        sf = bid.get("building_sf", 0)
        total = bid.get("total_bid", 0)
        if sf > 0 and total > 0:
            per_sf = total / sf
            btype = bid.get("building_type", "retail_small")
            floors = {
                "retail_small": 15, "retail_big_box": 14,
                "fitness": 18, "warehouse": 12
            }
            floor = floors.get(btype, 14)
            if per_sf < floor:
                return f"${per_sf:.2f}/SF is below the ${floor}/SF floor for {btype}. GC will flag this as low."
        return None

    def _check_freight(self, bid: Dict) -> Optional[str]:
        """Freight should be included for out-of-state jobs."""
        dist = bid.get("distance_mi", 0)
        freight = bid.get("freight", 0)
        if dist > 200 and freight == 0:
            return f"Job is {dist} miles from Houston but no freight line item. Add freight."
        return None

    def _check_overhead(self, bid: Dict) -> Optional[str]:
        """Overhead multiplier should be applied."""
        mult = bid.get("overhead_mult", 0)
        if mult > 0 and mult < 1.05:
            return f"Overhead multiplier {mult}x seems too low. Standard is 1.15x."
        return None

    def _check_gp_margin(self, bid: Dict) -> Optional[str]:
        """GP margin should be at least 10%."""
        gp = bid.get("gp_margin", 0)
        if 0 < gp < 10:
            return f"GP margin {gp:.1f}% is below 10% minimum. Consider adjusting pricing."
        return None

    def _check_no_porsche_plano(self, bid: Dict) -> Optional[str]:
        """[FORBIDDEN PROJECT] is NOT a Your Company project."""
        # Check text_content
        text = (bid.get("text_content") or "").lower()
        if "porsche" in text and "plano" in text:
            return "[FORBIDDEN PROJECT] referenced. This is NOT a Your Company project. Remove immediately."
        # Check project_name
        pname = (bid.get("project_name") or "").lower()
        if "porsche" in pname:
            return "[FORBIDDEN PROJECT] is NOT a Your Company project. Do not list on bids, marketing, or outreach."
        return None

    def _check_no_pemb(self, bid: Dict) -> Optional[str]:
        """No Red Dot Buildings or PEMB-manufacturer language."""
        text = (bid.get("text_content") or "").lower()
        PEMB_TERMS = ["red dot", "pre-engineered metal building", "pemb",
                      "metal building system", "butler", "varco pruden", "nucor building"]
        for term in PEMB_TERMS:
            if term in text:
                return f'PEMB language found: "{term}". Your Company is structural steel, not PEMB.'
        return None

    def _check_exclusions(self, bid: Dict) -> Optional[str]:
        """Standard exclusions should be present."""
        REQUIRED_EXCLUSIONS = ["concrete", "painting", "fireproofing"]
        exclusions = " ".join(bid.get("exclusions", [])).lower()
        text = (bid.get("text_content") or "").lower()
        combined = exclusions + " " + text
        missing = [e for e in REQUIRED_EXCLUSIONS if e not in combined]
        if missing and bid.get("total_bid", 0) > 0:
            return f"Missing standard exclusions: {', '.join(missing)}. Add to proposal."
        return None

    def _check_joist_tonnage(self, bid: Dict) -> Optional[str]:
        """Joist tonnage should be proportional to building SF."""
        sf = bid.get("building_sf", 0)
        joist_tons = bid.get("joist_tons", 0)
        if sf > 10000 and joist_tons > 0:
            joist_lbs_sf = (joist_tons * 2000) / sf
            if joist_lbs_sf < 1.5:
                return (f"Joist intensity {joist_lbs_sf:.1f} lbs/SF is low. "
                        f"Typical 2.0-3.0 lbs/SF for single-story retail. "
                        f"Check: are all joists counted? (Owner caught this on TSC Sumter)")
        return None

    def _check_deck_type(self, bid: Dict) -> Optional[str]:
        """Deck type should match the spec."""
        spec_deck = (bid.get("spec_deck_type") or "").lower()
        bid_deck = (bid.get("deck_type") or "").lower()
        if spec_deck and bid_deck and spec_deck != bid_deck:
            return (f"Deck type mismatch: spec says '{spec_deck}', bid says '{bid_deck}'. "
                    f"(Owner caught this on Planet Fitness: spec was 1-1/2\" 22ga, bid had 3\" composite)")
        return None

    def _check_pemb_scope(self, bid: Dict) -> Optional[str]:
        """Alpine lesson: PEMB areas must be excluded from deck SF and tonnage.
        Training: Alpine R1 included 31,904 SF of PEMB deck = $117K overcount."""
        total_sf = bid.get("total_building_sf", 0)
        scope_sf = bid.get("building_sf", 0)
        if total_sf > 0 and scope_sf > 0 and total_sf > scope_sf * 1.2:
            pemb_sf = total_sf - scope_sf
            text = (bid.get("text_content") or "").lower()
            if "pemb" not in text and "pre-engineered" not in text:
                return (f"Total building is {total_sf:,.0f} SF but scope is {scope_sf:,.0f} SF. "
                        f"The {pemb_sf:,.0f} SF difference may be PEMB manufacturer scope. "
                        f"Verify deck SF excludes PEMB areas. (Alpine R1 error: included PEMB deck = $117K overcount)")
        return None

    def _check_sf_mismatch(self, bid: Dict) -> Optional[str]:
        """Alpine lesson: total building SF != scope SF when PEMB or other exclusions exist."""
        deck_sf = bid.get("deck_sf", 0)
        scope_sf = bid.get("building_sf", 0)
        if deck_sf > 0 and scope_sf > 0 and deck_sf > scope_sf * 1.15:
            return (f"Deck SF ({deck_sf:,.0f}) exceeds building scope SF ({scope_sf:,.0f}) by "
                    f"{((deck_sf/scope_sf)-1)*100:.0f}%. Verify deck area matches Your Company scope boundary.")
        return None

    def _check_mezzanine_sf(self, bid: Dict) -> Optional[str]:
        """Planet Fitness lesson: mezzanine SF must come from mezzanine framing plan.
        Training: PF bid had 7,700 SF, actual was 12,000 SF (36% undercount)."""
        mezz_sf = bid.get("mezzanine_sf", 0)
        mezz_estimated = bid.get("mezzanine_estimated", False)
        if mezz_sf > 0 and mezz_estimated:
            return (f"Mezzanine SF ({mezz_sf:,.0f}) appears estimated, not measured from framing plan. "
                    f"(Planet Fitness error: estimated 7,700 SF, actual was 12,000 SF). "
                    f"Verify from mezzanine framing plan sheet.")
        return None

    def _check_gc_comparison(self, bid: Dict) -> Optional[str]:
        """TSC/PF lesson: when a GC says tonnage is low compared to other bidders, it IS low.
        This rule fires if the bid has been flagged by external comparison."""
        if bid.get("gc_flagged_low"):
            return (f"GC has flagged this bid as low compared to other bidders. "
                    f"This is a strong signal of undertonnage. Review ALL joists, deck SF, and misc steel. "
                    f"(This happened on TSC Sumter and Planet Fitness - both required revisions)")
        return None

    # ── R20-R26: Pilot fixes 2026-05-16 ─────────────────────────────────

    def _check_names_in_text(self, bid: Dict) -> Optional[str]:
        """R20: Staff names must not appear in client-facing proposals."""
        text = (bid.get("text_content") or "")
        INTERNAL_NAMES = ["Ivan", "Mario", "Paul", "Joseph", "Owner"]
        found = [n for n in INTERNAL_NAMES if re.search(rf"\b{re.escape(n)}\b", text, re.I)]
        if found:
            return (f"Internal name(s) in proposal: {', '.join(found)}. "
                    "Remove from client-facing documents.")
        return None

    def _check_no_est_2017(self, bid: Dict) -> Optional[str]:
        """R21: Company founding year is not a client-facing claim."""
        text = (bid.get("text_content") or "").lower()
        for pattern in ["est. 2017", "established 2017", "since 2017", "est 2017"]:
            if pattern in text:
                return f'Company age claim ("{pattern}") in proposal. Remove.'
        return None

    def _check_no_headcount(self, bid: Dict) -> Optional[str]:
        """R22: Headcount disclosure forbidden in proposals."""
        text = (bid.get("text_content") or "")
        PATTERNS = [
            r"\b12[\s-]?person\b",
            r"\btwelve\s+person\b",
            r"\b12\s+employees?\b",
            r"\b12\s+ironworkers?\b",
            r"\btwelve\s+ironworkers?\b",
            r"\bour\s+team\s+of\s+\d+\b",
            r"\b12\b[^.]{0,30}\b(?:team|crew|employees?|ironworkers?)\b",
        ]
        for pat in PATTERNS:
            if re.search(pat, text, re.I):
                return "Headcount disclosure in proposal. Remove team/crew size references."
        return None

    def _check_no_forbidden_payment_terms(self, bid: Dict) -> Optional[str]:
        """R23: Only 30/20/50 payment terms are permitted."""
        text = (bid.get("text_content") or "")
        for pat in [r"40\s*/\s*20\s*/\s*40", r"40-20-40"]:
            if re.search(pat, text, re.I):
                return "Forbidden payment terms 40/20/40 in proposal. Only 30/20/50 is permitted."
        return None

    def _check_no_precedent_projects(self, bid: Dict) -> Optional[str]:
        """R24: Project names belong on capability statements, not bids."""
        text = (bid.get("text_content") or "")
        PROJECTS = ["ICD Church", "Elite Crossing", "Topgolf", "Carvana"]
        found = [p for p in PROJECTS if re.search(re.escape(p), text, re.I)]
        if found:
            return (f"Precedent project(s) in bid: {', '.join(found)}. "
                    "These belong on capability statements, not bid proposals.")
        return None

    def _check_no_em_dash(self, bid: Dict) -> Optional[str]:
        """R25: Em-dash and en-dash are forbidden in proposal text."""
        text = (bid.get("text_content") or "")
        if "—" in text or "–" in text:
            return "Em-dash or en-dash found in proposal. Replace with hyphen or period."
        return None

    def _check_no_three_adj_list(self, bid: Dict) -> Optional[str]:
        """R26: Three-adjective list patterns signal AI-generated text."""
        text = (bid.get("text_content") or "")
        pat = re.compile(r"\b(\w+),\s+(\w+),?\s+and\s+(\w+)\b")
        COMMON_AI_ADJS = {
            "experienced", "certified", "dedicated", "professional", "skilled",
            "qualified", "reliable", "trusted", "proven", "expert", "exceptional",
            "comprehensive", "innovative", "collaborative", "efficient",
            "committed", "responsive", "knowledgeable", "competent", "capable",
            "solid", "compelling", "impressive", "detailed", "thorough", "precise",
        }
        for m in pat.finditer(text):
            triple = {m.group(1).lower(), m.group(2).lower(), m.group(3).lower()}
            if len(triple & COMMON_AI_ADJS) >= 2:
                return (f'Three-adjective list in proposal: "{m.group(0)}". '
                        "Owner rule: two adjectives max.")
        return None

    # R27-R29: Ivan calibration 2026-05-27/28 rules

    def _check_anchor_count(self, bid):
        # R27: anchor rod count must meet Ivan per-column minimums.
        # 4 per simple plate, 8 per moment or braced plate.
        # Source: Ivan L. Martinez, 2026-05-27 calibration reply.
        try:
            from bridge import anchor_rules
        except Exception as e:
            log.warning(f"R27: anchor_rules import failed: {e}")
            return None
        cc = bid.get("column_count", 0)
        ac = bid.get("anchor_count", 0)
        bp = bid.get("base_plate_type", "simple")
        is_braced = bool(bid.get("is_braced_frame", False))
        if not cc:
            return None
        expected = anchor_rules.minimum_anchor_count(
            column_count=cc, base_plate_type=bp, is_braced_frame=is_braced)
        verdict = anchor_rules.check_anchor_count(ac, expected)
        if verdict.get("verdict") == "UNDER_COUNT":
            return ("Anchor count {} is below Ivan minimum {} for {} columns x "
                    "{} rods/{} plate. Rule: {}. Default diameter {} inch UNO.".format(
                ac, expected["count"], cc, expected["per_column"], bp,
                expected["rule_applied"], expected["diameter_inches"]))
        return None

    def _check_connection_allowance(self, bid):
        # R28: connection-material line vs Ivan percent-of-structural-tonnage.
        # Source: Ivan L. Martinez, 2026-05-27 calibration reply.
        try:
            from bridge import connection_allowances
        except Exception as e:
            log.warning(f"R28: connection_allowances import failed: {e}")
            return None
        ss = (bid.get("structural_system") or "").strip().lower()
        if not ss:
            return None
        st = float(bid.get("struct_tons", 0) or 0)
        if st <= 0:
            return None
        conn_t = float(bid.get("connection_tons", 0) or 0)
        try:
            spec = connection_allowances.lookup_allowance(ss)
        except Exception:
            return None
        pct = spec.get("pct_of_structural") if isinstance(spec, dict) else None
        if pct is None:
            return None
        expected_conn = st * (pct / 100.0)
        if conn_t < expected_conn * 0.5:
            return ("Connection allowance ({:.1f} T) appears low for {}. Ivan "
                    "calibration expects ~{}% of structural tonnage ({:.1f} T on "
                    "{:.1f} T structural).".format(conn_t, ss, pct, expected_conn, st))
        return None

    def _check_joist_series(self, bid):
        # R29: joist series tags vs Ivan expected series per building type.
        # Source: Ivan L. Martinez, 2026-05-27 calibration reply.
        try:
            from bridge import joist_series_expectations
        except Exception as e:
            log.warning(f"R29: joist_series_expectations import failed: {e}")
            return None
        bt = bid.get("building_type", "")
        tags = bid.get("joist_tags") or []
        if not bt or not tags:
            return None
        try:
            unexpected = joist_series_expectations.flag_unexpected_joists(bt, tags)
        except Exception as e:
            log.warning(f"R29: flag_unexpected_joists error: {e}")
            return None
        if unexpected:
            tag_str = ", ".join(str(t) for t in unexpected[:5])
            more = "" if len(unexpected) <= 5 else " (+{} more)".format(len(unexpected) - 5)
            return "Joist tags outside expected series for {}: {}{}. Verify against schedule.".format(
                bt, tag_str, more)
        return None

    def _generate_owner_response(self, bid: Dict, blockers: List, warnings: List) -> str:
        """Generate what Owner would actually say."""
        project = bid.get("project_name", "this bid")
        if len(blockers) >= 3:
            return f"Stop. {project} has {len(blockers)} problems. Fix these before I look at it again."
        elif len(blockers) == 1:
            return f"Almost. One thing on {project}: {blockers[0]['detail']}"
        else:
            details = ". ".join(b["detail"].split(".")[0] for b in blockers[:2])
            return f"Two issues on {project}. {details}. Fix and resend."


# Singleton
_vm = None

def get_vm() -> VirtualOwner:
    """Get the Virtual Owner singleton."""
    global _vm
    if _vm is None:
        _vm = VirtualOwner()
    return _vm

def review_bid(bid: Dict) -> Dict:
    """Quick review function. Normalizes common key aliases then runs full 19-rule review.

    Accepts either the full internal key set OR the shorter caller format:
      margin_pct  -> gp_margin (as percentage, e.g. 0.18 -> 18.0)
      name        -> project_name
      tons        -> struct_tons
      gc          -> gc_name
      scope       -> line_items (list of strings converted to [{name:...}])
      bid_total   -> total_bid
    """
    b = dict(bid)

    # Key aliases
    if "project_name" not in b:
        b["project_name"] = b.pop("name", b.get("project_name", ""))
    if "gc_name" not in b:
        b["gc_name"] = b.pop("gc", b.get("gc_name", ""))
    if "struct_tons" not in b:
        b["struct_tons"] = b.pop("tons", b.get("struct_tons", 0))
    if "total_bid" not in b:
        b["total_bid"] = b.pop("bid_total", b.get("total_bid", 0))

    # margin_pct (0-1 float) -> gp_margin (0-100 percentage)
    if "gp_margin" not in b and "margin_pct" in b:
        b["gp_margin"] = b.pop("margin_pct") * 100

    # scope (list of strings) -> line_items (list of dicts)
    if "line_items" not in b and "scope" in b:
        scope = b.pop("scope", [])
        if isinstance(scope, list):
            b["line_items"] = [{"name": s} for s in scope]
        else:
            b["line_items"] = []

    return get_vm().review(b).to_dict()
