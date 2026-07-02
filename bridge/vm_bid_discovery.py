"""
VM Bid Discovery - Front Door of the Bid Process
==================================================
VM becomes the curator at the beginning, not just a reviewer at the end.

Workflow:
  1. Scan inbox for bid invitations (BuildingConnected, iSqFt, ConstructConnect)
  2. Evaluate each against the Owner's preferences (rule-based, then trained)
  3. Present discovery cards on STATUS dashboard
  4. "Start Estimating" creates project folder, extracts links, prompts for files

Rule-based scoring is the baseline. Training data (the Owner's Claude export +
bid list spreadsheet) adds preference weights via load_training_data().

Integrates with:
  - bridge/bid_scanner.py (email scanning + scoring)
  - bridge/bid_pipeline.py (state machine: SCANNED -> WON/LOST/PASSED)
  - bridge/virtual_owner.py (end-of-pipeline review before PDF)
"""

import json
import logging
import os
import re
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("vm_bid_discovery")

# ── Project folder root ──────────────────────────────────────────
# Windows: Documents/Your Company Bids/YYYY-MM/NC-YYYY-XXX-NNN/
# Sandbox: data/bids/YYYY-MM/NC-YYYY-XXX-NNN/
_SANDBOX = os.environ.get("YOURCO_SANDBOX", "")
if _SANDBOX:
    _BID_ROOT = Path(__file__).resolve().parent.parent / "data" / "bids"
else:
    _BID_ROOT = Path.home() / "Documents" / "Your Company Bids"

# ── Bid numbering ────────────────────────────────────────────────
# PRJ-2026-MAY-001, PRJ-2026-MAY-002, etc.
_COUNTER_FILE = Path(__file__).resolve().parent.parent / "data" / "bid_counter.json"


# ── Download link patterns (BuildingConnected, Dropbox, GDrive, etc.) ──
LINK_PATTERNS = [
    # BuildingConnected
    (r'https?://app\.buildingconnected\.com/[^\s<>"\']+', "BuildingConnected"),
    # Dropbox
    (r'https?://(?:www\.)?dropbox\.com/[^\s<>"\']+', "Dropbox"),
    # Google Drive
    (r'https?://drive\.google\.com/[^\s<>"\']+', "Google Drive"),
    # Box
    (r'https?://(?:app|[\w]+)\.box\.com/[^\s<>"\']+', "Box"),
    # ShareFile / Citrix
    (r'https?://[\w]+\.sharefile\.com/[^\s<>"\']+', "ShareFile"),
    # iSqFt / ConstructConnect
    (r'https?://(?:www\.)?isqft\.com/[^\s<>"\']+', "iSqFt"),
    (r'https?://(?:www\.)?constructconnect\.com/[^\s<>"\']+', "ConstructConnect"),
    # Procore
    (r'https?://(?:app\.)?procore\.com/[^\s<>"\']+', "Procore"),
    # PlanHub
    (r'https?://(?:www\.)?planhub\.com/[^\s<>"\']+', "PlanHub"),
    # SmartBid
    (r'https?://[\w]+\.smartbidnet\.com/[^\s<>"\']+', "SmartBidNet"),
    # Generic download/invitation links
    (r'https?://[^\s<>"\']+(?:download|drawings|plans|invitation|bid-package)[^\s<>"\']*', "Direct Link"),
]

