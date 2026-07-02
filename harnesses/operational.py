"""
Operational harnesses - self-test v3.5.2.
=========================================
Three harnesses the self-test runs in-process:

- BidPipelineHarness: a CONTRACT test. Verifies the bid pipeline's public
  surface exists and honors the _ok/_err and shape contracts, without running
  the network/LLM-dependent chain. Catches API drift on the path that builds a
  proposal (find_render -> generate_proposal, the Tekla viewport gate, locked
  rates). Deterministic, offline.

- ComplianceAttackLibrary: a RED-TEAM test. Feeds known forbidden phrases
  (supplier names, PEMB brands, [FORBIDDEN PROJECT], internal/PE names, headcount)
  through bridge.governance.check_compliance and asserts every one is flagged
  (no misses), and feeds clean phrases and asserts none are flagged (no false
  positives). This is the Tier-1 leak-scan guard that keeps suppliers and
  internal names off client documents.

- VoiceCalibrationHarness: a VOICE gate. Checks text against the Owner's 10
  voice rules from brand-voice.md (em-dash, AI opener, "not just X, it's Y",
  triple-adjective, buzzwords, marketing cliche, padding, placeholder tokens,
  tilde quantities, &amp; entities). Hard violations block, soft violations
  warn. Consumed by api.check_voice, bid_scorecard, documents voice_qc, and
  the diagnostics harness suite.

No new dependency. Pure standard library + existing bridge modules.
"""

import re


class BidPipelineHarness:
    """Offline contract test for the proposal-building pipeline."""

    @staticmethod
    def run() -> dict:
        checks = []

        def _check(name, fn):
            try:
                fn()
                checks.append({"name": name, "ok": True})
            except Exception as e:  # noqa: BLE001
                checks.append({"name": name, "ok": False, "error": str(e)[:140]})

        # 1. Locked rates present and well-formed (CEO-locked Q2 2026).
        def _rates():
            from bridge.bid_rates import BID_RATES
            for k in ("fab_per_ton", "erection_per_ton", "joists_per_ton",
                      "roof_deck_per_sf", "ga_overhead_pct"):
                assert k in BID_RATES, f"missing rate {k}"
                assert isinstance(BID_RATES[k], (int, float)), f"rate {k} not numeric"
        _check("locked rates present", _rates)

        # 2. find_render returns a str (path or "") and never raises.
        def _find_render():
            from bridge.bid_documents import find_render
            r = find_render(project_name="__contract_no_such_project__")
            assert isinstance(r, str), "find_render must return str"
        _check("find_render contract", _find_render)

        # 3. Tekla viewport gate returns the ok/required contract dict.
        def _tekla_gate():
            from bridge.tekla_viewport import require_tekla_viewport
            r = require_tekla_viewport(project_name="__contract_no_such_project__")
            assert isinstance(r, dict) and "ok" in r, "tekla gate must return dict with ok"
            assert r["ok"] in (True, False)
        _check("tekla viewport gate contract", _tekla_gate)

        # 4. Proposal generator is callable and accepts the render_path kwarg.
        def _proposal_sig():
            import inspect
            from bridge.documents import generate_proposal
            assert callable(generate_proposal)
            params = inspect.signature(generate_proposal).parameters
            assert "render_path" in params, "generate_proposal must accept render_path"
        _check("generate_proposal accepts render_path", _proposal_sig)

        # 5. Bid chain entry point is callable.
        def _compose():
            from bridge.agents.bid_chain import compose_bid
            assert callable(compose_bid)
        _check("compose_bid callable", _compose)

        passed = sum(1 for c in checks if c["ok"])
        total = len(checks)
        return {
            "verdict": "PASS" if passed == total else "FAIL",
            "passed": passed,
            "total": total,
            "checks": checks,
        }


