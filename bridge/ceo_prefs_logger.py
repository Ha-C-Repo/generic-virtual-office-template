"""
Your Company Virtual Office - CEO Preferences Auto-Logger (v3.2)
==============================================================

After each ai_ask() response, this module extracts any revealed preferences
about the Owner's working style, priorities, communication patterns, and
decisions - then persists them to a local JSON file.

This solves the "cold start" problem: without this, every chat session
starts fresh and Owner has to re-explain context that should be remembered.

Extracted preference categories:
  - rate_changes:    "changed fab rate to $3,850"
  - project_decisions: "pursuing ICD Church, passing on Baytown"
  - communication:   "prefers short answers", "don't say 'great question'"
  - priorities:      "focus on Marathon work this month"
  - contacts:        "Ivan handles field, Amber handles compliance"
  - scheduling:      "briefing at 6:30 AM not 7"
  - templates:       "use refinery template for Marathon bids"

On boot, the AI reads these preferences to personalize every response
from the first message - no warm-up period needed.

Sync: If OneDrive is available, preferences are also written to
  Your_Company_Team/memory/ceo_prefs_owner.json
for cross-device continuity (Linux reads the same file).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ── Storage ──────────────────────────────────────────────────────────

def _prefs_path() -> Path:
    """Return path to local preferences file."""
    p = Path(__file__).parent.parent / "data" / "ceo_preferences.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_prefs() -> dict:
    """Load current preferences from disk."""
    p = _prefs_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return _default_prefs()
    return _default_prefs()


def _save_prefs(prefs: dict):
    """Save preferences to disk + OneDrive if available."""
    prefs["updated_at"] = datetime.now(timezone.utc).isoformat()
    _prefs_path().write_text(json.dumps(prefs, indent=2), encoding="utf-8")

    # Sync to OneDrive if available
    try:
        from bridge.integrations import detect_onedrive
        od = detect_onedrive()
        if od["found"]:
            od_path = Path(od["path"]) / "memory"
            od_path.mkdir(parents=True, exist_ok=True)
            (od_path / "ceo_prefs_owner.json").write_text(
                json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception:
        pass  # OneDrive sync is best-effort


def _default_prefs() -> dict:
    return {
        "rate_changes": [],
        "project_decisions": [],
        "communication_style": [],
        "priorities": [],
        "contacts_roles": [],
        "scheduling": [],
        "templates": [],
        "general": [],
        "extraction_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Extraction patterns ─────────────────────────────────────────────

# Each pattern: (regex, category, extraction_function)
EXTRACTION_PATTERNS = [
    # Rate changes
    (r"(?:change|update|set|lock)\s+(?:the\s+)?(?:fab|fabrication)\s+(?:rate\s+)?(?:to\s+)?\$?([\d,]+)",
     "rate_changes", lambda m: f"Fabrication rate changed to ${m.group(1)}"),

    (r"(?:change|update|set|lock)\s+(?:the\s+)?(?:erect|erection)\s+(?:rate\s+)?(?:to\s+)?\$?([\d,]+)",
     "rate_changes", lambda m: f"Erection rate changed to ${m.group(1)}"),

    # Project decisions
    (r"(?:pursue|pursuing|go after|bid on|let'?s bid)\s+(?:the\s+)?(.+?)(?:\.|$|,)",
     "project_decisions", lambda m: f"Pursuing: {m.group(1).strip()[:60]}"),

    (r"(?:pass on|skip|don'?t bid|no-bid|decline)\s+(?:the\s+)?(.+?)(?:\.|$|,)",
     "project_decisions", lambda m: f"Passing on: {m.group(1).strip()[:60]}"),

    # Communication preferences
    (r"(?:don'?t|stop|quit|never)\s+(?:say|use|write)\s+['\"]?(.+?)['\"]?(?:\.|$)",
     "communication_style", lambda m: f"Don't say: '{m.group(1).strip()[:40]}'"),

    (r"(?:always|prefer|want you to)\s+(?:use|say|write|respond)\s+(.+?)(?:\.|$)",
     "communication_style", lambda m: f"Prefer: {m.group(1).strip()[:60]}"),

    # Scheduling
    (r"(?:briefing|brief|morning)\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))",
     "scheduling", lambda m: f"Morning briefing at {m.group(1)}"),

    # Template preferences
    (r"(?:use|switch to|set)\s+(?:the\s+)?(\w+)\s+template",
     "templates", lambda m: f"Preferred template: {m.group(1).upper()}"),

    # Contact/role assignments
    (r"(\w+)\s+(?:handles?|is responsible for|takes care of|manages?)\s+(.+?)(?:\.|$|,)",
     "contacts_roles", lambda m: f"{m.group(1)}: handles {m.group(2).strip()[:40]}"),

    # Priorities
    (r"(?:focus on|priority is|most important|concentrate on)\s+(.+?)(?:\.|$|,)",
     "priorities", lambda m: f"Focus: {m.group(1).strip()[:60]}"),
]


def extract_preferences(user_message: str, ai_response: str = "") -> list:
    """Extract CEO preferences from a user message + AI response.

    Returns list of extracted preference dicts:
      [{category, text, source, extracted_at}]
    """
    extracted = []
    text_to_scan = user_message  # Only scan user messages for preferences

    for pattern, category, formatter in EXTRACTION_PATTERNS:
        matches = re.finditer(pattern, text_to_scan, re.IGNORECASE)
        for match in matches:
            try:
                pref_text = formatter(match)
                if pref_text and len(pref_text) > 5:  # Skip trivially short extractions
                    extracted.append({
                        "category": category,
                        "text": pref_text,
                        "source": user_message[:100],
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception:
                continue

    return extracted


def log_preferences(user_message: str, ai_response: str = "") -> dict:
    """Extract and persist any CEO preferences found in this exchange.

    Call this after every ai_ask() for mode='owner'.
    Returns summary of what was extracted (empty if nothing found).
    """
    extracted = extract_preferences(user_message, ai_response)
    if not extracted:
        return {"extracted": 0}

    prefs = _load_prefs()

    new_count = 0
    for pref in extracted:
        cat = pref["category"]
        if cat not in prefs:
            prefs[cat] = []

        # Deduplicate: don't add if we already have this exact preference
        existing_texts = [p["text"] for p in prefs[cat] if isinstance(p, dict)]
        if pref["text"] not in existing_texts:
            prefs[cat].append(pref)
            # Keep each category to last 20 entries
            prefs[cat] = prefs[cat][-20:]
            new_count += 1

    if new_count > 0:
        prefs["extraction_count"] = prefs.get("extraction_count", 0) + new_count
        _save_prefs(prefs)

    return {
        "extracted": len(extracted),
        "new": new_count,
        "categories": list(set(p["category"] for p in extracted)),
    }


# ── Preference retrieval for system prompt ───────────────────────────

def get_preferences_summary() -> str:
    """Build a concise preference summary for system prompt injection.

    Returns a formatted string (max ~1500 chars) of active preferences.
    Called at boot to personalize the AI from the first message.
    """
    prefs = _load_prefs()
    lines = []

    for category in ["communication_style", "priorities", "scheduling",
                     "templates", "contacts_roles", "rate_changes", "project_decisions"]:
        items = prefs.get(category, [])
        if not items:
            continue
        # Get the most recent 3 per category
        recent = items[-3:] if isinstance(items[0], dict) else items[-3:]
        cat_label = category.replace("_", " ").title()
        for item in recent:
            text = item["text"] if isinstance(item, dict) else str(item)
            lines.append(f"  {cat_label}: {text}")

    if not lines:
        return ""

    header = "CEO LEARNED PREFERENCES (auto-extracted from conversations):"
    return header + "\n" + "\n".join(lines[:15])  # Max 15 lines


def get_all_preferences() -> dict:
    """Return full preferences data for the Settings panel or diagnostic."""
    return _load_prefs()


def clear_preferences() -> dict:
    """Reset all learned preferences. Used by factory_reset."""
    prefs = _default_prefs()
    _save_prefs(prefs)
    return {"cleared": True, "message": "All CEO preferences cleared."}