# ── the Owner's preference rules (rule-based baseline) ─────────────
# These get augmented when training data is loaded.
PREFERENCE_RULES = {
    # Geography: Houston-area strong preference, Texas acceptable, out-of-state case-by-case
    "geo_houston_bonus": 15,       # Houston metro area
    "geo_texas_bonus": 8,          # Texas but not Houston
    "geo_southeast_bonus": 3,      # SE US (AL, LA, MS, FL, GA, SC)
    "geo_outofstate_penalty": -5,  # Other states

    # Building type preferences
    "type_commercial_bonus": 10,   # Commercial/retail (Tractor Supply, TopGolf)
    "type_industrial_bonus": 12,   # Industrial/refinery/warehouse
    "type_institutional_bonus": 8, # Church, school, medical
    "type_multistory_bonus": 5,    # Multi-story steel frame

    # Tonnage sweet spot: 50-500 tons is Your Company's wheelhouse
    "tonnage_sweet_low": 50,
    "tonnage_sweet_high": 500,
    "tonnage_sweet_bonus": 10,
    "tonnage_too_small_penalty": -8,   # < 20 tons
    "tonnage_too_large_penalty": -3,   # > 1000 tons (can do but stretched)

    # GC relationship (known GCs score higher)
    "known_gc_bonus": 12,

    # Timeline
    "tight_deadline_penalty": -5,  # < 3 days to bid date
    "comfortable_deadline_bonus": 3,  # 7+ days

    # Value range
    "value_floor": 75000,          # Below this, not worth pursuing
    "value_sweet_low": 150000,
    "value_sweet_high": 2000000,
    "value_sweet_bonus": 5,
}

# Known GCs Owner has worked with (from project archive)
KNOWN_GCS = [
    "rycon", "the gonzalez group", "gonzalez group", "w.s. bellows",
    "bellows", "durotech", "spacex", "tellepsen", "harvey builders",
    "cadence mcshane", "mcshane", "rogers-o'brien", "rogers obrien",
    "manhattan construction", "hensel phelps", "brasfield & gorrie",
    "brasfield gorrie", "walbridge", "flintco", "joeris",
    "satterfield & pontikes", "s&p", "jordan foster",
]

# Training data placeholder. load_training_data() populates this.
_trained_preferences: Dict = {}
_training_loaded: bool = False

# Auto-load pre-built training preferences if available
_PREFS_FILE = Path(__file__).resolve().parent / "vm_training_preferences.json"
if _PREFS_FILE.exists():
    try:
        import json as _json_init
        _prefs_data = _json_init.loads(_PREFS_FILE.read_text())
        _trained_preferences = {
            "gc_frequency": {gc: info["count"] if isinstance(info, dict) else info
                            for gc, info in (_prefs_data.get("gc_weights") or {}).items()},
            "state_weights": {st: info["count"] if isinstance(info, dict) else info
                             for st, info in (_prefs_data.get("geographic_weights") or {}).items()},
            "cost_median": (_prefs_data.get("cost_ranges") or {}).get("median", 0),
            "cost_p25": (_prefs_data.get("cost_ranges") or {}).get("p25", 0),
            "cost_p75": (_prefs_data.get("cost_ranges") or {}).get("p75", 0),
            "area_median": (_prefs_data.get("area_ranges") or {}).get("median", 0),
            "correction_count": _prefs_data.get("correction_count", 0),
        }
        # Merge known GCs from training data into the module-level list
        for gc in (_prefs_data.get("known_gcs") or []):
            gc_lower = gc.lower()
            if gc_lower not in KNOWN_GCS:
                KNOWN_GCS.append(gc_lower)
        _training_loaded = True
        log.info("Auto-loaded training preferences: %d GCs, %d states",
                 len(_trained_preferences.get("gc_frequency", {})),
                 len(_trained_preferences.get("state_weights", {})))
    except Exception as _e:
        log.debug("Could not auto-load training preferences: %s", _e)


# ============================================================
# LINK EXTRACTION
# ============================================================

def vm_extract_bid_link(text: str) -> List[Dict]:
    """Extract download/invitation links from email body.

    Returns list of {url, source, context} sorted by relevance.
    BuildingConnected and plan room links rank highest.
    """
    if not text:
        return []

    links = []
    seen = set()
    for pattern, source in LINK_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            url = match.group(0).rstrip(".,;:)>")
            if url in seen:
                continue
            seen.add(url)
            # Grab surrounding context (30 chars each side)
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            links.append({
                "url": url,
                "source": source,
                "context": context,
            })

    # Sort: plan rooms first, then by position in text
    plan_room_sources = {"BuildingConnected", "iSqFt", "ConstructConnect",
                         "Procore", "PlanHub", "SmartBidNet"}
    links.sort(key=lambda l: (0 if l["source"] in plan_room_sources else 1))
    return links