class ComplianceAttackLibrary:
    """Red-team phrases that MUST be flagged, plus clean phrases that must not."""

    # Each attack phrase contains a Tier-1 violation check_compliance must catch.
    ATTACKS = [
        "Roof deck supplied by Vulcraft.",
        "Wide-flange steel from Nucor for this package.",
        "Steel joists by Canam.",
        "Anchor assemblies via Ayamsa.",
        "Detailing performed by Ivan Martinez.",
        "Erected by our 12-person crew.",
        "Comparable to our [FORBIDDEN PROJECT] project.",
        "Furnished as a Red Dot Buildings metal building system.",
        "Calculations sealed by John Smith, P.E.",
        "Plate from Triple-S Steel.",
    ]

    # Clean phrases that must produce ZERO violations in a bid context.
    CLEAN = [
        "Structural steel fabrication and erection per AISC 360-16.",
        "Roof deck supply and installation included in scope.",
        "Materials from qualified suppliers per ASTM/SDI specifications.",
        "Anchor rods furnished and installed by Your Company.",
        "Engineering PE-stamped per Texas registration.",
        "Shop primer one coat gray per AISC Code of Standard Practice.",
    ]

    @staticmethod
    def run_all() -> dict:
        from bridge.governance import check_compliance

        missed = 0
        false_positives = 0
        details = []

        for phrase in ComplianceAttackLibrary.ATTACKS:
            v = check_compliance(phrase, context="bid")
            if not v:
                missed += 1
                details.append({"phrase": phrase, "expected": "flag", "got": "clean"})

        for phrase in ComplianceAttackLibrary.CLEAN:
            v = check_compliance(phrase, context="bid")
            if v:
                false_positives += 1
                details.append({"phrase": phrase, "expected": "clean",
                                "got": [x.get("rule") for x in v]})

        total_phrases = len(ComplianceAttackLibrary.ATTACKS) + len(ComplianceAttackLibrary.CLEAN)
        correct = total_phrases - missed - false_positives
        accuracy = round(correct / total_phrases * 100, 1) if total_phrases else 0.0
        return {
            "total_phrases": total_phrases,
            "correct": correct,
            "missed": missed,
            "false_positives": false_positives,
            "accuracy": accuracy,
            "details": details,
        }


