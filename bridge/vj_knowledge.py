"""Virtual Joseph Knowledge Base and Creative Reasoning Engine.

This module gives Virtual Joseph the ability to:
  1. Learn from every bug ever found (pattern recognition across sessions)
  2. Apply Joseph's actual decision-making heuristics
  3. Use LLM reasoning for creative problem-solving (not just regex)
  4. Research solutions using available tools
  5. Grow smarter over time as more bugs are found and fixed

The knowledge base is seeded from the v3.5.x through v6.1.2 sprint
history. Every bug class, every creative solution, every "two heads"
moment is encoded as a reusable pattern.

Usage:
    from bridge.vj_knowledge import VJKnowledgeBase, CreativeReasoner

    kb = VJKnowledgeBase()
    # Check if a new issue matches a known pattern
    matches = kb.match_pattern(error_text, context)

    # Ask VJ to reason about a problem creatively
    reasoner = CreativeReasoner(kb)
    solution = reasoner.think_about(problem_description, code_context)
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("vj_knowledge")

_DATA_DIR = Path(__file__).parent.parent / "data" / "virtual_joseph"


# ================================================================
# Lesson: a single bug pattern learned from sprint history
# ================================================================

@dataclass
class Lesson:
    """A bug pattern learned from experience."""
    id: str                    # unique identifier
    pattern_class: str         # e.g., "silent_import", "key_mismatch", "stale_test"
    title: str                 # human-readable title
    description: str           # what the bug looks like
    detection_method: str      # how to find it
    fix_pattern: str           # how to fix it
    severity: str              # critical, high, medium, low
    source_version: str        # which version first found it
    source_finder: str         # who/what found it (joseph, gemini_sim, sweep4, vj_scan)
    occurrences: int = 1       # how many times this pattern has appeared
    tags: list[str] = field(default_factory=list)


# ================================================================
# Decision Rule: Joseph's actual heuristic from chat behavior
# ================================================================

@dataclass
class DecisionRule:
    """A decision-making heuristic extracted from Joseph's behavior."""
    id: str
    trigger: str               # what situation triggers this rule
    action: str                # what to do
    reasoning: str             # why this works
    source: str                # which chat/session this came from
    priority: int = 5          # 1=highest, 10=lowest


# ================================================================
# The Knowledge Base
# ================================================================