# ============================================================
# BID EVALUATION (rule-based, training-augmented)
# ============================================================

def vm_evaluate_bid(bid_info: Dict) -> Dict:
    """Score a bid against the Owner's preferences. Returns evaluation dict.

    bid_info keys:
        subject, body, sender, gc_company, location, tonnage,
        estimated_value, building_type, deadline, source_score

    Returns:
        score (0-100), tier (HIGH/MEDIUM/LOW/PASS), reasons [], recommendation str
    """
    score = 50  # neutral baseline
    reasons = []
    flags = []

    subject = (bid_info.get("subject") or "").lower()
    body = (bid_info.get("body") or "").lower()
    full = subject + " " + body
    gc = (bid_info.get("gc_company") or bid_info.get("sender") or "").lower()
    location = (bid_info.get("location") or "").lower()
    tonnage_str = str(bid_info.get("tonnage") or "")
    value_str = str(bid_info.get("estimated_value") or "")
    deadline = bid_info.get("deadline") or ""

    # ── Geography ──────────────────────────────────────────────
    houston_terms = ["houston", "katy", "sugar land", "pasadena", "baytown",
                     "spring", "humble", "league city", "pearland", "conroe",
                     "the woodlands", "cypress", "tomball", "webster",
                     "friendswood", "deer park", "la porte", "galveston",
                     "77064", "77040", "77041", "77084"]
    texas_terms = ["texas", " tx", ",tx", "dallas", "san antonio",
                   "austin", "fort worth", "el paso", "new braunfels",
                   "brownsville", "corpus christi", "lubbock", "amarillo",
                   "lake jackson", "beaumont"]
    se_states = ["alabama", " al ", "louisiana", " la ",
                 "mississippi", " ms ", "florida", " fl ",
                 "georgia", " ga ", "south carolina", " sc ",
                 "mobile", "new orleans", "baton rouge"]

    loc_text = location + " " + full
    if any(t in loc_text for t in houston_terms):
        score += PREFERENCE_RULES["geo_houston_bonus"]
        reasons.append("Houston metro area")
    elif any(t in loc_text for t in texas_terms):
        score += PREFERENCE_RULES["geo_texas_bonus"]
        reasons.append("Texas")
    elif any(t in loc_text for t in se_states):
        score += PREFERENCE_RULES["geo_southeast_bonus"]
        reasons.append("Southeast US")
    else:
        score += PREFERENCE_RULES["geo_outofstate_penalty"]
        flags.append("Out-of-state/unknown location")

    # ── Known GC ───────────────────────────────────────────────
    if any(g in gc for g in KNOWN_GCS):
        score += PREFERENCE_RULES["known_gc_bonus"]
        reasons.append("Known GC relationship")

    # ── Building type ──────────────────────────────────────────
    industrial = ["industrial", "refinery", "warehouse", "manufacturing",
                  "distribution", "plant", "facility", "petrochemical"]
    commercial = ["retail", "restaurant", "store", "shopping", "topgolf",
                  "tractor supply", "carvana", "commercial", "office"]
    institutional = ["church", "school", "hospital", "medical", "civic",
                     "university", "college", "library"]

    if any(t in full for t in industrial):
        score += PREFERENCE_RULES["type_industrial_bonus"]
        reasons.append("Industrial scope")
    elif any(t in full for t in commercial):
        score += PREFERENCE_RULES["type_commercial_bonus"]
        reasons.append("Commercial scope")
    elif any(t in full for t in institutional):
        score += PREFERENCE_RULES["type_institutional_bonus"]
        reasons.append("Institutional scope")

    # ── Tonnage ────────────────────────────────────────────────
    tonnage = _parse_number(tonnage_str)
    if tonnage is None:
        # Try to extract from body
        ton_match = re.search(r'(\d[\d,.]*)\s*(?:tons?|tn)', full)
        if ton_match:
            tonnage = _parse_number(ton_match.group(1))

    if tonnage is not None:
        if tonnage < 20:
            score += PREFERENCE_RULES["tonnage_too_small_penalty"]
            flags.append(f"Small tonnage ({tonnage:.0f} tons)")
        elif PREFERENCE_RULES["tonnage_sweet_low"] <= tonnage <= PREFERENCE_RULES["tonnage_sweet_high"]:
            score += PREFERENCE_RULES["tonnage_sweet_bonus"]
            reasons.append(f"Sweet spot tonnage ({tonnage:.0f} tons)")
        elif tonnage > 1000:
            score += PREFERENCE_RULES["tonnage_too_large_penalty"]
            flags.append(f"Large project ({tonnage:.0f} tons)")

    # ── Estimated value ────────────────────────────────────────
    value = _parse_number(value_str)
    if value is not None:
        if value < PREFERENCE_RULES["value_floor"]:
            score -= 25
            flags.append(f"Below value floor (${value:,.0f})")
        elif PREFERENCE_RULES["value_sweet_low"] <= value <= PREFERENCE_RULES["value_sweet_high"]:
            score += PREFERENCE_RULES["value_sweet_bonus"]
            reasons.append(f"Value sweet spot (${value:,.0f})")

    # ── Deadline ───────────────────────────────────────────────
    if deadline:
        try:
            # Try common date formats
            for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y"):
                try:
                    due = datetime.strptime(deadline, fmt).date()
                    days_left = (due - date.today()).days
                    if days_left < 0:
                        score -= 35
                        flags.append("Deadline passed")
                    elif days_left < 3:
                        score += PREFERENCE_RULES["tight_deadline_penalty"]
                        flags.append(f"Tight deadline ({days_left}d)")
                    elif days_left >= 7:
                        score += PREFERENCE_RULES["comfortable_deadline_bonus"]
                        reasons.append(f"Comfortable timeline ({days_left}d)")
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    # ── Incorporate source scanner score ───────────────────────
    source_score = bid_info.get("source_score") or bid_info.get("score")
    if source_score and isinstance(source_score, (int, float)):
        # Blend: 60% VM evaluation + 40% scanner scope score
        score = int(score * 0.6 + source_score * 0.4)

    # ── Apply trained preferences if loaded ────────────────────
    if _training_loaded and _trained_preferences:
        score = _apply_trained_weights(score, bid_info, reasons, flags)

    # ── Clamp and tier ─────────────────────────────────────────
    score = max(0, min(100, score))
    if score >= 70:
        tier = "HIGH"
    elif score >= 40:
        tier = "MEDIUM"
    elif score >= 20:
        tier = "LOW"
    else:
        tier = "PASS"

    # ── Recommendation text ────────────────────────────────────
    if tier == "HIGH":
        rec = "Strong match. Recommend pursuing."
    elif tier == "MEDIUM":
        rec = "Moderate match. Review scope details before committing."
    elif tier == "LOW":
        rec = "Weak match. Pass unless GC relationship justifies."
    else:
        rec = "Does not match Your Company scope or preferences."

    return {
        "score": score,
        "tier": tier,
        "reasons": reasons,
        "flags": flags,
        "recommendation": rec,
        "training_applied": _training_loaded,
    }


