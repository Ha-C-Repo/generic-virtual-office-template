"""LinkedIn content generator for Owner and Joseph.

Four rotating post formats per linkedin-content.md template.
Voice rules per brand-voice.md. Anti-AI fingerprint check runs
automatically before returning any draft.

All posts are DRAFT ONLY. Never publish directly.
"""

import re
from datetime import datetime

# ── Post format templates ────────────────────────────────────────────

FORMATS = {
    "A": {
        "name": "Counterintuitive Claim",
        "structure": (
            "Hook: 'Most [industry] companies think [X]. We found the opposite.'\n"
            "Body: 3-4 sentences with real Your Company numbers.\n"
            "Close: Question inviting engagement."
        ),
    },
    "B": {
        "name": "Specific Project Story",
        "structure": (
            "Hook: one-line hook about a specific project challenge.\n"
            "Body: problem > what we did > outcome. MUST include real numbers.\n"
            "Close: what this teaches the reader."
        ),
    },
    "C": {
        "name": "AI/Process Update",
        "structure": (
            "Hook: 'We just [built/automated/shipped] X. Here is what it does.'\n"
            "Body: before/after comparison with concrete examples.\n"
            "Close: invite others to ask how."
        ),
    },
    "D": {
        "name": "Industry Observation",
        "structure": (
            "Hook: Specific observation about Texas steel or construction market.\n"
            "Body: what Owner sees on the ground that news does not cover.\n"
            "Close: question or prediction."
        ),
    },
}

# ── Real numbers approved for LinkedIn (from linkedin-content.md) ────

APPROVED_NUMBERS = {
    "icd_church": "ICD Church: 1,500+ tons, circular frame, Spring TX",
    "elite_crossing": "Elite Crossing: SJI 30KCS4 joists, 50 ft spans, Lake Jackson TX",
    "efficiency": "405 manual hrs to 133 machine hrs (67% reduction)",
    "aisc_db": "2,299 AISC shapes validated against v16.0 database",
    "crew_size": "12-person crew, Houston-based",
    "certifications": "ISN [ISN ID]. AISC 207-25 certified.",
}

# ── Anti-AI fingerprint patterns (from brand-voice.md) ──────────────

_AI_FINGERPRINTS = [
    (re.compile(r"\u2014"), "Em-dash found. Replace with period or hyphen."),
    (re.compile(r"[Ii]t'?s not just .+, it'?s"),
     "'It's not just X, it's Y' construction. Rewrite as direct statement."),
    (re.compile(r"[Ii]n the \w+ world of"),
     "'In the [adj] world of' opening. Delete, start with the point."),
    (re.compile(r"\w+, \w+, and \w+ly"),
     "Possible three-adjective list. Cut to the best one."),
    (re.compile(r"[Mm]oreover|[Ff]urthermore|[Ii]n essence|[Ll]et'?s dive"),
     "AI transition word. Cut it."),
    (re.compile(r"[Tt]hat'?s where .+ comes? in"),
     "'That's where X comes in' construction. Rewrite."),
    (re.compile(r"[Gg]reat news|[Ww]e'?re thrilled|[Ee]xcited to announce"),
     "Corporate filler. Delete."),
    (re.compile(r"[Hh]ope this finds you"),
     "'Hope this finds you well.' Kill on sight."),
    (re.compile(
        r"[Ll]everage|[Ss]ynergy|[Ee]mpower|[Gg]ame.changing|[Uu]nlock value"),
     "Banned vocabulary."),
    (re.compile(r"[Aa]t scale|[Dd]eep dive|[Ee]cosystem|[Jj]ourney"),
     "Banned vocabulary."),
    (re.compile(r"[Bb]est regards|[Ww]arm regards"),
     "Formal closing. Owner doesn't use these."),
]


def fingerprint_check(text: str) -> list[dict]:
    """Run anti-AI fingerprint scan on draft text.

    Returns list of {pattern, line, suggestion} for each hit.
    Empty list means clean.
    """
    hits = []
    for pat, suggestion in _AI_FINGERPRINTS:
        match = pat.search(text)
        if match:
            pos = match.start()
            line_num = text[:pos].count("\n") + 1
            hits.append({
                "pattern": match.group(),
                "line": line_num,
                "suggestion": suggestion,
            })
    return hits


