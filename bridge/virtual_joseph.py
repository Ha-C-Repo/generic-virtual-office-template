"""Virtual Joseph - Quality Assurance Agent for Your Company Virtual Office.

This module acts as a persistent quality gate between user requests and
system responses. It enforces the lesson learned across v3.5.x through
v6.1.2: no single perspective catches every bug. Integration paths,
AI bias, and silent failures require adversarial validation at every
response cycle.

The agent:
  1. Validates responses before delivery (catches wrong, broken, empty)
  2. Detects AI-model bias in output (Gemini/Copilot/ChatGPT patterns)
  3. Catalogs user corrections as permanent rules
  4. Checks cross-module integration paths for silent failures
  5. Enforces Your Company voice rules and governance at the response level

Usage:
    from bridge.virtual_joseph import VirtualJoseph

    vj = VirtualJoseph()

    # Before returning any response to Owner:
    verdict = vj.validate_response(request, response)
    if not verdict.ok:
        response = vj.fix_response(request, response, verdict)

    # When Owner corrects something:
    vj.catalog_correction(original, correction, context)

    # Periodic health check:
    report = vj.run_sweep()
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("virtual_joseph")

# ---- Data directory for persistent corrections ----
_DATA_DIR = Path(__file__).parent.parent / "data" / "virtual_joseph"
_CORRECTIONS_FILE = _DATA_DIR / "corrections.json"
_BIAS_LOG_FILE = _DATA_DIR / "bias_detections.json"
_SWEEP_LOG_FILE = _DATA_DIR / "sweep_history.json"


# ---- Result types ----

@dataclass
class ValidationVerdict:
    """Result of validating a response before delivery."""
    ok: bool
    issues: list[str] = field(default_factory=list)
    bias_detected: list[str] = field(default_factory=list)
    voice_violations: list[str] = field(default_factory=list)
    empty_response: bool = False
    broken_data: bool = False
    governance_violations: list[str] = field(default_factory=list)
    corrections_applied: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CorrectionRecord:
    """A user correction cataloged as a permanent rule."""
    original: str
    correction: str
    context: str
    rule_type: str  # "fact", "voice", "behavior", "data"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    applied_count: int = 0


@dataclass
class SweepReport:
    """Result of a periodic quality sweep."""
    modules_checked: int = 0
    issues_found: list[str] = field(default_factory=list)
    integration_paths_tested: int = 0
    bias_patterns_checked: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---- Dependency Registry ----
# When VJ detects a missing dependency, it returns step-by-step install
# instructions with hyperlinks instead of a raw error message.
# Key = importable module name. Values = install info.

DEPENDENCY_REGISTRY: dict[str, dict] = {
    "webview": {
        "package": "pywebview", "pip": "pip install pywebview>=5.0.0",
        "url": "https://pywebview.flowrl.com/",
        "notes": "Desktop GUI framework. Requires WebView2 runtime on Windows.",
        "platform_notes": {
            "win32": "WebView2 runtime: https://developer.microsoft.com/en-us/microsoft-edge/webview2/",
            "linux": "sudo apt install python3-gi gir1.2-webkit2-4.1",
        },
    },
    "anthropic": {
        "package": "anthropic", "pip": "pip install anthropic>=0.50.0",
        "url": "https://docs.anthropic.com/en/docs/initial-setup",
        "notes": "Claude API SDK. Requires ANTHROPIC_API_KEY env var.",
        "env_vars": ["ANTHROPIC_API_KEY"],
    },
    "openai": {
        "package": "openai", "pip": "pip install openai>=1.30.0",
        "url": "https://platform.openai.com/docs/quickstart",
        "notes": "OpenAI SDK. Requires OPENAI_API_KEY env var.",
        "env_vars": ["OPENAI_API_KEY"],
    },
    "google.genai": {
        "package": "google-genai", "pip": "pip install google-genai>=2.0.0",
        "url": "https://ai.google.dev/gemini-api/docs/quickstart",
        "notes": "Gemini SDK (current). Do NOT install google-generativeai (deprecated).",
        "env_vars": ["GOOGLE_API_KEY"],
    },
    "pymupdf4llm": {
        "package": "pymupdf4llm", "pip": "pip install pymupdf4llm>=1.27.0",
        "url": "https://github.com/pymupdf/pymupdf4llm",
        "notes": "Layout-aware PDF extraction. Auto-installs PyMuPDF.",
    },
    "fitz": {
        "package": "PyMuPDF", "pip": "pip install PyMuPDF>=1.24.0",
        "url": "https://pymupdf.readthedocs.io/",
        "notes": "PDF rendering engine. Installed by pymupdf4llm automatically.",
    },
    "pdfplumber": {
        "package": "pdfplumber", "pip": "pip install pdfplumber>=0.11.0",
        "url": "https://github.com/jsvine/pdfplumber",
        "notes": "Backup PDF table/text extraction.",
    },
    "reportlab": {
        "package": "reportlab", "pip": "pip install reportlab>=4.0",
        "url": "https://docs.reportlab.com/",
        "notes": "PDF generation for bid proposals and change orders.",
    },
    "numpy": {
        "package": "numpy", "pip": "pip install numpy>=1.26.0",
        "url": "https://numpy.org/install/",
        "notes": "Required for geometry calculations and AISC weight math.",
    },
    "pandas": {
        "package": "pandas", "pip": "pip install pandas>=2.2.0",
        "url": "https://pandas.pydata.org/getting_started.html",
        "notes": "Dataframe operations for AISC CSV, takeoff analysis, bid history.",
    },
    "trimesh": {
        "package": "trimesh", "pip": "pip install trimesh>=4.0.0",
        "url": "https://trimesh.org/",
        "notes": "3D wireframe for takeoff validation.",
    },
    "stl": {
        "package": "numpy-stl", "pip": "pip install numpy-stl>=3.1.0",
        "url": "https://github.com/WoLpH/numpy-stl",
        "notes": "STL 3D model generation from AISC shape data.",
    },
    "ezdxf": {
        "package": "ezdxf", "pip": "pip install ezdxf>=1.3.0",
        "url": "https://ezdxf.mozman.at/",
        "notes": "DXF file generation for AutoCAD and CNC machines.",
    },
    "httpx": {
        "package": "httpx", "pip": "pip install httpx>=0.27.0",
        "url": "https://www.python-httpx.org/",
        "notes": "HTTP client. Required by Anthropic SDK.",
    },
    "flask": {
        "package": "flask", "pip": "pip install flask>=3.0.0",
        "url": "https://flask.palletsprojects.com/",
        "notes": "Webhook HTTP server.",
    },
    "psutil": {
        "package": "psutil", "pip": "pip install psutil>=5.9",
        "url": "https://github.com/giampaolo/psutil",
        "notes": "System resource monitoring.",
    },
    "fredapi": {
        "package": "fredapi", "pip": "pip install fredapi>=0.5.0",
        "url": "https://github.com/mortada/fredapi",
        "notes": "FRED API for live steel PPI data.",
        "env_vars": ["FRED_API_KEY"],
    },
    "twilio": {
        "package": "twilio", "pip": "pip install twilio>=8.0.0",
        "url": "https://www.twilio.com/docs/libraries/python",
        "notes": "SMS command channel.",
        "env_vars": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
    },
    "win32com": {
        "package": "pywin32", "pip": "pip install pywin32>=306",
        "url": "https://github.com/mhammond/pywin32",
        "notes": "Windows COM automation for Outlook bid scanner. Windows only.",
    },
    "pytest": {
        "package": "pytest", "pip": "pip install pytest>=8.0 pytest-mock>=3.0",
        "url": "https://docs.pytest.org/",
        "notes": "Test runner. Install from requirements-dev.txt.",
        "dev_only": True,  # pass 10i (R6): not required for the Owner's daily use
    },
    "PyInstaller": {
        "package": "pyinstaller", "pip": "pip install pyinstaller>=6.0",
        "url": "https://pyinstaller.org/",
        "notes": "EXE builder for Windows distribution.",
        "dev_only": True,  # pass 10i (R6): not required for the Owner's daily use
    },
    "tesseract": {
        "package": "tesseract-ocr", "pip": None,
        "url": "https://github.com/tesseract-ocr/tesseract",
        "notes": "OCR engine for scanned PDFs. System package, not pip.",
        "platform_notes": {
            "win32": "Download installer: https://github.com/UB-Mannheim/tesseract/wiki",
            "linux": "sudo apt install tesseract-ocr",
            "darwin": "brew install tesseract",
        },
    },
    "python": {
        "package": "Python", "pip": None,
        "url": "https://www.python.org/downloads/",
        "notes": "Python 3.10+ required. 3.12 recommended.",
        "platform_notes": {
            "win32": "Download: https://www.python.org/downloads/windows/",
            "linux": "sudo apt install python3 python3-pip python3-venv",
            "darwin": "brew install python@3.12",
        },
    },
}


def _resolve_dependency(error_text: str) -> Optional[dict]:
    """Parse an error and return install instructions if a known dep is missing."""
    import sys as _sys

    module_name = None
    for pat in [
        r"No module named ['\"]([^'\"]+)['\"]",
        r"ModuleNotFoundError: No module named ['\"]?([^'\";\s]+)",
        r"ImportError: cannot import name .+ from ['\"]([^'\"]+)['\"]",
        r"ImportError: DLL load failed",
        r"command ['\"]?(\w+)['\"]? not found",
    ]:
        m = re.search(pat, error_text)
        if m and m.lastindex:
            module_name = m.group(1)
            break

    if not module_name:
        return None

    # Lookup: try exact, then root of dotted path
    dep = DEPENDENCY_REGISTRY.get(module_name)
    if not dep and "." in module_name:
        dep = DEPENDENCY_REGISTRY.get(module_name.split(".")[0])
    if not dep:
        for key, val in DEPENDENCY_REGISTRY.items():
            if module_name.lower() in key.lower() or module_name.lower() in val.get("package", "").lower():
                dep = val
                break
    if not dep:
        return None

    platform = _sys.platform
    steps = []
    urls = [dep["url"]] if dep.get("url") else []

    if dep.get("pip"):
        steps.append(f"Run: {dep['pip']}")
    pn = dep.get("platform_notes", {})
    if platform in pn:
        steps.append(f"({platform}): {pn[platform]}")
    elif pn:
        for plat, note in pn.items():
            steps.append(f"({plat}): {note}")
    for ev in dep.get("env_vars", []):
        steps.append(f"Set env var: {ev}")

    return {
        "package": dep.get("package", module_name),
        "steps": steps,
        "urls": urls,
        "notes": dep.get("notes", ""),
        "module": module_name,
    }


# ---- AI Bias Detection Patterns ----
# These patterns indicate output that mirrors another AI model's style
# rather than Your Company's own voice. Updated as new patterns are observed.

AI_BIAS_PATTERNS = {
    # Em-dash is the primary signal (voice rule)
    "em_dash": {
        "pattern": r"\u2014",
        "description": "Em-dash detected (AI signal, voice rule violation)",
        "severity": "high",
    },
    # Three-adjective lists ("innovative, scalable, and robust")
    "triple_adjective": {
        "pattern": r"\b\w+,\s+\w+,\s+and\s+\w+\b",
        "description": "Three-adjective list (generic AI pattern)",
        "severity": "medium",
        "exceptions": ["fabrication, erection, and engineering"],
    },
    # "It's not just X, it's Y" construction
    "not_just_its": {
        "pattern": r"(?i)it'?s not just .{3,40}, it'?s",
        "description": "'Not just X, it's Y' construction (AI filler)",
        "severity": "medium",
    },
    # "Great question!" opener
    "great_question": {
        "pattern": r"(?i)^(great|excellent|good|wonderful)\s+(question|point|observation)",
        "description": "Sycophantic opener (AI pattern)",
        "severity": "medium",
    },
    # "Leverage" / "synergy" / "utilize" (corporate AI filler)
    "corporate_filler": {
        "pattern": r"(?i)\b(leverage|synergy|synergies|utilize|utilizing|leveraging|holistic|paradigm)\b",
        "description": "Corporate filler word (AI pattern)",
        "severity": "low",
    },
    # Markdown headers in conversational responses
    "excessive_markdown": {
        "pattern": r"(#{1,3}\s+\w+.*\n){3,}",
        "description": "Excessive markdown headers in conversational response",
        "severity": "low",
    },
    # "As an AI" or "as a language model" self-reference
    "ai_self_reference": {
        "pattern": r"(?i)\b(as an ai|as a language model|as an artificial|i'?m just an? ai)\b",
        "description": "AI self-reference (breaks immersion)",
        "severity": "high",
    },
    # Copilot-style numbered lists where prose would work
    "unnecessary_numbered_list": {
        "pattern": r"(?m)^1\.\s+.+\n2\.\s+.+\n3\.\s+.+\n4\.\s+.+\n5\.\s+",
        "description": "Long numbered list where prose would be clearer",
        "severity": "low",
    },
    # Gemini-style bold+bullet formatting
    "gemini_bold_bullets": {
        "pattern": r"(\*\*[^*]+\*\*:\s*\n\s*[-*]\s+){2,}",
        "description": "Bold-header + bullet-list pattern (Gemini style)",
        "severity": "low",
    },
    # Dismissing contextualized multi-AI input (v6.1.2 correction)
    # When a user strategically uses another AI with project context,
    # its output should be evaluated on merit, not dismissed.
    "dismiss_ai_input": {
        "pattern": r"(?i)(gemini|gpt|copilot|openai).{0,40}(same thing|redundant|scope creep|deflect|hype|not useful|already (have|built|exists))",
        "description": "Dismissing another AI's contextualized contribution without evaluating on merit",
        "severity": "high",
    },
}

# ---- Response Validation Rules ----
# Rules that check whether a response is correct, complete, and safe.

RESPONSE_RULES = {
    "no_empty_response": {
        "check": lambda r: bool(r and str(r).strip()),
        "description": "Response must not be empty",
        "severity": "critical",
    },
    "no_porsche_plano": {
        "check": lambda r: "porsche of plano" not in str(r).lower(),
        "description": "[FORBIDDEN PROJECT] is NOT a Your Company project",
        "severity": "critical",
    },
    "no_red_dot": {
        "check": lambda r: "red dot" not in str(r).lower() or "red dot buildings" not in str(r).lower(),
        "description": "No Red Dot Buildings or PEMB language",
        "severity": "critical",
    },
    "no_supplier_names": {
        "check": lambda r: not re.search(
            r"(?i)\b(nucor|steel technologies|metals usa|service center|russel metals)\b",
            str(r)
        ),
        "description": "No supplier names in client-facing output",
        "severity": "high",
    },
    "no_engineering_line_item": {
        "check": lambda r: not re.search(
            r"(?i)engineering\s*[:\-]\s*\$[\d,]+",
            str(r)
        ),
        "description": "Engineering costs folded into rates, never line-itemed",
        "severity": "high",
    },
    "no_lady_law": {
        "check": lambda r: "lady law" not in str(r).lower(),
        "description": "Lady Law is not part of Your Company operations",
        "severity": "high",
    },
    "correct_address": {
        "check": lambda r: (
            "8630 fairbanks" in str(r).lower()
            if any(w in str(r).lower() for w in ["address", "located", "location", "office"])
            else True
        ),
        "description": "Address must be [COMPANY ADDRESS]",
        "severity": "medium",
    },
    "correct_shop_rate": {
        "check": lambda r: (
            "$145" in str(r) or "145/hr" in str(r) or "145 per hour" in str(r).lower()
            if re.search(r"(?i)shop\s*rate", str(r))
            else True
        ),
        "description": "Shop rate must be $145/hr",
        "severity": "medium",
    },
    "math_firewall": {
        "check": lambda r: not re.search(
            r"\b\d{1,3}(?:,\d{3})*\.\d{3,}\b",  # suspicious precision
            str(r)
        ),
        "description": "Math results should come from calculators, not LLM arithmetic",
        "severity": "medium",
    },
}


class VirtualJoseph:
    """Quality assurance agent that validates every response before delivery.

    Named after Joseph Hasse, Director of I.T., who caught 26 bugs in
    code that had already passed 1,201 tests. The lesson: no single
    perspective catches every issue. This agent encodes that discipline
    into the runtime.
    """

    def __init__(self):
        self._corrections: list[CorrectionRecord] = []
        self._bias_log: list[dict] = []
        self._load_corrections()

    # ---- Core validation ----

    def validate_response(
        self,
        request: str,
        response: Any,
        context: str = "general",
    ) -> ValidationVerdict:
        """Validate a response before delivering it to the user.

        Args:
            request: The user's original request text.
            response: The system's proposed response (str, dict, or any).
            context: "bid", "email", "general", "compliance", etc.

        Returns:
            ValidationVerdict with ok=True if response is safe to deliver.
        """
        verdict = ValidationVerdict(ok=True)
        response_str = str(response) if response is not None else ""

        # Check for empty response
        if not response_str.strip():
            verdict.ok = False
            verdict.empty_response = True
            verdict.issues.append("Empty response. System returned nothing.")
            return verdict

        # Check for broken data (error responses that shouldn't reach user)
        if isinstance(response, dict):
            if response.get("ok") is False and response.get("error"):
                err = response["error"]
                # Some errors are informational (expected). Others are bugs.
                bug_signals = [
                    "ImportError", "AttributeError", "TypeError",
                    "KeyError", "ModuleNotFoundError", "NameError",
                    "not defined", "has no attribute",
                    "NoneType", "object is not callable",
                    "not found", "not installed",
                    "No module named", "No such file or directory",
                    "DLL load failed",
                ]
                if any(sig in str(err) for sig in bug_signals):
                    verdict.ok = False
                    verdict.broken_data = True
                    verdict.issues.append(
                        f"Bug detected in response: {str(err)[:200]}"
                    )

        # Run response rules
        for rule_name, rule in RESPONSE_RULES.items():
            try:
                if not rule["check"](response_str):
                    verdict.ok = verdict.ok and rule["severity"] != "critical"
                    verdict.governance_violations.append(
                        f"[{rule['severity']}] {rule['description']}"
                    )
            except Exception:
                pass  # Rule itself errored; skip

        # Run AI bias checks
        for pattern_name, pattern_def in AI_BIAS_PATTERNS.items():
            try:
                matches = re.findall(pattern_def["pattern"], response_str)
                if matches:
                    # Check exceptions
                    exceptions = pattern_def.get("exceptions", [])
                    real_matches = [
                        m for m in matches
                        if not any(exc in str(m).lower() for exc in exceptions)
                    ]
                    if real_matches:
                        verdict.bias_detected.append(
                            f"[{pattern_def['severity']}] "
                            f"{pattern_def['description']} "
                            f"({len(real_matches)} instance{'s' if len(real_matches) > 1 else ''})"
                        )
            except Exception:
                pass

        # Apply stored corrections
        for correction in self._corrections:
            if correction.original.lower() in response_str.lower():
                verdict.corrections_applied.append(
                    f"Stored correction applies: "
                    f"'{correction.original}' -> '{correction.correction}' "
                    f"(from {correction.context})"
                )

        # If bias detected at high severity, flag but don't block
        if any("[high]" in b for b in verdict.bias_detected):
            verdict.voice_violations.extend(
                [b for b in verdict.bias_detected if "[high]" in b]
            )

        return verdict

    # ---- Correction cataloging ----

    def catalog_correction(
        self,
        original: str,
        correction: str,
        context: str = "",
        rule_type: str = "fact",
    ) -> CorrectionRecord:
        """Catalog a user correction as a permanent rule.

        When Owner corrects something, this stores it so the same
        mistake is never repeated.

        Args:
            original: What was wrong.
            correction: What it should be.
            context: Where/when the correction happened.
            rule_type: "fact", "voice", "behavior", or "data".

        Returns:
            The stored CorrectionRecord.
        """
        record = CorrectionRecord(
            original=original,
            correction=correction,
            context=context,
            rule_type=rule_type,
        )
        self._corrections.append(record)
        self._save_corrections()
        log.info(
            "Correction cataloged: '%s' -> '%s' (%s)",
            original, correction, rule_type,
        )
        return record

    def get_corrections(self, rule_type: str = "") -> list[CorrectionRecord]:
        """Get all stored corrections, optionally filtered by type."""
        if rule_type:
            return [c for c in self._corrections if c.rule_type == rule_type]
        return list(self._corrections)

    # ---- Fix response ----

    def fix_response(
        self,
        request: str,
        response: Any,
        verdict: ValidationVerdict,
    ) -> dict:
        """Attempt to fix a broken response before delivery.

        If the response has governance violations, applies corrections.
        If the response is broken (ImportError, etc.), returns a clear
        error message instead of the broken output.
        If the response is empty, returns a structured error.

        Args:
            request: Original user request.
            response: The broken response.
            verdict: The validation verdict explaining what's wrong.

        Returns:
            A fixed response dict or a clear error dict.
        """
        if verdict.empty_response:
            return {
                "ok": False,
                "error": "System returned empty response. Retrying with different approach.",
                "virtual_joseph": "intercepted_empty",
                "original_request": request[:200],
            }

        if verdict.broken_data:
            # Check if this is a missing dependency we can help with
            error_text = " ".join(verdict.issues)
            dep_info = _resolve_dependency(error_text)
            if dep_info:
                steps_text = "\n".join(
                    f"  Step {i+1}. {s}" for i, s in enumerate(dep_info["steps"])
                )
                urls_text = "\n".join(
                    f"  - {u}" for u in dep_info["urls"]
                )
                return {
                    "ok": False,
                    "error": f"Missing dependency: {dep_info['package']}",
                    "virtual_joseph": "install_guide",
                    "package": dep_info["package"],
                    "module": dep_info["module"],
                    "install_steps": dep_info["steps"],
                    "download_urls": dep_info["urls"],
                    "notes": dep_info["notes"],
                    "message": (
                        f"'{dep_info['package']}' is not installed.\n\n"
                        f"To fix this:\n{steps_text}\n\n"
                        f"Documentation:\n{urls_text}\n\n"
                        f"{dep_info['notes']}"
                    ),
                }
            return {
                "ok": False,
                "error": "System hit an internal bug. Virtual Joseph intercepted before delivery.",
                "virtual_joseph": "intercepted_bug",
                "issues": verdict.issues,
                "action": "Retry with corrected integration path.",
            }

        # For governance violations, clean the response
        if verdict.governance_violations:
            cleaned = str(response)
            for correction in self._corrections:
                cleaned = re.sub(
                    re.escape(correction.original),
                    correction.correction,
                    cleaned,
                    flags=re.IGNORECASE,
                )
            return {
                "ok": True,
                "data": cleaned,
                "virtual_joseph": "governance_cleaned",
                "violations_fixed": verdict.governance_violations,
            }

        return {"ok": True, "data": response, "virtual_joseph": "passed"}

    # ---- Bias detection ----

    def check_bias(self, text: str) -> list[dict]:
        """Check text for AI-model bias patterns.

        Returns a list of detected bias patterns with severity and
        description. Use this before sending any LLM-generated content
        to Owner.
        """
        detections = []
        for name, pdef in AI_BIAS_PATTERNS.items():
            matches = re.findall(pdef["pattern"], text)
            if matches:
                exceptions = pdef.get("exceptions", [])
                real = [
                    m for m in matches
                    if not any(exc in str(m).lower() for exc in exceptions)
                ]
                if real:
                    detections.append({
                        "pattern": name,
                        "severity": pdef["severity"],
                        "description": pdef["description"],
                        "count": len(real),
                        "samples": [str(m)[:50] for m in real[:3]],
                    })
        return detections

    # ---- Integration sweep ----

    def run_sweep(self) -> SweepReport:
        """Run a quick integration sweep across critical modules.

        Tests the same cross-phase paths that caught 26 bugs in the
        v6.1.2 debug session. Any failure means a real bug, not a
        test artifact.
        """
        report = SweepReport()
        issues = []

        # Calculator chain
        try:
            from bridge.calculators import steel_weight, hours_estimate, labor_cost
            wt = steel_weight([("W14X82", 20, 1)])
            if wt["total_lbs"] != 1640:
                issues.append(f"Calculator: W14X82 weight wrong ({wt['total_lbs']} != 1640)")
            hrs = hours_estimate(wt["tons"])
            if hrs["total_hours"] <= 0:
                issues.append("Calculator: hours_estimate returned 0")
            lc = labor_cost(hrs["fab_hours"], hrs["erect_hours"])
            if lc["total_labor"] <= 0:
                issues.append("Calculator: labor_cost returned 0")
            report.integration_paths_tested += 3
        except Exception as e:
            issues.append(f"Calculator chain: {e}")

        # AISC validator
        try:
            from bridge.aisc_validator import validate_shape
            v = validate_shape("W14X82")
            if not v["valid"]:
                issues.append("AISC: W14X82 not valid")
            v2 = validate_shape("W14X81")
            if v2["valid"]:
                issues.append("AISC: W14X81 should be invalid")
            report.integration_paths_tested += 2
        except Exception as e:
            issues.append(f"AISC validator: {e}")

        # Governance
        try:
            from bridge.governance import check_compliance
            if not check_compliance("[FORBIDDEN PROJECT]"):
                issues.append("Governance: [FORBIDDEN PROJECT] not caught")
            if check_compliance("standard fabrication"):
                issues.append("Governance: clean text flagged")
            report.integration_paths_tested += 2
        except Exception as e:
            issues.append(f"Governance: {e}")

        # Intent routing
        try:
            from bridge.intent_router import classify_intent
            r = classify_intent("bid this project")
            if r.intent != "full_bid_pipeline":
                issues.append(f"Intent: 'bid this project' routed to {r.intent}")
            report.integration_paths_tested += 1
        except Exception as e:
            issues.append(f"Intent router: {e}")

        # STL generation
        try:
            from bridge.stl_generator import generate_stl
            r = generate_stl("W14X82", 20)
            if r.get("path") is None:
                issues.append("STL: W14X82 generation failed")
            report.integration_paths_tested += 1
        except Exception as e:
            issues.append(f"STL generator: {e}")

        # Voice rule (em-dashes in protected files)
        try:
            protected = [
                "bridge/api.py", "bridge/prompts.py",
                "frontend/index.html", "frontend/app.js",
                "frontend/styles.css", "mcp_server.py",
            ]
            base = Path(__file__).parent.parent
            for fp in protected:
                full = base / fp
                if full.exists():
                    content = full.read_text(encoding="utf-8", errors="replace")
                    count = content.count("\u2014")
                    if count > 0:
                        issues.append(f"Voice: {fp} has {count} em-dashes")
            report.integration_paths_tested += len(protected)
        except Exception as e:
            issues.append(f"Voice rule check: {e}")

        # Bias pattern check count
        report.bias_patterns_checked = len(AI_BIAS_PATTERNS)
        report.modules_checked = 6
        report.issues_found = issues

        return report

    # ---- Persistence ----

    def _load_corrections(self):
        """Load stored corrections from disk."""
        if _CORRECTIONS_FILE.exists():
            try:
                data = json.loads(_CORRECTIONS_FILE.read_text())
                self._corrections = [
                    CorrectionRecord(**c) for c in data
                ]
            except Exception:
                self._corrections = []
        else:
            self._corrections = []
            # Seed with known corrections from sprint history
            self._seed_corrections()

    def _seed_corrections(self):
        """Seed corrections from known sprint history."""
        seeds = [
            CorrectionRecord(
                original="[FORBIDDEN PROJECT]",
                correction="[BLOCKED: not a Your Company project]",
                context="Governance rule from project inception",
                rule_type="fact",
            ),
            CorrectionRecord(
                original="10+ years",
                correction="9+ years (Est. 2017)",
                context="Calculator tool stat correction, May 2026",
                rule_type="fact",
            ),
            CorrectionRecord(
                original="Red Dot Buildings",
                correction="[BLOCKED: no PEMB language]",
                context="Governance rule from bidding rules",
                rule_type="fact",
            ),
            CorrectionRecord(
                original="joseph@gmail.com",
                correction="joseph@yourcompany.example.com",
                context="Calculator tool email correction",
                rule_type="data",
            ),
        ]
        self._corrections.extend(seeds)

    def _save_corrections(self):
        """Save corrections to disk."""
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "original": c.original,
                "correction": c.correction,
                "context": c.context,
                "rule_type": c.rule_type,
                "timestamp": c.timestamp,
                "applied_count": c.applied_count,
            }
            for c in self._corrections
        ]
        _CORRECTIONS_FILE.write_text(json.dumps(data, indent=2))


# ---- Bridge integration ----

def get_virtual_joseph() -> VirtualJoseph:
    """Get the singleton VirtualJoseph instance."""
    if not hasattr(get_virtual_joseph, "_instance"):
        get_virtual_joseph._instance = VirtualJoseph()
    return get_virtual_joseph._instance


def validate_before_delivery(request: str, response: Any) -> ValidationVerdict:
    """Convenience function: validate a response before delivering it."""
    return get_virtual_joseph().validate_response(request, response)


def catalog_user_correction(original: str, correction: str, context: str = "") -> CorrectionRecord:
    """Convenience function: catalog a user correction."""
    return get_virtual_joseph().catalog_correction(original, correction, context)


def run_quality_sweep() -> SweepReport:
    """Convenience function: run a quick integration sweep."""
    return get_virtual_joseph().run_sweep()