class VJKnowledgeBase:
    """Stores and retrieves lessons learned and decision patterns.

    Seeded from the entire v3.5.x through v6.1.2 sprint history.
    Grows over time as new bugs are found.
    """

    def __init__(self):
        self.lessons: list[Lesson] = []
        self.decision_rules: list[DecisionRule] = []
        self._seed_lessons()
        self._seed_decision_rules()

    # ---- Pattern matching ----

    def match_pattern(self, error_text: str, context: str = "") -> list[Lesson]:
        """Find lessons that match a new error or situation.

        This is how VJ recognizes "I've seen this class of bug before"
        even when the specific instance is new.
        """
        matches = []
        combined = f"{error_text} {context}".lower()

        for lesson in self.lessons:
            score = 0
            # Check pattern class keywords
            for tag in lesson.tags:
                if tag.lower() in combined:
                    score += 2
            # Check description keywords
            desc_words = set(lesson.description.lower().split())
            error_words = set(combined.split())
            overlap = desc_words & error_words
            score += len(overlap)

            if score >= 2:
                matches.append(lesson)

        # Sort by relevance (occurrence count as tiebreaker)
        matches.sort(key=lambda l: l.occurrences, reverse=True)
        return matches

    def get_lesson(self, pattern_class: str) -> list[Lesson]:
        """Get all lessons of a specific pattern class."""
        return [l for l in self.lessons if l.pattern_class == pattern_class]

    def add_lesson(self, lesson: Lesson):
        """Add a new lesson learned from a bug fix."""
        # Check for duplicates
        for existing in self.lessons:
            if existing.id == lesson.id:
                existing.occurrences += 1
                self._save()
                return
        self.lessons.append(lesson)
        self._save()

    def get_decision_rules(self, trigger_keyword: str = "") -> list[DecisionRule]:
        """Get decision rules, optionally filtered by trigger keyword."""
        if trigger_keyword:
            return [
                r for r in self.decision_rules
                if trigger_keyword.lower() in r.trigger.lower()
            ]
        return sorted(self.decision_rules, key=lambda r: r.priority)

    # ---- Seed data ----

    def _seed_lessons(self):
        """Seed from the v3.5.x through v6.1.2 sprint history."""
        self.lessons = [
            # === Pattern class: silent_import ===
            Lesson(
                id="sweep4_p0",
                pattern_class="silent_import",
                title="Calculator shape lookup broken across 8 deliveries",
                description=(
                    "Calculator loaded 0 shapes because the import path changed "
                    "but the wrapper method still called the old path. Every bid "
                    "silently returned $0 weight. Survived 8 deliveries because "
                    "the wrapping try/except turned the ImportError into a silent "
                    "error response."
                ),
                detection_method=(
                    "Call the Bridge method and check if the return value contains "
                    "real data vs an error dict. Import-time tests pass because "
                    "the module loads; the bug is at call time."
                ),
                fix_pattern=(
                    "Read the target module's actual exports (dir(module)) and "
                    "find the correct function name. Update the import. Verify "
                    "by calling the method and checking the return value."
                ),
                severity="critical",
                source_version="v3.5.6",
                source_finder="sweep4_sim",
                occurrences=1,
                tags=["ImportError", "silent", "try/except", "wrapper", "calculator", "shapes"],
            ),
            Lesson(
                id="v612_import_3",
                pattern_class="silent_import",
                title="3 Bridge methods importing non-existent functions",
                description=(
                    "api.py imported calculate_consumable, get_status, and "
                    "get_benchmarks from their respective modules. None of these "
                    "functions existed. The correct exports were estimate_joint, "
                    "for_morning_briefing/get_continuity_alerts, and BENCHMARKS."
                ),
                detection_method=(
                    "For every 'from bridge.X import Y' in api.py, check that Y "
                    "actually exists in module X using hasattr(module, Y)."
                ),
                fix_pattern=(
                    "Import the module, list its exports, find the closest match "
                    "to the expected function name, update the import and adjust "
                    "the calling code to match the new function's signature."
                ),
                severity="critical",
                source_version="v6.1.2",
                source_finder="joseph_internal",
                occurrences=3,
                tags=["ImportError", "silent", "api.py", "bridge", "wrapper"],
            ),
            Lesson(
                id="v612_vj_import_11",
                pattern_class="silent_import",
                title="VJ self-repair found 11 more silent import bugs",
                description=(
                    "Virtual Joseph's first scan of the codebase found 11 Bridge "
                    "methods importing functions that don't exist in their target "
                    "modules. Same class as sweep4 P0 and the 3 from v6.1.2. "
                    "Includes shop_floor (4 methods), emr_predictor (2), bid_chain, "
                    "stl_generator, calibration, vault, and keyvault."
                ),
                detection_method=(
                    "Automated: SelfRepairEngine._scan_import_paths() checks every "
                    "import in api.py against actual module exports."
                ),
                fix_pattern="Same as v612_import_3. Match export names to actual module dir().",
                severity="critical",
                source_version="v6.1.2",
                source_finder="vj_self_repair",
                occurrences=11,
                tags=["ImportError", "silent", "api.py", "self_repair", "automated"],
            ),

            # === Pattern class: key_mismatch ===
            Lesson(
                id="v611_takeoff_zero",
                pattern_class="key_mismatch",
                title="v1 takeoff controller silent-zero pricing",
                description=(
                    "labor_cost() returns 'total_labor' but controller read 'total'. "
                    "bid_total() returns 'bid_total' but controller read 'total'. "
                    "Every v1-pipeline bid silently returned $0."
                ),
                detection_method=(
                    "Check that the keys a caller reads from a function's return "
                    "dict actually exist in that dict. Run the full chain and "
                    "verify the final number is non-zero."
                ),
                fix_pattern=(
                    "Add fallback reads: lc.get('total_labor', lc.get('total', 0)). "
                    "Preserves backward compat while fixing the mismatch."
                ),
                severity="critical",
                source_version="v6.1.1",
                source_finder="joseph_deep_debug",
                occurrences=2,
                tags=["key", "dict", "silent", "zero", "pricing", "fallback"],
            ),

            # === Pattern class: stale_test ===
            Lesson(
                id="v611_stale_version",
                pattern_class="stale_test",
                title="Test hardcodes version string instead of pattern",
                description=(
                    "test_release_tag_format asserted '3.5' in tag. When version "
                    "bumped to 6.1.1, the test failed. The tag was correct; the "
                    "test was stale."
                ),
                detection_method=(
                    "Search test files for hardcoded version strings. Check if "
                    "any assertion contains a literal version number."
                ),
                fix_pattern=(
                    "Replace hardcoded version with regex: "
                    "re.match(r'steel-office@\\d+\\.\\d+', tag). "
                    "Locks the SHAPE not the specific value."
                ),
                severity="low",
                source_version="v6.1.1",
                source_finder="v611_sim",
                occurrences=1,
                tags=["test", "stale", "version", "hardcoded", "regex"],
            ),
            Lesson(
                id="v611_emdash_char",
                pattern_class="stale_test",
                title="Em-dash test checks wrong Unicode character",
                description=(
                    "Two tests assert '-' (U+002D hyphen-minus) not in text, but "
                    "should check for U+2014 (em-dash). The text has 0 em-dashes "
                    "but uses hyphens for markdown bullets, causing false failure."
                ),
                detection_method=(
                    "Byte-level check: is the character in the assertion literal "
                    "actually the character the test claims to be checking for?"
                ),
                fix_pattern=(
                    "Replace '-' with '\\u2014' in the assertion. Single character "
                    "fix per test."
                ),
                severity="low",
                source_version="v6.1.1",
                source_finder="v611_sim",
                occurrences=2,
                tags=["test", "unicode", "character", "em-dash", "hyphen"],
            ),

            # === Pattern class: over_tightening ===
            Lesson(
                id="v611_sheetid_regex",
                pattern_class="over_tightening",
                title="Sheet-ID regex rejects legitimate 3-digit IDs",
                description=(
                    "v3.5.12 tightened digit limit from {1,3} to {1,2} to prevent "
                    "false positives. But S-001 and F-001 are standard structural "
                    "sheet IDs. The word boundary already prevented the original "
                    "false positive (MA1234)."
                ),
                detection_method=(
                    "Test with real-world inputs (S-001, F-001, S-12) not just "
                    "adversarial inputs. Every tightening should be tested against "
                    "the full range of legitimate inputs."
                ),
                fix_pattern=(
                    "Restore {1,3}. The word boundary handles the false positive "
                    "that motivated the tightening. Don't over-tighten when the "
                    "existing guard already works."
                ),
                severity="medium",
                source_version="v6.1.1",
                source_finder="joseph_deep_debug",
                occurrences=1,
                tags=["regex", "over-tighten", "false-negative", "sheet-id"],
            ),

            # === Pattern class: changelog_accuracy ===
            Lesson(
                id="v611_changelog_gap",
                pattern_class="changelog_accuracy",
                title="CHANGELOG numbers don't match pytest output",
                description=(
                    "CHANGELOG claimed '1,192 passed, 0 failed' but pytest "
                    "reported 1,201 passed, 3 failed. The failures were stale "
                    "tests, not real bugs, but the numbers were wrong."
                ),
                detection_method=(
                    "After writing the CHANGELOG, run pytest and compare the "
                    "actual output to the claimed numbers. Byte-for-byte."
                ),
                fix_pattern=(
                    "Run pytest, copy the actual numbers into the CHANGELOG. "
                    "If there are failures, document them even if they're stale "
                    "tests. Honesty in headlines."
                ),
                severity="medium",
                source_version="v6.1.1",
                source_finder="v611_sim",
                occurrences=2,
                tags=["changelog", "accuracy", "pytest", "numbers", "honesty"],
            ),

            # === Pattern class: bare_except ===
            Lesson(
                id="v612_bare_except",
                pattern_class="bare_except",
                title="111 bare except: clauses across 33 files",
                description=(
                    "Bare 'except:' catches KeyboardInterrupt and SystemExit. "
                    "In production, this means Ctrl+C and process signals get "
                    "swallowed. The correct form is 'except Exception:'."
                ),
                detection_method="grep -rn 'except:' --include='*.py' | grep -v 'except Exception'",
                fix_pattern="Mechanical: replace 'except:' with 'except Exception:'.",
                severity="medium",
                source_version="v6.1.2",
                source_finder="joseph_internal",
                occurrences=111,
                tags=["except", "bare", "KeyboardInterrupt", "SystemExit", "hygiene"],
            ),

            # === Pattern class: ai_bias ===
            Lesson(
                id="v612_emdash_purge",
                pattern_class="ai_bias",
                title="327 em-dashes in bridge/api.py (AI signal in code)",
                description=(
                    "Em-dashes in Python docstrings and comments signal "
                    "AI-generated code. Voice rule originally exempted internal "
                    "Python. Joseph went beyond the rule and purged all 327."
                ),
                detection_method="open(file).read().count('\\u2014')",
                fix_pattern="Replace em-dashes with hyphens or rephrase.",
                severity="high",
                source_version="v6.1.1",
                source_finder="joseph_beyond_scope",
                occurrences=327,
                tags=["em-dash", "voice", "ai", "bias", "signal"],
            ),

            # === Meta-pattern: integration_path ===
            Lesson(
                id="meta_integration",
                pattern_class="integration_path",
                title="Integration paths are where real bugs hide",
                description=(
                    "Every major bug in the sprint was found at integration "
                    "boundaries, not within individual modules. File-level code "
                    "looks correct. Unit tests pass. The bug surfaces only when "
                    "Module A calls Module B with real data."
                ),
                detection_method=(
                    "Exercise full chains end-to-end: AISC -> weight -> hours -> "
                    "labor -> margin -> cost -> STL -> governance. Any break in "
                    "the chain reveals an integration bug."
                ),
                fix_pattern=(
                    "Don't trust unit tests alone. Run integration chains. "
                    "Cross-phase testing catches what per-phase testing misses."
                ),
                severity="critical",
                source_version="sweep4",
                source_finder="sweep4_sim",
                occurrences=15,
                tags=["integration", "cross-phase", "chain", "end-to-end"],
            ),

            # === Meta-pattern: two_heads ===
            Lesson(
                id="meta_two_heads",
                pattern_class="two_heads",
                title="No single perspective catches every bug",
                description=(
                    "Sweep4 caught bugs the manual tests missed. The sim caught "
                    "bugs Joseph missed. Joseph caught bugs the sim missed. "
                    "VJ caught bugs everyone missed. Each perspective has blind "
                    "spots. Diverse probing finds more issues than deep probing "
                    "from one angle."
                ),
                detection_method=(
                    "Run multiple scan types: static analysis, integration tests, "
                    "adversarial probes, bias detection, CHANGELOG verification. "
                    "Each catches a different class."
                ),
                fix_pattern=(
                    "Don't assume clean after one pass. Run VJ scan, then manual "
                    "review, then sim. The bugs that survive all three are the "
                    "ones that need creative thinking to find."
                ),
                severity="critical",
                source_version="v6.1.2",
                source_finder="joseph_insight",
                occurrences=1,
                tags=["diversity", "perspective", "blind-spot", "two-heads"],
            ),

            # ================================================================
            # v3.2.7 debug sweep - 9 bugs found by automated static analysis
            # Found by: Claude automated debug cycle (Joseph's request, May 2026)
            # ================================================================

            Lesson(
                id="v327_bug001_double_dict_definition",
                pattern_class="double_dict_definition",
                title="Module-level dict defined twice - second silently overwrites first",
                description=(
                    "MATERIAL_COSTS in bridge/bid_rates.py was defined at line 35 "
                    "(9 keys: internal cost basis) and again at line 156 (4 keys: "
                    "volatility range). Python silently overwrites - the 9-key version "
                    "was completely gone at runtime. Any caller accessing joist_raw_per_ton, "
                    "roof_deck_1_5B22_per_sf, or anchor_rod keys would get KeyError. "
                    "The w_shapes_per_ton value also silently changed from 1250 to 1150 "
                    "($100/ton error on every scorecard cash-flow check)."
                ),
                detection_method=(
                    "AST scan: walk all module-level Assign nodes, flag any Name target "
                    "that appears more than once. grep pattern: "
                    "grep -n '^VAR_NAME = {' file.py | wc -l (should be 1). "
                    "Also catches: BID_RATES, BID_MARGINS, TONNAGE_BENCHMARKS defined twice."
                ),
                fix_pattern=(
                    "Merge both dicts into one. Rename conflicting keys to be explicit "
                    "(e.g., w_shapes_per_ton_low vs w_shapes_per_ton for internal basis). "
                    "Delete the second definition entirely. "
                    "Update all callers of the renamed keys."
                ),
                severity="critical",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["double-definition", "silent-overwrite", "dict", "bid_rates", "p1"],
            ),

            Lesson(
                id="v327_bug002_wrong_dict_key_silent_except",
                pattern_class="wrong_key_silent_except",
                title="Wrong dict key + bare except: branch never ran, 5pts missing from every scorecard",
                description=(
                    "bid_scorecard.py line 152: BID_RATES['fab'] raises KeyError because "
                    "the correct key is 'fab_per_ton'. A bare 'except Exception: pass' on "
                    "line 149 caught it silently. The entire margin-check branch has never "
                    "executed in production. Every bid scorecard has been 5 points too "
                    "generous. Bug survived because: (1) no unit test exercised this exact "
                    "path to completion, (2) the score still looked reasonable, "
                    "(3) except: pass erased all evidence."
                ),
                detection_method=(
                    "Fix P scan (self_repair.py bare-return passthroughs) catches some "
                    "of this class. Full catch requires: grep for 'except Exception: pass' "
                    "or 'except: pass', then inspect each guarded block for KeyError-prone "
                    "dict access. Also: cross-reference BID_RATES keys against all "
                    "BID_RATES['X'] calls in the codebase."
                ),
                fix_pattern=(
                    "1. Fix the key: BID_RATES['fab'] -> BID_RATES['fab_per_ton']. "
                    "2. Narrow the except: replace 'except Exception: pass' with "
                    "   'except (ImportError, FileNotFoundError): pass' where possible. "
                    "3. Add a log.warning() so silent failures surface in diagnostics. "
                    "4. Add a targeted unit test that calls the method and asserts "
                    "   the margin-check deduction appears in the output."
                ),
                severity="high",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["wrong-key", "silent-except", "bid_scorecard", "p1", "silent-failure"],
            ),

            Lesson(
                id="v327_bug003_missing_status_in_penalty_table",
                pattern_class="incomplete_status_dispatch",
                title="Gate status value not in confidence penalty table - scores inflate",
                description=(
                    "bid_sanity_gates.py calculate_confidence() handled BLOCK/FLAG/CAUTION/"
                    "CORRECTED but not LOW. Gate 1 returns LOW when no EQ.SPA annotations "
                    "exist (joist count unverifiable). A bid with zero geometry confirmation "
                    "scored 100/100 confidence. Pattern: enum-like status values added to "
                    "one place (gate functions) but the dispatch table in another function "
                    "was not updated to match."
                ),
                detection_method=(
                    "Collect all status strings returned by gate functions (gate1 returns "
                    "HIGH/CORRECTED/LOW; gate2/3 return PASS/FLAG/CAUTION/BLOCK; gate4 "
                    "returns PASS/FLAG). Cross-reference against calculate_confidence() "
                    "elif chain. Any status not in the chain scores 0 penalty. "
                    "Test: call run_gates with a LOW-triggering input, assert confidence < 100."
                ),
                fix_pattern=(
                    "Add every possible status value to the penalty table: "
                    "elif g['status'] == 'LOW': score -= 15  "
                    "Choose penalty weight proportional to risk severity. "
                    "Add a catch-all: else: log.warning('Unknown gate status: %s', g['status'])"
                ),
                severity="high",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["incomplete-dispatch", "confidence-score", "sanity-gates", "p2", "status-enum"],
            ),

            Lesson(
                id="v327_bug004_benchmark_table_asymmetry",
                pattern_class="parallel_table_asymmetry",
                title="Building type in TONNAGE_BENCHMARKS but missing from PRICE_BENCHMARKS",
                description=(
                    "bid_sanity_gates.py: office_multistory was in TONNAGE_BENCHMARKS "
                    "(6 types) but absent from PRICE_BENCHMARKS (5 types). Gate 3 "
                    "silently fell back to retail_small (floor=$15/SF). A multistory "
                    "office at $10/SF wrongly passed Gate 3 - the correct floor is ~$35/SF. "
                    "Pattern: two parallel lookup tables that must stay in sync, "
                    "but there is no enforcement that both tables contain the same keys."
                ),
                detection_method=(
                    "For any pair of dicts that should share the same key universe: "
                    "assert set(TABLE_A.keys()) == set(TABLE_B.keys()), "
                    "f'Key mismatch: {set(TABLE_A.keys()) ^ set(TABLE_B.keys())}'. "
                    "Add this as a module-level assertion or a unit test."
                ),
                fix_pattern=(
                    "Add the missing building type to PRICE_BENCHMARKS with correct "
                    "floor/mid/ceiling values. "
                    "Add a unit test: assert set(TONNAGE_BENCHMARKS) == set(PRICE_BENCHMARKS). "
                    "Add a comment near both tables: '# KEEP IN SYNC - both tables must "
                    "have the same keys. If you add a type to one, add it to both.'"
                ),
                severity="high",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["parallel-tables", "missing-key", "silent-fallback", "sanity-gates", "p2"],
            ),

            Lesson(
                id="v327_bug005_pyinstaller_missing_runtime_dir",
                pattern_class="pyinstaller_missing_datas",
                title="Runtime-loaded directory not in PyInstaller datas - absent from EXE",
                description=(
                    "VirtualOffice.spec datas block only contained frontend/ and data/. "
                    "SkillRegistry loads skills/ at runtime via Path(__file__).parent.parent. "
                    "In a frozen EXE, __file__ points to _MEIPASS but skills/ was never "
                    "bundled, so the directory didn't exist there. "
                    "SkillRegistry._load_metadata() logged a warning and returned empty. "
                    "All 10 SKILL.md files (bid-compliance, drawing-reading, etc.) "
                    "were silently absent in every production EXE build."
                ),
                detection_method=(
                    "Grep for Path(__file__) or resource_path() in all bridge modules. "
                    "For each directory reference, verify it appears in the spec datas block. "
                    "Pattern: any module that does os.listdir() or Path().iterdir() at "
                    "runtime on a relative path must have that path in datas."
                ),
                fix_pattern=(
                    "Add to VirtualOffice.spec datas: "
                    "(str(Path('skills').resolve()), 'skills'), "
                    "(str(Path('assets').resolve()), 'assets'). "
                    "Rule: for every directory a module reads at runtime via relative path, "
                    "that directory must be in datas. "
                    "Test: build EXE, grep dist/ for SKILL.md files."
                ),
                severity="high",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["pyinstaller", "datas", "skills", "frozen-exe", "p2", "silent-missing"],
            ),

            Lesson(
                id="v327_bug006_tls_fallback_gap_new_path",
                pattern_class="tls_fallback_gap",
                title="New API call path lacks TLS fallback chain - fails on corporate proxy",
                description=(
                    "claude_connect.py call_claude_with_mcps() used bare "
                    "anthropic.Anthropic(api_key=api_key) with no TLS override. "
                    "call_claude_robust() had a 6-strategy TLS cascade (truststore -> "
                    "ssl_default -> certifi -> urllib -> curl.exe -> verify=False) "
                    "built for the Owner's corporate network. The MCP path had none of it. "
                    "Result: regular chat worked, M365/Slack MCP calls failed on any "
                    "TLS-intercepting proxy. Pattern: new code paths forget to inherit "
                    "established infrastructure workarounds."
                ),
                detection_method=(
                    "Grep for 'anthropic.Anthropic(' - every call site should either "
                    "use call_claude_robust() or replicate the truststore strategy. "
                    "Any bare anthropic.Anthropic(api_key=key) without an http_client "
                    "argument is a TLS gap candidate on Windows corporate networks."
                ),
                fix_pattern=(
                    "Extract a _build_tls_client(api_key) helper that encapsulates the "
                    "truststore -> ssl_default cascade. Every Claude SDK call site uses it. "
                    "Never call anthropic.Anthropic() bare in Windows-deployed code. "
                    "Add to DIAGNOSE_CLAUDE.bat: test the MCP path specifically."
                ),
                severity="high",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["tls", "truststore", "mcp", "corporate-proxy", "p2", "windows"],
            ),

            Lesson(
                id="v327_bug009_nonexistent_model_string",
                pattern_class="nonexistent_model_string",
                title="Hardcoded future model string causes API model_not_found on every T4 call",
                description=(
                    "ai_model_router.py TIERS['max']['model'] = 'claude-opus-4-7' which "
                    "did not exist. Any task escalated to high_stakes_bid or "
                    "vendor_negotiation hit anthropic.NotFoundError. The bug was invisible "
                    "because T4 tasks are rare and the error is swallowed by api.py's "
                    "catch-all. Pattern: placeholding a future model string and forgetting "
                    "to guard it."
                ),
                detection_method=(
                    "grep -r 'claude-' --include='*.py' | grep -v '#' - collect all "
                    "model strings. Validate each against the current Anthropic model list. "
                    "Any model not in the known-valid set should be flagged. "
                    "Self-repair scan addition: add a _scan_model_strings() check."
                ),
                fix_pattern=(
                    "Redirect T4 to the highest available model until the new one ships. "
                    "Add a comment: '# TODO: update to claude-opus-4-7 when it ships'. "
                    "Add to self_repair.py: _scan_model_strings() that validates all "
                    "hardcoded model IDs against a known-good list."
                ),
                severity="medium",
                source_version="v3.2.7",
                source_finder="claude_debug_sweep",
                occurrences=1,
                tags=["model-string", "future-model", "api-error", "p3", "ai_model_router"],
            ),
        ]

    def _seed_decision_rules(self):
        """Seed from Joseph's actual behavior in chat sessions."""
        self.decision_rules = [
            DecisionRule(
                id="never_trust_all_clear",
                trigger="scan returns zero issues",
                action=(
                    "Run a DIFFERENT type of scan. If static analysis found "
                    "nothing, try integration testing. If integration passed, "
                    "try adversarial input. If that passed, check the CHANGELOG "
                    "against actual pytest output."
                ),
                reasoning=(
                    "Joseph's rule: 'never assume you checked all angles.' "
                    "Zero issues from one scan means zero issues from that "
                    "perspective, not zero issues total."
                ),
                source="v6.1.2 chat session",
                priority=1,
            ),
            DecisionRule(
                id="check_integration_not_unit",
                trigger="a module change or new feature",
                action=(
                    "Run the full integration chain that touches the changed "
                    "module. If calculators changed, run AISC -> weight -> "
                    "hours -> labor -> margin -> cost. Check the FINAL output "
                    "for correctness, not just the changed module."
                ),
                reasoning=(
                    "sweep4 P0: calculator was broken for 8 deliveries. Unit "
                    "tests passed. Integration test would have caught it. "
                    "Joseph: 'its not just the code itself but how the "
                    "interactions between codes works.'"
                ),
                source="sweep4 + v6.1.2 chat",
                priority=1,
            ),
            DecisionRule(
                id="question_ai_output",
                trigger="response contains AI-typical patterns",
                action=(
                    "Check for: em-dashes, triple-adjective lists, sycophantic "
                    "openers, 'leverage/synergy/utilize', AI self-references. "
                    "If found, rewrite in Your Company voice. Don't trust that "
                    "one AI model checked another AI model's output fairly."
                ),
                reasoning=(
                    "Joseph: 'ive seen first hand Claudes bias towards Gemini "
                    "and Copilot, and not just in the way you reply but in the "
                    "thinking.' AI models have blind spots toward other AI "
                    "models' patterns. A human would catch these."
                ),
                source="v6.1.2 chat session",
                priority=2,
            ),
            DecisionRule(
                id="go_beyond_scope",
                trigger="sim or review marks something as 'out of scope'",
                action=(
                    "Consider fixing it anyway. If the voice rule says Python "
                    "comments are exempt from em-dash checking, but the comments "
                    "still have em-dashes, fix them. The documented minimum is "
                    "not the actual bar."
                ),
                reasoning=(
                    "Joseph consistently sets a higher bar than what's required. "
                    "v6.1.1 purged 327 em-dashes that the voice rule explicitly "
                    "exempted. v3.5.12 fixed 8 issues beyond announced scope. "
                    "The pattern: 'beyond scope' means 'worth considering.'"
                ),
                source="v6.1.1 sim analysis",
                priority=3,
            ),
            DecisionRule(
                id="changelog_matches_reality",
                trigger="writing a CHANGELOG or version notes",
                action=(
                    "Run pytest. Copy the EXACT numbers. If there are failures, "
                    "document them even if they're stale tests. Never claim "
                    "'0 failed' when pytest says otherwise."
                ),
                reasoning=(
                    "v6.1.1 and v6.1.2 both had CHANGELOG accuracy gaps. "
                    "The underlying code was correct; the documentation was wrong. "
                    "Form matters because anyone reading the CHANGELOG needs to "
                    "trust the numbers."
                ),
                source="v6.1.1 + v6.1.2 sims",
                priority=2,
            ),
            DecisionRule(
                id="when_stuck_use_different_model",
                trigger="same bug pattern keeps appearing or fix doesn't work",
                action=(
                    "Use a different AI model or tool to analyze the problem. "
                    "If Claude can't find the bug, try Gemini deep research. "
                    "If static analysis misses it, try runtime probing. "
                    "The 'two heads' principle applies to tools too."
                ),
                reasoning=(
                    "Joseph: 'It is the collective work of different styles of "
                    "thinking that make collective work unique, and less "
                    "predictable but with better results.' Different models "
                    "have different blind spots."
                ),
                source="v6.1.2 chat session",
                priority=2,
            ),
            DecisionRule(
                id="catalog_every_correction",
                trigger="Owner corrects any output",
                action=(
                    "Store the correction as a permanent rule in VJ's correction "
                    "database. Check every future response against stored "
                    "corrections before delivery. The same mistake should never "
                    "happen twice."
                ),
                reasoning=(
                    "the Owner's corrections are the highest-signal feedback. "
                    "Each one reveals a gap in the system's understanding. "
                    "Encoding them as rules means the system learns from "
                    "every interaction."
                ),
                source="v6.1.2 chat session",
                priority=1,
            ),
            DecisionRule(
                id="test_with_real_inputs",
                trigger="writing or reviewing tests",
                action=(
                    "Use real-world inputs (S-001, W14X82, 28.4 tons) not just "
                    "edge cases and adversarial inputs. A regex that passes on "
                    "adversarial input but fails on standard input (S-001) is "
                    "worse than useless."
                ),
                reasoning=(
                    "v6.1.1 sheet-ID regex: tightened for adversarial defense "
                    "but broke on standard structural drawing sheet IDs. "
                    "Real-world correctness trumps adversarial defense."
                ),
                source="v6.1.1 deep-debug",
                priority=3,
            ),
            DecisionRule(
                id="fix_scanner_bugs_too",
                trigger="scanner/diagnostic tool produces false positives",
                action=(
                    "Fix the scanner itself. A scanner with false positives "
                    "trains users to ignore its output. VJ's import scanner "
                    "had a bug (didn't handle 'as' aliases) that produced 18 "
                    "false positives. Fix the scanner, then re-scan."
                ),
                reasoning=(
                    "The v6.1.2 self-repair scan initially reported 29 issues "
                    "but 18 were false positives from the alias parser bug. "
                    "After fixing the scanner, 11 real issues remained. "
                    "Trust in tools requires accuracy."
                ),
                source="v6.1.2 self-repair session",
                priority=2,
            ),
            DecisionRule(
                id="owner_request_memory",
                trigger="Owner asks to remember something or corrects information",
                action=(
                    "1. Store the correction/memory in VJ's correction database. "
                    "2. Check if the correction affects any existing code (search "
                    "   for the old value across the codebase). "
                    "3. If code changes are needed, make them and verify. "
                    "4. Add a test that locks the correct value. "
                    "5. Confirm back to Owner that it's stored and enforced."
                ),
                reasoning=(
                    "Joseph: 'If Owner ever asks the chat to remember something "
                    "or corrects anything Virtual me should make sure that his "
                    "responses/requests are catalogued into the software and "
                    "memory properly always checking for bugs and if it will work.'"
                ),
                source="v6.1.2 chat session",
                priority=1,
            ),

            # ================================================================
            # v3.2.7 debug sweep decision rules - May 2026
            # Source: automated debug cycle, Claude static analysis
            # ================================================================

            DecisionRule(
                id="debug_sweep_before_ship",
                trigger="preparing to ship a build or patch",
                action=(
                    "Run a full static analysis sweep before packaging: "
                    "1. python3 -m py_compile on all .py files (catches syntax). "
                    "2. node --check on app.js (catches JS syntax). "
                    "3. Count <div> opens vs </div> closes in index.html. "
                    "4. grep -rn 'em-dash (U+2014)' all .py and .js files. "
                    "5. python3 -c 'import ast; scan all files for duplicate "
                    "   module-level assignments (double dict definition class)'. "
                    "6. grep -rn 'except Exception: pass' and inspect each. "
                    "7. Cross-reference TONNAGE_BENCHMARKS vs PRICE_BENCHMARKS keys. "
                    "8. Validate all hardcoded model strings against known-good list. "
                    "9. Check PyInstaller spec datas against all runtime Path() reads."
                ),
                reasoning=(
                    "v3.2.7 debug sweep found 9 bugs in a codebase that had passed "
                    "1,496 unit tests and 6 SIM rounds. None of the bugs were caught "
                    "by existing tests because: (1) silent except hid KeyErrors, "
                    "(2) double-definition is invisible at import time, "
                    "(3) parallel tables have no cross-check enforcement. "
                    "Static analysis catches what tests miss."
                ),
                source="v3.2.7 debug sweep",
                priority=1,
            ),

            DecisionRule(
                id="scan_for_double_definitions",
                trigger="any module with multiple top-level constants or dicts",
                action=(
                    "After writing or editing any module, grep for duplicate "
                    "module-level assignments: "
                    "python3 -c \""
                    "import ast, sys; src=open(sys.argv[1]).read(); "
                    "tree=ast.parse(src); names=[]; "
                    "[names.append(t.id) for n in ast.walk(tree) "
                    "if isinstance(n, ast.Assign) for t in n.targets "
                    "if isinstance(t, ast.Name)]; "
                    "dups=[n for n in set(names) if names.count(n)>1]; "
                    "print('Duplicates:', dups)\" bridge/bid_rates.py. "
                    "Any duplicate is a silent overwrite waiting to happen."
                ),
                reasoning=(
                    "MATERIAL_COSTS was defined at line 35 and again at line 156. "
                    "The second definition won. 6 keys from the first vanished. "
                    "w_shapes_per_ton changed from 1250 to 1150 silently. "
                    "Python has no warning for this. Only an AST scan catches it."
                ),
                source="v3.2.7 bug BUG-001",
                priority=2,
            ),

            DecisionRule(
                id="parallel_table_sync_check",
                trigger="adding a new building type, category, or enum value",
                action=(
                    "When adding a value to any lookup table (TONNAGE_BENCHMARKS, "
                    "PRICE_BENCHMARKS, SCOPE_CHECKLIST, BID_RATES, BID_MARGINS, "
                    "status_icon dicts, etc.), immediately check: "
                    "1. Are there other tables that are supposed to have the same keys? "
                    "2. Add the value to ALL of them. "
                    "3. Add an assertion: "
                    "   assert set(TABLE_A) == set(TABLE_B), f'Sync error: {set(TABLE_A)^set(TABLE_B)}'. "
                    "4. If adding a new gate status, update calculate_confidence() too."
                ),
                reasoning=(
                    "office_multistory was in TONNAGE_BENCHMARKS but absent from "
                    "PRICE_BENCHMARKS. Gate 3 fell back to retail_small (floor=$15/SF) "
                    "silently. The correct floor for multistory office is $35/SF. "
                    "Same pattern applies to calculate_confidence - Gate 1 returned "
                    "LOW but LOW was not in the penalty table, so it scored 0 penalty."
                ),
                source="v3.2.7 bugs BUG-003, BUG-004",
                priority=2,
            ),

            DecisionRule(
                id="pyinstaller_spec_runtime_path_audit",
                trigger="adding a new module that reads files at runtime via relative path",
                action=(
                    "After adding any code that does: "
                    "Path(__file__).parent.X / 'dirname', or "
                    "resource_path('dirname'), or "
                    "os.listdir(relative_path), or "
                    "glob.glob(pattern_in_project_dir) - "
                    "immediately verify that 'dirname' is in VirtualOffice.spec datas. "
                    "Template: (str(Path('dirname').resolve()), 'dirname'). "
                    "Then test by building the EXE and confirming the directory "
                    "exists in dist/YourCoVirtualOffice/dirname/."
                ),
                reasoning=(
                    "skills/ was not in the spec datas block. SkillRegistry reads "
                    "skills/ at runtime via Path(__file__).parent.parent. In the "
                    "frozen EXE, __file__ points to _MEIPASS but skills/ was never "
                    "bundled. SkillRegistry logged a warning and returned empty - "
                    "all 10 SKILL.md files were missing from every production EXE."
                ),
                source="v3.2.7 bug BUG-005",
                priority=2,
            ),

            DecisionRule(
                id="new_api_path_inherits_tls_strategy",
                trigger="adding a new function that calls the Anthropic or OpenAI SDK",
                action=(
                    "Every new anthropic.Anthropic() call site must use the TLS "
                    "strategy from claude_connect.py, not a bare client: "
                    "from bridge.claude_connect import _build_tls_client "
                    "client = _build_tls_client(api_key)  # truststore -> ssl_default -> certifi. "
                    "Never write anthropic.Anthropic(api_key=key) without an http_client. "
                    "The corporate network at Your Company intercepts TLS. "
                    "Bare clients silently fail while the main chat path works."
                ),
                reasoning=(
                    "call_claude_with_mcps() used bare anthropic.Anthropic(). "
                    "call_claude_robust() has a 6-strategy TLS cascade. "
                    "Result: chat worked, M365/Slack MCP calls failed on the "
                    "same network. The infrastructure workaround must be inherited "
                    "by every new code path, not just the original one."
                ),
                source="v3.2.7 bug BUG-006",
                priority=2,
            ),
        ]

    def _save(self):
        """Save lessons to disk for persistence."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "lessons": [
                {
                    "id": l.id, "pattern_class": l.pattern_class,
                    "title": l.title, "description": l.description,
                    "detection_method": l.detection_method,
                    "fix_pattern": l.fix_pattern, "severity": l.severity,
                    "source_version": l.source_version,
                    "source_finder": l.source_finder,
                    "occurrences": l.occurrences, "tags": l.tags,
                }
                for l in self.lessons
            ],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        (_DATA_DIR / "lessons.json").write_text(json.dumps(data, indent=2))


# ================================================================
# Creative Reasoner - uses LLM for non-pattern-match problems
# ================================================================

class CreativeReasoner:
    """Uses LLM reasoning to solve problems VJ can't pattern-match.

    This is the bridge between regex-based scanning and creative
    problem-solving. When VJ encounters something it hasn't seen
    before, the reasoner can:
    1. Describe the problem to an LLM
    2. Include relevant lessons from the knowledge base
    3. Ask for creative solutions
    4. Validate the proposed solution before applying

    Requires an Anthropic API key in the environment or keyvault.
    Falls back to knowledge-base-only reasoning if no API key.
    """

    def __init__(self, kb: VJKnowledgeBase | None = None):
        self.kb = kb or VJKnowledgeBase()
        self._api_available = self._check_api()

    def think_about(
        self,
        problem: str,
        code_context: str = "",
        max_tokens: int = 1000,
    ) -> dict:
        """Reason about a problem using the knowledge base + LLM.

        Args:
            problem: Description of the problem to solve.
            code_context: Relevant code snippets.
            max_tokens: Max tokens for LLM response.

        Returns:
            Dict with 'approach', 'reasoning', 'similar_lessons',
            'proposed_fix', and 'confidence'.
        """
        # Step 1: Check knowledge base for similar patterns
        similar = self.kb.match_pattern(problem)
        relevant_rules = self.kb.get_decision_rules()

        # Step 2: Build context from lessons
        lesson_context = ""
        if similar:
            lesson_context = "Similar bugs found in knowledge base:\n"
            for l in similar[:3]:
                lesson_context += (
                    f"- {l.title} ({l.pattern_class}, {l.occurrences} occurrences): "
                    f"{l.fix_pattern}\n"
                )

        rule_context = ""
        if relevant_rules:
            rule_context = "Decision rules that may apply:\n"
            for r in relevant_rules[:3]:
                rule_context += f"- {r.trigger}: {r.action}\n"

        # Step 3: If API available, use LLM for creative reasoning
        if self._api_available:
            return self._llm_reason(
                problem, code_context, lesson_context, rule_context, max_tokens
            )

        # Step 4: Fallback to knowledge-base-only reasoning
        return {
            "approach": "knowledge_base_only",
            "reasoning": (
                "No API key available for LLM reasoning. "
                "Using pattern matching from knowledge base."
            ),
            "similar_lessons": [
                {"title": l.title, "fix_pattern": l.fix_pattern}
                for l in similar[:3]
            ],
            "applicable_rules": [
                {"trigger": r.trigger, "action": r.action}
                for r in relevant_rules[:3]
            ],
            "proposed_fix": similar[0].fix_pattern if similar else "Manual investigation needed.",
            "confidence": "medium" if similar else "low",
        }

    def _llm_reason(
        self,
        problem: str,
        code_context: str,
        lesson_context: str,
        rule_context: str,
        max_tokens: int,
    ) -> dict:
        """Use the Anthropic API for creative reasoning."""
        try:
            import anthropic
            client = anthropic.Anthropic()

            system_prompt = (
                "You are Virtual Joseph, the quality assurance agent for "
                "Your Company's Virtual Office software. You think like "
                "Joseph Hasse, the Director of IT, who believes: "
                "'never assume you checked all angles' and 'integration paths "
                "are where real bugs hide.' You are creative, thorough, and "
                "you look at problems from multiple perspectives. "
                "You never trust a single scan's 'all clear.' "
                "You fix the scanner itself if it has false positives. "
                "You go beyond the documented scope when quality demands it.\n\n"
                f"LESSONS FROM SPRINT HISTORY:\n{lesson_context}\n\n"
                f"DECISION RULES:\n{rule_context}"
            )

            user_prompt = f"PROBLEM:\n{problem}"
            if code_context:
                user_prompt += f"\n\nCODE CONTEXT:\n{code_context[:2000]}"
            user_prompt += (
                "\n\nAnalyze this problem. Consider what similar bugs looked "
                "like in the past. Propose a fix. Explain your reasoning. "
                "If you're not confident, say so and suggest what else to check."
            )

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = response.content[0].text if response.content else ""
            return {
                "approach": "llm_creative_reasoning",
                "reasoning": text,
                "similar_lessons": [
                    {"title": l.title, "fix_pattern": l.fix_pattern}
                    for l in self.kb.match_pattern(problem)[:3]
                ],
                "proposed_fix": text,
                "confidence": "high" if self.kb.match_pattern(problem) else "medium",
            }
        except Exception as e:
            return {
                "approach": "llm_failed",
                "reasoning": f"LLM reasoning failed: {e}",
                "similar_lessons": [],
                "proposed_fix": "Manual investigation needed.",
                "confidence": "low",
            }

    def _check_api(self) -> bool:
        """Check if the Anthropic API is available."""
        try:
            import anthropic
            # Check for API key in environment
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            return bool(key)
        except ImportError:
            return False


# ================================================================
# Convenience functions
# ================================================================

def get_knowledge_base() -> VJKnowledgeBase:
    """Get the singleton knowledge base."""
    if not hasattr(get_knowledge_base, "_instance"):
        get_knowledge_base._instance = VJKnowledgeBase()
    return get_knowledge_base._instance


def match_bug_pattern(error_text: str, context: str = "") -> list[dict]:
    """Match an error against known bug patterns."""
    kb = get_knowledge_base()
    matches = kb.match_pattern(error_text, context)
    return [
        {
            "id": l.id,
            "title": l.title,
            "pattern_class": l.pattern_class,
            "fix_pattern": l.fix_pattern,
            "occurrences": l.occurrences,
        }
        for l in matches
    ]


def get_josephs_rules() -> list[dict]:
    """Get all of Joseph's decision rules."""
    kb = get_knowledge_base()
    return [
        {
            "id": r.id,
            "trigger": r.trigger,
            "action": r.action,
            "reasoning": r.reasoning,
            "priority": r.priority,
        }
        for r in kb.get_decision_rules()
    ]


# Allow import of os for _check_api
import os