# ============================================================
# INBOX SCAN (wraps bid_scanner with VM layer)
# ============================================================

def vm_scan_inbox(days_back: int = 3) -> Dict:
    """Scan the Owner's inbox for bid invitations. Layer VM evaluation
    on top of bid_scanner's scope scoring.

    Returns:
        leads: list of evaluated bid cards
        stats: {total_scanned, qualified, high, medium, low, passed}
    """
    # Get raw leads from bid_scanner
    try:
        from bridge.bid_scanner import scan_outlook
        raw = scan_outlook(days_back=days_back)
    except ImportError:
        log.warning("bid_scanner not available, returning empty")
        raw = {"leads": [], "scanned": 0}
    except Exception as e:
        log.error("Inbox scan failed: %s", e)
        raw = {"leads": [], "scanned": 0, "error": str(e)}

    leads = raw.get("leads") or []
    cards = []
    stats = {"total_scanned": raw.get("scanned", 0),
             "qualified": 0, "high": 0, "medium": 0, "low": 0, "passed": 0}

    for lead in leads:
        # Build bid_info from scanner lead
        bid_info = {
            "subject": lead.get("subject", ""),
            "body": lead.get("body", ""),
            "sender": lead.get("sender", ""),
            "gc_company": lead.get("gc_company", ""),
            "location": lead.get("location", ""),
            "tonnage": lead.get("tonnage", ""),
            "estimated_value": lead.get("estimated_value", ""),
            "building_type": lead.get("building_type", ""),
            "deadline": lead.get("deadline", ""),
            "source_score": lead.get("score", 0),
            "email_id": lead.get("email_id", ""),
            "date": lead.get("date", ""),
        }

        # VM evaluation
        ev = vm_evaluate_bid(bid_info)

        # Extract download links
        links = vm_extract_bid_link(lead.get("body", ""))

        card = {
            "subject": lead.get("subject", "Unknown Project"),
            "gc_company": bid_info["gc_company"],
            "location": bid_info["location"],
            "tonnage": bid_info["tonnage"],
            "estimated_value": bid_info["estimated_value"],
            "deadline": bid_info["deadline"],
            "sender": bid_info["sender"],
            "date": bid_info["date"],
            "email_id": bid_info["email_id"],
            "vm_score": ev["score"],
            "vm_tier": ev["tier"],
            "vm_reasons": ev["reasons"],
            "vm_flags": ev["flags"],
            "vm_recommendation": ev["recommendation"],
            "download_links": links,
            "training_applied": ev["training_applied"],
        }
        cards.append(card)

        # Update stats
        tier_key = ev["tier"].lower()
        if tier_key in stats:
            stats[tier_key] += 1
        if ev["tier"] in ("HIGH", "MEDIUM"):
            stats["qualified"] += 1

    # Sort: HIGH first, then MEDIUM, then by score desc
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "PASS": 3}
    cards.sort(key=lambda c: (tier_order.get(c["vm_tier"], 9), -c["vm_score"]))

    # Register HIGH leads in bid pipeline
    for card in cards:
        if card["vm_tier"] == "HIGH":
            try:
                from bridge.bid_pipeline import add_bid
                add_bid(
                    name=card["subject"],
                    gc_company=card["gc_company"],
                    location=card["location"],
                    tonnage=card["tonnage"],
                    estimated_value=card["estimated_value"],
                    score=card["vm_score"],
                    source="vm_discovery",
                    deadline=card["deadline"],
                )
            except Exception as e:
                log.warning("Failed to register bid in pipeline: %s", e)

    return {"leads": cards, "stats": stats}