def draft_linkedin_post(
    topic: str = "",
    format_code: str = "",
    voice: str = "owner",
    project_ref: str = "",
    numbers: str = "",
    hashtags: list | None = None,
    max_words: int = 250,
) -> dict:
    """Generate a LinkedIn post draft.

    Args:
        topic: What the post is about (required).
        format_code: A/B/C/D or empty for auto-rotate by day of week.
        voice: 'owner' or 'joseph'.
        project_ref: Project name to reference (ICD, Elite, etc.)
        numbers: Specific numbers/stats to include.
        hashtags: Override default hashtags. Max 3.
        max_words: Target word count (150-250 recommended).

    Returns dict with draft, format info, fingerprint results, status.
    """
    if not topic:
        return {"error": "topic is required. What should the post be about?"}

    # Auto-rotate format if not specified
    if not format_code:
        # Day-of-week selection is intentional local-time semantics - a
        # Monday post should rotate based on Houston Monday, not UTC.
        dow = datetime.now().weekday()  # vj: local-time-ok
        format_code = ["A", "B", "C", "D", "A", "B", "C"][dow]
    format_code = format_code.upper()
    if format_code not in FORMATS:
        return {"error": f"format_code must be A/B/C/D. Got: {format_code}"}

    fmt = FORMATS[format_code]
    draft_lines = _build_draft(format_code, topic, voice, project_ref, numbers)

    # Add hashtags (max 3, per template rules)
    tags = hashtags or ["#structuralsteel", "#texasbusiness"]
    tags = tags[:3]
    draft_lines.append("")
    draft_lines.append(" ".join(tags))

    draft = "\n".join(draft_lines)

    # Trim to max_words
    words = draft.split()
    if len(words) > max_words:
        draft = " ".join(words[:max_words]) + "..."

    # Fingerprint check
    fp_hits = fingerprint_check(draft)

    # Track which approved numbers were used
    used = []
    for key, desc in APPROVED_NUMBERS.items():
        for chunk in desc.split(","):
            chunk = chunk.strip()
            if len(chunk) > 6 and chunk.lower() in draft.lower():
                used.append(key)
                break

    return {
        "draft": draft,
        "format": f"{format_code} - {fmt['name']}",
        "format_structure": fmt["structure"],
        "voice": voice,
        "word_count": len(draft.split()),
        "fingerprint_hits": fp_hits,
        "fingerprint_clean": len(fp_hits) == 0,
        "approved_numbers_used": used,
        "status": "draft",
        "note": "Route to Owner for approval before publishing.",
    }