class VoiceCalibrationHarness:
    """the Owner's 10 voice rules from brand-voice.md, as a deterministic gate.

    check() is a staticmethod so both the class call
    (VoiceCalibrationHarness.check(text), used by api.check_voice,
    bid_scorecard, documents) and the instance call
    (VoiceCalibrationHarness().check(text), used by diagnostics) work.

    Severity model per brand-voice.md: the kill-list constructions are
    hard (block and rewrite); wording-quality items (vague intensifiers,
    marketing cliche, padding) are soft (warn). Verdict: FAIL on any hard
    violation, WARN on soft only, PASS when clean.
    """

    # Rule 1: em-dash U+2014 and typographic dash U+2013 (hard).
    # Escapes, not literals: this file is itself subject to the rule.
    _EM_DASH = re.compile("[\\u2014\\u2013]")

    # Rule 2: three-adjective list (hard). Pure-stdlib heuristic: flag
    # "<w>, <w>, and <w>" only when at least two of the three words sit in
    # the marketing-adjective lexicon, so plain noun lists ("columns,
    # beams, and joists") pass clean.
    _TRIPLE = re.compile(r"\b([A-Za-z-]+), ([A-Za-z-]+),? and ([A-Za-z-]+)\b")
    _ADJ_LEXICON = frozenset([
        "solid", "compelling", "impressive", "reliable", "dependable",
        "durable", "robust", "proven", "trusted", "trustworthy", "seamless",
        "innovative", "efficient", "effective", "dedicated", "experienced",
        "professional", "skilled", "certified", "premium", "superior",
        "exceptional", "outstanding", "strong", "fast", "safe", "simple",
        "clean", "modern", "flexible", "scalable", "affordable",
        "competitive", "responsive", "accurate", "precise", "thorough",
        "detailed", "powerful", "comprehensive", "significant", "great",
        "excellent", "unmatched", "unparalleled", "streamlined",
    ])

    # Rule 3: "not just X, it's Y" / "it's not X, it's Y" (hard).
    _NOT_JUST = [
        re.compile(r"(?i)\bnot just\b[^.!?\n]{0,80}?[,;]?\s+(?:it'?s|but)\b"),
        re.compile(r"(?i)\bit'?s not\b[^.!?\n]{0,80}?,\s*it'?s\b"),
    ]

    # Rule 4: AI openers and hedging (hard).
    _AI_OPENERS = [
        "great question", "i'd be happy to", "i would be happy to",
        "i understand your concern", "let's dive in", "moreover",
        "furthermore", "in conclusion", "i hope this helps",
        "feel free to", "don't hesitate to",
    ]
    _COMES_IN = re.compile(r"(?i)\bthat'?s where\b[^.!?\n]{0,60}?\bcomes in\b")

    # Rule 5: vague intensifiers and buzzwords (soft).
    _BUZZWORDS = [
        "huge", "significant", "robust", "comprehensive", "best-in-class",
        "world-class", "cutting-edge", "leverage", "synergy", "unpack",
        "deep dive", "circle back", "touch base",
    ]

    # Rule 6: marketing cliche (soft).
    _CLICHES = [
        "in house from day one", "passion-driven", "customer-obsessed",
        "we live and breathe", "from concept to completion",
        "one-stop shop", "turnkey solution",
    ]

    # Rule 7: padding language (soft), with the brand-voice replacement.
    _PADDING = {
        "in order to": "to",
        "due to the fact that": "because",
        "at this point in time": "now",
        "in the event that": "if",
        "for the purpose of": "for",
        "with regard to": "about",
        "the fact of the matter is": "(cut)",
        "it should be noted that": "(cut)",
        "needless to say": "(cut)",
        "as a matter of fact": "(cut)",
    }

    # Rule 8: placeholder tokens (hard). Uppercase tokens plus any
    # [bracketed] or {braced} text; quantities ship exact or not at all.
    _PLACEHOLDERS = [
        re.compile(r"\bTBD\b"), re.compile(r"\bTBA\b"),
        re.compile(r"\bPENDING\b"), re.compile(r"\bTO BE DETERMINED\b"),
        re.compile(r"\bINSERT NUMBER HERE\b"),
        re.compile(r"\[[^\]\n]{1,60}\]"), re.compile(r"\{[^}\n]{1,60}\}"),
    ]

    # Rule 9: tilde on a quantity (hard).
    _TILDE_QTY = re.compile(r"~\s*\d")

    # Rule 10: HTML ampersand entity (hard). Literal & only.
    _AMP = re.compile(r"&amp;")

    _MAX_PER_RULE = 10

    @staticmethod
    def check(text: str) -> dict:
        """Run the 10 rules over text. Returns counts, details, verdict."""
        text = text or ""
        cls = VoiceCalibrationHarness
        violations = []

        def _add(rule, severity, match, fix):
            violations.append({
                "rule": rule, "severity": severity,
                "match": str(match)[:80], "fix": fix,
            })

        for m in cls._EM_DASH.finditer(text):
            ctx = text[max(0, m.start() - 25):m.end() + 25].strip()
            _add("em_dash", "hard", ctx,
                 "Replace: period between clauses, comma for a "
                 "parenthetical, hyphen for a separator.")

        for m in list(cls._TRIPLE.finditer(text))[:cls._MAX_PER_RULE]:
            words = [m.group(1).lower(), m.group(2).lower(), m.group(3).lower()]
            if sum(1 for w in words if w in cls._ADJ_LEXICON) >= 2:
                _add("triple_adjective", "hard", m.group(0),
                     "Drop the middle adjective. Two carry; three pad.")

        for pat in cls._NOT_JUST:
            for m in list(pat.finditer(text))[:cls._MAX_PER_RULE]:
                _add("not_just_x_its_y", "hard", m.group(0),
                     "Remove the construction. State the second clause "
                     "directly.")

        low = text.lower()
        for phrase in cls._AI_OPENERS:
            idx = low.find(phrase)
            if idx >= 0:
                _add("ai_opener", "hard", text[idx:idx + len(phrase)],
                     "Delete the opener. Start with the point.")
        for m in list(cls._COMES_IN.finditer(text))[:cls._MAX_PER_RULE]:
            _add("ai_opener", "hard", m.group(0),
                 "Delete the construction. Name the thing and what it does.")

        for word in cls._BUZZWORDS:
            for m in list(re.finditer(r"(?i)\b" + re.escape(word) + r"\b",
                                      text))[:cls._MAX_PER_RULE]:
                _add("vague_intensifier", "soft", m.group(0),
                     "Replace with a specific number or cut.")

        for phrase in cls._CLICHES:
            idx = low.find(phrase)
            if idx >= 0:
                _add("marketing_cliche", "soft", text[idx:idx + len(phrase)],
                     "Cut. State the capability plainly.")

        for phrase, repl in cls._PADDING.items():
            idx = low.find(phrase)
            if idx >= 0:
                _add("padding", "soft", text[idx:idx + len(phrase)],
                     f"Use '{repl}'." if repl != "(cut)" else "Cut the phrase.")

        for pat in cls._PLACEHOLDERS:
            for m in list(pat.finditer(text))[:cls._MAX_PER_RULE]:
                _add("placeholder_token", "hard", m.group(0),
                     "Replace with the exact measured value before this "
                     "text ships.")

        for m in list(cls._TILDE_QTY.finditer(text))[:cls._MAX_PER_RULE]:
            ctx = text[max(0, m.start() - 15):m.end() + 15].strip()
            _add("tilde_quantity", "hard", ctx,
                 "Quantities are exact measured numbers. Drop the tilde.")

        for m in list(cls._AMP.finditer(text))[:cls._MAX_PER_RULE]:
            _add("amp_entity", "hard", m.group(0),
                 "Use a literal & and regenerate the rendering.")

        hard = sum(1 for v in violations if v["severity"] == "hard")
        soft = sum(1 for v in violations if v["severity"] == "soft")
        verdict = "FAIL" if hard else ("WARN" if soft else "PASS")
        return {
            "rules_checked": 10,
            "text_length": len(text),
            "violations": violations,
            "hard_violations": hard,
            "soft_violations": soft,
            "verdict": verdict,
        }