# ============================================================
# PROJECT FOLDER CREATION
# ============================================================

def _next_bid_number() -> str:
    """Generate next bid number: NC-YYYY-MON-NNN."""
    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%b").upper()
    prefix = f"NC-{year}-{month}"

    _COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        counters = json.loads(_COUNTER_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        counters = {}

    current = counters.get(prefix, 0) + 1
    counters[prefix] = current
    _COUNTER_FILE.write_text(json.dumps(counters, indent=2))

    return f"{prefix}-{current:03d}"


def vm_create_project_folder(bid_info: Dict) -> Dict:
    """Create project folder for a bid being pursued.

    Structure:
        Your Company Bids/
          2026-05/
            PRJ-2026-MAY-001 - Project Name/
              _project_info.json
              drawings/
              correspondence/

    Returns: {bid_number, folder_path, project_info_path, download_links}
    """
    bid_number = _next_bid_number()
    project_name = _clean_project_name(bid_info.get("subject", "Unknown"))
    month_dir = datetime.now().strftime("%Y-%m")  # vj: local-display-ok
    folder_name = f"{bid_number} - {project_name}"

    folder = _BID_ROOT / month_dir / folder_name
    drawings_dir = folder / "drawings"
    correspondence_dir = folder / "correspondence"

    folder.mkdir(parents=True, exist_ok=True)
    drawings_dir.mkdir(exist_ok=True)
    correspondence_dir.mkdir(exist_ok=True)

    # Save project info
    project_info = {
        "bid_number": bid_number,
        "project_name": project_name,
        "gc_company": bid_info.get("gc_company", ""),
        "gc_contact_email": bid_info.get("sender", ""),
        "location": bid_info.get("location", ""),
        "tonnage": bid_info.get("tonnage", ""),
        "estimated_value": bid_info.get("estimated_value", ""),
        "deadline": bid_info.get("deadline", ""),
        "source": bid_info.get("source", "vm_discovery"),
        "vm_score": bid_info.get("vm_score", 0),
        "vm_tier": bid_info.get("vm_tier", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "PURSUING",
        "notes": "",
    }

    # Extract links from email body
    links = vm_extract_bid_link(bid_info.get("body", ""))
    project_info["download_links"] = links

    info_path = folder / "_project_info.json"
    info_path.write_text(json.dumps(project_info, indent=2))

    # Save email body as correspondence
    if bid_info.get("body"):
        email_path = correspondence_dir / "original_email.txt"
        email_path.write_text(
            f"Subject: {bid_info.get('subject', '')}\n"
            f"From: {bid_info.get('sender', '')}\n"
            f"Date: {bid_info.get('date', '')}\n"
            f"{'=' * 60}\n\n"
            f"{bid_info.get('body', '')}"
        )

    # Advance bid pipeline state if bid_id provided
    bid_id = bid_info.get("bid_id")
    if bid_id:
        try:
            from bridge.bid_pipeline import advance
            advance(bid_id, "PURSUING", actor="VM", notes=f"Folder: {folder_name}")
        except Exception as e:
            log.warning("Failed to advance pipeline: %s", e)

    return {
        "bid_number": bid_number,
        "folder_path": str(folder),
        "project_info_path": str(info_path),
        "drawings_dir": str(drawings_dir),
        "download_links": links,
        "project_info": project_info,
    }


# ============================================================
# DISCOVERY CARDS (for STATUS dashboard)
# ============================================================

def vm_get_discovery_cards(limit: int = 6) -> List[Dict]:
    """Get bid discovery cards for STATUS dashboard display.

    Combines:
    1. Fresh leads from last scan (bid_leads.db via bid_scanner)
    2. Active pipeline bids in SCANNED/REVIEWING state

    Returns list of card dicts ready for frontend rendering.
    """
    cards = []

    # Pull from bid_leads.db (recent scanner results)
    try:
        from bridge.bid_scanner import get_leads
        high_leads = get_leads(tier="HIGH", limit=limit)
        med_leads = get_leads(tier="MEDIUM", limit=max(1, limit - len(high_leads)))
        for lead in (high_leads + med_leads):
            ev = vm_evaluate_bid(lead)
            cards.append({
                "id": lead.get("email_id", ""),
                "source": "scanner",
                "subject": lead.get("subject", "Unknown"),
                "gc_company": lead.get("gc_company", ""),
                "location": lead.get("location", ""),
                "vm_score": ev["score"],
                "vm_tier": ev["tier"],
                "vm_reasons": ev["reasons"][:3],
                "deadline": lead.get("deadline", ""),
                "estimated_value": lead.get("estimated_value", ""),
            })
    except Exception as e:
        log.debug("Could not load scanner leads: %s", e)

    # Pull from bid pipeline (SCANNED/REVIEWING bids)
    try:
        from bridge.bid_pipeline import get_pipeline
        pipeline_bids = get_pipeline(state="SCANNED", limit=limit)
        for bid in (pipeline_bids or []):
            if not any(c["subject"] == bid["name"] for c in cards):
                cards.append({
                    "id": str(bid["id"]),
                    "source": "pipeline",
                    "subject": bid["name"],
                    "gc_company": bid.get("gc_company", ""),
                    "location": bid.get("location", ""),
                    "vm_score": bid.get("score", 0),
                    "vm_tier": _score_to_tier(bid.get("score", 0)),
                    "vm_reasons": [],
                    "deadline": bid.get("deadline", ""),
                    "estimated_value": bid.get("estimated_value", ""),
                })
    except Exception as e:
        log.debug("Could not load pipeline bids: %s", e)

    # Sort and limit
    tier_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "PASS": 3}
    cards.sort(key=lambda c: (tier_order.get(c["vm_tier"], 9), -c["vm_score"]))
    return cards[:limit]


# ============================================================
# TRAINING DATA LOADER (placeholder for the Owner's export)
# ============================================================

def load_training_data(claude_export_path: str = "",
                       bid_list_path: str = "") -> Dict:
    """Load the Owner's preference patterns from training data.

    Sources:
      1. Claude export (~70MB) - decision patterns, bid preferences
      2. Bid list spreadsheet - historical bids with outcomes

    Parses into preference weights that augment PREFERENCE_RULES.

    Returns: {loaded: bool, patterns: int, adjustments: dict}
    """
    global _trained_preferences, _training_loaded

    patterns_found = 0
    adjustments = {}

    # Claude export parsing (when provided)
    if claude_export_path and Path(claude_export_path).exists():
        log.info("Loading Claude export from %s", claude_export_path)
        patterns_found += _parse_claude_export(claude_export_path)

    # Bid list parsing (when provided)
    if bid_list_path and Path(bid_list_path).exists():
        log.info("Loading bid list from %s", bid_list_path)
        patterns_found += _parse_bid_list(bid_list_path)

    if patterns_found > 0:
        _training_loaded = True
        adjustments = dict(_trained_preferences)

    return {
        "loaded": _training_loaded,
        "patterns": patterns_found,
        "adjustments": adjustments,
    }


def _parse_claude_export(path: str) -> int:
    """Parse the Owner's Claude export for bid decision patterns.

    Looks for bid-related conversations with correction language.
    Extracts patterns that indicate where AI gets bids wrong.

    Streaming parser for large files (~116MB conversations.json).
    Returns count of patterns extracted.
    """
    global _trained_preferences
    import zipfile

    patterns = 0
    try:
        z = zipfile.ZipFile(path)
        filenames = z.namelist()

        # Check for conversations.json
        if 'conversations.json' not in filenames:
            log.warning("No conversations.json in export")
            return 0

        with z.open('conversations.json') as f:
            import json as _json
            convos = _json.load(f)

        bid_keywords = ['bid', 'rfq', 'rfp', 'proposal', 'takeoff',
                        'structural steel', 'estimate', 'pricing', 'quote']

        corrections = []
        for conv in convos:
            name = (conv.get('name') or '').lower()
            if not any(kw in name for kw in bid_keywords):
                continue
            for msg in conv.get('chat_messages', []):
                if msg.get('sender') != 'human':
                    continue
                t = (msg.get('text') or '').lower()
                if any(w in t for w in ['wrong', 'error', 'too low', 'too high',
                                        'missing', 'incorrect', 'recheck', 'revision']):
                    corrections.append(t[:300])
                    patterns += 1

        _trained_preferences['correction_count'] = len(corrections)
        _trained_preferences['source_conversations'] = len(convos)
        log.info("Claude export: %d corrections from %d conversations", len(corrections), len(convos))

    except Exception as e:
        log.error("Claude export parse failed: %s", e)

    return patterns


def _parse_bid_list(path: str) -> int:
    """Parse bid list spreadsheet for historical preference patterns.

    Extracts: geographic weights, GC relationships, cost/area distributions,
    building type preferences.

    Returns count of patterns extracted.
    """
    global _trained_preferences
    import re as _re

    patterns = 0
    try:
        # Try openpyxl for xlsx
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb.active

        from collections import Counter
        state_counts = Counter()
        gc_counts = Counter()
        costs = []
        areas = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) < 11:
                continue
            sr, name, addr, area, typ, due, company, email, cost, contact, remark = row[:11]
            addr_s = str(addr) if addr else ''
            st_match = _re.findall(r',\s*([A-Z]{2})\s', addr_s)
            if st_match:
                state_counts[st_match[-1]] += 1
            if company:
                gc_counts[str(company).strip()] += 1
            if cost and isinstance(cost, (int, float)):
                costs.append(cost)
            if area and isinstance(area, (int, float)):
                areas.append(area)
            patterns += 1

        wb.close()

        # Store extracted patterns
        _trained_preferences['state_weights'] = dict(state_counts.most_common())
        _trained_preferences['gc_frequency'] = {gc: cnt for gc, cnt in gc_counts.items() if cnt >= 2}
        if costs:
            sc = sorted(costs)
            _trained_preferences['cost_median'] = sc[len(sc) // 2]
            _trained_preferences['cost_p25'] = sc[int(len(sc) * 0.25)]
            _trained_preferences['cost_p75'] = sc[int(len(sc) * 0.75)]
        if areas:
            sa = sorted(areas)
            _trained_preferences['area_median'] = sa[len(sa) // 2]

        log.info("Bid list: %d bids, %d states, %d GCs with 2+ bids",
                 patterns, len(state_counts), len(_trained_preferences.get('gc_frequency', {})))

    except ImportError:
        log.warning("openpyxl not installed, trying CSV fallback")
        try:
            import csv
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    patterns += 1
        except Exception as e2:
            log.error("CSV fallback failed: %s", e2)
    except Exception as e:
        log.error("Bid list parse failed: %s", e)

    return patterns


def _apply_trained_weights(base_score: int, bid_info: Dict,
                           reasons: list, flags: list) -> int:
    """Apply trained preference weights to base score.
    Called only when _training_loaded is True.
    """
    score = base_score

    # GC frequency boost: GCs Owner has bid with multiple times
    gc = (bid_info.get("gc_company") or bid_info.get("sender") or "").strip()
    gc_freq = _trained_preferences.get('gc_frequency', {})
    if gc and gc_freq:
        for known_gc, count in gc_freq.items():
            if known_gc.lower() in gc.lower() or gc.lower() in known_gc.lower():
                boost = min(12, count * 2)
                score += boost
                reasons.append(f"Repeat GC ({count} prior bids)")
                break

    # State frequency boost: states Owner bids in frequently
    location = (bid_info.get("location") or "").upper()
    state_weights = _trained_preferences.get('state_weights', {})
    if state_weights:
        import re as _re
        state_match = _re.findall(r'\b([A-Z]{2})\b', location)
        for st in state_match:
            if st in state_weights:
                freq = state_weights[st]
                if freq >= 50:
                    score += 8
                    reasons.append(f"High-frequency state ({st}: {freq} prior bids)")
                elif freq >= 10:
                    score += 4
                    reasons.append(f"Active state ({st}: {freq} prior bids)")
                break

    return max(0, min(100, score))


# ============================================================
# HELPERS
# ============================================================

def _parse_number(s: str) -> Optional[float]:
    """Parse numeric value from string, handling $, commas, K/M suffixes."""
    if not s:
        return None
    s = str(s).strip().replace("$", "").replace(",", "").replace(" ", "")
    m = re.match(r'^([\d.]+)\s*([kKmM])?', s)
    if not m:
        return None
    try:
        val = float(m.group(1))
        suffix = (m.group(2) or "").upper()
        if suffix == "K":
            val *= 1000
        elif suffix == "M":
            val *= 1000000
        return val
    except ValueError:
        return None


def _clean_project_name(subject: str) -> str:
    """Clean email subject into a folder-safe project name."""
    cleaned = subject.strip()
    # Strip chained prefixes (RE: FW: RFQ - etc.)
    prefix_re = re.compile(
        r'^(?:RE:|FW:|FWD:|ITB|RFQ|RFP|bid invitation|invitation to bid)[:\s-]*',
        re.IGNORECASE
    )
    for _ in range(5):  # max 5 prefix layers
        m = prefix_re.match(cleaned)
        if not m:
            break
        cleaned = cleaned[m.end():].strip()
    # Remove characters not safe for folder names
    cleaned = re.sub(r'[<>:"/\\|?*]', '', cleaned)
    # Truncate to 60 chars
    if len(cleaned) > 60:
        cleaned = cleaned[:57] + "..."
    return cleaned or "Unknown Project"


def _score_to_tier(score: int) -> str:
    if score >= 70:
        return "HIGH"
    elif score >= 40:
        return "MEDIUM"
    elif score >= 20:
        return "LOW"
    return "PASS"