def _build_draft(
    format_code: str, topic: str, voice: str,
    project_ref: str, numbers: str,
) -> list[str]:
    """Build draft lines. Constructs real sentences from topic + approved numbers.
    Brackets are last-resort fallbacks only.
    """
    lines: list[str] = []
    topic_clean = topic.strip().rstrip(".")

    # ── Topic keyword extraction ───────────────────────────────────
    t_lower = topic_clean.lower()
    is_ai     = any(w in t_lower for w in ["ai","built","automated","tool","claude","system","database","validator"])
    is_safety = any(w in t_lower for w in ["safety","osha","trir","isnetworld","compliance","emr","incident"])
    is_market = any(w in t_lower for w in ["price","market","houston","texas","demand","supply","cost","tariff"])
    is_speed  = any(w in t_lower for w in ["fast","speed","turnaround","quick","deadline","schedule","delivery"])
    is_quality= any(w in t_lower for w in ["quality","weld","aws","cert","aisc","d1.1","inspection","qc"])

    # ── Pull best available number context ─────────────────────────
    eff  = APPROVED_NUMBERS["efficiency"]      # 405 hrs -> 133 hrs
    icd  = APPROVED_NUMBERS["icd_church"]      # 1,500+ tons
    ec   = APPROVED_NUMBERS["elite_crossing"]  # SJI joists
    db   = APPROVED_NUMBERS["aisc_db"]         # 2,299 shapes
    cert = APPROVED_NUMBERS["certifications"]  # ISN + AISC
    crew = APPROVED_NUMBERS["crew_size"]       # 12-person

    # Resolve project ref or infer from topic
    proj_fact = None
    if project_ref:
        proj_fact = _resolve_ref(project_ref)
    elif "icd" in t_lower or "church" in t_lower:
        proj_fact = icd
    elif "elite" in t_lower or "crossing" in t_lower:
        proj_fact = ec

    caller_numbers = numbers.strip().rstrip(".") if numbers else None

    # ── FORMAT A: Counterintuitive Claim ──────────────────────────
    if format_code == "A":
        for strip in ("most fab shops think ", "most fabricators think ",
                      "most people think ", "everyone thinks ", "most think "):
            if t_lower.startswith(strip):
                topic_clean = topic_clean[len(strip):].strip().capitalize()
                t_lower = topic_clean.lower()
                break
        short = topic_clean.split(",")[0].split(".")[0].strip()
        lines.append(f"Most structural steel shops think: {short}.")
        lines.append("We found the opposite.")
        lines.append("")

        # Body: pick the most relevant number fact
        if caller_numbers:
            lines.append(caller_numbers + ".")
        elif is_ai:
            lines.append(f"{eff}.")
            lines.append(f"{db}.")
        elif proj_fact:
            lines.append(f"{proj_fact}.")
        elif is_speed:
            lines.append(f"{eff}.")
            lines.append("Turnaround windows do not move. Fab speed does.")
        elif is_quality:
            lines.append(f"{cert}.")
            lines.append("Every weld certified. Every connection calc-stamped.")
        else:
            lines.append(f"{crew}. {cert}.")
            lines.append("Nine years in Houston structural steel.")
        lines.append("")
        lines.append("What has your experience been?")

    # ── FORMAT B: Specific Project Story ──────────────────────────
    elif format_code == "B":
        # Hook from project or topic
        if proj_fact:
            # Split on " - " first; fall back to splitting before the FIRST
            # alphabetic comma (skip commas inside numbers like "1,500+")
            import re as _re
            if " - " in proj_fact:
                hook = proj_fact.split(" - ")[0]
            else:
                # Find first comma that is followed by a space and a letter
                m = _re.search(r",\s+(?=[A-Za-z])", proj_fact)
                hook = proj_fact[:m.start()] if m else proj_fact
            lines.append(f"{hook}.")
        else:
            lines.append(f"{topic_clean}.")
        lines.append("")

        # Problem: infer from topic keywords
        if is_speed:
            problem = "The schedule was impossible. GC needed steel on-site in three weeks."
        elif is_quality:
            problem = "The connection detail was non-standard. No template in the library."
        elif is_ai or is_ai:
            problem = "Takeoff was manual. Two days per set. One estimator, one set of drawings."
        elif proj_fact and "circular" in str(proj_fact).lower():
            problem = "No straight walls. Every member a different length. Standard software would not handle it."
        elif proj_fact and "joist" in str(proj_fact).lower():
            problem = "50-foot clear spans. Joist sizing had to match the deck spec exactly."
        else:
            problem = "The drawings changed twice in 10 days. Scope was still moving when we bid."
        lines.append(f"The problem: {problem}")
        lines.append("")

        # Action
        if is_ai:
            lines.append(f"What we did: {eff}. Same output. One third of the time.")
        elif is_speed:
            lines.append("What we did: Locked the critical path to shop hours, not calendar days. Crew ran two shifts.")
        elif proj_fact:
            lines.append(f"What we did: Pulled every member from AISC v16.0. {db}. Zero hallucinated shapes.")
        else:
            lines.append("What we did: Locked scope before drawings were final. Change order ready before the GC asked.")
        lines.append("")

        # Result
        if caller_numbers:
            lines.append(f"Result: {caller_numbers}.")
        elif proj_fact:
            lines.append(f"Result: {proj_fact}. No punchlist items at final inspection.")
        elif is_ai:
            lines.append(f"Result: {eff}. Estimator freed for three more bids that week.")
        else:
            lines.append("Result: Delivered on the original schedule. No change orders from our side.")
        lines.append("")

        # Takeaway
        if is_ai:
            lines.append("The takeaway: Speed is a process problem. Not a headcount problem.")
        elif is_speed:
            lines.append("The takeaway: A tight schedule is a bid advantage if your shop can hold it.")
        elif is_quality:
            lines.append("The takeaway: Non-standard details are where the margin lives. Most shops pass. We do not.")
        else:
            lines.append("The takeaway: The GC remembers who did not create problems.")

    # ── FORMAT C: AI/Process Update ───────────────────────────────
    elif format_code == "C":
        lines.append(f"We just {topic_clean}.")
        lines.append("Here is what changed.")
        lines.append("")

        if caller_numbers:
            before_after = caller_numbers
        elif is_ai or "database" in t_lower or "automat" in t_lower:
            before_after = eff
        else:
            before_after = eff

        # Parse before/after from the efficiency number if it matches pattern
        if "to" in before_after and "hrs" in before_after:
            parts = before_after.split(" to ")
            lines.append(f"Before: {parts[0].strip()}.")
            lines.append(f"After: {parts[1].strip()}.")
        else:
            lines.append(f"Before: Manual process. Slower. More room for error.")
            lines.append(f"After: {before_after}.")

        lines.append("")
        if voice == "owner":
            lines.append("Built it in-house. Ask me how.")
        else:
            lines.append("Happy to walk through the setup if anyone is curious.")

    # ── FORMAT D: Industry Observation ────────────────────────────
    elif format_code == "D":
        lines.append(f"{topic_clean}.")
        lines.append("")

        # Body: what Owner sees that news misses
        if is_market:
            lines.append("What I see on the ground in Houston:")
            lines.append("GCs are padding contingencies. Not because scope changed.")
            lines.append("Because material costs are moving again.")
            lines.append(f"{crew}. We started seeing this six weeks ago.")
        elif is_safety:
            lines.append("What I see on the ground in Houston:")
            lines.append("ISNetworld approvals are taking longer.")
            lines.append("Refineries are tightening requirements, not loosening them.")
            lines.append(f"{cert}. That is not an accident.")
        elif is_speed:
            lines.append("What I see on the ground in Houston:")
            lines.append("Every GC is running lean. No float in the schedule.")
            lines.append("Fast-track is the new baseline, not a premium service.")
            lines.append(f"{eff}. That gap matters now.")
        else:
            lines.append("What I see on the ground in Houston:")
            lines.append("Structural steel demand is not slowing.")
            lines.append("The shops that are slow are the ones that did not invest in process.")
            lines.append(f"{crew}. Nine years. Still here.")

        lines.append("")
        if is_market:
            lines.append("Where do you think lead times go in Q3?")
        elif is_safety:
            lines.append("How are other subs handling the compliance load?")
        else:
            lines.append("What are you seeing on your projects right now?")

    return lines


def _resolve_ref(ref: str) -> str:
    """Map a project reference to approved numbers."""
    r = ref.lower()
    if "icd" in r or "church" in r:
        return APPROVED_NUMBERS["icd_church"]
    if "elite" in r or "crossing" in r:
        return APPROVED_NUMBERS["elite_crossing"]
    if "efficien" in r or "hour" in r:
        return APPROVED_NUMBERS["efficiency"]
    if "aisc" in r or "shape" in r:
        return APPROVED_NUMBERS["aisc_db"]
    return ref


def list_formats() -> list[dict]:
    """Return all four formats for display."""
    return [
        {"code": k, "name": v["name"], "structure": v["structure"]}
        for k, v in FORMATS.items()
    ]


def get_approved_numbers() -> dict:
    """Return all approved real numbers for LinkedIn posts."""
    return dict(APPROVED_NUMBERS)


# Alias for backward compatibility with Bridge.get_portfolio_facts()
def get_portfolio_facts() -> dict:
    """Return approved portfolio facts for LinkedIn posts.

    Alias for get_approved_numbers(). Called by Bridge.get_portfolio_facts().
    """
    return get_approved_numbers()
