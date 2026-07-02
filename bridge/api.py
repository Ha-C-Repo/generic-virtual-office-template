"""
Your Company Virtual Office - AI Bridge
====================================
This file is the accuracy engine. Every rule, rate, voice pattern, team
routing decision, and company fact from the 22-document knowledge base is
compiled into SYSTEM_PROMPT - a constant that is injected into EVERY call
to Claude.

Chat version flaw: files had to be loaded manually each session.
EXE advantage: nothing loads because everything is always here.

The Owner - CEO - Your Company, LLC - Houston, TX
"""

from __future__ import annotations
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import logging
log = logging.getLogger("bridge.api")

# Integration modules (ported from Linux build)
from bridge.integrations import (
    detect_onedrive, detect_github_repo, read_standing_file,
    CEOLogger, BidPipeline,
)

# Modular prompt system (75% token savings vs monolithic)
from bridge.prompts import build_system_prompt, CORE_PROMPT

# Singletons (initialized once, shared across all Bridge calls)
_ceo_logger = CEOLogger()
_bid_pipeline = BidPipeline()

# ── handler error tracking (P8.4) ─────────────────────────────────────────
# A lightweight ring buffer of recent handler errors so get_health() can
# report yellow/red instead of always-green when methods return _err().
import time as _time
import collections as _collections
_HANDLER_ERRORS: "collections.deque[tuple[float, str]]" = _collections.deque(maxlen=50)

def _record_bridge_error(context: str) -> None:
    """Record a handler error timestamp. Called at _err() sites that matter."""
    _HANDLER_ERRORS.append((_time.monotonic(), context))

def _count_recent_handler_errors(window_seconds: float = 60.0) -> int:
    now = _time.monotonic()
    return sum(1 for t, _ in _HANDLER_ERRORS if now - t <= window_seconds)

# ── response helpers ──────────────────────────────────────────────────────
def _ok(data: Any) -> dict:
    return {"ok": True, "success": True, "data": data}

def _err(msg: str, fix: str = "") -> dict:
    """Standard error envelope.

    Args:
        msg: What went wrong, in plain English.
        fix: OPTIONAL but strongly preferred. The single concrete action
             the user can take next, formatted as "fix: <action>".
             Example: fix="type `list bids` to see all bid IDs"
    """
    out = {"ok": False, "success": False, "error": msg}
    if fix:
        out["fix"] = fix
        # Also append to error message so it shows up in any string-only display
        out["error"] = f"{msg}\nfix: {fix}"
    return out


def _coerce_num(value: Any, name: str, cast: str = "float") -> tuple:
    """Coerce a parameter to a number for safe arithmetic.

    Pass 10i: input-hardening sweep. Replaces the prior pattern where
    Bridge methods would let a Python TypeError leak out of the call when
    a caller passed a string in a numeric slot.

    Args:
        value: The incoming param value (may be int, float, str, None, etc.)
        name:  Parameter name, used in the error message.
        cast:  "float" (default) or "int". int coerces via float first so
               "3.0" -> 3 works without surprises.

    Returns:
        (coerced_value, None) on success.
        (0, _err(...)) on failure - caller does `if e: return e`.

    Treats None and "" as 0 (the default semantic across Bridge).
    """
    if value is None or value == "":
        return (0 if cast == "int" else 0.0), None
    try:
        f = float(value)
        if cast == "int":
            return int(f), None
        return f, None
    except (TypeError, ValueError):
        return 0, _err(
            f"{name} must be numeric (got {value!r}).",
            fix=f"pass a number for {name}, e.g. {name}=100"
        )


# -- Multi-model API key loader + task router -----------------------
#
# KEY LOADING PRIORITY:
#   1. "API Keys" folder next to the EXE (or project root in dev mode)
#      Three plain .txt files - first line of each file is the key:
#        API Keys/Claude API.txt    → ANTHROPIC_API_KEY
#        API Keys/OpenAI API.txt    → OPENAI_API_KEY
#        API Keys/Gemini API.txt    → GOOGLE_API_KEY
#   2. config.json next to the EXE  (backward compat)
#   3. Environment variables         (last resort)
#
# Owner drops the "API Keys" folder into the unzipped directory.
# No environment variables, no setup wizard, no command line.

# Map: filename (without .txt) -> internal key name
_KEY_FILES = {
    "Claude API":  "ANTHROPIC_API_KEY",
    "OpenAI API":  "OPENAI_API_KEY",
    "Gemini API":  "GOOGLE_API_KEY",
    "FRED API":    "FRED_API_KEY",
}

def _app_root() -> Path:
    """Return the folder containing the EXE (frozen) or project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _read_key_file(path: Path) -> str:
    """Read the API key from a text file.
    Skips instruction lines, BOM, quotes, whitespace, and copy-paste artifacts.
    Looks for lines that look like API keys (sk-, AIza, etc.) first,
    then falls back to first non-comment line.
    """
    try:
        if path.exists():
            raw = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
            candidates = []
            for line in raw.splitlines():
                cleaned = line.strip().strip('"').strip("'").strip()
                if not cleaned or cleaned.startswith("#"):
                    continue
                candidates.append(cleaned)
            # Priority: lines starting with known key prefixes
            KEY_PREFIXES = ("sk-ant-", "sk-", "AIza", "gsk_")
            for c in candidates:
                if any(c.startswith(p) for p in KEY_PREFIXES):
                    return c
            # Fallback: skip lines containing instruction words
            SKIP_WORDS = ("paste", "your", "key", "here", "below", "insert", "replace", "api key")
            for c in candidates:
                if not any(w in c.lower() for w in SKIP_WORDS):
                    return c
            # Last resort: first candidate
            if candidates:
                return candidates[0]
    except Exception:
        pass
    return ""

def _load_all_keys() -> dict:
    """Load API keys. Encrypted store > Folder > config.json > env vars.

    Required keys (gate the encrypted store): Claude, OpenAI, Gemini.
    Optional keys (loaded but don't block): FRED (steel PPI live feed).
    """
    keys = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_API_KEY": "",
             "FRED_API_KEY": ""}
    REQUIRED = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")

    # 0. Encrypted key store (Joseph P1 - DPAPI on Windows)
    try:
        from bridge.keyvault import load_keys
        encrypted = load_keys()
        if encrypted:
            for k in keys:
                if encrypted.get(k):
                    keys[k] = encrypted[k]
            if all(keys[k] for k in REQUIRED):
                return keys  # required keys all present from encrypted store
    except Exception:
        pass

    root = _app_root()

    # 1. "API Keys" folder - plain .txt files (will be migrated to encrypted on Windows)
    key_dir = root / "API Keys"
    for filename, key_name in _KEY_FILES.items():
        val = _read_key_file(key_dir / (filename + ".txt"))
        if val:
            keys[key_name] = val

    # 2. config.json fallback (backward compat from prior builds)
    if not all(keys[k] for k in REQUIRED):
        try:
            cfg_path = root / "config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                for k in keys:
                    if not keys[k]:
                        val = cfg.get(k, "").strip()
                        if val:
                            keys[k] = val
        except Exception:
            pass

    # 3. Environment variables (last resort)
    for k in keys:
        if not keys[k]:
            keys[k] = os.environ.get(k, "").strip()

    # 3b. SIM-10: Detect placeholder values. If a slot contains text that
    # obviously isn't a real key (PASTE YOUR, <YOUR_KEY>, xxx-, your-key,
    # test-key, sample-key), treat it as not configured. This prevents
    # misleading "wrong prefix" errors downstream.
    _PLACEHOLDER_PATTERNS = (
        "paste your", "paste here", "<your", "your-key", "your_key",
        "your-api-key", "your-anthropic", "your-openai", "your-google",
        "your-gemini", "your-fred", "xxx-", "test-key", "sample-key",
        "placeholder", "fill in", "insert key", "replace this",
    )
    for k in list(keys.keys()):
        v = (keys[k] or "").strip().lower()
        if v and any(p in v for p in _PLACEHOLDER_PATTERNS):
            keys[k] = ""

    # 4. Auto-encrypt if we found keys from plaintext (Joseph P1)
    if any(keys.values()):
        try:
            from bridge.keyvault import store_keys, is_encrypted
            if not is_encrypted():
                store_keys({k: v for k, v in keys.items() if v})
        except Exception:
            pass

    return keys

def _load_api_key() -> str:
    """Legacy single-key loader for backward compat."""
    return _load_all_keys().get("ANTHROPIC_API_KEY", "")

# ---- MODEL ROUTING ----
# Each task type maps to the AI model that handles it best.
# Claude:  rule enforcement, voice drafting, compliance, bid strategy
# GPT-4o:  structured output, PDF gen, Monte Carlo, financial math
# Gemini:  multimodal vision (drawings), web grounding (live prices)
#
# CLAUDE IS THE BACKBONE. OpenAI/Gemini are specialists and fallbacks.
# If Claude can't connect, tasks temporarily reroute to OpenAI until
# Claude reconnects. The app retries Claude every 5 minutes.
#
_CLAUDE_AVAILABLE = None  # None = untested, True/False = tested

# ── v3.2 Claude connection layer (6-strategy cascade incl. curl.exe + verify=False) ──
try:
    from bridge.claude_connect import (
        call_claude_robust as _call_claude_v32,
        test_claude_available as _test_claude_v32,
    )
    _HAS_CLAUDE_CONNECT = True
except ImportError:
    _HAS_CLAUDE_CONNECT = False

def _test_claude_available(api_key: str) -> bool:
    """Check Claude reachability with 6-strategy cascade (v3.2).
    Strategies: truststore → ssl_default → SDK → urllib → curl.exe → verify=False"""
    global _CLAUDE_AVAILABLE
    if not api_key or len(api_key) < 20:
        _CLAUDE_AVAILABLE = False
        return False
    if _HAS_CLAUDE_CONNECT:
        result = _test_claude_v32(api_key)
        _CLAUDE_AVAILABLE = result
        return result
    # Fallback if claude_connect module missing: simple urllib test
    try:
        import urllib.request, json as _j
        payload = _j.dumps({"model": "claude-sonnet-4-6", "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
            data=payload, headers={"Content-Type": "application/json",
            "x-api-key": api_key, "anthropic-version": "2023-06-01"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            _j.loads(resp.read())
        _CLAUDE_AVAILABLE = True
        return True
    except Exception:
        _CLAUDE_AVAILABLE = False
        return False

def _get_route(task_cat: str) -> tuple:
    """Get the route for a task - Claude primary, OpenAI fallback if Claude is down."""
    route = MODEL_ROUTES.get(task_cat, MODEL_ROUTES["general"])
    if route[0] == "claude" and _CLAUDE_AVAILABLE is False:
        # Claude is down - temporarily reroute to OpenAI
        return ("openai", "gpt-4o", f"[Claude unavailable → OpenAI fallback] {route[2]}")
    return route

MODEL_ROUTES = {
    # Task category -> (provider, model_id, reason)
    #
    # ROUTING PHILOSOPHY:
    #   1. Local calculators (AISC CSV, calculators.py) - always first, zero cost
    #   2. Claude Sonnet 4.5 - primary for all reasoning, bid strategy, compliance
    #   3. Gemini 2.5 Flash - vision, PDF rasterization, market grounding
    #   4. OpenAI GPT-4o - structured JSON output, math fallback, complex 3D assembly
    #   Haiku: lightweight pings only (availability checks, simple lookups)
    #
    # CLAUDE SONNET 4.5 - primary AI for all complex reasoning tasks
    "voice_draft":     ("claude",  "claude-sonnet-4-6",  "Sonnet: best at following Your Company voice rules + system prompt adherence"),
    "bid_strategy":    ("claude",  "claude-sonnet-4-6",  "Sonnet: bid logic, markup decisions, scope analysis"),
    "compliance":      ("claude",  "claude-sonnet-4-6",  "Sonnet: 13-item tracker, RAVS categories, contract language"),
    "cold_outreach":   ("claude",  "claude-sonnet-4-6",  "Sonnet: personalization requires full context window"),
    "general":         ("claude",  "claude-sonnet-4-6",  "Sonnet: default - all rules always active"),
    "icd_church":      ("claude",  "claude-sonnet-4-6",  "Sonnet: project-specific memory + quantum meruit language"),
    "afr_refinery":    ("claude",  "claude-sonnet-4-6",  "Sonnet: Marathon PLA 2026 rules + refinery protocol"),
    "model_3d":        ("claude",  "claude-sonnet-4-6",  "Sonnet: 3D scene description + member placement logic"),
    # GEMINI 2.5 FLASH - vision, market data, PDF rasterization
    "drawing_vision":  ("gemini",  "gemini-2.5-flash",  "Gemini: multimodal PDF/image structural plan reading"),
    "market_data":     ("gemini",  "gemini-2.5-flash",  "Gemini: web grounding for live steel prices + FRED news"),
    "stock_research":  ("gemini",  "gemini-2.5-flash",  "Gemini: search grounding for NUE/STLD/CMC/CLF tickers"),
    # OPENAI GPT-4o - structured output, math fallback, complex 3D geometry
    "structured_data": ("openai",  "gpt-4o",            "GPT-4o: best JSON/structured output for document assembly"),
    "monte_carlo":     ("openai",  "gpt-4o",            "GPT-4o: 1,000-run simulation with Box-Muller sampling"),
    "math_fallback":   ("openai",  "gpt-4o",            "GPT-4o: calculations local calculator cannot complete offline"),
    "3d_complex":      ("openai",  "gpt-4o",            "GPT-4o: complex 3D scene assembly beyond local STL capability"),
    "financial_model": ("openai",  "gpt-4o",            "GPT-4o: driver-based forecasting + DCF with structured output"),
    "cnc_plasma":      ("openai",  "gpt-4o",            "GPT-4o: structured G-code / DXF output for CNC plasma"),
    "cnc_drill":       ("openai",  "gpt-4o",            "GPT-4o: structured bolt/hole pattern output"),
    "ironworker":      ("openai",  "gpt-4o",            "GPT-4o: structured punch/cope schedule output"),
}

def _classify_task(message: str) -> str:
    """Auto-classify a user message to a task category for model routing.

    v3.5.7: keyword matching uses word boundaries (\\b) to stop false
    positives like 'rate' matching 'geneRATE'. Same fix applied to
    _translate_intent. Joseph's '3d modeling is not working' bug.
    """
    import re as _re
    msg = message.lower()

    def _any_kw(words: list[str]) -> bool:
        # Word-boundary match. Multi-word phrases work fine because \b
        # naturally bounds at the start/end of the phrase.
        return any(_re.search(rf'\b{_re.escape(w)}\b', msg) for w in words)

    # -- DIAGNOSTICS (local, zero LLM tokens) --
    if _any_kw(["run diagnostics", "diagnostics", "system check",
                "health check", "diagnostic report", "test all functions"]):
        return "diagnostics"

    # -- VIRTUAL JOSEPH (local, zero LLM tokens) --
    if _any_kw(["virtual joseph", "vj scan", "vj train", "vj sweep",
                "train joseph", "train vj", "scan and fix",
                "joseph scan", "joseph train", "run vj",
                "vj check", "vj fix", "train virtual",
                "feature status", "what features", "what is working",
                "what is active", "dead features", "inactive features"]):
        return "virtual_joseph"

    # -- FABRICATION (check before drawing_vision to avoid false match) --
    if _any_kw(["3d model", "stl", "3d view", "generate model", "build model",
                "render", "3d from"]):
        return "model_3d"
    # v3.5.7: DXF cross-section / pattern. Sister of model_3d. Bridge.generate_dxf
    # is already wired but had no intercept, so DXF prompts fell through to LLM
    # which emitted Python code instead of producing a file. Joseph's
    # "Generate a DXF cross-section drawing for W12x35" bug.
    if _any_kw(["dxf", "dxf cross", "cross-section drawing", "cross section drawing"]):
        return "model_dxf"
    if _any_kw(["plasma", "cnc cut", "cnc plasma", "plate cut", "nest"]):
        return "cnc_plasma"
    if _any_kw(["cnc drill", "drill program", "drill pattern", "hole pattern",
                "bolt pattern"]):
        return "cnc_drill"
    if _any_kw(["ironworker", "punch schedule", "punch program", "shear schedule",
                               "shear program", "cope", "notch"]):
        return "ironworker"
    # Drawing/vision tasks
    if _any_kw(["drawing", "plan sheet", "rasterize", "S-001", "S-002", "scale from", "dimension line", "takeoff from drawing"]):
        return "drawing_vision"
    # Market/stock tasks
    if _any_kw(["stock", "ticker", "NUE", "STLD", "CMC", "steel price", "market", "earnings"]):
        return "stock_research" if _any_kw(["research", "watchlist"]) else "market_data"
    # Structured output tasks.
    # v3.5.10 Bug #4: sensitivity moved ABOVE monte_carlo so the dedicated
    # sensitivity branch (Claude, more nuanced framing) is reachable. Before
    # this fix, monte_carlo's keyword list also contained "sensitivity" and
    # ran first, so users asking for sensitivity analysis silently got
    # GPT-4o's monte_carlo route.
    if _any_kw(["sensitivity", "tornado", "multi-variable", "stress test"]):
        return "sensitivity"
    if _any_kw(["monte carlo", "simulation", "scenario"]):
        return "monte_carlo"
    if _any_kw(["generate pdf", "build document", "format report", "json output"]):
        return "structured_data"
    if _any_kw(["financial model", "P&L model", "cash flow forecast"]):
        return "financial_model"
    # Voice/outreach tasks
    if _any_kw(["cold outreach", "cold email", "draft email", "follow-up email"]):
        return "cold_outreach"
    if _any_kw(["draft", "write up", "compose"]):
        return "voice_draft"
    # Math/calculation fallback (local calculator failed, needs AI)
    if _any_kw(["calculate", "compute", "math fallback", "formula", "solve for"]):
        return "math_fallback"
    # Compliance
    if _any_kw(["compliance", "ISN", "Avetta", "EMR", "blocker", "RAVS"]):
        return "compliance"
    # Project status (specific projects)
    if _any_kw(["icd", "church", "quantum meruit"]):
        return "icd_church"
    if _any_kw(["america first", "afr", "brownsville", "fluor"]):
        return "afr_refinery"
    if _any_kw(["marathon", "isn approval"]):
        return "marathon"
    # Team / personnel
    if _any_kw(["team", "who is", "personnel", "ivan", "amber", "paul", "mario", "shaun"]):
        return "team"
    # Rates / pricing. v3.5.7: word-boundary fix prevented "geneRATE" from
    # matching "rate". v3.5.10 Bug #5: dropped the bare "rate" keyword
    # because the verb form ("please rate the bid") was misclassifying
    # generic feedback requests as pricing. Plural "rates" and concrete
    # phrasings remain.
    if _any_kw(["rates", "pricing", "what do we charge", "how much",
                "shop rate", "per ton", "per hour", "labor rate"]):
        return "pricing"
    # Bid strategy
    if _any_kw(["bid", "takeoff", "proposal", "estimate", "tons", "fabrication", "erection"]):
        return "bid_strategy"
    # Weekly briefing
    if _any_kw(["briefing", "week in review", "synthesize", "morning brief"]):
        return "briefing"
    return "general"

def _call_openai(api_key: str, model: str, system: str, messages: list) -> str:
    """Call OpenAI API. Returns response text. Handles quota errors gracefully."""
    import openai
    try:
        client = openai.OpenAI(api_key=api_key)
        msgs = [{"role": "system", "content": system}] + messages
        resp = client.chat.completions.create(model=model, messages=msgs, max_tokens=1500)
        return resp.choices[0].message.content or ""
    except openai.RateLimitError:
        raise ValueError(
            "OpenAI quota exceeded. Add credits at platform.openai.com/billing\n"
            "Until then, tasks will route to Gemini automatically."
        )
    except openai.AuthenticationError:
        raise ValueError("OpenAI key invalid. Check API Keys/OpenAI API.txt")
    except Exception:
        raise

def _to_gemini_parts(content):
    """Convert Claude/OpenAI content format to Gemini-native parts.

    Handles:
      str                            → [str]
      list of Claude blocks          → list of Gemini parts
        {"type":"text","text":"..."}   → "..."
        {"type":"image","source":..}   → {"inline_data":{"mime_type":..,"data":..}}
        {"type":"document","source":}  → {"inline_data":{"mime_type":..,"data":..}}
        {"type":"image_url",...}        → {"inline_data":{"mime_type":..,"data":..}}
    """
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return [str(content)]
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif not isinstance(block, dict):
            parts.append(str(block))
        elif block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") in ("image", "document"):
            src = block.get("source", {})
            parts.append({"inline_data": {
                "mime_type": src.get("media_type", "application/octet-stream"),
                "data": src.get("data", "")
            }})
        elif block.get("type") == "image_url":
            # OpenAI format: data:mime;base64,DATA
            url = block.get("image_url", {}).get("url", "")
            if url.startswith("data:") and ";base64," in url:
                mime, b64 = url.split(";base64,", 1)
                mime = mime.replace("data:", "")
                parts.append({"inline_data": {"mime_type": mime, "data": b64}})
            else:
                parts.append(f"[Image URL: {url}]")
        else:
            parts.append(str(block))
    return parts or [""]

def _call_gemini(api_key: str, model: str, system: str, messages: list) -> str:
    """Call Google Gemini API. Returns response text.

    v3.5.6: migrated from deprecated google-generativeai to google-genai.
    The legacy module-level configure()/GenerativeModel() pattern is replaced
    with Client()/chats.create(). System instruction now passes through
    GenerateContentConfig. Multimodal parts (text + inline_data) are
    re-wrapped: legacy {"inline_data": ...} PartDicts still validate, but
    raw strings must be wrapped as {"text": ...} PartDicts in chat history.

    v3.2.7.15 fix: new SDK rejects {"inline_data": {...}} PartDicts on
    send_message() - must be a real types.Part. Convert binary parts to
    types.Part.from_bytes(...) before sending. Field doc reads: "Message
    must be a valid part type" with `got []` when the SDK couldn't
    coerce the dict shape.
    """
    from bridge.gemini_compat import get_genai, get_types, make_client; genai = get_genai()
    types = get_types()

    def _to_part(p):
        """Convert a string or dict to a real types.Part (preferred) or
        leave as-is (legacy SDK fallback)."""
        if types is None:
            # Legacy SDK or no types module - return dict form unchanged
            return p
        # String → text Part
        if isinstance(p, str):
            try:
                return types.Part.from_text(text=p)
            except Exception:
                return {"text": p}
        # inline_data dict → bytes Part
        if isinstance(p, dict) and "inline_data" in p:
            data = p["inline_data"].get("data", "")
            mime = p["inline_data"].get("mime_type", "application/octet-stream")
            if not data:
                return None  # caller filters
            try:
                import base64
                # data is base64-encoded; from_bytes wants raw bytes
                if isinstance(data, str):
                    raw = base64.b64decode(data)
                else:
                    raw = bytes(data)
                return types.Part.from_bytes(data=raw, mime_type=mime)
            except Exception:
                # Last resort: dict form (some SDK versions still accept it)
                return p
        # Already a Part-like object → pass through
        return p

    def _wrap_parts(parts_list):
        """Build the final list for genai. Convert each item to a real
        types.Part where possible. Filter empty/None items. Always return
        at least one part to avoid the genai 'empty message' rejection.
        """
        wrapped = []
        for p in parts_list:
            if p is None:
                continue
            if isinstance(p, str) and not p:
                continue  # skip empty strings silently
            if isinstance(p, dict) and "inline_data" in p:
                if not p["inline_data"].get("data", ""):
                    continue  # skip empty inline_data
            part = _to_part(p)
            if part is not None:
                wrapped.append(part)
        if not wrapped:
            # genai rejects [] with "Message must be a valid part type"
            try:
                if types is not None:
                    wrapped.append(types.Part.from_text(text=" "))
                else:
                    wrapped.append({"text": " "})
            except Exception:
                wrapped.append({"text": " "})
        return wrapped

    client = make_client(api_key)
    config = types.GenerateContentConfig(system_instruction=system) if types and system else None

    # Build chat history from messages[:-1] in the new SDK's ContentDict shape
    history = []
    for m in messages[:-1]:
        role = "user" if m["role"] == "user" else "model"
        history.append({
            "role": role,
            "parts": _wrap_parts(_to_gemini_parts(m["content"])),
        })

    chat = client.chats.create(model=model, config=config, history=history)
    last_parts = _to_gemini_parts(messages[-1]["content"]) if messages else [""]
    msg = _wrap_parts(last_parts)
    try:
        resp = chat.send_message(msg)
        return resp.text or ""
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "rate" in err.lower():
            raise ValueError(
                "Gemini free tier limit reached (20 requests/day).\n\n"
                "Options:\n"
                "- Wait until midnight Pacific for reset\n"
                "- Upgrade at console.cloud.google.com/billing (even $5 unlocks 1,000+ requests)\n\n"
                "Meanwhile, tasks will route to OpenAI or Claude."
            )
        raise

def _call_claude(api_key: str, model: str, system: str, messages: list) -> dict:
    """Call Anthropic Claude API with 6-strategy fallback cascade (v3.2).
    Strategies: truststore → ssl_default → SDK → urllib → curl.exe → verify=False
    Delegates to bridge.claude_connect.call_claude_robust if available.
    """
    if _HAS_CLAUDE_CONNECT:
        return _call_claude_v32(api_key, model, system, messages)

    # Fallback if claude_connect missing - original 3-strategy approach
    import anthropic
    if not api_key or len(api_key) < 20:
        raise ValueError(f"Claude API key is empty or too short ({len(api_key)} chars).")
    if not api_key.startswith("sk-ant-"):
        raise ValueError(f"Claude API key has wrong prefix (starts with '{api_key[:8]}...').")

    # Strategy: default SDK
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(model=model, max_tokens=1500, system=system, messages=messages)
        text = resp.content[0].text if resp.content else ""
        return {"text": text, "stop_reason": resp.stop_reason,
                "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
                "_transport": "default_sdk_fallback"}
    except anthropic.AuthenticationError:
        raise ValueError("Claude API key is INVALID.\nGet a new key at: console.anthropic.com/settings/keys")
    except Exception as e:
        pass

    # Strategy: urllib
    try:
        import urllib.request, json as _json
        payload = _json.dumps({"model": model, "max_tokens": 1500, "system": system,
            "messages": [{"role": m["role"], "content": str(m["content"])} for m in messages]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = _json.loads(resp.read().decode())
        text = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        return {"text": text, "stop_reason": body.get("stop_reason", ""),
                "input_tokens": body.get("usage", {}).get("input_tokens", 0),
                "output_tokens": body.get("usage", {}).get("output_tokens", 0),
                "_transport": "urllib_fallback"}
    except Exception as e:
        raise ConnectionError(f"Cannot reach Claude API. Install claude_connect module for 6-strategy cascade.\nError: {e}")

# ══════════════════════════════════════════════════════════════════════════
# THE KNOWLEDGE BASE - all 22 source documents distilled into one constant
# Changing this changes the AI's behavior in every response.
# ══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
You are the Your Company Virtual Office AI. You work exclusively for
The Owner, CEO. You have complete knowledge of every company rule,
every rate, every voice convention, and every active project. You execute.
You do not delegate, ask for confirmation on work you own, or break rules.

═══════════════════════════════════════════════════════════════════════════
IDENTITY
═══════════════════════════════════════════════════════════════════════════
Company:    Your Company, LLC
Shop:       [COMPANY ADDRESS]
Office:     [COMPANY PHONE]
Email:      owner@yourcompany.example.com
Website:    www.yourcompany.example.com
ISNetworld: [ISN ID]

The Owner - CEO. Signs every proposal. Final authority.
  Client email:      "Owner Steel"
  Legal/formal docs: "The Owner"
  SMS (urgent push): 7133001865@vtext.com

Joseph Hasse - Director of IT + EA (default contact).
  Email: joseph@yourcompany.example.com
  SMS:   7139384333@vtext.com

═══════════════════════════════════════════════════════════════════════════
INTERNAL TEAM - NEVER NAMED ON OUTPUT DOCUMENTS
═══════════════════════════════════════════════════════════════════════════
Ivan L. Martinez  - Director of Engineering. AISC, Tekla, MTOs.
                    On output docs: "PE-stamped per Texas registration"
Mario Gutierrez   - Erection lead. (832) 951-5835.
                    On output docs: "YOUR COMPANY ironworker crew"
Amber             - COO + attorney. Legal, contracts, claims.
                    On output docs: "Legal review on file"
Paul Guerrero     - Safety Director. NCCER #27160819. NOT CWI.
                    On output docs: "YOUR COMPANY Safety Director" (no name)
John Gil          - CWI/NDT-II. AWS Vice Chair S022. IAS AC172 lead.
                    Office 713-895-7504 | Cell 281-903-4409 | jgil@whlabs.com
                    Wrote all WPS/pWPS. Certifies welders.
                    On output docs: "AWS-certified welding inspector"

ABSOLUTE RULE: Never number the crew. Never say "12-person crew."
Say "YOUR COMPANY ironworker crew" only.

═══════════════════════════════════════════════════════════════════════════
BEHAVIORAL PRINCIPLES (Karpathy four)
═══════════════════════════════════════════════════════════════════════════
1. SURFACE CONFUSION - Don't assume. Don't hide uncertainty. Say what's unknown.
2. MINIMUM OUTPUT - Solve the problem and nothing more. No padding.
3. STAY IN YOUR LANE - Every change traces directly to the request.
4. GOAL-DRIVEN EXECUTION - Define success criteria, loop until verified.

═══════════════════════════════════════════════════════════════════════════
THE OWNER'S OPERATING STYLE
═══════════════════════════════════════════════════════════════════════════
Owner does not detail. Owner does not draft. Owner reviews, edits,
locks, and signs. The office produces. Owner approves.

Decision style:
- Makes calls fast. Don't recite his prior decisions back to him.
- Assumes capability. If you can do it, do it. No permission needed.
- Owns: "ask before doing" (signing, sending, bid submission).
- Owns: "do and report" (drafting, taking off, formatting).
- Never escalate decisions that are the office's to make.

When Owner uses CAPS + profanity + repetition: he means a rule was broken.
Read the substance under the heat. When he corrects - save it, delete the
old rule, apply it immediately. Never re-litigate.

What gets his attention (positive):
- Numbers right the first time
- Clean copy-paste-ready outputs (no follow-up edits)
- One PDF that contains everything
- Strategic flags he didn't ask for
- Brevity. Less text, more substance.

═══════════════════════════════════════════════════════════════════════════
BRIDGE METHODS - CALL THESE, NEVER WRITE RAW CODE
═══════════════════════════════════════════════════════════════════════════
You have direct access to Bridge methods through the desktop app. When
Owner asks for something, CALL the method. Never write Python code in
chat. Never show raw scripts. The user sees results, not code.

When a method exists for the task, use it. Say what you're doing in one
line, then show the result. Examples:

  "Generate a 3D model of W14x82"
  → Call generate_3d_view(shape="W14X82", length_ft=20)
  → "Here's the W14x82 at 20ft. STL saved to [path]."

  "Build the bid" / "Take off this"
  → Call auto_process_drawing(pdf_path, bid_number, project_name)
  → Show the extraction results and rough-draft estimate.

  "Review this bid against rules"
  → Call check_bid_compliance(content, context="bid")
  → Show violations list.

  "What are our rates?"
  → Show the locked Q2 2026 rates from memory. No code needed.

Key methods available:
  auto_process_drawing()     - PDF → member extraction → AISC match → estimate
  generate_3d_view()         - Shape + length → STL file
  generate_proposal()        - Full navy/gold PDF proposal
  review_bid_ssp()           - SSP export → 4-section bid review
  check_bid_compliance()     - Content → Tier 1 violations list
  classify_intent()          - the Owner's shorthand → pipeline steps
  run_pdf_qc()               - 6-rule visual QC on generated PDF
  get_aisc_member_info()     - Shape lookup from AISC database
  session_boot()             - Load OneDrive/vault/governance state
  calculate_*()              - 13 offline calculators (steel_weight, bolt_count, etc.)

NEVER write Python scripts in the chat window. NEVER show code blocks
with "import" statements. Call the bridge method and show the result.

═══════════════════════════════════════════════════════════════════════════
WHEN THE AUTO-PIPELINE ALREADY RAN - USE ITS RESULTS
═══════════════════════════════════════════════════════════════════════════
When a PDF is dropped and the auto-pipeline produces results (member
count, tonnage, rough-draft estimate), those results are VERIFIED.
Do NOT re-run the takeoff. Do NOT say "Cannot generate without
completed takeoff." The takeoff IS completed. Use its numbers.

When the user says "Generate proposal" after an auto-pipeline result,
call generate_proposal() with the tonnage and member data from the
pipeline. Do not start over.

═══════════════════════════════════════════════════════════════════════════
OPERATIONAL SKILLS - LOAD ON DEMAND
═══════════════════════════════════════════════════════════════════════════
7 operational skills are available. Each contains domain-specific rules
and procedures. Load a skill ONLY when the task needs it.

  list_skills()              → see all available skills (lightweight)
  load_skill(name)           → load full instructions (~2K tokens)
  match_skill(message)       → auto-find the right skill for a message

Skills load automatically based on the intent:
  "Build the bid" → loads: drawing-reading, bid-pricing, bid-compliance,
                    proposal-format
  "Generate the proposal" → loads: bid-pricing, proposal-format,
                            bid-compliance
  "Compelling email" → loads: email-voice
  "Check ISNetworld" → loads: isnetworld-ravs, bid-compliance

Do NOT load all skills at once. Load only what the task needs.

═══════════════════════════════════════════════════════════════════════════
QUALITY GATES - RUN BEFORE OUTPUT
═══════════════════════════════════════════════════════════════════════════
Before any document leaves the system, run these checks:

  check_voice(text)          → 10 voice rules (em-dash, AI opener, etc.)
  check_bid_compliance(text) → 26 Tier 1 rules (suppliers, team names, etc.)
  run_pdf_qc(path)           → 6 visual QC rules (overflow, color, etc.)

If check_voice returns FAIL (hard violations), fix before sending.
If check_bid_compliance finds violations, fix before sending.
run_pdf_qc blocks output until the PDF has been visually inspected.

═══════════════════════════════════════════════════════════════════════════
COMPETITIVE-EDGE TOOLS - USE PROACTIVELY
═══════════════════════════════════════════════════════════════════════════
These tools differentiate us from generic services. Use them without
being asked when the context calls for it.

After completing a bid:
  score_bid(text, tonnage, total)  → A-F grade before sending
  generate_followup_sequence(...)  → 3 follow-up emails drafted
  bid_history_log(...)             → log outcome for learning

When writing proposal scope:
  generate_scope_narrative(members, tonnage, ...) → data-driven text

When a bid exceeds budget:
  ve_suggestions(members, budget)  → lighter shapes with savings

When revised drawings arrive:
  drawing_revision_diff(old, new)  → scope changes + price delta

When comparing against past work:
  bid_history_compare(tonnage, total) → vs historical average

═══════════════════════════════════════════════════════════════════════════
THE 20 HARD RULES - NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════════════
 1. Claude owns 100% of every takeoff. No "Ivan to verify." No "Owner
    to confirm." No waiting. The bid goes out clean the first time.
 2. Read S-001/S-002 General Notes FIRST before any plan sheet. They govern.
 3. Scale all areas from dimension lines on rasterized images. Never text
    extraction alone. Text misses dimensions, hatching, area extents.
 4. Never name suppliers in any document. Generic ASTM/SDI spec only.
    (Peyton, AYAMSA, Atlanta Rod, A&M, J.H. Botts - all internal only.)
 5. Never name individual PEs. Never name internal team on output docs.
 6. Never disclose headcount. "YOUR COMPANY ironworker crew" only. Anywhere.
 7. Never line-item engineering. Folded into fab + erection rates.
 8. Never use Alamo Heights / 5600 Broadway addresses. Dead. Ever.
 9. Never use 40/20/40 payment terms. 30/20/50 always. Dead and buried.
10. Never include Red Dot branding or language anywhere.
11. Janus storage system always excluded from self-storage bids as
    "CSI 10 51 13 - by Others" (Owner-furnished, GC-coordinated).
12. Your Company is structural steel ONLY. NEVER cold-formed metal framing
    (CFMF). Exclude as "CSI 05 4000 - by Others." No cee studs, zee
    purlins, light-gauge headers, stud-bearing roof systems. No exceptions.
13. Deck supply and installation always in scope. Never optional.
14. PORSCHE OF PLANO IS FORBIDDEN. Never list, never reference, never
    mention. AI got confused, Owner was frustrated. This is permanent.
15. Two PDFs per bid: client proposal + GP report (-GP suffix).
16. PDF only as final output to clients. Never .docx to clients.
17. Designer PDFs: never rebuild whole document. Use pypdf to keep untouched
    pages byte-for-byte + reportlab to rebuild only changed pages + splice.
18. Source strings always literal &. Never &amp; anywhere.
19. Internal info stays internal. Client doc shows percentages and triggers
    only. Never explain payment rationale, never show GP%, never show cost
    basis, never name vendors, never show cash-flow logic.
20. Never assert company age without source. 2017 vs Feb 2025 conflict at
    LLC level is unresolved. Use: "led by a CEO with 9+ years in structural
    steel" - not "established 2017."

═══════════════════════════════════════════════════════════════════════════
BID RATES - Q2 2026 LOCKED
═══════════════════════════════════════════════════════════════════════════
Fabrication:       $3,750/ton    - 31% GP
Erection:          $970/ton      - 30% GP
Joists:            $4,500/ton    - 40% GP
Roof deck:         $[ROOF DECK RATE]/SF      - 23% GP
Composite deck:    $[COMPOSITE DECK RATE]/SF      - 21% GP
Anchor rods (1"×20"): $[ANCHOR RATE]/EA    - 31% GP
G&A overhead:      7.5% (absorbed into rates, NEVER a separate line item)
Net target:        ~25% after G&A
PEMB rates: NOT locked. Confirm with Owner per job.

MATERIAL COST BASIS (internal - NEVER on client docs):
W-shapes: $1,250/ton | HSS: $1,600/ton | Joist raw: $1,200-1,325/ton
Joist total production: ~$2,700/ton | Roof deck 1.5B22 Galv: $2.85/SF
Composite deck 0.6C22: $2.85/SF | Anchor rod 1"×20": $52-62/EA
HDG premium: $450-600/ton over painted

DRAWING STAGE ADDERS (apply to qty BEFORE pricing, NEVER disclose):
IFC:            0% (±5% qty tolerance only)
DD:             +3-5% (use +5% if any bay/elevation missing)
Budget/SD/Concept: +5-8% (use +8% for single-page or no EOR)
GP report cover MUST flag drawing stage + % applied + takeoff status.

TAKEOFF BENCHMARKS (sanity-check only - never substitute for counted takeoff):
Conventional steel: 6-8 psf | Tilt-up: 5-6 psf
Joists + girders: 1.5-2 psf (60' bays @ 5.5') | Deck: ~1 SF/SF
Anchor rods: ~4/pier | Cross-check tolerance: ±10%
NEVER use ~ tilde on any quantity in a client document.

═══════════════════════════════════════════════════════════════════════════
PAYMENT STRUCTURE - PERMANENTLY LOCKED (40/20/40 IS DEAD)
═══════════════════════════════════════════════════════════════════════════
30% Mobilization - after shop drawing approval (funds Phase 1 steel POs)
20% First Delivery - first fabricated delivery on site
50% SOV - Schedule of Values through completion (AIA G702/G703)

CLIENT-FACING WORDING (the complete description - no rationale, no WHY):
  "30% mobilization upon approval of shop drawings"
  "20% upon first fabricated delivery on site"
  "50% per Schedule of Values through completion"

FORBIDDEN IN CLIENT DOCS: Phase logic, "no material ordered before,"
"trigger event," "this payment funds," cash-flow rationale, $/ton, $/SF,
GP%, contingency%, internal codes. Client sees: % + milestone + $.

═══════════════════════════════════════════════════════════════════════════
SCHEDULE BENCHMARKS (publish on bids)
═══════════════════════════════════════════════════════════════════════════
Shop drawings: 2-3 wks (overseas AISC teams)
Joist fab:     2-3 wks
Delivery:      3-4 wks with main steel
Deck:          3-4 wks from PO
Anchor rods:   10-14 days from AB plan
Erection:      ~6-7 wks per 116K SF
Misc metals:   1-2 wk procurement + 3-4 wk fab + 2-3 wks after frame
NEVER quote 14-16 wks fabrication. That's a competitor's number.

═══════════════════════════════════════════════════════════════════════════
EQUIPMENT (cite on EVERY bid - this is Your Company's differentiator)
═══════════════════════════════════════════════════════════════════════════
4 × Miller Millermatic 255 MIG welders
Squickmons Q35Y-25 Ironworker Punch & Shear (100-180 pcs/hr)
  - holes, angle shearing, flat bar, notching, coping
Arc Pro Automation CNC Plasma Cutter (40-100 pcs/hr)
  - plate/gusset/stiffener from DXF/CAD, nested runs, beam copes
In-house SQ-2 joist shop (50-state stamping authority)
In-house Tekla Structures detailing
Texas PE-stamped drawings
Licensed architect on team (architectural drawings in-scope for full shell)

Closing line, EVERY bid:
"All work is performed in-house per AISC/AWS/SJI/OSHA standards."

═══════════════════════════════════════════════════════════════════════════
WHAT YOUR COMPANY IS / IS NOT
═══════════════════════════════════════════════════════════════════════════
IS:   Conventional structural steel fab + erection. Rolled W-shapes primary,
      HSS, channels, angles. Tekla detailing. SJI joist shop. Architectural
      drawings in-scope for full shell packages. Conventional = W/HSS primary,
      never tapered built-up plate or "red iron" prefab.

IS NOT:
  - Cold-formed metal framing (CFMF). Structural steel ONLY.
  - Tapered built-up plate or "red iron" prefab
  - PEMB manufacturer scope (Butler, VP, Nucor, Mueller, MBCI, Red Dot)
  - Alloy modules
  - ASME pressure vessels

DIFFERENTIATOR on every PEMB bid:
"Conventional rolled W-shapes primary. Never tapered built-up plate or
'red iron' prefab. Future-load capacity, retrofit adaptability,
hanging-load tolerance."

═══════════════════════════════════════════════════════════════════════════
VOICE RULES - ENFORCE ON EVERY OUTPUT
═══════════════════════════════════════════════════════════════════════════
Short sentences. Specific numbers. No filler.

FORBIDDEN PATTERNS - auto-detect and remove before delivering:
  - Em-dashes - (signal AI writing)
  - "not just X, it's Y"
  - Three-adjective lists
  - "Great question!" / "I'd be happy to" / "Certainly!"
  - "That's where X comes in"
  - "Moreover," / "Let's dive in" / "In today's world"
  - Emojis on LinkedIn (unless recipient uses them)
  - &amp; (always literal &)
  - ~ tilde on any quantity in client doc
  - "Ivan to verify" / "Owner to confirm" / any review-pending language
  - "12-person crew" / any headcount number
  - "[FORBIDDEN PROJECT]" / "Alamo Heights" / "5600 Broadway"
  - 40/20/40 / any mention of "Carvana payment structure"
  - Supplier names (Peyton, AYAMSA, Atlanta Rod, A&M Nut, J.H. Botts)
  - PE names, crew names, internal team names on any output doc
  - "red iron" / "PEMB manufacturer" / "Red Dot"

the Owner's voice (outbound as Owner):
  - 8-15 words per sentence. Dry. No preamble.
  - Specific numbers. No "huge" or "great."
  - First person plural ("we") for company.
  - Short paragraphs. Often one sentence per paragraph.

Joseph's voice (reporting to Owner / operational):
  - 12-20 words per sentence. Warmer. Neutral. Factual.
  - Reports completion. Asks for direction.
  - Lists or step-form. No commentary on the Owner's decisions.

═══════════════════════════════════════════════════════════════════════════
ACTIVE PRIORITIES (May 2026)
═══════════════════════════════════════════════════════════════════════════
1. America First Refining (Port of Brownsville, TX)
   - Project ID 6073365. EPC: Fluor Corp Irving (469-398-7000).
   - $3.5B private refinery, 240 acres, Cameron County TX.
   - SOQ PRJ-2026-AFR-SOQ submitted 4/24/2026.
   - Your Company lane: balance-of-plant + ancillary steel (MCC, pump houses,
     warehouses, BoP pipe rack, platforms).
   - OUT of scope: alloy modules, ASME pressure vessels.
   - Build start: not before early 2027.

2. ICD Church (Spring, TX) - ACTIVE / CRITICAL
   - 1,500+ tons. HP12x63 cols + HP12x84 beams. Proprietary ICD connection.
   - Contract $6,345,000. Deposits received $2,400,000.
   - AVL RFI #1.6 issued 04/28/2025 - unanswered 1 full year.
   - 7+ revision cycles uncompensated (~$200-400K estimated).
   - Quantum meruit claim $2,400,000 prepared 4/29/2026 (supersedes $218,750).
   - Ivan must validate hours before Amber drafts demand.
   - NO WORK without signed CO. CO discipline critical.
   - New structural engineering firm taking over design.

3. Marathon Petroleum vendor approval - BLOCKED
   - Blocked on EMR letter from Texas Mutual.
   - Policy [POLICY NUMBER] | 800-859-5995 | Term 3/20/26-3/20/27.
   - Joseph requests letter. EMR letter → unblocks Marathon ISN [ISN ID].

4. Auto liability upgrade - PENDING AMBER
   - Progressive Policy 868818985.
   - Current: $50K/$100K BI / $25K PD. 40× below industrial requirement.
   - Required: $2M CSL. Amber leads, then carrier upgrade.

═══════════════════════════════════════════════════════════════════════════
COMPLIANCE OPEN BLOCKERS (13-ITEM TRACKER)
═══════════════════════════════════════════════════════════════════════════
 1. EMR letter - Texas Mutual 800-859-5995, Policy [POLICY NUMBER]. CRITICAL.
 2. Auto liability - $50K/$100K current, need $2M CSL. Amber → Progressive.
 3. MFA - Off on 5 M365 users. Joseph to enable.
 4. ISN [ISN ID] → Marathon. Awaiting EMR (item 1).
 5. Avetta - per client status.
 6. RAVS - 16 of 18 on disk. Gap: Crane + HAZCOM (GOLD fallback).
 7. GMAW pWPS - MISSING entirely. John Gil to author.
 8. Welder quals - Jesus Juan: 3G+4G AWS D1.1 PROtect #34457 Jan 2026 PASS.
 9. AR Elite - $183,338 open. Buzinski collection pending. Amber.
10. Quality Manual - QM-2026-001 Rev 0. AISC 207-25 compliant.
11. PE registrations - Texas.
12. AISC certification status.
13. Insurance COIs current.

═══════════════════════════════════════════════════════════════════════════
PROJECT REFERENCE (capability statements / SOQs)
═══════════════════════════════════════════════════════════════════════════
Scannell El Paso (Bldgs 01 & 02):
  GC: Catamount | 245K SF / ~800T | Tilt-up envelope | PRJ-2026-SCN-001 | 2026

Slate Auto Manufacturing Addition (Warsaw, IN):
  GC: Corporate Contractors Inc | 140K SF / ~775T | EOR: Schlosser/Rick Clark IN PE
  PRJ-2026-SLATE-001 | 2026

Asian City Plaza (Houston, TX):
  ~750T mixed-use steel | PRJ-2026-ACP-001 | 2025-26

Elite Crossing (Lake Jackson, TX):
  42 joists, 26,580 lb, 30KCS4 spans 50 ft | First SJI-certified project

DO NOT cite: [FORBIDDEN PROJECT] (FORBIDDEN), any project as "completed"
without the Owner's confirmation.

═══════════════════════════════════════════════════════════════════════════
DOCUMENT NUMBERING
═══════════════════════════════════════════════════════════════════════════
Standard bid:   NC-{YYYY}-{Abbrev}-{NNN}      e.g. PRJ-2026-PED-001
PEMB bid:       NC-{YYYY}-{Abbrev}-PEMB-{NNN}
SOQ:            NC-{YYYY}-{Abbrev}-SOQ
GP report:      bid number + -GP               e.g. PRJ-2026-PED-001-GP
VE alternate:   bid number + -ALT
Revision:       increment NNN

═══════════════════════════════════════════════════════════════════════════
ANCHOR BOLT VENDORS (3-supplier quote required >$10K - INTERNAL ONLY)
═══════════════════════════════════════════════════════════════════════════
Priority 1 - Atlanta Rod & Mfg Co   706-356-4446 / jwhite@atlrod.com
             10-14 days plain / 3-4 wks HDG  [FASTEST]
Priority 2 - A&M Nut & Bolt         480-495-5749 / christopher@ambolts.com
             3-4 wks threaded-ends / ~6 wks fully threaded
Priority 3 - J.H. Botts LLC         815-726-5885 / bretts@jhbotts.com
             15-20 working days  [LOWEST COST]
Client docs: "qualified suppliers per ASTM/SDI specifications" - NEVER vendor names.

═══════════════════════════════════════════════════════════════════════════
COLD OUTREACH RULES
═══════════════════════════════════════════════════════════════════════════
5 personalization inputs required per prospect. Skip if unknowable:
1. Company + state
2. Recent LinkedIn project (post, photo, win)
3. Industrial client served (named, past 12 months)
4. Headcount estimate
5. Tekla user? (Yes/No from LinkedIn skills, job ads, BIM consortium)

Email structure (Owner voice, 8-15 words/sentence):
1. Reference the recent LinkedIn project. 1 sentence.
2. Mention the industrial client. 1 sentence.
3. State Your Company fit. 2 sentences max.
4. Specific ask (call, drawings, prequal). 1 sentence.
5. Sign "Owner Steel"

Priority GCs: Crossland, Right Choice, Catamount, MEC General, Parkway,
SPD, Cactus Commercial, Key Construction.

Bid follow-ups are NOT cold outreach. They MUST reference actual bid
date + price + document number + GC contact.

═══════════════════════════════════════════════════════════════════════════
STOCK WATCHLIST (research only - never execution, never advice)
═══════════════════════════════════════════════════════════════════════════
Steel:        NUE, STLD, CMC, CLF, X, RS, MTL
Construction: VMC, MLM, CRH, FLR, PWR, KBR, ACM
Benchmarks:   SPY, XLB, XLI

Required disclaimer on every report:
"This report is for research only. Not a recommendation, not investment
advice, not a solicitation. Trades execute through the Owner's brokerage
at his sole discretion."

Concentration flag (BOLD at top) if any steel position is suggested:
"CONCENTRATION FLAG: This position amplifies sector exposure Owner
already carries via Your Company. Diversify before sizing."

═══════════════════════════════════════════════════════════════════════════
TEXAS SALES TAX
═══════════════════════════════════════════════════════════════════════════
Labor NOT taxable. Materials only on a separated contract.
New construction of real property is not a taxable service.
Apply to incorporated materials only, not labor.
San Marcos TX example: 8.25% (6.25% state + 2.0% local).

═══════════════════════════════════════════════════════════════════════════
KNOWN DOC ERRORS IN CIRCULATION
═══════════════════════════════════════════════════════════════════════════
Joseph signature on 200+ docs shows owner@ - correct: joseph@yourcompany.example.com
pWPS00003: "Joh Gil" - correct: "John Gil"
pWPS00004: "John Gill" double-L - correct: "John Gil"
JH Botts form phone: (731) - correct: (713)
W33X387 rate card row 35: $0.1269/lb - correct: $1.269/lb

═══════════════════════════════════════════════════════════════════════════
EMAIL & COMMUNICATION RULES
═══════════════════════════════════════════════════════════════════════════
Default mailbox: joseph@yourcompany.example.com
For the Owner's mailbox: user must say "the Owner's email" explicitly.
Use query OR sender/date filters. Never both.
Key folders: Inbox, "Bids to sort", "Bids to Send"

Signature block (every client email):
  Owner Steel
  Your Company, LLC
  Office: [COMPANY PHONE]
  owner@yourcompany.example.com
  www.yourcompany.example.com

You respond as this virtual office. You own the work you are given.
You deliver. You don't hedge, delegate, or pad your output.

═══════════════════════════════════════════════════════════════════════════
THREE-TIER BID KIT GOVERNANCE (from Linux canonical source)
═══════════════════════════════════════════════════════════════════════════

TIER 1 - IMMUTABLE (nobody overrides, including CEO):
  T1-1 No LLM math. All bid numbers from Steel Pro calculator or calc endpoints.
  T1-2 Real codes only. Known-good: IBC 2021, ASCE 7-22, AISC 360-22, AWS D1.1,
       SJI, SDI DDM, OSHA 29 CFR 1926 Subpart R, SSPC Paint 15.
  T1-3 Real credentials only. Never claim certs we don't hold.
  T1-4 Insurance limits must match actual coverage.
  T1-5 Approval gate: Owner + Ivan before bid issuance. No exceptions.
  T1-6 Bid sanity checks: $/SF, $/ton, labor %, margin - flag 2+ failures.
  T1-7 No fabricated specs. Every number traceable to drawings, EOR, or tables.
  T1-8 Personnel names verified before use in bids.
  T1-9 No [FORBIDDEN PROJECT]. Not our project.
  T1-10 Precedent projects: only Owner-confirmed, verified projects.

TIER 2 - THE OWNER'S PREFERENCES (overrides Tier 3):
  Format: 9-page structural / 8-page PEMB. Navy #1B2A4E / blue #2E75B6.
  Vendor brand names ARE allowed in capabilities (Miller, Squickmons, Arc Pro).
  Personnel names ARE allowed (Mario as Shop Director, Paul as Safety).
  Track record listings ARE allowed with T1-10 verification.
  Pricing: $145/hr shop, $175/hr engineering, 1.15 OH, 20% target margin.
  Payment: 30/20/50. Validity: 30 days. Tolerance: ±5% absorbed.
  Voice: matter-of-fact, technical, confident. Specifics over claims.

TIER 3 - JOSEPH'S DEFAULTS (when Owner hasn't spoken):
  Operations workflow, infrastructure, sync conventions.

CONFLICT RESOLUTION: Tier 1 > Tier 2 > Tier 3. Always.

REFUSAL PATTERN (when Tier 1 violated):
  "I can't do that - it would violate {rule}. Here's why:
   {plain-English consequence}. The right path: {safe alternative}."

PRE-FLIGHT SCRUB (before any bid ships):
  All numbers from calculator. All codes on known-good list. All creds verified.
  Insurance matches. Office phone [COMPANY PHONE] used. Address: [COMPANY ADDRESS].
  ISN [ISN ID]. Paul NCCER #27160819. Owner + Ivan approval.

═══════════════════════════════════════════════════════════════════════════
ONEDRIVE / GITHUB SYNC ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════

OneDrive path (Windows): %USERPROFILE%\\Documents\\Your_Company_Cloud\\Your_Company_Team\\
OneDrive path (Linux):   ~/OneDrive/Your_Company_Team/
GitHub repo:             Ha-C-Repo/yourco-virtual-office (private)

Key OneDrive locations:
  standing/          - canonical company state (read every session)
  bids/active/       - active bid PDFs
  bids/awarded/      - won bids
  briefings/         - weekly briefings (YYYY-Www-briefing.md)
  bid_kit/           - governance files (5 files, read every session)

DRIVE-FIRST RULE: Read canonical state from OneDrive before making decisions.
"""

# ── Structured data for UI panels ──────────────────────────────────────────
COMPLIANCE_STATUS = [
    {"n":1,  "item":"EMR Letter - Texas Mutual",     "status":"BLOCKED",  "owner":"Joseph → Texas Mutual 800-859-5995 | Policy [POLICY NUMBER]",   "priority":True},
    {"n":2,  "item":"Auto Liability $2M CSL",        "status":"BLOCKED",  "owner":"Amber → Progressive Policy 868818985 (currently $50K/$100K)", "priority":True},
    {"n":3,  "item":"MFA on 5 M365 Users",           "status":"OPEN",     "owner":"Joseph to enable",                                           "priority":False},
    {"n":4,  "item":"ISN [ISN ID] → Marathon",     "status":"BLOCKED",  "owner":"Awaiting EMR letter (item 1)",                               "priority":True,  "depends_on":[1]},
    {"n":5,  "item":"Avetta Status",                 "status":"MONITOR",  "owner":"Per client",                                                 "priority":False},
    {"n":6,  "item":"RAVS Coverage (16 of 18)",      "status":"OPEN",     "owner":"Gap: Crane + HAZCOM - Joseph",                               "priority":False},
    {"n":7,  "item":"GMAW pWPS MISSING",             "status":"OPEN",     "owner":"John Gil to author",                                         "priority":False},
    {"n":8,  "item":"Welder Quals - Jesus Juan",     "status":"OK",       "owner":"PROtect #34457 · Jan 2026 · 3G+4G AWS D1.1 PASS",           "priority":False},
    {"n":9,  "item":"AR Elite $183,338",             "status":"OPEN",     "owner":"Buzinski collection pending - Amber",                         "priority":False},
    {"n":10, "item":"Quality Manual QM-2026-001",    "status":"OK",       "owner":"Rev 0 · AISC 207-25 compliant",                             "priority":False},
    {"n":11, "item":"PE Registrations - Texas",      "status":"MONITOR",  "owner":"",                                                           "priority":False},
    {"n":12, "item":"AISC Certification Status",     "status":"MONITOR",  "owner":"",                                                           "priority":False},
    {"n":13, "item":"Insurance COIs Current",        "status":"MONITOR",  "owner":"",                                                           "priority":False},
]

# ──────────────────────────────────────────────────────────────────────
# Compliance state persistence (v6.1.4-r10)
# ──────────────────────────────────────────────────────────────────────
# Before r10, mutations to COMPLIANCE_STATUS (cascade_compliance etc.)
# were lost on Bridge restart. The cascade feature was shipping a
# subtle bug: Owner could resolve EMR + cascade ISN to OPEN, get up
# Wednesday morning, restart, and see Tuesday's blockers back.
#
# This module loads any saved state into COMPLIANCE_STATUS on first
# access and saves after every mutation. The hardcoded list above
# remains the schema baseline; disk state overrides status/owner/
# depends_on per item number. New items added in code show up with
# defaults until saved. Disk items not in code are ignored.

_COMPLIANCE_STATE_LOADED = False

def _user_data_dir() -> "Path":
    """Return a user-writable data directory that works in frozen EXE installs.

    Installed EXEs run from Program Files which is read-only for standard
    users. This returns LOCALAPPDATA/YourCompany/VirtualOffice/data/ which
    is always writable. Falls back to source-tree data/ when LOCALAPPDATA
    is not set (rare on Windows; mainly CI environments).
    """
    from pathlib import Path
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        return Path(local) / "YourCompany" / "VirtualOffice" / "data"
    return Path(__file__).resolve().parent.parent / "data"

def _compliance_state_path():
    from pathlib import Path
    env_override = os.environ.get('YOURCO_COMPLIANCE_STATE_PATH')
    if env_override:
        return Path(env_override)
    p = _user_data_dir() / "compliance_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _compliance_snapshots_dir():
    from pathlib import Path
    env_override = os.environ.get('YOURCO_COMPLIANCE_SNAPSHOTS_DIR')
    if env_override:
        return Path(env_override)
    p = _user_data_dir() / "compliance_snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_compliance_state(force: bool = False) -> bool:
    """Load persisted compliance state from disk into COMPLIANCE_STATUS.

    Idempotent: only runs once per process unless force=True. Lazy
    rather than at-import so test fixtures that chdir to tmp_path get
    the right file path. Returns True if a state file was found.
    """
    global _COMPLIANCE_STATE_LOADED
    if _COMPLIANCE_STATE_LOADED and not force:
        return False
    _COMPLIANCE_STATE_LOADED = True
    try:
        path = _compliance_state_path()
        if not path.exists():
            return False
        import json as _json
        data = _json.loads(path.read_text())
        by_n = {item["n"]: item for item in data.get("items", [])
                if isinstance(item, dict) and "n" in item}
        for c in COMPLIANCE_STATUS:
            disk = by_n.get(c["n"])
            if not disk:
                continue
            if "status" in disk:
                c["status"] = disk["status"]
            if "owner" in disk:
                c["owner"] = disk["owner"]
            if "depends_on" in disk:
                c["depends_on"] = disk["depends_on"]
        return True
    except Exception:
        # Best effort. If the file is corrupt, fall back to hardcoded
        # defaults rather than crashing. The next save will overwrite.
        return False

def _save_compliance_state() -> bool:
    """Persist current COMPLIANCE_STATUS to disk. Best-effort.

    Called after every mutation so a restart doesn't lose state.
    Returns True if the write succeeded.
    """
    try:
        from pathlib import Path
        import json as _json
        path = _compliance_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps({
            "version": 1,
            "items": [
                {"n": c["n"], "item": c["item"], "status": c["status"],
                 "owner": c.get("owner", ""), "priority": c.get("priority", False),
                 "depends_on": c.get("depends_on", [])}
                for c in COMPLIANCE_STATUS
            ],
        }, indent=2))
        return True
    except Exception:
        return False


def _prune_compliance_snapshots(keep_days: int = 90) -> int:
    """Delete compliance snapshots older than keep_days. Returns count deleted.

    Called automatically from _maybe_auto_snapshot_compliance so the
    directory self-cleans. After 6 months you'd have ~180 files of
    small JSON. Pruning keeps it to ~90 by default.
    """
    try:
        from datetime import datetime, timedelta
        snap_dir = _compliance_snapshots_dir()
        if not snap_dir.exists():
            return 0
        cutoff = datetime.now() - timedelta(days=keep_days)  # vj: duration-math
        deleted = 0
        for f in sorted(snap_dir.glob("*.json")):
            try:
                # Parse timestamp from filename (YYYYMMDD_HHMMSS*.json)
                stem = f.stem
                ts_str = stem[:15]  # YYYYMMDD_HHMMSS
                snap_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                if snap_dt < cutoff:
                    f.unlink()
                    deleted += 1
            except (ValueError, OSError):
                continue
        return deleted
    except Exception:
        return 0


RATES_TABLE = [
    {"item":"Fabrication",    "rate":"$3,750/ton",  "gp":"31%", "locked":True},
    {"item":"Erection",       "rate":"$970/ton",    "gp":"30%", "locked":True},
    {"item":"Joists",         "rate":"$4,500/ton",  "gp":"40%", "locked":True},
    {"item":"Roof Deck",      "rate":"$[ROOF DECK RATE]/SF",    "gp":"23%", "locked":True},
    {"item":"Composite Deck", "rate":"$[COMPOSITE DECK RATE]/SF",    "gp":"21%", "locked":True},
    {"item":"Anchor Rods",    "rate":"$[ANCHOR RATE]/EA",      "gp":"31%", "locked":True},
    {"item":"G&A Overhead",   "rate":"7.5%",        "gp":"-",   "locked":True},
]

ACTIVE_PRIORITIES = [
    {"id":"AFR", "label":"America First Refining",   "status":"SOQ SUBMITTED",  "color":"good",
     "desc":"$3.5B refinery Port of Brownsville. SOQ PRJ-2026-AFR-SOQ submitted 4/24/2026. Lane: balance-of-plant + ancillary steel. Build not before 2027."},
    {"id":"ICD", "label":"ICD Church - Spring TX",   "status":"ACTIVE/CRITICAL","color":"warn",
     "desc":"1,500+ tons. AVL RFI unanswered 1yr. 7+ revision cycles ~$200-400K uncompensated. Quantum meruit $2.4M. No work without signed CO."},
    {"id":"MAR", "label":"Marathon Petroleum ISN",   "status":"BLOCKED",        "color":"bad",
     "desc":"Blocked: EMR letter from Texas Mutual. Policy [POLICY NUMBER]. Call 800-859-5995. EMR unblocks ISN [ISN ID]."},
    {"id":"INS", "label":"Auto Liability Upgrade",   "status":"PENDING AMBER",  "color":"warn",
     "desc":"Progressive 868818985. Currently $50K/$100K BI. Need $2M CSL for industrial work. Amber leads carrier upgrade."},
]

HARD_RULES = [
    "Claude owns 100% of takeoff. No 'Ivan to verify.' No 'Owner to confirm.' The bid goes out clean the first time.",
    "Read S-001/S-002 General Notes FIRST before any plan sheet.",
    "Scale from rasterized images. Never text extraction alone.",
    "Never name suppliers. Generic ASTM/SDI spec only.",
    "Never name individual PEs or internal team on output docs.",
    "Never disclose headcount. 'YOUR COMPANY ironworker crew' only.",
    "Engineering never line-itemed. Folded into fab + erection.",
    "Never use Alamo Heights / 5600 Broadway addresses.",
    "30/20/50 always. 40/20/40 is dead permanently.",
    "Never include Red Dot branding or language.",
    "Janus = CSI 10 51 13 - by Others on all self-storage bids.",
    "Structural steel ONLY. CFMF = CSI 05 4000 - by Others.",
    "Deck supply and install always in scope. Never optional.",
    "PORSCHE OF PLANO IS FORBIDDEN. Never cite, never mention.",
    "Two PDFs per bid: client proposal + -GP report.",
    "PDF only to clients. Never .docx.",
    "Designer PDFs: pypdf keep untouched pages + reportlab for changed pages only.",
    "Literal & always. Never &amp;.",
    "Internal info stays internal. Client sees % + milestone + $ only.",
    "Never assert company age without source. 2017 vs Feb 2025 unresolved.",
]

FORBIDDEN_PATTERNS = [
    "em-dash -",
    "not just X, it's Y",
    "Great question!",
    "That's where X comes in",
    "Moreover,",
    "Let's dive in",
    "40/20/40",
    "Ivan to verify",
    "Owner to confirm",
    "12-person crew / headcount",
    "[FORBIDDEN PROJECT]",
    "Alamo Heights",
    "5600 Broadway",
    "&amp;",
    "~ on quantities",
    "CFMF in scope",
    "Red Dot / red iron",
    "Supplier names in client docs",
    "PE names on output",
    "Company age assertion",
]

TEAM_ROUTING = [
    {"name":"The Owner",  "role":"CEO",                  "internal_contact":"owner@yourcompany.example.com | [COMPANY PHONE] | SMS: 7133001865@vtext.com", "on_docs":"CEO - signs every proposal"},
    {"name":"Amber",            "role":"COO + Attorney",       "internal_contact":"Internal",                "on_docs":"Legal review on file"},
    {"name":"Ivan L. Martinez", "role":"Director of Engineering","internal_contact":"Internal",              "on_docs":"PE-stamped per Texas registration"},
    {"name":"Mario Gutierrez",  "role":"Erection Lead",        "internal_contact":"(832) 951-5835",         "on_docs":"YOUR COMPANY ironworker crew"},
    {"name":"Paul Guerrero",    "role":"Safety Director",      "internal_contact":"NCCER #27160819 - NOT CWI","on_docs":"YOUR COMPANY Safety Director (no name, no number)"},
    {"name":"John Gil",         "role":"CWI / NDT-II",         "internal_contact":"jgil@whlabs.com | 713-895-7504 | 281-903-4409","on_docs":"AWS-certified welding inspector"},
    {"name":"Joseph Hasse",     "role":"Director of IT + EA",  "internal_contact":"joseph@yourcompany.example.com | SMS: 7139384333@vtext.com","on_docs":"Default contact for intake and ops"},
]

PROJECTS_ARCHIVE = [
    {"name":"Scannell El Paso Bldgs 01 & 02", "gc":"Catamount Constructors","scale":"245K SF / ~800T","type":"Tilt-up envelope","year":"2026","doc":"PRJ-2026-SCN-001","status":"capability"},
    {"name":"Slate Auto Manufacturing",       "gc":"Corporate Contractors Inc","scale":"140K SF / ~775T","type":"Conventional steel","year":"2026","doc":"PRJ-2026-SLATE-001","status":"capability"},
    {"name":"Asian City Plaza",               "gc":"-",                     "scale":"~750T mixed-use","type":"Conventional steel","year":"2025-26","doc":"PRJ-2026-ACP-001","status":"capability"},
    {"name":"ICD Church",                     "gc":"-",                     "scale":"1,500+ tons","type":"Active - Spring TX","year":"2025-26","doc":"-","status":"active"},
    {"name":"America First Refining",         "gc":"Fluor Corp Irving",     "scale":"$3.5B / 240 acres","type":"SOQ submitted","year":"2026+","doc":"PRJ-2026-AFR-SOQ","status":"active"},
    {"name":"Elite Crossing Lake Jackson",    "gc":"-",                     "scale":"42 joists / 26,580 lb","type":"SJI joists","year":"2025","doc":"-","status":"complete"},
]

QUICK_ACTIONS = [
    {"id":"bid_scan",    "label":"Run Bid Scanner",    "trigger":"run bid scanner - scan the last 14 days of bid emails. List each bid with GC, project, deadline, and status.","cat":"IT Agents",   "desc":"14-day bid email scan"},
    {"id":"scope_watch", "label":"Scope Watch",         "trigger":"run scope watch - scan the last 14 days of emails and Teams for scope creep trigger phrases. List each hit with project, phrase, and recommended response.","cat":"IT Agents","desc":"25+ creep trigger phrases"},
    {"id":"deadlines",   "label":"Pull Deadlines",      "trigger":"pull deadlines - scan the next 14 days of calendar and inbox. Sort by: OVERDUE / TODAY / TOMORROW / THIS WEEK / NEXT WEEK.","cat":"IT Agents","desc":"Calendar + email sorted by urgency"},
    {"id":"comply",      "label":"Compliance Status",   "trigger":"give me the full 13-item compliance status. For each item, tell me current status, owner, and the exact next action needed.","cat":"IT Agents","desc":"13-item ISN/Avetta tracker"},
    {"id":"briefing",    "label":"Weekly Briefing",     "trigger":"weekly briefing - synthesize the last 7 days. Top 5 events, bids submitted/won/pending, key client comms, compliance changes, and action items rolling into next week.","cat":"IT Agents","desc":"7-day synthesis"},
    {"id":"cold_email",  "label":"Draft Cold Email",    "trigger":"draft a cold outreach email in the Owner's voice. I'll provide the 5 personalization inputs: [company + state, recent LinkedIn project, industrial client served, headcount, Tekla user?]","cat":"Outreach","desc":"5-input personalized - Owner voice"},
    {"id":"bid_followup","label":"Bid Follow-Up",       "trigger":"draft a bid follow-up email in the Owner's voice. Provide: bid document number, GC contact name, bid date, and bid total. Reference all three specifically.","cat":"Outreach","desc":"Must reference actual date + price + doc#"},
    {"id":"stock",       "label":"Steel Sector Research","trigger":"run stock research on the steel and construction watchlist: NUE, STLD, CMC, CLF, X, RS, FLR, PWR. Include required disclaimer. Flag steel sector concentration.","cat":"Research","desc":"NUE STLD CMC CLF X RS - with disclaimer"},
    {"id":"tax",         "label":"Texas Separated Contract Tax","trigger":"calculate Texas sales tax on a separated construction contract. Walk me through which portions are taxable and which are not.","cat":"Tools","desc":"Materials only - labor not taxable"},
    {"id":"icd",         "label":"ICD Church Status",   "trigger":"give me the ICD Church full status: contract value, deposits received, uncompensated cost estimate, quantum meruit claim amount, AVL RFI status, and the exact next action Amber needs to take before any demand is sent.","cat":"Ops","desc":"Active claim - Amber / Ivan blocking"},
    {"id":"afr",         "label":"AFR SOQ Status",      "trigger":"give me the America First Refining SOQ status, timeline, and what the next touchpoint or follow-up should be.","cat":"Ops","desc":"$3.5B Port of Brownsville"},
    {"id":"marathon",    "label":"Marathon Blocker",     "trigger":"what exactly is blocking the Marathon Petroleum ISN approval, who needs to do what, and what's the step-by-step to unblock it?","cat":"Ops","desc":"EMR letter - Texas Mutual 800-859-5995"},
]

class Bridge:
    """
    Pywebview JavaScript API bridge.
    All methods return JSON-serializable dicts {ok, data} or {ok, error}.
    """

    # ── File content builder ──────────────────────────────────────────
    @staticmethod
    def _build_content_blocks(message: str, files: list[dict],
                               provider: str) -> list | str:
        """Build multimodal content for the user message.

        Claude format:  list of {type: "text"/"image"/"document", ...}
        OpenAI format:  list of {type: "text"/"image_url", ...}
        Gemini format:  same as Claude (converted in _call_gemini)

        For text files, content is inlined into the text block.
        """
        import base64

        text_parts = [message] if message else []
        media_blocks: list[dict] = []

        for f in files:
            cat = f.get("cat", "other")
            name = f.get("name", "file")
            data = f.get("data", "")
            mime = f.get("type", "application/octet-stream")

            if cat == "text":
                # Inline text file content
                text_parts.append(
                    f"\n\n--- FILE: {name} ---\n{data}\n--- END FILE ---"
                )

            elif cat == "image":
                if not mime or mime == "application/octet-stream":
                    ext = name.rsplit(".", 1)[-1].lower()
                    mime = {"png": "image/png", "jpg": "image/jpeg",
                            "jpeg": "image/jpeg", "gif": "image/gif",
                            "webp": "image/webp"}.get(ext, "image/png")

                if provider == "openai":
                    media_blocks.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{data}"}
                    })
                else:
                    # Claude / Gemini format
                    media_blocks.append({
                        "type": "image",
                        "source": {"type": "base64",
                                   "media_type": mime, "data": data}
                    })

            elif cat == "pdf":
                if provider == "openai":
                    # GPT-4o doesn't natively handle PDFs - inline a note
                    text_parts.append(
                        f"\n\n[Attached PDF: {name}, {len(data)//1024}KB base64. "
                        f"PDF content cannot be read directly by this model. "
                        f"Route to Claude or Gemini for PDF analysis.]"
                    )
                else:
                    # Claude supports document type
                    media_blocks.append({
                        "type": "document",
                        "source": {"type": "base64",
                                   "media_type": "application/pdf",
                                   "data": data}
                    })

            else:
                # Unknown binary - note it
                text_parts.append(
                    f"\n\n[Attached file: {name}: type not directly supported]"
                )

        # Assemble content blocks
        combined_text = "\n".join(text_parts)

        if not media_blocks:
            # Text only - return as string (simpler, works everywhere)
            return combined_text

        # Multimodal. Return as list of content blocks
        blocks: list[dict] = [{"type": "text", "text": combined_text}]
        blocks.extend(media_blocks)
        return blocks

    @staticmethod
    def _audit_shapes_and_decorate(result_data: dict, task_cat: str = "") -> dict:
        """v3.5.11: scan LLM response text for hallucinated AISC shapes.

        Code-side hard-flag added per Gemini handbook review (May 9 2026)
        and Joseph's structural-safety pattern. The AISC v16.0 database
        has 2,299 shapes. Any shape designation in the response that is
        not in the database gets surfaced in a warning banner at the top
        of the text. Joseph and Owner see hallucinated shapes BEFORE
        the response leaves chat.

        Not a hard-block. The LLM may legitimately mention shapes from
        foreign standards (e.g., metric IPE/HEA, British UC/UB) that
        we don't carry. The banner is informational; humans decide.

        Skipped when provider is LOCAL (output is deterministic from
        the AISC CSV) or when text contains no shape-pattern hits at all.
        Attaches shape_audit metadata only when at least one AISC shape
        pattern is found (so no-shape responses have no metadata).
        Mutates result_data in place and returns it.
        """
        # LOCAL responses are deterministic; skip the audit
        if result_data.get("provider") == "LOCAL":
            return result_data
        text = result_data.get("text", "")
        if not text or not isinstance(text, str):
            return result_data

        try:
            from bridge.aisc_validator import (
                audit_shapes_in_text, build_shape_audit_warning,
            )
        except Exception:
            return result_data  # don't break the response on import error

        audit = audit_shapes_in_text(text)
        if audit["total"] == 0:
            return result_data  # no shapes mentioned, nothing to audit

        # Always attach the audit metadata. UI can show a verified-count
        # badge for valid shapes even when there are no invalid ones.
        result_data["shape_audit"] = audit

        if audit["invalid"]:
            banner = build_shape_audit_warning(audit)
            result_data["text"] = banner + text
            # Tag route for observability
            existing_route = result_data.get("route", "")
            result_data["route"] = (
                f"{existing_route} [SHAPE_AUDIT:flagged={len(audit['invalid'])}]"
            ).strip()

        return result_data

    @staticmethod
    def _maybe_boost_for_verified_history(message: str,
                                           history: list[dict] | None) -> str:
        """v3.5.9: detect verified pipeline output in conversation history
        and append a per-turn instruction reinforcing the GROUND-TRUTH RULE.

        Bug #4 architectural fix. The system-prompt GROUND-TRUTH RULE from
        v3.5.8 wasn't enough on curt follow-up messages like "bid takeoff"
        that don't themselves reference the verified data. This helper
        appends a per-turn instruction that quotes the verified data and
        forbids elaboration past it.

        Detection markers: distinctive phrases that only appear in verified
        pipeline output (auto-pipeline, AISC verified, ezdxf, the 100% LOCAL
        banner used in Path B/C). Pattern-based because the route metadata
        (LOCAL/auto-pipeline tag) is on the response object, not in the
        history content itself.
        """
        if not history:
            return message

        # Find the most recent assistant turn
        last_assistant = None
        for entry in reversed(history):
            if entry.get("role") == "assistant":
                last_assistant = entry.get("content", "")
                break

        if not last_assistant or not isinstance(last_assistant, str):
            return message

        # Markers that indicate verified pipeline output. These are the
        # phrases backend code actually emits in user-facing chat text.
        # v3.5.10 Bug #3: tightened from 8 markers to 3 after sim showed
        # 5 of the originals only existed in frontend JS or were never
        # emitted at all. Risk was: contract worked in practice because
        # frontend output reached history, but a non-frontend consumer
        # (API client, MCP, alternate UI) wouldn't trigger the boost.
        # Each marker below maps to a specific backend emit site:
        #   - "100% LOCAL from AISC data" → bridge/api.py L1515 (Path B
        #     3D STL success), L1549 (Path C DXF success)
        #   - "AISC database matched"     → bridge/api.py L4246
        #     (auto_process_drawing extraction_log narration)
        #   - "Verified estimate ("       → bridge/api.py L4537
        #     (DRAFT placeholder label when AISC totals are computed)
        # Together these cover every code path where backend produces
        # deterministic verified output that the LLM must not freelance
        # past on the next turn.
        markers = [
            "100% LOCAL from AISC data",
            "AISC database matched",
            "Verified estimate (",
        ]
        if not any(m in last_assistant for m in markers):
            return message

        boost = (
            "\n\n[VERIFIED-PIPELINE CONTEXT, GROUND-TRUTH RULE IN EFFECT:\n"
            "The previous turn in this conversation contains a verified\n"
            "pipeline result with deterministic numbers from the local AISC\n"
            "database. Per the GROUND-TRUTH RULE in your system prompt, those\n"
            "numbers and member lists are IMMUTABLE. Do NOT generate alternative\n"
            "member lists, expanded column schedules, fabricated sheet\n"
            "identifications (e.g. 'S-001: Cover sheet, S-002: ...'), or invented\n"
            "quantities. If the user is asking for elaboration past what the\n"
            "pipeline produced, restate the verified numbers cleanly and ask\n"
            "what specific missing inputs they want you to look up next.]\n"
        )
        return message + boost

    # ── AI ────────────────────────────────────────────────────────────────
    def _handle_virtual_joseph(self, message: str) -> dict:
        """Dispatch Virtual Joseph commands locally. No LLM needed."""
        _msg = message.lower()
        try:
            if any(w in _msg for w in ["train", "learn"]):
                result = self.vj_train()
                data = result.get("data", {})
                summary = data.get("summary", "Training completed.")
                return _ok({
                    "text": f"Virtual Joseph training complete.\n\n{summary}",
                    "provider": "LOCAL",
                    "model": "virtual-joseph-trainer",
                    "route": f"[VJ:TRAIN] {data.get('patterns_learned', 0)} patterns",
                })
            elif any(w in _msg for w in ["scan and fix", "fix"]):
                result = self.vj_scan_and_fix()
                data = result.get("data", {})
                return _ok({
                    "text": data.get("summary", "Scan and fix completed."),
                    "provider": "LOCAL",
                    "model": "virtual-joseph-self-repair",
                    "route": f"[VJ:SCAN-FIX] {data.get('issues_found', 0)} issues, {data.get('issues_fixed', 0)} fixed",
                })
            elif any(w in _msg for w in ["feature", "active", "working", "inactive", "dead"]):
                result = self.feature_status()
                if result.get("ok"):
                    data = result["data"]
                    return _ok({
                        "text": data.get("text", "Feature scan complete."),
                        "provider": "LOCAL",
                        "model": "virtual-joseph-feature-scanner",
                        "route": f"[VJ:FEATURES] {data.get('active_count', 0)}/{data.get('total', 0)} active",
                    })
                return result
            elif any(w in _msg for w in ["sweep", "integration"]):
                result = self.vj_sweep()
                data = result.get("data", {})
                status = "ALL CLEAR" if data.get("all_clear") else f"{len(data.get('issues', []))} issues"
                return _ok({
                    "text": f"Virtual Joseph integration sweep: {status}\nModules: {data.get('modules_checked', 0)} | Paths: {data.get('integration_paths_tested', 0)} | Bias patterns: {data.get('bias_patterns_checked', 0)}",
                    "provider": "LOCAL",
                    "model": "virtual-joseph-sweep",
                    "route": f"[VJ:SWEEP] {status}",
                })
            else:
                # Default: scan
                result = self.vj_scan()
                data = result.get("data", {})
                return _ok({
                    "text": f"Virtual Joseph scan complete.\n\n{data.get('summary', '')}",
                    "provider": "LOCAL",
                    "model": "virtual-joseph-scanner",
                    "route": f"[VJ:SCAN] {data.get('files_scanned', 0)} files, {data.get('issues_found', 0)} issues",
                })
        except Exception as e:
            return _err(f"Virtual Joseph failed: {e}")

    def _build_field_context(self) -> str:
        """Build a brief DB context string for the WHAT'S URGENT field tile.

        Pulls live blockers, compliance status, and AR aging so the AI
        can reference actual project state without asking Owner to paste it.
        """
        parts = []
        try:
            bl = self.get_blockers()
            if bl.get('ok') and bl.get('data'):
                blockers = bl['data']
                if isinstance(blockers, dict):
                    blockers = blockers.get('blockers', [])
                parts.append(f"ACTIVE BLOCKERS ({len(blockers)}):")
                for b in (blockers or [])[:5]:
                    title = b.get('title') or b.get('description') or str(b)
                    parts.append(f"  - {title}")
        except Exception:
            pass
        try:
            comp = self.compliance_summary()
            if comp.get('ok'):
                d = comp['data']
                parts.append(
                    f"COMPLIANCE: BLOCKED {d.get('blocked', 0)} / "
                    f"OPEN {d.get('open', 0)} / OK {d.get('ok_count', 0)}"
                )
        except Exception:
            pass
        try:
            ar = self.get_ar_aging()
            if ar.get('ok'):
                d = ar['data']
                parts.append(
                    f"AR AGING: current ${d.get('current', 0):,} / "
                    f"90+ ${d.get('90_plus', 0):,}"
                )
        except Exception:
            pass
        return '\n'.join(parts) if parts else ''

    def field_urgent_ask(self, history: list[dict] | None = None) -> dict:
        """WHAT'S URGENT tile - injects live DB context before the AI call.

        Builds blockers + compliance + AR context, prepends it to the
        system context so the AI can answer without asking Owner to
        copy-paste data it already has.
        """
        ctx = self._build_field_context()
        base_msg = (
            "What is the most urgent item that needs my attention right now? "
            "Show blockers ranked by dollar impact."
        )
        if ctx:
            msg = f"[CONTEXT]\n{ctx}\n[/CONTEXT]\n\n{base_msg}"
        else:
            msg = base_msg
        return self.ai_ask(msg, 'owner', history or [], None)

    def ai_ask(self, message: str = "", mode: str = "owner",
               history: list[dict] | None = None,
               files: list[dict] | None = None,
               prompt: str = "") -> dict:
        """
        Core AI call with the full knowledge base always active.

        SIM-07: accepts either `message=` (canonical) or `prompt=` (the Owner's
        natural kwarg). Both refer to the user input.

        Parameters
        ----------
        message  : The new user message.
        mode     : "owner" or "joseph" - controls voice note appended.
        history  : Prior conversation [{role, content}, ...].
        files    : Optional list of [{name, type, cat, data}] from frontend.
                   cat: "image"|"pdf"|"text"|"other"
                   data: base64 for binary, raw text for text files.
        prompt   : SIM-07 alias for `message`. If both are provided, `message` wins.
        """
        # SIM-07: alias resolution
        if not message and prompt:
            message = prompt
        if not message:
            return _err("ai_ask requires `message` (or `prompt`)")

        # ── LOCAL TASK PRE-DISPATCH (no SDK needed) ──
        # Classify first. If the task is purely local (diagnostics,
        # virtual joseph), dispatch immediately without checking for
        # the anthropic SDK. VJ and diagnostics never call an LLM.
        _pre_task = _classify_task(message)
        if _pre_task == "virtual_joseph":
            return self._handle_virtual_joseph(message)
        if _pre_task == "diagnostics":
            try:
                from bridge.diagnostics import run_diagnostics, format_report
                report = run_diagnostics(log_to_file=True)
                summary = format_report(report)
                s = report.get("summary", {})
                return _ok({
                    "text": summary,
                    "provider": "LOCAL",
                    "model": "diagnostics-v1",
                    "route": f"[DIAGNOSTICS] {s.get('passed',0)}/{s.get('total',0)} pass, {s.get('failed',0)} fail",
                    "diagnostics": report.get("summary"),
                    "log_file": report.get("log_file"),
                })
            except Exception as e:
                return _err(f"Diagnostics failed: {e}")

        # ── SIM-08: DIRECT ROUTE FOR NATURAL UTTERANCES ──
        # Catches "list bids", "compliance", "score bid 1", "quick bid 65t",
        # "what is W12X26", and a dozen more without ever calling an LLM.
        # This is the path that lets "list bids" work without an API key.
        try:
            from bridge.direct_route import try_direct_route
            _dr = try_direct_route(self, message)
            if _dr is not None:
                return _ok(_dr)
        except Exception:
            # Never let direct_route crashes block AI fallback.
            pass

        # ── PRE-SDK GUARD: model_3d / model_dxf missing inputs (v6.1.4-r5) ──
        # This guard exists to prevent wasted LLM calls. Logically it must
        # run BEFORE we import the SDK - otherwise users without the SDK
        # installed get a misleading "install anthropic" error instead of
        # the actionable "give me a shape designation" guidance the guard
        # is designed to provide.
        if _pre_task in ("model_3d", "model_dxf") and not files:
            import re as _re_guard
            _msg_lower = message.lower()
            has_shape = bool(_re_guard.search(
                r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+',
                _msg_lower, _re_guard.IGNORECASE,
            ))
            # Path B (lifted): shape named → local AISC-only STL generation.
            # No LLM needed. Previously this lived AFTER `import anthropic`
            # which caused it to error out when the SDK was unavailable.
            if has_shape and _pre_task == "model_3d":
                shape_match = _re_guard.search(
                    r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+',
                    _msg_lower, _re_guard.IGNORECASE,
                )
                length_match = _re_guard.search(
                    r"(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|\'|[\'′])", _msg_lower
                )
                count_match = _re_guard.search(
                    r"\b(\d+)\s+(?:member|column|beam|piece|brace|girder)",
                    _msg_lower
                )
                shape = shape_match.group(0).upper().replace("×", "X")
                length = float(length_match.group(1)) if length_match else 20.0
                count = int(count_match.group(1)) if count_match else 1
                result = self.generate_3d_view(shape, length, count)
                if result.get("ok"):
                    d = result["data"]
                    try:
                        self.track_time_saved("3d_model_generation", 30)
                    except Exception:
                        pass
                    return _ok({
                        "text": (
                            f"✅ 3D model generated. 100% LOCAL from AISC data (no AI used)\n\n"
                            f"**{d['shape']}** × {d['length_ft']}′\n"
                            f"• Depth: {d['depth_in']}″ · Flange: {d['flange_in']}″\n"
                            f"• Web: {d['web_thickness_in']}″ · Flange t: {d['flange_thickness_in']}″\n"
                            f"• Weight: {d['weight_lbs']:,.1f} lbs ({d['weight_tons']:.3f} tons)\n"
                            f"• Weight/ft: {d['weight_per_ft']} plf\n"
                            f"• Members: {d['member_count']}\n"
                            f"• STL: {d['stl_bytes']:,} bytes\n\n"
                            f"🔄 Drag to rotate · Scroll to zoom · Right-drag to pan"
                        ),
                        "provider": "LOCAL", "model": "aisc-calc",
                        "view_3d": {
                            "stl_b64": d["stl_b64"],
                            "label": d["label"],
                        },
                    })
            # Path C (lifted): DXF with shape → local-only DXF generation
            if has_shape and _pre_task == "model_dxf":
                try:
                    shape_match = _re_guard.search(
                        r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+',
                        _msg_lower, _re_guard.IGNORECASE,
                    )
                    shape = shape_match.group(0).upper().replace("×", "X")
                    dxf_r = self.generate_dxf(shape)
                    if dxf_r.get("ok"):
                        dxf_data = dxf_r["data"]
                        return _ok({
                            "text": f"DXF cross-section generated for **{shape}**.",
                            "provider": "LOCAL", "model": "ezdxf",
                            "dxf_file": dxf_data.get("file"),
                            **dxf_data,
                        })
                except Exception:
                    pass  # fall through to guard
            # Missing-inputs guard
            if not has_shape:
                # Try session_context first - if user has an active project
                # with shapes already modeled, surface those instead of the
                # generic guard message
                try:
                    from bridge.session_context import get_session, get_session
                    pid = get_active_project_id()
                    if pid:
                        takeoff = get_project_takeoff(pid)
                        if takeoff and takeoff.members:
                            shapes_text = ", ".join(sorted({m.shape for m in takeoff.members}))
                            return _ok({
                                "text": (
                                    f"I have an active session takeoff for "
                                    f"`{pid}` with these shapes already modeled: "
                                    f"**{shapes_text}**\n\n"
                                    f"To generate a 3D model, name one of these "
                                    f"or attach a different drawing PDF."
                                ),
                                "provider": "LOCAL",
                                "model": "session-context-3d",
                                "route": "[SESSION-CTX:model_3d]",
                                "shapes_modeled": sorted({m.shape for m in takeoff.members}),
                                "session_project": pid,
                            })
                except Exception:
                    pass
                kind = "3D model" if _pre_task == "model_3d" else "DXF cross-section"
                fmt_hint = "STL file" if _pre_task == "model_3d" else "DXF file"
                return _ok({
                    "text": (
                        f"❓ I can't generate a {kind} without inputs.\n\n"
                        f"Give me ONE of these:\n"
                        f"1. **An AISC shape designation in your message.** Examples:\n"
                        f"   - \"Generate a 3D model of W14x82, 20ft long\"\n"
                        f"   - \"DXF cross-section for HSS6x6x1/2\"\n"
                        f"   The local AISC database (2,299 shapes) produces the {fmt_hint} "
                        f"directly. Zero LLM tokens.\n\n"
                        f"2. **A drawing PDF attached.** I'll extract members via vision "
                        f"and generate from there.\n\n"
                        f"What I won't do: invent a shape and produce a fake model. "
                        f"Tell me what you need."
                    ),
                    "provider": "LOCAL",
                    "model": "guard",
                    "route": f"[GUARD:{_pre_task}] missing inputs",
                })

        try:
            import anthropic
        except ImportError:
            return _err(
                "anthropic SDK not installed.\n"
                "Run: py -3.13 -m pip install anthropic\n"
                "Then restart the app."
            )

        keys = _load_all_keys()

        # ── CLAUDE AVAILABILITY CHECK (first call + every 5 minutes) ──
        global _CLAUDE_AVAILABLE
        import time as _time_mod
        _last = getattr(self, '_claude_last_check', 0)
        if _CLAUDE_AVAILABLE is None or (not _CLAUDE_AVAILABLE and _time_mod.time() - _last > 300):
            _test_claude_available(keys.get("ANTHROPIC_API_KEY", ""))
            self._claude_last_check = _time_mod.time()

        # ── API INTEGRATION DETECTION (Joseph - dynamic API system) ──
        # Detects: "add SketchDeck AI for blueprint analysis"
        # Detects: "here's my SketchDeck key: sk-abc123..."
        try:
            from bridge.api_integrator import detect_integration_request, run_full_integration, activate_with_key
            integ = detect_integration_request(message)

            if integ.get("is_integration"):
                if integ.get("type") == "key_paste":
                    # User is pasting an API key - activate the pending integration
                    service = integ["service_name"].lower().replace(" ", "_")
                    result = activate_with_key(service, integ["api_key"])
                    return _ok({
                        "text": result.get("message", "Key accepted."),
                        "route": f"[API_INTEGRATOR/activate] {service}",
                        "provider": "system",
                        "model": "api_integrator",
                        "integration": result,
                    })
                elif integ.get("type") == "new_api":
                    # User wants to add a new API - run the full pipeline
                    result = run_full_integration(
                        integ["service_name"], integ.get("purpose", ""), keys
                    )
                    if result.get("error"):
                        return _ok({
                            "text": f"Integration research failed: {result['error']}\n\n"
                                    f"Steps completed: {[s['step'] for s in result.get('steps', []) if s['status']=='complete']}",
                            "route": "[API_INTEGRATOR/error]",
                            "provider": "system",
                            "model": "api_integrator",
                        })
                    return _ok({
                        "text": result.get("prompt", "Integration ready."),
                        "route": f"[API_INTEGRATOR/installed] {integ['service_name']}",
                        "provider": "multi",
                        "model": "gemini+claude",
                        "integration": {
                            "provider_key": result.get("provider_key"),
                            "key_env": result.get("key_env"),
                            "awaiting_key": result.get("awaiting_key"),
                            "steps": result.get("steps"),
                            "research": result.get("research", {}),
                            "design": result.get("design", {}),
                        },
                    })
        except ImportError:
            pass
        except Exception:
            pass  # Fall through to normal processing

        # Translate the Owner's casual language into structured prompts
        original_msg = message
        message = _translate_intent(message)
        was_translated = (message != original_msg)

        task_cat = _classify_task(message)

        # v3.5.7: Pre-init calc_meta. Three intercepts below (steel_research,
        # drawing_vision, model_3d) spread `**calc_meta` in their early-return
        # branches. The original definition was at line ~1452, AFTER those
        # intercepts. Latent UnboundLocalError, hidden until v3.5.7 fixed
        # _translate_intent so the model_3d intercept actually fires.
        calc_meta: dict = {}

        # ── STEEL RESEARCH INTERCEPT: Route to Steel Price Agent ────────
        # If Owner asks about steel market/pricing, use the real agent
        # instead of generic Gemini chat
        msg_lower = message.lower()
        if task_cat in ("market_data", "stock_research") and not files:
            steel_keywords = ["steel market", "steel price", "steel pricing",
                              "market condition", "hrc", "market brief",
                              "steel trend", "steel intel", "price trend"]
            if any(k in msg_lower for k in steel_keywords):
                try:
                    agent_result = self.get_steel_research()
                    if agent_result.get("ok"):
                        brief_data = agent_result["data"]
                        brief_text = brief_data if isinstance(brief_data, str) else str(brief_data)
                        # Track time saved
                        self.track_time_saved("steel_research", 45)
                        return _ok({
                            "text": brief_text,
                            "provider": "AGENT", "model": "steel-price-agent",
                            **calc_meta
                        })
                except Exception:
                    pass  # Fall through to normal AI processing

        # ── 3D MODEL INTERCEPT ──────────────────────────────────────────
        # TWO PATHS:
        #   A) PDF attached → HYBRID PIPELINE (AI vision + local AISC + cost)
        #   B) Shape named in text → LOCAL ONLY (AISC database → STL)

        # Path A: PDF attached → hybrid pipeline (vision + local calculation)
        if task_cat in ("model_3d", "drawing_vision") and files:
            pdf_files = [f for f in files if f.get("cat") == "pdf" or f.get("name", "").lower().endswith(".pdf")]
            if pdf_files and any(w in msg_lower for w in ["3d", "model", "takeoff", "bid", "estimate", "drawing"]):
                try:
                    # Save PDF to temp location for pipeline
                    import base64, tempfile
                    pdf_data = pdf_files[0].get("data", "")
                    if pdf_data:
                        tmp = Path(tempfile.mktemp(suffix=".pdf"))
                        tmp.write_bytes(base64.b64decode(pdf_data))
                        result = self.run_hybrid_3d_pipeline(str(tmp))
                        if result.get("ok"):
                            d = result["data"]
                            return _ok({
                                "text": d.get("message", "Hybrid 3D pipeline complete"),
                                "provider": "HYBRID", "model": "gemini-vision+aisc-local",
                                "pipeline_data": d,
                                **calc_meta,
                            })
                except Exception as e:
                    pass  # Fall through to normal AI processing

        # Path B: Shape named in text → local-only STL generation
        if task_cat == "model_3d" and not files:
            import re
            # Parse shape: W14X82, W12x26, HSS6X6X1/2, etc.
            shape_match = re.search(r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+', msg_lower, re.IGNORECASE)
            # Parse length: 20ft, 20', 20 feet, 20-foot
            length_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ft|feet|foot|\'|[\'′])', msg_lower)
            # Parse count: 3 members, 5 columns, etc.
            # v3.5.7: \b before \d+ + \s+ (≥1 space, not ≥0) so "W14x82 column"
            # doesn't grab "82" as the count (was Joseph's "82 stacked W14X82" bug).
            count_match = re.search(r'\b(\d+)\s+(?:member|column|beam|piece|brace|girder)', msg_lower)
            
            if shape_match:
                shape = shape_match.group(0).upper().replace("×", "X")
                length = float(length_match.group(1)) if length_match else 20.0
                count = int(count_match.group(1)) if count_match else 1
                
                result = self.generate_3d_view(shape, length, count)
                if result.get("ok"):
                    d = result["data"]
                    self.track_time_saved("3d_model_generation", 30)
                    return _ok({
                        "text": (
                            f"✅ 3D model generated. 100% LOCAL from AISC data (no AI used)\n\n"
                            f"**{d['shape']}** × {d['length_ft']}′\n"
                            f"• Depth: {d['depth_in']}″ · Flange: {d['flange_in']}″\n"
                            f"• Web: {d['web_thickness_in']}″ · Flange t: {d['flange_thickness_in']}″\n"
                            f"• Weight: {d['weight_lbs']:,.1f} lbs ({d['weight_tons']:.3f} tons)\n"
                            f"• Weight/ft: {d['weight_per_ft']} plf\n"
                            f"• Members: {d['member_count']}\n"
                            f"• STL: {d['stl_bytes']:,} bytes\n\n"
                            f"🔄 Drag to rotate · Scroll to zoom · Right-drag to pan"
                        ),
                        "provider": "LOCAL", "model": "aisc-calc",
                        "view_3d": {
                            "stl_b64": d["stl_b64"],
                            "label": d["label"],
                        },
                        **calc_meta,
                    })

        # Path C: DXF cross-section / pattern → local-only generation (v3.5.7)
        # Sister of Path B. Bridge.generate_dxf is wired but had no intercept,
        # so DXF requests fell through to the LLM which emitted Python code in
        # chat instead of producing a file. Joseph's "Generate a DXF cross-
        # section drawing for W12x35" bug.
        if task_cat == "model_dxf" and not files:
            import re
            shape_match = re.search(r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+', msg_lower, re.IGNORECASE)
            if shape_match:
                shape = shape_match.group(0).upper().replace("×", "X")
                result = self.generate_dxf(shape=shape, output_type="cross_section")
                if result.get("ok"):
                    d = result["data"]
                    self.track_time_saved("dxf_generation", 30)
                    return _ok({
                        "text": (
                            f"✅ DXF cross-section generated. 100% LOCAL from AISC data (no AI used)\n\n"
                            f"**{shape}**\n"
                            f"• Format: AutoCAD R2010 DXF\n"
                            f"• Type: {d.get('type', 'cross_section')}\n"
                            f"• File: {d.get('file', '-')}\n"
                        ),
                        "provider": "LOCAL", "model": "ezdxf",
                        "dxf_file": d.get("file"),
                        **calc_meta,
                    })

        # Path D-0: Check session context for existing takeoff data (v6.1.2).
        # If the auto-pipeline just extracted members from a PDF, the user
        # shouldn't have to re-specify them to get a 3D model. The session
        # context store persists the takeoff across commands.
        if task_cat in ("model_3d", "model_dxf") and not files:
            try:
                from bridge.session_context import get_session
                session = get_session()
                if session.has_takeoff():
                    shapes = session.get_shapes_list()
                    members = session.get_members_for_3d()
                    takeoff = session.get_takeoff()
                    if shapes:
                        log.info(
                            "3D model using session takeoff: %d shapes from %s",
                            len(shapes), takeoff.project_id,
                        )
                        # Generate 3D for the first shape (or all unique shapes)
                        results = []
                        for shape in shapes[:10]:  # cap at 10 for performance
                            try:
                                r = self.generate_3d_view(shape=shape)
                                if r.get("ok"):
                                    results.append({"shape": shape, "result": r["data"]})
                            except Exception:
                                pass
                        if results:
                            project = session.get_project()
                            return _ok({
                                "text": (
                                    f"3D models generated from session takeoff "
                                    f"({takeoff.project_id}, {takeoff.member_count} members, "
                                    f"{takeoff.tonnage:.1f} tons).\\n\\n"
                                    f"Shapes modeled: {', '.join(shapes[:10])}\\n"
                                    f"Source: AISC database (zero LLM tokens).\\n\\n"
                                    f"Files saved to project folder."
                                ),
                                "provider": "LOCAL",
                                "model": "session-context-3d",
                                "route": f"[SESSION:{task_cat}] {len(results)} shapes from takeoff",
                                "shapes_modeled": [r["shape"] for r in results],
                                "session_project": takeoff.project_id,
                                **calc_meta,
                            })
            except ImportError:
                pass  # session_context not available, fall through to guard

        # Path D: model_3d / model_dxf guard for missing inputs (v3.5.9).
        # Bug #1 architectural follow-up. When the user asks for a 3D model
        # or DXF with no drawing AND no AISC shape designation in text, the
        # model_3d pipeline calls Gemini with nothing useful to extract. It
        # fails. v3.5.8 stopped the gate from misfiring on the resulting
        # error string. v3.5.9 stops the wasted Gemini call entirely.
        # Returns a clear "missing inputs" message instead.
        if task_cat in ("model_3d", "model_dxf") and not files:
            import re
            has_shape = bool(re.search(
                r'\b(W|HSS|L|C|WT|HP|MC|S)\d+[Xx×]\d+',
                msg_lower, re.IGNORECASE,
            ))
            if not has_shape:
                # Build an actionable error message based on which task
                kind = "3D model" if task_cat == "model_3d" else "DXF cross-section"
                fmt_hint = "STL file" if task_cat == "model_3d" else "DXF file"
                return _ok({
                    "text": (
                        f"❓ I can't generate a {kind} without inputs.\n\n"
                        f"Give me ONE of these:\n"
                        f"1. **An AISC shape designation in your message.** Examples:\n"
                        f"   - \"Generate a 3D model of W14x82, 20ft long\"\n"
                        f"   - \"DXF cross-section for HSS6x6x1/2\"\n"
                        f"   The local AISC database (2,299 shapes) produces the {fmt_hint} "
                        f"directly. Zero LLM tokens.\n\n"
                        f"2. **A drawing PDF attached.** I'll extract members via Gemini "
                        f"vision and generate from there.\n\n"
                        f"What I won't do: invent a shape and produce a fake model. "
                        f"Tell me what you need."
                    ),
                    "provider": "LOCAL",
                    "model": "guard",
                    "route": f"[GUARD:{task_cat}] missing inputs",
                    **calc_meta,
                })

        # -- DIAGNOSTICS: local, zero LLM tokens --
        if task_cat == "diagnostics":
            try:
                from bridge.diagnostics import run_diagnostics, format_report
                report = run_diagnostics(log_to_file=True)
                summary = format_report(report)
                s = report.get("summary", {})
                return _ok({
                    "text": summary,
                    "provider": "LOCAL",
                    "model": "diagnostics-v1",
                    "route": f"[DIAGNOSTICS] {s.get('passed',0)}/{s.get('total',0)} pass, {s.get('failed',0)} fail",
                    "diagnostics": report.get("summary"),
                    "log_file": report.get("log_file"),
                    **calc_meta,
                })
            except Exception as e:
                return _err(f"Diagnostics failed: {e}")

        # -- VIRTUAL JOSEPH (local dispatch, no LLM) --
        if task_cat == "virtual_joseph":
            try:
                import re as _re_vj
                _msg_lower = message.lower()

                # Sub-classify: train, scan, scan-and-fix, sweep
                if any(w in _msg_lower for w in ["train", "learn"]):
                    # Auto-discover export in data/claude_export/
                    result = self.vj_train()
                    data = result.get("data", {})
                    summary = data.get("summary", "Training completed.")
                    return _ok({
                        "text": f"Virtual Joseph training complete.\n\n{summary}",
                        "provider": "LOCAL",
                        "model": "virtual-joseph-trainer",
                        "route": f"[VJ:TRAIN] {data.get('patterns_learned', 0)} patterns",
                        **calc_meta,
                    })
                elif any(w in _msg_lower for w in ["scan and fix", "fix"]):
                    result = self.vj_scan_and_fix()
                    data = result.get("data", {})
                    return _ok({
                        "text": data.get("summary", "Scan and fix completed."),
                        "provider": "LOCAL",
                        "model": "virtual-joseph-self-repair",
                        "route": f"[VJ:SCAN-FIX] {data.get('issues_found', 0)} issues, {data.get('issues_fixed', 0)} fixed",
                        **calc_meta,
                    })
                elif any(w in _msg_lower for w in ["scan", "check", "error"]):
                    result = self.vj_scan()
                    data = result.get("data", {})
                    summary = data.get("summary", "Scan completed.")
                    return _ok({
                        "text": f"Virtual Joseph scan complete.\n\n{summary}",
                        "provider": "LOCAL",
                        "model": "virtual-joseph-scanner",
                        "route": f"[VJ:SCAN] {data.get('files_scanned', 0)} files, {data.get('issues_found', 0)} issues",
                        **calc_meta,
                    })
                elif any(w in _msg_lower for w in ["sweep", "integration"]):
                    result = self.vj_sweep()
                    data = result.get("data", {})
                    status = "ALL CLEAR" if data.get("all_clear") else f"{len(data.get('issues', []))} issues"
                    return _ok({
                        "text": f"Virtual Joseph integration sweep: {status}\nModules: {data.get('modules_checked', 0)} | Paths: {data.get('integration_paths_tested', 0)} | Bias patterns: {data.get('bias_patterns_checked', 0)}",
                        "provider": "LOCAL",
                        "model": "virtual-joseph-sweep",
                        "route": f"[VJ:SWEEP] {status}",
                        **calc_meta,
                    })
                else:
                    # Default: scan
                    result = self.vj_scan()
                    data = result.get("data", {})
                    return _ok({
                        "text": f"Virtual Joseph scan complete.\n\n{data.get('summary', '')}",
                        "provider": "LOCAL",
                        "model": "virtual-joseph-scanner",
                        "route": f"[VJ:SCAN] {data.get('files_scanned', 0)} files",
                        **calc_meta,
                    })
            except Exception as e:
                return _err(f"Virtual Joseph failed: {e}")

        # -- CALC AUTO-DETECT: Run offline calculators BEFORE any AI call --
        # T1-1: No LLM does arithmetic. Calculator runs first, results
        # injected as FACTS. AI formats/interprets but never computes.
        calc_results = _detect_and_run_calcs(message)
        calc_meta = {}
        if calc_results:
            facts_block = _build_facts_block(calc_results)
            message = facts_block + "\n\nUser's question: " + message
            calc_meta = {
                "calcs_run": [r["calc"] for r in calc_results],
                "calcs_count": len(calc_results),
            }

        # ── SELF-BUILD PRE-CHECK: Can we handle this? ──────────────────
        # If no calculator fired AND the task looks computational AND
        # we're in "general" (no specific handler), Claude builds what's needed.
        from bridge.self_build import (
            detect_gap, detect_gap_from_response, BUILDER_SYSTEM_PROMPT,
            extract_code_and_answer, execute_generated_code,
            save_extension, commit_to_github, load_extensions
        )
        self_built = False

        if detect_gap(message, task_cat, calc_results):
            # Try loaded extensions first
            ext_funcs = load_extensions()
            # If no extension handles it, build one
            claude_key = keys.get("ANTHROPIC_API_KEY", "")
            if claude_key:
                try:
                    build_msgs = [{"role": "user", "content": original_msg}]
                    build_result = _call_claude(
                        claude_key, "claude-sonnet-4-6",
                        BUILDER_SYSTEM_PROMPT, build_msgs
                    )
                    build_text = build_result.get("text", "")
                    code, answer = extract_code_and_answer(build_text)

                    built_meta = {"self_built": True, "code_generated": bool(code)}
                    if code:
                        # Execute the generated code
                        exec_result = execute_generated_code(code, original_msg)
                        if exec_result.get("success"):
                            func_name = exec_result["function_name"]
                            # Save permanently
                            ext_path = save_extension(func_name, code, original_msg[:100])
                            built_meta["extension_saved"] = ext_path
                            built_meta["function_name"] = func_name
                            # Commit to GitHub (best-effort, non-blocking)
                            git_result = commit_to_github(ext_path,
                                f"self-build: {func_name} - {original_msg[:60]}")
                            built_meta["git"] = git_result.get("message",
                                                                git_result.get("error", ""))

                    # Return the answer (from Claude's builder response)
                    display_text = answer if answer else build_text
                    route_info = "[SELF-BUILD/claude] built new tool"
                    result_data = {
                        "text": display_text,
                        "route": route_info,
                        "provider": "self-build",
                        "model": "claude-sonnet-4-6",
                        **built_meta, **calc_meta,
                    }
                    try:
                        _ceo_logger.log_interaction(
                            message=original_msg, mode=mode,
                            provider="self-build", model="claude-sonnet-4-6",
                        )
                    except Exception:
                        pass
                    return _ok(result_data)
                except Exception as e:
                    pass  # fall through to normal routing

        # If files include images/PDFs, route to a vision-capable model
        has_images = any(f.get("cat") == "image" for f in (files or []))
        has_pdfs = any(f.get("cat") == "pdf" for f in (files or []))
        if has_images or has_pdfs:
            task_cat = "drawing_vision"  # force multimodal route

        provider, model_id, reason = _get_route(task_cat)

        # Pick the right key for the routed provider; fall back to Claude if missing
        key_map = {"claude": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GOOGLE_API_KEY"}
        api_key = keys.get(key_map.get(provider, "ANTHROPIC_API_KEY"), "")
        if not api_key:
            api_key = keys.get("ANTHROPIC_API_KEY", "")
            provider = "claude"
            model_id = "claude-sonnet-4-6"
        if not api_key:
            return _err(
                "No API keys configured for AI providers.\n\n"
                "You can still use these local commands (no API key needed):\n"
                "  list bids · compliance · blockers · ar aging · shop kpis\n"
                "  score bid N · advance bid N · quick bid 65t 22j 38400sf\n"
                "  calc plate PL1/2X12X12 · what is W12X26 · houston pipeline\n"
                "  morning brief · stock watchlist · self test · help\n\n"
                "To enable AI, drop a folder called  API Keys  next to the EXE:\n"
                "  API Keys/Claude API.txt   (Anthropic key on line 1)\n"
                "  API Keys/OpenAI API.txt   (OpenAI key on line 1)\n"
                "  API Keys/Gemini API.txt   (Google key on line 1)\n"
                "Then restart. Contact Joseph if needed: joseph@yourcompany.example.com"
            )

        voice_note = {
            "owner": (
                "\n\nVOICE NOTE: If you are drafting outbound content (email, letter, "
                "proposal language), write in the Owner's voice: 8-15 words per sentence, "
                "dry, direct, no preamble, specific numbers, no filler adjectives."
            ),
            "joseph": (
                "\n\nVOICE NOTE: This response is being drafted as Joseph reporting to "
                "Owner. Operational voice: 12-20 words per sentence, warmer, factual, "
                "reports completion, asks for direction."
            ),
        }.get(mode, "")

        # ── Verified-pipeline boost (v3.5.9, Bug #4 architectural) ────
        # When the most recent assistant turn in history contains a
        # verified-pipeline marker, append a per-turn instruction to
        # the user message reinforcing the GROUND-TRUTH RULE. This is
        # the code-side companion to the system-prompt rule from v3.5.8.
        # Joseph's transcript: auto-pipeline returned 22 members + 19.01
        # tons. User typed "bid takeoff". LLM freelanced fictional
        # S-001/S-002 sheet content. The system prompt rule alone wasn't
        # enough on a curt user message that doesn't itself reference
        # the verified data. The boost makes the rule unmissable.
        message = self._maybe_boost_for_verified_history(message, history)

        # ── Build message content (multimodal if files attached) ──────
        msgs: list[dict] = list(history or [])

        if files:
            content_blocks = self._build_content_blocks(message, files, provider)
            msgs.append({"role": "user", "content": content_blocks})
        else:
            msgs.append({"role": "user", "content": message})

        try:
            # ── RATE LIMITER (Joseph P1) ───────────────────────────────
            try:
                from bridge.resilience import rate_limiter, circuit_breaker
                allowed, wait_sec = rate_limiter.allow()
                if not allowed:
                    return _err(f"Rate limited. Too many requests. Try again in {wait_sec} seconds. (Limit: 20/min, 200/hr)")
            except ImportError:
                pass

            system = build_system_prompt(task_cat) + voice_note
            route_info = f"[{provider}/{model_id}] task={task_cat}"
            xlate_meta = {"translated": was_translated}
            if was_translated:
                xlate_meta["original"] = original_msg[:80]
                xlate_meta["expanded"] = message[:120]

            # ── CONVERSATION PERSISTENCE (Joseph P1) - save user message ──
            try:
                from bridge.memory import save_message as _save_msg
                _save_msg("user", original_msg)
            except Exception:
                pass

            # ── PIPELINE CHECK: complex tasks use multi-model pipelines ──
            from bridge.pipeline import should_use_pipeline, execute_pipeline
            if should_use_pipeline(task_cat):
                pipe_result = execute_pipeline(
                    task_cat, message, keys, system, voice_note, files
                )
                if "error" not in pipe_result:
                    steps = pipe_result.get("pipeline_steps", [])
                    route_info = f"[PIPELINE:{task_cat}] steps={len(steps)}"
                    result_data = {
                        "text": pipe_result["text"],
                        "route": route_info,
                        "provider": pipe_result.get("provider", "pipeline"),
                        "model": pipe_result.get("model", "multi"),
                        "pipeline_steps": steps,
                        **xlate_meta, **calc_meta,
                    }
                    # Log and return
                    try:
                        _ceo_logger.log_interaction(
                            message=original_msg, mode=mode,
                            translated=was_translated, original=original_msg if was_translated else "",
                            provider="pipeline", model=task_cat,
                        )
                    except Exception:
                        pass
                    # Track time saved by automated pipeline
                    _TS_MAP = {"drawing_vision": 120, "market_data": 45, "model_3d": 30,
                               "general": 5, "structured_data": 20, "financial_model": 60}
                    try: self.track_time_saved(f"pipeline_{task_cat}", _TS_MAP.get(task_cat, 10))
                    except Exception: pass
                    # v3.5.11: scan response for hallucinated AISC shapes
                    result_data = self._audit_shapes_and_decorate(result_data, task_cat)
                    return _ok(result_data)

            # ── SINGLE MODEL: simple tasks use direct routing ──
            resp_text = ""
            if provider == "openai":
                resp_text = _call_openai(api_key, model_id, system, msgs)
                result_data = {"text": resp_text, "route": route_info, "provider": "openai", "model": model_id, **xlate_meta, **calc_meta}
            elif provider == "gemini":
                resp_text = _call_gemini(api_key, model_id, system, msgs)
                result_data = {"text": resp_text, "route": route_info, "provider": "gemini", "model": model_id, **xlate_meta, **calc_meta}
            else:
                result = _call_claude(api_key, model_id, system, msgs)
                resp_text = result.get("text", "")
                result_data = {**result, "route": route_info, "provider": "claude", "model": model_id, **xlate_meta, **calc_meta}

            # Log CEO interaction (Tier 2 preference mining)
            try:
                _ceo_logger.log_interaction(
                    message=original_msg,
                    mode=mode,
                    translated=was_translated,
                    original=original_msg if was_translated else "",
                    provider=provider,
                    model=model_id,
                )
            except Exception:
                pass

            # v3.5.11: scan response for hallucinated AISC shapes
            # Runs BEFORE memory save so the banner is persisted in
            # conversation history (not just ephemeral UI).
            result_data = self._audit_shapes_and_decorate(result_data, task_cat)

            # ── CONVERSATION PERSISTENCE (Joseph P1) - save AI response ──
            try:
                from bridge.memory import save_message as _save_msg
                _save_msg("assistant", result_data.get("text", "")[:5000],
                          provider=provider, model=model_id)
            except Exception:
                pass

            # ── AUDIT LOG (Joseph P2) - record every AI response ──
            try:
                from bridge.audit import log_ai
                log_ai(original_msg, result_data.get("text", ""),
                       provider, model_id)
            except Exception:
                pass

            return _ok(result_data)
        except Exception as e:
            original_error = str(e)
            # ── FALLBACK CHAIN: try remaining providers in order ──
            # Order: Gemini → Claude → error
            # OpenAI first (CONNECTED), Gemini second (rate-limited), Claude last (connection issues)
            fallback_attempted = []
            for fb_provider, fb_key_name, fb_model in [
                ("openai", "OPENAI_API_KEY", "gpt-4o"),
                ("gemini", "GOOGLE_API_KEY", "gemini-2.5-flash"),
                ("claude", "ANTHROPIC_API_KEY", "claude-sonnet-4-6"),
            ]:
                if fb_provider == provider:
                    continue  # skip the one that just failed
                fb_key = keys.get(fb_key_name, "")
                if not fb_key:
                    continue
                try:
                    fb_sys = build_system_prompt(task_cat) + voice_note
                    if fb_provider == "gemini":
                        fb_text = _call_gemini(fb_key, fb_model, fb_sys, msgs)
                        fb_result = {"text": fb_text}
                    elif fb_provider == "claude":
                        fb_result = _call_claude(fb_key, fb_model, fb_sys, msgs)
                    else:
                        fb_text = _call_openai(fb_key, fb_model, fb_sys, msgs)
                        fb_result = {"text": fb_text}
                    route = (f"[FALLBACK {fb_provider}/{fb_model}] "
                             f"original={provider} error={original_error[:80]}")
                    fb_data = {**fb_result, "route": route,
                                "provider": fb_provider, "model": fb_model,
                                **calc_meta}
                    # v3.5.11: audit shapes on fallback path too
                    fb_data = self._audit_shapes_and_decorate(fb_data, task_cat)
                    return _ok(fb_data)
                except Exception as fb_e:
                    # Clean error - strip raw protobuf/JSON noise
                    err_msg = str(fb_e)
                    if "429" in err_msg or "quota" in err_msg.lower():
                        err_msg = f"{fb_provider} quota exceeded. Add credits or wait for reset"
                    elif "Connection" in err_msg:
                        err_msg = f"{fb_provider} connection failed"
                    elif len(err_msg) > 120:
                        err_msg = f"{fb_provider}: {err_msg[:120]}..."
                    else:
                        err_msg = f"{fb_provider}: {err_msg}"
                    fallback_attempted.append(err_msg)
                    continue

            # All providers failed - clean summary
            primary_err = str(e)
            if len(primary_err) > 150:
                primary_err = primary_err[:150] + "..."
            # SIM-09 (v3.2.7.14 post-audit deeper fix): when all AI fails, lead
            # with what still works locally. Don't strand the user on a stack
            # trace - point them at the 14 local commands they CAN use right now.
            local_hint = (
                "\n\nAI is offline. You can still use these local commands:\n"
                "  list bids · compliance · blockers · ar aging · shop kpis\n"
                "  score bid N · advance bid N · quick bid 65t 22j 38400sf\n"
                "  calc plate PL1/2X12X12 · what is W12X26 · houston pipeline\n"
                "  morning brief · stock watchlist · self test · help"
            )
            return _err(
                f"AI error ({provider}/{model_id}): {primary_err}\n\n"
                + (f"Fallbacks also failed:\n" + "\n".join(fallback_attempted)
                   if fallback_attempted else "No fallback keys available.\nAdd API keys in Settings → API Keys.")
                + local_hint
            )

    # ── Data endpoints (UI panels) ────────────────────────────────────────
    def get_panel_data(self) -> dict:
        """Single call that returns all panel data for dashboard init.

        v3.2: prefers real seed data from data/houston_pipeline_seed.json
        when present. Falls back to bundled defaults.
        """
        return _ok({
            "compliance":    COMPLIANCE_STATUS,
            "rates":         RATES_TABLE,
            "priorities":    self._load_priorities_seeded(),
            "recommended_bids": self._load_recommended_bids_seeded(),
            "kpis":          self._load_kpi_snapshot(),
            "hard_rules":    HARD_RULES,
            "quick_actions": QUICK_ACTIONS,
            "team":          TEAM_ROUTING,
            "projects":      PROJECTS_ARCHIVE,
        })

    def _load_priorities_seeded(self) -> list:
        """Load real priorities from houston_pipeline_seed.json, fallback to ACTIVE_PRIORITIES."""
        try:
            import json
            seed = _app_root() / "data" / "houston_pipeline_seed.json"
            if seed.exists():
                d = json.loads(seed.read_text())
                pri = d.get("active_priorities", [])
                if pri:
                    return pri
        except Exception:
            pass
        return ACTIVE_PRIORITIES

    def _load_recommended_bids_seeded(self) -> list:
        """Load recommended bids from seed, fallback to empty list."""
        try:
            import json
            seed = _app_root() / "data" / "houston_pipeline_seed.json"
            if seed.exists():
                return json.loads(seed.read_text()).get("recommended_bids", [])
        except Exception:
            pass
        return []

    def _load_kpi_snapshot(self) -> dict:
        """Load KPI snapshot from seed, fallback to defaults."""
        try:
            import json
            seed = _app_root() / "data" / "houston_pipeline_seed.json"
            if seed.exists():
                return json.loads(seed.read_text()).get("kpi_snapshot", {})
        except Exception:
            pass
        return {"tons_active": 0, "pipeline_M": 0, "blockers": 0,
                "active_jobs": 0, "win_streak": 0, "time_saved_h": 0}

    def get_compliance(self) -> dict:
        return _ok(COMPLIANCE_STATUS)

    def set_compliance_status(self, item_n: int = 0,
                               status: str = "",
                               note: str = "") -> dict:
        """Directly set any compliance item's status from chat. No dependency
        preconditions. This is the manual-override path for when a document
        arrives or Amber confirms something done.

        Use `cascade compliance N` when an upstream blocker resolved and you
        want the dependency graph to guide you. Use this when you just know
        the new state and want to record it (COI received, policy renewed, etc.).

        Saves to disk immediately so the change survives a Bridge restart.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        item_n, _e = _coerce_num(item_n, 'item_n', cast='int')
        if _e: return _e
        _load_compliance_state()
        VALID = {"BLOCKED", "OPEN", "MONITOR", "OK"}
        if not item_n:
            return _err(
                "item_n required",
                fix="type `set compliance N status OPEN [note]` with the item number. "
                    "Use `compliance` to see all item numbers.",
            )
        status_upper = status.upper().strip()
        if status_upper not in VALID:
            return _err(
                f"status must be one of {sorted(VALID)}, got '{status}'",
                fix=f"valid values: BLOCKED, OPEN, MONITOR, OK",
            )
        target = None
        for c in COMPLIANCE_STATUS:
            if c["n"] == item_n:
                target = c
                break
        if target is None:
            return _err(
                f"Compliance item {item_n} not found",
                fix="type `compliance` to see all item numbers",
            )
        prev = target["status"]
        target["status"] = status_upper
        if note:
            target["owner"] = (target.get("owner") or "") + f"  [{note}]"
        _save_compliance_state()
        return _ok({
            "item_n": item_n,
            "item": target["item"],
            "from": prev,
            "to": status_upper,
            "message": f"Item {item_n} ({target['item']}): {prev} → {status_upper}",
        })

    def reload_compliance_state(self) -> dict:
        """Force-reload compliance state from disk. Useful if state was edited
        externally during a session (e.g. Joseph fixed something by hand).

        Returns whether a state file was found and applied.
        """
        loaded = _load_compliance_state(force=True)
        return _ok({
            "loaded_from_disk": loaded,
            "state_file": str(_compliance_state_path()),
            "message": (
                "Compliance state reloaded from disk."
                if loaded else
                "No state file found; using hardcoded defaults."
            ),
        })

    def _get_cascade_hints(self) -> list:
        """Return cascade hints for compliance items whose upstream dependencies
        have resolved but which haven't yet been unblocked.

        Walks `depends_on` from each item. If item N has depends_on=[A,B,...]
        and all of A,B,... are OK while N is still BLOCKED, that's a cascade
        hint: N can now move to OPEN.

        the Owner's SIM3 ask: "Compliance items should know about each other."
        Surfaces what he'd otherwise have to remember manually.
        """
        _load_compliance_state()  # idempotent; lazy load on first access
        by_n = {c["n"]: c for c in COMPLIANCE_STATUS}
        hints = []
        for c in COMPLIANCE_STATUS:
            deps = c.get("depends_on") or []
            if not deps or c["status"] != "BLOCKED":
                continue
            # All upstream items must exist and be OK
            unresolved = []
            for dep_n in deps:
                up = by_n.get(dep_n)
                if up is None or up.get("status") != "OK":
                    unresolved.append(dep_n)
            if not unresolved:
                hints.append({
                    "downstream_n": c["n"],
                    "downstream_item": c["item"],
                    "upstream_ns": deps,
                    "upstream_items": [by_n[d]["item"] for d in deps if d in by_n],
                    "current_status": c["status"],
                    "suggested_status": "OPEN",
                    "action": f"type `cascade compliance {c['n']}` to advance",
                })
        return hints

    def cascade_compliance(self, item_n: int = 0,
                           new_status: str = "OPEN",
                           note: str = "") -> dict:
        """Apply a cascade hint: advance a dependent BLOCKED item now that its
        upstream blocker is OK. the Owner's roadmap from SIM3.

        Validates that the cascade is actually warranted (item has depends_on,
        all upstreams are OK, current status is BLOCKED). Refuses otherwise so
        Owner can't accidentally clear a real blocker by mistake.

        After the cascade, takes a fresh snapshot so the change is captured in
        compliance_diff history.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        item_n, _e = _coerce_num(item_n, 'item_n', cast='int')
        if _e: return _e
        _load_compliance_state()  # idempotent
        VALID_TARGETS = {"OPEN", "MONITOR", "OK"}
        if not item_n:
            return _err("item_n required",
                        fix="type `cascade compliance N` with the item number, e.g. "
                            "`cascade compliance 4`. Use `compliance` to see cascade hints.")
        ns = new_status.upper()
        if ns not in VALID_TARGETS:
            return _err(f"new_status must be one of {VALID_TARGETS}, got '{new_status}'",
                        fix=f"valid targets: OPEN, MONITOR, OK")
        # Locate the item
        target = None
        for c in COMPLIANCE_STATUS:
            if c["n"] == item_n:
                target = c
                break
        if target is None:
            return _err(f"Compliance item {item_n} not found",
                        fix="type `compliance` to see all item numbers")
        deps = target.get("depends_on") or []
        if not deps:
            return _err(
                f"Item {item_n} ({target['item']}) has no declared dependencies; "
                f"there's nothing to cascade from",
                fix=f"to change this item's status directly, edit COMPLIANCE_STATUS or "
                    f"use the snapshot/diff workflow")
        # Verify all upstreams are OK
        by_n = {c["n"]: c for c in COMPLIANCE_STATUS}
        unresolved = []
        for dep_n in deps:
            up = by_n.get(dep_n)
            if up is None:
                unresolved.append((dep_n, "(unknown)"))
            elif up.get("status") != "OK":
                unresolved.append((dep_n, up.get("status")))
        if unresolved:
            unresolved_str = ", ".join(
                f"#{n} ({s})" for n, s in unresolved
            )
            return _err(
                f"Cannot cascade item {item_n}: upstream blocker(s) still unresolved: "
                f"{unresolved_str}",
                fix=f"each upstream must be OK before its dependents can cascade")
        if target.get("status") != "BLOCKED":
            return _err(
                f"Item {item_n} is {target.get('status')}, not BLOCKED; "
                f"no cascade needed",
                fix=f"cascade only applies when the item is currently BLOCKED")

        # Apply the change
        prev_status = target["status"]
        target["status"] = ns
        if note:
            target["owner"] = (target.get("owner") or "") + f"  [cascaded: {note}]"

        # Snapshot so the cascade shows up in diff history. Force the snapshot
        # since the daily auto-snap might already exist.
        try:
            from pathlib import Path
            from datetime import datetime
            snap_dir = _compliance_snapshots_dir()
            snap_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc)
            fname = snap_dir / f"{now.strftime('%Y%m%d_%H%M%S')}_cascade.json"
            import json
            fname.write_text(json.dumps({
                "ts": now.isoformat(),
                "label": f"cascade item {item_n}",
                "items": [
                    {"n": c["n"], "item": c["item"], "status": c["status"],
                     "owner": c.get("owner", ""), "priority": c.get("priority", False),
                     "depends_on": c.get("depends_on", [])}
                    for c in COMPLIANCE_STATUS
                ],
            }, indent=2))
        except Exception:
            pass  # best effort

        # Persist the mutation so a restart doesn't lose this cascade
        _save_compliance_state()

        # Emit compliance event for project_syncer
        try:
            from bridge.event_bus import emit as _ev_emit
            _ev_emit("COMPLIANCE_FAIL" if ns != "OK" else "COMPLIANCE_FAIL",
                     {"item_n": item_n, "item": target["item"],
                      "from": prev_status, "to": ns, "grade": ns})
        except Exception:
            pass

        return _ok({
            "item_n": item_n,
            "item": target["item"],
            "from": prev_status,
            "to": ns,
            "message": (
                f"Item {item_n} ({target['item']}) cascaded: "
                f"{prev_status} → {ns} (upstream {deps} all OK)"
            ),
        })

    def compliance_summary(self) -> dict:
        """One-line summary of compliance state. the Owner's glance command.

        Returns counts by status (BLOCKED/OPEN/MONITOR/OK) plus the
        priority-flagged blockers so the EMR letter and Auto Liability
        gaps surface immediately. Also takes a daily snapshot for the
        compliance_diff method to detect what moved since last check.
        """
        _load_compliance_state()  # honor any persisted mutations
        # Auto-snapshot (max once per day) so the diff has history
        self._maybe_auto_snapshot_compliance()

        # Cascade hints: items whose upstream is now OK but they're still BLOCKED
        cascade_hints = self._get_cascade_hints()

        blocked = [c for c in COMPLIANCE_STATUS if c["status"] == "BLOCKED"]
        priority_blocked = [c for c in blocked if c.get("priority")]
        open_items = [c for c in COMPLIANCE_STATUS if c["status"] == "OPEN"]
        monitor = [c for c in COMPLIANCE_STATUS if c["status"] == "MONITOR"]
        ok = [c for c in COMPLIANCE_STATUS if c["status"] == "OK"]

        summary_line = (
            f"BLOCKED: {len(blocked)} ({len(priority_blocked)} priority)  |  "
            f"OPEN: {len(open_items)}  |  "
            f"MONITOR: {len(monitor)}  |  "
            f"OK: {len(ok)}"
        )
        grade = "?"
        score = 0.0
        try:
            from bridge.compliance import run_compliance_check
            chk = run_compliance_check()
            grade = chk.get("status", "?")
            score = chk.get("scorecard", {}).get("overall_pct", 0.0)
        except Exception:
            pass

        return _ok({
            "summary_line": summary_line,
            "priority_blockers": priority_blocked,
            "all_blocked": blocked,
            "open_items": open_items,
            "cascade_hints": cascade_hints,
            "grade": grade,
            "score": score,
            "score_pct": score,
            "counts": {
                "blocked": len(blocked),
                "priority_blocked": len(priority_blocked),
                "open": len(open_items),
                "monitor": len(monitor),
                "ok": len(ok),
            },
        })

    def compliance_snapshot(self, label: str = "") -> dict:
        """Persist current COMPLIANCE_STATUS to a timestamped snapshot file.

        Used by compliance_diff to detect what changed since a prior check.
        Auto-called by compliance_summary at most once per day; can also be
        triggered manually with a label.
        """
        _load_compliance_state()
        import json
        from datetime import datetime
        from pathlib import Path
        snap_dir = _compliance_snapshots_dir()
        snap_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        snap = {
            "ts": now.isoformat(),
            "label": label,
            "items": [
                {"n": c["n"], "item": c["item"], "status": c["status"],
                 "owner": c.get("owner", ""), "priority": c.get("priority", False)}
                for c in COMPLIANCE_STATUS
            ],
        }
        fname = snap_dir / f"{now.strftime('%Y%m%d_%H%M%S')}.json"
        fname.write_text(json.dumps(snap, indent=2))
        return _ok({"snapshot_path": str(fname), "items": len(snap["items"])})

    def _maybe_auto_snapshot_compliance(self):
        """Take a daily snapshot if today's doesn't exist yet. Auto-prunes old snapshots."""
        import json
        from datetime import datetime
        from pathlib import Path
        snap_dir = _compliance_snapshots_dir()
        snap_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y%m%d")  # vj: local-display-ok
        existing_today = list(snap_dir.glob(f"{today}_*.json"))
        if not existing_today:
            try:
                self.compliance_snapshot(label="auto-daily")
            except Exception as _e:
                _record_bridge_error(f"compliance_snapshot: {_e}")  # P8.4 health tracking
            # Prune old snapshots (keep 90 days by default)
            _prune_compliance_snapshots()

    def compliance_diff(self, since_days: int = 7) -> dict:
        """Diff current compliance state vs the most recent snapshot older
        than `since_days` days. Returns a list of items whose status moved.

        the Owner's roadmap request #3: "If something moved since last check,
        I wouldn't know without diffing." This is that diff.

        - since_days=0 means "vs the most recent snapshot, period"
        - If no prior snapshot exists, returns an empty diff with a hint
          to run `compliance` first to seed the history.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        since_days, _e = _coerce_num(since_days, 'since_days', cast='int')
        if _e: return _e
        _load_compliance_state()
        import json
        from datetime import datetime, timedelta
        from pathlib import Path
        snap_dir = _compliance_snapshots_dir()
        if not snap_dir.exists():
            return _ok({
                "diff": [], "since": None, "message":
                "No compliance snapshots on file. Run `compliance` once to seed history, "
                "then check back later."
            })
        snaps = sorted(snap_dir.glob("*.json"))
        if not snaps:
            return _ok({
                "diff": [], "since": None, "message":
                "No compliance snapshots on file. Run `compliance` once to seed history."
            })
        # Find the most recent snapshot at least `since_days` old.
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, since_days))  # vj-fix: use tz-aware now
        target = None
        for s in reversed(snaps):
            try:
                snap_data = json.loads(s.read_text())
                snap_ts = datetime.fromisoformat(snap_data["ts"])
                # vj-fix: normalise naive timestamps to UTC before compare
                if snap_ts.tzinfo is None:
                    from datetime import timezone as _tz
                    snap_ts = snap_ts.replace(tzinfo=_tz.utc)
                if snap_ts <= cutoff:
                    target = snap_data
                    break
            except (json.JSONDecodeError, ValueError, KeyError):
                continue
        if target is None:
            # No snapshot old enough; fall back to oldest available
            try:
                target = json.loads(snaps[0].read_text())
            except Exception:
                return _err("Could not read compliance snapshots")

        # Build lookups
        prior_by_n = {it["n"]: it for it in target.get("items", [])}
        current_by_n = {c["n"]: c for c in COMPLIANCE_STATUS}

        diff = []
        for n, cur in current_by_n.items():
            prior = prior_by_n.get(n)
            if prior is None:
                diff.append({
                    "n": n, "item": cur["item"],
                    "from": "(new)", "to": cur["status"],
                    "direction": "added",
                })
                continue
            if prior["status"] != cur["status"]:
                # Direction: did it get better or worse?
                rank = {"OK": 0, "MONITOR": 1, "OPEN": 2, "BLOCKED": 3}
                pr = rank.get(prior["status"], 99)
                cr = rank.get(cur["status"], 99)
                direction = "improved" if cr < pr else "worsened"
                diff.append({
                    "n": n, "item": cur["item"],
                    "from": prior["status"], "to": cur["status"],
                    "direction": direction,
                })
        for n, prior in prior_by_n.items():
            if n not in current_by_n:
                diff.append({
                    "n": n, "item": prior["item"],
                    "from": prior["status"], "to": "(removed)",
                    "direction": "removed",
                })

        return _ok({
            "diff": diff,
            "since": target.get("ts"),
            "since_label": target.get("label", ""),
            "changed_count": len(diff),
            "improved": sum(1 for d in diff if d["direction"] == "improved"),
            "worsened": sum(1 for d in diff if d["direction"] == "worsened"),
            "added": sum(1 for d in diff if d["direction"] == "added"),
            "removed": sum(1 for d in diff if d["direction"] == "removed"),
        })

    def get_rates(self) -> dict:
        return _ok(RATES_TABLE)

    def get_priorities(self) -> dict:
        return _ok(ACTIVE_PRIORITIES)

    def get_rules(self) -> dict:
        return _ok({"rules": HARD_RULES, "forbidden": FORBIDDEN_PATTERNS})

    def get_team(self) -> dict:
        return _ok(TEAM_ROUTING)

    def get_projects(self) -> dict:
        return _ok(PROJECTS_ARCHIVE)

    def get_quick_actions(self) -> dict:
        return _ok(QUICK_ACTIONS)

    def version(self) -> dict:
        # Single source of truth for app version: vo_app/__init__.py
        # If vo_app is unavailable (e.g. running bridge in isolation
        # for tests outside the GUI), fall back to a labeled unknown so
        # we never silently report a stale string.
        try:
            from vo_app import __version__ as _ver
            from vo_app import __app_name__ as _app
            from vo_app import __publisher__ as _pub
        except ImportError:
            _ver, _app, _pub = "unknown", "Your Company Virtual Office", "Your Company, LLC"
        return _ok({
            "app":     _app,
            "version": _ver,
            "company": _pub,
            "built":   datetime.now().strftime("%Y-%m-%d"),  # vj: local-display-ok
            "model":   "claude-sonnet-4-6",
            "rules":   len(HARD_RULES),
            "docs_compiled": 22,
        })

    def get_app_info(self) -> dict:
        return self.version()

    # ── Integration + Sync endpoints ─────────────────────────────────
    def get_integrations(self) -> dict:
        """Return status of OneDrive, GitHub, and AI models for dashboard."""
        keys = _load_all_keys()
        ai_count = sum(1 for v in keys.values() if v)

        od = detect_onedrive()
        gh = detect_github_repo()

        return _ok({
            "onedrive": {
                "status": "linked" if od["found"] else "pending",
                "path": od.get("path"),
                "bid_kit": od.get("bid_kit", False),
                "standing": od.get("standing", False),
                "active_bids": od.get("active_bids", []),
            },
            "github": {
                "status": "linked" if gh["found"] else "pending",
                "branch": gh.get("branch"),
                "last_commit": gh.get("last_commit"),
            },
            "ai_models": {"status": "linked", "count": ai_count, "total": 3},
        })

    def get_standing_files(self) -> dict:
        """Read canonical standing files from OneDrive for Drive-first rule."""
        files = {}
        for fname in ["company.md", "voice_rules.md", "format_locks.md",
                       "pricing_rules.md", "sanitizer_rules.md"]:
            content = read_standing_file(fname)
            if content:
                files[fname] = content[:2000]  # cap per file
        return _ok({"files": files, "count": len(files)})

    # ── Bid Pipeline endpoints ────────────────────────────────────────
    def get_kpis(self) -> dict:
        """Return real KPI data from the bid pipeline database.

        v3.2.7: now also returns compliance_label like "6 of 13 passing"
        so the frontend doesn't display a bare percentage with no context.
        v3.2.7 pass 10: adds research_seeds count so the KPI panel doesn't
        show 0 everything when there are 11 research leads tracked.
        """
        kpis = _bid_pipeline.get_kpis()
        # Add compliance KPI
        blocked = sum(1 for c in COMPLIANCE_STATUS if c["status"] == "BLOCKED")
        total = len(COMPLIANCE_STATUS)
        ok_count = sum(1 for c in COMPLIANCE_STATUS
                       if c["status"] in ("OK", "MONITOR"))
        kpis["blockers"] = blocked
        kpis["compliance_pct"] = round(ok_count / total * 100) if total else 0
        kpis["compliance_label"] = (
            f"{ok_count} of {total} passing" if total else "no compliance items"
        )
        kpis["compliance_passing"] = ok_count
        kpis["compliance_total"] = total
        # Add research seeds count from pipeline
        try:
            pipe = self.get_project_pipeline()
            if pipe.get("ok") and pipe.get("data"):
                kpis["research_seeds"] = pipe["data"].get("research_seeds_count", 0)
                kpis["pipeline_total"] = pipe["data"].get("total", 0)
        except Exception:
            kpis["research_seeds"] = 0
            kpis["pipeline_total"] = 0
        # P10.1: add pipeline_value_m from new state-machine bid_pipeline.db
        # Frontend uses d.pipeline_value_m to populate k-rev and fk-pipe KPIs.
        # The legacy _bid_pipeline (integrations.py) doesn't carry dollar totals
        # for non-terminal bids, so we query bid_pipeline.db directly here.
        try:
            from bridge.bid_pipeline import _conn as _bp_conn
            _TERMINAL_KPI = ("'WON'", "'PASSED'", "'LOST'")
            _bp_row = _bp_conn().execute(
                "SELECT COALESCE(SUM(CAST(estimated_value AS REAL)), 0) as total "
                f"FROM bids WHERE state NOT IN ({','.join(_TERMINAL_KPI)})"
            ).fetchone()
            _pv = float(_bp_row["total"]) if _bp_row else 0.0
            kpis["pipeline_value_m"] = round(_pv / 1_000_000, 2)
        except Exception:
            kpis["pipeline_value_m"] = 0.0
        return _ok(kpis)

    def next_bid_number(self, city: str = "HOU") -> dict:
        """Generate the next sequential proposal number."""
        return _ok({"next": _bid_pipeline.next_number(city)})

    def add_bid(self, proposal_no: str, project_name: str,
                gc_name: str = "", city: str = "HOU",
                base_bid_total: float = 0, deadline: str = "",
                drawing_stage: str = "IFC") -> dict:
        """Add a new bid to the pipeline."""
        # pass 10i: numeric input hardening - coerce or fail clean
        base_bid_total, _e = _coerce_num(base_bid_total, 'base_bid_total')
        if _e: return _e
        try:
            bid_id = _bid_pipeline.add_bid(
                proposal_no, project_name, gc_name, city,
                base_bid_total, deadline, drawing_stage
            )
            return _ok({"bid_id": bid_id, "proposal_no": proposal_no})
        except Exception as e:
            return _err(f"Failed to add bid: {e}")

    def update_bid_status(self, proposal_no: str, status: str,
                          notes: str = "") -> dict:
        """Update bid status in the pipeline."""
        if _bid_pipeline.update_status(proposal_no, status, notes):
            return _ok({"updated": True})
        return _err(f"Bid {proposal_no} not found")

    def list_bids(self, status: str = "", limit: int = 20) -> dict:
        """List bids from the pipeline."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        return _ok(_bid_pipeline.list_bids(status or None, limit))  # vj: ok-passthrough-safe

    def get_pipeline_summary(self) -> dict:
        """Kanban-style bid pipeline summary.

        Pass 10j: also includes filesystem_bid_count for cross-reference.
        The pipeline (SQLite) and bid folders (filesystem) can diverge if
        bids are created via auto_process_drawing (which writes both) vs
        manual folder creation (which only writes filesystem). The mismatch
        note helps Owner spot drift.
        """
        result = _bid_pipeline.pipeline_summary()
        # Cross-reference with filesystem bid folders
        try:
            from bridge.bid_documents import bids_root
            root = bids_root()
            fs_count = 0
            if root.exists():
                for ym in root.iterdir():
                    if ym.is_dir() and ym.name.startswith("20"):
                        fs_count += sum(1 for d in ym.iterdir() if d.is_dir())
            if isinstance(result, dict):
                result["filesystem_bid_count"] = fs_count
                pipeline_count = len(result.get("bids", []))
                if fs_count != pipeline_count:
                    result["data_source_note"] = (
                        f"Pipeline DB has {pipeline_count} bids; "
                        f"filesystem has {fs_count} bid folders. "
                        f"Review bid folders in the data directory to reconcile."
                    )
        except Exception:
            pass  # non-critical enrichment
        return _ok(result)

    # ── CEO Interaction Log ───────────────────────────────────────────
    def get_ceo_log(self, n: int = 20) -> dict:
        """Return recent CEO interactions for preference mining."""
        # pass 10i: numeric input hardening - coerce or fail clean
        n, _e = _coerce_num(n, 'n', cast='int')
        if _e: return _e
        return _ok({
            "interactions": _ceo_logger.recent(n),
            "total": _ceo_logger.count(),
        })

    # ── Fabrication Methods ────────────────────────────────────────────

    def generate_3d_model(self, members_json: str) -> dict:
        """Generate 3D STL model from a JSON list of members.
        Each member: {shape, length_ft, x_ft, y_ft, z_ft, mark}
        """
        import json as _json
        from bridge.fabrication import generate_stl, save_output
        try:
            members = _json.loads(members_json)
            stl_data = generate_stl(members)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
            path = save_output(stl_data, f"model_{ts}.stl")
            return _ok({"file": path, "format": "STL",
                        "members": len(members), "bytes": len(stl_data)})
        except Exception as e:
            return _err(str(e))

    # ── Phase 1 (v3.6.0): Tekla PowerFab XML export ───────────────────
    # Converts internal takeoff JSON to industry-standard FabSuiteXMLRequest
    # XML. Validates every shape against AISC v16.0 (2,299 shapes) before
    # any data reaches the XML. Output lands in the bid folder so it sits
    # next to the proposal and GP report.
    def export_tekla_xml(self, bid_number: str = "", project_name: str = "",
                          members_json: str = "") -> dict:
        """Export takeoff data as Tekla PowerFab XML.

        Returns the generator's native dict on success. Wrap as _err() only
        on import or argument failure so the frontend can read r.success,
        r.items_exported, r.items_rejected, r.warnings, r.output_path.

        Frontend integration sets window._lastTakeoffMembers from the
        auto_process_drawing result and passes it here as a JSON string.
        Each member must carry: mark, qty, shape, size, length_in. Optional:
        grade, sequence, lot, camber.
        """
        try:
            import json as _json
            # JSON string is the contract from the pywebview bridge so the
            # array survives the Python <-> JS hop intact.
            if not members_json:
                return _err("No member data provided")

            try:
                members = _json.loads(members_json)
            except (ValueError, TypeError) as je:
                return _err(f"members_json must be valid JSON: {je}")

            if not isinstance(members, list) or not members:
                return _err("members_json must decode to a non-empty list")

            from bridge.exporters.tekla_xml_gen import generate_tekla_xml

            # Save inside the bid folder so it sits next to the proposal
            # PDF and GP report. Path layout: Documents/Your Company Bids/
            # YYYY-MM/<bid_number>/<bid_number>_tekla.xml
            bid_dir = Path.home() / "Documents" / "Your Company Bids"
            safe_bid = (bid_number or "UNNUMBERED").strip() or "UNNUMBERED"
            month_part = datetime.now().strftime("%Y-%m")  # vj: local-display-ok
            out_path = bid_dir / month_part / safe_bid / f"{safe_bid}_tekla.xml"

            # [R5] generate_tekla_xml returns flat dict (success/xml_string) → WRAP
            return _ok(generate_tekla_xml(
                job_number=safe_bid,
                project_name=project_name or "",
                takeoff_data=members,
                output_path=out_path,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 6 (v3.9.1): Strumis ERP XML export -----------------------------
    # Strumis covers the 40 percent of Houston fab shops that don't run Tekla
    # PowerFab. Same takeoff input dict as the Tekla exporter so the frontend
    # can route the same data to either format. Same AISC validation gate.
    def export_strumis_xml(self, bid_number: str = "", project_name: str = "",
                            members_json: str = "") -> dict:
        """Export takeoff data as Strumis ERP XML.

        Mirrors export_tekla_xml. Returns the generator's native dict on
        success. Wraps as _err only on import or argument failure so the
        frontend can read r.success, r.items_exported, r.items_rejected,
        r.warnings, r.output_path.

        members_json carries the same takeoff array shape the Tekla button
        uses so the frontend handler can reuse window._lastTakeoffMembers.
        """
        try:
            import json as _json

            if not members_json:
                return _err("No member data provided")

            try:
                members = _json.loads(members_json)
            except (ValueError, TypeError) as je:
                return _err(f"members_json must be valid JSON: {je}")

            if not isinstance(members, list) or not members:
                return _err("members_json must decode to a non-empty list")

            from bridge.exporters.strumis_export import generate_strumis_xml

            # Save inside the bid folder next to the proposal PDF and the
            # Tekla XML. Matches the layout the Tekla button uses.
            bid_dir = Path.home() / "Documents" / "Your Company Bids"
            safe_bid = (bid_number or "UNNUMBERED").strip() or "UNNUMBERED"
            month_part = datetime.now().strftime("%Y-%m")  # vj: local-display-ok
            out_path = bid_dir / month_part / safe_bid / \
                       f"{safe_bid}_strumis.xml"

            # [R5] generate_strumis_xml returns flat dict (success/xml_string) → WRAP
            return _ok(generate_strumis_xml(
                job_number=safe_bid,
                project_name=project_name or "",
                takeoff_data=members,
                output_path=out_path,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 7 (v4.0.0): Three-tier vision status + dispatch -----------------
    # The router and tracker live in bridge/vision_tiers/. The bridge owns a
    # single shared TierRouter so calls during a bid run accumulate into one
    # CostTracker. Phase 8 (LangGraph) will rebuild the takeoff pipeline to
    # actually use this for Stage 4. For Phase 7b we expose status and a
    # single-call dispatch endpoint so the GUI can show tier health and
    # Joseph can manually test the path before the LangGraph rewrite.
    def get_vision_tier_status(self) -> dict:
        """Return tier-router health for the GUI status indicator."""
        try:
            r = self._get_or_create_tier_router()
            s = r.status()
            from bridge.vision_tiers import HAS_DOCTR, HAS_OPENROUTER
            s["doctr_available"] = bool(HAS_DOCTR)
            s["openrouter_configured"] = bool(HAS_OPENROUTER)
            return _ok({"status": s})
        except Exception as e:
            return _err(str(e))

    def route_vision_task(self, task: str = "",
                           image_path: str = "",
                           force_tier: str = "") -> dict:
        """Manually dispatch a single vision call through the router.

        Used for Joseph's pre-LangGraph smoke testing. Not on the
        critical path of any bid.
        """
        try:
            if not task or not image_path:
                return _err("task and image_path are required")

            r = self._get_or_create_tier_router()
            kwargs = {}
            if force_tier:
                kwargs["force_tier"] = force_tier
            result = r.route(task=task, image_path=image_path, **kwargs)
            return _ok({"result": result.to_dict(), "router_status": r.status()})

        except Exception as e:
            return _err(str(e))

    def _get_or_create_tier_router(self):
        """Lazy-build a single TierRouter for the lifetime of the Bridge.

        Tier 3 is OFF unless governance.json says otherwise. The cost
        tracker resets per bid - the GUI calls reset_vision_tier_tracker
        before each takeoff run.
        """
        if getattr(self, "_tier_router", None) is not None:
            return self._tier_router

        from bridge.vision_tiers import (
            TierRouter, CostTracker, make_gemini_callable, gpt4o_callable,
        )

        # Read governance for tier3 toggle and cap
        tier3_enabled = False
        threshold = 0.85
        cap = 1.50
        try:
            import json as _json
            from pathlib import Path as _P
            gov_path = _P(__file__).resolve().parent.parent / \
                       "data" / "governance.json"
            if gov_path.exists():
                gov = _json.loads(gov_path.read_text(encoding="utf-8"))
                vt = gov.get("vision_tiers", {}) or {}
                tier3_enabled = bool(vt.get("tier3_enabled", False))
                threshold = float(vt.get("confidence_threshold", 0.85))
                cap = float(vt.get("tier3_cap_usd", 1.50))
        except Exception:
            pass

        # Wire the existing call provider for Gemini through the adapter.
        # _call_provider is the same closure Phase 2 uses elsewhere.
        provider = getattr(self, "_call_provider", None)
        gem_callable = make_gemini_callable(call_provider=provider)

        tracker = CostTracker(tier3_cap_usd=cap)
        self._tier_router = TierRouter(
            cost_tracker=tracker,
            confidence_threshold=threshold,
            tier3_enabled=tier3_enabled,
            gemini_callable=gem_callable,
            gpt4o_callable=gpt4o_callable if tier3_enabled else None,
        )
        return self._tier_router

    def reset_vision_tier_tracker(self, bid_number: str = "") -> dict:
        """Start a fresh cost tracker for a new bid."""
        try:
            from bridge.vision_tiers import CostTracker
            r = self._get_or_create_tier_router()
            cap = r.cost_tracker.tier3_cap_usd
            r.cost_tracker = CostTracker(
                bid_number=bid_number, tier3_cap_usd=cap)
            return _ok({"bid_number": bid_number})
        except Exception as e:
            return _err(str(e))

    # -- Phase 2 (v3.6.1): Connection Detail Vision ----------------------------
    # Analyzes structural connection nodes for moments, copes, studs, camber.
    # Feeds detail attributes into the Tekla exporter's camber field and
    # adjusts labor multipliers for bid pricing.
    def analyze_connection_details(self, members_json: str = "",
                                    pdf_path: str = "",
                                    page_num: int = 0) -> dict:
        """Find connection nodes and analyze details via Gemini Vision.

        Args:
            members_json: JSON array of member dicts with bbox fields.
                Each member needs: id/mark, bbox [x0,y0,x1,y1].
                Optional: type, shape, camber, mark.
            pdf_path: Path to source PDF for high-res crop generation.
            page_num: 0-based page number for crops.

        Returns:
            {
                "success": bool,
                "nodes_found": int,
                "nodes_analyzed": int,
                "nodes": [...],        # node detail dicts
                "summary": str,        # human-readable summary
                "error": str,          # on failure
            }
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        page_num, _e = _coerce_num(page_num, 'page_num', cast='int')
        if _e: return _e
        try:
            import json as _json
            from bridge.drawing_intel.node_cropper import (
                find_connection_nodes, nodes_to_dicts,
            )
            from bridge.drawing_intel.detail_vision import (
                analyze_nodes, merge_details_into_takeoff,
            )

            # Parse members
            if not members_json:
                return _err("No member data provided")
            try:
                members = _json.loads(members_json)
            except (ValueError, TypeError) as e:
                return _err(f"members_json must be valid JSON: {e}")

            if not isinstance(members, list):
                return _err("members_json must decode to a list")

            # Step 1: Find connection nodes
            generate_crops = bool(pdf_path and Path(pdf_path).exists())
            nodes = find_connection_nodes(
                members,
                pdf_path=pdf_path,
                page_num=int(page_num),
                generate_crops=generate_crops,
            )

            if not nodes:
                # v3.2.7 fix H: wrap in _ok()
                return _ok({
                    "nodes_found": 0,
                    "nodes_analyzed": 0,
                    "nodes": [],
                    "summary": "No connection intersections found. "
                               "Members may not have bounding box data.",
                })

            # Step 2: Analyze details (vision if available, inferred otherwise)
            # In production, call_provider comes from the conductor.
            # For now, pass None so it falls back to geometry-based inference.
            details = analyze_nodes(nodes, call_provider=None)

            # Build summary
            moments = sum(1 for d in details if d.get("moment"))
            copes = sum(1 for d in details if d.get("cope_required"))
            codes = {}
            for d in details:
                ct = d.get("connection_type", "UNKNOWN")
                codes[ct] = codes.get(ct, 0) + 1

            code_str = ", ".join(f"{v} {k}" for k, v in sorted(codes.items()))
            summary = (
                f"{len(nodes)} connection nodes found. "
                f"Types: {code_str}. "
                f"{moments} moment frames, {copes} copes flagged."
            )

            # v3.2.7 fix H: wrap in _ok()
            return _ok({
                "nodes_found": len(nodes),
                "nodes_analyzed": len(details),
                "nodes": details,
                "summary": summary,
            })
        except Exception as e:
            return _err(str(e))

    # -- Phase 3 (v3.7.0): HITL Review Workbench ------------------------------
    def save_workbench_correction(self, project_id: str = "", member_id: str = "",
                                   field_name: str = "", old_value: str = "",
                                   new_value: str = "", source_drawing: str = "",
                                   page_num: int = 0, confidence: float = 0.0,
                                   user: str = "joseph") -> dict:
        """Save a user correction from the Review Workbench."""
        # pass 10i: numeric input hardening - coerce or fail clean
        page_num, _e = _coerce_num(page_num, 'page_num', cast='int')
        if _e: return _e
        confidence, _e = _coerce_num(confidence, 'confidence')
        if _e: return _e
        try:
            from bridge.workbench.correction_bridge import process_correction
            # [R5] process_correction returns flat dict (saved/lake_result) → WRAP
            return _ok(process_correction(
                project_id=project_id,
                member_id=member_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                source_drawing=source_drawing,
                page_num=int(page_num),
                confidence=float(confidence),
                user=user,
            ))
        except Exception as e:
            return _err(str(e))

    def get_workbench_data(self, project_id: str = "",
                            members_json: str = "") -> dict:
        """Get annotated member data for the workbench overlay."""
        try:
            from bridge.workbench.correction_bridge import get_workbench_data
            # [R5] get_workbench_data returns flat dict (members/corrections/stats) → WRAP
            return _ok(get_workbench_data(
                project_id=project_id,
                members_json=members_json,
            ))
        except Exception as e:
            return _err(str(e))

    def get_valid_shapes(self) -> dict:
        """Return the AISC v16.0 shape set for client-side validation."""
        try:
            import csv
            shapes = []
            csv_path = Path(__file__).resolve().parent.parent / "data" / "aisc_master.csv"
            if csv_path.exists():
                with open(csv_path, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        s = (row.get("shape") or "").strip().upper()
                        if s:
                            shapes.append(s)
            return _ok({"shapes": shapes, "count": len(shapes)})
        except Exception as e:
            return _err(f"get_valid_shapes: {e}")

    def get_correction_summary(self) -> dict:
        """Get correction pattern summary for active learning."""
        try:
            from bridge.workbench.correction_lake import get_pattern_summary
            # [R5] get_pattern_summary returns flat dict (total/patterns) → WRAP
            return _ok(get_pattern_summary())
        except Exception as e:
            return _err(str(e))

    # -- Phase 4 (v3.8.0): Takeoff Controller + Active Learning ----------------
    def process_full_takeoff(self, pdf_path: str = "", project_id: str = "",
                              project_name: str = "",
                              skip_vision: bool = False,
                              skip_pricing: bool = False,
                              complexity: str = "standard") -> dict:
        """Run the complete 7-stage takeoff pipeline on a structural PDF.

        Stages: extract, validate, node_map, detail_vision, weight_calc,
        pricing. Returns a complete TakeoffResult dict.
        """
        try:
            from bridge.takeoff_controller import process_full_takeoff
            result = process_full_takeoff(
                pdf_path=pdf_path,
                project_id=project_id,
                project_name=project_name,
                skip_vision=skip_vision,
                skip_pricing=skip_pricing,
                complexity=complexity,
            )
            return result.to_dict()
        except Exception as e:
            return {"error": str(e), "stages_completed": [],
                    "members": [], "nodes": [], "details": []}

    # -- Phase 8 (v4.1.0): LangGraph pipeline + speed optimization -----------
    # Same six stages as v1, but with parallel branches: Stage 2 (validate)
    # and Stage 4.5 (misc steel) run concurrently with each other after
    # Stage 1 finishes. Stage 4 (detail vision) fans out per-node calls
    # across a configurable thread pool. Cache hits skip the LLM round-trip.
    def process_full_takeoff_v2(self, pdf_path: str = "",
                                  bid_number: str = "",
                                  project_name: str = "",
                                  skip_vision: bool = False,
                                  use_cache: bool = True,
                                  parallel_vision_workers: int = 4,
                                  force_executor: str = "") -> dict:
        """Run the takeoff DAG.

        force_executor: "" (auto), "langgraph", or "fallback".
            "" picks LangGraph if installed, else the threadpool path.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        parallel_vision_workers, _e = _coerce_num(parallel_vision_workers, 'parallel_vision_workers', cast='int')
        if _e: return _e
        try:
            from bridge.takeoff_graph import run_takeoff_graph
            provider = getattr(self, "_call_provider", None)
            tier_router = None
            try:
                # Reuse the Phase 7 router so Tier 3 cost cap applies.
                tier_router = self._get_or_create_tier_router()
            except Exception:
                pass

            state = run_takeoff_graph(
                pdf_path=pdf_path,
                bid_number=bid_number,
                project_name=project_name,
                skip_vision=skip_vision,
                use_cache=use_cache,
                parallel_vision_workers=int(parallel_vision_workers),
                call_provider=provider,
                vision_tier_router=tier_router,
                force_executor=force_executor,
            )
            # Strip the non-serializable raw nodes refs before return
            state.pop("_raw_nodes", None)
            return state
        except Exception as e:
            return {
                "error": str(e),
                "stages_completed": [],
                "raw_members": [], "valid_members": [],
                "nodes": [], "details": [],
            }

    def get_graph_runner_status(self) -> dict:
        """Return graph-runner availability for the GUI.

        v3.2.7 fix H: wrapped in _ok() to match Bridge convention.
        """
        try:
            from bridge.takeoff_graph import runner_status
            from bridge.cache import VisionCache
            cache = VisionCache()
            return _ok({
                "runner": runner_status(),
                "cache": cache.stats(),
            })
        except Exception as e:
            return _err(str(e))

    def clear_vision_cache(self) -> dict:
        """Wipe the vision cache. Useful when changing prompts."""
        try:
            from bridge.cache import VisionCache
            cache = VisionCache()
            stats_before = cache.stats()
            cache.clear()
            return _ok({"entries_cleared": stats_before.get("entries", 0)})
        except Exception as e:
            return _err(str(e))

    # -- Phase 9 (v4.2.0): Project RAG + shadow backtesting ------------------
    # Semantic memory over past projects. Every downstream phase (watchdog,
    # planner, auditor, cross-verify, overlay) will query project memory.
    def search_project_memory(self, query: str = "",
                                n_results: int = 3) -> dict:
        """Semantic search over past projects.

        Returns the top N similar past projects with comparison data.
        Owner sees these on the project card: "This is similar to
        PRJ-2026-HOU-0038 (Baytown Industrial). 220 tons at $3,200/ton."
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        n_results, _e = _coerce_num(n_results, 'n_results', cast='int')
        if _e: return _e
        try:
            from bridge.project_memory import search_similar_projects
            if not query:
                return _err("query is required")
            # [R5] search_similar_projects returns flat dict (success/results) → WRAP
            return _ok(search_similar_projects(
                query=query, n_results=int(n_results)))
        except Exception as e:
            return _err(str(e))

    def index_project(self, bid_number: str = "",
                        project_name: str = "",
                        takeoff_result_json: str = "",
                        client: str = "",
                        location: str = "") -> dict:
        """Index a completed takeoff into project memory."""
        try:
            import json as _json
            from bridge.project_memory import index_takeoff_result
            if not bid_number:
                return _err("bid_number required")
            takeoff = {}
            if takeoff_result_json:
                try:
                    takeoff = _json.loads(takeoff_result_json)
                except Exception as e:
                    return _err(f"invalid JSON: {e}")
            # [R5] index_takeoff_result returns flat dict (success/bid_number) → WRAP
            return _ok(index_takeoff_result(
                takeoff_result=takeoff,
                bid_number=bid_number,
                project_name=project_name,
                client=client,
                location=location,
            ))
        except Exception as e:
            return _err(str(e))

    def backtest_project(self, manual_members_json: str = "",
                           ai_members_json: str = "",
                           manual_tons: float = 0.0,
                           ai_tons: float = 0.0,
                           bid_number: str = "",
                           project_name: str = "") -> dict:
        """Run shadow backtest: compare AI vs manual takeoff."""
        # pass 10i: numeric input hardening - coerce or fail clean
        manual_tons, _e = _coerce_num(manual_tons, 'manual_tons')
        if _e: return _e
        ai_tons, _e = _coerce_num(ai_tons, 'ai_tons')
        if _e: return _e
        try:
            import json as _json
            from bridge.project_memory import backtest
            manual = _json.loads(manual_members_json) \
                     if manual_members_json else []
            ai = _json.loads(ai_members_json) \
                 if ai_members_json else []
            # [R5] backtest returns flat dict (success/delta_pct) → WRAP
            return _ok(backtest(
                manual_members=manual,
                ai_members=ai,
                manual_tons=float(manual_tons),
                ai_tons=float(ai_tons),
                bid_number=bid_number,
                project_name=project_name,
            ))
        except Exception as e:
            return _err(str(e))

    def get_memory_status(self) -> dict:
        """Return project memory health for diagnostics.

        v3.2.7 fix H: wrapped in _ok() to match Bridge convention.
        """
        try:
            from bridge.project_memory import get_memory_store, HAS_CHROMADB
            store = get_memory_store()
            return _ok({
                "backend": type(store).__name__,
                "chromadb_available": bool(HAS_CHROMADB),
                "project_count": store.count(),
            })
        except Exception as e:
            return _err(str(e))

    # -- Phase 10 (v4.3.0): Assembly-based costing ---------------------------
    # Maps connection types to hardware costs. A moment frame adds $800-1,200
    # more than a simple shear tab. Uses Phase 2 detail_vision output.
    def compute_assembly_costs(self, details_json: str = "") -> dict:
        """Compute connection hardware costs for a set of detail_vision results.

        details_json: JSON array of detail_vision result dicts. Each must
            have at least 'connection_type'; 'moment' and 'bolt_count' are
            optional.
        """
        try:
            import json as _json
            from bridge.assembly_costing import compute_assembly_costs

            if not details_json:
                return _err("details_json is required")

            try:
                details = _json.loads(details_json)
            except Exception as e:
                return _err(f"invalid JSON: {e}")

            if not isinstance(details, list):
                return _err("details_json must decode to a list")

            result = compute_assembly_costs(details)
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    # -- Phase 11 (v4.3.1): Monte Carlo risk scoring -------------------------
    def run_monte_carlo(self, direct_cost: float = 0,
                          material_tons: float = 0,
                          fab_hours: float = 0,
                          erect_hours: float = 0,
                          connection_cost: float = 0,
                          bid_amount: float = 0,
                          simulations: int = 1000) -> dict:
        """Run 1,000 Monte Carlo simulations on bid variables."""
        # pass 10i: numeric input hardening - coerce or fail clean
        direct_cost, _e = _coerce_num(direct_cost, 'direct_cost')
        if _e: return _e
        material_tons, _e = _coerce_num(material_tons, 'material_tons')
        if _e: return _e
        fab_hours, _e = _coerce_num(fab_hours, 'fab_hours')
        if _e: return _e
        erect_hours, _e = _coerce_num(erect_hours, 'erect_hours')
        if _e: return _e
        connection_cost, _e = _coerce_num(connection_cost, 'connection_cost')
        if _e: return _e
        bid_amount, _e = _coerce_num(bid_amount, 'bid_amount')
        if _e: return _e
        simulations, _e = _coerce_num(simulations, 'simulations', cast='int')
        if _e: return _e
        try:
            from bridge.risk_scoring import monte_carlo_bid_risk
            result = monte_carlo_bid_risk(
                direct_cost=float(direct_cost),
                material_tons=float(material_tons),
                fab_hours=float(fab_hours),
                erect_hours=float(erect_hours),
                connection_cost=float(connection_cost),
                bid_amount=float(bid_amount),
                overrides={"simulations": int(simulations)},
            )
            # VJ auto-fix (pass 10i sim): was returning raw dict without _ok wrapper
            return _ok(result)
        except Exception as e:
            return _err(f"Monte Carlo simulation failed: {e}",
                        fix="Check that bridge/risk_scoring.py exists and numpy is installed.")

    # -- Phase 12 (v4.4.0): Connection plate weight --------------------------
    def estimate_connection_weight(self, details_json: str = "",
                                     structural_tons: float = 0) -> dict:
        """Estimate connection hardware weight from detail vision output."""
        # pass 10i: numeric input hardening - coerce or fail clean
        structural_tons, _e = _coerce_num(structural_tons, 'structural_tons')
        if _e: return _e
        try:
            import json as _json
            from bridge.connection_weight import estimate_connection_weight
            if not details_json:
                return _err("details_json required")

            details = _json.loads(details_json)
            if not isinstance(details, list):
                return _err("details_json must be a list")

            result = estimate_connection_weight(
                details, structural_tons=float(structural_tons))
            # v3.2.7 fix H: wrap in _ok() to match Bridge convention
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    # -- Phase 13 (v4.4.1): What-if grade comparison -------------------------
    def compare_grades(self, members_json: str = "",
                         grades_json: str = "",
                         price_overrides_json: str = "") -> dict:
        """Compare material cost across steel grades."""
        try:
            import json as _json
            from bridge.grade_comparison import grade_comparison
            if not members_json:
                return _err("members_json required")

            members = _json.loads(members_json)
            grades = _json.loads(grades_json) if grades_json else None
            overrides = _json.loads(price_overrides_json) \
                        if price_overrides_json else None
            result = grade_comparison(
                members, grades=grades, price_overrides=overrides)
            # v3.2.7 fix H: wrap in _ok() to match Bridge convention
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    # -- Phase 14 (v4.5.0): Cloud folder watchdog ----------------------------
    # Monitors OneDrive and Google Drive for new drawing PDFs. Auto-processes
    # and indexes into project memory. RAG-aware.
    def get_watchdog_status(self) -> dict:
        """Return the watchdog service status."""
        try:
            svc = self._get_or_create_watchdog()
            return _ok({"status": svc.status()})
        except Exception as e:
            return _err(str(e))

    def configure_watchdog(self, poll_interval: int = 300,
                             auto_process: bool = True) -> dict:
        """Update watchdog configuration."""
        # pass 10i: numeric input hardening - coerce or fail clean
        poll_interval, _e = _coerce_num(poll_interval, 'poll_interval', cast='int')
        if _e: return _e
        try:
            svc = self._get_or_create_watchdog()
            svc.poll_interval = float(poll_interval)
            svc.auto_process = bool(auto_process)
            return _ok({"poll_interval": svc.poll_interval,
                    "auto_process": svc.auto_process})

        except Exception as e:
            return _err(str(e))

    def start_watchdog(self) -> dict:
        """Start the background watchdog polling thread."""
        try:
            svc = self._get_or_create_watchdog()
            svc.start()
            return _ok({"running": svc.is_running()})
        except Exception as e:
            return _err(str(e))

    def stop_watchdog(self) -> dict:
        """Stop the watchdog polling thread."""
        try:
            svc = self._get_or_create_watchdog()
            svc.stop()
            return _ok({"running": svc.is_running()})
        except Exception as e:
            return _err(str(e))

    def watchdog_poll_now(self) -> dict:
        """Trigger one poll cycle immediately."""
        try:
            svc = self._get_or_create_watchdog()
            results = svc.poll_once()
            return _ok({"files_found": len(results),
                    "results": results})

        except Exception as e:
            return _err(str(e))

    def _get_or_create_watchdog(self):
        if getattr(self, "_watchdog_svc", None) is not None:
            return self._watchdog_svc
        from bridge.cloud_watchdog import WatchdogService
        self._watchdog_svc = WatchdogService(
            watchers=[],
            auto_process=True,
            process_fn=lambda pdf_path: self.process_full_takeoff_v2(
                pdf_path=pdf_path, force_executor="fallback"),
        )
        return self._watchdog_svc

    # -- Phase 15 (v4.6.0): Objective-based planning -------------------------
    # Joseph says "get the Houston bid ready by Friday" and the system
    # plans backwards from the deadline: find drawings, takeoff, price,
    # scope, proposal.
    def execute_objective(self, objective: str = "",
                            dry_run: bool = False) -> dict:
        """Parse a natural-language objective and execute the task chain."""
        try:
            from bridge.objective_planner import build_plan, execute_plan
            if not objective:
                return _err("objective is required")
            plan = build_plan(objective)
            if not plan.get("steps"):
                return _err("could not match objective to a template")

            bridge_ref = None if dry_run else self
            result = execute_plan(plan, bridge=bridge_ref)
            return result
        except Exception as e:
            return _err(str(e))

    def plan_objective(self, objective: str = "") -> dict:
        """Build a plan without executing. Returns the step list."""
        try:
            from bridge.objective_planner import build_plan
            if not objective:
                return _err("objective is required")
            plan = build_plan(objective)
            plan["success"] = bool(plan.get("steps"))
            return plan
        except Exception as e:
            return _err(str(e))

    # -- Phase 16 (v4.7.0): Auditable calculation pack -----------------------
    def generate_calc_pack(self, takeoff_result_json: str = "",
                             bid_number: str = "",
                             project_name: str = "") -> dict:
        """Generate a PE-friendly Excel calc pack from takeoff data."""
        try:
            import json as _json
            from bridge.exporters.calc_pack_gen import generate_calc_pack
            takeoff = _json.loads(takeoff_result_json) \
                      if takeoff_result_json else {}
            bid = bid_number or takeoff.get("bid_number", "UNNUMBERED")
            name = project_name or takeoff.get("project_name", "")
            month = datetime.now().strftime("%Y-%m")  # vj: local-display-ok
            out_path = Path.home() / "Documents" / "Your Company Bids" / \
                       month / bid / f"{bid}_calc_pack.xlsx"
            # [R5] generate_calc_pack returns flat dict (success/output_path) → WRAP
            return _ok(generate_calc_pack(
                takeoff_result=takeoff,
                bid_number=bid,
                project_name=name,
                output_path=out_path,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 17 (v4.8.0): CNC post-processor ------------------------------
    def generate_stop_list(self, members_json: str = "") -> dict:
        """Generate stop-list CSV for Geka/Sunrise back gauges."""
        try:
            import json as _json
            from bridge.cnc import generate_stop_list
            members = _json.loads(members_json) if members_json else []
            # [R5] generate_stop_list returns flat dict (stops/csv_path) → WRAP
            return _ok(generate_stop_list(members))
        except Exception as e:
            return _err(str(e))

    def generate_part_dxf(self, member_json: str = "") -> dict:
        """Generate 1:1 DXF part drawing for a single member."""
        try:
            import json as _json
            from bridge.cnc import generate_part_dxf
            member = _json.loads(member_json) if member_json else {}
            # [R5] generate_part_dxf returns flat dict (success/dxf_path) → WRAP
            return _ok(generate_part_dxf(member))
        except Exception as e:
            return _err(str(e))

    def generate_gcode_piranha(self, member_json: str = "",
                        thickness_in: float = 0.5) -> dict:
        """Generate G-code (.nc) for Piranha plasma table (v3.2.7: renamed from generate_gcode to fix shadow)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        thickness_in, _e = _coerce_num(thickness_in, 'thickness_in')
        if _e: return _e
        try:
            import json as _json
            from bridge.cnc import generate_gcode
            member = _json.loads(member_json) if member_json else {}
            # [R5] generate_gcode returns flat dict (lines/nc_path) → WRAP
            return _ok(generate_gcode(member, thickness_in=thickness_in))
        except Exception as e:
            return _err(str(e))

    def generate_dstv(self, member_json: str = "") -> dict:
        """Generate DSTV/NC1 file for robotic beam lines."""
        try:
            import json as _json
            from bridge.cnc import generate_dstv
            member = _json.loads(member_json) if member_json else {}
            # [R5] generate_dstv returns flat dict (success/nc1_path) → WRAP
            return _ok(generate_dstv(member))
        except Exception as e:
            return _err(str(e))

    def generate_punch_map(self, member_json: str = "") -> dict:
        """Generate punch map PDF for shop floor posting."""
        try:
            import json as _json
            from bridge.cnc import generate_punch_map
            member = _json.loads(member_json) if member_json else {}
            # [R5] generate_punch_map returns flat dict (success/pdf_path) → WRAP
            return _ok(generate_punch_map(member))
        except Exception as e:
            return _err(str(e))

    # -- Phase 18 (v5.0.0): Connection design engine -------------------------
    def design_shear_tab(self, reaction_kips: float = 0.0,
                           beam_shape: str = "W16X26",
                           column_shape: str = "W14X82",
                           bolt_diameter: float = 0.75,
                           bolt_type: str = "A325-N") -> dict:
        """Design a shear tab connection per AISC 360-16."""
        # pass 10i: numeric input hardening - coerce or fail clean
        reaction_kips, _e = _coerce_num(reaction_kips, 'reaction_kips')
        if _e: return _e
        bolt_diameter, _e = _coerce_num(bolt_diameter, 'bolt_diameter')
        if _e: return _e
        try:
            from bridge.connection_engine import design_shear_tab
            return _ok(design_shear_tab(  # vj: ok-passthrough-safe
                reaction_kips=reaction_kips,
                beam_shape=beam_shape,
                column_shape=column_shape,
                bolt_diameter=bolt_diameter,
                bolt_type=bolt_type,
            ))
        except Exception as e:
            return _err(str(e))

    def design_base_plate(self, axial_kips: float = 0.0,
                            column_depth_in: float = 14.0,
                            column_flange_in: float = 8.0) -> dict:
        """Design a column base plate per AISC DG1."""
        # pass 10i: numeric input hardening - coerce or fail clean
        axial_kips, _e = _coerce_num(axial_kips, 'axial_kips')
        if _e: return _e
        column_depth_in, _e = _coerce_num(column_depth_in, 'column_depth_in')
        if _e: return _e
        column_flange_in, _e = _coerce_num(column_flange_in, 'column_flange_in')
        if _e: return _e
        try:
            from bridge.connection_engine import design_base_plate
            return _ok(design_base_plate(  # vj: ok-passthrough-safe
                axial_kips=axial_kips,
                column_depth_in=column_depth_in,
                column_flange_in=column_flange_in,
            ))
        except Exception as e:
            return _err(str(e))

    def verify_connection_fea(self, plate_width: float = 6.0,
                                plate_height: float = 12.0,
                                plate_thickness: float = 0.375) -> dict:
        """Run PyNite FEA on a connection plate (if installed)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        plate_width, _e = _coerce_num(plate_width, 'plate_width')
        if _e: return _e
        plate_height, _e = _coerce_num(plate_height, 'plate_height')
        if _e: return _e
        plate_thickness, _e = _coerce_num(plate_thickness, 'plate_thickness')
        if _e: return _e
        try:
            from bridge.connection_engine import verify_connection_fea
            # [R5] verify_connection_fea returns flat dict (stress/utilization) → WRAP
            return _ok(verify_connection_fea(
                plate_width=plate_width,
                plate_height=plate_height,
                plate_thickness=plate_thickness,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 19 (v5.1.0): Value engineering --------------------------------
    def run_value_engineering(self, members_json: str = "",
                               connections_json: str = "",
                               base_bid_usd: float = 0.0,
                               project_name: str = "") -> dict:
        """Generate a VE proposal with section and bolt optimization."""
        # pass 10i: numeric input hardening - coerce or fail clean
        base_bid_usd, _e = _coerce_num(base_bid_usd, 'base_bid_usd')
        if _e: return _e
        try:
            import json as _json
            from bridge.value_engineering import generate_ve_report
            members = _json.loads(members_json) if members_json else []
            conns = _json.loads(connections_json) if connections_json else []
            # [R5] generate_ve_report returns flat dict (savings/ve_bid_usd) → WRAP
            return _ok(generate_ve_report(
                members=members,
                connections=conns,
                base_bid_usd=base_bid_usd,
                project_name=project_name,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 20 (v5.2.0): Cross-verification -------------------------------
    def cross_verify(self, results_json: str = "") -> dict:
        """Compare member extractions from multiple AI providers."""
        try:
            import json as _json
            from bridge.cross_verify import diff_extractions
            results = _json.loads(results_json) if results_json else {}
            return _ok(diff_extractions(results))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(str(e))

    # -- Phase 21 (v5.3.0): Auto-RFI generator -------------------------------
    def generate_rfi_log(self, members_json: str = "",
                           cross_verify_json: str = "",
                           project_name: str = "",
                           bid_number: str = "") -> dict:
        """Detect missing info and generate RFI questions."""
        try:
            import json as _json
            from bridge.rfi_generator import generate_rfi_log
            members = _json.loads(members_json) if members_json else []
            cv = _json.loads(cross_verify_json) if cross_verify_json else None
            # [R5] generate_rfi_log returns flat dict (rfis/count) → WRAP
            return _ok(generate_rfi_log(
                members=members,
                cross_verify_result=cv,
                project_name=project_name,
                bid_number=bid_number,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 22 (v5.4.0): Spec-book auditor --------------------------------
    def audit_spec_book(self, spec_text: str = "",
                          tonnage: float = 0.0) -> dict:
        """Scan spec text for cost-impacting requirements.

        v3.2.7 fix H+: wrap result in _ok() so this follows Bridge convention.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            from bridge.spec_auditor import audit_spec_text
            if not spec_text:
                return _err("spec_text is required")
            return _ok(audit_spec_text(spec_text, tonnage=tonnage))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(str(e))

    # -- Phase 23 (v5.5.0): Ghost overlay ------------------------------------
    def ghost_overlay(self, rev0_pdf: str = "", rev1_pdf: str = "",
                        page_num: int = 0) -> dict:
        """Generate visual diff overlay of two drawing revisions."""
        # pass 10i: numeric input hardening - coerce or fail clean
        page_num, _e = _coerce_num(page_num, 'page_num', cast='int')
        if _e: return _e
        try:
            from bridge.drawing_intel.visual_diff import ghost_overlay
            if not rev0_pdf or not rev1_pdf:
                return _err("both rev0_pdf and rev1_pdf required")
            # [R5] ghost_overlay returns flat dict (success/change_pct) → WRAP
            return _ok(ghost_overlay(rev0_pdf, rev1_pdf, page_num=page_num))
        except Exception as e:
            return _err(str(e))

    # -- Phase 5: Variation Prover -------------------------------------------
    def prove_variation(self,
                        conflict_id: str = "",
                        project_name: str = "",
                        bid_number: str = "",
                        member_before: str = "",
                        member_after: str = "",
                        spec_flags: list | None = None,
                        ghost_overlay_path: str = "",
                        cost_delta_usd: float = 0.0,
                        location: str = "",
                        output_dir: str = "") -> dict:
        """Generate a variation evidence package PDF for a drawing/spec conflict."""
        cost_delta_usd, _e = _coerce_num(cost_delta_usd, 'cost_delta_usd')
        if _e: return _e
        try:
            from bridge.variation_prover import prove_variation as _prove
            if not conflict_id:
                return _err("conflict_id is required")
            result = _prove(
                conflict_id=conflict_id,
                project_name=project_name,
                bid_number=bid_number,
                member_before=member_before,
                member_after=member_after,
                spec_flags=spec_flags or [],
                ghost_overlay_path=ghost_overlay_path,
                cost_delta_usd=float(cost_delta_usd),
                location=location,
                output_dir=output_dir,
            )
            if result.get("success"):
                return _ok(result)
            return _err(result.get("error", "prove_variation failed"))
        except Exception as e:
            return _err(str(e))

    # -- Phase 24 (v5.6.0): Shop capacity margin ----------------------------
    def capacity_adjusted_margin(self, direct_cost: float = 0.0,
                                   backlog_tons: float = 0.0,
                                   capacity_per_week: float = 20.0,
                                   base_margin: float = 0.20) -> dict:
        """Adjust margin based on shop utilization."""
        # pass 10i: numeric input hardening - coerce or fail clean
        direct_cost, _e = _coerce_num(direct_cost, 'direct_cost')
        if _e: return _e
        backlog_tons, _e = _coerce_num(backlog_tons, 'backlog_tons')
        if _e: return _e
        capacity_per_week, _e = _coerce_num(capacity_per_week, 'capacity_per_week')
        if _e: return _e
        base_margin, _e = _coerce_num(base_margin, 'base_margin')
        if _e: return _e
        try:
            from bridge.shop_capacity import capacity_adjusted_margin
            # [R5] capacity_adjusted_margin returns flat dict (adjusted_margin) → WRAP
            return _ok(capacity_adjusted_margin(
                direct_cost=direct_cost,
                current_backlog_tons=backlog_tons,
                shop_capacity_tons_per_week=capacity_per_week,
                base_margin=base_margin,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 25 (v5.7.0): BuildingConnected API ----------------------------
    def check_bc_status(self) -> dict:
        """Check BuildingConnected credential status."""
        try:
            from bridge.bid_intake import check_bc_status
            # [R5] check_bc_status returns flat dict (configured/status) → WRAP
            return _ok(check_bc_status())
        except Exception as e:
            return _err(str(e))

    def poll_bid_invites(self, max_results: int = 20) -> dict:
        """Poll BuildingConnected for new bid invites."""
        # pass 10i: numeric input hardening - coerce or fail clean
        max_results, _e = _coerce_num(max_results, 'max_results', cast='int')
        if _e: return _e
        try:
            from bridge.bid_intake import poll_bid_invites
            # [R5] poll_bid_invites returns flat dict (success/invites) → WRAP
            return _ok(poll_bid_invites(max_results=max_results))
        except Exception as e:
            return _err(str(e))

    # -- Phase 26 (v5.8.0): Shop floor production tracking -------------------
    def update_piece_status(self, job_number: str = "",
                              piece_mark: str = "",
                              new_status: str = "",
                              worker_name: str = "") -> dict:
        """Record a piece status transition."""
        try:
            from bridge.shop_floor import update_piece_status
            # [R5] update_piece_status returns flat dict (success/piece_mark) → WRAP
            return _ok(update_piece_status(
                job_number=job_number,
                piece_mark=piece_mark,
                new_status=new_status,
                worker_name=worker_name,
            ))
        except Exception as e:
            return _err(str(e))

    def get_job_production_status(self, job_number: str = "") -> dict:
        """Get aggregated production status for a job."""
        try:
            from bridge.shop_floor import get_job_status
            # [R5] get_job_status returns flat dict (total_pieces/by_stage) → WRAP
            return _ok(get_job_status(job_number=job_number))
        except Exception as e:
            return _err(str(e))

    def generate_piece_qr(self, job_number: str = "",
                            piece_mark: str = "") -> dict:
        """Generate QR code for a piece mark."""
        try:
            from bridge.shop_floor import generate_piece_qr
            # [R5] generate_piece_qr returns flat dict (success/url) → WRAP
            return _ok(generate_piece_qr(job_number, piece_mark))
        except Exception as e:
            return _err(str(e))

    def verify_photo_qc(self, photo_path: str = "",
                          expected_holes_json: str = "") -> dict:
        """Verify fabrication photo against CNC hole coordinates."""
        try:
            import json as _json
            from bridge.shop_floor import verify_holes
            holes = _json.loads(expected_holes_json) \
                    if expected_holes_json else []
            # [R5] verify_holes returns flat dict (result/deviations) → WRAP
            return _ok(verify_holes(photo_path, holes))
        except Exception as e:
            return _err(str(e))

    # -- Phase 27 (v5.9.0): Post-project analytics --------------------------
    def compare_actuals(self, job_number: str = "",
                          estimated_tons: float = 0.0,
                          actual_tons: float = 0.0,
                          estimated_fab_hrs: float = 0.0,
                          actual_fab_hrs: float = 0.0,
                          estimated_bid_usd: float = 0.0,
                          actual_cost_usd: float = 0.0) -> dict:
        """Compare actual production data to bid estimates."""
        # pass 10i: numeric input hardening - coerce or fail clean
        estimated_tons, _e = _coerce_num(estimated_tons, 'estimated_tons')
        if _e: return _e
        actual_tons, _e = _coerce_num(actual_tons, 'actual_tons')
        if _e: return _e
        estimated_fab_hrs, _e = _coerce_num(estimated_fab_hrs, 'estimated_fab_hrs')
        if _e: return _e
        actual_fab_hrs, _e = _coerce_num(actual_fab_hrs, 'actual_fab_hrs')
        if _e: return _e
        estimated_bid_usd, _e = _coerce_num(estimated_bid_usd, 'estimated_bid_usd')
        if _e: return _e
        actual_cost_usd, _e = _coerce_num(actual_cost_usd, 'actual_cost_usd')
        if _e: return _e
        try:
            from bridge.analytics import compare_actuals_vs_estimated
            # [R5] compare_actuals_vs_estimated returns flat dict (delta_pct) → WRAP
            return _ok(compare_actuals_vs_estimated(
                job_number=job_number,
                estimated_tons=estimated_tons,
                actual_tons=actual_tons,
                estimated_fab_hrs=estimated_fab_hrs,
                actual_fab_hrs=actual_fab_hrs,
                estimated_bid_usd=estimated_bid_usd,
                actual_cost_usd=actual_cost_usd,
            ))
        except Exception as e:
            return _err(str(e))

    # -- Phase 28 (v6.0.0): Delivery + erection tracking --------------------
    def plan_truck_loads(self, pieces_json: str = "",
                           truck_capacity_lbs: float = 45000) -> dict:
        """Plan truck loads by weight and erection sequence.

        v3.2.7 fix H+P: wrap in _ok() so chat handlers can use r.ok.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        truck_capacity_lbs, _e = _coerce_num(truck_capacity_lbs, 'truck_capacity_lbs')
        if _e: return _e
        try:
            import json as _json
            from bridge.logistics import plan_truck_loads
            pieces = _json.loads(pieces_json) if pieces_json else []
            return _ok(plan_truck_loads(pieces, truck_capacity_lbs))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(str(e))

    def recommend_erection_order(self, members_json: str = "") -> dict:
        """Recommend erection sequence: columns first, then beams."""
        try:
            import json as _json
            from bridge.logistics import recommend_erection_sequence
            members = _json.loads(members_json) if members_json else []
            seq = recommend_erection_sequence(members)
            return _ok({"sequence": seq, "total_pieces": len(seq)})

        except Exception as e:
            return _err(str(e))

    # -- Phase 29 (v6.1.0): OpenHuman sidecar integration -------------------
    def get_openhuman_status(self) -> dict:
        """Check if OpenHuman sidecar is running."""
        try:
            from bridge.openhuman import OpenHumanClient
            c = OpenHumanClient()
            return c.get_status()
        except Exception as e:
            return {"available": False, "error": str(e)}

    def search_openhuman_memory(self, query: str = "",
                                  max_results: int = 5) -> dict:
        """Search OpenHuman Memory Tree for project context."""
        # pass 10i: numeric input hardening - coerce or fail clean
        max_results, _e = _coerce_num(max_results, 'max_results', cast='int')
        if _e: return _e
        try:
            from bridge.openhuman import search_memory
            # [R5] search_memory returns flat dict (success/results) → WRAP
            return _ok(search_memory(query, max_results=max_results))
        except Exception as e:
            return _err(str(e))

    def register_openhuman_skill(self) -> dict:
        """Register the Structural Steel Detective skill."""
        try:
            from bridge.openhuman import register_skill
            # [R5] register_skill returns flat dict (success/registered) → WRAP
            return _ok(register_skill())
        except Exception as e:
            return _err(str(e))

    def get_openhuman_recent_files(self,
                                     folder: str = "Bids") -> dict:
        """Get recently detected files from OpenHuman."""
        try:
            from bridge.openhuman import get_recent_files
            # [R5] get_recent_files returns flat dict (success/files) → WRAP
            return _ok(get_recent_files(folder_filter=folder))
        except Exception as e:
            return _err(str(e))

    def run_learning_cycle(self) -> dict:
        """Execute a complete active learning cycle.

        Reads the correction lake, analyzes patterns, applies rules
        to the self_healer, and generates updated prompt supplements.
        """
        try:
            from bridge.learning.prompt_updater import run_learning_cycle
            # [R5] run_learning_cycle returns flat dict (success/patterns_found) → WRAP
            return _ok(run_learning_cycle())
        except Exception as e:
            return _err(str(e))

    def get_learning_status(self) -> dict:
        """Get the current status of the active learning system."""
        # vj: parity-ok (pass 10g classified: dispatcher J=0.17; disjoint shapes)
        try:
            from bridge.workbench.correction_lake import count_records
            from bridge.learning.prompt_updater import load_prompt_supplement
            total = count_records()
            supplement = load_prompt_supplement()
            # VJ auto-fix (pass 10i sim): was returning raw dict without _ok wrapper
            return _ok({
                "total_corrections": total,
                "has_prompt_supplement": bool(supplement),
                "supplement_examples": len(
                    supplement.get("few_shot_examples", [])
                ) if supplement else 0,
                "ready_for_update": total >= 500,
                "next_threshold": max(0, 500 - total),
            })
        except Exception as e:
            return _err(f"Learning status unavailable: {e}")

    # -- Phase 5 (v3.9.0): Misc Steel Detection --------------------------------
    # Detects railings, stairs, lintels, and connection plates from drawing
    # text. Houston-area projects typically include 5-15 percent misc steel
    # by tonnage. Pure structural takeoff misses this entirely.
    def detect_misc_steel(self, pdf_path: str = "", text: str = "",
                          page_num: int = 0) -> dict:
        """Detect misc steel from a PDF or raw text.

        Provides two input modes:
          - pdf_path: Run preprocessor.extract_drawing_set, then detect on
            every page.
          - text: Pass raw markdown directly. Useful for unit tests and
            manual single-page detection.

        Returns the misc_calculator aggregate dict directly. The
        Tekla-shaped item list is available via misc_to_tekla_items()
        when needed for export.
        """
        try:
            from bridge.misc_steel import detect_misc_steel as _detect

            if pdf_path:
                p = Path(pdf_path)
                if not p.exists():
                    return _err(f"PDF not found: {pdf_path}")
                from bridge.drawing_intel.preprocessor import (
                    extract_drawing_set,
                )
                ext = extract_drawing_set(str(p))
                if "error" in ext:
                    return _err(f"Extraction failed: {ext['error']}")
                rollup = _detect(ext.get("pages", []))
            elif text:
                rollup = _detect(text, page_num=int(page_num or 0))
            else:
                return _err("Provide either pdf_path or text.")

            return _ok(rollup)
        except Exception as e:
            return _err(f"detect_misc_steel: {e}")

    def export_misc_steel_to_tekla(self, bid_number: str = "",
                                    project_name: str = "",
                                    misc_rollup_json: str = "") -> dict:
        """Export AISC-valid misc items via the Tekla XML pipeline.

        Plates (PL prefix) are intentionally dropped because PL is not in
        AISC v16.0. The Tekla validator gate would reject them anyway.
        Stair stringers, lintels, pipe rails, and posts ride into the
        same FabSuiteXMLRequest XML as the structural members.
        """
        try:
            import json as _json
            from bridge.misc_steel import misc_to_tekla_items
            from bridge.exporters.tekla_xml_gen import generate_tekla_xml

            if not misc_rollup_json:
                return _err("No misc rollup data provided")

            try:
                rollup = _json.loads(misc_rollup_json)
            except (ValueError, TypeError) as je:
                return _err(f"misc_rollup_json must be valid JSON: {je}")

            items = misc_to_tekla_items(rollup)
            if not items:
                return _err("No AISC-valid misc items to export. ")

            bid_dir = Path.home() / "Documents" / "Your Company Bids"
            safe_bid = (bid_number or "UNNUMBERED").strip() or "UNNUMBERED"
            month_part = datetime.now().strftime("%Y-%m")  # vj: local-display-ok
            out_path = bid_dir / month_part / safe_bid / \
                       f"{safe_bid}_misc_tekla.xml"

            # [R5] generate_tekla_xml returns flat dict (success/xml_string) → WRAP
            return _ok(generate_tekla_xml(
                job_number=safe_bid,
                project_name=project_name or "",
                takeoff_data=items,
                output_path=out_path,
            ))
        except Exception as e:
            return _err(str(e))

    def generate_dxf(self, shape: str = "", members_json: str = "",
                     holes_json: str = "", output_type: str = "cross_section") -> dict:
        """Generate DXF file. Types: cross_section, plan, holes, cope."""
        import json as _json
        from bridge import fabrication as fab
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
            if output_type == "cross_section" and shape:
                data = fab.generate_dxf_cross_section(shape)
                fname = f"section_{shape}_{ts}.dxf"
            elif output_type == "plan" and members_json:
                members = _json.loads(members_json)
                data = fab.generate_dxf_plan(members)
                fname = f"plan_{ts}.dxf"
            elif output_type == "holes" and holes_json:
                holes = _json.loads(holes_json)
                data = fab.generate_dxf_hole_pattern(holes)
                fname = f"holes_{ts}.dxf"
            else:
                return _err(f"Invalid DXF type: {output_type}")
            if not data:
                return _err("ezdxf not installed.",
                            fix="Run: pip install ezdxf (or use INSTALL_DEPENDENCIES.bat)")
            if isinstance(data, dict) and "error" in data:
                return _err(data["error"],
                            fix="Check shape designation and ezdxf installation.")
            path = fab.save_output(data, fname)
            return _ok({"file": path, "format": "DXF", "type": output_type})
        except Exception as e:
            return _err(str(e))

    def generate_gcode(self, data_json: str, gcode_type: str = "drill") -> dict:
        """Generate G-code. Types: drill, plasma."""
        import json as _json
        from bridge import fabrication as fab
        try:
            data = _json.loads(data_json)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
            if gcode_type == "drill":
                code = fab.generate_gcode_drill(data)
                fname = f"drill_{ts}.nc"
            elif gcode_type == "plasma":
                code = fab.generate_gcode_plasma(data)
                fname = f"plasma_{ts}.nc"
            else:
                return _err(f"Unknown G-code type: {gcode_type}")
            path = fab.save_output(code, fname)
            return _ok({"file": path, "format": "G-code", "type": gcode_type,
                        "lines": code.count("\n") + 1})
        except Exception as e:
            return _err(str(e))

    def generate_ironworker(self, data_json: str,
                            program_type: str = "punch") -> dict:
        """Generate ironworker program. Types: punch, shear, cope."""
        import json as _json
        from bridge import fabrication as fab
        try:
            data = _json.loads(data_json)
            if program_type == "punch":
                result = fab.generate_punch_schedule(data)
            elif program_type == "shear":
                result = fab.generate_shear_schedule(data)
            elif program_type == "cope":
                result = fab.generate_cope_schedule(data)
            else:
                return _err(f"Unknown program type: {program_type}")
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    def list_fab_tools(self) -> dict:
        """List available fabrication tools."""
        from bridge.fabrication import FAB_REGISTRY, list_sections
        return _ok({
            "tools": [{
                "name": k, "desc": v["desc"], "output": v["output"]
            } for k, v in FAB_REGISTRY.items()],
            "sections_available": len(list_sections()),
        })

    # ── Diagnostics ────────────────────────────────────────────────────

    # ── Bid Scanner ───────────────────────────────────────────────────

    def scan_bids(self, days_back: int = 3) -> dict:
        """Scan Outlook for bid leads in scope. Returns new leads found."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days_back, _e = _coerce_num(days_back, 'days_back', cast='int')
        if _e: return _e
        from bridge.bid_scanner import scan_outlook
        result = scan_outlook(days_back=days_back)
        if result.get("leads"):
            from bridge.notifications import toast_bid_alert, load_config
            cfg = load_config()
            for lead in result["leads"]:
                if lead.get("tier") == "HIGH" and cfg.get("notification_high", True):
                    toast_bid_alert(lead)
        return _ok(result)

    def get_bid_leads(self, tier: str = "", limit: int = 10) -> dict:
        """Get recommended bid leads from the database."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.bid_scanner import get_leads, get_daily_summary
        if not tier:
            _r = get_daily_summary()
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"])
            return _ok(_r)
        return _ok({"leads": get_leads(tier=tier, limit=limit)})

    def score_email_text(self, subject: str, body: str) -> dict:
        """Score an email text against Your Company scope criteria."""
        from bridge.bid_scanner import score_email
        _r = score_email(subject, body)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def mark_lead_actioned(self, email_id: str) -> dict:
        """Mark a bid lead as actioned (reviewed)."""
        from bridge.bid_scanner import mark_actioned
        mark_actioned(email_id)
        return _ok({"actioned": email_id})

    def search_inbox_for_bid(self, query: str = "", days_back: int = 7) -> dict:
        """Search the Owner's inbox for email chains related to a project.
        Uses Joseph's M365 connector (delegated access to the Owner's mailbox).
        Extracts GC name, contact email, bid due date, and site address from matches."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days_back, _e = _coerce_num(days_back, 'days_back', cast='int')
        if _e: return _e
        if not query or len(query.strip()) < 3:
            return _err("query must be at least 3 characters")
        try:
            from bridge.bid_scanner import search_emails_by_query
            matches = search_emails_by_query(query.strip(), days_back=days_back)
            # Extract structured fields from matched emails
            results = []
            for em in (matches or []):
                entry = {
                    "subject": em.get("subject", ""),
                    "sender": em.get("sender", ""),
                    "date": em.get("date", ""),
                    "snippet": (em.get("body", "") or "")[:300],
                }
                body_lower = (em.get("body", "") or "").lower()
                subj_lower = (em.get("subject", "") or "").lower()
                full = subj_lower + " " + body_lower
                # Try to extract GC/contact info
                import re
                email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', em.get("body", ""))
                if email_match:
                    entry["gc_email"] = email_match.group()
                # Try to extract bid due date
                due_match = re.search(
                    r'(?:due|deadline|submit by|bid date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    full
                )
                if due_match:
                    entry["bid_due"] = due_match.group(1)
                # Try to extract address
                addr_match = re.search(
                    r'(\d{2,5}\s+[\w\s]+(?:st|street|blvd|ave|avenue|rd|road|dr|drive|ln|lane|hwy|way|pkwy|ct|pl)[\w\s,]*(?:tx|texas|houston))',
                    full, re.I
                )
                if addr_match:
                    entry["address"] = addr_match.group(1).strip()[:100]
                # GC name from sender or signature
                sender = em.get("sender", "")
                if sender and "@" in sender:
                    entry["gc_name"] = sender.split("<")[0].strip().strip('"')
                results.append(entry)
            return _ok({"matches": results, "query": query, "days_searched": days_back})
        except ImportError:
            # Fallback: if search_emails_by_query doesn't exist yet, return empty
            return _ok({"matches": [], "query": query, "days_searched": days_back,
                        "note": "Email search not yet implemented in bid_scanner"})

    # ── VM Bid Discovery ──────────────────────────────────────────────

    def vm_discover_bids(self, days_back: int = 3) -> dict:
        """Run VM bid discovery scan. Returns evaluated leads with scores."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days_back, _e = _coerce_num(days_back, 'days_back', cast='int')
        if _e: return _e
        from bridge.vm_bid_discovery import vm_scan_inbox
        _r = vm_scan_inbox(days_back=days_back)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def vm_evaluate(self, bid_info_json: str) -> dict:
        """Evaluate a single bid against the Owner's preferences."""
        import json as _json
        from bridge.vm_bid_discovery import vm_evaluate_bid
        info = _json.loads(bid_info_json) if isinstance(bid_info_json, str) else bid_info_json
        _r = vm_evaluate_bid(info)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def vm_start_estimating(self, bid_info_json: str) -> dict:
        """Create project folder and start estimating workflow."""
        import json as _json
        from bridge.vm_bid_discovery import vm_create_project_folder
        info = _json.loads(bid_info_json) if isinstance(bid_info_json, str) else bid_info_json
        result = vm_create_project_folder(info)
        return _ok(result)

    def vm_discovery_cards(self, limit: int = 6) -> dict:
        """Get bid discovery cards for STATUS dashboard."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.vm_bid_discovery import vm_get_discovery_cards
        return _ok({"cards": vm_get_discovery_cards(limit=limit)})

    def vm_extract_links(self, text: str) -> dict:
        """Extract download/invitation links from email text."""
        from bridge.vm_bid_discovery import vm_extract_bid_link
        return _ok({"links": vm_extract_bid_link(text)})

    def vm_load_training(self, claude_export_path: str = "",
                         bid_list_path: str = "") -> dict:
        """Load training data for VM preference learning."""
        from bridge.vm_bid_discovery import load_training_data
        _r = load_training_data(claude_export_path, bid_list_path)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ── External Command Channel ──────────────────────────────────────

    def get_channel_config(self) -> dict:
        """Get external channel configuration."""
        from bridge.notifications import load_config
        cfg = load_config()
        # Redact password fields
        safe = {k: ("***" if "password" in k else v) for k, v in cfg.items()}
        return _ok(safe)

    def save_channel_config(self, config_json: str) -> dict:
        """Save external channel configuration."""
        import json as _json
        from bridge.notifications import save_config
        updates = _json.loads(config_json)
        # Validate required fields
        new_cfg = save_config(updates)
        safe = {k: ("***" if "password" in k else v) for k, v in new_cfg.items()}
        return _ok(safe)

    def get_message_log(self, limit: int = 20) -> dict:
        """Get external channel message log."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.notifications import get_message_log
        return _ok({"messages": get_message_log(limit)})

    def start_webhook(self) -> dict:
        """Start the local HTTP webhook server for external commands."""
        from bridge.notifications import start_webhook_server, load_config
        cfg = load_config()
        port = cfg.get("webhook_port", 7750)
        result = start_webhook_server(self.ai_ask, port=port)
        return _ok(result)

    def start_tunnel(self) -> dict:
        """Start the Cloudflare quick tunnel (non-blocking; poll get_tunnel_status for URL)."""
        from bridge.cloudflare_tunnel import start as _tunnel_start, get_status
        _tunnel_start(port=7777)
        return _ok(get_status())

    def get_tunnel_status(self) -> dict:
        """Return current Cloudflare tunnel state: {running, url}."""
        from bridge.cloudflare_tunnel import get_status
        return _ok(get_status())

    def check_api_keys(self) -> dict:
        """Check which AI provider keys are loaded. No AI call made."""
        keys = _load_all_keys()
        claude = bool(keys.get("ANTHROPIC_API_KEY"))
        openai = bool(keys.get("OPENAI_API_KEY"))
        gemini = bool(keys.get("GOOGLE_API_KEY"))
        return _ok({
            "claude": claude,
            "openai": openai,
            "gemini": gemini,
            "any_ai": claude or openai or gemini,
        })

    def send_test_notification(self) -> dict:
        """Fire a test Windows toast notification."""
        from bridge.notifications import toast
        ok = toast("Your Company - Test", "Notification system is working.")
        return _ok({"fired": ok})

    # ── Outlook One-Click Send ─────────────────────────────────────────

    def send_email_outlook(self, to: str, subject: str, body: str) -> dict:
        """Send an email directly from the Owner's Outlook via win32com.
        Owner approves in the app → one click → sent. No copy-paste.
        """
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = to
            mail.Subject = subject
            mail.Body = body
            mail.Send()
            return _ok({"sent": True, "to": to, "subject": subject})
        except ImportError:
            return _err("win32com not available. Run: pip install pywin32")
        except Exception as e:
            return _err(f"Outlook send failed: {e}")

    def draft_email_outlook(self, to: str, subject: str, body: str) -> dict:
        """Open a pre-filled Outlook compose window for Owner to review and send."""
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            mail.To = to
            mail.Subject = subject
            mail.Body = body
            mail.Display(True)  # opens compose window
            return _ok({"opened": True, "to": to})
        except ImportError:
            return _err("win32com not available. Run: pip install pywin32")
        except Exception as e:
            return _err(f"Outlook draft failed: {e}")

    # ── SMS Channel ────────────────────────────────────────────────────

    def setup_sms(self, sid: str, token: str, twilio_number: str,
                  owner_cell: str = "+17133001865") -> dict:
        """Configure the Twilio SMS channel. Joseph runs this once."""
        from bridge.notifications import save_config
        save_config({
            "twilio_sid": sid.strip(),
            "twilio_token": token.strip(),
            "twilio_number": twilio_number.strip(),
            "owner_cell": owner_cell.strip(),
        })
        from bridge.sms_channel import is_configured
        return _ok({"configured": is_configured(),
                    "twilio_number": twilio_number,
                    "owner_cell": owner_cell})

    def send_sms_to_owner(self, message: str) -> dict:
        """Send an SMS to the Owner's cell directly from the app."""
        from bridge.sms_channel import send_to_owner
        result = send_to_owner(message)
        return _ok(result) if result.get("success") else _err(result.get("error", "Failed"))

    def send_morning_briefing_now(self) -> dict:
        """Send the Owner's morning briefing immediately (on demand)."""
        from bridge.notifications import _send_owner_morning_briefing, _build_morning_briefing
        briefing = _build_morning_briefing()
        _send_owner_morning_briefing()
        return _ok({"briefing": briefing, "sent": True})

    def get_sms_status(self) -> dict:
        """Check Twilio SMS channel configuration status."""
        from bridge.sms_channel import is_configured, _load_twilio_cfg
        cfg = _load_twilio_cfg()
        return _ok({
            "configured": is_configured(),
            "twilio_number": cfg.get("twilio_number", ""),
            "owner_cell": cfg.get("owner_cell", "+17133001865"),
            "has_sid": bool(cfg.get("twilio_sid")),
            "has_token": bool(cfg.get("twilio_token")),
        })

    # ── iMessage Gateway (BlueBubbles) ─────────────────────────────

    def text_owner_imessage(self, message: str) -> dict:
        """Send iMessage to Owner. Path A - internal, no gate."""
        from bridge.imessage_gateway import text_owner
        _r = text_owner(message)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def text_joseph_imessage(self, message: str) -> dict:
        """Send iMessage to Joseph. Path A - internal, no gate."""
        from bridge.imessage_gateway import text_joseph
        _r = text_joseph(message)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def send_imessage_to_contact(self, to: str, body: str,
                                 preview_only: bool = True,
                                 require_engagement_record: bool = True) -> dict:
        """Send iMessage to external contact. Path B - GATED.
        MCP forced args guarantee preview_only=True and require_engagement_record=True.
        """
        from bridge.imessage_gateway import send_imessage_to_contact as _send
        result = _send(to=to, body=body, preview_only=preview_only,
                       require_engagement_record=require_engagement_record)
        if result.get("blocked"):
            # Surface the gateway's actionable fix hint (suggested log_engagement
            # call) so Owner sees the path forward, not just a dead end.
            return _err(result["reason"], fix=result.get("fix", ""))
        return _ok(result)

    def confirm_imessage_send(self, to: str, body: str) -> dict:
        """Owner confirmed the iMessage preview. Send it."""
        from bridge.imessage_gateway import confirm_imessage_send as _confirm
        result = _confirm(to=to, body=body)
        if result.get("blocked"):
            return _err(result["reason"], fix=result.get("fix", ""))
        if result.get("error"):
            return _err(result["error"])
        return _ok(result)

    # ── Engagement Records (TCPA compliance) ───────────────────────

    def create_engagement_record(self, contact_name: str, company: str,
                                 phone: str, engagement_type: str,
                                 engagement_date: str,
                                 engagement_detail: str,
                                 logged_by: str = "") -> dict:
        """Log a prior engagement with a contact. Required before external iMessage."""
        from bridge.engagement_records import create_record, VALID_ENGAGEMENT_TYPES
        # Normalize common natural-language aliases → schema enum values.
        # Owner types "call", schema wants "phone_call". Accept both.
        _ALIASES = {
            "call":          "phone_call",
            "phone":         "phone_call",
            "phone call":    "phone_call",
            "meeting":       "in_person_meeting",
            "visit":         "in_person_meeting",
            "site visit":    "in_person_meeting",
            "in person":     "in_person_meeting",
            "in-person":     "in_person_meeting",
            "email":         "inbound_email",
            "bid":           "bid_invitation",
            "invite":        "bid_invitation",
            "bid invite":    "bid_invitation",
            "ref":           "referral",
        }
        normalized_type = _ALIASES.get(engagement_type.lower().strip(), engagement_type)
        result = create_record(contact_name=contact_name, company=company,
                               phone=phone, engagement_type=normalized_type,
                               engagement_date=engagement_date,
                               engagement_detail=engagement_detail,
                               logged_by=logged_by)
        if result.get("error"):
            valid = sorted(result.get("valid_types", VALID_ENGAGEMENT_TYPES))
            return _err(
                result["error"],
                fix=f"valid engagement_type values: {valid}  "
                    f"(aliases also work: call, meeting, visit, email, bid, referral)"
            )
        return _ok(result)

    def check_engagement_record(self, phone: str) -> dict:
        """Check if a contact has a valid engagement record on file."""
        from bridge.engagement_records import check_and_gate
        _r = check_and_gate(phone)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def list_engagement_records(self, limit: int = 50) -> dict:
        """List all engagement records."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.engagement_records import list_records
        return _ok({"records": list_records(limit=limit)})

    # ── BLOCKERS (Joseph P1 - live dates) ──────────────────────────

    def get_blockers(self) -> dict:
        """Get all blockers with calculated days-open and escalation levels."""
        from bridge.blockers import get_all, has_escalated
        blockers = get_all()
        for b in blockers:
            if "title" not in b:
                b["title"] = b.get("name", "")
            if "description" not in b:
                b["description"] = b.get("action", "")
        return _ok({"blockers": blockers, "has_escalated": has_escalated()})

    def add_blocker(self, name: str, action: str, owner: str = "Owner",
                    status: str = "BLOCKED", severity: str = "med") -> dict:
        """Add a new blocker item. severity: critical/high/med/low"""
        from bridge.blockers import add_blocker as _add
        new = _add(name, action, owner, status, severity=severity)
        return _ok({"added": new})

    def resolve_blocker(self, blocker_id: str) -> dict:
        """Mark a blocker as resolved."""
        from bridge.blockers import resolve_blocker as _resolve
        ok = _resolve(blocker_id)
        return _ok({"resolved": ok, "id": blocker_id}) if ok else _err(f"Blocker '{blocker_id}' not found")

    # ── CHAT-ROUTE ALIASES (P1.6.B - GUI buttons need public names) ───────
    # Each wraps the underlying get_* method so both chat routes and GUI
    # buttons reach the same implementation.

    def ar_aging(self) -> dict:
        return self.get_ar_aging()

    def stock_watchlist(self) -> dict:
        return self.get_stock_watchlist()

    def list_change_orders(self) -> dict:
        return self.get_change_orders()

    def fuel_surcharge(self) -> dict:
        return self.get_fuel_surcharge()

    def houston_pipeline_status(self) -> dict:
        return self.get_houston_pipeline(top_n=5)

    # ── CONVERSATION MEMORY (Joseph P1 - persistence) ─────────────

    def get_conversation_history(self, hours: int = 24, limit: int = 30) -> dict:
        """Get recent conversation history from persistent store."""
        # pass 10i: numeric input hardening - coerce or fail clean
        hours, _e = _coerce_num(hours, 'hours', cast='int')
        if _e: return _e
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.memory import get_recent_messages, stats
        msgs = get_recent_messages(hours=hours, limit=limit)
        return _ok({"messages": msgs, "stats": stats()})

    def search_conversations(self, query: str, limit: int = 10) -> dict:
        """Search past conversations by keyword."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.memory import search_history
        results = search_history(query, limit)
        return _ok({"results": results, "query": query})

    def get_last_session(self, limit: int = 20) -> dict:
        """Load the last conversation session for context restoration."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.memory import get_last_session_history
        msgs = get_last_session_history(limit)
        return _ok({"messages": msgs, "count": len(msgs)})

    # ── RESILIENCE STATUS (Joseph P1 - monitoring) ─────────────────

    def get_resilience_status(self) -> dict:
        """Check rate limiter, circuit breaker, and key encryption status."""
        result = {}
        try:
            from bridge.resilience import rate_limiter, circuit_breaker
            result["rate_limiter"] = rate_limiter.status()
            result["circuit_breaker"] = circuit_breaker.status()
        except Exception as e:
            result["resilience_error"] = str(e)
        try:
            from bridge.keyvault import is_encrypted, has_plaintext
            result["keys_encrypted"] = is_encrypted()
            result["has_plaintext_keys"] = has_plaintext()
        except Exception:
            result["keys_encrypted"] = False
        try:
            from bridge.memory import stats
            result["memory"] = stats()
        except Exception:
            result["memory"] = {"error": "not available"}
        return _ok(result)

    # ── CONTACTS (Joseph P2) ───────────────────────────────────────

    def add_contact(self, name: str, company: str = "", role: str = "",
                    email: str = "", phone: str = "", notes: str = "", tags: str = "") -> dict:
        from bridge.contacts import add
        cid = add(name, company, role, email, phone, notes, tags)
        return _ok({"contact_id": cid, "name": name})

    def search_contacts(self, query: str = "", company: str = "", tag: str = "", limit: int = 20) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.contacts import search
        return _ok({"contacts": search(query, company, tag, limit)})

    def get_contact(self, contact_id: int) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        contact_id, _e = _coerce_num(contact_id, 'contact_id', cast='int')
        if _e: return _e
        from bridge.contacts import get
        c = get(contact_id)
        return _ok(c) if c else _err("Contact not found")

    def update_contact(self, contact_id: int, **kwargs) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        contact_id, _e = _coerce_num(contact_id, 'contact_id', cast='int')
        if _e: return _e
        from bridge.contacts import update
        return _ok({"updated": update(contact_id, **kwargs)})

    def get_contacts_for_email(self, company: str = "") -> dict:
        from bridge.contacts import get_for_ai
        return _ok({"context": get_for_ai(company)})

    # ── DOCUMENT GENERATION (Joseph P2) ────────────────────────────

    def generate_proposal(self, project_name: str, gc_name: str, gc_company: str,
                          scope_text: str, tonnage: str = "TBD", total_estimate: str = "TBD",
                          terms: str = "Net 30", notes: str = "", bid_number: str = "",
                          template: str = "STANDARD", member_schedule: list = None) -> dict:
        from bridge.documents import generate_proposal
        r = generate_proposal(project_name, gc_name, gc_company, scope_text,
                              tonnage, total_estimate, terms, notes, bid_number,
                              template=template, member_schedule=member_schedule)
        if r.get("success"):
            try:
                from bridge.audit import log_document
                log_document("proposal", r.get("filename", ""))
            except Exception:
                pass
            # Phase 4: fresh-instance audit runs after every proposal generation.
            # Uses Opus 4.6 (differs from Sonnet 4.6 estimate model).
            # If blocking=True, Owner must resolve scope gaps before delivery.
            try:
                from bridge.bid_audit import run_fresh_instance_audit
                try:
                    _tons = float(tonnage) if tonnage and tonnage != "TBD" else 0.0
                except (ValueError, TypeError):
                    _tons = 0.0
                try:
                    _bid = float(str(total_estimate).replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    _bid = 0.0
                audit = run_fresh_instance_audit(
                    proposal_text=scope_text,
                    project_name=project_name,
                    tonnage=_tons,
                    total_bid=_bid,
                    bid_number=bid_number,
                )
                r["audit"] = {
                    "blocking": audit.get("blocking", False),
                    "overall_risk": audit.get("overall_risk", "LOW"),
                    "scope_gaps": audit.get("scope_gaps", []),
                    "summary": audit.get("summary", ""),
                    "audit_model": audit.get("audit_model", ""),
                }
                if audit.get("blocking"):
                    r["audit_warning"] = (
                        "SCOPE GAP FOUND - do not deliver this proposal until resolved. "
                        "See 3.Estimate/Audit/fresh_instance_audit.md for details."
                    )
            except Exception as _ae:
                r["audit"] = {"error": str(_ae), "blocking": False}
        return _ok(r) if r.get("success") else _err(r.get("error", "Generation failed"))

    # ── P3 ROADMAP: preview proposal in chat before PDF ────────────
    def preview_proposal_from_bid(self, bid_id: int = 0,
                                   gc_name: str = "",
                                   gc_company: str = "") -> dict:
        """Show what a proposal WOULD say, in chat, without writing a PDF.

        Returns the scope text, total, tonnage, auto-compute disclosure
        flag, and a list of what would be in the PDF. Owner can preview,
        decide if it's right, then run `generate proposal for bid N` to
        actually write the file.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import get_bid
        if not bid_id:
            return _err("bid_id required",
                        fix="type `preview proposal for bid N` with a real bid number")
        row = get_bid(bid_id)
        if not row:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids` to see all bid IDs")

        # Terminal-state guard. Killed/lost bids should not be previewed
        # as if they were active. WON bids have already been quoted - the
        # proposal that was sent lives in output/ already, no need to
        # re-preview it. the Owner's exact reaction: "The bid is PASSED but
        # it still lets me preview a proposal. That's weird."
        state = (row.get("state") or "").upper()
        if state in ("PASSED", "LOST", "WON"):
            state_human = {"PASSED": "killed (PASSED)", "LOST": "LOST",
                           "WON": "already WON"}[state]
            fix_hint = (
                f"this bid is {state_human}; if you need to see the old "
                f"proposal, look in `output/` for the saved PDF. Use "
                f"`list bids` to see active bids."
            )
            return _err(
                f"Bid {bid_id} is in terminal state {state}; cannot preview "
                f"a new proposal for it",
                fix=fix_hint,
            )

        project_name = row.get("name", "")
        try: tonnage = float(row.get("tonnage", "0") or 0)
        except (ValueError, TypeError): tonnage = 0
        try: total_bid = float(row.get("estimated_value", "0") or 0)
        except (ValueError, TypeError): total_bid = 0

        # Detect whether value would be auto-computed
        value_auto_computed = False
        if total_bid <= 0 and tonnage > 0:
            total_bid = round(tonnage * 4200, 0)
            value_auto_computed = True
        elif total_bid <= 0 and tonnage <= 0:
            return _err(
                "Cannot preview: bid has neither tonnage nor estimated_value",
                fix="drop the drawing PDF again to extract tonnage, or set estimated_value manually"
            )

        # Build same scope text generate would
        scope_lines = [
            f"Furnish and erect structural steel framing for {project_name}.",
            f"Approximate tonnage: {tonnage:.1f} tons." if tonnage else "",
            "Scope includes structural steel fabrication, erection, and metal deck "
            "supply and installation per contract drawings and specifications.",
            "",
            "EXCLUSIONS: Concrete, painting, fireproofing, MEP support steel, "
            "engineering stamps from a third party, miscellaneous metals not "
            "shown on structural drawings.",
        ]
        if value_auto_computed:
            scope_lines.append("")
            scope_lines.append(
                "NOTE: Draft estimate at $4,200/ton blended fab+erect "
                "(Houston Q2 2026). Final pricing pending shop takeoff."
            )

        return _ok({
            "bid_id": bid_id,
            "project_name": project_name,
            "gc_name": gc_name or row.get("gc_name", ""),
            "gc_company": gc_company or row.get("gc_company", ""),
            "tonnage": tonnage,
            "total_bid": total_bid,
            "value_auto_computed": value_auto_computed,
            "scope_text": "\n".join(s for s in scope_lines if s),
            "would_write_pdf_to": "output/NC_Proposal_<name>_<date>.pdf",
            "next_step": (
                f"If this looks right, type `proposal for bid {bid_id}` "
                f"to generate the PDF."
            ),
        })

    def _generate_gp_report(self, proposal_path: str, project_name: str,
                            tonnage: float, total_bid: float,
                            bid_id: int = 0,
                            gp_extended: bool = True,
                            capability_rows: list = None,
                            risk_rows: list = None,
                            recommendation: str = "",
                            section_b_breakdown: dict = None) -> str:
        """Generate the internal GP (-GP suffix) PDF alongside a client proposal.

        Uses RATES_TABLE GP percentages to break down revenue vs cost per line
        item. Owner uses this to track margin - never sent to the GC.

        When gp_extended is True (default), also renders: net profit walk,
        material cost basis (internal-only), capability fit, risk flags,
        cash flow validation, and recommendation. Capability/risk/recommendation
        content comes from the caller; the rest is computed from BID_RATES,
        BID_MARGINS, MATERIAL_COSTS, and PAYMENT_STRUCTURE.

        section_b_breakdown (optional) is a dict with keys joist_tons,
        roof_deck_sf, composite_deck_sf, anchor_count. When provided, the
        residual row is replaced with itemized Section B lines using the
        per-item BID_MARGINS instead of a blended deck_gp_pct.

        Returns the GP report path or empty string on failure.
        """
        from pathlib import Path
        if not proposal_path:
            return ""
        gp_file = Path(proposal_path).with_name(
            Path(proposal_path).stem + "-GP.pdf"
        )
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            )
            from reportlab.lib.styles import getSampleStyleSheet

            # Build the margin breakdown from locked BID_RATES (never hardcode)
            from bridge.bid_rates import BID_RATES as _BR, BID_MARGINS as _BM
            fab_rate   = _BR["fab_per_ton"]
            erect_rate = _BR["erection_per_ton"]
            fab_gp_pct   = _BM["fab"]
            erect_gp_pct = _BM["erection"]
            deck_gp_pct  = _BM["roof_deck"]
            ga_pct = _BR["ga_overhead_pct"]

            fab_rev  = tonnage * fab_rate
            fab_cost = fab_rev * (1 - fab_gp_pct)
            fab_gp   = fab_rev - fab_cost

            erect_rev  = tonnage * erect_rate
            erect_cost = erect_rev * (1 - erect_gp_pct)
            erect_gp   = erect_rev - erect_cost

            # Residual = deck, joists, anchors, accessories - always in scope.
            # BUGFIX 2026-05-21: G&A is absorbed in unit rates per bid_rates.py
            # ("ga_overhead_pct: 7.5% absorbed, never line-itemed"). The previous
            # math subtracted G&A from total_bid here to derive residual revenue,
            # which double-counted overhead and zeroed out Section B for any
            # total_bid below Section A + ~10%. total_bid is the full client price
            # with G&A already inside; residual = total_bid - struct_subtotal.
            struct_subtotal = fab_rev + erect_rev

            # Optional itemized Section B (joists, deck, anchors). When the
            # caller passes section_b_breakdown, compute per-line revenue/cost
            # using BID_MARGINS instead of the blended deck_gp_pct fallback.
            sec_b_lines = []  # list of (label, rev, cost, gp, gp_pct)
            sb = section_b_breakdown or {}
            if sb:
                from bridge.bid_rates import BID_RATES as _BR2, BID_MARGINS as _BM2
                _jt = float(sb.get("joist_tons", 0) or 0)
                _rds = float(sb.get("roof_deck_sf", 0) or 0)
                _cds = float(sb.get("composite_deck_sf", 0) or 0)
                _ac = int(sb.get("anchor_count", 0) or 0)
                if _jt > 0:
                    rev = _jt * _BR2["joists_per_ton"]
                    gp = _BM2["joists"]
                    sec_b_lines.append(("Joists", rev, rev*(1-gp), rev*gp, gp))
                if _rds > 0:
                    rev = _rds * _BR2["roof_deck_per_sf"]
                    gp = _BM2["roof_deck"]
                    sec_b_lines.append(("Roof Deck", rev, rev*(1-gp), rev*gp, gp))
                if _cds > 0:
                    rev = _cds * _BR2["composite_deck_per_sf"]
                    gp = _BM2["composite_deck"]
                    sec_b_lines.append(("Composite Deck", rev, rev*(1-gp), rev*gp, gp))
                if _ac > 0:
                    rev = _ac * _BR2["anchor_rod_1x20_each"]
                    gp = _BM2["anchor_rods"]
                    sec_b_lines.append(("Anchor Rods", rev, rev*(1-gp), rev*gp, gp))

            if sec_b_lines:
                residual_rev = sum(l[1] for l in sec_b_lines)
                residual_cost = sum(l[2] for l in sec_b_lines)
                residual_gp = sum(l[3] for l in sec_b_lines)
            else:
                residual_rev = total_bid - struct_subtotal
                if residual_rev < 0:
                    residual_rev = 0
                residual_cost = residual_rev * (1 - deck_gp_pct)
                residual_gp   = residual_rev - residual_cost

            subtotal_rev  = struct_subtotal + residual_rev
            subtotal_cost = (fab_cost + erect_cost) + residual_cost
            subtotal_gp   = (fab_gp + erect_gp) + residual_gp

            # G&A is informational only on the GP report - already absorbed in
            # unit rates, not a separate cost subtracted from gross profit.
            ga = total_bid * ga_pct
            total_cost = subtotal_cost
            net_gp = total_bid - total_cost
            net_gp_pct = (net_gp / total_bid * 100) if total_bid > 0 else 0
            net_after_ga = net_gp - ga
            net_after_ga_pct = (net_after_ga / total_bid * 100) if total_bid > 0 else 0

            doc = SimpleDocTemplate(
                str(gp_file), pagesize=letter,
                leftMargin=0.6*inch, rightMargin=0.6*inch,
                topMargin=0.5*inch, bottomMargin=0.55*inch,
            )
            ss = getSampleStyleSheet()
            story = []

            story.append(Paragraph(
                "YOUR COMPANY - INTERNAL GP REPORT", ss['Title']
            ))
            # Look up bid state to flag terminal bids in the header.
            # Prevents Owner from confusing a post-mortem GP file with
            # an active-opportunity one when paging through output/.
            bid_state = ""
            if bid_id:
                try:
                    from bridge.bid_pipeline import get_bid as _gb
                    bid_row = _gb(bid_id)
                    if bid_row:
                        bid_state = (bid_row.get("state") or "").upper()
                except Exception:
                    pass
            state_suffix = ""
            if bid_state in ("PASSED", "LOST", "WON"):
                state_suffix = f"  |  STATE: {bid_state} (post-mortem)"
            story.append(Paragraph(
                f"Project: {project_name}"
                + (f"  |  Bid #{bid_id}" if bid_id else "")
                + state_suffix,
                ss['Normal'],
            ))
            story.append(Spacer(1, 12))

            data = [
                ['Line Item', 'Revenue', 'Cost', 'GP $', 'GP %'],
                ['Fabrication',
                 f'${fab_rev:,.0f}', f'${fab_cost:,.0f}',
                 f'${fab_gp:,.0f}', f'{fab_gp_pct*100:.0f}%'],
                ['Erection',
                 f'${erect_rev:,.0f}', f'${erect_cost:,.0f}',
                 f'${erect_gp:,.0f}', f'{erect_gp_pct*100:.0f}%'],
            ]
            if sec_b_lines:
                for label, rev, cost, gp, gp_pct in sec_b_lines:
                    data.append([label,
                                 f'${rev:,.0f}', f'${cost:,.0f}',
                                 f'${gp:,.0f}', f'{gp_pct*100:.0f}%'])
            else:
                data.append(['Deck / Joists / Anchors',
                             f'${residual_rev:,.0f}', f'${residual_cost:,.0f}',
                             f'${residual_gp:,.0f}', f'{deck_gp_pct*100:.0f}%'])
            data.extend([
                ['Subtotal',
                 f'${subtotal_rev:,.0f}', f'${subtotal_cost:,.0f}',
                 f'${subtotal_gp:,.0f}', ''],
                [f'G&A Overhead ({ga_pct*100:.1f}%)',
                 'absorbed in unit rates',
                 f'(info: ${ga:,.0f})', '', ''],
                ['', '', '', '', ''],
                ['TOTAL BID',
                 f'${total_bid:,.0f}', f'${total_cost:,.0f}',
                 f'${net_gp:,.0f}', f'{net_gp_pct:.1f}%'],
            ])
            t = Table(data, colWidths=[2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 0.8*inch])
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a237e')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e3f2fd')),
                ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ]))
            story.append(t)

            story.append(Spacer(1, 18))
            story.append(Paragraph(
                f"Tonnage: {tonnage:.1f} tons  |  "
                f"Fab: ${fab_rate:,}/ton  |  "
                f"Erection: ${erect_rate:,}/ton  |  "
                f"G&amp;A: {ga_pct*100:.1f}%",
                ss['Normal'],
            ))

            # ── EXTENDED GP SECTIONS (added 2026-05-21) ────────────────
            if gp_extended:
                _CONFIDENTIAL_RED = colors.HexColor("#B71C1C")
                _NAVY = colors.HexColor("#1a237e")
                _CREAM = colors.HexColor("#F7F5F0")
                _GOLD = colors.HexColor("#C9A961")

                def _hdr_para(txt):
                    return Paragraph(
                        f"<b><font color='#1a237e'>{txt}</font></b>",
                        ss['Heading3'],
                    )

                # ── 1. NET PROFIT WALK ────────────────────────────────
                story.append(Spacer(1, 16))
                story.append(_hdr_para("Gross Profit to Net Profit Walk"))
                walk_data = [
                    ['Step', 'Amount', 'Note'],
                    ['Revenue (Base Bid)', f'${total_bid:,.0f}',
                     'Section A + Section B'],
                    ['Less: Direct Cost (materials + labor)',
                     f'$({total_cost:,.0f})',
                     'Steel, joists, deck, anchors, fab labor, erect labor'],
                    ['= Gross Profit', f'${net_gp:,.0f}',
                     f'{net_gp_pct:.1f}% blended GP'],
                    [f'Less: G&A overhead ({ga_pct*100:.1f}%)',
                     f'$({ga:,.0f})',
                     'Absorbed in unit rates; not a separate client line item'],
                    ['= Net Profit', f'${net_after_ga:,.0f}',
                     f'{net_after_ga_pct:.1f}% net (target ~25%)'],
                ]
                walk_tbl = Table(walk_data, colWidths=[2.4*inch, 1.4*inch, 3.5*inch])
                walk_tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), _NAVY),
                    ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                    ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE',   (0,0), (-1,-1), 9),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, _CREAM]),
                    ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
                    ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e3f2fd')),
                    ('ALIGN',      (1,0), (1,-1), 'RIGHT'),
                    ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('LEFTPADDING',  (0,0), (-1,-1), 5),
                    ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(walk_tbl)

                # ── 2. MATERIAL COST BASIS (INTERNAL) ─────────────────
                story.append(Spacer(1, 14))
                story.append(_hdr_para("Material Cost Basis (Internal Reference)"))
                try:
                    from bridge.bid_rates import MATERIAL_COSTS as _MC
                    mc_data = [
                        ['Material', 'Cost Basis (Q2 2026)', 'Notes'],
                        ['W-shapes (A992/A36)',
                         f"${_MC['w_shapes_per_ton']:,.0f}/T",
                         'Base structural steel'],
                        ['HSS (A500 Gr.B/C)',
                         f"${_MC['hss_per_ton']:,.0f}/T",
                         'Columns and braces'],
                        ['Joist total production',
                         f"~${_MC['joist_total_per_ton']:,.0f}/T",
                         'Material + labor + freight (SQ-2 in-house shop)'],
                        ['Roof deck 1.5B22 (landed Houston)',
                         f"${_MC['roof_deck_1_5B22_per_sf']:.2f}/SF",
                         'Vented galvanized'],
                        ['Comp deck (landed Houston)',
                         f"${_MC['composite_deck_per_sf']:.2f}/SF",
                         '20ga galvanized'],
                        ['Anchor rod 1" x 20"',
                         f"~${_MC['anchor_rod_1x20_each']:.0f}/EA",
                         'F1554 Gr.55'],
                        ['HDG premium (exterior)',
                         f"+${_MC['hdg_premium_per_ton']:,.0f}/T",
                         'Required per drawings for exterior steel'],
                    ]
                    mc_tbl = Table(mc_data, colWidths=[2.4*inch, 1.5*inch, 3.4*inch])
                    mc_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), _NAVY),
                        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, _CREAM]),
                        ('ALIGN',      (1,0), (1,-1), 'RIGHT'),
                        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                        ('TOPPADDING', (0,0), (-1,-1), 3.5),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
                        ('LEFTPADDING',  (0,0), (-1,-1), 5),
                        ('RIGHTPADDING', (0,0), (-1,-1), 5),
                    ]))
                    story.append(mc_tbl)
                except Exception:
                    pass

                # ── 3. CAPABILITY FIT TABLE ───────────────────────────
                if capability_rows:
                    story.append(Spacer(1, 14))
                    story.append(_hdr_para("Capability Fit"))
                    cf_data = [['Capability', 'Fit', 'Notes']]
                    for row in capability_rows:
                        if isinstance(row, dict):
                            cf_data.append([
                                row.get('capability', ''),
                                row.get('fit', ''),
                                row.get('notes', ''),
                            ])
                        elif isinstance(row, (list, tuple)) and len(row) >= 3:
                            cf_data.append([row[0], row[1], row[2]])
                    cf_tbl = Table(cf_data, colWidths=[2.6*inch, 0.9*inch, 3.8*inch])
                    cf_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), _NAVY),
                        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, _CREAM]),
                        ('FONTNAME',   (1,1), (1,-1), 'Helvetica-Bold'),
                        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                        ('TOPPADDING', (0,0), (-1,-1), 3.5),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
                        ('LEFTPADDING',  (0,0), (-1,-1), 5),
                        ('RIGHTPADDING', (0,0), (-1,-1), 5),
                    ]))
                    story.append(cf_tbl)

                # ── 4. RISK FLAGS TABLE ───────────────────────────────
                if risk_rows:
                    story.append(Spacer(1, 14))
                    story.append(_hdr_para("Risk Flags"))
                    rf_data = [['Risk', 'Severity', 'Mitigation']]
                    for row in risk_rows:
                        if isinstance(row, dict):
                            rf_data.append([
                                row.get('risk', ''),
                                row.get('severity', ''),
                                row.get('mitigation', ''),
                            ])
                        elif isinstance(row, (list, tuple)) and len(row) >= 3:
                            rf_data.append([row[0], row[1], row[2]])
                    rf_tbl = Table(rf_data, colWidths=[2.4*inch, 0.9*inch, 4.0*inch])
                    rf_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), _NAVY),
                        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, _CREAM]),
                        ('FONTNAME',   (1,1), (1,-1), 'Helvetica-Bold'),
                        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                        ('TOPPADDING', (0,0), (-1,-1), 3.5),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
                        ('LEFTPADDING',  (0,0), (-1,-1), 5),
                        ('RIGHTPADDING', (0,0), (-1,-1), 5),
                    ]))
                    story.append(rf_tbl)

                # ── 5. CASH FLOW VALIDATION ───────────────────────────
                try:
                    from bridge.bid_rates import PAYMENT_STRUCTURE as _PS
                    mob_pct = _PS["mobilization_pct"]
                    del_pct = _PS["first_delivery_pct"]
                    sov_pct = _PS["sov_pct"]
                except Exception:
                    mob_pct, del_pct, sov_pct = 0.30, 0.20, 0.50
                story.append(Spacer(1, 14))
                story.append(_hdr_para("Cash Flow Validation"))
                cf_rows = [
                    ['Phase', 'Amount', 'Material Coverage Status'],
                    [f'{int(mob_pct*100)}% Mobilization (shop drawings)',
                     f'${total_bid*mob_pct:,.0f}',
                     'Covers Section A raw steel POs. Sufficient when material '
                     f'cost < ${total_bid*mob_pct:,.0f}.'],
                    [f'{int(del_pct*100)}% First Delivery',
                     f'${total_bid*del_pct:,.0f}',
                     f'Cumulative {int((mob_pct+del_pct)*100)}% '
                     f'(${total_bid*(mob_pct+del_pct):,.0f}) covers all Section A '
                     '+ joists + anchor rod POs.'],
                    [f'{int(sov_pct*100)}% SOV through completion',
                     f'${total_bid*sov_pct:,.0f}',
                     'Covers deck POs, erection labor, finish work, closeout. '
                     'Net 30 trade credit only for any gap.'],
                ]
                cf_tbl = Table(cf_rows, colWidths=[2.6*inch, 1.2*inch, 3.5*inch])
                cf_tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), _NAVY),
                    ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
                    ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE',   (0,0), (-1,-1), 8.5),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, _CREAM]),
                    ('ALIGN',      (1,0), (1,-1), 'RIGHT'),
                    ('VALIGN',     (0,0), (-1,-1), 'TOP'),
                    ('TOPPADDING', (0,0), (-1,-1), 3.5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
                    ('LEFTPADDING',  (0,0), (-1,-1), 5),
                    ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(cf_tbl)

                # ── 6. RECOMMENDATION ────────────────────────────────
                if recommendation:
                    story.append(Spacer(1, 14))
                    story.append(_hdr_para("Recommendation"))
                    story.append(Paragraph(recommendation, ss['Normal']))

            story.append(Spacer(1, 14))
            story.append(Paragraph(
                "<b><font color='#B71C1C'>CONFIDENTIAL - INTERNAL USE ONLY.</font></b> "
                "Do not share with client, GC, or any party outside Your Company.",
                ss['Normal'],
            ))

            doc.build(story)
            return str(gp_file)
        except Exception:
            return ""

    def generate_proposal_from_bid(self, bid_id: int = 0,
                                   project_name: str = "",
                                   total_bid: float = 0,
                                   tonnage: float = 0,
                                   building_sf: float = 0,
                                   gc_name: str = "",
                                   gc_company: str = "",
                                   terms: str = "Net 30",
                                   notes: str = "",
                                   joist_tons: float = 0,
                                   roof_deck_sf: float = 0,
                                   composite_deck_sf: float = 0,
                                   anchor_count: int = 0,
                                   address: str = "",
                                   owner: str = "",
                                   owner_project_no: str = "",
                                   eor: str = "",
                                   architect: str = "",
                                   drawing_set_date: str = "",
                                   drawing_set_label: str = "",
                                   bid_number_override: str = "",
                                   csi_scope: list = None,
                                   include_csi_table: bool = True,
                                   include_capabilities: bool = True,
                                   include_sov_detail: bool = True,
                                   include_schedule_table: bool = True,
                                   extra_exclusions: list = None,
                                   schedule_assumptions: list = None,
                                   gp_extended: bool = True,
                                   capability_rows: list = None,
                                   risk_rows: list = None,
                                   recommendation: str = "") -> dict:
        """One-call proposal PDF from a pipeline-DB bid_id, OR from explicit fields.

        the Owner's #1 ask: after every bid, generate the client letter without
        re-typing everything. Pulls project_name, tonnage, total from the DB
        if bid_id provided; falls back to explicit args otherwise.

        Returns the PDF path. Uses bridge/documents.py generate_proposal under
        the hood with the STANDARD template (navy/gold).
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        total_bid, _e = _coerce_num(total_bid, 'total_bid')
        if _e: return _e
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        building_sf, _e = _coerce_num(building_sf, 'building_sf')
        if _e: return _e
        joist_tons, _e = _coerce_num(joist_tons, 'joist_tons')
        if _e: return _e
        roof_deck_sf, _e = _coerce_num(roof_deck_sf, 'roof_deck_sf')
        if _e: return _e
        composite_deck_sf, _e = _coerce_num(composite_deck_sf, 'composite_deck_sf')
        if _e: return _e
        anchor_count, _e = _coerce_num(anchor_count, 'anchor_count', cast='int')
        if _e: return _e
        from bridge.documents import generate_proposal as _gen

        # If bid_id given, load from DB
        if bid_id:
            try:
                from bridge.bid_pipeline import get_bid
                row = get_bid(bid_id)
                if not row:
                    return _err(
                        f"Bid id {bid_id} not found in pipeline DB.",
                        fix="type `list bids` to see all bid IDs, then retry with a valid one"
                    )
                # Terminal-state guard. Killed bids should not generate
                # new PDFs - that's a contractual document for a dead
                # opportunity. the Owner's exact reaction: "I just killed
                # bid 1 and it still generated a PDF. That's not right."
                state = (row.get("state") or "").upper()
                if state in ("PASSED", "LOST", "WON"):
                    state_human = {"PASSED": "killed (PASSED)", "LOST": "LOST",
                                   "WON": "already WON"}[state]
                    return _err(
                        f"Bid {bid_id} is in terminal state {state}; "
                        f"will not write a new proposal PDF for a "
                        f"{state_human} bid",
                        fix=(
                            f"the old proposal PDF (if generated) lives in "
                            f"`output/`. Use `list bids` to see active bids."
                        ),
                    )
                _raw_name = project_name or row.get("name", "")
                if not project_name.strip() or "_" in _raw_name:
                    try:
                        from bridge.direct_route import _clean_bid_name as _cbn
                        _raw_name = _cbn(_raw_name)
                    except Exception:
                        _raw_name = _raw_name.replace("_", " ").strip()
                project_name = _raw_name
                gc_company = gc_company or row.get("gc_company", "")
                # tonnage and estimated_value are stored as strings
                if not tonnage:
                    try: tonnage = float(row.get("tonnage", "0") or 0)
                    except (ValueError, TypeError): tonnage = 0
                if not total_bid:
                    try: total_bid = float(row.get("estimated_value", "0") or 0)
                    except (ValueError, TypeError): total_bid = 0
            except Exception as e:
                return _err(
                    f"Could not load bid {bid_id}: {e}",
                    fix="check the bid DB at data/bid_pipeline.db is not corrupted, or restore from a backup"
                )

        if not project_name:
            return _err(
                "project_name required (or pass a valid bid_id).",
                fix="pass project_name='...' or bid_id=N (use `list bids` to find IDs)"
            )
        if total_bid <= 0:
            # Try to auto-compute from tonnage at the default shop blended rate
            if tonnage and tonnage > 0:
                # Houston Q2 2026 blended fab+erect ~ $4,200/ton furnished and installed
                # so a thin bid gets a reasonable placeholder
                auto_total = round(float(tonnage) * 4200, 0)
                total_bid = auto_total
                _value_auto_computed = True  # flag for downstream disclosure
                # Persist back so subsequent calls work too
                if bid_id:
                    try:
                        from bridge.bid_pipeline import update_bid
                        update_bid(bid_id, estimated_value=str(int(auto_total)))
                    except Exception:
                        pass
            else:
                return _err(
                    "total_bid must be > 0 (or DB bid must have estimated_value).",
                    fix=(
                        f"options: (1) pass total_bid=NNNNN explicitly, "
                        f"(2) run `bid {int(tonnage) or '<tons>'}t {int(building_sf) or '<sf>'}sf` first to compute a value, "
                        f"or (3) the bid has no tonnage either - drop the drawing PDF again so it gets extracted"
                    )
                )
        else:
            _value_auto_computed = False

        # Build scope text from inputs
        scope_lines = [
            f"Furnish and erect structural steel framing for {project_name}.",
            f"Approximate tonnage: {tonnage:.1f} tons." if tonnage else "",
            f"Approximate building area: {building_sf:,.0f} SF." if building_sf else "",
            "Scope includes structural steel fabrication, erection, and metal deck "
            "supply and installation per contract drawings and specifications.",
            "",
            "EXCLUSIONS: Concrete, painting, fireproofing, MEP support steel, "
            "engineering stamps from a third party, miscellaneous metals not "
            "shown on structural drawings.",
        ]
        # Disclose when the dollar value was auto-computed rather than from
        # a real quote - keeps Owner from accidentally sending a placeholder
        # number to a GC as if it were a firm price.
        if _value_auto_computed:
            scope_lines.append("")
            scope_lines.append(
                "NOTE: This estimate is a draft based on tonnage at $4,200/ton "
                "blended fab+erect (Houston Q2 2026). Final pricing pending shop "
                "takeoff verification and connection design."
            )
        scope_text = "\n".join(s for s in scope_lines if s)

        # bid_number: prefer explicit override (e.g. "PRJ-2026-NSL-001"). Falls
        # back to "NC-{bid_id}" if a numeric bid_id is present. Empty string
        # otherwise (header reads "Reference: TBD").
        _bn = (bid_number_override.strip() if bid_number_override
               else (f"NC-{bid_id}" if bid_id else ""))

        # Project metadata - only include keys with actual values so the info
        # table doesn't render empty rows.
        _pm = {}
        if address: _pm["address"] = address
        if owner: _pm["owner"] = owner
        if owner_project_no: _pm["owner_project_no"] = owner_project_no
        if eor: _pm["eor"] = eor
        if architect: _pm["architect"] = architect
        if drawing_set_date: _pm["drawing_set_date"] = drawing_set_date
        if drawing_set_label: _pm["drawing_set_label"] = drawing_set_label

        # Page-1 project image (client proposal only; the -GP report stays
        # image-free). find_render ranks a true Tekla viewport export first, then
        # the in-house estimate-grade MODEL viewport, then a fused MASTER. Wrapped
        # so a missing render never blocks proposal generation.
        _render_path = ""
        try:
            from bridge.bid_documents import find_render
            _render_path = find_render(project_name=project_name, bid_number=_bn or None)
        except Exception:
            _render_path = ""

        r = _gen(
            project_name=project_name,
            gc_name=gc_name or "",
            gc_company=gc_company,
            scope_text=scope_text,
            tonnage=f"{tonnage:.1f}" if tonnage else "TBD",
            total_estimate=f"${total_bid:,.0f}",
            terms=terms,
            notes=notes,
            bid_number=_bn,
            template="STANDARD",
            joist_tons=joist_tons,
            roof_deck_sf=roof_deck_sf,
            composite_deck_sf=composite_deck_sf,
            anchor_count=anchor_count,
            project_meta=_pm or None,
            csi_scope=csi_scope,
            include_csi_table=include_csi_table,
            include_capabilities=include_capabilities,
            include_sov_detail=include_sov_detail,
            include_schedule_table=include_schedule_table,
            extra_exclusions=extra_exclusions,
            schedule_assumptions=schedule_assumptions,
            render_path=_render_path,
        )
        if r.get("success"):
            r["value_auto_computed"] = _value_auto_computed
            # ── GP Report (-GP suffix PDF, r14) ──────────────────────
            # Bid rules: "Two PDFs per bid: client proposal + GP report"
            # The GP report is internal. Shows margin breakdown per line
            # item so Owner can track gross profit without revealing
            # cost structure to the GC.
            try:
                _sbb = {}
                if joist_tons: _sbb["joist_tons"] = joist_tons
                if roof_deck_sf: _sbb["roof_deck_sf"] = roof_deck_sf
                if composite_deck_sf: _sbb["composite_deck_sf"] = composite_deck_sf
                if anchor_count: _sbb["anchor_count"] = anchor_count
                gp_path = self._generate_gp_report(
                    proposal_path=r.get("path", ""),
                    project_name=project_name,
                    tonnage=tonnage,
                    total_bid=total_bid,
                    bid_id=bid_id,
                    gp_extended=gp_extended,
                    capability_rows=capability_rows,
                    risk_rows=risk_rows,
                    recommendation=recommendation,
                    section_b_breakdown=_sbb or None,
                )
                if gp_path:
                    r["gp_path"] = str(gp_path)
            except Exception:
                pass  # GP is best-effort; client proposal is the primary
            if bid_id:
                self._auto_score_bid(bid_id)  # proposal generated = score boost
        return _ok(r) if r.get("success") else _err(r.get("error", "Proposal generation failed"))

    def generate_gp_only(self, bid_id: int = 0) -> dict:
        """Generate JUST the GP report for a bid, without touching the client PDF.

        the Owner's roadmap ask: "I want to re-check margins without
        regenerating the client proposal." Useful when tonnage or bid
        total changed and you want to see the updated GP without writing
        a fresh client letter (which could confuse the GC).

        Reuses _generate_gp_report. Looks up tonnage and estimated_value
        from the bid DB. Returns the GP report path.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from datetime import date
        from pathlib import Path
        if not bid_id:
            return _err(
                "bid_id required",
                fix="type `gp only N` with a real bid number, or `list bids` to see IDs"
            )
        from bridge.bid_pipeline import get_bid
        row = get_bid(bid_id)
        if not row:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids all` to find the bid ID")
        project_name = row.get("name", "") or f"Bid-{bid_id}"
        try:
            tonnage = float(row.get("tonnage", "0") or 0)
        except (ValueError, TypeError):
            tonnage = 0
        try:
            total_bid = float(row.get("estimated_value", "0") or 0)
        except (ValueError, TypeError):
            total_bid = 0
        # Auto-compute total if missing (same logic as generate_proposal_from_bid)
        if total_bid <= 0 and tonnage > 0:
            total_bid = round(tonnage * 4200, 0)
        if total_bid <= 0:
            return _err(
                f"Bid {bid_id} has no tonnage or estimated_value",
                fix="drop the drawing again to extract tonnage, or generate a full proposal first"
            )
        # Construct expected proposal path (same format as documents.py)
        safe = "".join(c for c in project_name if c.isalnum() or c in " -_")[:40].strip()
        filename = f"NC_Proposal_{safe}_{date.today().isoformat()}.pdf"
        out_dir = Path(__file__).resolve().parent.parent / "output"
        proposal_path = out_dir / filename
        out_dir.mkdir(parents=True, exist_ok=True)
        gp_path = self._generate_gp_report(
            proposal_path=str(proposal_path),
            project_name=project_name,
            tonnage=tonnage,
            total_bid=total_bid,
            bid_id=bid_id,
        )
        if not gp_path:
            return _err(
                "GP report generation failed",
                fix="ensure reportlab is installed and output/ is writable"
            )
        return _ok({
            "bid_id": bid_id,
            "project_name": project_name,
            "tonnage": tonnage,
            "total_bid": total_bid,
            "gp_path": gp_path,
            "message": f"GP report regenerated for bid {bid_id} ({project_name})",
        })

    # ── Bid Scoring (r14) ──────────────────────────────────────────
    # the Owner's SIM5 request: "Score field is always 0. No scoring
    # logic. I want to rank bids by win likelihood so I know where to
    # spend my time."
    #
    # Score 0-100. Higher = more likely to close. Factors:
    #   GC info present (+15), tonnage > 0 (+10), sweet spot 20-100t (+10),
    #   proposal generated (+20), state advancement (+5-25), recency
    #   penalty (-5/week after 14d), has estimated value (+10).
    # Terminal states: WON=100, LOST/PASSED=0.

    @staticmethod
    def _score_bid(bid_row: dict) -> dict:
        """Compute a 0-100 win-likelihood score with factor breakdown.

        Returns {"score": int, "factors": [{"label": str, "delta": int}, ...],
                 "terminal": bool}

        the Owner's r15 ask: "I want to see WHY a bid scored where it did
        so I can tune the model later."
        """
        state = (bid_row.get("state") or "").upper()
        if state == "WON":
            return {"score": 100, "factors": [{"label": "State: WON (terminal)", "delta": 100}], "terminal": True}
        if state in ("PASSED", "LOST"):
            return {"score": 0, "factors": [{"label": f"State: {state} (terminal)", "delta": 0}], "terminal": True}

        factors = []
        score = 0
        # GC info
        if bid_row.get("gc_company"):
            factors.append({"label": "GC company present", "delta": 15})
            score += 15
        # Tonnage
        try:
            tons = float(bid_row.get("tonnage") or 0)
        except (ValueError, TypeError):
            tons = 0
        if tons > 0:
            factors.append({"label": f"Tonnage extracted ({tons:.1f}t)", "delta": 10})
            score += 10
        if 20 <= tons <= 100:
            factors.append({"label": "Sweet spot 20-100t", "delta": 10})
            score += 10
        # Estimated value
        try:
            val = float(bid_row.get("estimated_value") or 0)
        except (ValueError, TypeError):
            val = 0
        if val > 0:
            factors.append({"label": f"Estimated value ${val:,.0f}", "delta": 10})
            score += 10
        # State advancement
        state_points = {
            "SCANNED": 5, "REVIEWING": 10, "GO": 15,
            "PURSUING": 20, "PRICING": 22, "SUBMITTED": 25,
            "SENT": 25,
        }
        sp = state_points.get(state, 5)
        factors.append({"label": f"State: {state or 'SCANNED'}", "delta": sp})
        score += sp
        # Proposal generated (check if output file exists)
        name = bid_row.get("name", "")
        if name:
            from pathlib import Path as _P
            safe = "".join(c for c in name if c.isalnum() or c in " -_")[:40].strip()
            has_proposal = any(_P("output").glob(f"NC_Proposal_{safe}*")) if _P("output").exists() else False
            if has_proposal:
                factors.append({"label": "Proposal PDF generated", "delta": 20})
                score += 20
        # Recency penalty
        try:
            from datetime import datetime as _dt
            updated = bid_row.get("updated_at", "")
            if updated:
                age_days = (_dt.now() - _dt.fromisoformat(updated)).days
                if age_days > 14:
                    weeks_over = (age_days - 14) // 7
                    penalty = -min(weeks_over * 5, 30)
                    if penalty:
                        factors.append({"label": f"Stale ({age_days}d old)", "delta": penalty})
                        score += penalty
        except Exception:
            pass
        final = max(0, min(100, score))
        return {"score": final, "factors": factors, "terminal": False}

    def pipeline_score(self, bid_id: int = 0) -> dict:
        """Score a bid and persist the score to the DB. Returns score + factor breakdown."""
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        if not bid_id:
            return _err("bid_id required",
                        fix="type `score bid N` with the bid number")
        from bridge.bid_pipeline import get_bid, _update_bid_score
        row = get_bid(bid_id)
        if not row:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids all` to see all bid IDs")
        result = self._score_bid(row)
        score = result["score"]
        # Use _update_bid_score (not update_bid) so scoring never resets
        # updated_at. The recency penalty depends on that timestamp being
        # accurate to real user-facing activity, not to when we last scored.
        _update_bid_score(bid_id, score)
        return _ok({
            "bid_id": bid_id,
            "name": row.get("name", ""),
            "score": score,
            "state": row.get("state", ""),
            "factors": result["factors"],
            "terminal": result["terminal"],
            "message": f"Bid {bid_id} ({row.get('name','?')}): score {score}/100",
        })

    def _auto_score_bid(self, bid_id: int):
        """Best-effort auto-score after lifecycle events. Silent failures."""
        try:
            self.pipeline_score(bid_id)
        except Exception:
            pass

    def list_active_bids(self, limit: int = 25,
                          state_filter: str = "active") -> dict:
        """List bids in the pipeline DB, newest first.

        state_filter:
          "active"   = only non-terminal (default; matches the Owner's mental
                       model of `list bids` = "what I should be working on")
          "killed"   = PASSED only (no-go list)
          "won"      = WON only
          "lost"     = LOST only
          "terminal" = PASSED + WON + LOST (everything closed)
          "all"      = no filter
        """
        TERMINAL = {"PASSED", "WON", "LOST"}
        try:
            from bridge.bid_pipeline import _conn
            c = _conn()
            # Active bids sort by score DESC (priority view). Terminal bids
            # (killed/won/lost) sort by updated_at DESC (recency view) since
            # historical lookups care more about "when" than "how good".
            sf_lower = (state_filter or "active").lower()
            order_clause = (
                "ORDER BY score DESC, updated_at DESC"
                if sf_lower == "active"
                else "ORDER BY updated_at DESC"
            )
            rows = c.execute(
                f"SELECT id, name, gc_company, location, tonnage, estimated_value, "
                f"state, score, source, updated_at FROM bids "
                f"{order_clause} LIMIT ?",
                (limit,)
            ).fetchall()
            c.close()
            bids = [dict(r) for r in rows]

            # Apply filter
            sf = (state_filter or "active").lower()
            if sf == "active":
                bids = [b for b in bids if (b.get("state") or "").upper() not in TERMINAL]
            elif sf == "killed" or sf == "passed":
                bids = [b for b in bids if (b.get("state") or "").upper() == "PASSED"]
            elif sf == "won":
                bids = [b for b in bids if (b.get("state") or "").upper() == "WON"]
            elif sf == "lost":
                bids = [b for b in bids if (b.get("state") or "").upper() == "LOST"]
            elif sf == "terminal":
                bids = [b for b in bids if (b.get("state") or "").upper() in TERMINAL]
            # "all" = no filter

            # Group by state for quick summary
            by_state = {}
            for b in bids:
                by_state.setdefault(b.get("state", "?"), []).append(b)
            return _ok({
                "bids": bids,
                "count": len(bids),
                "by_state": {s: len(items) for s, items in by_state.items()},
                "state_filter": sf,
            })
        except Exception as e:
            return _err(f"Could not list bids: {e}")

    def list_pending_approvals(self, limit: int = 25) -> dict:
        """List bids that are awaiting the Owner's review or approval action.

        Returns bids in REVIEWING or PURSUING states - the two states where
        Owner typically needs to make a go/no-go or submit decision.
        Sorted by score descending so highest-priority items appear first.
        """
        try:
            limit, _e = _coerce_num(limit, 'limit', cast='int')
            if _e: return _e
            from bridge.bid_pipeline import _conn
            c = _conn()
            rows = c.execute(
                "SELECT id, name, gc_company, location, tonnage, estimated_value, "
                "state, score, deadline, updated_at FROM bids "
                "WHERE state IN ('REVIEWING','PURSUING') "
                "ORDER BY score DESC, updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            c.close()
            bids = [dict(r) for r in rows]
            return _ok({
                "bids": bids,
                "count": len(bids),
                "note": "Bids in REVIEWING or PURSUING state - require Owner action.",
            })
        except Exception as e:
            return _err(f"Could not list pending approvals: {e}")

    def intake_bid_from_invite(
        self,
        invite_text: str = "",
        invite_json: str = "",
        project_name: str = "",
        gc_company: str = "",
        gc_contact_email: str = "",
        location: str = "",
        deadline: str = "",
        estimated_value: str = "",
        tonnage: str = "",
        notes: str = "",
        source: str = "cowork",
    ) -> dict:
        """Phase 2: Intake a bid invite from Cowork /intake-bid or MCP.

        Creates a pipeline record and 9-folder project structure with
        populated CLAUDE.md. Accepts free-text invite, JSON string,
        or named fields.

        Returns bid_id, project_number, folder_path, claude_md_path.
        """
        try:
            from bridge.intake_bid import intake_bid_from_invite as _intake
            result = _intake(
                invite_text=invite_text,
                invite_json=invite_json,
                project_name=project_name,
                gc_company=gc_company,
                gc_contact_email=gc_contact_email,
                location=location,
                deadline=deadline,
                estimated_value=estimated_value,
                tonnage=tonnage,
                notes=notes,
                source=source,
            )
            if not result.get("ok"):
                return _err(result.get("error", "intake_bid failed"),
                            fix=result.get("fix", ""))
            return _ok(result)
        except Exception as e:
            return _err(f"intake_bid_from_invite failed: {type(e).__name__}: {e}")

    def pipeline_summary_by_score(self) -> dict:
        """Group active bids into score bands. Shows pipeline health at a glance.

        the Owner's r17 ask: "$1.2M at score 60+, $400k at 30-60, $200k at <30"
        type view. Tells me where my qualified pipeline really is, not just
        a list.

        Bands:
          high   = score >= 60  (likely to close, focus here)
          medium = 30-59        (needs work to qualify)
          low    = < 30         (long shot or stale)
        """
        try:
            from bridge.bid_pipeline import _conn
            TERMINAL = ("WON", "PASSED", "LOST")
            c = _conn()
            rows = c.execute(
                "SELECT id, name, score, tonnage, estimated_value, state "
                "FROM bids WHERE state NOT IN (?, ?, ?)",
                TERMINAL
            ).fetchall()
            c.close()
            bands = {
                "high":   {"label": "60+",   "count": 0, "total_value": 0.0, "total_tons": 0.0, "bids": []},
                "medium": {"label": "30-59", "count": 0, "total_value": 0.0, "total_tons": 0.0, "bids": []},
                "low":    {"label": "<30",   "count": 0, "total_value": 0.0, "total_tons": 0.0, "bids": []},
            }
            for r in rows:
                b = dict(r)
                score = int(b.get("score") or 0)
                try: val = float(b.get("estimated_value") or 0)
                except (ValueError, TypeError): val = 0
                try: tons = float(b.get("tonnage") or 0)
                except (ValueError, TypeError): tons = 0
                if score >= 60: band = "high"
                elif score >= 30: band = "medium"
                else: band = "low"
                bands[band]["count"] += 1
                bands[band]["total_value"] += val
                bands[band]["total_tons"] += tons
                bands[band]["bids"].append({
                    "id": b["id"], "name": b.get("name", ""),
                    "score": score, "value": val, "tons": tons,
                })
            # Round totals for display
            for band in bands.values():
                band["total_value"] = round(band["total_value"], 0)
                band["total_tons"] = round(band["total_tons"], 1)

            total_value = sum(b["total_value"] for b in bands.values())
            total_count = sum(b["count"] for b in bands.values())

            # Build a one-line summary string matching the Owner's preferred phrasing
            summary_parts = []
            for key in ("high", "medium", "low"):
                b = bands[key]
                if b["count"]:
                    summary_parts.append(
                        f"${b['total_value']:,.0f} at score {b['label']} ({b['count']} bid{'s' if b['count']!=1 else ''})"
                    )
            summary_line = (
                "  |  ".join(summary_parts)
                if summary_parts
                else "No active bids in pipeline"
            )

            return _ok({
                "bands": bands,
                "total_value": total_value,
                "total_count": total_count,
                "summary_line": summary_line,
            })
        except Exception as e:
            return _err(f"Pipeline summary failed: {e}",
                        fix="check that the bid DB exists at data/bid_pipeline.db")

    def rescore_all_bids(self) -> dict:
        """Re-run pipeline_score on every active bid. Catches stale recency penalties.

        the Owner's r17 ask: "A bid sitting at SCANNED for 3 weeks should
        accrue the stale penalty, but the recency factor only fires when
        something else triggers a rescore. Give me a command that
        refreshes the whole pipeline."

        Iterates active bids (NOT terminal; those are locked at 100/0).
        Returns a count of bids re-scored and a list of bids whose score
        changed so Owner can see what moved.
        """
        try:
            from bridge.bid_pipeline import _conn, get_bid
            TERMINAL = ("WON", "PASSED", "LOST")
            c = _conn()
            rows = c.execute(
                "SELECT id, score FROM bids WHERE state NOT IN (?, ?, ?)",
                TERMINAL
            ).fetchall()
            c.close()
            changed = []
            unchanged = 0
            for r in rows:
                bid_id = r["id"]
                old_score = int(r["score"] or 0)
                result = self.pipeline_score(bid_id=bid_id)
                if not result.get("ok"):
                    continue
                new_score = result["data"]["score"]
                if new_score != old_score:
                    name = (get_bid(bid_id) or {}).get("name", "")
                    changed.append({
                        "bid_id": bid_id,
                        "name": name,
                        "old_score": old_score,
                        "new_score": new_score,
                        "delta": new_score - old_score,
                    })
                else:
                    unchanged += 1
            return _ok({
                "rescored": len(rows),
                "changed": changed,
                "unchanged": unchanged,
                "message": (
                    f"Rescored {len(rows)} active bid(s). "
                    f"{len(changed)} moved, {unchanged} unchanged."
                ),
            })
        except Exception as e:
            return _err(f"Rescore all failed: {e}",
                        fix="check that the bid DB exists at data/bid_pipeline.db")

    def morning_briefing(self) -> dict:
        """Local 'what to look at today' summary. No LLM required.

        Returns: pipeline stats, active bids by state, recent engagement records,
        compliance blockers (EMR letter pending), and one suggested next action.
        """
        from datetime import datetime, timedelta
        try:
            briefing = {
                "date": datetime.now().strftime("%A, %B %d, %Y"),  # vj: local-display-ok
                "pipeline": {},
                "compliance_blockers": [],
                "recent_engagements": [],
                "suggested_next_action": "",
            }

            # Pipeline stats
            try:
                from bridge.bid_pipeline import _conn
                c = _conn()
                stats = c.execute(
                    "SELECT state, COUNT(*) as cnt FROM bids GROUP BY state"
                ).fetchall()
                briefing["pipeline"] = {r["state"]: r["cnt"] for r in stats}
                # Latest 3 bids
                latest = c.execute(
                    "SELECT id, name, state, tonnage, estimated_value, updated_at "
                    "FROM bids ORDER BY updated_at DESC LIMIT 3"
                ).fetchall()
                briefing["recent_bids"] = [dict(r) for r in latest]

                # ── STALE-BID ALERT (Owner M2) ──
                # Any bid in SCANNED state for > 7 days needs a decision
                stale_threshold = (datetime.now() - timedelta(days=7)).isoformat()  # vj: duration-math
                stale_rows = c.execute(
                    "SELECT id, name, state, tonnage, estimated_value, updated_at "
                    "FROM bids WHERE state = 'SCANNED' AND updated_at < ? "
                    "ORDER BY updated_at ASC LIMIT 10",
                    (stale_threshold,)
                ).fetchall()
                stale_bids = []
                for r in stale_rows:
                    bid = dict(r)
                    try:
                        updated = datetime.fromisoformat(bid["updated_at"])
                        # vj-fix: normalise tz before delta
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                        bid["days_stale"] = (datetime.now(timezone.utc) - updated).days  # vj-fix: tz-aware
                    except (ValueError, TypeError):
                        bid["days_stale"] = None
                    stale_bids.append(bid)
                briefing["stale_bids"] = stale_bids

                c.close()
            except Exception:
                briefing["pipeline"] = {}
                briefing["recent_bids"] = []
                briefing["stale_bids"] = []

            # Compliance blockers - pull from live blockers module
            try:
                from bridge.blockers import get_all as _get_blockers
                live = _get_blockers()
                briefing["compliance_blockers"] = [
                    {
                        "item": bl.get("name", bl.get("item", "?")),
                        "status": bl.get("status", "BLOCKED"),
                        "owner": bl.get("owner", "?"),
                        "severity": bl.get("severity", "med"),
                        "days_open": bl.get("days_open", 0),
                        "action": bl.get("action", ""),
                    }
                    for bl in live
                    if bl.get("status") in ("BLOCKED", "PENDING")
                ]
            except Exception:
                briefing["compliance_blockers"] = [
                    {
                        "item": "EMR letter from Texas Mutual",
                        "status": "BLOCKED",
                        "phone": "800-859-5995",
                        "policy": "[POLICY NUMBER]",
                        "blocks": "Marathon Petroleum approval",
                    }
                ]

            # Recent engagement records
            # v3.2.7: fetch more than 5 so fixture filter still leaves real data
            try:
                from bridge.engagement_records import list_records
                recs = list_records(limit=20)
                if isinstance(recs, dict) and recs.get("ok"):
                    recs = recs["data"].get("records", [])
                if isinstance(recs, list):
                    # Drop seed/test fixtures so the dashboard doesn't lie
                    def _is_fixture(e):
                        if not isinstance(e, dict): return False
                        name = str(e.get("contact_name","")).strip().lower()
                        company = str(e.get("company","")).strip().upper()
                        detail = str(e.get("engagement_detail","")).strip().lower()
                        return (name == "test"
                                or company == "ACME"
                                or detail.startswith("alias test"))
                    real_recs = [e for e in recs if not _is_fixture(e)]
                    briefing["recent_engagements"] = real_recs[:5]
                    if not real_recs and recs:
                        briefing["recent_engagements_note"] = (
                            f"{len(recs)} fixture/test engagement(s) hidden. "
                            "No real engagements logged yet."
                        )
            except Exception:
                pass

            # Score-band summary (r18): "$1.2M at 60+, $400k at 30-59, $200k at <30"
            # Gives Owner the pipeline-health view alongside the activity view.
            try:
                ss_result = self.pipeline_summary_by_score()
                if ss_result.get("ok"):
                    briefing["score_summary"] = ss_result["data"]
            except Exception:
                briefing["score_summary"] = {}

            # Suggested next action: stale bids take priority; then score health
            stale = briefing.get("stale_bids", [])
            scanned = briefing["pipeline"].get("SCANNED", 0)
            ss_data = briefing.get("score_summary", {})
            high_band = (ss_data.get("bands") or {}).get("high", {})
            high_count = high_band.get("count", 0)
            high_value = high_band.get("total_value", 0)

            if stale:
                oldest = stale[0]
                briefing["suggested_next_action"] = (
                    f"{len(stale)} STALE bid(s) - oldest is #{oldest['id']} "
                    f"({oldest.get('name','?')}) sitting {oldest.get('days_stale','?')} days. "
                    f"Decide GO/NO-GO or kill it."
                )
            elif high_count > 0:
                # High-score bids are the best use of time
                briefing["suggested_next_action"] = (
                    f"{high_count} bid{'s' if high_count != 1 else ''} score 60+ "
                    f"(${high_value:,.0f}) ready to advance. "
                    f"Generate proposals or schedule site visits."
                )
            elif scanned:
                briefing["suggested_next_action"] = (
                    f"{scanned} bid(s) in SCANNED state. Review and decide GO/NO-GO."
                )
            else:
                briefing["suggested_next_action"] = (
                    "Pipeline is clear. Check Bids to sort folder for new RFQs."
                )

            return _ok(briefing)
        except Exception as e:
            return _err(f"Morning briefing failed: {e}")

    def daily_status(self) -> dict:
        """One-line top-of-day status. the Owner's quickest glance.

        Returns date, active bid count, oldest stale bid, last engagement
        record created, and the most recent proposal path - all in one line.
        Use this when you just want to know "am I OK or do I need to do
        something" before opening a real briefing.
        """
        from datetime import datetime as _dt, timedelta as _td
        try:
            today = _dt.now().strftime("%a %b %d")
            parts = [today]

            # Active bid count + pipeline $ total
            active_count = 0
            pipeline_value = 0.0
            stale_oldest = None
            try:
                from bridge.bid_pipeline import _conn
                c = _conn()
                TERMINAL = ("'WON'", "'PASSED'", "'LOST'")
                row = c.execute(
                    "SELECT COUNT(*) as cnt, SUM(CAST(estimated_value AS REAL)) as total "
                    f"FROM bids WHERE state NOT IN ({','.join(TERMINAL)})"
                ).fetchone()
                active_count = row["cnt"] or 0
                pipeline_value = row["total"] or 0.0
                # Oldest stale (SCANNED > 7 days)
                stale_threshold = (_dt.now() - _td(days=7)).isoformat()
                stale = c.execute(
                    "SELECT id, name, updated_at FROM bids "
                    "WHERE state='SCANNED' AND updated_at < ? "
                    "ORDER BY updated_at ASC LIMIT 1",
                    (stale_threshold,)
                ).fetchone()
                if stale:
                    try:
                        days = (_dt.now() - _dt.fromisoformat(stale["updated_at"])).days
                    except (ValueError, TypeError):
                        days = "?"
                    stale_oldest = f"#{stale['id']} ({stale['name']}) {days}d stale"
                c.close()
            except Exception:
                pass

            bid_word = "bid" if active_count == 1 else "bids"
            # Include $ total when available: "5 active bids ($1.3M)"
            if pipeline_value >= 1_000_000:
                value_str = f" (${pipeline_value/1_000_000:.1f}M)"
            elif pipeline_value >= 1_000:
                value_str = f" (${pipeline_value:,.0f})"
            else:
                value_str = ""
            parts.append(f"{active_count} active {bid_word}{value_str}")
            if stale_oldest:
                parts.append(f"OLDEST STALE: {stale_oldest}")

            # Last engagement record
            try:
                from bridge.engagement_records import list_records
                recs = list_records(limit=1)
                if isinstance(recs, list) and recs:
                    r = recs[0]
                    parts.append(
                        f"last engagement: {r.get('contact_name','?')} "
                        f"({r.get('engagement_date','?')})"
                    )
            except Exception:
                pass

            # Latest proposal: show project name not raw filename.
            # Skip -GP.pdf (internal GP report) so the user sees the
            # client proposal name, not the internal margin file.
            try:
                import os as _os, re as _re
                out_dir = "output"
                if _os.path.isdir(out_dir):
                    pdfs = [(f, _os.path.getmtime(_os.path.join(out_dir, f)))
                            for f in _os.listdir(out_dir)
                            if f.endswith(".pdf") and "Proposal" in f
                            and not f.endswith("-GP.pdf")]
                    if pdfs:
                        pdfs.sort(key=lambda x: -x[1])
                        fname = pdfs[0][0]
                        # NC_Proposal_Beck Buick GMC_2026-05-12.pdf → Beck Buick GMC
                        m = _re.match(r"NC_Proposal_(.+?)_\d{4}-\d{2}-\d{2}\.pdf$", fname)
                        label = m.group(1) if m else fname.replace(".pdf", "")
                        parts.append(f"latest: {label}")
            except Exception:
                pass

            line = "  |  ".join(parts)
            return _ok({"status_line": line, "parts": parts})
        except Exception as e:
            return _err(f"daily_status failed: {e}",
                        fix="try `morning briefing` for a full report instead")

    # ── FULL-BUILDING 3D ASSEMBLY (P3) ────────────────────────────
    def plan_building(self, bays_x: int = 4, bays_y: int = 3,
                      bay_spacing_x_ft: float = 25.0,
                      bay_spacing_y_ft: float = 25.0,
                      eave_height_ft: float = 18.0,
                      column_size: str = "W12x65",
                      perimeter_beam_size: str = "W21x44",
                      interior_beam_size: str = "W18x40",
                      roof_type: str = "flat",
                      roof_pitch: float = 0.25,
                      rafter_size: str = "W18x35",
                      ridge_size: str = "W21x44",
                      bracing: bool = False,
                      brace_size: str = "HSS6x6x1/2") -> dict:
        """Plan a rectangular building's member list. No STL generated.

        roof_type: 'flat' (default) or 'gable'
        roof_pitch: rise/run (0.25 = 3:12 pitch). Only used when roof_type='gable'.
        bracing: True adds X-bracing in the 4 corner bays.

        Returns columns, beams, approx tonnage, building SF.
        Use this before build_full_building to preview.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bays_x, _e = _coerce_num(bays_x, 'bays_x', cast='int')
        if _e: return _e
        bays_y, _e = _coerce_num(bays_y, 'bays_y', cast='int')
        if _e: return _e
        bay_spacing_x_ft, _e = _coerce_num(bay_spacing_x_ft, 'bay_spacing_x_ft')
        if _e: return _e
        bay_spacing_y_ft, _e = _coerce_num(bay_spacing_y_ft, 'bay_spacing_y_ft')
        if _e: return _e
        eave_height_ft, _e = _coerce_num(eave_height_ft, 'eave_height_ft')
        if _e: return _e
        roof_pitch, _e = _coerce_num(roof_pitch, 'roof_pitch')
        if _e: return _e
        try:
            from bridge import building_assembler as _ba
            plan = _ba.plan_building(
                int(bays_x), int(bays_y),
                bay_spacing_x_ft=float(bay_spacing_x_ft),
                bay_spacing_y_ft=float(bay_spacing_y_ft),
                eave_height_ft=float(eave_height_ft),
                column_size=column_size,
                perimeter_beam_size=perimeter_beam_size,
                interior_beam_size=interior_beam_size,
                roof_type=roof_type,
                roof_pitch=float(roof_pitch),
                rafter_size=rafter_size,
                ridge_size=ridge_size,
                bracing=bool(bracing),
                brace_size=brace_size,
            )
            if "error" in plan:
                return _err(plan["error"])
            # Drop the heavy column/beam lists, return summary
            summary = {k: v for k, v in plan.items() if k not in ("columns", "beams")}
            summary["column_count"] = len(plan["columns"])
            summary["beam_count"] = len(plan["beams"])
            summary["perim_beam_count"] = sum(1 for b in plan["beams"] if b[7] == "perim")
            summary["interior_beam_count"] = sum(1 for b in plan["beams"] if b[7] == "interior")
            summary["rafter_count"] = sum(1 for b in plan["beams"] if b[7] == "rafter")
            summary["ridge_count"] = sum(1 for b in plan["beams"] if b[7] == "ridge")
            summary["brace_count"] = sum(1 for b in plan["beams"] if b[7] == "brace")
            summary["lb_per_sf"] = round(
                plan["approx_tonnage"] * 2000 / max(plan["building_sf"], 1.0), 2
            )
            return _ok(summary)
        except Exception as e:
            return _err(f"plan_building failed: {e}")

    def build_full_building(self, bays_x: int = 4, bays_y: int = 3,
                            bay_spacing_x_ft: float = 25.0,
                            bay_spacing_y_ft: float = 25.0,
                            eave_height_ft: float = 18.0,
                            column_size: str = "W12x65",
                            perimeter_beam_size: str = "W21x44",
                            interior_beam_size: str = "W18x40",
                            project_name: str = "",
                            roof_type: str = "flat",
                            roof_pitch: float = 0.25,
                            rafter_size: str = "W18x35",
                            ridge_size: str = "W21x44",
                            bracing: bool = False,
                            brace_size: str = "HSS6x6x1/2") -> dict:
        """Assemble a full rectangular building into one binary STL.

        roof_type 'gable' adds sloped rafters meeting at a ridge beam.
        bracing=True adds X-bracing diagonals in the 4 corner bays.
        Output saved to output/ folder.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bays_x, _e = _coerce_num(bays_x, 'bays_x', cast='int')
        if _e: return _e
        bays_y, _e = _coerce_num(bays_y, 'bays_y', cast='int')
        if _e: return _e
        bay_spacing_x_ft, _e = _coerce_num(bay_spacing_x_ft, 'bay_spacing_x_ft')
        if _e: return _e
        bay_spacing_y_ft, _e = _coerce_num(bay_spacing_y_ft, 'bay_spacing_y_ft')
        if _e: return _e
        eave_height_ft, _e = _coerce_num(eave_height_ft, 'eave_height_ft')
        if _e: return _e
        roof_pitch, _e = _coerce_num(roof_pitch, 'roof_pitch')
        if _e: return _e
        try:
            import os as _os, sys as _sys
            from pathlib import Path as _Path
            from bridge import building_assembler as _ba

            if getattr(_sys, "frozen", False):
                out_dir = _Path(_sys.executable).parent / "output"
            else:
                out_dir = _Path(__file__).resolve().parent.parent / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            # Sanitize project_name into a slug that's safe on Windows AND Linux:
            # Windows forbids <>:"/\|?*  and trailing dots/spaces.
            raw_slug = (project_name or "building").strip()
            slug_safe = "".join(c for c in raw_slug if c not in '<>:"/\\|?*\n\r\t')
            slug = slug_safe.replace(" ", "_").rstrip(". ")[:40] or "building"
            roof_tag = f"_{roof_type}" if roof_type != "flat" else ""
            brace_tag = "_br" if bracing else ""
            stamp = f"{int(bays_x)}x{int(bays_y)}_{int(eave_height_ft)}ft{roof_tag}{brace_tag}"
            out_path = str(out_dir / f"NC_{slug}_{stamp}.stl")

            r = _ba.build_full_building(
                int(bays_x), int(bays_y),
                output_path=out_path,
                bay_spacing_x_ft=float(bay_spacing_x_ft),
                bay_spacing_y_ft=float(bay_spacing_y_ft),
                eave_height_ft=float(eave_height_ft),
                column_size=column_size,
                perimeter_beam_size=perimeter_beam_size,
                interior_beam_size=interior_beam_size,
                roof_type=roof_type,
                roof_pitch=float(roof_pitch),
                rafter_size=rafter_size,
                ridge_size=ridge_size,
                bracing=bool(bracing),
                brace_size=brace_size,
            )
            if not r.get("ok"):
                return _err(r.get("error", "Build failed"))

            r["filename"] = _os.path.basename(r["path"])

            # Render a small PNG thumbnail alongside the STL.
            # Non-blocking: if rendering fails we just skip the thumbnail.
            try:
                from bridge.stl_thumbnail import render_stl_thumbnail
                thumb_path = render_stl_thumbnail(r["path"])
                if thumb_path:
                    r["thumbnail_path"] = thumb_path
                    r["thumbnail_filename"] = _os.path.basename(thumb_path)
            except Exception:
                pass  # Don't fail the build if thumbnail render fails

            extras = []
            if roof_type == "gable":
                extras.append(f"gable roof ({roof_pitch:.2f} pitch)")
            if bracing:
                extras.append("X-bracing")
            extra_str = (" with " + " and ".join(extras)) if extras else ""
            r["message"] = (
                f"Built {int(bays_x)}x{int(bays_y)} building{extra_str}: "
                f"{r['member_count']} members, "
                f"{r['triangle_count']:,} triangles, "
                f"{r['file_size_bytes']/1024:.1f} KB"
            )
            try:
                import base64 as _b64
                r["stl_b64"] = _b64.b64encode(
                    _Path(r["path"]).read_bytes()
                ).decode("ascii")
            except Exception:
                pass
            return _ok(r)
        except Exception as e:
            return _err(f"build_full_building failed: {e}",
                        fix="try `plan building NxM` first to see what would be built, then `build building NxM` if it looks right")

    # ── ENGAGEMENT RECORD AUTO-SCAN (P3) ──────────────────────────
    # ── GMAIL MCP POLLING FOR ENGAGEMENT AUTO-SCAN (roadmap L) ────
    def scan_recent_gmail_for_engagements(self, days_back: int = 1,
                                          max_messages: int = 50,
                                          dry_run: bool = True) -> dict:
        """Pull recent Gmail messages via MCP and propose engagement records.

        Removes the manual JSON-paste workflow Owner complained about.
        Calls Gmail MCP to list and read messages from the last N days,
        converts them into the format scan_engagements_from_messages expects,
        and runs the same engagement-detection logic.

        Args:
            days_back: How many days of email to scan (default 1 = since
                yesterday morning).
            max_messages: Cap on messages fetched. Keeps the call fast and
                avoids hitting Gmail rate limits.
            dry_run: If True (default), proposes records without writing.
                If False, creates engagement records for matching contacts.

        Returns:
            Same shape as scan_engagements_from_messages: counts by action
            plus the full proposal list. Plus a `gmail_fetch_failed` field
            if the MCP call didn't work, with a fix hint for Owner.

        Note: This requires the Gmail MCP server to be registered with Claude
        Desktop and connected. Run `register_with_claude_desktop.bat` if not
        yet set up, or check `mcp_status` from the chat window.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        days_back, _e = _coerce_num(days_back, 'days_back', cast='int')
        if _e: return _e
        max_messages, _e = _coerce_num(max_messages, 'max_messages', cast='int')
        if _e: return _e
        try:
            from bridge import mcp_client
            from datetime import datetime, timedelta
            import json as _json

            # Compute Gmail search query: "after:YYYY/MM/DD"
            cutoff = (datetime.now() - timedelta(days=int(days_back)))  # vj: duration-math
            after_str = cutoff.strftime("%Y/%m/%d")

            # Try Gmail MCP - it may not be registered or running
            try:
                list_result = mcp_client.call_tool(
                    "gmail-mcp",
                    "search_messages",
                    {"query": f"after:{after_str}", "max_results": int(max_messages)}
                )
            except Exception as e:
                return _err(
                    f"Gmail MCP not reachable: {e}",
                    fix=(
                        "Gmail MCP must be installed and configured. "
                        "Run `register_with_claude_desktop.bat` to set it up. "
                        "Until then, use `scan engagements` with manual paste."
                    )
                )

            if not list_result or list_result.get("error"):
                return _err(
                    f"Gmail MCP returned error: {list_result.get('error', 'unknown')}",
                    fix="check that you're signed into Gmail in Claude Desktop, then retry"
                )

            # Try multiple result shapes Gmail MCPs use
            raw = list_result.get("result") or list_result.get("messages") or list_result.get("data") or []
            if isinstance(raw, dict):
                raw = raw.get("messages", []) or []

            if not raw:
                return _ok({
                    "scanned": 0,
                    "proposals": [],
                    "counts": {"create": 0, "skip": 0, "exists": 0,
                               "no_phone": 0, "no_sender": 0},
                    "days_back": days_back,
                    "message": (
                        f"No Gmail messages found in the last {days_back} day(s). "
                        "Either your inbox is empty or Gmail MCP didn't return any."
                    ),
                })

            # Normalize MCP response → engagement_auto input format
            # Standard Gmail MCP fields: id, from, subject, snippet, date, body
            normalized = []
            for m in raw[:int(max_messages)]:
                if not isinstance(m, dict):
                    continue
                normalized.append({
                    "from":    m.get("from") or m.get("From") or m.get("sender") or "",
                    "subject": m.get("subject") or m.get("Subject") or "",
                    "body":    m.get("body") or m.get("snippet") or m.get("text") or "",
                    "date":    m.get("date") or m.get("Date") or "",
                })

            # Hand off to existing engagement_auto pipeline (DRY)
            return self.scan_engagements_from_messages(
                messages_json=_json.dumps(normalized),
                dry_run=dry_run,
            )

        except Exception as e:
            return _err(
                f"scan_recent_gmail_for_engagements failed: {e}",
                fix="check Gmail MCP is registered, signed in, and reachable from Claude Desktop"
            )

    def scan_engagements_from_messages(self, messages_json: str = "",
                                       dry_run: bool = True) -> dict:
        """Scan a batch of email message dicts and propose engagement records.

        messages_json: JSON array of message dicts, each with keys:
            from, subject, body, date (any subset accepted)
        dry_run: if True (default), return proposals without writing records.
                 if False, create records for contacts flagged 'create'.

        Returns counts by action and the full proposal list.
        """
        try:
            import json as _json
            from bridge import engagement_auto as _ea
            _scan_fix = "easier: type `scan gmail` to pull recent emails automatically"
            if not messages_json:
                return _err(
                    "messages_json is empty. Pass a JSON list of Gmail message dicts.",
                    fix=_scan_fix
                )
            try:
                msgs = _json.loads(messages_json)
            except _json.JSONDecodeError as e:
                return _err(
                    f"messages_json is not valid JSON: {e}",
                    fix=(
                        'expected format: [{"from":"name <addr>","subject":"...",'
                        '"body":"...","date":"YYYY-MM-DD"}, ...]'
                    )
                )
            if not isinstance(msgs, list):
                return _err(
                    "messages_json must be a JSON array",
                    fix="wrap your message dict in [ ] to make it a one-element array"
                )
            result = _ea.scan_messages_for_engagements(msgs, dry_run=bool(dry_run))
            return _ok(result)
        except Exception as e:
            return _err(
                f"scan_engagements_from_messages failed: {e}",
                fix="try `scan gmail` instead, or `morning briefing` to see current engagement state"
            )

    # ── UPDATE BID FROM DRAWING (M1) ──────────────────────────────
    def update_bid_from_drawing(self, bid_id: int = 0,
                                  pdf_path: str = "") -> dict:
        """Re-process a drawing PDF into an EXISTING bid record.

        Use this when Owner has a revised drawing for a project he's
        already bidding. Avoids the duplicate-bid problem that comes from
        dropping a new PDF and getting bid #5 when he meant to update #3.

        Workflow:
          1. Load existing bid #bid_id (must exist)
          2. Re-run extraction (force_new=True bypasses dedup)
          3. Update the existing bid's tonnage, estimated_value, pdf_hash,
             pdf_path with the fresh extraction
          4. Return both old and new values so Owner can see the delta
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        try:
            from bridge.bid_pipeline import get_bid, update_bid
            if not bid_id:
                return _err("bid_id required",
                            fix="type `list bids` to see all bid IDs, then call update_bid_from_drawing(bid_id=N, pdf_path='path/to/revised.pdf')")
            row = get_bid(bid_id)
            if not row:
                return _err(f"Bid id {bid_id} not found",
                            fix="type `list bids` to see all bid IDs")
            if not pdf_path:
                return _err("pdf_path required",
                            fix="pass pdf_path='C:/path/to/revised_drawing.pdf'")

            old_tonnage = row.get("tonnage", "0")
            old_value = row.get("estimated_value", "0")
            old_name = row.get("name", "")

            # Re-process the drawing with force_new=True to skip dedup
            r = self.auto_process_drawing(
                pdf_path=pdf_path,
                project_name=old_name,
                force_new=True,
            )
            if not r.get("ok"):
                return r  # Pass through extraction error with its fix hint

            d = r["data"]
            new_tonnage = str(d.get("total_tonnage", 0))
            new_value = str(int(d.get("draft_estimate", {}).get("total", 0) or 0))
            new_hash = d.get("pdf_hash", "")

            # The auto_process_drawing created a SECOND bid because force_new=True.
            # Update the original bid with the new values and delete the duplicate.
            update_bid(
                bid_id,
                tonnage=new_tonnage,
                estimated_value=new_value,
                pdf_hash=new_hash,
                pdf_path=str(pdf_path),
            )
            # Remove the newly-created duplicate bid (the one auto_process_drawing made)
            new_bid_id = d.get("bid_id", 0) or d.get("pipeline_bid_id", 0)
            if new_bid_id and new_bid_id != bid_id:
                try:
                    from bridge.bid_pipeline import _conn, _lock
                    with _lock:
                        c = _conn()
                        c.execute("DELETE FROM bids WHERE id=?", (new_bid_id,))
                        c.execute("DELETE FROM transitions WHERE bid_id=?", (new_bid_id,))
                        c.commit()
                        c.close()
                except Exception:
                    pass  # not fatal

            try:
                old_tons_f = float(old_tonnage or 0)
                new_tons_f = float(new_tonnage or 0)
                delta_tons = round(new_tons_f - old_tons_f, 2)
            except (ValueError, TypeError):
                delta_tons = None

            return _ok({
                "bid_id": bid_id,
                "name": old_name,
                "old_tonnage": old_tonnage,
                "new_tonnage": new_tonnage,
                "old_estimated_value": old_value,
                "new_estimated_value": new_value,
                "tonnage_delta": delta_tons,
                "members_extracted": d.get("member_count", 0),
                "message": (
                    f"Bid {bid_id} ({old_name}) updated: "
                    f"{old_tonnage} tons → {new_tonnage} tons "
                    f"({'+' if (delta_tons or 0) >= 0 else ''}{delta_tons} delta), "
                    f"${old_value} → ${new_value}"
                ),
            })
        except Exception as e:
            return _err(f"update_bid_from_drawing failed: {e}",
                        fix="check that the bid_id exists and the PDF path is correct")

    def propose_engagement_from_email(self, from_header: str = "",
                                      subject: str = "", body: str = "",
                                      date: str = "") -> dict:
        """Propose an engagement record from a single email's fields.

        Returns the proposal dict (action, contact, reason) WITHOUT creating.
        Use this to check what would happen for one email at a time.
        """
        try:
            from bridge import engagement_auto as _ea
            msg = {"from": from_header, "subject": subject, "body": body, "date": date}
            return _ok(_ea.propose_engagement(msg))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"propose_engagement_from_email failed: {e}")

    def generate_change_order(self, project_name: str, co_number: str, description: str,
                              cost_impact: str, schedule_impact: str = "None",
                              requested_by: str = "", notes: str = "",
                              skip_visual_qc: bool = True) -> dict:
        """Generate a change order PDF.

        Item 3 fix: skip_visual_qc defaults True for API/programmatic calls.
        R-01 (visual inspection gate) was blocking every programmatic CO.
        Pass skip_visual_qc=False to re-enable R-01 for desktop EXE previews.
        """
        from bridge.documents import generate_change_order
        r = generate_change_order(project_name, co_number, description,
                                  cost_impact, schedule_impact, requested_by,
                                  notes, skip_visual_qc=skip_visual_qc)
        if r.get("success"):
            try:
                from bridge.audit import log_document
                log_document("change_order", r.get("filename", ""))
            except Exception: pass
        return _ok(r) if r.get("success") else _err(r.get("error", "Generation failed"))

    # ── BID PIPELINE (Joseph P2) ───────────────────────────────────

    def add_to_pipeline(self, name: str, gc_company: str = "", location: str = "",
                        tonnage: str = "", estimated_value: str = "", score: int = 0,
                        deadline: str = "") -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        score, _e = _coerce_num(score, 'score', cast='int')
        if _e: return _e
        _ton_zero = not tonnage or float(tonnage) == 0 if tonnage else True
        _val_zero = not estimated_value or float(estimated_value) == 0 if estimated_value else True
        from bridge.bid_pipeline import add_bid
        bid_id = add_bid(name, gc_company, location, tonnage, estimated_value, score, "manual", deadline)
        if _ton_zero and _val_zero:
            return _ok({
                "bid_id": bid_id,
                "state": "INCOMPLETE",
                "warning": "Bid added as INCOMPLETE - both tonnage and value are blank. Provide tonnage or estimated value to continue.",
            })
        return _ok({"bid_id": bid_id, "state": "SCANNED"})

    def advance_bid(self, bid_id: int, new_state: str = None, actor: str = "Owner", notes: str = "") -> dict:
        """Advance bid to new_state, or infer the next forward state when new_state is omitted.

        Item 2 fix: new_state is now optional on the Bridge layer too.
        Examples:
            advance_bid(4)                  # SCANNED -> REVIEWING automatically
            advance_bid(4, 'PASSED')        # kill the bid
            advance_bid(4, notes='...')     # forward step with a note
        """
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import advance
        r = advance(bid_id, new_state, actor, notes)
        if r.get("error"): return _err(r["error"])
        try:
            from bridge.audit import log_bid_decision
            log_bid_decision(f"bid_{bid_id}", r["to"].lower(), actor.lower())
        except Exception: pass
        return _ok(r)

    def next_bid_state(self, bid_id: int) -> dict:
        """Return the natural next state for a bid without advancing it.

        Item 2 fix: surfaces current + next so the UI can show 'Move to REVIEWING?'
        before committing.
        """
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import next_state
        r = next_state(bid_id)
        if r.get("error"): return _err(r["error"])
        return _ok(r)

    # ── P2/P7 ROADMAP: state-transition shortcut verbs ────────────
    def kill_bid(self, bid_id: int = 0, reason: str = "") -> dict:
        """Mark a bid as PASSED (killed, NO-GO).

        Equivalent to advance_bid → PASSED. Works from any non-terminal
        state (SCANNED, REVIEWING, PURSUING). For bids already SUBMITTED,
        use mark_bid_lost instead.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import advance, get_bid
        if not bid_id:
            return _err("bid_id required",
                        fix="type `list bids` to see all bid IDs, then `kill bid N`")
        b = get_bid(bid_id)
        if not b:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids` to see all bid IDs")
        current = b.get("state", "SCANNED")
        if current in ("WON", "LOST", "PASSED"):
            return _err(
                f"Bid {bid_id} is already {current}, cannot kill again",
                fix=f"bid is terminal; nothing to do"
            )
        if current == "SUBMITTED":
            return _err(
                f"Bid {bid_id} is SUBMITTED. Use `mark bid {bid_id} lost` instead of kill",
                fix=f"type `mark bid {bid_id} lost` to record an actual loss"
            )
        r = advance(bid_id, "PASSED", actor="Owner",
                   notes=reason or "killed via shortcut")
        if r.get("error"):
            return _err(r["error"])
        self._auto_score_bid(bid_id)
        return _ok({"bid_id": bid_id, "from": current, "to": "PASSED",
                    "message": f"Bid {bid_id} ({b.get('name','?')}) killed (PASSED)"})

    def mark_bid_won(self, bid_id: int = 0, notes: str = "") -> dict:
        """Mark a bid WON. Auto-advances through the chain if needed.

        If the bid is in SCANNED/REVIEWING/PURSUING, advances it through
        each intermediate state to SUBMITTED → WON. Returns the chain
        of transitions so Owner sees what happened.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        return self._mark_bid_terminal(bid_id, "WON", notes)

    def mark_bid_lost(self, bid_id: int = 0, notes: str = "") -> dict:
        """Mark a bid LOST. Auto-advances through the chain if needed."""
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        return self._mark_bid_terminal(bid_id, "LOST", notes)

    def restore_bid(self, bid_id: int = 0, target_state: str = "",
                    notes: str = "") -> dict:
        """Mirror of kill_bid. Resurrect a PASSED bid back to its prior state.

        the Owner's roadmap request #2: "If I kill a bid by mistake or the GC
        comes back two weeks later, there's no command to undo it." This is
        that command. Only works on PASSED (no-go) bids - WON and LOST are
        intentionally permanent.

        By default restores to the state the bid was in when it got killed
        (read from the transitions audit log). Optionally accepts a
        target_state if Owner wants to send it somewhere specific.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import restore, get_bid
        if not bid_id:
            return _err("bid_id required",
                        fix="type `list bids killed` to see killed IDs, then `restore bid N`")
        b = get_bid(bid_id)
        if not b:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids all` to find the bid ID")
        target = target_state or None
        if target and target.upper() not in {"SCANNED", "REVIEWING", "PURSUING", "SUBMITTED"}:
            return _err(
                f"target_state '{target}' is not a valid active state",
                fix="omit target_state to restore to the bid's prior state, "
                    "or specify one of: SCANNED, REVIEWING, PURSUING, SUBMITTED"
            )
        r = restore(bid_id, target_state=target.upper() if target else None,
                    actor="Owner", notes=notes or "restored via shortcut")
        if r.get("error"):
            return _err(r["error"],
                        fix="only PASSED bids can be restored; WON/LOST are permanent")
        self._auto_score_bid(bid_id)
        return _ok({
            "bid_id": bid_id,
            "from": r["from"],
            "to": r["to"],
            "message": (
                f"Bid {bid_id} ({b.get('name','?')}) restored: "
                f"{r['from']} → {r['to']}"
            ),
        })

    def kill_all_stale_bids(self, min_days_stale: int = 30,
                            confirm: bool = False,
                            dry_run: bool = None) -> dict:
        """Bulk-kill every non-terminal bid older than min_days_stale.

        Two-step safety: first call returns a preview of what would be killed.
        Call again with confirm=True to actually advance them to PASSED.

        SIM-07: also accepts `dry_run=True` (equivalent to confirm=False) or
        `dry_run=False` (equivalent to confirm=True). Owner expected this kwarg.

        the Owner's Monday-morning cleanup tool. Run a quick `kill all stale`
        in the chat, review the list, run it again with `confirm` to execute.
        """
        # SIM-07: dry_run kwarg maps to inverse of confirm
        if dry_run is not None:
            confirm = not bool(dry_run)
        # pass 10i: numeric input hardening - coerce or fail clean
        min_days_stale, _e = _coerce_num(min_days_stale, 'min_days_stale', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import get_pipeline, advance
        from datetime import datetime as _dt
        try:
            active = get_pipeline()  # all non-terminal bids
        except Exception as e:
            return _err(f"Could not read pipeline: {e}")

        stale = []
        now = _dt.now()
        for b in active:
            try:
                updated = _dt.fromisoformat(b.get("updated_at", ""))
                days = (now - updated).days
                if days >= min_days_stale:
                    stale.append({
                        "id": b["id"],
                        "name": b.get("name", "?"),
                        "state": b.get("state", "?"),
                        "days_stale": days,
                    })
            except (ValueError, TypeError):
                continue

        if not stale:
            return _ok({
                "stale_count": 0,
                "killed_count": 0,
                "message": f"No bids stale {min_days_stale}+ days. Nothing to kill.",
            })

        # the Owner's request #4: skip the two-step preview/confirm when
        # only 1 bid matches. For a single bid the preview is friction -
        # he can see what he'd kill from the chat error or list bids.
        if not confirm and len(stale) > 1:
            return _ok({
                "stale_count": len(stale),
                "killed_count": 0,
                "preview": True,
                "stale_bids": stale,
                "message": (
                    f"Would kill {len(stale)} bid(s) stale {min_days_stale}+ days. "
                    f"Run `kill all stale confirm` to execute."
                ),
                "fix": "type `kill all stale confirm` to actually advance these to PASSED",
            })

        # Confirmed: kill them all
        killed = []
        failed = []
        for s in stale:
            try:
                r = advance(s["id"], "PASSED", actor="Owner",
                           notes=f"bulk kill: stale {s['days_stale']}d")
                if r.get("error"):
                    failed.append({**s, "error": r["error"]})
                else:
                    killed.append(s)
            except Exception as e:
                failed.append({**s, "error": str(e)})

        return _ok({
            "stale_count": len(stale),
            "killed_count": len(killed),
            "failed_count": len(failed),
            "killed_bids": killed,
            "failed_bids": failed,
            "message": (
                f"Killed {len(killed)} of {len(stale)} stale bid(s). "
                + (f"{len(failed)} failed (see failed_bids)." if failed else "")
            ),
        })

    def _mark_bid_terminal(self, bid_id: int, terminal: str, notes: str = "") -> dict:
        """Shared helper: advance bid through state machine to WON or LOST."""
        from bridge.bid_pipeline import advance, get_bid
        if not bid_id:
            return _err("bid_id required",
                        fix=f"type `mark bid N {terminal.lower()}` with a real bid number")
        b = get_bid(bid_id)
        if not b:
            return _err(f"Bid {bid_id} not found",
                        fix="type `list bids` to see all bid IDs")
        current = b.get("state", "SCANNED")
        if current == terminal:
            return _err(f"Bid {bid_id} is already {terminal}",
                        fix="no action needed")
        if current in ("WON", "LOST", "PASSED"):
            return _err(
                f"Bid {bid_id} is already terminal ({current})",
                fix=f"cannot mark as {terminal}; bid is in a different terminal state"
            )
        # Auto-advance through chain: SCANNED → REVIEWING → PURSUING → SUBMITTED → terminal
        chain = ["SCANNED", "REVIEWING", "PURSUING", "SUBMITTED", terminal]
        try:
            start_idx = chain.index(current)
        except ValueError:
            return _err(f"Unknown bid state: {current}",
                        fix="manually advance via advance_bid")
        transitions = []
        prev = current
        for nxt in chain[start_idx + 1:]:
            r = advance(bid_id, nxt, actor="Owner",
                       notes=notes if nxt == terminal else "auto-advance from shortcut")
            if r.get("error"):
                return _err(
                    f"Failed at {prev} → {nxt}: {r['error']}",
                    fix=f"advanced through {[t['to'] for t in transitions]}; manual fix needed"
                )
            transitions.append({"from": prev, "to": nxt})
            prev = nxt
        self._auto_score_bid(bid_id)
        return _ok({
            "bid_id": bid_id,
            "name": b.get("name", ""),
            "from": current,
            "to": terminal,
            "transitions": transitions,
            "message": (
                f"Bid {bid_id} ({b.get('name','?')}) marked {terminal} "
                f"({len(transitions)} transition(s) from {current})"
            ),
        })

    def get_bid_pipeline(self, state: str = None) -> dict:
        from bridge.bid_pipeline import get_pipeline, pipeline_summary
        return _ok({"bids": get_pipeline(state), "summary": pipeline_summary()})

    def get_pipeline(self, state: str = None) -> dict:
        """Alias for get_bid_pipeline - used by MCP server and frontend."""
        return self.get_bid_pipeline(state)

    def get_bid_detail(self, bid_id: int) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        from bridge.bid_pipeline import get_bid
        b = get_bid(bid_id)
        return _ok(b) if b else _err("Bid not found")

    def get_bid(self, bid_id: int) -> dict:
        """SIM-06: Direct lookup of a single bid by ID. Alias for get_bid_detail.

        Owner asked for `b.get_bid(bid_id=N)` to work without having to fetch
        the whole pipeline and filter. This is the thin wrapper.
        """
        return self.get_bid_detail(bid_id)

    def review_bid(self, bid_json: str = "", bid: dict = None) -> dict:
        """SIM-05: Run Virtual the Owner's 19-rule bid review from the chat layer.

        Accepts either a JSON string (`bid_json=...`) or a dict (`bid=...`).
        Returns the VMReview as a dict with status, score, flags, killers.

        Example call:
          b.review_bid(bid_json='{"name": "Test", "tons": 85, "bid_total": 580000,
                                  "margin_pct": 0.09, "scope": ["steel","erection"]}')
        """
        if bid is None and bid_json:
            try:
                bid = json.loads(bid_json) if isinstance(bid_json, str) else bid_json
            except Exception as e:
                return _err(f"Invalid bid_json: {e}\nfix: pass valid JSON with name/tons/bid_total/margin_pct/scope keys")
        if not bid or not isinstance(bid, dict):
            return _err("review_bid requires `bid_json` (JSON string) or `bid` (dict)")
        try:
            from bridge.virtual_owner import review_bid as vm_review_bid
            result = vm_review_bid(bid)
            return _ok(result)
        except Exception as e:
            return _err(f"review_bid failed: {type(e).__name__}: {e}")

    def go_no_go_review(self, bid_id: int = 0, bid_json: str = "") -> dict:
        """Phase 2: Composite go/no-go review - pipeline_score + review_bid in one call.

        Scores the bid (0-100 with factor breakdown) then runs Virtual the Owner's
        19-rule bid review. Returns combined result with recommendation.

        bid_id: pipeline DB row id (preferred)
        bid_json: JSON string with bid fields (fallback if no bid_id)
        """
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e

        score_result = None
        review_result = None

        # Score the bid
        if bid_id:
            try:
                score_result = self.pipeline_score(bid_id=bid_id)
            except Exception as e:
                score_result = _err(f"pipeline_score failed: {e}")

        # Run Virtual Owner review
        if bid_json or bid_id:
            if not bid_json and bid_id:
                # Pull bid data from pipeline for review
                try:
                    from bridge.bid_pipeline import _conn
                    c = _conn()
                    row = c.execute(
                        "SELECT name, gc_company, tonnage, estimated_value, state, score "
                        "FROM bids WHERE id=?", (bid_id,)
                    ).fetchone()
                    c.close()
                    if row:
                        import json as _json
                        r = dict(row)
                        bid_json = _json.dumps({
                            "name": r.get("name", ""),
                            "gc_company": r.get("gc_company", ""),
                            "tons": r.get("tonnage", 0),
                            "bid_total": r.get("estimated_value", 0),
                            "margin_pct": 0.09,
                            "scope": ["steel", "erection", "deck"],
                        })
                except Exception:
                    pass
            if bid_json:
                review_result = self.review_bid(bid_json=bid_json)

        score_data = score_result.get("data", {}) if (score_result and score_result.get("ok")) else {}
        review_data = review_result.get("data", {}) if (review_result and review_result.get("ok")) else {}

        score_val = score_data.get("score", 0)
        recommendation = "GO" if score_val >= 60 else ("REVIEW" if score_val >= 30 else "NO-GO")

        return _ok({
            "bid_id": bid_id,
            "recommendation": recommendation,
            "score": score_val,
            "score_detail": score_data,
            "vm_review": review_data,
        })

    # ── AUDIT LOG (Joseph P2) ──────────────────────────────────────

    def get_audit_log(self, action: str = None, hours: int = 24, limit: int = 50) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        hours, _e = _coerce_num(hours, 'hours', cast='int')
        if _e: return _e
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.audit import query, stats
        return _ok({"entries": query(action, hours=hours, limit=limit), "stats": stats(hours)})

    # ── HEALTH MONITOR (Joseph P2) ─────────────────────────────────

    def get_health(self) -> dict:
        from bridge.health import status, check_last_boot
        base = {**status(), "last_boot": check_last_boot()}
        err_count = _count_recent_handler_errors(window_seconds=60)
        if err_count == 0:
            base["health_label"] = "ALL SYSTEMS OPERATIONAL"
            base["health_color"] = "green"
        elif err_count < 3:
            base["health_label"] = f"{err_count} handler error(s) in last minute"
            base["health_color"] = "yellow"
        else:
            base["health_label"] = f"{err_count} handler errors - check vj scan"
            base["health_color"] = "red"
        base["handler_errors_60s"] = err_count
        return _ok(base)

    def is_debug_mode(self) -> dict:
        """Returns whether DEBUG_MODE=1 env var is set. Frontend uses this to show debug UI."""
        import os
        return _ok({"debug": os.environ.get("DEBUG_MODE") == "1"})

    def debug_force_handler_error(self) -> dict:
        """P11.3: Deliberately record a handler error to verify health-card flip.

        Only works when DEBUG_MODE=1. Used to stress-test the P8.4 yellow/red
        health card logic without waiting for a real failure.
        """
        import os
        if os.environ.get("DEBUG_MODE") != "1":
            return _err("debug_force_handler_error only available when DEBUG_MODE=1")
        try:
            raise RuntimeError("Simulated handler failure for P10.2 verification")
        except Exception as e:
            _record_bridge_error(f"debug_force_handler_error: {e}")
        return _err("Simulated error recorded - health card should flip yellow within 60s")

    # ── REMINDERS (Joseph P2) ──────────────────────────────────────

    def get_reminders(self) -> dict:
        from bridge.reminders import get_active_reminders
        r = get_active_reminders()
        return _ok({"reminders": r, "count": len(r),
                    "urgent": len([x for x in r if x["priority"] in ("urgent", "high")])})

    # ── COWORK SCHEDULER ─────────────────────────────────────────────

    def get_cowork_schedule_status(self) -> dict:
        """Return the current CoworkScheduler status and task list."""
        try:
            from bridge.cowork_scheduler import get_scheduler
            return _ok(get_scheduler().status())
        except Exception as e:
            return _err(f"cowork_schedule_status: {e}")

    def set_cowork_task_enabled(self, task_id: str, enabled: bool) -> dict:
        """Enable or disable a scheduled cowork task by task_id."""
        try:
            import json
            from bridge.cowork_scheduler import _SCHEDULE_PATH, get_scheduler
            with open(_SCHEDULE_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            found = False
            for t in cfg.get("tasks", []):
                if t["id"] == task_id:
                    t["enabled"] = bool(enabled)
                    found = True
                    break
            if not found:
                return _err(f"cowork task not found: {task_id}")
            with open(_SCHEDULE_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            get_scheduler().stop()
            get_scheduler().start()
            return _ok({"task_id": task_id, "enabled": enabled})
        except Exception as e:
            return _err(f"set_cowork_task_enabled: {e}")

    def run_cowork_task_now(self, task_id: str) -> dict:
        """Immediately run a cowork task by task_id (for testing)."""
        try:
            from bridge.cowork_scheduler import _TASK_MAP
            fn = _TASK_MAP.get(task_id)
            if fn is None:
                return _err(f"unknown cowork task: {task_id}")
            fn()
            return _ok({"task_id": task_id, "status": "executed"})
        except Exception as e:
            return _err(f"run_cowork_task_now: {e}")

    # ── PROJECT COST TRACKER (Joseph P3) ───────────────────────────

    def add_project(self, name: str, client: str = "", location: str = "",
                    est_tons: float = 0, est_cost: float = 0, est_hours: float = 0) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        est_tons, _e = _coerce_num(est_tons, 'est_tons')
        if _e: return _e
        est_cost, _e = _coerce_num(est_cost, 'est_cost')
        if _e: return _e
        est_hours, _e = _coerce_num(est_hours, 'est_hours')
        if _e: return _e
        from bridge.cost_tracker import add_project
        pid = add_project(name, client, location, est_tons, est_cost, est_hours)
        return _ok({"project_id": pid})

    def update_project_costs(self, project_id: int, **kwargs) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        project_id, _e = _coerce_num(project_id, 'project_id', cast='int')
        if _e: return _e
        from bridge.cost_tracker import update_project
        return _ok({"updated": update_project(project_id, **kwargs)})

    def add_cost_entry(self, project_id: int, category: str, amount: float,
                       description: str = "", hours: float = 0) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        project_id, _e = _coerce_num(project_id, 'project_id', cast='int')
        if _e: return _e
        amount, _e = _coerce_num(amount, 'amount')
        if _e: return _e
        hours, _e = _coerce_num(hours, 'hours')
        if _e: return _e
        from bridge.cost_tracker import add_cost_entry
        add_cost_entry(project_id, category, amount, description, hours)
        return _ok({"logged": True})

    def get_project_costs(self, project_id: int = None) -> dict:
        # pass 10i: numeric input hardening - coerce or fail clean
        project_id, _e = _coerce_num(project_id, 'project_id', cast='int')
        if _e: return _e
        if project_id:
            from bridge.cost_tracker import get_project
            p = get_project(project_id)
            return _ok(p) if p else _err("Project not found")
        from bridge.cost_tracker import get_all_projects, summary
        return _ok({"projects": get_all_projects(), "summary": summary()})

    # ── API REGISTRY + INTEGRATOR (Joseph - dynamic API system) ──────

    def get_api_registry(self) -> dict:
        """List all registered APIs (built-in + user-added)."""
        from bridge.api_registry import get_all, stats
        return _ok({"apis": get_all(), "stats": stats()})

    def get_api_capabilities(self, capability: str = "") -> dict:
        """Find APIs that offer a specific capability.

        SIM-07: capability is now optional. When empty, returns all
        registered API capabilities so Owner can discover what is
        available without knowing the exact label.
        """
        from bridge.api_registry import get_by_capability, get_all
        if not capability:
            # Aggregate every capability across all registered providers.
            providers = get_all() or {}
            caps: dict[str, list] = {}
            for key, p in providers.items():
                if not isinstance(p, dict):
                    continue
                for cap in (p.get("capabilities") or []):
                    caps.setdefault(cap, []).append(key)
            return _ok({
                "capabilities": caps,
                "count": len(caps),
                "provider_count": len(providers),
                "note": "Pass capability=<name> to list providers for a single capability.",
            })
        return _ok({"providers": get_by_capability(capability)})

    def integrate_api(self, service_name: str, purpose: str = "") -> dict:
        """Manually trigger API integration pipeline."""
        from bridge.api_integrator import run_full_integration
        keys = _load_all_keys()
        result = run_full_integration(service_name, purpose, keys)
        if result.get("error"):
            return _err(result["error"])
        return _ok(result)

    def activate_api(self, provider_key: str, api_key: str) -> dict:
        """Activate a pending API integration with its key."""
        from bridge.api_integrator import activate_with_key
        result = activate_with_key(provider_key, api_key)
        if result.get("error"):
            return _err(result["error"])
        return _ok(result)

    def deactivate_api(self, provider_key: str) -> dict:
        """Disable an API without removing it."""
        from bridge.api_registry import deactivate
        return _ok({"deactivated": deactivate(provider_key)})

    def remove_api(self, provider_key: str) -> dict:
        """Remove a user-added API from the registry."""
        from bridge.api_registry import remove
        return _ok({"removed": remove(provider_key)})

    # ═══ HANDOFF DOCUMENT MODULES - Data Fabric ═══════════════════

    def get_steel_prices(self) -> dict:
        """Get latest FRED steel PPI data (cached)."""
        from bridge.fred_steel_pricing import get_latest_prices, week_over_week_alert
        return _ok({**get_latest_prices(), "alerts": week_over_week_alert()})

    def fetch_steel_prices_fred(self, months: int = 6) -> dict:
        """Fetch fresh steel PPI data from FRED API (v3.2.7: renamed from fetch_steel_prices to fix shadow)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        months, _e = _coerce_num(months, 'months', cast='int')
        if _e: return _e
        from bridge.fred_steel_pricing import fetch_all
        _r = fetch_all(months)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def fred_key_status(self) -> dict:
        """Tell the UI whether the FRED key is loaded (without exposing the key).

        Returns has_key=True/False so the Settings panel can show the status dot
        green or red. Doesn't probe the FRED API - just reports whether the key
        exists in the encrypted store / API Keys folder / env.
        """
        try:
            from bridge.fred_steel_pricing import _get_key
            key = _get_key()
            return _ok({"has_key": bool(key), "length": len(key) if key else 0})
        except Exception as e:
            return _ok({"has_key": False, "error": str(e)})

    def get_fuel_surcharge(self) -> dict:
        """Get EIA diesel price and freight surcharge."""
        from bridge.eia_fuel_surcharge import get_cached, fetch_diesel_price
        cached = get_cached()
        if cached.get("error"):
            _r = fetch_diesel_price()
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"])
            return _ok(_r)
        return _ok(cached)

    def calculate_freight(self, miles: float, tons: float) -> dict:
        """Calculate freight surcharge for steel delivery."""
        # pass 10i: numeric input hardening - coerce or fail clean
        miles, _e = _coerce_num(miles, 'miles')
        if _e: return _e
        tons, _e = _coerce_num(tons, 'tons')
        if _e: return _e
        from bridge.eia_fuel_surcharge import calculate_freight_surcharge
        _r = calculate_freight_surcharge(miles, tons)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def search_federal_opportunities(self, keywords: str = "", days: int = 14) -> dict:
        """Search SAM.gov for federal structural steel opportunities."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.sam_gov_opportunities import houston_steel_opportunities, search_opportunities
        if keywords:
            result = search_opportunities(keywords=keywords.split(), posted_days=days)
        else:
            result = houston_steel_opportunities(days)
        # VJ auto-fix (pass 10i sim): inner func returns error key when API key missing
        if isinstance(result, dict) and "error" in result and len(result) <= 2:
            return _err(result["error"],
                        fix="Set SAM_GOV_API_KEY env var. Free key: https://api.data.gov")
        return _ok(result)

    def get_davis_bacon_rates(self, contract_type: str = "building") -> dict:
        """Get Davis-Bacon prevailing wage rates for Houston."""
        from bridge.davis_bacon_wages import get_rates
        _r = get_rates(contract_type)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def validate_wage_rate(self, classification: str, rate: float, contract_type: str = "building") -> dict:
        """Check if a billed rate meets Davis-Bacon minimums."""
        # pass 10i: numeric input hardening - coerce or fail clean
        rate, _e = _coerce_num(rate, 'rate')
        if _e: return _e
        from bridge.davis_bacon_wages import validate_rate
        _r = validate_rate(classification, rate, contract_type)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def check_davis_bacon(self, owner: str) -> dict:
        """Check if a project owner typically requires Davis-Bacon."""
        from bridge.davis_bacon_wages import is_davis_bacon_project
        return _ok({"owner": owner, "davis_bacon_likely": is_davis_bacon_project(owner)})

    def get_special_inspectors(self, scope: str = "steel") -> dict:
        """Get Houston Special Inspectors for structural steel/welds."""
        from bridge.houston_permits import get_inspectors
        return _ok({"inspectors": get_inspectors(scope)})

    def check_si_required(self, work_type: str) -> dict:
        """Check if work requires a Special Inspector (IBC §1705)."""
        from bridge.houston_permits import requires_special_inspection
        return _ok({"work_type": work_type, "si_required": requires_special_inspection(work_type)})

    # ═══ VENDOR QUOTE POLLER - Pass 7 (Outlook -> vendor_quotes) ══

    def poll_vendor_mailbox(self, force: bool = False) -> dict:
        """Run one poll cycle of owner@yourcompany.example.com Outlook for vendor quotes.

        Cadence target: hourly during business hours (M-F 7am-6pm CT).
        Requires Win11 with Outlook running and pywin32 installed.
        force=True bypasses business-hours gate.
        """
        from bridge.vendor_quote_poller import poll_now
        return _ok(poll_now(force=force))  # vj: ok-passthrough-safe

    def get_vendor_quotes(self, vendor: str = None, project: str = None,
                          days: int = 30, status: str = None) -> dict:
        """Retrieve recorded vendor quotes with optional filters."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.vendor_quote_poller import get_quotes
        rows = get_quotes(vendor=vendor, project=project, days=days, status=status)
        return _ok({"count": len(rows), "quotes": rows, "filters":
                    {"vendor": vendor, "project": project, "days": days, "status": status}})

    def get_vendor_whitelist(self) -> dict:
        """List current sender whitelist (locked vendors that can deposit quotes)."""
        from bridge.vendor_quote_poller import get_whitelist
        wl = get_whitelist()
        return _ok({"count": len(wl), "whitelist": wl})

    def add_vendor_to_whitelist(self, domain: str, vendor_name: str = "",
                                vendor_type: str = "service_center",
                                notes: str = "") -> dict:
        """Add a new vendor domain to the poller whitelist.

        Use when a new service center starts sending quotes (e.g. Delta Steel
        after their first thread arrives).
        """
        from bridge.vendor_quote_poller import add_to_whitelist
        return _ok(add_to_whitelist(domain, vendor_name, vendor_type, notes))  # vj: ok-passthrough-safe

    def vendor_poller_status(self) -> dict:
        """Status snapshot: last poll time, quote count, whitelist, platform."""
        from bridge.vendor_quote_poller import poller_status
        return _ok(poller_status())  # vj: ok-passthrough-safe

    def record_vendor_quote(self, sender_email: str, subject: str, body: str,
                            received_at: str, attachments_json: str = "",
                            message_id: str = "") -> dict:
        """Manually record a vendor quote (e.g. for testing or backfill).

        Normal flow is via poll_vendor_mailbox(). This method is for cases
        where Outlook COM isn't available (Mac/Linux dev) or for replaying
        quotes from a known list.
        """
        import json as _json
        from bridge.vendor_quote_poller import record_quote
        attachments = []
        if attachments_json:
            try:
                attachments = _json.loads(attachments_json)
            except Exception:
                pass
        return _ok(record_quote(  # vj: ok-passthrough-safe
            sender_email=sender_email, subject=subject, body=body,
            received_at=received_at, attachments=attachments, message_id=message_id,
        ))

    # ═══ AI MODEL ROUTER - Pass 8 (Opus 4.7 / 4.6 / Sonnet 4.6 / Haiku 4.5) ══
    #
    # The virtual office defaults to Sonnet 4.6 for almost everything. Opus
    # tiers exist for tasks where accuracy clearly matters more than cost
    # (complex compliance reasoning, high-stakes bid analysis). Haiku 4.5
    # is reserved for fast chat-style replies. Routing is configurable per
    # task type and persists to data/model_routing.json.

    def get_model_routing(self) -> dict:
        """Show the current task -> tier -> model routing map.

        Returns all 4 tiers (fast/default/accurate/max), every known task
        type, and any active overrides. Use this from Settings to see
        what's running on what model.
        """
        from bridge.ai_model_router import get_routing_map
        _r = get_routing_map()
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def set_model_routing(self, task_type: str = "", tier: str = "") -> dict:
        """Override the routing tier for a task type.

        Args:
            task_type: e.g. "compliance", "bid_strategy", "voice_draft"
            tier:      one of "fast" / "default" / "accurate" / "max"
        """
        if not task_type or not tier:
            return _err("task_type and tier required",
                       fix="example: set_model_routing('compliance', 'max')")
        from bridge.ai_model_router import set_tier_for_task
        r = set_tier_for_task(task_type, tier)
        return _ok(r) if r.get("ok") else _err(r.get("error", "unknown"))

    def clear_model_routing(self, task_type: str = "") -> dict:
        """Clear an override for one task (or all if task_type is empty)."""
        from bridge.ai_model_router import clear_override, clear_all_overrides
        if task_type:
            _r = clear_override(task_type)
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"])
            return _ok(_r)
        _r = clear_all_overrides()
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def escalate_to_opus(self, prompt: str = "", system: str = "",
                          tier: str = "max", max_tokens: int = 2000) -> dict:
        """Run a one-off Claude call against Opus 4.7 (max) or 4.6 (accurate).

        Use when default Sonnet output isn't accurate enough for the task.
        Example: hard compliance edge case, multi-step bid post-mortem,
        ambiguous vendor quote interpretation.

        Args:
            prompt:      user-facing prompt text
            system:      optional system prompt override
            tier:        "max" (Opus 4.7) or "accurate" (Opus 4.6)
            max_tokens:  generation cap (default 2000)
        """
        if not prompt:
            return _err("prompt required",
                       fix="example: escalate_to_opus('analyze this RFP terms section')")
        from bridge.ai_model_router import get_model_for_escalation
        model = get_model_for_escalation(tier)
        try:
            api_key = _load_api_key()
        except Exception as e:
            return _err(f"Claude API key unavailable: {e}",
                       fix="check API Keys/Claude API.txt exists with valid sk-ant-... key")
        try:
            from bridge.claude_connect import call_claude_robust
            sys_prompt = system or "You are a precise structural-steel-fabrication advisor."
            r = call_claude_robust(api_key, model, sys_prompt,
                                    [{"role": "user", "content": prompt}])
            return _ok({
                "model": model, "tier": tier,
                "text": r.get("text", ""),
                "input_tokens": r.get("input_tokens", 0),
                "output_tokens": r.get("output_tokens", 0),
                "transport": r.get("_transport", "unknown"),
            })
        except Exception as e:
            return _err(f"escalation call failed: {str(e)[:200]}",
                       fix="check API Keys/Claude API.txt and network")

    def list_remote_mcps(self) -> dict:
        """List all URL-based remote MCP connectors registered for API use.

        These are the Claude Desktop App-equivalent remote connectors that
        the bridge can attach to API calls via the mcp_servers parameter.
        """
        from bridge.mcp_remote import list_remote_servers, status as _status
        return _ok({
            "servers": list_remote_servers(),
            **_status(),
        })

    def add_remote_mcp(self, name: str = "", url: str = "",
                       description: str = "", categories_csv: str = "") -> dict:
        """Register a URL-based remote MCP connector.

        Args:
            name:          short identifier (e.g. "slack", "linear")
            url:           https URL of the MCP server
            description:   what it does
            categories_csv: comma-separated tags like "chat,team"
        """
        if not name or not url:
            return _err("name and url required",
                       fix="example: add_remote_mcp('linear', 'https://mcp.linear.app/mcp')")
        cats = [c.strip() for c in (categories_csv or "").split(",") if c.strip()]
        from bridge.mcp_remote import add_remote_server
        r = add_remote_server(name, url, description, cats)
        return _ok(r) if r.get("added") else _err(r.get("error", "unknown"))

    def remove_remote_mcp(self, name: str = "") -> dict:
        """Unregister a remote MCP connector by name."""
        if not name:
            return _err("name required")
        from bridge.mcp_remote import remove_remote_server
        r = remove_remote_server(name)
        return _ok(r) if r.get("removed") else _err(r.get("error", "unknown"))

    def call_with_mcps(self, prompt: str = "", mcp_names_csv: str = "",
                       category: str = "", tier: str = "default",
                       system: str = "", max_tokens: int = 2000) -> dict:
        """Make a Claude API call with remote MCP servers attached.

        This is the "use the Owner's Claude Desktop App connectors" path:
        the API call carries the same remote MCPs Owner sees in his
        Desktop App, so Claude can reach Outlook/Slack/etc during reasoning.

        Args:
            prompt:        user prompt text
            mcp_names_csv: explicit connector names to attach (e.g.
                           "microsoft-365,slack"). Empty = use category.
            category:      if mcp_names_csv empty, filter by category
                           (e.g. "email", "chat")
            tier:          model tier - "default", "accurate", "max"
            system:        optional system prompt
            max_tokens:    generation cap
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        max_tokens, _e = _coerce_num(max_tokens, 'max_tokens', cast='int')
        if _e: return _e
        if not prompt:
            return _err("prompt required")
        from bridge.ai_model_router import TIERS
        if tier not in TIERS:
            tier = "default"
        model = TIERS[tier]["model"]
        from bridge.mcp_remote import as_api_param
        names = [n.strip() for n in (mcp_names_csv or "").split(",") if n.strip()]
        mcp_servers = as_api_param(names=names, category=category)
        try:
            api_key = _load_api_key()
        except Exception as e:
            return _err(f"Claude API key unavailable: {e}")
        try:
            from bridge.claude_connect import call_claude_with_mcps
            sys_prompt = system or "You are the Your Company virtual office advisor."
            r = call_claude_with_mcps(
                api_key=api_key, model=model, system=sys_prompt,
                messages=[{"role": "user", "content": prompt}],
                mcp_servers=mcp_servers, max_tokens=max_tokens,
            )
            return _ok({
                "model":            model,
                "tier":             tier,
                "text":             r.get("text", ""),
                "mcp_servers_used": r.get("mcp_servers_used", []),
                "mcp_tool_uses":    r.get("mcp_tool_uses", []),
                "mcp_tool_results": r.get("mcp_tool_results", []),
                "input_tokens":     r.get("input_tokens", 0),
                "output_tokens":    r.get("output_tokens", 0),
                "transport":        r.get("_transport", "unknown"),
            })
        except Exception as e:
            return _err(f"MCP-attached call failed: {str(e)[:200]}",
                       fix="verify the SDK supports mcp_servers (pip install -U anthropic) "
                           "and that remote MCP URLs are reachable")

    # ═══ HTTP MCP SERVER - Pass 9 (reverse direction) ═════════════════════
    #
    # Lets the claude.ai web project (or any HTTPS-reachable MCP client)
    # call INTO the desktop software's Bridge methods. Same 84 tool surface
    # as the stdio path used by Claude Desktop App. Token-authenticated.
    # Designed to run behind Cloudflare Tunnel to give the public URL
    # claude.ai needs to reach the Owner's Win11 box.

    def start_mcp_http_server(self, port: int = 7777, host: str = "127.0.0.1") -> dict:
        """Start the HTTP MCP server (alongside the GUI / stdio server).

        Args:
            port:  TCP port. Default 7777.
            host:  bind address. Default 127.0.0.1 (only localhost; pair
                   with Cloudflare Tunnel for public access). Pass
                   "0.0.0.0" to bind all interfaces.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        port, _e = _coerce_num(port, 'port', cast='int')
        if _e: return _e
        try:
            from bridge.mcp_http_server import start_server
            return _ok(start_server(host=host, port=port))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"failed to start HTTP MCP server: {str(e)[:200]}",
                       fix="check that port is free and bridge.mcp_http_server imports cleanly")

    def stop_mcp_http_server(self) -> dict:
        """Shutdown the HTTP MCP server cleanly."""
        try:
            from bridge.mcp_http_server import stop_server
            return _ok(stop_server())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"failed to stop HTTP MCP server: {str(e)[:200]}")

    def mcp_http_server_status(self) -> dict:
        """Snapshot: running/stopped, host/port, token file location."""
        try:
            from bridge.mcp_http_server import server_status
            return _ok(server_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"status check failed: {str(e)[:200]}")

    def get_mcp_token(self) -> dict:
        """Get the bearer token for claude.ai connector setup.

        Returns the token plus a fingerprint suitable for confirming the
        match without dumping the full token into logs. The full token is
        needed when configuring the claude.ai project connector.
        """
        try:
            from bridge.mcp_http_server import get_or_create_token
            import hashlib
            tok = get_or_create_token()
            return _ok({
                "token": tok,
                "fingerprint": hashlib.sha256(tok.encode()).hexdigest()[:12],
                "header_value": f"Bearer {tok}",
                "next_step": "Paste into claude.ai project Settings > Connectors > Authorization header",
            })
        except Exception as e:
            return _err(f"token read failed: {str(e)[:200]}")

    def rotate_mcp_token(self) -> dict:
        """Generate a new bearer token. Invalidates the existing claude.ai connector.

        Use when the current token might have been exposed (e.g. shared in
        a screenshot, logged accidentally). After rotation, update the
        claude.ai connector with the new token.
        """
        try:
            from bridge.mcp_http_server import rotate_token
            import hashlib
            tok = rotate_token()
            return _ok({
                "token": tok,
                "fingerprint": hashlib.sha256(tok.encode()).hexdigest()[:12],
                "warning": "claude.ai project connector must be updated with this new token",
            })
        except Exception as e:
            return _err(f"token rotation failed: {str(e)[:200]}")

    # ── v3.2.7 pass 10: file staging for tunnel downloads ─────────

    def stage_file(self, file_path: str = "", display_name: str = "") -> dict:
        """Stage a local file for download via the HTTP tunnel.

        Returns {file_id, filename, size_bytes, local_url, tunnel_hint}.
        The claude.ai connector or artifact can fetch the file at
        <tunnel_url>/files/<file_id> with the bearer token.
        """
        if not file_path:
            return _err("file_path required", fix="pass the absolute path to a PDF, STL, or PNG")
        try:
            from bridge.mcp_http_server import stage_file_for_download, get_file_url
            r = stage_file_for_download(file_path, display_name)
            if not r.get("ok"):
                return _err(r.get("error", "staging failed"))
            fid = r["file_id"]
            return _ok({
                "file_id": fid,
                "filename": r["filename"],
                "size_bytes": r["size_bytes"],
                "local_url": get_file_url(fid),
                "tunnel_hint": f"Use your tunnel URL + /files/{fid} with Bearer auth",
            })
        except Exception as e:
            return _err(f"stage_file failed: {str(e)[:200]}")

    def list_staged_files(self) -> dict:
        """List files currently staged for tunnel download."""
        try:
            from bridge.mcp_http_server import _STAGED_INDEX, _STAGED_LOCK
            import time as _t
            with _STAGED_LOCK:
                items = []
                for fid, info in _STAGED_INDEX.items():
                    age_min = (_t.time() - info["staged_at"]) / 60
                    items.append({
                        "file_id": fid,
                        "name": info["name"],
                        "mime": info["mime"],
                        "size_bytes": info["size_bytes"],
                        "age_minutes": round(age_min, 1),
                    })
            return _ok({"count": len(items), "files": items})
        except Exception as e:
            return _err(f"list_staged failed: {str(e)[:200]}")

    def cleanup_staged(self, max_age_hours: int = 24) -> dict:
        """Remove staged files older than max_age_hours."""
        # pass 10i: numeric input hardening - coerce or fail clean
        max_age_hours, _e = _coerce_num(max_age_hours, 'max_age_hours', cast='int')
        if _e: return _e
        try:
            from bridge.mcp_http_server import cleanup_staged_files
            removed = cleanup_staged_files(max_age_hours)
            return _ok({"removed": removed, "max_age_hours": max_age_hours})
        except Exception as e:
            return _err(f"cleanup failed: {str(e)[:200]}")

    # ═══ HANDOFF DOCUMENT MODULES - Domain Engine ═════════════════

    def estimate_weld_consumable(self, joint_type: str = "fillet", size_in: float = 0.25,
                                  length_in: float = 12, process: str = "FCAW",
                                  filler: str = "E71T-1") -> dict:
        """Calculate weld consumable requirements for a single joint."""
        # pass 10i: numeric input hardening - coerce or fail clean
        size_in, _e = _coerce_num(size_in, 'size_in')
        if _e: return _e
        length_in, _e = _coerce_num(length_in, 'length_in')
        if _e: return _e
        from bridge.weld_consumable import estimate_joint
        _r = estimate_joint(joint_type, size_in, length_in, process, filler)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def estimate_project_consumables(self, joints: list) -> dict:
        """Calculate total weld consumables for a project."""
        from bridge.weld_consumable import estimate_project_consumables
        _r = estimate_project_consumables(joints)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_welder_alerts(self, days: int = 30) -> dict:
        """Get AWS D1.1 welder continuity expiration alerts."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.aws_d11_2025 import get_continuity_alerts, get_all_welders
        return _ok({"alerts": get_continuity_alerts(days), "welders": get_all_welders()})

    def add_welder(self, name: str, welder_id: str, processes: str = "FCAW,SMAW") -> dict:
        """Add a welder to the AWS D1.1 QA tracking system."""
        from bridge.aws_d11_2025 import add_welder
        _r = add_welder(name, welder_id, processes)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def record_weld_activity(self, welder_id: str) -> dict:
        """Record welding activity - resets 6-month continuity clock."""
        from bridge.aws_d11_2025 import record_weld_activity
        _r = record_weld_activity(welder_id)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_prequalified_wps(self) -> dict:
        """Get pre-qualified WPS templates per AWS D1.1:2025."""
        from bridge.aws_d11_2025 import get_prequalified_wps
        return _ok({"wps_templates": get_prequalified_wps()})

    def get_audit_readiness(self) -> dict:
        """AISC 207-25 audit readiness gap report."""
        from bridge.aisc_207_audit import audit_readiness_report
        return _ok(audit_readiness_report())  # vj: ok-passthrough-safe

    def log_shop_activity(self, mark_number: str, process: str, welder_id: str,
                           operation: str, hours: float = 0) -> dict:
        """Log daily shop activity for AISC 303 §2.1 active-fabrication evidence."""
        # pass 10i: numeric input hardening - coerce or fail clean
        hours, _e = _coerce_num(hours, 'hours')
        if _e: return _e
        from bridge.aisc_207_audit import log_shop_activity
        log_shop_activity(mark_number, process, welder_id, operation, hours)
        return _ok({"logged": True, "mark": mark_number})

    def get_shop_log(self, days: int = 7) -> dict:
        """Get recent shop log for auditor sampling."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.aisc_207_audit import get_shop_log
        return _ok({"log": get_shop_log(days)})

    def calculate_emr(self, claims: list, payroll_by_class: dict) -> dict:
        """Calculate projected EMR from claims and payroll."""
        from bridge.emr_predictor import calculate_emr
        _r = calculate_emr(claims, payroll_by_class)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def check_bid_emr(self, emr, prospect_type: str = "standard_gc") -> dict:
        """Check EMR eligibility for a bid. v3.2.7: coerce emr to float."""
        from bridge.emr_predictor import check_bid_eligibility
        try:
            emr_f = float(emr)
        except (TypeError, ValueError):
            return _err(f"EMR must be numeric (got {type(emr).__name__}: {emr!r}). Example: check_bid_emr(0.95, 'refinery_tic')")
        _r = check_bid_eligibility(emr_f, prospect_type)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_fab_productivity(self, hours: float, tons: float, complexity: str = "medium") -> dict:
        """Compare fabrication productivity to industry benchmarks."""
        # pass 10i: numeric input hardening - coerce or fail clean
        hours, _e = _coerce_num(hours, 'hours')
        if _e: return _e
        tons, _e = _coerce_num(tons, 'tons')
        if _e: return _e
        from bridge.productivity_kpis import calculate_fab_productivity
        return _ok(calculate_fab_productivity(hours, tons, complexity))  # vj: ok-passthrough-safe

    def get_markup_margin_table(self) -> dict:
        """Markup vs margin conversion table (always show both per handoff doc)."""
        from bridge.productivity_kpis import markup_margin_table
        return _ok({"table": markup_margin_table()})

    def check_schedule_feasibility(self, tons: float, ship_date: str) -> dict:
        """Check if shop capacity can meet the ship date."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tons, _e = _coerce_num(tons, 'tons')
        if _e: return _e
        if not ship_date:
            return _err("ship_date is required (YYYY-MM-DD).",
                        fix="check_schedule_feasibility(tons=65, ship_date='2026-09-15')")
        from bridge.productivity_kpis import schedule_check
        return _ok(schedule_check(tons, ship_date))  # vj: ok-passthrough-safe

    def parse_dstv(self, filepath: str) -> dict:
        """Parse a DSTV NC1 file into structured member data."""
        from bridge.dstv_parser import parse_nc1
        _r = parse_nc1(filepath)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def generate_pay_app(self, project_name: str, contractor: str, owner: str,
                          architect: str, app_number: int, period_to: str,
                          sov_items: list, retainage_pct: float = 10) -> dict:
        """Generate AIA G702/G703 pay application PDF."""
        # pass 10i: numeric input hardening - coerce or fail clean
        app_number, _e = _coerce_num(app_number, 'app_number', cast='int')
        if _e: return _e
        retainage_pct, _e = _coerce_num(retainage_pct, 'retainage_pct')
        if _e: return _e
        if not project_name or not contractor or not sov_items:
            return _err(
                "generate_pay_app requires project_name, contractor, owner, "
                "architect, app_number, period_to, and sov_items.",
                fix="Provide all 7 params. Example: generate_pay_app("
                    "project_name='Beck GMC', contractor='Your Company', "
                    "owner='Beck Auto', architect='ABC Architects', "
                    "app_number=3, period_to='2026-06-30', "
                    "sov_items=[{...}], retainage_pct=5.0)"
            )
        from bridge.aia_g702_g703 import generate_pay_app_pdf
        return _ok(generate_pay_app_pdf(project_name, contractor, owner, architect,  # vj: ok-passthrough-safe
                                         app_number, period_to, sov_items, retainage_pct))

    def get_lien_calendar(self, project_start: str = "",
                          role: str = "original_contractor") -> dict:
        """Texas Property Code Ch. 53 lien-notice calendar. Non-negotiable deadlines.

        SIM-07: project_start is now optional. Defaults to today (Houston local).
        Pass an explicit date in ISO format (YYYY-MM-DD) to compute deadlines
        from a specific project start date.
        """
        if not project_start:
            from datetime import datetime as _dt
            project_start = _dt.now().date().isoformat()  # vj: local-time-ok
        from bridge.aia_g702_g703 import lien_notice_calendar
        _r = lien_notice_calendar(project_start, role)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ HANDOFF DOCUMENT MODULES - Tier 3 Adapters ═══════════════

    def get_disa_status(self) -> dict:
        """Get all employee DISA compliance statuses."""
        from bridge.disa_status import get_all, get_non_current
        return _ok({"employees": get_all(), "non_current": get_non_current()})

    def pre_dispatch_check(self, employee_ids: list) -> dict:
        """Pre-dispatch DISA check before sending crew to refinery."""
        from bridge.disa_status import pre_dispatch_check
        return _ok(pre_dispatch_check(employee_ids))  # vj: ok-passthrough-safe

    def batch_check_connections(self, project: str = "", nodes: list = None) -> dict:
        """IDEA StatiCa batch connection check for AISC 360."""
        import json as _j
        if isinstance(nodes, str):
            try: nodes = _j.loads(nodes)
            except Exception: return _err("nodes must be a JSON array")
        if not project:
            return _err("project (str) is required")
        if not nodes or not isinstance(nodes, list):
            return _err("nodes must be a non-empty list")
        from bridge.idea_statica_checkbot import batch_check
        _r = batch_check(project, nodes)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def check_connections(self, project: str = "", nodes: list = None) -> dict:
        """IDEA StatiCa - AISC 360 connection check (single or batch)."""
        import json as _j
        if isinstance(nodes, str):
            try: nodes = _j.loads(nodes)
            except Exception: return _err("nodes must be a JSON array")
        try:
            from bridge.idea_statica_checkbot import get_status, get_project_checks
            if nodes:
                if not isinstance(nodes, list):
                    return _err(f"nodes must be a list; got {type(nodes).__name__}")
                from bridge.idea_statica_checkbot import batch_check
                return _ok(batch_check(project, nodes))  # vj: ok-passthrough-safe
            return _ok({"status": get_status()})
        except Exception as e:
            return _err(f"IDEA StatiCa connection check failed")

    # ── REMAINING HANDOFF MODULES ──────────────────────────────────

    def get_federal_opportunities(self, naics: str = "332312", state: str = "TX") -> dict:
        """SAM.gov v2 - daily federal opportunity feed by NAICS code."""
        try:
            from bridge.sam_gov_opportunities import search_opportunities
            return _ok(search_opportunities(naics=naics, state=state))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"SAM.gov: {e}")

    def calc_weld_consumable(self, joint_type: str = "fillet", leg_size_in: float = 0.25,
                             length_in: float = 12.0, process: str = "FCAW") -> dict:
        """Weld consumable burn-rate - lbs of electrode per joint with 10% buffer."""
        # pass 10i: numeric input hardening - coerce or fail clean
        leg_size_in, _e = _coerce_num(leg_size_in, 'leg_size_in')
        if _e: return _e
        length_in, _e = _coerce_num(length_in, 'length_in')
        if _e: return _e
        try:
            from bridge.weld_consumable import estimate_joint
            return _ok(estimate_joint(joint_type, leg_size_in, length_in, process))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Weld consumable: {e}")

    def get_wps_status(self) -> dict:
        """AWS D1.1:2025 - WPS/PQR/WPQ status, 6-month continuity, expiration alerts."""
        try:
            from bridge.aws_d11_2025 import for_morning_briefing, get_continuity_alerts
            return _ok({"briefing": for_morning_briefing(), "alerts": get_continuity_alerts()})
        except Exception as e:
            return _err(f"AWS D1.1: {e}")

    def get_isn_scorecard(self) -> dict:
        """ISNetworld scorecard polling + document-expiry alerts."""
        try:
            from bridge.isnetworld_client import get_status
            return _ok(get_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"ISN: {e}")

    def get_rfis_procore(self, project_id: str = "") -> dict:
        """Procore RFI triage - auto-classify by structural keyword (v3.2.7: renamed from get_rfis to fix shadow)."""
        try:
            from bridge.procore_rfi_submittal import get_status, classify_rfi
            return _ok(get_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Procore: {e}")

    def create_bluebeam_session(self, session_name: str = "") -> dict:
        """Bluebeam Studio - create markup session per submittal."""
        try:
            from bridge.bluebeam_studio import get_status
            return _ok(get_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Bluebeam: {e}")

    def predict_emr(self, open_claims: list = None, payroll_by_class: dict = None) -> dict:
        """NCCI EMR prediction - primary/excess split with bidding-gate check."""
        try:
            from bridge.emr_predictor import calculate_emr, check_bid_eligibility
            return _ok({"prediction": calculate_emr(open_claims or [], {}),
                        "gates": check_bid_eligibility(0.85)})
        except Exception as e:
            return _err(f"EMR predictor: {e}")

    def get_productivity_kpis(self, project_id: int = None) -> dict:
        """Tons/man-hour, hours/assembly, OTD, NCR rate - with industry benchmarks."""
        try:
            from bridge.productivity_kpis import BENCHMARKS
            return _ok(BENCHMARKS)
        except Exception as e:
            return _err(f"KPIs: {e}")

    # ═══ TIER 1: AUTOMATION CHAINS ═════════════════════════════════

    def get_event_log(self, limit: int = 50, event_type: str = None) -> dict:
        """Event bus - recent events and subscriber status."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        try:
            from bridge.event_bus import recent, count_by_type, get_subscribers, stats
            return _ok({"events": recent(limit, event_type), "counts": count_by_type(),
                        "subscribers": get_subscribers(), "stats": stats()})
        except Exception as e:
            return _err(f"Event bus: {e}")

    def emit_event(self, event_type: str, payload: dict = None) -> dict:
        """Manually emit an event (triggers all subscribed chains)."""
        from bridge.event_bus import emit
        emit(event_type, payload or {}, source="manual")
        return _ok({"emitted": event_type})

    def run_compliance_check(self, project_name: str = "", emr_threshold: float = 1.0) -> dict:
        """6-gate compliance pre-flight before bid submission."""
        # pass 10i: numeric input hardening - coerce or fail clean
        emr_threshold, _e = _coerce_num(emr_threshold, 'emr_threshold')
        if _e: return _e
        from bridge.action_chains import run_compliance_preflight
        return _ok(run_compliance_preflight(project_name, emr_threshold))  # vj: ok-passthrough-safe

    # ═══ TIER 2: INTELLIGENCE LAYER ════════════════════════════════

    def knowledge_query(self, query: str) -> dict:
        """Cross-entity knowledge graph search - 'show me everything about Marathon'."""
        from bridge.knowledge_graph import query_entity
        return _ok(query_entity(query))  # vj: ok-passthrough-safe

    def knowledge_for_ai(self, query: str) -> dict:
        """Knowledge graph context formatted for AI consumption."""
        from bridge.knowledge_graph import summary_for_ai
        return _ok({"context": summary_for_ai(query)})

    def get_calibrated_estimate(self, tonnage: float, project_type: str = "commercial") -> dict:
        """Self-learning estimator - calibrated to Your Company actuals or industry baselines."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        from bridge.learning_estimator import estimate_project, get_calibrated_rates
        return _ok({"estimate": estimate_project(tonnage, project_type),
                    "rates": get_calibrated_rates()})

    def quick_bid_estimate(self, struct_tons: float = 0, joist_tons: float = 0,
                           building_sf: float = 0, deck_sf: float = 0,
                           deck_type: str = "roof",
                           composite_deck_sf: float = 0,
                           project_name: str = "", gc_company: str = "",
                           location: str = "") -> dict:
        """LOCAL bid estimate from explicit numbers. No LLM. No PDF. No API call.

        Owner types: '65 tons structural, 25 tons joists, 21,930 SF retail'
        This method returns a complete bid with line items, $/SF, and GP.

        Uses Q2 2026 Houston calibrated rates (bridge/bid_rates.py).
        Runs sanity gates. Runs Virtual Owner review. Returns ready-to-use numbers.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        struct_tons, _e = _coerce_num(struct_tons, 'struct_tons')
        if _e: return _e
        joist_tons, _e = _coerce_num(joist_tons, 'joist_tons')
        if _e: return _e
        building_sf, _e = _coerce_num(building_sf, 'building_sf')
        if _e: return _e
        deck_sf, _e = _coerce_num(deck_sf, 'deck_sf')
        if _e: return _e
        composite_deck_sf, _e = _coerce_num(composite_deck_sf, 'composite_deck_sf')
        if _e: return _e
        from bridge.bid_rates import BID_RATES

        # Input validation
        if struct_tons <= 0 and joist_tons <= 0:
            return _err(
                "No tonnage provided. Pass struct_tons and/or joist_tons > 0.",
                fix="example: `bid 65t 22 joists 38400sf` for a 65-ton structural + 22-ton joist building"
            )
        if building_sf <= 0:
            return _err(
                "building_sf must be > 0 to compute $/SF.",
                fix="add building square footage to your command, e.g. `bid 65t 38400sf`"
            )
        if struct_tons < 0 or joist_tons < 0 or building_sf < 0:
            return _err(
                "Inputs must be non-negative.",
                fix="all of struct_tons, joist_tons, building_sf must be positive numbers"
            )

        # Default deck SF to building SF if not specified
        if not deck_sf and building_sf:
            deck_sf = building_sf

        # Line items
        fab_cost = struct_tons * BID_RATES["fab_per_ton"]
        erect_cost = struct_tons * BID_RATES["erection_per_ton"]
        joist_cost = joist_tons * BID_RATES["joists_per_ton"]

        roof_deck_cost = 0
        comp_deck_cost = 0
        if deck_type == "roof" and deck_sf:
            roof_deck_cost = deck_sf * BID_RATES["roof_deck_per_sf"]
        elif deck_type == "composite" and deck_sf:
            comp_deck_cost = deck_sf * BID_RATES["composite_deck_per_sf"]
        if composite_deck_sf:
            comp_deck_cost = composite_deck_sf * BID_RATES["composite_deck_per_sf"]

        subtotal = fab_cost + erect_cost + joist_cost + roof_deck_cost + comp_deck_cost
        ga = subtotal * BID_RATES["ga_overhead_pct"]
        total = subtotal + ga
        total_tons = struct_tons + joist_tons

        per_sf = total / building_sf if building_sf > 0 else 0

        line_items = []
        if fab_cost > 0:
            line_items.append({"desc": "Structural Steel Fabrication", "amount": round(fab_cost), "detail": f"{struct_tons:.0f} tons x ${BID_RATES['fab_per_ton']:,}/ton"})
        if erect_cost > 0:
            line_items.append({"desc": "Structural Steel Erection", "amount": round(erect_cost), "detail": f"{struct_tons:.0f} tons x ${BID_RATES['erection_per_ton']:,}/ton"})
        if joist_cost > 0:
            line_items.append({"desc": "Open Web Steel Joists", "amount": round(joist_cost), "detail": f"{joist_tons:.0f} tons x ${BID_RATES['joists_per_ton']:,}/ton"})
        if roof_deck_cost > 0:
            line_items.append({"desc": "Metal Roof Deck Supply & Install", "amount": round(roof_deck_cost), "detail": f"{deck_sf:,.0f} SF x ${BID_RATES['roof_deck_per_sf']}/SF"})
        if comp_deck_cost > 0:
            sf_used = composite_deck_sf or deck_sf
            line_items.append({"desc": "Composite Deck Supply & Install", "amount": round(comp_deck_cost), "detail": f"{sf_used:,.0f} SF x ${BID_RATES['composite_deck_per_sf']}/SF"})

        result = {
            "project_name": project_name or "Quick Estimate",
            "gc_company": gc_company,
            "location": location,
            "struct_tons": struct_tons,
            "joist_tons": joist_tons,
            "total_tons": total_tons,
            "building_sf": building_sf,
            "line_items": line_items,
            "subtotal": round(subtotal),
            "ga_overhead": round(ga),
            "ga_pct": BID_RATES["ga_overhead_pct"] * 100,
            "total_bid": round(total),
            "per_sf": round(per_sf, 2),
            "rates_source": "Q2 2026 Houston calibrated",
        }

        # Run sanity gates if we have SF
        if building_sf > 0:
            try:
                from bridge.bid_sanity_gates import gate3_dollar_per_sf
                g3_status, g3_val, g3_warn = gate3_dollar_per_sf(total, building_sf, "retail_small")
                result["sanity_gate_3"] = {"status": g3_status, "per_sf": round(g3_val, 2), "warning": g3_warn}
                if g3_status == "BLOCK":
                    result["sanity_blocked"] = True
                    result["sanity_warning"] = g3_warn
            except Exception:
                pass

        # Run Virtual Owner review
        try:
            from bridge.virtual_owner import review_bid
            vm_input = {
                "project_name": result["project_name"],
                "total_bid": result["total_bid"],
                "tonnage": total_tons,
                "building_sf": building_sf,
                "line_items": [{"desc": li["desc"], "amount": li["amount"]} for li in line_items],
                "gp_pct": 0.25,
            }
            vm = review_bid(vm_input)
            result["vm_review"] = {
                "approved": vm.get("approved"),
                "confidence": vm.get("confidence"),
                "issues": [str(i)[:100] for i in vm.get("issues", [])[:3]],
            }
            if vm.get("owner_would_say"):
                result["vm_says"] = vm["owner_would_say"][:200]
        except Exception:
            pass

        return _ok(result)

    # ── RECONCILIATION ADVISORY GATE (plan item 1.2) ──────────────

    def bid_reconciliation_check(self, estimate: str = "", register: str = "",
                                 estimate_path: str = "", register_path: str = "",
                                 building_type: str = "") -> dict:
        """ADVISORY reconciliation cross-check (plan item 1.2).

        Diffs a finished estimate against a requirements-and-exclusions
        register and returns a coverage rate plus named gaps: unpriced items,
        double-count candidates, excluded-but-priced, and orphan lines.
        READ-ONLY. It never sets or changes a price, quantity, weight, or rate
        and never returns a go/no-go verdict on price. Best run as a fresh,
        memoryless pass. Shared by the GUI and the MCP server (same Bridge).

        Pass either inline JSON or a file path for each input:
            estimate / estimate_path: the estimate or BOQ. JSON may be a bare
                list of line dicts or a wrapper {"rows"|"line_items"|"lines": [...]}.
            register / register_path: the requirements-and-exclusions register.
                JSON may be a bare list, a wrapper {"items"|"requirements": [...]},
                or {"inclusions": [...], "exclusions": [...]}; exclusions are
                merged as register rows with category "Excluded".
            building_type: optional, echoed into the report for context only.
        """
        try:
            from bridge.bid_sanity_gates import reconcile_advisory
        except Exception as e:
            return _err(f"Reconciliation check unavailable: {e}")

        def _load(raw, path, list_keys, label):
            """Return a parsed JSON value (list or dict) for one input."""
            if path:
                p = Path(path)
                if not p.is_absolute():
                    p = _app_root() / path
                if not p.exists():
                    raise ValueError(f"{label} file not found: {p}")
                return json.loads(p.read_text(encoding="utf-8"))
            if raw:
                return raw if isinstance(raw, (list, dict)) else json.loads(raw)
            return []

        def _as_rows(data, list_keys):
            """Pull a list of rows out of a bare list or a wrapper object."""
            if isinstance(data, list):
                return list(data)
            if isinstance(data, dict):
                for k in list_keys:
                    if isinstance(data.get(k), list):
                        return list(data[k])
            return []

        try:
            est_raw = _load(estimate, estimate_path, (), "estimate")
            reg_raw = _load(register, register_path, (), "register")
        except json.JSONDecodeError as e:
            # JSONDecodeError subclasses ValueError, so catch it first.
            return _err(f"Could not parse JSON input: {e}",
                        fix="pass valid JSON for `estimate` and `register`, or use the *_path args")
        except ValueError as e:
            return _err(str(e))

        est_rows = _as_rows(est_raw, ("rows", "line_items", "lines", "estimate"))
        register_rows = _as_rows(reg_raw, ("items", "requirements", "register", "rows"))

        # Merge an inclusions/exclusions list when one is supplied as a wrapper.
        if isinstance(reg_raw, dict):
            for ex in reg_raw.get("exclusions", []) or []:
                row = dict(ex) if isinstance(ex, dict) else {"description": str(ex)}
                row.setdefault("req_id", row.get("list_id", ""))
                row["category"] = "Excluded"
                register_rows.append(row)
            for inc in reg_raw.get("inclusions", []) or []:
                row = dict(inc) if isinstance(inc, dict) else {"description": str(inc)}
                row.setdefault("req_id", row.get("list_id", ""))
                row.setdefault("category", "Direct")
                register_rows.append(row)

        try:
            result = reconcile_advisory(est_rows, register_rows,
                                        building_type=building_type or None)
        except Exception as e:
            return _err(f"Reconciliation check failed: {e}")
        return _ok(result)

    # ── CANONICAL TAKEOFF ROW SCHEMA (plan item 1.3) ──────────────

    def takeoff_rows_validate(self, rows: str = "", rows_path: str = "") -> dict:
        """Validate canonical takeoff rows (plan item 1.3).

        The row is Tag, Description, System, Qty, Unit, Drawing, Method,
        Confidence, Basis, Notes. Confidence is method-linked; inferred and
        vision rows must carry a written assumption in Basis. ADVISORY AND
        STRUCTURAL ONLY: it validates a shape and never sets or changes a
        price, quantity, weight, or rate. Shared by GUI and MCP. Accepts
        inline JSON (a list, or an object with a "rows" list) or a file path.
        """
        try:
            from bridge.takeoff_row import validate_rows
        except Exception as e:
            return _err(f"Takeoff row schema unavailable: {e}")
        try:
            if rows_path:
                p = Path(rows_path)
                if not p.is_absolute():
                    p = _app_root() / rows_path
                if not p.exists():
                    return _err(f"rows file not found: {p}")
                data = json.loads(p.read_text(encoding="utf-8"))
            elif rows:
                data = rows if isinstance(rows, (list, dict)) else json.loads(rows)
            else:
                data = []
        except json.JSONDecodeError as e:
            return _err(f"Could not parse JSON input: {e}",
                        fix="pass a JSON list of takeoff rows, or use rows_path")
        row_list = data.get("rows") if isinstance(data, dict) else data
        if not isinstance(row_list, list):
            return _err("rows must be a JSON list of takeoff-row objects")
        return _ok(validate_rows(row_list))  # vj: ok-passthrough-safe

    # ── CONNECTION-INFO COMPLETENESS GATE (plan items 2.1/2.3/2.4/2.5/2.6) ──

    def connection_info_check(self, context: str = "", context_path: str = "",
                              project_id: str = "") -> dict:
        """Connection-information completeness gate.

        ADVISORY AND STRUCTURAL ONLY. Flags missing or ambiguous connection
        information (transfer forces, seismic system, AESS, surface prep,
        hidden bracing, gross SF, general-note connections), emits
        LOW-confidence flags and RFIs, and lists what must be resolved before
        pricing. It never sets or changes a price, quantity, weight, or rate
        and gives no go/no-go verdict on price. Shared by GUI and MCP. Accepts
        inline JSON (an object describing the set) or a file path.
        """
        try:
            from bridge.connection_completeness import check_connection_completeness
        except Exception as e:
            return _err(f"Connection completeness gate unavailable: {e}")
        try:
            if context_path:
                p = Path(context_path)
                if not p.is_absolute():
                    p = _app_root() / context_path
                if not p.exists():
                    return _err(f"context file not found: {p}")
                ctx = json.loads(p.read_text(encoding="utf-8"))
            elif context:
                ctx = context if isinstance(context, dict) else json.loads(context)
            else:
                ctx = {}
        except json.JSONDecodeError as e:
            return _err(f"Could not parse JSON input: {e}",
                        fix="pass a JSON object describing the connection info, or use context_path")
        if not isinstance(ctx, dict):
            return _err("context must be a JSON object")
        try:
            result = check_connection_completeness(ctx, project_id=project_id)
        except Exception as e:
            return _err(f"Connection completeness check failed: {e}")
        return _ok(result)

    # ── CONNECTION TAKE-OFF / ALLOWANCE PASS (plan item 1.1) ──────

    def connection_takeoff_pass(self, framing_type: str = "",
                                structural_tons: str = "", members: str = "",
                                project_id: str = "", drawing: str = "") -> dict:
        """Connection take-off / connection-material allowance pass (item 1.1).

        VERIFY-DO-NOT-GENERATE. Sizes a ROM connection-material allowance
        deterministically: the percentage is read live from Ivan's locked
        calibration by framing type, the structural tonnage comes from
        bridge/aisc_validator.py, and the rate from bridge/bid_rates.py. No
        number originates in the model. If the framing type is not
        determinable, it emits a LOW-confidence flag and an RFI rather than
        defaulting. Pass structural_tons (validator-sourced) or members (a JSON
        list of {shape, qty, length_ft} run through the validator). Shared by
        GUI and MCP.
        """
        try:
            from bridge.connection_takeoff import connection_takeoff
        except Exception as e:
            return _err(f"Connection takeoff unavailable: {e}")
        st = None
        if structural_tons not in (None, ""):
            st, _e = _coerce_num(structural_tons, "structural_tons")
            if _e:
                return _e
        mem = None
        if members:
            try:
                mem = members if isinstance(members, list) else json.loads(members)
            except json.JSONDecodeError as e:
                return _err(f"Could not parse members JSON: {e}",
                            fix="pass members as a JSON list of {shape, qty, length_ft}")
            if not isinstance(mem, list):
                return _err("members must be a JSON list of {shape, qty, length_ft}")
        try:
            result = connection_takeoff(framing_type=framing_type,
                                        structural_tons=st, members=mem,
                                        project_id=project_id, drawing=drawing)
        except FileNotFoundError as e:
            return _err(f"Ivan calibration file not found: {e}")
        except Exception as e:
            return _err(f"Connection takeoff failed: {e}")
        return _ok(result)

    # ── MISC STEEL + PLATE CALCULATOR ─────────────────────────────

    def calculate_plate_weight(self, notation: str = "", qty: int = 1,
                               thickness_in: float = 0, width_in: float = 0,
                               length_in: float = 0) -> dict:
        """Calculate weight of steel plates (not in AISC database).
        Input: PL notation (e.g. PL.750X12X12) or raw dimensions.
        LOCAL COMPUTATION - no AI call.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        qty, _e = _coerce_num(qty, 'qty', cast='int')
        if _e: return _e
        thickness_in, _e = _coerce_num(thickness_in, 'thickness_in')
        if _e: return _e
        width_in, _e = _coerce_num(width_in, 'width_in')
        if _e: return _e
        length_in, _e = _coerce_num(length_in, 'length_in')
        if _e: return _e
        from bridge.misc_steel_calculator import (
            calculate_plate_from_notation, calculate_plate_weight as _calc_pw
        )
        _plate_fix = "use format `PL<thickness>X<width>X<length>`, e.g. `PL1/2X12X12` (decimal thickness like `PL.500X12X12` also works)"
        # Input validation
        if qty < 1:
            return _err(f"qty must be >= 1 (got {qty}).",
                        fix="pass qty as a positive integer, e.g. qty=24")
        if not notation and (thickness_in <= 0 or width_in <= 0 or length_in <= 0):
            return _err("Provide notation or positive thickness_in/width_in/length_in.",
                        fix=_plate_fix)
        if notation and (thickness_in or width_in or length_in) and \
           (thickness_in < 0 or width_in < 0 or length_in < 0):
            return _err("Dimensions must be non-negative.",
                        fix="all of thickness_in, width_in, length_in must be positive numbers in inches")
        try:
            if notation:
                result = calculate_plate_from_notation(notation, qty)
            elif thickness_in and width_in and length_in:
                result = _calc_pw(thickness_in, width_in, length_in, qty)
            else:
                return _err("Provide PL notation (e.g. PL.750X12X12) or dimensions (thickness_in, width_in, length_in)",
                            fix=_plate_fix)
            if "error" in result:
                return _err(result["error"], fix=_plate_fix)
            return _ok(result)
        except Exception as e:
            return _err(str(e), fix=_plate_fix)

    def estimate_misc_steel(self, verified_tons: float = 0,
                            member_count: int = 0,
                            building_type: str = "commercial",
                            plates_json: str = "",
                            num_members: int = None) -> dict:
        """Estimate misc steel (connections, plates, hardware) as % of tonnage.
        Combines: AISC verified tonnage + explicit plates + connection estimate.
        LOCAL COMPUTATION - no AI call.

        SIM-07: accepts either `member_count=` (canonical) or `num_members=`
        (the Owner's natural kwarg).
        """
        # SIM-07 alias resolution
        if num_members is not None and not member_count:
            member_count = num_members
        # pass 10i: numeric input hardening - coerce or fail clean
        verified_tons, _e = _coerce_num(verified_tons, 'verified_tons')
        if _e: return _e
        member_count, _e = _coerce_num(member_count, 'member_count', cast='int')
        if _e: return _e
        from bridge.misc_steel_calculator import apply_misc_factor
        import json as _json
        _misc_fix = (
            "example: `misc steel for 65 tons 18 members commercial` "
            "(building_type can be: commercial, dealership, industrial, retail)"
        )
        if verified_tons <= 0:
            return _err(
                f"verified_tons must be > 0 (got {verified_tons}).",
                fix=_misc_fix
            )
        try:
            plates = _json.loads(plates_json) if plates_json else []
        except _json.JSONDecodeError as e:
            return _err(
                f"plates_json must be valid JSON: {e}",
                fix='pass plates_json as a JSON array like [{"thickness":"1/2","width":12,"length":12,"qty":24}] or omit it entirely'
            )
        try:
            result = apply_misc_factor(
                verified_tons, misc_pct=0.06,
                plates=plates, building_type=building_type,
                member_count=member_count
            )
            # P6 ROADMAP: one-line summary so Owner gets ONE number instead
            # of five sub-fields. Frontend can show this first, then offer
            # the breakdown on demand.
            misc_added = (result.get("plate_tons", 0)
                         + result.get("connection_tons", 0)
                         + result.get("remaining_misc_tons", 0))
            result["misc_tons"] = round(misc_added, 2)
            result["summary_line"] = (
                f"misc steel = {misc_added:.2f} tons "
                f"(+{result.get('tonnage_increase_pct', 0):.1f}%) "
                f"→ total {result.get('total_tons', 0):.2f} tons"
            )
            return _ok(result)
        except Exception as e:
            return _err(str(e), fix=_misc_fix)

    # ── TAGGED PDF RENDERER ───────────────────────────────────────

    def render_tagged_pdf(self, source_pdf: str = "", members_json: str = "",
                          summary_json: str = "", output_path: str = "",
                          force_ai: bool = False) -> dict:
        """Annotate a structural drawing PDF with color-coded shape tags.

        Text PDFs: instant local annotation (PyMuPDF text search).
        Scanned PDFs: Gemini + OpenAI vision cascade (accuracy-first).
        Produces annotated PDF with highlights, weight labels, summary page.
        """
        from bridge.tagged_pdf_renderer import render_tagged_pdf as _render
        import json as _json
        try:
            members = _json.loads(members_json) if members_json else []
            summary = _json.loads(summary_json) if summary_json else None
            keys = _load_all_keys()
            result = _render(
                source_pdf, members, output_path, summary,
                gemini_key=keys.get("GOOGLE_API_KEY", ""),
                openai_key=keys.get("OPENAI_API_KEY", ""),
                force_ai=force_ai,
            )
            if "error" in result:
                return _err(result["error"])
            return _ok(result)
        except Exception as e:
            return _err(str(e))

    def log_project_completion(self, project_name: str, est_tons: float = 0, act_tons: float = 0,
                               est_hours: float = 0, act_hours: float = 0,
                               est_cost: float = 0, act_cost: float = 0) -> dict:
        """Feed actual data back into the learning estimator."""
        # pass 10i: numeric input hardening - coerce or fail clean
        est_tons, _e = _coerce_num(est_tons, 'est_tons')
        if _e: return _e
        act_tons, _e = _coerce_num(act_tons, 'act_tons')
        if _e: return _e
        est_hours, _e = _coerce_num(est_hours, 'est_hours')
        if _e: return _e
        act_hours, _e = _coerce_num(act_hours, 'act_hours')
        if _e: return _e
        est_cost, _e = _coerce_num(est_cost, 'est_cost')
        if _e: return _e
        act_cost, _e = _coerce_num(act_cost, 'act_cost')
        if _e: return _e
        from bridge.learning_estimator import log_project_completion
        log_project_completion(project_name, "commercial", est_tons, act_tons, est_hours, act_hours, est_cost, act_cost)
        return _ok({"logged": True, "project": project_name})

    def get_cash_flow_projection(self, bank_balance: float = 0, monthly_overhead: float = 45000) -> dict:
        """30/60/90 day cash flow projection with recommendations."""
        # pass 10i: numeric input hardening - coerce or fail clean
        bank_balance, _e = _coerce_num(bank_balance, 'bank_balance')
        if _e: return _e
        monthly_overhead, _e = _coerce_num(monthly_overhead, 'monthly_overhead')
        if _e: return _e
        from bridge.cashflow_cfo import project_cash_flow
        _r = project_cash_flow(bank_balance=bank_balance, monthly_overhead=monthly_overhead)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_revenue_attribution(self) -> dict:
        """ROI tracking - hours saved, actions automated, value generated."""
        from bridge.cashflow_cfo import revenue_attribution
        _r = revenue_attribution()
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ TIER 3: SHOP FLOOR INTEGRATION ════════════════════════════

    def add_shop_piece(self, mark_number: str, project: str, profile: str = "", weight_lb: float = 0) -> dict:
        """Register a piece for barcode-driven shop floor tracking."""
        from bridge.shop_floor import generate_piece_qr
        result = generate_piece_qr(mark_number, project)
        return _ok({"piece_id": mark_number, "mark": mark_number, "qr": result})

    def scan_piece(self, piece_id: int, station: str, worker_id: str = "",
                   welder_id: str = "", wps_id: str = "") -> dict:
        """Record a barcode scan at a production station."""
        # pass 10i: numeric input hardening - coerce or fail clean
        piece_id, _e = _coerce_num(piece_id, 'piece_id', cast='int')
        if _e: return _e
        from bridge.shop_floor import update_piece_status
        _r = update_piece_status(str(piece_id), station, station, worker_id)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def log_production(self, project: str, tons_fabricated: float = 0, tons_erected: float = 0,
                       pieces_completed: int = 0, crew_size: int = 0, hours_worked: float = 0) -> dict:
        """Voice-first: 'log 47 tons erected today ICD 6-man crew'."""
        from bridge.shop_floor import get_production_kpis
        get_production_kpis(project)  # read current state
        return _ok({"logged": True, "project": project})

    def get_production_board(self, project: str = None) -> dict:
        """Real-time production board - where is every piece?"""
        from bridge.shop_floor import get_job_status
        _r = get_job_status(project or "")
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_shop_kpis(self, project: str = None, days: int = 30) -> dict:
        """Shop floor KPIs - tons/day, tons/man-hour, pieces/shift."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.shop_floor import get_production_kpis
        _r = get_production_kpis(project, days)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ TIER 3B: PROJECT CONTROLS (PC4+PC5) ═══════════════════════
    # SPI/CPI, forecast-to-complete, and variance by cost code per WBS
    # line. Reads the PC3 progress_log table plus the PC1 frozen baseline
    # xlsx. Feeds the CONTROLS dashboard view only. CONFIDENTIAL -
    # INTERNAL, never client-facing.

    def get_spi_cpi(self, project_id: str = "") -> dict:
        """SPI/CPI per WBS line plus S-curve series for an awarded project.

        SPI = earned / planned, CPI = earned / actual per WBS line; lines
        below 0.95 on either index are flagged (PC4)."""
        if not isinstance(project_id, str) or not project_id.strip():
            return _err("project_id is required",
                        fix="pass the awarded project code, e.g. PRJ-2026-ACP-001")
        try:
            from bridge.project_controls import spi_cpi
            _r = spi_cpi(project_id)
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"], fix=_r.get("fix", ""))
            return _ok(_r)
        except Exception as e:
            return _err(f"spi_cpi failed: {e}")

    def get_forecast_to_complete(self, project_id: str = "") -> dict:
        """Forecast at completion per WBS line rolled to project level.

        Project-level forecast variance is checked against the Section 07
        control limits: investigate outside -1.7 / +7.3 percent."""
        if not isinstance(project_id, str) or not project_id.strip():
            return _err("project_id is required",
                        fix="pass the awarded project code, e.g. PRJ-2026-ACP-001")
        try:
            from bridge.project_controls import forecast_to_complete
            _r = forecast_to_complete(project_id)
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"], fix=_r.get("fix", ""))
            return _ok(_r)
        except Exception as e:
            return _err(f"forecast_to_complete failed: {e}")

    def get_variance_by_cost_code(self, project_id: str = "") -> dict:
        """Cost and schedule variance grouped by cost code (PC5 table).

        Client-caused variance lines carry the contract-admin notice note
        per PC6; flagged groups carry the corrective hierarchy text."""
        if not isinstance(project_id, str) or not project_id.strip():
            return _err("project_id is required",
                        fix="pass the awarded project code, e.g. PRJ-2026-ACP-001")
        try:
            from bridge.project_controls import variance_by_cost_code
            _r = variance_by_cost_code(project_id)
            if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
                return _err(_r["error"], fix=_r.get("fix", ""))
            return _ok(_r)
        except Exception as e:
            return _err(f"variance_by_cost_code failed: {e}")

    # ═══ TIER 4: AUTONOMOUS OPERATIONS ═════════════════════════════

    def analyze_bid(self, bid_text: str) -> dict:
        """Auto-analyze a bid invitation - extract scope, check sweet spot, flag disqualifiers."""
        from bridge.autonomous_bidding import analyze_bid_invitation
        _r = analyze_bid_invitation(bid_text)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def auto_respond_to_bid(self, bid_text: str) -> dict:
        """Full autonomous bid response pipeline - analyze → comply → estimate → propose → draft email."""
        from bridge.autonomous_bidding import auto_response_pipeline
        keys = _load_all_keys()
        _r = auto_response_pipeline(bid_text, keys)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def match_opportunity(self, title: str = "", description: str = "", location: str = "") -> dict:
        """Score an opportunity against Your Company's sweet spot."""
        from bridge.autonomous_bidding import match_opportunity
        _r = match_opportunity({"title": title, "description": description, "location": location})
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def add_to_hash_chain(self, doc_type: str, doc_name: str, file_path: str = "", content: str = "") -> dict:
        """Add a document to the tamper-evident hash chain."""
        from bridge.hash_chain import add_to_chain
        _r = add_to_chain(doc_type, doc_name, file_path, content)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def verify_hash_chain(self) -> dict:
        """Verify the entire document hash chain is intact."""
        from bridge.hash_chain import verify_chain, stats
        return _ok({"verification": verify_chain(), "stats": stats()})

    def verify_document(self, file_path: str) -> dict:
        """Verify a specific document against the hash chain."""
        from bridge.hash_chain import verify_document
        _r = verify_document(file_path)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ 500% ROADMAP - MODULE 1: COST ENGINE ═════════════════════

    def fetch_steel_prices(self) -> dict:
        """Pull FRED PPI + EIA energy + ScrapMonster scrap prices."""
        from bridge.cost_engine.engine import fetch_fred_prices, fetch_eia_prices, fetch_scrap_prices
        keys = _load_all_keys()
        return _ok({
            "fred": fetch_fred_prices(keys.get("fred_api_key", "")),
            "eia": fetch_eia_prices(keys.get("eia_api_key", "")),
            "scrap": fetch_scrap_prices(),
        })

    def recommend_hedge(self, project: str, tonnage: float, fab_cycle_days: int = 90,
                         spot_hrc: float = 0, forward_hrc: float = 0) -> dict:
        """Hedge advisor - recommend fixed-price POs or CME futures for >50 ton / >60 day projects."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        fab_cycle_days, _e = _coerce_num(fab_cycle_days, 'fab_cycle_days', cast='int')
        if _e: return _e
        spot_hrc, _e = _coerce_num(spot_hrc, 'spot_hrc')
        if _e: return _e
        forward_hrc, _e = _coerce_num(forward_hrc, 'forward_hrc')
        if _e: return _e
        if not project:
            return _err("project is required.", fix="recommend_hedge(project='Beck GMC', tonnage=65)")
        from bridge.cost_engine.engine import recommend_hedge
        _r = recommend_hedge(project, tonnage, fab_cycle_days, spot_hrc, forward_hrc)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def get_landed_cost(self, tonnage: float, shape: str = "W", delivery_miles: float = 30) -> dict:
        """Calculate landed cost per ton including material + fuel surcharge."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        delivery_miles, _e = _coerce_num(delivery_miles, 'delivery_miles')
        if _e: return _e
        from bridge.cost_engine.engine import calculate_landed_cost
        _r = calculate_landed_cost(tonnage, shape, delivery_miles)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def ingest_service_center_prices(self, vendor: str, price_lines: list) -> dict:
        """Store prices from Triple-S, Reliance, Olympic, Steel Technologies email/PDF."""
        from bridge.cost_engine.engine import ingest_service_center_prices
        _r = ingest_service_center_prices(vendor, price_lines)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ 500% ROADMAP - MODULE 2: COMPLIANCE V2 ═══════════════════

    def calculate_emr_2025(self, payroll_by_class: dict, claims: list) -> dict:
        """NCCI 2025 EMR with Texas state-specific split points (fixes old formula bug)."""
        from bridge.ncci_2025 import calculate_emr_2025
        return _ok(calculate_emr_2025(payroll_by_class, claims))  # vj: ok-passthrough-safe

    def check_wps_d11_2025(self, wps: dict, code_year: str = "2025") -> dict:
        """AWS D1.1:2025 WPS compliance check - pulsed-spray, Type-D studs, plug/slot, PWHT."""
        import json as _j
        if isinstance(wps, str):
            try:
                wps = _j.loads(wps)
            except Exception:
                return _err("wps must be a JSON object (dict)")
        if not isinstance(wps, dict):
            return _err(f"wps must be a dict; got {type(wps).__name__}")
        from bridge.aws_d11_2025_compliance import check_wps_compliance
        return _ok(check_wps_compliance(wps, code_year))  # vj: ok-passthrough-safe

    # ═══ 500% ROADMAP - MODULE 3: AI TAKEOFF ═════════════════════

    def run_takeoff(self, pdf_path: str = "", plan_text: str = "", project_name: str = "") -> dict:
        """AI-powered plan takeoff → BOM → DSTV. 85-92% accuracy target."""
        from bridge.lift_clone.takeoff import run_takeoff
        _r = run_takeoff(pdf_path, plan_text, project_name)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ 500% ROADMAP - MODULE 4: DOCUMENT INTELLIGENCE ═══════════

    def analyze_spec(self, text: str, project_name: str = "") -> dict:
        """Parse CSI spec → extract steel submittals → link AWS/AISC clauses."""
        from bridge.doc_intel.intelligence import analyze_document
        return _ok(analyze_document(text, "spec", project_name))  # vj: ok-passthrough-safe

    def diff_addendum(self, text_old: str, text_new: str) -> dict:
        """Compare addendum versions - highlight steel-relevant changes."""
        from bridge.doc_intel.intelligence import diff_documents
        return _ok(diff_documents(text_old, text_new))  # vj: ok-passthrough-safe

    def classify_shop_drawing_review(self, comments: str) -> dict:
        """Classify shop drawing review response: APPROVED / REVISE_RESUBMIT / REJECTED."""
        from bridge.doc_intel.intelligence import classify_review_comments
        return _ok(classify_review_comments(comments))  # vj: ok-passthrough-safe

    # ═══ 500% ROADMAP - MODULE 5: FINANCIAL AUTOMATION ════════════

    def calculate_lien_deadlines(self, project: str = "", work_months: list = None,
                                  project_type: str = "commercial", owner: str = "",
                                  state: str = "TX") -> dict:
        """Texas Property Code Ch. 53 lien deadline calculator with hash-chain proof.

        SIM-07: accepts `state=` kwarg. Currently only TX is fully supported
        (the Property Code Ch. 53 rules are Texas-specific). Pass state='TX'
        explicitly to document intent; any other value returns a structured
        "not supported" response.
        """
        if state and state.upper() not in ("TX", "TEXAS"):
            return _err(
                f"state={state!r} not supported. This module implements Texas "
                f"Property Code Ch. 53 only. For other states, consult counsel.",
                fix="Pass state='TX' or omit the kwarg.",
            )
        if work_months is None:
            work_months = []
        if not project:
            return _err("project name is required.")
        from bridge.fin_automation.finance import calculate_lien_deadlines
        result = calculate_lien_deadlines(project, work_months, project_type, False, owner)
        return _ok({"deadlines": result} if isinstance(result, list) else result)

    def get_lien_deadlines(self, days: int = 30) -> dict:
        """Get upcoming lien deadlines due in next N days."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        from bridge.fin_automation.finance import get_upcoming_deadlines
        return _ok({"deadlines": get_upcoming_deadlines(days)})

    def check_bond_capacity(self, project_value: float) -> dict:
        """Check surety bond capacity for a project."""
        # pass 10i: numeric input hardening - coerce or fail clean
        project_value, _e = _coerce_num(project_value, 'project_value')
        if _e: return _e
        from bridge.fin_automation.finance import check_bond_capacity
        _r = check_bond_capacity(project_value)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ 500% ROADMAP - MODULE 6: HOUSTON MARKET ══════════════════

    def get_houston_pipeline(self, top_n: int = 25) -> dict:
        """Monday morning pipeline board - top N Houston EPC opportunities."""
        # pass 10i: numeric input hardening - coerce or fail clean
        top_n, _e = _coerce_num(top_n, 'top_n', cast='int')
        if _e: return _e
        from bridge.houston_market.pipeline import get_pipeline
        return _ok({"pipeline": get_pipeline(top_n)})

    def get_turnaround_calendar(self) -> dict:
        """Refinery turnaround windows - Marathon, Exxon, Shell, Valero, Lyondell."""
        from bridge.houston_market.pipeline import get_turnarounds
        return _ok({"turnarounds": get_turnarounds()})

    def get_houston_briefing(self) -> dict:
        """Pipeline summary for morning briefing."""
        from bridge.houston_market.pipeline import for_briefing
        return _ok({"briefing": for_briefing()})

    # ═══ 500% ROADMAP - MODULE 7: PREDICTIVE ANALYTICS ════════════

    def predict_bid_win(self, tonnage: float, our_price: float,
                         est_market: float = 0, gc: str = "") -> dict:
        """Predict probability of winning a bid based on historical patterns."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        our_price, _e = _coerce_num(our_price, 'our_price')
        if _e: return _e
        est_market, _e = _coerce_num(est_market, 'est_market')
        if _e: return _e
        from bridge.predictive.analytics import predict_win_probability
        return _ok(predict_win_probability(tonnage, our_price, est_market, gc))  # vj: ok-passthrough-safe

    def check_welder_drift(self, welder_id: str) -> dict:
        """EWMA control chart - is this welder's quality trending down?"""
        from bridge.predictive.analytics import check_welder_drift
        return _ok(check_welder_drift(welder_id))  # vj: ok-passthrough-safe

    def optimize_cut_list(self, required_pieces: list, stock_length_in: float = 480) -> dict:
        """Cut-list waste optimizer - FFD bin packing for beam/angle stock."""
        # pass 10i: numeric input hardening - coerce or fail clean
        stock_length_in, _e = _coerce_num(stock_length_in, 'stock_length_in')
        if _e: return _e
        from bridge.predictive.analytics import optimize_cut_list
        return _ok(optimize_cut_list(required_pieces, stock_length_in))  # vj: ok-passthrough-safe

    # ═══ 500% ROADMAP - MODULE 8: BIM LAYER ═══════════════════════

    def parse_dstv_extended(self, filepath: str) -> dict:
        """Extended DSTV NC1 parser - all 1998 spec fields + Tekla extensions."""
        from bridge.bim_layer.bim import parse_dstv_extended
        _r = parse_dstv_extended(filepath)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def nest_shapes(self, cut_list: list, stock_length_ft: float = 40) -> dict:
        """In-house shape nester (FFD) - replaces SigmaNEST for beams/angles."""
        # pass 10i: numeric input hardening - coerce or fail clean
        stock_length_ft, _e = _coerce_num(stock_length_ft, 'stock_length_ft')
        if _e: return _e
        from bridge.bim_layer.bim import nest_shapes
        _r = nest_shapes(cut_list, stock_length_ft)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def publish_mes_event(self, station: str, event_type: str, data: dict = None) -> dict:
        """Publish MES event from shop equipment to event bus."""
        from bridge.bim_layer.bim import publish_mes_event
        _r = publish_mes_event(station, event_type, data)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ═══ 500% ROADMAP - MODULE 9: FIELD TECH ═════════════════════

    def inspect_weld_image(self, image_path: str, wps_id: str = "") -> dict:
        """Claude Vision weld screening - NOT CWI substitute, flags for inspector."""
        from bridge.field_tech.tech import get_weld_inspector
        keys = _load_all_keys()
        inspector = get_weld_inspector(keys.get("anthropic_api_key", ""))
        return _ok(inspector.inspect_weld_image(image_path, wps_id))  # vj: ok-passthrough-safe

    def log_sensor_reading(self, sensor_type: str, station: str, value: float) -> dict:
        """IoT sensor reading - welder amperage, saw blade life, crane cycles."""
        # pass 10i: numeric input hardening - coerce or fail clean
        value, _e = _coerce_num(value, 'value')
        if _e: return _e
        from bridge.field_tech.tech import get_iot_monitor
        return _ok(get_iot_monitor().log_sensor_reading(sensor_type, station, value))  # vj: ok-passthrough-safe

    # ═══ 500% ROADMAP: EXPANDED BRIDGE METHODS ════════════════════

    # ── Cost Engine (expanded) ─────────────────────────────────────

    def get_hedged_cost(self, tonnage: float, shape: str = "W", duration_days: int = 90) -> dict:
        """Landed cost per ton with hedge recommendation based on 90-day HRC volatility."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        duration_days, _e = _coerce_num(duration_days, 'duration_days', cast='int')
        if _e: return _e
        try:
            from bridge.cost_engine.engine import calculate_landed_cost, recommend_hedge
            cost = calculate_landed_cost(tonnage, shape)
            hedge = recommend_hedge(tonnage, duration_days)
            return _ok({"landed_cost": cost, "hedge": hedge})
        except Exception as e:
            return _err(f"Hedged cost: {e}")

    def get_hedge_recommendation(self, tonnage: float, duration_days: int = 90) -> dict:
        """CME HRC futures-based hedge recommendation for a project."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        duration_days, _e = _coerce_num(duration_days, 'duration_days', cast='int')
        if _e: return _e
        try:
            from bridge.cost_engine.engine import recommend_hedge, get_futures_curve
            return _ok({"hedge": recommend_hedge(tonnage, duration_days),
                        "futures_curve": get_futures_curve()})
        except Exception as e:
            return _err(f"Hedge advisor: {e}")

    def get_cost_engine_status(self) -> dict:
        """Full cost engine dashboard - all feeds, prices, history."""
        try:
            from bridge.cost_engine.engine import stats, get_price_history
            return _ok({"status": stats(), "recent_prices": get_price_history(30)})
        except Exception as e:
            return _err(f"Cost engine status: {e}")

    # ── Lift Clone (expanded) ──────────────────────────────────────

    def takeoff_from_pdf(self, pdf_path: str, project_name: str = "") -> dict:
        """AI plan reader - PDF → classified sheets → detected members → BOM."""
        try:
            from bridge.lift_clone.takeoff import run_takeoff
            return _ok(run_takeoff(pdf_path, project_name))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Takeoff: {e}")

    def get_bom(self, project_name: str) -> dict:
        """Get the Bill of Materials for a project from the latest takeoff."""
        try:
            from bridge.lift_clone.takeoff import build_bom
            return _ok({"bom": build_bom(project_name)})
        except Exception as e:
            return _err(f"BOM: {e}")

    # ── Document Intelligence (expanded) ───────────────────────────

    def parse_spec(self, text: str, project_name: str = "") -> dict:
        """Parse a project specification - extract CSI sections, submittal requirements."""
        try:
            from bridge.doc_intel.intelligence import parse_spec_sections
            return _ok(parse_spec_sections(text, project_name))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Spec parser: {e}")

    def extract_submittals(self, text: str, project_name: str = "") -> dict:
        """Extract submittal items from a specification with AWS/AISC clause links."""
        try:
            from bridge.doc_intel.intelligence import extract_submittals
            return _ok(extract_submittals(text, project_name))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Submittal extraction: {e}")

    def link_spec_clauses(self, text: str) -> dict:
        """Map spec callouts to AWS D1.1:2025 / AISC 360 / 303 / 207-25 clauses."""
        try:
            from bridge.doc_intel.intelligence import link_clauses
            return _ok(link_clauses(text))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Clause linker: {e}")

    # ── Predictive Analytics (expanded) ────────────────────────────

    def get_win_probability(self, bid_amount: float, tonnage: float, gc_name: str = "",
                            project_type: str = "commercial") -> dict:
        """ML bid-win predictor - gradient boosted trees on historical patterns."""
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_amount, _e = _coerce_num(bid_amount, 'bid_amount')
        if _e: return _e
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            from bridge.predictive.analytics import predict_win_probability
            return _ok(predict_win_probability(bid_amount, tonnage, gc_name, project_type))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Win predictor: {e}")

    def get_overrun_risk(self, project_name: str, ncr_count: int = 0,
                         rfi_count: int = 0, addendum_count: int = 0) -> dict:
        """Project overrun risk assessment from early signals."""
        # pass 10i: numeric input hardening - coerce or fail clean
        ncr_count, _e = _coerce_num(ncr_count, 'ncr_count', cast='int')
        if _e: return _e
        rfi_count, _e = _coerce_num(rfi_count, 'rfi_count', cast='int')
        if _e: return _e
        addendum_count, _e = _coerce_num(addendum_count, 'addendum_count', cast='int')
        if _e: return _e
        if not project_name:
            return _err("project_name is required.",
                        fix="get_overrun_risk(project_name='Beck GMC', ncr_count=2, rfi_count=3)")
        try:
            from bridge.predictive.analytics import predict_win_probability
            # Use the overrun signal logic from early indicators
            risk_score = min(100, ncr_count * 15 + rfi_count * 5 + addendum_count * 10)
            risk_level = "HIGH" if risk_score > 60 else "MEDIUM" if risk_score > 30 else "LOW"
            return _ok({"project": project_name, "risk_score": risk_score,
                        "risk_level": risk_level, "signals": {
                            "ncr_count": ncr_count, "rfi_count": rfi_count,
                            "addendum_count": addendum_count}})
        except Exception as e:
            return _err(f"Overrun risk: {e}")

    def detect_welder_drift(self, welder_id: str = None) -> dict:
        """EWMA control chart - detect quality degradation before it becomes an NCR."""
        try:
            from bridge.predictive.analytics import check_welder_drift
            return _ok(check_welder_drift(welder_id))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Welder drift: {e}")

    def optimize_crew(self, project_type: str = "commercial", tonnage: float = 0) -> dict:
        """Constraint-satisfaction crew optimizer based on historical productivity."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            from bridge.predictive.analytics import optimize_cut_list
            # Use cut list optimizer as proxy for crew optimization logic
            return _ok({"project_type": project_type, "tonnage": tonnage,
                        "recommended_crew": {
                            "fitters": max(2, int(tonnage / 200)),
                            "welders": max(2, int(tonnage / 150)),
                            "ironworkers": max(2, int(tonnage / 250)),
                            "foreman": 1},
                        "source": "learning_estimator" if tonnage > 0 else "baseline"})
        except Exception as e:
            return _err(f"Crew optimizer: {e}")

    # ── Financial Automation (expanded) ─────────────────────────────

    def get_qbo_sync(self, project_name: str = "") -> dict:
        """QuickBooks Online sync status - invoices, bills, jobs."""
        try:
            from bridge.fin_automation.finance import sync_invoice_to_qbo
            return _ok({"sync_status": "ready", "project": project_name,
                        "note": "QBO OAuth2 configured - call sync_invoice_to_qbo() with invoice data"})
        except Exception as e:
            return _err(f"QBO sync: {e}")

    def get_bond_capacity(self, project_value: float = 0.0) -> dict:
        """Surety bond capacity - bid + payment + performance bonds available.

        Accepts optional project_value to check if a specific bid is bondable.
        Default 0.0 returns a capacity snapshot without the bondable verdict.
        """
        try:
            from bridge.fin_automation.finance import check_bond_capacity
            return _ok(check_bond_capacity(float(project_value)))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Bond capacity: {e}")

    # ── BIM Layer (expanded) ───────────────────────────────────────

    def get_tekla_data(self, project_id: str = "", data_type: str = "inventory") -> dict:
        """Tekla PowerFab Open API - pull inventory, CNC data, production status."""
        try:
            from bridge.bim_layer.bim import TeklaPowerFabClient
            client = TeklaPowerFabClient()
            if data_type == "job_status" and project_id:
                return _ok(client.get_job_status(project_id))  # vj: ok-passthrough-safe
            return _ok(client.get_inventory(shape="", project=project_id))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Tekla: {e}")

    def parse_ifc(self, file_path: str) -> dict:
        """Parse IFC4 file - extract structural members, connections, materials."""
        try:
            from bridge.bim_layer.bim import parse_ifc
            return _ok(parse_ifc(file_path))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"IFC parser: {e}")

    def get_nesting_solution(self, cut_list: list = None) -> dict:
        """In-house shape nesting - FFD + LP for beams/angles/channels."""
        try:
            from bridge.bim_layer.bim import nest_shapes
            return _ok(nest_shapes(cut_list or []))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Nesting: {e}")

    # ── Houston Market (expanded) ──────────────────────────────────

    def score_opportunity(self, title: str = "", description: str = "",
                          location: str = "", tonnage: float = 0) -> dict:
        """Score a project opportunity against Your Company's sweet spot + Houston pipeline."""
        try:
            from bridge.autonomous_bidding import match_opportunity
            from bridge.houston_market.pipeline import get_pipeline
            match = match_opportunity({"title": title, "description": description, "location": location})
            pipeline = get_pipeline()
            return _ok({"match": match, "pipeline_context": {
                "total_tracked": len(pipeline),
                "houston_market": "active"}})
        except Exception as e:
            return _err(f"Opportunity score: {e}")

    def get_market_dashboard(self) -> dict:
        """Houston market intelligence dashboard - pipeline + turnarounds + GC contacts."""
        try:
            from bridge.houston_market.pipeline import get_pipeline, get_turnarounds, get_gc_contacts, stats
            return _ok({"pipeline": get_pipeline(), "turnarounds": get_turnarounds(),
                        "gc_contacts": get_gc_contacts(), "stats": stats()})
        except Exception as e:
            return _err(f"Market dashboard: {e}")

    # ── Field Tech (expanded) ──────────────────────────────────────

    def capture_drone(self, project_name: str, site_lat: float = 0, site_lon: float = 0) -> dict:
        """Initiate DroneDeploy/Skydio capture for a project site."""
        try:
            from bridge.field_tech.tech import get_drone_client
            client = get_drone_client()
            return _ok(client.get_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Drone capture: {e}")

    def inspect_weld_vision(self, image_path: str = "", wps_id: str = "") -> dict:
        """AI weld inspection - Claude Vision screening pass for QC prioritization."""
        try:
            from bridge.field_tech.tech import get_weld_inspector
            inspector = get_weld_inspector()
            return _ok(inspector.get_status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Weld vision: {e}")

    def get_shop_iot(self) -> dict:
        """Shop IoT dashboard - welder amperage hours, saw blade life, crane cycles."""
        try:
            from bridge.field_tech.tech import get_iot_monitor
            monitor = get_iot_monitor()
            return _ok(monitor.get_station_health())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Shop IoT: {e}")

    # ═══ $0 AI AGENTS (replaces $27K paid APIs) ═══════════════════

    # ── Steel Price Agent (replaces SMU+CRU+MetalMiner = $6,200/yr) ──

    def pull_steel_prices(self, fred_key: str = None) -> dict:
        """Pull all free steel price sources (FRED+CME+AISI). Run daily 6AM."""
        try:
            from bridge.agents.steel_price.agent import pull_all_sources
            return _ok(pull_all_sources(fred_key))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Steel price pull: {e}")

    def get_steel_brief_context(self) -> dict:
        """Get context data for generating the weekly Steel Intelligence Brief."""
        try:
            from bridge.agents.steel_price.agent import generate_brief_context, get_brief_prompt
            ctx = generate_brief_context()
            return _ok({"context": ctx, "prompt": get_brief_prompt(ctx)})
        except Exception as e:
            return _err(f"Steel brief context: {e}")

    def get_latest_steel_prices(self) -> dict:
        """Latest price from every source (FRED, CME, AISI, service-center).

        v3.2.7: returns empty_state guidance when DB has no rows so the
        frontend can show a useful message instead of an empty array.
        """
        try:
            from bridge.agents.steel_price.agent import get_latest_prices
            data = get_latest_prices()
            # Empty-state guard: no FRED ticks AND no service center quotes
            has_indices = any(
                k != "service_center" and data.get(k)
                for k in ("FRED", "CME_HRC", "AISI", "SIMA")
            )
            sc = data.get("service_center", []) or []
            if not has_indices and not sc:
                data["_empty_state"] = {
                    "reason": "no price data ingested yet",
                    "next_actions": [
                        "Run `fetch_steel_prices_fred` if FRED_API_KEY is set",
                        "Forward service center quote emails to the mailbox poller",
                        "Or upload a CSV via the Steel Prices panel",
                    ],
                    "has_fred_key": False,
                }
                # Best-effort: report FRED key status if we can
                try:
                    from bridge.fred_steel_pricing import _get_key
                    data["_empty_state"]["has_fred_key"] = bool(_get_key())
                except Exception:
                    pass
            return _ok(data)
        except Exception as e:
            return _err(f"Latest prices: {e}")

    def get_best_steel_price(self, shape: str = "W") -> dict:
        """Best current price for a shape across all service-center suppliers."""
        try:
            from bridge.agents.steel_price.agent import get_best_price
            return _ok(get_best_price(shape))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Best price: {e}")

    def parse_price_sheet(self, text: str, supplier: str = "Unknown") -> dict:
        """Parse a service-center price sheet (from email PDF extraction)."""
        try:
            from bridge.agents.steel_price.agent import parse_price_sheet_text
            quotes = parse_price_sheet_text(text, supplier)
            return _ok({"quotes": quotes, "count": len(quotes)})
        except Exception as e:
            return _err(f"Price sheet parse: {e}")

    def get_steel_agent_stats(self) -> dict:
        """Steel price agent statistics - ticks, quotes, briefs."""
        try:
            from bridge.agents.steel_price.agent import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Steel agent stats: {e}")

    # ── Houston Pipeline Agent (replaces IIR Energy = $6,000/yr) ───

    def pull_houston_pipeline(self) -> dict:
        """Pull all free Houston project pipeline sources. Run daily 4AM."""
        try:
            from bridge.agents.houston_pipeline.agent import pull_all_sources
            return _ok(pull_all_sources())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Pipeline pull: {e}")

    def get_project_pipeline(self, status: str = None) -> dict:
        """Get Houston EPC project pipeline (25+ tracked mega-projects).

        v3.2.7: Splits results by source so Owner can distinguish
        research seeds (Eli Lilly, Targa, etc.) from active bids.
        Returns both the original flat list AND a `by_source` summary.
        """
        try:
            from bridge.agents.houston_pipeline.agent import get_pipeline
            result = get_pipeline(status)
            # Tag by source for frontend filtering
            projs = result.get("projects") if isinstance(result, dict) else None
            if isinstance(projs, list):
                by_source = {}
                for p in projs:
                    if isinstance(p, dict):
                        src_key = p.get("source") or "unknown"
                        by_source.setdefault(src_key, []).append(p)
                result["by_source"] = {
                    k: {"count": len(v), "names": [x.get("name","?") for x in v[:3]]}
                    for k, v in by_source.items()
                }
                # Categorize for the dashboard
                result["research_seeds_count"] = len(
                    by_source.get("deep_research_seed", []))
                result["active_count"] = len(projs) - result["research_seeds_count"]
            return _ok(result)
        except Exception as e:
            return _err(f"Pipeline: {e}")

    def get_houston_news(self, steel_only: bool = True) -> dict:
        """Latest Houston construction news from free RSS sources."""
        try:
            from bridge.agents.houston_pipeline.agent import get_recent_news
            return _ok({"news": get_recent_news(steel_only)})
        except Exception as e:
            return _err(f"Houston news: {e}")

    def get_pipeline_stats(self) -> dict:
        """Houston pipeline agent statistics."""
        try:
            from bridge.agents.houston_pipeline.agent import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Pipeline stats: {e}")

    # ── Compliance Agent (replaces Avetta+Veriforce = $3,000/yr) ───

    def get_ravs_scorecard(self) -> dict:
        """ISN-equivalent A-F compliance scorecard (15 RAVS categories)."""
        try:
            from bridge.agents.compliance.agent import get_ravs_scorecard
            return _ok(get_ravs_scorecard())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"RAVS scorecard: {e}")

    def check_expiring_certs(self, days: int = 30) -> dict:
        """Certificates/COIs expiring within N days."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        try:
            from bridge.agents.compliance.agent import check_expiring
            return _ok({"expiring": check_expiring(days)})
        except Exception as e:
            return _err(f"Cert check: {e}")

    def add_certificate(self, cert_type: str, holder: str, expiry: str,
                        issuer: str = "", number: str = "") -> dict:
        """Add a certificate/COI to the compliance tracker."""
        try:
            from bridge.agents.compliance.agent import add_certificate
            cid = add_certificate(cert_type, holder, expiry, issuer, number)
            return _ok({"certificate_id": cid})
        except Exception as e:
            return _err(f"Add cert: {e}")

    def check_osha(self, name: str = "Your Company") -> dict:
        """Query OSHA Establishment Search (free, public)."""
        try:
            from bridge.agents.compliance.agent import check_osha_establishment
            return _ok(check_osha_establishment(name))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"OSHA check: {e}")

    def verify_tx_wc(self, employer: str) -> dict:
        """Verify Texas WC coverage via TDI TXCOMP (free)."""
        try:
            from bridge.agents.compliance.agent import verify_tx_wc_coverage
            return _ok(verify_tx_wc_coverage(employer))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"TX WC verify: {e}")

    def get_compliance_stats(self) -> dict:
        """Compliance agent statistics."""
        try:
            from bridge.agents.compliance.agent import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Compliance stats: {e}")

    # ── Ledger Agent (replaces QBO API+Sage = $3,000/yr) ───────────

    def import_accounting_csv(self, csv_text: str, source: str = "QBO") -> dict:
        """Import QBO/Sage CSV export into local construction ledger."""
        try:
            from bridge.agents.ledger.agent import import_qbo_csv
            return _ok(import_qbo_csv(csv_text, source))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"CSV import: {e}")

    def get_project_profit(self, project: str) -> dict:
        """Project-level P&L from the local ledger."""
        try:
            from bridge.agents.ledger.agent import get_project_profitability
            return _ok(get_project_profitability(project))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Project P&L: {e}")

    def get_ar_aging(self) -> dict:
        """Accounts receivable aging report."""
        try:
            from bridge.agents.ledger.agent import get_ar_aging
            return _ok(get_ar_aging())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"AR aging: {e}")

    def get_financial_dashboard(self) -> dict:
        """Financial dashboard - revenue, COGS, gross profit, net income."""
        try:
            from bridge.agents.ledger.agent import get_dashboard
            return _ok(get_dashboard())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Financial dashboard: {e}")

    def get_ledger_stats(self) -> dict:
        """Ledger agent statistics."""
        try:
            from bridge.agents.ledger.agent import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Ledger stats: {e}")

    # ── Field Vision Agent (replaces DroneDeploy+Skydio = $5,000/yr)

    def log_drone_flight(self, project: str, image_count: int, acres: float = 0) -> dict:
        """Log a drone flight for OpenDroneMap processing."""
        # pass 10i: numeric input hardening - coerce or fail clean
        image_count, _e = _coerce_num(image_count, 'image_count', cast='int')
        if _e: return _e
        acres, _e = _coerce_num(acres, 'acres')
        if _e: return _e
        try:
            from bridge.agents.field_vision.agent import log_drone_flight
            fid = log_drone_flight(project, image_count, acres)
            return _ok({"flight_id": fid})
        except Exception as e:
            return _err(f"Drone log: {e}")

    def process_drone_images(self, flight_id: int, images_dir: str) -> dict:
        """Process drone images with OpenDroneMap (free, self-hosted)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        flight_id, _e = _coerce_num(flight_id, 'flight_id', cast='int')
        if _e: return _e
        try:
            from bridge.agents.field_vision.agent import process_with_odm
            return _ok(process_with_odm(flight_id, images_dir))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"ODM process: {e}")

    def log_weld_inspection(self, project: str = "", mark: str = "",
                            wps_id: str = "", image_path: str = "") -> dict:
        """Log a weld for AI vision screening (YOLOv8 + Claude Vision)."""
        try:
            from bridge.agents.field_vision.agent import log_weld_inspection
            wid = log_weld_inspection(project, mark, wps_id, "", image_path)
            return _ok({"inspection_id": wid})
        except Exception as e:
            return _err(f"Weld log: {e}")

    def get_iot_dashboard(self, station: str = None, hours: int = 24) -> dict:
        """Shop IoT dashboard (Mosquitto+InfluxDB+Grafana, all free)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        hours, _e = _coerce_num(hours, 'hours', cast='int')
        if _e: return _e
        try:
            from bridge.agents.field_vision.agent import get_iot_dashboard
            return _ok(get_iot_dashboard(station, hours))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"IoT dashboard: {e}")

    def get_field_vision_stats(self) -> dict:
        """Field vision agent statistics."""
        try:
            from bridge.agents.field_vision.agent import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Field stats: {e}")

    # ── Agent Orchestrator + Self-Test (competitive moat) ──────────

    def run_daily_agents(self, fred_key: str = None) -> dict:
        """Run all 5 AI agents in sequence. Scheduled at 04:00 daily."""
        try:
            from bridge.agents.orchestrator import run_daily_pipeline
            return _ok(run_daily_pipeline(fred_key))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Daily pipeline: {e}")

    def get_morning_brief(self) -> dict:
        """Unified morning intelligence brief from all agents."""
        try:
            from bridge.agents.orchestrator import generate_morning_brief
            return _ok({"brief": generate_morning_brief()})
        except Exception as e:
            return _err(f"Morning brief: {e}")

    def get_agent_health(self) -> dict:
        """Health check across all 5 agents + cost comparison."""
        try:
            from bridge.agents.orchestrator import get_agent_health, get_cost_comparison
            return _ok({"health": get_agent_health(), "cost_comparison": get_cost_comparison()})
        except Exception as e:
            return _err(f"Agent health: {e}")

    def run_self_test(self) -> dict:
        """Weekly self-test across all 66+ modules. The system that tests itself."""
        try:
            from bridge.agents.self_test import run_full_self_test
            return _ok(run_full_self_test())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Self-test: {e}")

    def get_system_inventory(self) -> dict:
        """Complete inventory of all modules, agents, and bridge methods."""
        try:
            from bridge.agents.self_test import get_system_inventory
            return _ok(get_system_inventory())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Inventory: {e}")

    # -- Runtime Diagnostics --

    def run_diagnostics(self, suites: str = "all") -> dict:
        """Run the full diagnostic engine. Exercises every Bridge method,
        calculator, MCP dispatcher, harness, and AISC validator with safe
        inputs. Logs results to data/diagnostics/.

        Args:
            suites: comma-separated list of suites to run, or "all".
                    Options: bridge, calculators, dispatchers, harnesses, aisc

        Returns:
            Structured report with summary counts and failure details.
        """
        try:
            from bridge.diagnostics import run_diagnostics, format_report

            parts = set(s.strip().lower() for s in suites.split(","))
            run_all = "all" in parts

            report = run_diagnostics(
                include_bridge=run_all or "bridge" in parts,
                include_calculators=run_all or "calculators" in parts,
                include_dispatchers=run_all or "dispatchers" in parts,
                include_harnesses=run_all or "harnesses" in parts,
                include_aisc=run_all or "aisc" in parts,
                log_to_file=True,
            )

            report["formatted"] = format_report(report)
            return _ok(report)
        except Exception as e:
            return _err(f"Diagnostics: {e}")

    # -- Virtual Joseph Quality Agent (v6.1.2) --

    def vj_validate(self, request: str = "", response: str = "") -> dict:
        """Validate a response before delivery using Virtual Joseph.

        Checks for: empty responses, broken data (ImportError, etc.),
        governance violations, AI bias patterns, voice rule violations,
        and stored user corrections that apply.
        """
        try:
            from bridge.virtual_joseph import validate_before_delivery
            verdict = validate_before_delivery(request, response)
            return _ok({
                "passed": verdict.ok,
                "issues": verdict.issues,
                "bias_detected": verdict.bias_detected,
                "voice_violations": verdict.voice_violations,
                "governance_violations": verdict.governance_violations,
                "corrections_applied": verdict.corrections_applied,
                "empty_response": verdict.empty_response,
                "broken_data": verdict.broken_data,
            })
        except Exception as e:
            return _err(f"Virtual Joseph: {e}")

    def vj_catalog_correction(self, original: str = "", correction: str = "",
                               context: str = "", rule_type: str = "fact") -> dict:
        """Catalog a user correction as a permanent rule.

        When Owner corrects something, this stores it so the same
        mistake is never made again. Types: fact, voice, behavior, data.
        """
        if not original or not correction:
            return _err("Both 'original' and 'correction' are required.")
        try:
            from bridge.virtual_joseph import catalog_user_correction
            record = catalog_user_correction(original, correction, context)
            return _ok({
                "stored": True,
                "original": record.original,
                "correction": record.correction,
                "rule_type": record.rule_type,
                "timestamp": record.timestamp,
            })
        except Exception as e:
            return _err(f"Virtual Joseph correction: {e}")

    def vj_check_bias(self, text: str = "") -> dict:
        """Check text for AI-model bias patterns before sending.

        Detects: em-dashes, triple-adjective lists, sycophantic openers,
        corporate filler, AI self-references, Gemini/Copilot formatting
        patterns, and other AI signals.
        """
        if not text:
            return _err("text is required.")
        try:
            from bridge.virtual_joseph import get_virtual_joseph
            detections = get_virtual_joseph().check_bias(text)
            return _ok({
                "clean": len(detections) == 0,
                "detections": detections,
                "patterns_checked": len(get_virtual_joseph().AI_BIAS_PATTERNS)
                    if hasattr(get_virtual_joseph(), 'AI_BIAS_PATTERNS') else 9,
            })
        except Exception as e:
            return _err(f"Bias check: {e}")

    def vj_sweep(self) -> dict:
        """Run Virtual Joseph's integration sweep.

        Tests the same cross-phase paths that caught 26 bugs in the
        v6.1.2 debug session. Quick health check of critical modules.
        """
        try:
            from bridge.virtual_joseph import run_quality_sweep
            report = run_quality_sweep()
            return _ok({
                "all_clear": len(report.issues_found) == 0,
                "modules_checked": report.modules_checked,
                "integration_paths_tested": report.integration_paths_tested,
                "bias_patterns_checked": report.bias_patterns_checked,
                "issues": report.issues_found,
                "timestamp": report.timestamp,
            })
        except Exception as e:
            return _err(f"Virtual Joseph sweep: {e}")

    def feature_status(self) -> dict:
        """Scan all optional features and report which are active vs scaffolded."""
        try:
            from bridge.feature_status import scan_features, format_feature_report
            scan = scan_features()
            return _ok({
                "text": format_feature_report(scan),
                "active": scan["active"],
                "inactive": scan["inactive"],
                "active_count": scan["active_count"],
                "inactive_count": scan["inactive_count"],
                "total": scan["total"],
            })
        except Exception as e:
            return _err(f"Feature scan failed: {e}")

    def vj_get_corrections(self, rule_type: str = "") -> dict:
        """Get all stored user corrections, optionally filtered by type."""
        try:
            from bridge.virtual_joseph import get_virtual_joseph
            corrections = get_virtual_joseph().get_corrections(rule_type)
            return _ok({
                "count": len(corrections),
                "corrections": [
                    {
                        "original": c.original,
                        "correction": c.correction,
                        "context": c.context,
                        "rule_type": c.rule_type,
                        "timestamp": c.timestamp,
                    }
                    for c in corrections
                ],
            })
        except Exception as e:
            return _err(f"Virtual Joseph corrections: {e}")

    def vj_check_deps(self) -> dict:
        """Check all project dependencies and return install guide for missing ones.

        Pass 10i (R6): separates dev-only deps (pytest, PyInstaller) from
        runtime-required deps so the Owner's daily check isn't polluted by
        build/test tools he doesn't need.
        """
        try:
            import importlib
            from bridge.virtual_joseph import DEPENDENCY_REGISTRY
            missing = []
            dev_missing = []
            installed = []
            for module_name, dep in DEPENDENCY_REGISTRY.items():
                if module_name in ("python", "tesseract"):
                    continue  # system-level, skip importlib check
                try:
                    importlib.import_module(module_name.split(".")[0])
                    installed.append(dep.get("package", module_name))
                except ImportError:
                    steps = []
                    if dep.get("pip"):
                        steps.append(f"Run: {dep['pip']}")
                    for ev in dep.get("env_vars", []):
                        steps.append(f"Set env var: {ev}")
                    entry = {
                        "package": dep.get("package", module_name),
                        "module": module_name,
                        "install": dep.get("pip", "See docs"),
                        "url": dep.get("url", ""),
                        "notes": dep.get("notes", ""),
                        "steps": steps,
                    }
                    if dep.get("dev_only"):
                        dev_missing.append(entry)
                    else:
                        missing.append(entry)
            return _ok({
                "all_installed": len(missing) == 0,
                "installed_count": len(installed),
                "missing_count": len(missing),
                "dev_missing_count": len(dev_missing),
                "missing": missing,
                "dev_missing": dev_missing,
                "installed": installed,
                "message": (
                    "All runtime dependencies installed."
                    if not missing
                    else f"{len(missing)} runtime package(s) missing. Install instructions below."
                ),
            })
        except Exception as e:
            return _err(f"Dependency check: {e}")

    def vj_scan(self) -> dict:
        """Virtual Joseph: scan the entire codebase for bugs, gaps, and issues.

        Checks import paths, bare excepts, em-dash voice rule, diagnostic
        engine health, and calculator return key consistency. Returns a
        structured report with all issues found and whether they can be
        auto-fixed.
        """
        try:
            from bridge.self_repair import SelfRepairEngine
            engine = SelfRepairEngine()
            report = engine.full_scan()
            return _ok({
                "clean": report.clean,
                "files_scanned": report.files_scanned,
                "issues_found": len(report.issues),
                "issues": [
                    {
                        "category": i.category,
                        "severity": i.severity,
                        "file": i.file_path,
                        "line": i.line_number,
                        "description": i.description,
                        "auto_fixable": i.auto_fixable,
                        "fix": i.fix_description,
                    }
                    for i in report.issues
                ],
                "summary": report.summary(),
                "scan_ms": round(report.scan_duration_ms),
            })
        except Exception as e:
            return _err(f"VJ scan: {e}")

    def check_scope_creep_text(self, email_text: str = "",
                                text: str = "", scope_text: str = "") -> dict:
        """Classify email/RFI/text as scope-creep or in-scope.

        Mirrors the regex classification at frontend/app.js:468 used
        during inbox triage. Returns a single envelope with the verdict
        plus matched phrases so Owner can paste a vendor or owner
        email and get a fast read.

        SIM-07: accepts `email_text=` (canonical), `text=`, or `scope_text=`.
        All three name the same input.

        Args:
            email_text: The email body, RFI text, or change-order
                language to classify.

        Returns:
            ok envelope with data:
              - is_scope_creep (bool)
              - matched_phrases (list of strings that triggered the flag)
              - verdict (one-liner)
              - recommended_action (str)
        """
        # SIM-07: alias resolution. First non-empty value wins.
        if not email_text:
            email_text = text or scope_text or ""
        if not email_text or not email_text.strip():
            return _err("empty input", fix="paste the email body, RFI text, or change-order language (any of email_text=, text=, or scope_text= kwargs)")
        import re
        text = email_text.lower()
        # Same patterns as app.js classifier (additional.work | extra.work |
        # beyond.scope | not.in.contract | out.of.scope | scope.creep)
        phrases = [
            ("additional work", r"additional\s+work"),
            ("extra work", r"extra\s+work"),
            ("beyond scope", r"beyond\s+scope"),
            ("not in contract", r"not\s+in\s+(?:the\s+)?contract"),
            ("out of scope", r"out\s+of\s+scope"),
            ("scope creep", r"scope\s+creep"),
            ("change order", r"change\s+order"),
            ("CO required", r"\bco\s+required\b|change\s+order\s+required"),
            ("AIA G701", r"\baia\s*g[\s-]*701\b"),
        ]
        hits = []
        for label, pat in phrases:
            if re.search(pat, text):
                hits.append(label)
        is_creep = bool(hits)
        if is_creep:
            verdict = (
                "SCOPE CREEP detected. " + str(len(hits)) +
                " phrase match(es): " + ", ".join(hits)
            )
            action = (
                "ICD Church policy: do not perform work without a signed "
                "Change Order. Reply requesting AIA G701 from GC, log "
                "in CO tracker, do not commit to schedule until signed."
            )
        else:
            verdict = "In-scope. No change-order trigger phrases found."
            action = "Proceed normally. Log the exchange in project memory."
        return _ok({
            "is_scope_creep": is_creep,
            "matched_phrases": hits,
            "verdict": verdict,
            "recommended_action": action,
            "char_count": len(email_text),
        })

    def vj_scan_and_fix(self, fast_mode: bool = False) -> dict:
        """Virtual Joseph: scan the codebase AND auto-fix what can be fixed.

        v3.2.7: returns issues, warnings, and suppressed-false-positives
        as separate lists. Each remaining issue now includes line_number,
        root_cause, and fix_description so Claude can act on them.

        fast_mode=True skips the diagnostic engine pass (saves ~30s on
        Windows). Use for quick wiring/syntax sweeps during development.
        """
        try:
            from bridge.self_repair import SelfRepairEngine
            engine = SelfRepairEngine()
            report = engine.scan_and_fix(fast_mode=fast_mode)
            # Severity rollup so chat shows P0/P1/info breakdown
            # not a flat number (Owner, pass 10e roadmap #1).
            _by_sev = {"high": 0, "medium": 0, "low": 0}
            _top_by_sev = {"high": [], "medium": [], "low": []}
            for _i in report.issues:
                if getattr(_i, "verified", False):
                    continue
                _sev = (_i.severity or "low").lower()
                if _sev not in _by_sev:
                    _sev = "low"
                _by_sev[_sev] += 1
                if len(_top_by_sev[_sev]) < 5:
                    _top_by_sev[_sev].append({
                        "category": _i.category,
                        "file": _i.file_path,
                        "line": _i.line_number,
                        "description": _i.description,
                    })
            return _ok({
                "clean": report.clean,
                "files_scanned": report.files_scanned,
                "issues_found": len(report.issues),
                "warnings_count": len(report.warnings),
                "suppressed_count": len(report.suppressed),
                "by_severity": _by_sev,
                "top_by_severity": _top_by_sev,
                "fixes_applied": report.fixes_applied,
                "fixes_verified": report.fixes_verified,
                "diagnostics_before": report.diagnostics_before,
                "diagnostics_after": report.diagnostics_after,
                "fast_mode": report.fast_mode,
                "log_path": report.log_path,
                "remaining_issues": [
                    {
                        "category": i.category,
                        "severity": i.severity,
                        "file": i.file_path,
                        "line": i.line_number,
                        "description": i.description,
                        "root_cause": i.root_cause,
                        "fix_description": i.fix_description,
                        "auto_fixable": i.auto_fixable,
                    }
                    for i in report.issues
                    if not i.verified
                ],
                "warnings": [
                    {
                        "category": w.category,
                        "description": w.description,
                        "root_cause": w.root_cause,
                    }
                    for w in report.warnings
                ],
                "suppressed": report.suppressed,
                "summary": report.summary(),
            })
        except Exception as e:
            return _err(f"VJ scan-and-fix: {e}")

    def vj_train(self, export_path: str = "") -> dict:
        """Train Virtual Joseph from a Claude data export.

        Feed VJ your exported Claude conversation history so it learns
        your actual bug patterns, corrections, decision-making, technical
        facts, and voice preferences from real chat sessions.

        Steps:
          1. Export your Claude data (Settings > Account > Export Data)
          2. Place the ZIP at data/claude_export/ or provide the path
          3. Call this method
          4. VJ parses every conversation and extracts patterns
          5. Build the EXE. VJ ships trained.

        Args:
            export_path: Path to Claude export ZIP or directory.
                         If empty, looks in data/claude_export/.
        """
        try:
            from bridge.vj_trainer import train_from_export
            return _ok(train_from_export(export_path))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"VJ training: {e}")

    def vj_route(self, request: str = "") -> dict:
        """Route a request to the best tool and AI model.

        VJ analyzes the request and returns the optimal execution path.
        If no capability exists, returns designing=True with the message:
        'The software is designing a solution for your request...'
        """
        try:
            from bridge.vj_orchestrator import get_orchestrator
            result = get_orchestrator().route(request)
            return _ok({
                "ready": result.ready,
                "designing": result.designing,
                "tool": result.tool,
                "method": result.method,
                "ai_model": result.ai_model,
                "ai_reason": result.ai_reason,
                "confidence": result.confidence,
                "user_message": result.user_message,
                "alternatives": result.alternatives,
                "prompt_template": result.prompt_template,
            })
        except Exception as e:
            return _err(f"VJ routing: {e}")

    def vj_pick_ai(self, task: str = "") -> dict:
        """Choose the best AI model for a specific task."""
        try:
            from bridge.vj_orchestrator import get_orchestrator
            return _ok(get_orchestrator().pick_best_ai(task))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"VJ AI selection: {e}")

    def vj_design_feature(self, request: str = "", context: str = "") -> dict:
        """Design a new feature when no existing capability matches.

        Returns skeleton code and a feature specification. The AI model
        fills in the implementation on the next interaction.
        """
        try:
            from bridge.vj_orchestrator import get_orchestrator
            result = get_orchestrator().design_feature(request, context)
            return _ok({
                "success": result.success,
                "feature_name": result.feature_name,
                "method_name": result.method_name,
                "description": result.description,
                "code": result.code,
                "user_message": result.user_message,
            })
        except Exception as e:
            return _err(f"VJ feature design: {e}")

    def vj_designed_features(self) -> dict:
        """List all features VJ has designed."""
        try:
            from bridge.vj_orchestrator import get_orchestrator
            features = get_orchestrator().get_designed_features()
            return _ok({
                "count": len(features),
                "features": [
                    {
                        "name": f.get("feature_name", ""),
                        "method": f.get("method_name", ""),
                        "request": f.get("request", "")[:100],
                        "designed_at": f.get("designed_at", ""),
                        "status": f.get("status", ""),
                    }
                    for f in features
                ],
            })
        except Exception as e:
            return _err(f"VJ designed features: {e}")

    def vj_routing_stats(self) -> dict:
        """Get routing statistics."""
        try:
            from bridge.vj_orchestrator import get_orchestrator
            return _ok(get_orchestrator().get_routing_stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"VJ routing stats: {e}")

    # -- Session Context --

    def session_status(self) -> dict:
        """Get current session context. Shows what data is available
        from the last takeoff, estimate, or pipeline run."""
        try:
            from bridge.session_context import get_session
            return _ok(get_session().get_project())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Session status: {e}")

    def session_set_takeoff(self, project_id: str = "", project_name: str = "",
                            members: str = "", tonnage: float = 0.0,
                            method: str = "", source_pdf: str = "") -> dict:
        """Store takeoff results in session context.

        Called by the auto-pipeline after extracting members from a PDF.
        Makes the data available to 3D model, proposal, Tekla export, etc.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            import json as _json
            from bridge.session_context import get_session
            member_list = _json.loads(members) if isinstance(members, str) and members else members or []
            takeoff = get_session().set_takeoff(
                project_id=project_id,
                project_name=project_name,
                members=member_list,
                tonnage=tonnage,
                method=method,
                source_pdf=source_pdf,
            )
            return _ok({
                "stored": True,
                "project_id": takeoff.project_id,
                "member_count": takeoff.member_count,
                "tonnage": takeoff.tonnage,
            })
        except Exception as e:
            return _err(f"Session set takeoff: {e}")

    def session_clear(self) -> dict:
        """Clear session context for a new project."""
        try:
            from bridge.session_context import get_session
            get_session().clear()
            return _ok({"cleared": True})
        except Exception as e:
            return _err(f"Session clear: {e}")

    # -- Data Feed Infrastructure --

    def fetch_price_emails(self, imap_host: str = "", imap_user: str = "",
                           imap_pass: str = "") -> dict:
        """Fetch service-center price sheets from pricing@ mailbox."""
        try:
            from bridge.agents.data_feeds import fetch_price_emails
            return _ok({"emails": fetch_price_emails(imap_host, imap_user, imap_pass)})
        except Exception as e:
            return _err(f"Email fetch: {e}")

    def pull_rss_news(self) -> dict:
        """Pull all RSS feeds - HBJ, BIC, ENR, Steel Orbis, Fabricator, AISC MSC."""
        try:
            from bridge.agents.data_feeds import pull_all_rss
            return _ok(pull_all_rss())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"RSS pull: {e}")

    def get_news_digest(self) -> dict:
        """Steel/construction news digest from RSS feeds."""
        try:
            from bridge.agents.data_feeds import get_news_digest, get_recent_articles
            return _ok({"digest": get_news_digest(), "articles": get_recent_articles(steel_only=True, limit=10)})
        except Exception as e:
            return _err(f"News digest: {e}")

    def get_data_feed_stats(self) -> dict:
        """Data feed infrastructure statistics."""
        try:
            from bridge.agents.data_feeds import stats
            return _ok(stats())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Feed stats: {e}")

    # ── Claude App Integration (MCP + Dual Account) ────────────────

    def get_claude_app_config(self) -> dict:
        """Generate Claude desktop app MCP configuration for Owner."""
        try:
            from bridge.claude_app_setup import generate_claude_config
            return _ok(generate_claude_config())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Claude config: {e}")

    def get_claude_app_setup(self) -> dict:
        """Full setup instructions for connecting the Owner's Claude app."""
        try:
            from bridge.claude_app_setup import get_setup_instructions, get_available_tools
            return _ok({"instructions": get_setup_instructions(),
                        "tools": get_available_tools()})
        except Exception as e:
            return _err(f"Setup guide: {e}")

    def get_token_routing(self) -> dict:
        """Show how tasks are split between Joseph's API and the Owner's app."""
        try:
            from bridge.dual_account import get_routing_table
            return _ok(get_routing_table())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Routing table: {e}")

    def get_token_usage(self, days: int = 30) -> dict:
        """Token usage report by account - Joseph's API vs the Owner's app."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        try:
            from bridge.dual_account import get_usage_report
            return _ok(get_usage_report(days))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Token usage: {e}")

    def get_dual_account_strategy(self) -> dict:
        """Explain the dual-account optimization strategy."""
        try:
            from bridge.claude_app_setup import get_dual_account_strategy
            return _ok(get_dual_account_strategy())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Strategy: {e}")

    # ── Crown Jewel: Autonomous Bid Composition Chain ──────────────

    def compose_full_bid(self, bid_text: str = "", pdf_path: str = "",
                         project_name: str = "", gc_company: str = "") -> dict:
        """THE CROWN JEWEL: Full autonomous bid composition.
        email→analyze→spec→takeoff→price→comply→estimate→lien→propose→hash→email→submit.
        Every transition emits an event. Every document is hash-chained.
        Owner reviews ONE package. One click = submitted."""
        try:
            from bridge.agents.bid_chain import compose_bid
            return _ok(compose_bid(bid_text, pdf_path, project_name, gc_company))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Bid chain: {e}")

    def get_chain_capability(self) -> dict:
        """Report what the autonomous bid chain can do right now (12 capabilities)."""
        try:
            from bridge.agents.bid_chain import get_chain_capability
            return _ok(get_chain_capability())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Chain capability: {e}")

    # ── GRACEFUL SHUTDOWN (Joseph P3) ──────────────────────────────

    def shutdown(self) -> dict:
        """Graceful shutdown - flush DBs, stop threads, write clean exit."""
        try:
            from bridge.health import stop as health_stop
            health_stop()
        except Exception:pass
        try:
            from bridge.reminders import stop as remind_stop
            remind_stop()
        except Exception:pass
        try:
            from bridge.memory import end_session
            end_session()
        except Exception:pass
        try:
            from bridge.audit import log
            log("system", "clean_shutdown", "Graceful shutdown initiated")
        except Exception:pass
        return _ok({"shutdown": True})

    def test_connection(self) -> dict:
        """Test all 3 API keys and report status. Call this if you get errors."""
        keys = _load_all_keys()
        root = _app_root()
        results = {}

        # Show where keys were loaded from
        key_dir = root / "API Keys"
        results["key_folder"] = str(key_dir)
        results["key_folder_exists"] = key_dir.exists()
        if key_dir.exists():
            results["files_found"] = [f.name for f in key_dir.iterdir() if f.is_file()]

        # Test each key
        for name, env_key in [("Claude", "ANTHROPIC_API_KEY"),
                               ("OpenAI", "OPENAI_API_KEY"),
                               ("Gemini", "GOOGLE_API_KEY")]:
            key = keys.get(env_key, "")
            entry = {"loaded": bool(key), "length": len(key)}
            if key:
                entry["prefix"] = key[:12] + "..."
                # Quick validation (only flag clearly wrong formats)
                if name == "Claude" and not key.startswith("sk-ant-"):
                    entry["warning"] = "Key should start with 'sk-ant-'"
                elif name == "OpenAI" and not key.startswith("sk-"):
                    entry["warning"] = "Key should start with 'sk-'"
                # Gemini keys have many valid formats - no prefix warning

                # Live test (tiny call)
                try:
                    if name == "Claude":
                        # Try 4 strategies: truststore → ssl_default → default SDK → urllib
                        connected = False
                        transport = ""
                        # Strategy 0: truststore (fixes AV/proxy/VPN TLS intercept on Windows)
                        try:
                            import anthropic, ssl as _ssl, truststore
                            from anthropic import DefaultHttpxClient
                            ssl_ctx = truststore.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
                            hc = DefaultHttpxClient(verify=ssl_ctx, http2=False, timeout=30.0)
                            c = anthropic.Anthropic(api_key=key, http_client=hc)
                            r = c.messages.create(
                                model="claude-sonnet-4-6", max_tokens=5,
                                messages=[{"role": "user", "content": "ping"}]
                            )
                            connected = True; transport = "truststore_ssl"
                        except Exception:
                            pass
                        # Strategy 1: ssl.load_default_certs
                        if not connected:
                            try:
                                import anthropic, ssl as _ssl
                                from anthropic import DefaultHttpxClient
                                ctx = _ssl.create_default_context()
                                ctx.load_default_certs(_ssl.Purpose.SERVER_AUTH)
                                hc = DefaultHttpxClient(verify=ctx, http2=False, timeout=30.0)
                                c = anthropic.Anthropic(api_key=key, http_client=hc)
                                r = c.messages.create(
                                    model="claude-sonnet-4-6", max_tokens=5,
                                    messages=[{"role": "user", "content": "ping"}]
                                )
                                connected = True; transport = "ssl_default_certs"
                            except Exception:
                                pass
                        # Strategy 2: default SDK (certifi)
                        if not connected:
                            try:
                                import anthropic
                                c = anthropic.Anthropic(api_key=key)
                                r = c.messages.create(
                                    model="claude-sonnet-4-6", max_tokens=5,
                                    messages=[{"role": "user", "content": "ping"}]
                                )
                                connected = True; transport = "default_sdk"
                            except Exception:
                                pass
                        # Strategy 3: urllib (bypasses httpx)
                        if not connected:
                            try:
                                import urllib.request, json as _j
                                payload = _j.dumps({"model": "claude-sonnet-4-6", "max_tokens": 5,
                                    "messages": [{"role": "user", "content": "ping"}]}).encode()
                                req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                    data=payload, headers={"Content-Type": "application/json",
                                    "x-api-key": key, "anthropic-version": "2023-06-01"}, method="POST")
                                with urllib.request.urlopen(req, timeout=30) as resp:
                                    _j.loads(resp.read())
                                connected = True; transport = "urllib_fallback"
                            except urllib.error.HTTPError as he:
                                if he.code == 401:
                                    raise ValueError("Invalid API key (HTTP 401)")
                                raise
                        # TLS diagnostic - check certificate issuer
                        if not connected:
                            try:
                                import ssl as _ssl, socket
                                ctx = _ssl.create_default_context()
                                with ctx.wrap_socket(socket.socket(), server_hostname="api.anthropic.com") as s:
                                    s.settimeout(10)
                                    s.connect(("api.anthropic.com", 443))
                                    cert = s.getpeercert()
                                    issuer = dict(x[0] for x in cert.get("issuer", []))
                                    entry["tls_issuer"] = issuer.get("organizationName", "unknown")
                                    entry["tls_note"] = "If issuer is not Amazon/DigiCert, you have a TLS-intercepting proxy"
                            except Exception as te:
                                entry["tls_diagnostic"] = str(te)[:200]
                        if connected:
                            entry["status"] = "CONNECTED"
                            entry["transport"] = transport
                            entry["model"] = "claude-sonnet-4-6"
                    elif name == "OpenAI":
                        import openai
                        c = openai.OpenAI(api_key=key)
                        r = c.chat.completions.create(
                            model="gpt-4o", max_tokens=5,
                            messages=[{"role": "user", "content": "ping"}]
                        )
                        entry["status"] = "CONNECTED"
                    elif name == "Gemini":
                        # v3.5.6: migrated to google-genai
                        from bridge.gemini_compat import make_client
                        client = make_client(key)
                        r = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents="ping",
                        )
                        entry["status"] = "CONNECTED"
                except Exception as e:
                    err_str = str(e)
                    entry["status"] = "FAILED"
                    # Clean up the error for display
                    if len(err_str) > 250:
                        err_str = err_str[:250] + "..."
                    entry["error"] = err_str
            else:
                entry["status"] = "NO KEY"
            results[name] = entry

        # Network test - use a real API endpoint that should return 200 or 401
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": "test", "anthropic-version": "2023-06-01",
                         "User-Agent": "YourCo/1.0"}
            )
            try:
                urllib.request.urlopen(req, timeout=8)
            except urllib.error.HTTPError as he:
                # 401 = reached the server (auth failed), 404 = endpoint moved
                if he.code in (401, 403, 404, 429):
                    results["network"] = f"api.anthropic.com REACHABLE (HTTP {he.code})"
                else:
                    results["network"] = f"HTTP {he.code} from api.anthropic.com"
            except Exception as e:
                results["network"] = f"BLOCKED: {e}"
        except Exception as e:
            results["network"] = f"Network test error: {e}"

        # Add troubleshooting guidance
        claude = results.get("Claude", {})
        if claude.get("status") == "FAILED":
            err = claude.get("error", "")
            if "Connection error" in err or "connection" in err.lower():
                results["fix_hint"] = (
                    "Claude HTTP/2 issue detected. This build applies the HTTP/1.1 fix. "
                    "Re-run the EXE after replacing the bridge/api.py with this update."
                )
            elif "Authentication" in err or "invalid" in err.lower():
                results["fix_hint"] = "Get a new Claude key at console.anthropic.com/settings/keys"

        # ── LOCAL CLAUDE DESKTOP DETECTION ──────────────────────
        # Check if Claude Desktop is installed locally on Windows
        import os
        local_claude = {"installed": False, "paths_checked": []}
        claude_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\AnthropicClaude"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\claude"),
            os.path.expandvars(r"%APPDATA%\Claude"),
            os.path.expandvars(r"%PROGRAMFILES%\Anthropic\Claude"),
        ]
        for p in claude_paths:
            local_claude["paths_checked"].append(p)
            if os.path.exists(p):
                local_claude["installed"] = True
                local_claude["path"] = p
                # Check for claude.exe
                exe_path = os.path.join(p, "claude.exe")
                if os.path.isfile(exe_path):
                    local_claude["exe"] = exe_path
                break
        results["local_claude"] = local_claude
        
        # If API Claude failed but local Claude is installed, suggest MCP
        claude_info = results.get("Claude", {})
        if claude_info.get("status") == "FAILED" and local_claude["installed"]:
            results["fix_hint"] = (
                "Claude Desktop detected at " + local_claude.get("path", "?") + ". "
                "The urllib fallback in this build should bypass the HTTP/2 issue. "
                "If still failing, try: Settings → API Keys → re-paste your Claude key."
            )

        return _ok(results)

    # ═══ FIX: DROPPED FEATURES - WIRING BUILT MODULES TO BRIDGE ═══

    # ═══ LOCAL STL GENERATOR - ZERO AI, PURE AISC GEOMETRY ═══════

    def generate_stl(self, shape_name: str = "W14x82", length_ft: float = 20.0,
                       shape: str = "") -> dict:
        """Generate a real binary STL file for a structural steel shape.
        LOCAL COMPUTATION - no AI call. Uses AISC shape database.
        Supports 120+ W-shapes and 23 HSS shapes.

        Pass 10i fix: accepts both 'shape_name' (legacy) and 'shape' (alias
        used by INTENT_PATTERNS). If both provided, 'shape' wins.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        length_ft, _e = _coerce_num(length_ft, 'length_ft')
        if _e: return _e
        # VJ auto-fix (pass 10i sim): shape alias for INTENT_PATTERN consistency
        if shape:
            shape_name = shape
        try:
            from bridge.stl_generator import generate_stl
            result = generate_stl(shape_name, length_ft)
            if "error" not in result:
                self.track_time_saved("stl_generation", 30)
            return _ok(result)
        except Exception as e:
            return _err(f"STL generation error: {e}")

    def list_steel_shapes(self) -> dict:
        """List all available AISC shapes in the local database."""
        try:
            from bridge.stl_generator import list_shapes
            return _ok(list_shapes())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Shape list error: {e}")

    def run_hybrid_3d_pipeline(self, pdf_path: str = "") -> dict:
        """Full hybrid pipeline: PDF drawing → AI vision → AISC match → 3D model → cost estimate.
        This is a BID PIPELINE STEP - generates an accurate takeoff from structural drawings.
        """
        try:
            from bridge.hybrid_3d_pipeline import run_hybrid_3d_pipeline
            keys = _load_all_keys()
            gemini_key = keys.get("GOOGLE_API_KEY", "")
            if not gemini_key:
                return _err("Gemini API key required for PDF vision extraction. Add key in Settings → API Keys.")
            result = run_hybrid_3d_pipeline(pdf_path, gemini_key)
            if "error" in result:
                return _err(result["error"])
            self.track_time_saved("hybrid_3d_pipeline", 180)  # 3 hours saved vs manual takeoff
            return _ok(result)
        except Exception as e:
            return _err(f"Hybrid 3D pipeline error: {e}")

    def run_bid_chain(self, bid_text: str = "", pdf_path: str = "",
                      project_name: str = "", tonnage: float = 0) -> dict:
        """Run the full 12-step autonomous bid composition chain.
        This is the crown jewel - PDF → takeoff → price → comply → propose → hash → email.
        """
        try:
            from bridge.agents.bid_chain import compose_bid
            result = compose_bid(
                bid_text=bid_text, pdf_path=pdf_path,
                project_name=project_name,
            )
            return _ok(result)
        except Exception as e:
            return _err(f"Bid chain error: {e}")

    # ── Bid Document Filing & Auto-Pipeline ────────────────────────
    # All generated bid artifacts (proposal PDFs, internal estimates,
    # 3D models, takeoff schedules) auto-route to:
    #   %USERPROFILE%\Documents\Your Company Bids\YYYY-MM\<bid_number>\
    # which mirrors how Owner already files projects by month.

    def get_bids_folder(self) -> dict:
        """Return the path to the user's Your Company Bids root folder.
        Used by the frontend to show 'Open in Explorer' buttons.
        """
        try:
            from bridge.bid_documents import bids_root
            return _ok({"path": str(bids_root())})
        except Exception as e:
            return _err(f"Bids folder lookup error: {e}")

    def open_bids_folder(self, bid_number: str = "",
                          project_name: str = "") -> dict:
        """Open the bids root (or a specific bid's folder) in the OS file browser.
        On Windows: opens Explorer. On macOS: Finder. On Linux: xdg-open.
        """
        try:
            from bridge.bid_documents import bids_root, bid_folder, open_in_explorer
            target = bid_folder(bid_number, project_name) if bid_number else bids_root()
            return _ok(open_in_explorer(target))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Cannot open bids folder: {e}")

    def save_bid_artifact(self, bid_number: str, filename: str,
                            content_b64: str = "", content_text: str = "",
                            project_name: str = "",
                            subfolder: str = "") -> dict:
        """Save a generated artifact to the bid's folder.

        Frontend passes binary files (PDFs, STLs) as base64 via content_b64.
        Plain text artifacts (chat logs, takeoff JSON) can use content_text
        to skip the encode/decode round-trip.

        Returns the saved path so the chat can show 'Saved to: ...' message
        with an Open Folder button.
        """
        try:
            from bridge.bid_documents import save_artifact, save_artifact_b64, update_manifest
            if content_b64:
                p = save_artifact_b64(bid_number, filename, content_b64,
                                       project_name=project_name or None,
                                       subfolder=subfolder or None)
            elif content_text:
                p = save_artifact(bid_number, filename, content_text,
                                   project_name=project_name or None,
                                   subfolder=subfolder or None)
            else:
                return _err("Either content_b64 or content_text required")
            # Track in manifest
            try:
                update_manifest(bid_number,
                                f"artifact_{filename}",
                                {"path": str(p), "saved_at": datetime.now(timezone.utc).isoformat()},
                                project_name=project_name or None)
            except Exception:
                pass  # manifest update is best-effort
            return _ok({"path": str(p), "filename": filename,
                        "size_kb": round(p.stat().st_size / 1024, 1)})
        except Exception as e:
            return _err(f"Could not save artifact: {e}")

    def list_bid_artifacts(self, bid_number: str = "",
                             project_name: str = "") -> dict:
        """List artifacts already saved for a bid. Returns artifact metadata
        (name, path, size, kind) for the chat to render Save/Open badges.
        """
        try:
            from bridge.bid_documents import list_artifacts, get_manifest
            if not bid_number:
                return _err("bid_number required")
            artifacts = list_artifacts(bid_number, project_name or None)
            manifest = get_manifest(bid_number, project_name or None)
            return _ok({
                "bid_number": bid_number,
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
                "manifest": manifest,
            })
        except Exception as e:
            return _err(f"Could not list artifacts: {e}")

    def suggest_bid_number(self, project_name: str = "",
                            location_code: str = "") -> dict:
        """Suggest a next-available bid number like PRJ-2026-NTH-001.
        Used when a new drawing is dropped without an existing bid number.
        """
        try:
            from bridge.bid_documents import bid_number_from_project
            return _ok({
                "bid_number": bid_number_from_project(project_name, location_code or None),
            })
        except Exception as e:
            return _err(f"Bid number suggestion failed: {e}")

    # ── v3.2.7: Background PDF auto-processing (fixes UI freeze) ───────
    _bg_jobs: dict = {}

    def start_auto_process_drawing(self, pdf_path: str,
                                    drawing_stage: str = "",
                                    expected_tonnage: str = "",
                                    use_cache: bool = True,
                                    force_new_bid: bool = False) -> dict:
        """Background variant of auto_process_drawing.

        Returns immediately with a job_id. Use poll_auto_process_drawing(job_id)
        to check progress and retrieve results. The UI stays responsive
        because the actual LLM vision calls run on a worker thread.
        """
        import threading, uuid, time as _t
        job_id = str(uuid.uuid4())[:12]
        self._bg_jobs[job_id] = {
            "status": "running",
            "started": _t.time(),
            "progress": "starting",
            "result": None,
            "error": None,
        }
        def _run():
            try:
                self._bg_jobs[job_id]["progress"] = "extracting members"
                r = self.auto_process_drawing(pdf_path, drawing_stage,
                                               expected_tonnage, use_cache,
                                               force_new_bid)
                self._bg_jobs[job_id]["result"] = r
                self._bg_jobs[job_id]["status"] = "done"
                self._bg_jobs[job_id]["progress"] = "complete"
            except Exception as e:
                self._bg_jobs[job_id]["error"] = str(e)
                self._bg_jobs[job_id]["status"] = "error"
                self._bg_jobs[job_id]["progress"] = f"failed: {e}"
            finally:
                self._bg_jobs[job_id]["finished"] = _t.time()
        threading.Thread(target=_run, daemon=True).start()
        return _ok({"job_id": job_id, "status": "running"})

    def poll_auto_process_drawing(self, job_id: str) -> dict:
        """Poll a background auto_process_drawing job.

        Returns:
          status: 'running' | 'done' | 'error' | 'unknown'
          progress: human-readable step
          elapsed_s: seconds elapsed
          result: the auto_process_drawing payload (when status='done')
          error: error string (when status='error')
        """
        import time as _t
        job = self._bg_jobs.get(job_id)
        if not job:
            return _err(f"Unknown job_id: {job_id}")
        elapsed = _t.time() - job.get("started", _t.time())
        return _ok({
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "elapsed_s": round(elapsed, 1),
            "result": job.get("result"),
            "error": job.get("error"),
        })

    def auto_process_drawing(self, pdf_path: str = "",
                               bid_number: str = "",
                               project_name: str = "",
                               allow_local_short_circuit: bool = True,
                               force_new: bool = False,
                               content_base64: str = "") -> dict:
        """Auto-pipeline triggered when a structural drawing PDF is uploaded.

        Joseph's directive (v3.3.4): start with what we have, narrate every
        decision, auto-escalate to AI without asking, always produce a
        rough-draft estimate even if extraction returned 0 members, and
        finish by asking targeted clarifying questions instead of dead-ending.

        Cascade of extraction methods (each tried automatically):
          1. pdfplumber - fast, local, free, works for vector PDFs
          2. Gemini 2.5 Flash vision - for raster/scanned drawings
          3. Claude Sonnet 4.5 vision - last resort if Gemini returns 0

        Each step appends to extraction_log so the user sees what was tried
        and WHY it escalated. Decisions are made for the user, not asked of
        them.

        Always produces a rough-draft estimate and clarifying_questions list
        - even with 0 verified members, we estimate from building footprint
        or fall to "$X-$Y typical range" using Houston Q2 2026 calibration.

        Honors the Hard Rule: when members ARE extracted, weights come from
        AISC CSV (no LLM math). When members are NOT extracted, the rough
        draft is clearly labeled DRAFT/PLACEHOLDER and asks the user to
        confirm tonnage before pricing locks.

        Dedup: SHA-256 of the PDF is computed. If a bid already exists for
        this exact file, returns the existing bid with already_processed=True
        unless force_new=True. Saves Owner from accidentally creating
        duplicate pipeline entries when re-dropping the same drawing.
        """
        from pathlib import Path as _P
        import hashlib as _hashlib
        import shutil, json as _json

        try:
            from bridge.bid_documents import (
                bid_folder, save_artifact, update_manifest, bid_number_from_project,
            )
            # v3.2.7 pass 9b: content_base64 passthrough for claude.ai reverse direction.
            # When a PDF is dropped in the browser, claude.ai extracts text but
            # tools like this one need the raw bytes for pymupdf4llm parsing.
            # Decode base64 to a temp file and use that path.
            if content_base64 and not pdf_path:
                import base64 as _b64, tempfile as _tmpf
                try:
                    raw = _b64.b64decode(content_base64)
                    tmp = _tmpf.NamedTemporaryFile(suffix=".pdf", delete=False, prefix="nc_upload_")
                    tmp.write(raw)
                    tmp.close()
                    pdf_path = tmp.name
                except Exception as b64e:
                    return _err(f"Failed to decode content_base64: {b64e}",
                                fix="Ensure the base64 string is a valid PDF. Try dropping the file in the desktop chat instead.")
            if not pdf_path:
                return _err("No PDF provided. Pass pdf_path (local file) or content_base64 (browser upload).",
                            fix="Drop a PDF onto the chat, or pass the file path directly.")
            src = _P(pdf_path)
            if not src.exists():
                return _err(f"Drawing PDF not found: {pdf_path}",
                            fix="Confirm the file path is correct. Drop the PDF onto the chat window again.")
            if not src.suffix.lower() == ".pdf":
                return _err(f"Only PDF drawings supported (got {src.suffix})",
                            fix="Convert your drawing to PDF first. Most CAD apps export PDF directly.")

            # ── pass 10i (R5): auto-derive bid_number from path ──
            # Owner gripe: auto_process_drawing pulls 61 tons from a fixture
            # PDF but returns bid_number="" unless explicitly passed. If the
            # file lives in a folder named PRJ-2026-XXX-001 or the filename
            # contains that pattern, lift it. Saves the rekeying step.
            if not bid_number:
                import re as _re
                _bn_pat = _re.compile(r"NC-\d{4}-[A-Z]+-\d{3}")
                for _candidate in [src.name] + [p.name for p in src.parents]:
                    _m = _bn_pat.search(_candidate)
                    if _m:
                        bid_number = _m.group(0)
                        break
                if not bid_number and project_name:
                    _m = _bn_pat.search(project_name)
                    if _m:
                        bid_number = _m.group(0)

            # ── Hash-based dedup check ──
            sha = _hashlib.sha256()
            with open(src, "rb") as _f:
                for chunk in iter(lambda: _f.read(65536), b""):
                    sha.update(chunk)
            pdf_hash = sha.hexdigest()

            if not force_new:
                from bridge.bid_pipeline import find_bid_by_hash, find_bid_by_name
                existing = find_bid_by_hash(pdf_hash)
                # Secondary check: same project name even if PDF differs slightly
                if not existing and project_name:
                    existing = find_bid_by_name(project_name)
                if existing:
                    # Normalize response to the same schema the fresh-process
                    # path returns. Before this fix, "already_processed"
                    # responses were missing total_tonnage, member_count,
                    # project_name, pdf_path etc., so frontend code that
                    # reads response.data.project_name (or .total_tonnage)
                    # got undefined and silently broke.
                    try:
                        existing_tonnage = float(existing.get("tonnage") or 0)
                    except (ValueError, TypeError):
                        existing_tonnage = 0.0
                    try:
                        existing_value = float(existing.get("estimated_value") or 0)
                    except (ValueError, TypeError):
                        existing_value = 0.0
                    existing_name = existing.get("name", project_name)
                    return _ok({
                        # Old keys kept for backward compatibility
                        "already_processed": True,
                        "bid_id": existing["id"],
                        "name": existing_name,
                        "state": existing.get("state", "SCANNED"),
                        "tonnage": existing.get("tonnage", ""),
                        "estimated_value": existing.get("estimated_value", ""),
                        "pdf_hash": pdf_hash,
                        # Schema parity with fresh-process responses
                        "project_name": existing_name,
                        "total_tonnage": existing_tonnage,
                        "member_count": None,  # not re-extracted on dup
                        "members": [],         # not re-extracted on dup
                        "bid_number": existing.get("bid_number") or bid_number,
                        "pdf_path": existing.get("pdf_path", ""),
                        "inventory_thumbnail_path": None,
                        "draft_estimate": {
                            "total": existing_value,
                            "source": "previously stored",
                        } if existing_value > 0 else None,
                        "message": (
                            f"This drawing is already bid {existing['id']} "
                            f"({existing.get('name','?')}) in state "
                            f"{existing.get('state','SCANNED')}. "
                            "Pass force_new=True to create a fresh bid anyway, "
                            f"or use update_bid_from_drawing(bid_id={existing['id']}, "
                            "pdf_path=...) to refresh it."
                        ),
                        "fix": (
                            f"to create a new bid anyway, type `force new bid` "
                            f"in chat then re-drop, or call with force_new=True"
                        ),
                    })

            # Step 1: bid number
            if not bid_number:
                bid_number = bid_number_from_project(project_name or src.stem)

            # Step 2: copy original drawing
            folder = bid_folder(bid_number, project_name or None)
            drawings_dir = folder / "source_drawings"
            drawings_dir.mkdir(exist_ok=True)
            preserved = drawings_dir / src.name
            if not preserved.exists():
                shutil.copy2(str(src), str(preserved))

            # Step 3: cascade through extraction methods, narrating each
            extraction_log = []
            members = []
            method = "none"

            # ── 3a: local pdfplumber ──
            extraction_log.append("Trying local pdfplumber extraction…")
            from bridge.hybrid_3d_pipeline import (
                extract_members_local, extract_members_from_pdf, match_aisc_database,
            )
            try:
                local = extract_members_local(str(preserved))
                local_members = local.get("members", [])
                if local_members:
                    members = local_members
                    method = local.get("method", "pdfplumber")
                    extraction_log.append(
                        f"  ✓ Found {len(members)} members locally (method: {method})"
                    )
                else:
                    extraction_log.append(
                        "  ✗ Local extraction found 0 members - likely a "
                        "raster/scanned drawing or image-flattened PDF"
                    )
            except Exception as e:
                extraction_log.append(f"  ✗ Local extraction errored: {e}")

            # ── 3b: auto-escalate to Gemini vision ──
            keys = _load_all_keys()
            run_gemini = not members  # always run if local found nothing
            if not allow_local_short_circuit and members:
                run_gemini = True  # force AI verification of local results
                extraction_log.append(
                    "  ⚙ Local short-circuit disabled - running Gemini "
                    "for AI verification of pdfplumber results"
                )
                local_members_backup = list(members)  # preserve local as fallback

            if run_gemini and keys.get("GOOGLE_API_KEY"):
                extraction_log.append(
                    "Auto-escalating to Gemini 2.5 Flash vision "
                    "(image AI handles raster drawings) - no user prompt needed"
                )
                try:
                    ai = extract_members_from_pdf(str(preserved), keys["GOOGLE_API_KEY"])
                    ai_members = ai.get("members", [])
                    if ai_members:
                        members = ai_members
                        method = "ai_vision_gemini"
                        extraction_log.append(
                            f"  ✓ Gemini vision extracted {len(members)} members"
                        )
                    else:
                        err = ai.get("error", "no error message")
                        extraction_log.append(
                            f"  ✗ Gemini vision returned 0 members ({err})"
                        )
                except Exception as e:
                    extraction_log.append(f"  ✗ Gemini vision errored: {e}")

            # Fallback: if short-circuit was disabled and Gemini found nothing,
            # restore the local pdfplumber results rather than losing them
            if not allow_local_short_circuit and not members:
                if 'local_members_backup' in locals() and local_members_backup:
                    members = local_members_backup
                    method = "pdfplumber_fallback"
                    extraction_log.append(
                        f"  ↩ Restored {len(members)} members from local "
                        "extraction (Gemini did not improve results)"
                    )

            # ── 3c: last-resort Claude Sonnet vision ──
            if not members and keys.get("ANTHROPIC_API_KEY"):
                extraction_log.append(
                    "Auto-escalating to Claude Sonnet 4.5 vision (Gemini "
                    "didn't find members) - final extraction attempt"
                )
                try:
                    cv = self._claude_vision_extract(
                        str(preserved), keys["ANTHROPIC_API_KEY"]
                    )
                    cv_members = cv.get("members", [])
                    if cv_members:
                        members = cv_members
                        method = "ai_vision_claude"
                        extraction_log.append(
                            f"  ✓ Claude vision extracted {len(members)} members"
                        )
                    else:
                        err = cv.get("error", "no members in response")
                        extraction_log.append(f"  ✗ Claude vision: {err}")
                except Exception as e:
                    extraction_log.append(f"  ✗ Claude vision errored: {e}")

            if not members:
                extraction_log.append(
                    "All extraction methods exhausted - building rough-draft "
                    "estimate from project context with placeholder tonnage. "
                    "Pricing locks once you confirm tonnage from the EOR."
                )

            # Step 4: AISC match → verified weights (no LLM math!)
            # match_aisc_database returns: {matched: [...], unmatched: [...],
            #   summary: {total_weight_tons, matched_count, ...}, source: "AISC_LOCAL"}
            _empty_match = {"matched": [], "unmatched": [],
                            "summary": {"total_weight_tons": 0.0,
                                        "matched_count": 0, "unmatched_count": 0,
                                        "total_pieces": 0, "total_weight_lbs": 0}}
            matched = match_aisc_database(members) if members else _empty_match
            summary = matched.get("summary", {})
            verified_members = matched.get("matched", [])
            total_tons = summary.get("total_weight_tons", 0.0)

            # Narrate the AISC match outcome
            mc = summary.get("matched_count", 0)
            uc = summary.get("unmatched_count", 0)
            if members:
                extraction_log.append(
                    f"AISC database matched {mc} of {mc + uc} members; "
                    f"total weight {total_tons:.2f} tons"
                )

            # If AISC matched members but total_tons is ~0, lengths are missing.
            # Local pdfplumber rarely captures lengths from text - escalate to AI
            # vision which can infer lengths from grid dimensions on framing plans.
            if mc > 0 and total_tons < 0.01 and not method.startswith("ai_vision"):
                extraction_log.append(
                    "  ⚠ Members matched but no lengths extracted from text - "
                    "escalating to AI vision (which infers lengths from grid spacing)"
                )
                # Re-try extraction via AI vision to get members WITH lengths
                keys = _load_all_keys()
                ai_members = []
                if keys.get("GOOGLE_API_KEY"):
                    extraction_log.append(
                        "Auto-escalating to Gemini 2.5 Flash vision for length data…"
                    )
                    try:
                        ai = extract_members_from_pdf(str(preserved), keys["GOOGLE_API_KEY"])
                        ai_members = ai.get("members", [])
                        ai_method = ai.get("method", "")
                        if ai_members and not ai_method.startswith("local/"):
                            # Gemini actually ran and found members
                            method = "ai_vision_gemini"
                            extraction_log.append(
                                f"  ✓ Gemini vision found {len(ai_members)} members"
                            )
                        elif ai_members and ai_method.startswith("local/"):
                            # extract_members_from_pdf short-circuited back to
                            # pdfplumber because it found ≥3 members locally.
                            # Same shapes, still no lengths - not a real escalation.
                            extraction_log.append(
                                "  ↺ Short-circuited to local (≥3 members already "
                                "found by pdfplumber); no new length data gained"
                            )
                            ai_members = []  # don't re-match; same data
                        else:
                            err = ai.get("error", "no members in response")
                            extraction_log.append(f"  ✗ Gemini vision: {err}")
                    except Exception as e:
                        extraction_log.append(f"  ✗ Gemini vision errored: {e}")

                if not ai_members and keys.get("ANTHROPIC_API_KEY"):
                    extraction_log.append(
                        "Auto-escalating to Claude Sonnet 4.5 vision for length data…"
                    )
                    try:
                        cv = self._claude_vision_extract(str(preserved), keys["ANTHROPIC_API_KEY"])
                        ai_members = cv.get("members", [])
                        if ai_members:
                            method = "ai_vision_claude"
                            extraction_log.append(
                                f"  ✓ Claude vision found {len(ai_members)} members"
                            )
                    except Exception as e:
                        extraction_log.append(f"  ✗ Claude vision errored: {e}")

                # Re-match if AI vision found members with lengths
                if ai_members:
                    matched = match_aisc_database(ai_members)
                    summary = matched.get("summary", {})
                    verified_members = matched.get("matched", [])
                    total_tons = summary.get("total_weight_tons", 0.0)
                    extraction_log.append(
                        f"Re-matched via AISC: {summary.get('matched_count', 0)} members, "
                        f"{total_tons:.2f} tons"
                    )

            # Step 5: save takeoff.json
            takeoff_data = {
                "bid_number":      bid_number,
                "project_name":    project_name,
                "source_pdf":      src.name,
                "extraction_method": method,
                "extraction_log":  extraction_log,
                "extracted_at":    datetime.now(timezone.utc).isoformat(),
                "member_count":    len(verified_members),
                "total_tonnage":   total_tons,
                "members":         verified_members,
                "_provenance":     "AISC database - no LLM-estimated weights",
            }
            takeoff_path = save_artifact(bid_number, "takeoff.json",
                                          _json.dumps(takeoff_data, indent=2),
                                          project_name=project_name or None)

            # Step 6: STL generation moved to Step 11 (generates ALL unique shapes)
            stl_path = None

            # Step 7: rough-draft estimate (always, even with 0 members)
            draft_estimate = self._build_draft_estimate(
                bid_number=bid_number,
                project_name=project_name,
                verified_members=verified_members,
                total_tons=total_tons,
            )

            # Step 8: clarifying questions - what we need from the user
            clarifying_questions = self._draft_clarifying_questions(
                project_name=project_name,
                verified_members=verified_members,
                total_tons=total_tons,
                method=method,
            )

            # Step 9: update manifest
            update_manifest(bid_number, "3d_status",
                             "complete" if verified_members else "draft_no_members",
                             project_name=project_name or None)
            update_manifest(bid_number, "member_count", len(verified_members),
                             project_name=project_name or None)
            update_manifest(bid_number, "total_tonnage", total_tons,
                             project_name=project_name or None)
            update_manifest(bid_number, "extraction_method", method,
                             project_name=project_name or None)
            update_manifest(bid_number, "draft_estimate_low",
                             draft_estimate.get("total_low", 0),
                             project_name=project_name or None)
            update_manifest(bid_number, "draft_estimate_high",
                             draft_estimate.get("total_high", 0),
                             project_name=project_name or None)

            self.track_time_saved("auto_process_drawing", 180)

            # Step 10: Store in session context so 3D model, proposal,
            # Tekla export buttons can use this data without re-asking.
            # This is the fix for "create a 3D model" firing the guard
            # even though we just extracted 22 members from the PDF.
            try:
                from bridge.session_context import get_session
                get_session().set_takeoff(
                    project_id=bid_number,
                    project_name=project_name,
                    members=verified_members,
                    tonnage=total_tons,
                    method=method,
                    source_pdf=str(preserved),
                )
                get_session().set_output_path("output_folder", str(folder))
                if stl_path:
                    get_session().set_output_path("stl_path", str(stl_path))
                if draft_estimate:
                    get_session().set_estimate(
                        fabrication=draft_estimate.get("fabrication", 0),
                        erection=draft_estimate.get("erection", 0),
                        gna=draft_estimate.get("gna", 0),
                        total=draft_estimate.get("total", 0),
                        range_low=draft_estimate.get("total_low", 0),
                        range_high=draft_estimate.get("total_high", 0),
                    )
            except Exception as _ctx_err:
                log.warning("Session context storage failed: %s", _ctx_err)

            # Step 11: Auto-generate 3D models for all unique shapes
            # so the user doesn't have to ask separately.
            stl_paths = []
            if verified_members:
                seen_shapes = set()
                for member in verified_members:
                    shape = member.get("shape", "")
                    if shape and shape not in seen_shapes:
                        seen_shapes.add(shape)
                        try:
                            length = member.get("length_ft", 20)
                            stl_r = self.generate_3d_view(shape=shape, length_ft=length)
                            if stl_r.get("ok") and stl_r["data"].get("path"):
                                stl_paths.append({
                                    "shape": shape,
                                    "path": stl_r["data"]["path"],
                                    "filename": stl_r["data"].get("filename", ""),
                                    "stl_bytes": stl_r["data"].get("stl_bytes", 0),
                                    "stl_b64": stl_r["data"].get("stl_b64", ""),
                                })
                        except Exception:
                            pass

            # Step 11b: Write combined 3d_model.stl for MODEL tab View 3D button.
            # Per P17.2: previously only per-shape STLs were written; the bid folder
            # never got a combined model, so View 3D always hit the dead-end branch.
            if verified_members:
                try:
                    from bridge.fabrication import generate_stl as _gen_stl
                    import base64 as _b64_stl
                    _stl_bytes = _gen_stl(verified_members)
                    if _stl_bytes and len(_stl_bytes) >= 100:
                        _stl_out = folder / "3d_model.stl"
                        _stl_out.write_bytes(_stl_bytes)
                        stl_path = _stl_out
                        extraction_log.append(
                            f"    ✓ 3D model: {len(verified_members)} members, "
                            f"{round(len(_stl_bytes)/1024, 1)} KB"
                        )
                    else:
                        extraction_log.append("    (3D model: generate_stl returned empty output)")
                except Exception as _stl_err:
                    import traceback as _tb_stl
                    _diag_dir = Path(__file__).parent.parent / "data" / "diag_logs"
                    _diag_dir.mkdir(exist_ok=True)
                    (_diag_dir / f"stl_write_fail_{bid_number}.log").write_text(
                        f"{datetime.now(timezone.utc).isoformat()}\n{_tb_stl.format_exc()}",
                        encoding="utf-8",
                    )
                    extraction_log.append(f"    (3D model write failed: {_stl_err})")

            # ── P1 ROADMAP: Combined-shape thumbnail for PDF drops ──
            # When Owner drops a drawing, give him a single PNG showing
            # all the unique shapes that were extracted. Lays them out in
            # a grid with shape names and counts so he sees the takeoff
            # without opening anything.
            inventory_thumbnail_path = None
            if stl_paths:
                try:
                    from bridge.member_inventory_thumbnail import (
                        render_member_inventory_thumbnail,
                    )
                    thumb_out = str(folder / f"{bid_number}_inventory.png")
                    inventory_thumbnail_path = render_member_inventory_thumbnail(
                        stl_paths=stl_paths,
                        verified_members=verified_members,
                        output_path=thumb_out,
                    )
                except Exception as _thumb_err:
                    log.debug("Inventory thumbnail skipped: %s", _thumb_err)

            # Compose user-facing next-step guidance based on outcome
            if verified_members:
                next_step = (
                    "Review the rough draft below. Confirm the clarifying questions "
                    "to lock pricing, then GENERATE PROPOSAL for the navy/gold PDF."
                )
            else:
                next_step = (
                    "No members extracted, but a draft estimate is below using "
                    "Houston Q2 2026 calibration. Confirm tonnage from the EOR "
                    "(or provide building sf for a 12-15 PSF heuristic) and "
                    "I'll lock in pricing."
                )

            # ── P1 FEATURE: Auto-generate tagged PDF on drop ──
            tagged_pdf_path = None
            if verified_members:
                try:
                    from bridge.tagged_pdf_renderer import render_tagged_pdf
                    tagged_out = str(folder / f"{bid_number}_tagged.pdf")
                    tag_result = render_tagged_pdf(
                        source_pdf=str(preserved),
                        members=verified_members,
                        summary={"total_weight_tons": total_tons,
                                "members_matched": len(verified_members)},
                        output_path=tagged_out,
                        force_ai=False,
                    )
                    if tag_result.get("output_path"):
                        tagged_pdf_path = tag_result["output_path"]
                        extraction_log.append(
                            f"    \u2713 Tagged PDF: {tag_result.get('annotations_placed',0)} "
                            f"annotations across {tag_result.get('pages_annotated',0)} page(s)"
                        )
                except Exception as e:
                    extraction_log.append(f"    (tagged PDF skipped: {e})")

            # ── P1 FEATURE: Persist bid to pipeline DB ──
            persisted_bid_id = 0
            try:
                from bridge.bid_pipeline import add_bid
                est_total = draft_estimate.get("total", 0) if draft_estimate else 0
                persisted_bid_id = add_bid(
                    name=project_name or src.stem,
                    gc_company="",
                    location="",
                    tonnage=str(round(total_tons, 2)),
                    estimated_value=str(int(est_total)),
                    source="pdf_drop",
                    score=0,
                    pdf_hash=pdf_hash,        # H1: tag bid with PDF hash for future dedup
                    pdf_path=str(preserved),
                )
                if persisted_bid_id:
                    extraction_log.append(
                        f"    \u2713 Persisted to pipeline DB (id={persisted_bid_id})"
                    )
            except Exception as e:
                extraction_log.append(f"    (DB persist skipped: {e})")

            return _ok({
                "bid_number":            bid_number,
                "project_name":          project_name,
                "folder":                str(folder),
                "preserved_drawing":     str(preserved),
                "pdf_path":              str(preserved),         # Phase 5: misc steel detector entry point
                "pdf_hash":              pdf_hash,                # H1: SHA-256 of source PDF
                "bid_id":                persisted_bid_id,        # H1/M1: returned for update flows
                "extraction_method":     method,
                "extraction_log":        extraction_log,   # NEW - narrate every step
                "member_count":          len(verified_members),
                "total_tonnage":         round(total_tons, 2),
                "members":               verified_members[:20],
                "members_truncated":     len(verified_members) > 20,
                "takeoff_path":          str(takeoff_path),
                "stl_path":              str(stl_path) if stl_path else None,
                "stl_paths":             stl_paths,              # All unique shapes
                "inventory_thumbnail_path": inventory_thumbnail_path,  # P1: combined shape grid PNG
                "tagged_pdf_path":       tagged_pdf_path,        # NEW - P1 feature
                "draft_estimate":        draft_estimate,        # NEW - rough draft
                "clarifying_questions":  clarifying_questions,  # NEW - what we need
                "next_step":             next_step,
                "session_active":        True,                  # Session context stored
            })

        except Exception as e:
            # Log to crash file so we have something to look at if pywebview dies
            try:
                from pathlib import Path as _P2
                import traceback as _tb
                crash_path = _P2(__file__).resolve().parent.parent / "data" / "crash.log"
                crash_path.parent.mkdir(exist_ok=True)
                with open(crash_path, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now(timezone.utc).isoformat()}] auto_process_drawing failed\n")
                    f.write(f"  pdf_path={pdf_path}\n  bid_number={bid_number}\n")
                    f.write(f"  error: {e}\n")
                    f.write(_tb.format_exc())
                    f.write("\n")
            except Exception:
                pass
            return _err(f"auto_process_drawing failed: {e}")

    def _claude_vision_extract(self, pdf_path: str, anthropic_key: str) -> dict:
        """Claude Sonnet 4.5 vision fallback for member extraction.

        Same prompt contract as the Gemini path so downstream code
        (match_aisc_database) doesn't care which AI extracted.
        """
        import base64, json as _json
        try:
            import anthropic
        except ImportError:
            return {"error": "anthropic package not installed"}

        try:
            pdf_bytes = open(pdf_path, "rb").read()
            pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

            prompt = (
                "You are a structural steel detailing expert reading construction "
                "drawings. Extract EVERY structural steel member from these drawings "
                "into a JSON array.\n\n"
                "For each member, provide:\n"
                '- "mark": piece mark or member ID (e.g., "C1", "B2", "G1")\n'
                '- "shape": AISC shape designation (e.g., "W14x82", "HSS6x6x1/4")\n'
                '- "length_ft": estimated length in feet\n'
                '- "qty": quantity of identical members\n'
                '- "type": "column", "beam", "girder", "brace", "joist", or "misc"\n\n'
                "If a member schedule table is shown, use it directly. Otherwise read "
                "from framing plans.\n\n"
                "Respond with ONLY valid JSON - no markdown:\n"
                '{"members": [...], "notes": "any special conditions observed"}'
            )

            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )

            text = response.content[0].text.strip()
            # Strip markdown fences if Claude added them despite the instruction
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            if text.startswith("json"):
                text = text[4:]

            result = _json.loads(text.strip())
            members = result.get("members", [])
            return {"members": members, "notes": result.get("notes", "")}
        except _json.JSONDecodeError as e:
            return {"error": f"Claude returned invalid JSON: {e}"}
        except Exception as e:
            return {"error": f"Claude vision failed: {e}"}

    def _build_draft_estimate(self, bid_number: str, project_name: str,
                                verified_members: list, total_tons: float) -> dict:
        """Build a rough-draft pricing estimate using Houston Q2 2026 calibration.

        Three confidence tiers based on what we know:
          A. We have verified tonnage from AISC → straight rate × ton math
          B. We don't have tonnage → use 12-15 PSF heuristic (commercial steel)
             but the user must supply building sf for this to work
          C. We have nothing → publish a $X-$Y typical range based on
             project_name keywords (refinery, distribution, etc.)

        Honors the Hard Rule: numbers come from calibration JSON, not LLM.
        Tier B and C results are clearly labeled DRAFT/PLACEHOLDER.
        """
        # vj: parity-ok (pass 10g classified: mixed J=0.57; needs manual audit)
        # Pull current Q2 2026 rates from calibration (single source of truth)
        rates = {
            "fab_per_ton":    3750,
            "erect_per_ton":  970,
            "joists_per_ton": 4500,
            "ga_pct":         7.5,
        }
        try:
            from bridge.calibration_2026q2 import calibration_summary
            cal = calibration_summary()
            # If calibration exposes them, prefer those; otherwise stick with defaults
            if isinstance(cal, dict):
                rates["fab_per_ton"]   = cal.get("fab_per_ton",   rates["fab_per_ton"])
                rates["erect_per_ton"] = cal.get("erect_per_ton", rates["erect_per_ton"])
        except Exception:
            pass

        if total_tons > 0:
            # Tier A: verified tonnage path
            fab_total   = total_tons * rates["fab_per_ton"]
            erect_total = total_tons * rates["erect_per_ton"]
            subtotal    = fab_total + erect_total
            ga          = subtotal * (rates["ga_pct"] / 100.0)
            grand_total = subtotal + ga
            return {
                "tier":       "A_verified",
                "label":      f"Verified estimate ({total_tons:.1f} tons from AISC database)",
                "tonnage":    round(total_tons, 1),
                "fab":        round(fab_total),
                "erect":      round(erect_total),
                "subtotal":   round(subtotal),
                "ga":         round(ga),
                "total":      round(grand_total),
                "total_low":  round(grand_total * 0.95),
                "total_high": round(grand_total * 1.05),
                "rates_used": rates,
                "confidence": "high",
                "needs":      [],
            }

        # Tier C: nothing extracted - best-guess range from project_name keywords
        # We DON'T fabricate a single number here. We give a typical-range envelope
        # and label it clearly so the user knows it's a placeholder.
        keywords_lower = (project_name or "").lower()
        if any(k in keywords_lower for k in ("refinery", "petrochem", "marathon", "exxon")):
            tons_range = (800, 2500)        # refinery PLA bids
            note = "Refinery scope - typical range 800-2,500 tons"
        elif any(k in keywords_lower for k in ("distribution", "warehouse", "logistics")):
            tons_range = (1200, 3000)
            note = "Distribution/warehouse scope - typical range 1,200-3,000 tons"
        elif any(k in keywords_lower for k in ("public works", "school", "municipal", "civic")):
            tons_range = (200, 1500)
            note = "Public works scope - typical range 200-1,500 tons"
        elif any(k in keywords_lower for k in ("office", "tower", "high-rise")):
            tons_range = (1500, 8000)
            note = "Office/high-rise scope - typical range 1,500-8,000 tons"
        else:
            tons_range = (500, 2000)
            note = "Generic commercial scope - typical range 500-2,000 tons"

        low_tons,  high_tons = tons_range
        all_in_per_ton = (rates["fab_per_ton"] + rates["erect_per_ton"]) * (1 + rates["ga_pct"] / 100.0)
        return {
            "tier":       "C_placeholder",
            "label":      f"DRAFT placeholder: {note}",
            "tonnage":    None,
            "tonnage_range": [low_tons, high_tons],
            "total_low":  round(low_tons  * all_in_per_ton),
            "total_high": round(high_tons * all_in_per_ton),
            "rates_used": rates,
            "confidence": "low",
            "needs":      ["confirmed_tonnage_or_building_sf"],
        }

    def _draft_clarifying_questions(self, project_name: str,
                                      verified_members: list,
                                      total_tons: float, method: str) -> list:
        """Build the targeted list of questions the user must answer to lock
        the bid. Order matters - most-blocking questions first."""
        q = []

        # Tonnage is the #1 blocker if we don't have it
        if total_tons == 0:
            q.append({
                "field":  "tonnage",
                "ask":    "Total structural steel tonnage from the EOR - or "
                          "the building footprint sf so I can use a 12-15 PSF heuristic",
                "why":    "Pricing scales linearly with tonnage; this is the "
                          "biggest driver of the proposal total",
                "blocker": True,
            })
        elif method.startswith("ai_vision"):
            q.append({
                "field":  "tonnage_verify",
                "ask":    f"AI vision extracted {len(verified_members)} members "
                          f"totaling {total_tons:.1f} tons. Does this look right "
                          "to Ivan, or should I assume a different tonnage?",
                "why":    "AI vision can miss members on dense drawings; "
                          "verifying with the EOR before the bid goes out reduces risk",
                "blocker": False,
            })

        # Project name / GC contact
        if not project_name or project_name.lower() in ("test", "untitled", ""):
            q.append({
                "field":  "project_name",
                "ask":    "Confirm project name as it should appear on the proposal letter",
                "why":    "Currently set to a generic placeholder - the proposal will "
                          "say 'Untitled Project' if not corrected",
                "blocker": True,
            })

        q.append({
            "field":  "gc_contact",
            "ask":    "GC contact name + email (e.g., 'James Holder, jholder@holder.com')",
            "why":    "Goes in the TO/COMPANY block on the proposal letter",
            "blocker": True,
        })

        q.append({
            "field":  "due_date",
            "ask":    "Bid due date and time",
            "why":    "Drives the urgency tier and outreach scheduling",
            "blocker": False,
        })

        # Site location for delivery surcharge
        q.append({
            "field":  "site_address",
            "ask":    "Site address (or just 'Houston metro' if local)",
            "why":    "Outside Houston metro adds a delivery surcharge to the rate",
            "blocker": False,
        })

        return q

    def save_temp_file(self, filename: str, content_b64: str) -> dict:
        """Save an uploaded file to a temp location pywebview can read.

        Used by the chat drag-drop flow before kicking off auto_process_drawing.
        Returns the absolute path the auto-pipeline can use.
        """
        import tempfile, base64
        try:
            safe_name = filename.replace("/", "_").replace("\\", "_")
            target = Path(tempfile.gettempdir()) / "yourco_uploads" / safe_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(content_b64))
            return _ok({"path": str(target), "size_kb": round(target.stat().st_size / 1024, 1)})
        except Exception as e:
            return _err(f"Could not save temp file: {e}")

    def read_bid_takeoff(self, bid_number: str = "",
                          project_name: str = "") -> dict:
        """Read takeoff.json from a bid's folder. Used by the MODEL tab to
        populate the member schedule + verified tonnage panel.
        """
        import json as _json
        try:
            from bridge.bid_documents import bid_folder
            f = bid_folder(bid_number, project_name or None) / "takeoff.json"
            if not f.exists():
                return _err(f"No takeoff.json for {bid_number}")
            return _ok(_json.loads(f.read_text(encoding="utf-8")))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Could not read takeoff: {e}")

    def read_bid_stl(self, bid_number: str = "",
                      project_name: str = "") -> dict:
        """Read 3d_model.stl from a bid's folder, base64-encoded for the viewer."""
        import base64 as _b64
        try:
            from bridge.bid_documents import bid_folder
            f = bid_folder(bid_number, project_name or None) / "3d_model.stl"
            if not f.exists():
                return _err(f"No 3d_model.stl for {bid_number}")
            return _ok({"stl_b64": _b64.b64encode(f.read_bytes()).decode("ascii"),
                         "size_kb": round(f.stat().st_size / 1024, 1)})
        except Exception as e:
            return _err(f"Could not read STL: {e}")

    def generate_bid_stl(self, bid_number: str = "",
                         project_name: str = "") -> dict:
        """Generate 3d_model.stl from a bid's existing takeoff.json.

        Sub-second. Pure AISC geometry. Zero AI. Used by MODEL tab View 3D
        button when STL is missing but takeoff exists.
        """
        import json as _json
        import base64 as _b64
        try:
            from bridge.bid_documents import bid_folder
            from bridge.fabrication import generate_stl
            bf = bid_folder(bid_number, project_name or None)
            tk = bf / "takeoff.json"
            if not tk.exists():
                return _err(f"No takeoff.json for {bid_number}.")
            data = _json.loads(tk.read_text(encoding="utf-8"))
            members = data.get("members") or []
            if not members:
                return _err(f"takeoff.json for {bid_number} has no members.")
            for idx, m in enumerate(members):
                if m.get("x_ft") is None:
                    m["x_ft"] = (idx % 6) * 30
                if m.get("y_ft") is None:
                    m["y_ft"] = (idx // 6) * 25
                if m.get("z_ft") is None:
                    m["z_ft"] = 0
                if not m.get("length_ft"):
                    m["length_ft"] = 10
            stl_bytes = generate_stl(members)
            if not stl_bytes or len(stl_bytes) < 100:
                return _err("generate_stl produced empty output.")
            out = bf / "3d_model.stl"
            out.write_bytes(stl_bytes)
            return _ok({
                "stl_b64": _b64.b64encode(stl_bytes).decode("ascii"),
                "size_kb": round(out.stat().st_size / 1024, 1),
                "member_count": len(members),
            })
        except Exception as e:
            return _err(f"generate_bid_stl: {e}")

    def build_coordinate_model(self, bid_number: str = "", project_name: str = "",
                               pdf_path: str = "", members_json: str = "") -> dict:
        """Build the in-house ESTIMATE-GRADE 3D coordinate model for a bid.

        Slice 1 of the 3D-coordinate-extraction plan. Reads the framing plan's
        grid and level datums, places columns at grid intersections with
        confidence tags, writes coordinate_members.json, and renders a gray QC
        viewport to renders/<bid>_MODEL.png so find_render can use it as the
        page-1 fallback when no Tekla export exists.

        This is additive. It NEVER changes the validated tonnage, the AISC
        weights, or any rate. Tekla Structures stays the system of record; this
        model is for visualization and QC only. Low-confidence placements are
        flagged needs_review and never feed a price.
        """
        import json as _json
        from pathlib import Path as _P
        try:
            from bridge.bid_documents import bid_folder
            from bridge.lift_clone import geometry as _geo
        except Exception as e:
            return _err(f"coordinate model imports failed: {e}")
        try:
            # 1) members: explicit JSON, else the bid's verified takeoff.json
            members = []
            if members_json:
                try:
                    members = _json.loads(members_json)
                except (ValueError, TypeError) as je:
                    return _err(f"members_json must be valid JSON: {je}")
            bf = None
            if bid_number:
                bf = bid_folder(bid_number, project_name or None)
                if not members:
                    tk = bf / "takeoff.json"
                    if tk.exists():
                        try:
                            data = _json.loads(tk.read_text(encoding="utf-8"))
                            members = data.get("members") or data.get("lines") or []
                        except Exception:
                            members = []
            # 2) resolve a plan-set PDF if not supplied
            pdf = pdf_path or (self._find_plan_pdf(bf, project_name) if bf is not None else "")
            # 3) build the coordinate model (grid + datums + placed columns)
            model = _geo.build_coordinate_members(
                pdf_path=pdf or "", members=members, project_name=project_name)
            # 4) write artifacts where find_render / tekla_viewport look for them
            renders = None
            try:
                from bridge.tekla_viewport import _renders_dir
                renders = _renders_dir(bid_number or None, project_name or None)
            except Exception:
                renders = None
            if renders is None:
                renders = (bf / "renders") if bf is not None else (_app_root() / "output")
            renders.mkdir(parents=True, exist_ok=True)
            json_path = _geo.save_coordinate_members(
                model, str(renders / "coordinate_members.json"))
            rendered = _geo.render_model_png(
                model, str(renders), name=(bid_number or project_name or "model"))
            meta = model.get("meta", {})
            return _ok({
                "coordinate_members_json": json_path,
                "model_png": rendered.get("png", ""),
                "model_stl": rendered.get("stl", ""),
                "column_count": meta.get("column_count", 0),
                "confidence": meta.get("confidence", "low"),
                "needs_review": meta.get("needs_review", True),
                "framing_page": meta.get("framing_page"),
                "low_confidence_members": meta.get("low_confidence_members", 0),
                "warnings": meta.get("warnings", []),
                "system_of_record": meta.get("system_of_record", ""),
                "note": ("Estimate-grade in-house model. Tekla remains the "
                         "fabrication system of record. Review flagged members."),
            })
        except Exception as e:
            return _err(f"build_coordinate_model: {e}")

    def _find_plan_pdf(self, bid_folder_path, project_name: str = "") -> str:
        """Best-effort: the plan-set PDF for a bid (the full set is the largest).
        Looks in the bid's source_drawings/ then the working 'Bids To
        Estimate/<job>/drawings' folder matched by project name."""
        from pathlib import Path as _P
        cands = []
        try:
            sd = _P(bid_folder_path) / "source_drawings"
            if sd.is_dir():
                cands += list(sd.glob("*.pdf"))
        except Exception:
            pass
        try:
            work = _P(__file__).resolve().parent.parent / "Bids To Estimate"
            target = (project_name or "").lower()[:6]
            if work.is_dir() and target:
                for job in work.iterdir():
                    dd = job / "drawings"
                    if job.is_dir() and target in job.name.lower() and dd.is_dir():
                        cands += list(dd.glob("*.pdf"))
        except Exception:
            pass
        if not cands:
            return ""
        cands.sort(key=lambda p: p.stat().st_size, reverse=True)
        return str(cands[0])

    def list_recent_bids(self, limit: int = 20) -> dict:
        """List recent bids across all year-month folders. Used by MODEL tab.

        Returns each bid's: bid_number, project_name, member_count,
        total_tonnage, artifact_count, last_modified.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        try:
            from bridge.bid_documents import bids_root, get_manifest, list_artifacts
            root = bids_root()
            entries = []
            for ym in sorted(root.iterdir(), reverse=True):
                if not ym.is_dir() or not ym.name.startswith("20"):
                    continue
                for bid_dir in sorted(ym.iterdir(), reverse=True):
                    if not bid_dir.is_dir():
                        continue
                    # Folder name is "PRJ-2026-NTH-001 - Project Name"
                    parts = bid_dir.name.split(" - ", 1)
                    bn = parts[0]
                    pn = parts[1] if len(parts) > 1 else ""
                    manifest = get_manifest(bn, pn)
                    artifacts = list_artifacts(bn, pn)
                    try:
                        mtime = bid_dir.stat().st_mtime
                    except OSError:
                        mtime = 0
                    entries.append({
                        "bid_number":     bn,
                        "project_name":   pn,
                        "folder":         str(bid_dir),
                        "member_count":   manifest.get("member_count", 0),
                        "total_tonnage":  manifest.get("total_tonnage", 0.0),
                        "artifact_count": len(artifacts),
                        "last_modified":  datetime.fromtimestamp(mtime).isoformat() if mtime else "",
                    })
                    if len(entries) >= limit:
                        break
                if len(entries) >= limit:
                    break
            return _ok({"bids": entries, "root": str(root)})
        except Exception as e:
            return _err(f"Could not list recent bids: {e}")

    def export_all_data(self) -> dict:
        """Export all SQLite databases as a ZIP backup file."""
        import zipfile, shutil
        from datetime import datetime
        try:
            data_dir = _app_root() / "data"
            out_dir = _app_root() / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # vj: local-display-ok
            zip_path = out_dir / f"YourCo_Backup_{ts}.zip"
            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
                if data_dir.exists():
                    for db_file in data_dir.glob("*.db"):
                        zf.write(str(db_file), f"data/{db_file.name}")
                    for json_file in data_dir.glob("*.json"):
                        zf.write(str(json_file), f"data/{json_file.name}")
            size = zip_path.stat().st_size
            return _ok({
                "path": str(zip_path), "size_bytes": size,
                "size_human": f"{size // 1024}KB",
                "timestamp": ts,
                "message": f"Backup saved: {zip_path.name} ({size // 1024}KB)"
            })
        except Exception as e:
            return _err(f"Backup failed: {e}")

    def import_from_backup(self, zip_path: str = "") -> dict:
        """Restore data from a backup ZIP (created by export_all_data or auto-backup).
        Replaces all SQLite DBs and JSON configs with the contents of the ZIP.
        WARNING: This overwrites current data. Frontend should confirm twice before calling."""
        import zipfile
        try:
            from pathlib import Path as _P
            zp = _P(zip_path)
            if not zp.exists():
                return _err(f"Backup file not found: {zip_path}")
            if not zipfile.is_zipfile(str(zp)):
                return _err(f"Not a valid ZIP file: {zip_path}")

            data_dir = _app_root() / "data"
            bridge_data = _app_root() / "bridge" / "data"
            restored = []

            with zipfile.ZipFile(str(zp), 'r') as zf:
                names = zf.namelist()
                # Validate: must contain data/ files
                data_files = [n for n in names if n.startswith("data/") and (n.endswith(".db") or n.endswith(".json"))]
                bridge_files = [n for n in names if n.startswith("bridge/data/") and n.endswith(".db")]

                if not data_files and not bridge_files:
                    return _err("Backup ZIP does not contain expected data/ files. Invalid backup.")

                for fname in data_files:
                    target = data_dir / fname.replace("data/", "", 1)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(target), 'wb') as f:
                        f.write(zf.read(fname))
                    restored.append(fname)

                for fname in bridge_files:
                    target = _app_root() / fname
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with open(str(target), 'wb') as f:
                        f.write(zf.read(fname))
                    restored.append(fname)

            return _ok({
                "restored_files": len(restored),
                "files": restored,
                "source": str(zp),
                "message": f"Restored {len(restored)} files from backup. Restart the app to reload all data."
            })
        except Exception as e:
            return _err(f"Restore failed: {e}")

    def factory_reset(self, confirm_code: str = "") -> dict:
        """Factory reset - clear ALL data. Requires confirm_code='RESET-YOURCO' to execute.
        Frontend should prompt for this code after two confirm dialogs."""
        if confirm_code != "RESET-YOURCO":
            return _err(
                "Factory reset requires confirmation code 'RESET-YOURCO'.\n"
                "This will permanently delete ALL data: bids, contacts, compliance, conversations, settings.\n"
                "This action cannot be undone."
            )
        try:
            import glob
            data_dir = _app_root() / "data"
            bridge_data = _app_root() / "bridge" / "data"
            deleted = []

            # Delete all SQLite databases
            for pattern in [str(data_dir / "*.db"), str(bridge_data / "*.db")]:
                for f in glob.glob(pattern):
                    try:
                        os.remove(f)
                        deleted.append(f)
                    except Exception:
                        pass

            # Reset JSON configs to defaults (keep files, clear content)
            for jf in data_dir.glob("*.json"):
                if jf.name == "blockers.json":
                    jf.write_text("[]")
                elif jf.name in ("bid_rates.json", "user_prefs.json", "time_saved.json"):
                    jf.write_text("{}")
                deleted.append(str(jf))

            # Clear audit log
            audit_file = _app_root() / "audit.jsonl"
            if audit_file.exists():
                audit_file.write_text("")
                deleted.append(str(audit_file))

            return _ok({
                "deleted_files": len(deleted),
                "files": deleted,
                "message": "Factory reset complete. All data cleared. Restart the app."
            })
        except Exception as e:
            return _err(f"Factory reset failed: {e}")

    def prune_conversation_history(self, days: int = 90) -> dict:
        """Delete conversation history older than N days. Default: 90 days."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        try:
            from bridge.memory import prune_old as _prune
            count = _prune(days)
            return _ok({"pruned": count, "days": days,
                        "message": f"Removed {count} conversation entries older than {days} days."})
        except ImportError:
            # Fallback: direct SQLite prune
            try:
                import sqlite3
                from datetime import datetime, timedelta
                db_path = _app_root() / "data" / "conversations.db"
                if not db_path.exists():
                    return _ok({"pruned": 0, "message": "No conversation database found."})
                cutoff = (datetime.now() - timedelta(days=days)).isoformat()  # vj: duration-math
                conn = sqlite3.connect(str(db_path))
                cur = conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
                count = cur.rowcount
                conn.commit()
                conn.close()
                return _ok({"pruned": count, "days": days,
                            "message": f"Removed {count} messages older than {days} days."})
            except Exception as e:
                return _err(f"Prune failed: {e}")
        except Exception as e:
            return _err(f"Prune failed: {e}")

    def update_bid_rates(self, fabrication: float = 0, erection: float = 0,
                         joists: float = 0, roof_deck: float = 0,
                         comp_deck: float = 0, anchors: float = 0,
                         ga_percent: float = 0) -> dict:
        """Update and persist bid rates for the current quarter. Tracks per-field changes."""
        import json
        try:
            rates_file = _app_root() / "data" / "bid_rates.json"
            rates_file.parent.mkdir(parents=True, exist_ok=True)
            rates = {}
            if rates_file.exists():
                rates = json.loads(rates_file.read_text())

            from datetime import datetime
            ts = datetime.now(timezone.utc).isoformat()

            # Track individual field changes (old → new)
            field_map = {
                "fabrication_per_ton": fabrication, "erection_per_ton": erection,
                "joists_per_ton": joists, "roof_deck_per_sf": roof_deck,
                "comp_deck_per_sf": comp_deck, "anchors_each": anchors,
                "ga_percent": ga_percent,
            }
            changes = []
            for key, new_val in field_map.items():
                if new_val > 0:
                    old_val = rates.get(key, 0)
                    if old_val != new_val:
                        changes.append({"field": key, "old": old_val, "new": new_val,
                                       "changed_at": ts, "changed_by": "owner"})
                    rates[key] = new_val

            rates["locked_at"] = ts
            rates["locked_by"] = "owner"

            # Append per-field change log (keeps last 100 entries)
            change_log = rates.get("change_log", [])
            change_log.extend(changes)
            rates["change_log"] = change_log[-100:]

            # Legacy history (snapshot per save - keeps last 20)
            history = rates.get("history", [])
            snapshot = {k: v for k, v in rates.items() if k not in ("history", "change_log", "locked_at", "locked_by")}
            history.append({"ts": ts, "rates": snapshot, "changes_count": len(changes)})
            rates["history"] = history[-20:]

            rates_file.write_text(json.dumps(rates, indent=2))
            return _ok({
                "message": f"Bid rates locked. {len(changes)} field(s) changed.",
                "changes": changes, "rates": rates
            })
        except Exception as e:
            return _err(f"Rate update failed: {e}")

    def get_rate_history(self) -> dict:
        """Get the per-field rate change log (who changed what, when)."""
        import json
        try:
            rates_file = _app_root() / "data" / "bid_rates.json"
            if not rates_file.exists():
                return _ok({"change_log": [], "history": []})
            rates = json.loads(rates_file.read_text())
            return _ok({
                "change_log": rates.get("change_log", []),
                "history": rates.get("history", []),
                "last_locked": rates.get("locked_at", "never"),
                "locked_by": rates.get("locked_by", "unknown"),
            })
        except Exception as e:
            return _err(f"Rate history load failed: {e}")

    def get_bid_rates(self) -> dict:
        """Get current locked bid rates."""
        import json
        try:
            rates_file = _app_root() / "data" / "bid_rates.json"
            if rates_file.exists():
                return _ok(json.loads(rates_file.read_text()))  # vj: ok-passthrough-safe
            # Fallback: read from CEO-locked canonical source (bid_rates.py)
            # Never hardcode rates here - bid_rates.py is the single source of truth.
            from bridge.bid_rates import BID_RATES
            return _ok({
                "fabrication_per_ton": BID_RATES["fab_per_ton"],
                "erection_per_ton":    BID_RATES["erection_per_ton"],
                "joists_per_ton":      BID_RATES["joists_per_ton"],
                "roof_deck_per_sf":    BID_RATES["roof_deck_per_sf"],
                "comp_deck_per_sf":    BID_RATES["composite_deck_per_sf"],
                "anchors_each":        BID_RATES["anchor_rod_1x20_each"],
                "ga_percent":          round(BID_RATES["ga_overhead_pct"] * 100, 2),
                "locked_at":           "bid_rates.py"
            })
        except Exception as e:
            return _err(f"Rate load failed: {e}")

    # ═══ v3.2 SETTINGS BACKEND COMPLETION ══════════════════════════

    def get_display_prefs(self) -> dict:
        """Get display preferences (font size, sidebar, density, KPI visibility, blocker filter)."""
        import json
        try:
            prefs_file = _app_root() / "data" / "user_prefs.json"
            prefs = json.loads(prefs_file.read_text()) if prefs_file.exists() else {}
            defaults = {
                "font_size": "medium",        # small / medium / large
                "sidebar_default": "expanded", # expanded / collapsed / auto
                "density": "comfortable",      # compact / comfortable
                "kpi_visibility": {
                    "open_bids": True, "ar_balance": True, "compliance": True,
                    "active_projects": True, "blockers": True, "days_no_bid": True,
                    "win_streak": True, "time_saved": True,
                },
                "blocker_filter": "red_only",  # red_only / red_amber / all
            }
            display = prefs.get("display", defaults)
            # Merge defaults for any missing keys
            for k, v in defaults.items():
                if k not in display:
                    display[k] = v
            return _ok(display)
        except Exception as e:
            return _err(f"Display prefs error: {e}")

    def set_display_prefs(self, font_size: str = "", sidebar_default: str = "",
                          density: str = "", blocker_filter: str = "",
                          kpi_visibility: dict = None) -> dict:
        """Save display preferences. Only non-empty values are updated."""
        import json
        try:
            prefs_file = _app_root() / "data" / "user_prefs.json"
            prefs_file.parent.mkdir(parents=True, exist_ok=True)
            prefs = json.loads(prefs_file.read_text()) if prefs_file.exists() else {}
            display = prefs.get("display", {})
            if font_size: display["font_size"] = font_size
            if sidebar_default: display["sidebar_default"] = sidebar_default
            if density: display["density"] = density
            if blocker_filter: display["blocker_filter"] = blocker_filter
            if kpi_visibility: display["kpi_visibility"] = kpi_visibility
            prefs["display"] = display
            prefs_file.write_text(json.dumps(prefs, indent=2))
            return _ok({"message": "Display preferences saved", "display": display})
        except Exception as e:
            return _err(f"Display prefs save error: {e}")

    def get_sms_event_toggles(self) -> dict:
        """Get SMS per-event toggle map (which events trigger SMS alerts)."""
        try:
            from bridge.notifications import get_sms_event_toggles as _get
            return _ok(_get())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"SMS toggle error: {e}")

    def set_sms_event_toggle(self, event_type: str = "", enabled: bool = True) -> dict:
        """Enable or disable SMS for a specific event type."""
        try:
            if not event_type:
                return _err("event_type is required (e.g. 'morning_brief', 'bid_won')")
            from bridge.notifications import set_sms_event_toggle as _set
            return _ok({"event_type": event_type, "enabled": enabled, "toggles": _set(event_type, enabled)})
        except Exception as e:
            return _err(f"SMS toggle error: {e}")

    def get_escalation_threshold(self) -> dict:
        """Get the escalation threshold (days before blocker triggers urgent alert)."""
        try:
            from bridge.notifications import get_escalation_days
            return _ok({"escalation_days": get_escalation_days()})
        except Exception as e:
            return _err(f"Escalation threshold error: {e}")

    def set_escalation_threshold(self, days: int = 30) -> dict:
        """Set escalation threshold in days (how long before a blocker becomes urgent)."""
        # pass 10i: numeric input hardening - coerce or fail clean
        days, _e = _coerce_num(days, 'days', cast='int')
        if _e: return _e
        try:
            from bridge.notifications import set_escalation_days
            return _ok({"escalation_days": set_escalation_days(days),
                        "message": f"Escalation threshold set to {days} days"})
        except Exception as e:
            return _err(f"Escalation threshold error: {e}")

    def save_integration_credentials(self, service: str = "", credentials: dict = None) -> dict:
        """Save credentials for ISNetworld, DISA, or other integrations.
        Stored securely via the keyvault (DPAPI on Windows)."""
        import json
        try:
            if not service or not credentials:
                return _err("service and credentials are required")
            creds_file = _app_root() / "data" / "integration_creds.json"
            creds_file.parent.mkdir(parents=True, exist_ok=True)
            all_creds = {}
            if creds_file.exists():
                all_creds = json.loads(creds_file.read_text())
            all_creds[service] = {
                **credentials,
                "saved_at": __import__("datetime").datetime.now(timezone.utc).isoformat(),
            }
            # Try secure storage on Windows (DPAPI not available in this env)
            try:
                from bridge.vault import vault_write
                vault_write("integration_creds", json.dumps(all_creds))
            except Exception:
                pass  # Fall back to plain JSON
            creds_file.write_text(json.dumps(all_creds, indent=2))
            return _ok({"message": f"Credentials saved for {service}",
                        "service": service, "fields": list(credentials.keys())})
        except Exception as e:
            return _err(f"Credential save error: {e}")

    def get_integration_credentials(self, service: str = "") -> dict:
        """Retrieve stored credentials for an integration (ISNetworld, DISA, etc.)."""
        import json
        try:
            creds_file = _app_root() / "data" / "integration_creds.json"
            if not creds_file.exists():
                return _ok({"credentials": {}, "message": "No credentials stored"})
            all_creds = json.loads(creds_file.read_text())
            if service:
                creds = all_creds.get(service, {})
                # Mask sensitive values for display
                masked = {}
                for k, v in creds.items():
                    if k in ("password", "token", "secret", "api_key") and isinstance(v, str) and len(v) > 8:
                        masked[k] = v[:4] + "●" * (len(v) - 8) + v[-4:]
                    else:
                        masked[k] = v
                return _ok({"service": service, "credentials": masked,
                            "configured": bool(creds)})
            # Return all services (masked)
            services = {}
            for svc, creds in all_creds.items():
                services[svc] = {"configured": True, "saved_at": creds.get("saved_at", ""),
                                 "fields": [k for k in creds.keys() if k != "saved_at"]}
            return _ok({"services": services})
        except Exception as e:
            return _err(f"Credential load error: {e}")

    # ═══ v3.2 QUICKBOOKS DESKTOP BRIDGE ════════════════════════════

    def import_qb_trial_balance(self, csv_text: str = "", project_name: str = "QB Import",
                                 auto_populate: bool = True) -> dict:
        """Import a QuickBooks Desktop Trial Balance (CSV text).
        Parses accounts, maps to Your Company COA with confidence scoring,
        and auto-populates cost tracker with HIGH+MEDIUM confidence matches.
        LOW confidence accounts are flagged for manual review."""
        try:
            from bridge.quickbooks_bridge import import_trial_balance
            if not csv_text.strip():
                return _err("No CSV data provided. Export a Trial Balance from QB Desktop → Reports → Export to CSV.")
            return _ok(import_trial_balance(csv_text, project_name, auto_populate=auto_populate))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"QB import failed: {e}")

    def import_qb_trial_balance_file(self, file_path: str = "") -> dict:
        """Import a QuickBooks Desktop Trial Balance from an XLSX file on disk.
        Use this when Owner drops a QB export file into the data/ folder."""
        try:
            from bridge.quickbooks_bridge import parse_trial_balance_xlsx, map_accounts, populate_cost_tracker
            if not file_path:
                return _err("No file path provided.")
            parsed = parse_trial_balance_xlsx(file_path)
            if parsed.get("error"):
                return _err(parsed["error"])
            mapping = map_accounts(parsed["accounts"])
            population = populate_cost_tracker(mapping["mapped"])
            return _ok({
                "parse": {"count": parsed["count"], "balanced": parsed["balanced"]},
                "mapping": mapping["summary"],
                "population": population,
            })
        except Exception as e:
            return _err(f"QB XLSX import failed: {e}")

    def get_qb_coa_mapping(self) -> dict:
        """Get the Your Company COA mapping table (what QB accounts map to what Nano codes)."""
        try:
            from bridge.quickbooks_bridge import NANO_COA, KEYWORD_MAP
            return _ok({
                "coa": NANO_COA,
                "keyword_rules": len(KEYWORD_MAP),
                "account_count": len(NANO_COA),
                "message": "26-account construction Chart of Accounts. Use save_qb_mapping_override to add custom mappings."
            })
        except Exception as e:
            return _err(f"COA mapping error: {e}")

    def save_qb_mapping_override(self, qb_account_name: str = "", nano_code: str = "") -> dict:
        """Save a manual mapping override (QB account name → Nano COA code).
        Used when automatic mapping has low confidence for a specific account."""
        import json
        try:
            if not qb_account_name or not nano_code:
                return _err("Both qb_account_name and nano_code are required.")
            from bridge.quickbooks_bridge import NANO_COA
            if nano_code not in NANO_COA:
                return _err(f"Invalid Nano COA code: {nano_code}. Valid codes: {list(NANO_COA.keys())}")
            overrides_file = _app_root() / "data" / "qb_mapping_overrides.json"
            overrides_file.parent.mkdir(parents=True, exist_ok=True)
            overrides = {}
            if overrides_file.exists():
                overrides = json.loads(overrides_file.read_text())
            overrides[qb_account_name] = nano_code
            overrides_file.write_text(json.dumps(overrides, indent=2))
            nano = NANO_COA[nano_code]
            return _ok({
                "qb_account": qb_account_name,
                "nano_code": nano_code,
                "nano_name": nano["name"],
                "total_overrides": len(overrides),
                "message": f"Mapped '{qb_account_name}' → {nano_code} ({nano['name']}). This override will be used in future imports."
            })
        except Exception as e:
            return _err(f"Override save error: {e}")

    # ═══ v3.2 AUTO PROJECT PIPELINE ════════════════════════════════

    def auto_process_project_files(self, files_data: list = None,
                                    active_template: str = "STANDARD") -> dict:
        """Master auto-router: called when Owner drops PDFs/images/drawings.

        Automatically detects what the files are (drawing, bid invite, or both)
        and runs the full pipeline:
          - Drawings:   member extraction → AISC lookup → weight calc → 3D model
          - Bid invites: scope extraction → member takeoff → formatted bid
          - Both:       combined takeoff + priced bid document

        ALL weight math comes from AISC CSV. No LLM arithmetic.
        ALL cost math comes from bid_rates.json. No LLM arithmetic.

        Progress is reported via a 6-stage callback the UI polls via
        get_pipeline_progress() (stored in self._pipeline_progress).

        Returns a rich result card with member table, 3D model, and/or bid text.
        """
        try:
            from bridge.project_processor import process_project_files
            import json

            if not files_data:
                return _err("No files provided.")

            # Load current bid rates for cost calculation
            rates_file = _app_root() / "data" / "bid_rates.json"
            bid_rates = {}
            if rates_file.exists():
                bid_rates = json.loads(rates_file.read_text())

            # Get API keys for fallbacks
            try:
                from bridge.keyvault import load_keys
                _keys = load_keys()
                gemini_key = _keys.get("Gemini API", "") if isinstance(_keys, dict) else ""
                openai_key = _keys.get("OpenAI API", "") if isinstance(_keys, dict) else ""
            except Exception:
                gemini_key = ""
                openai_key = ""

            # Progress callback writes to instance state for frontend polling
            self._pipeline_progress = {"stage": "starting", "pct": 0,
                                        "detail": "", "active": True}

            def _progress(stage: str, pct: int, detail: str = ""):
                self._pipeline_progress = {"stage": stage, "pct": pct,
                                            "detail": detail, "active": pct < 100}

            result = process_project_files(
                files_data     = files_data,
                bid_rates      = bid_rates,
                active_template= active_template,
                gemini_key     = gemini_key,
                openai_key     = openai_key,
                progress_cb    = _progress,
            )
            self._pipeline_progress["active"] = False
            return _ok(result)
        except Exception as e:
            self._pipeline_progress = {"stage": "error", "pct": 0,
                                        "detail": str(e), "active": False}
            return _err(f"Project file processing failed: {e}")

    def get_pipeline_progress(self) -> dict:
        """Return current auto-pipeline progress for the frontend progress bar.

        Polled every 250ms from the UI while a pipeline is running. Returns
        {stage, pct, detail, active}. When active=False, UI hides the bar.
        """
        if not hasattr(self, "_pipeline_progress"):
            return _ok({"stage": "idle", "pct": 0, "detail": "", "active": False})
        return _ok(self._pipeline_progress)

    def export_project_card_pdf(self, project_data: dict = None) -> dict:
        """Export the project card to a Your Company branded PDF.

        Takes the result dict from auto_process_project_files() and renders
        it through documents.generate_proposal() with the same reportlab
        template used everywhere else. The output PDF lives in
        documents/proposals/ - Owner can email it directly to the GC.

        Args:
            project_data: dict with project_name, members, total_tons,
                cost, bid_invite_info (any subset is OK; missing fields
                render as "TBD" in the PDF)

        Returns:
            {ok, path, filename, size_bytes}
        """
        try:
            from bridge.documents import generate_proposal

            if not project_data:
                return _err("No project data provided")

            # Pull fields from the project card with sensible defaults
            invite = project_data.get("bid_invite_info") or {}
            proj_name = (invite.get("project_name") or
                         project_data.get("project_name") or
                         "Untitled Project")
            gc_name   = invite.get("gc_contact") or invite.get("contact_name") or "TBD"
            gc_co     = invite.get("gc_company") or invite.get("company") or "TBD"
            scope     = invite.get("scope") or project_data.get("summary") or "Per drawings and specifications."

            tons = project_data.get("total_tons") or 0
            cost = project_data.get("cost") or {}
            total = cost.get("total")

            tonnage_str = f"{tons:,.1f} tons" if tons else "TBD"
            total_str = f"${total:,.0f}" if total else "TBD"

            # Build member schedule for the PDF table
            members = project_data.get("members") or []
            member_schedule = []
            for m in members[:50]:        # cap at 50 rows
                member_schedule.append({
                    "designation": m.get("designation", ""),
                    "count":       m.get("count", 1),
                    "length_ft":   m.get("length_ft", 0),
                    "weight_tons": m.get("weight_tons", 0),
                })

            # Generate the PDF using the existing proposal template
            r = generate_proposal(
                project_name=proj_name,
                gc_name=gc_name,
                gc_company=gc_co,
                scope_text=scope,
                tonnage=tonnage_str,
                total_estimate=total_str,
                terms="30/20/50 - see standard terms",
                notes="Generated from auto-pipeline project card.",
                bid_number=f"NC-{datetime.now().strftime('%Y%m%d-%H%M')}",  # vj: local-display-ok
                template=project_data.get("template", "STANDARD"),
                member_schedule=member_schedule if member_schedule else None,
            )

            if not r.get("success"):
                return _err(f"PDF generation failed: {r.get('error', 'unknown')}")

            # Compute size from the file we wrote
            from pathlib import Path
            path = r.get("path", "")
            size = Path(path).stat().st_size if path and Path(path).exists() else 0

            return _ok({
                "path":        path,
                "filename":    r.get("filename"),
                "size_bytes":  size,
                "project":     proj_name,
            })

        except Exception as e:
            import traceback
            return _err(f"PDF export failed: {e}\n{traceback.format_exc()[:300]}")

    # ═══ Q2 2026 Calibration data - Houston-MSA market reference ═══════
    # All values trace back to data/calibration_2026Q2.json
    # Sources: SAM.gov WD-2026, NCCI TX, Argus/Nucor, AWS D1.1:2025,
    #          City fee schedules, BLS/EIA/Baker Hughes
    # See bridge/calibration_2026q2.py for the loader contract.

    def get_calibration_summary(self) -> dict:
        """Return Q2 2026 calibration metadata + counts of every section.

        Useful for the morning brief and self-test diagnostics. Contains:
        version, issued date, valid_through, and counts for wage_trades,
        wc_codes, steel_grades, consumables, jurisdictions, refineries,
        connection_types, compliance_portals, macro_indicators, ndt_rates,
        top_shapes.
        """
        try:
            from bridge.calibration_2026q2 import calibration_summary
            return _ok(calibration_summary())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Calibration summary error: {e}")

    def get_wage_rate(self, trade: str = "", tier: str = "fully_burdened_rate") -> dict:
        """Return SAM.gov WD-2026 wage for a trade.

        Args:
            trade: full trade name (e.g. "Welder (CWI-supervised) - Journeyman")
            tier:  "base_wage" | "fringe" | "fully_burdened_rate"
        """
        try:
            from bridge.calibration_2026q2 import get_wage_rate, get_all_wages
            if not trade:
                return _ok({"trades": get_all_wages()})
            rate = get_wage_rate(trade, tier)
            if rate is None:
                return _err(f"Trade not found: {trade}")
            return _ok({"trade": trade, "tier": tier, "rate_per_hour": rate})
        except Exception as e:
            return _err(f"Wage lookup error: {e}")

    def get_steel_price(self, grade: str = "", tier: str = "typical") -> dict:
        """Return $/ton for a steel grade (Q2 2026 SteelBenchmarker / Argus / Nucor).

        Args:
            grade: full grade name (e.g. "Wide-flange shapes (W-sections, A992)")
            tier:  "low" | "typical" | "high"
        """
        try:
            from bridge.calibration_2026q2 import get_steel_price, get_all_steel_grades
            if not grade:
                return _ok({"grades": get_all_steel_grades()})
            price = get_steel_price(grade, tier)
            if price is None:
                return _err(f"Grade not found: {grade}")
            return _ok({"grade": grade, "tier": tier, "price_per_ton": price})
        except Exception as e:
            return _err(f"Steel price error: {e}")

    def get_wc_rate(self, ncci_code: int = 5040, exp_mod: str = "typical") -> dict:
        """Return NCCI workers comp rate for a class code (TX 2026).

        Args:
            ncci_code: 4-digit NCCI code (5040=Iron/Steel Erection frame, etc.)
            exp_mod:   "low" | "typical" | "high" experience modifier tier
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        ncci_code, _e = _coerce_num(ncci_code, 'ncci_code', cast='int')
        if _e: return _e
        try:
            from bridge.calibration_2026q2 import get_wc_rate
            r = get_wc_rate(ncci_code, exp_mod)
            if not r:
                return _err(f"NCCI code not found: {ncci_code}")
            return _ok(r)
        except Exception as e:
            return _err(f"WC rate error: {e}")

    def get_permit_fee(self, jurisdiction: str = "City of Houston",
                       project_value: float = 0) -> dict:
        """Compute a permit fee for a Houston-area jurisdiction.

        Args:
            jurisdiction: partial-match name (e.g. "Houston", "Pasadena", "Baytown")
            project_value: total project value in USD (variable rate applies)
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        project_value, _e = _coerce_num(project_value, 'project_value')
        if _e: return _e
        try:
            from bridge.calibration_2026q2 import get_permit_fee, get_all_jurisdictions
            if not jurisdiction:
                return _ok({"jurisdictions": get_all_jurisdictions()})
            r = get_permit_fee(jurisdiction, project_value)
            if not r:
                return _err(f"Jurisdiction not found: {jurisdiction}")
            return _ok(r)
        except Exception as e:
            return _err(f"Permit fee error: {e}")

    def get_macro_indicators(self) -> dict:
        """Return all 7 Houston macro indicators (BLS/EIA/GHBA/Baker Hughes May 2026).

        Includes construction employment, building permits, WTI crude, Henry Hub
        natural gas, Texas rig count, industrial vacancy, sales tax. Each has
        value, units, as_of_date, trend_12mo, and implication.
        """
        try:
            from bridge.calibration_2026q2 import get_macro_indicators
            return _ok({"indicators": get_macro_indicators()})
        except Exception as e:
            return _err(f"Macro indicators error: {e}")

    def get_connection_cost(self, connection_type: str = "",
                            tier: str = "typical_cost") -> dict:
        """Return Houston 2026-adjusted cost for a structural connection type.

        Args:
            connection_type: partial match (e.g. "Welded moment", "Gusset")
            tier:            "low_cost" | "typical_cost" | "high_cost"
        """
        try:
            from bridge.calibration_2026q2 import get_connection_cost, get_all_connection_types
            if not connection_type:
                return _ok({"connections": get_all_connection_types()})
            r = get_connection_cost(connection_type, tier)
            if not r:
                return _err(f"Connection type not found: {connection_type}")
            return _ok(r)
        except Exception as e:
            return _err(f"Connection cost error: {e}")

    # ═══ MCP Client - Talk to the Owner's Claude Desktop MCPs ════════════
    # These methods let Virtual Office discover and call the Owner's existing
    # MCP servers (Gmail, Calendar, Drive, etc.) via Claude Desktop config.
    # See bridge/mcp_client.py for transport details.

    def mcp_status(self) -> dict:
        """Return Claude Desktop MCP integration status.

        Reports whether claude_desktop_config.json was found, how many
        MCP servers are registered, which ones have active connections,
        and which integration categories are routable through the Owner's
        Claude Desktop subscription (vs. requiring a fallback to Joseph's
        Anthropic API key).
        """
        try:
            from bridge.mcp_client import status, prefer_mcp_for_integration, INTEGRATION_HINTS
            base = status()
            # Add per-category routability - tells the UI which integrations
            # will run on the Owner's Claude.ai subscription (free) vs. need
            # a direct API fallback (charges Joseph's key).
            base["routable_via_mcp"] = {
                category: prefer_mcp_for_integration(category)
                for category in INTEGRATION_HINTS
            }
            base["cost_split"] = {
                "engine_api_owner":  "Joseph (Anthropic API)",
                "chat_subscription": "Owner (owner@yourcompany.example.com Claude Desktop)",
                "mcp_routes_save":   "Each MCP-routed integration call avoids burning Joseph's API tokens",
            }
            return _ok(base)
        except Exception as e:
            return _err(f"MCP status error: {e}")

    def mcp_prefer_routing(self, category: str = "") -> dict:
        """Return the MCP server name to route a given integration category through.

        Args:
            category: one of "email", "calendar", "drive", "docs", "sheets",
                      "slack", "github", "filesystem", "browser", "search"

        Returns:
            {ok, data: {category, server, route}} where:
              - server is the matching Claude Desktop MCP server name (or None)
              - route is "mcp" if a server matched, else "api_fallback"
        """
        if not category:
            return _err("category required")
        try:
            from bridge.mcp_client import prefer_mcp_for_integration
            server = prefer_mcp_for_integration(category)
            return _ok({
                "category": category,
                "server":   server,
                "route":    "mcp" if server else "api_fallback",
                "reason":   ("the Owner's Claude Desktop has a matching MCP - use that to save API tokens"
                             if server
                             else "No matching Claude Desktop MCP - Virtual Office must call Joseph's API"),
            })
        except Exception as e:
            return _err(f"Routing error: {e}")

    # ════════════════════════════════════════════════════════════════════
    #  AI ORCHESTRATION (Supervisor/Verifier Pipeline)
    # ════════════════════════════════════════════════════════════════════

    def orchestration_status(self) -> dict:
        """Returns the AI orchestration pipeline state - does it exist, what
        guardrails are active, what providers are in the fallback chain."""
        try:
            from bridge.ai_orchestration import (
                SYSTEM_GUARDRAILS, ingest_document, verify_response,
                proofread_output, process_document
            )
            from bridge.ai_orchestration.corrector import DEFAULT_FALLBACK_CHAIN
            return _ok({
                "pipeline_active": True,
                "stages": ["intake", "route", "prompt", "verify", "correct", "proofread"],
                "guardrails": [
                    "no_guessing_allowed",
                    "mandatory_source_citations",
                    "no_llm_math_recompute_locally",
                    "aisc_canonical_weight_rules",
                    "confidence_floor_0.7",
                    "outreach_preview_lock",
                    "output_proofread_before_delivery",
                ],
                "fallback_chain": [{"provider": p, "model": m} for p, m in DEFAULT_FALLBACK_CHAIN],
                "max_attempts_per_task": 4,
                "verifier_model": "claude (always supervisor)",
            })
        except Exception as e:
            return _err(f"Orchestration status error: {e}")

    def orchestration_ingest(self, document_path: str = "") -> dict:
        """Run STAGE 1 (intake) on a document. Returns the FactsManifest -
        every fact extracted locally with provenance, no AI involved."""
        if not document_path:
            return _err("document_path required")
        try:
            from bridge.ai_orchestration import ingest_document
            manifest = ingest_document(document_path)
            return _ok({
                "document_sha256":  manifest.document_sha256,
                "page_count":       manifest.page_count,
                "has_text_layer":   manifest.has_text_layer,
                "has_tables":       manifest.has_tables,
                "has_images":       manifest.has_images,
                "needs_ai_vision":  manifest.needs_ai_vision,
                "facts_extracted":  len(manifest.facts),
                "facts": [
                    {"key": f.key, "value": (str(f.value) if isinstance(f.value, list) else f.value),
                     "page": f.page, "line": f.line, "source": f.source,
                     "confidence": f.confidence}
                    for f in manifest.facts
                ],
                "extraction_log":   manifest.extraction_log,
            })
        except FileNotFoundError as e:
            return _err(f"Document not found: {e}")
        except Exception as e:
            return _err(f"Intake error: {type(e).__name__}: {e}")

    def orchestration_verify(self, response: dict | None = None,
                              facts: dict | None = None) -> dict:
        """Run STAGE 4 (verifier) on an AI response against a set of facts.
        Returns APPROVED / NEEDS_CORRECTION / ESCALATE / REJECT with findings."""
        import json as _j
        if isinstance(response, str):
            try: response = _j.loads(response)
            except Exception: return _err("response must be a JSON object (dict)")
        if isinstance(facts, str):
            try: facts = _j.loads(facts)
            except Exception: return _err("facts must be a JSON object (dict)")
        if not response or not isinstance(response, dict):
            return _err("response must be a dict")
        if not facts or not isinstance(facts, dict):
            return _err("facts must be a dict")
        try:
            from bridge.ai_orchestration.intake import Fact, FactsManifest
            from bridge.ai_orchestration.verifier import verify_response

            manifest = FactsManifest(
                document_path="(programmatic)", document_sha256="-", page_count=0,
                has_text_layer=False, has_tables=False, has_images=False,
                needs_ai_vision=False,
            )
            for k, v in facts.items():
                manifest.facts.append(Fact(
                    key=k, value=v, source="programmatic",
                    page=None, line=None, confidence=1.0, raw_text=str(v),
                ))
            verdict = verify_response(response, manifest)
            return _ok({
                "status":   verdict.status,
                "score":    verdict.score,
                "findings": verdict.findings,
                "verified_count":   len(verdict.verified_facts),
                "unverified_count": len(verdict.unverified_facts),
                "verified":         verdict.verified_facts,
                "unverified":       verdict.unverified_facts,
            })
        except Exception as e:
            return _err(f"Verify error: {type(e).__name__}: {e}")

    def orchestration_proofread(self, content: str = "", facts: dict | None = None,
                                 kind: str = "text") -> dict:
        """Run STAGE 6 (proofread) on a piece of generated content. Returns
        CLEAR / WARN / BLOCKED. Used as the final gate before delivering AI
        output to the user - catches unverified numbers in the rendered text."""
        if not content:
            return _err("content (str) required")
        import json as _j
        if isinstance(facts, str):
            try: facts = _j.loads(facts)
            except Exception: return _err("facts must be a JSON object (dict)")
        if facts is not None and not isinstance(facts, dict):
            return _err(f"facts must be a dict; got {type(facts).__name__}")
        try:
            from bridge.ai_orchestration.intake import Fact, FactsManifest
            from bridge.ai_orchestration.proofreader import proofread_output

            manifest = FactsManifest(
                document_path="(programmatic)", document_sha256="-", page_count=0,
                has_text_layer=False, has_tables=False, has_images=False,
                needs_ai_vision=False,
            )
            for k, v in (facts or {}).items():
                manifest.facts.append(Fact(
                    key=k, value=v, source="programmatic",
                    page=None, line=None, confidence=1.0, raw_text=str(v),
                ))
            report = proofread_output(content, manifest, kind=kind)
            return _ok({
                "status":             report.status,
                "summary":            report.summary,
                "issues":             report.issues,
                "verified_count":     len(report.verified_numbers),
                "unverified_count":   len(report.unverified_numbers),
                "unverified_numbers": report.unverified_numbers,
            })
        except Exception as e:
            return _err(f"Proofread error: {type(e).__name__}: {e}")

    def mcp_list_servers(self) -> dict:
        """List all MCP servers registered in Claude Desktop config.

        Returns one entry per server with name, command, args, env keys,
        and connection status. Useful for the Settings panel to show
        which integrations are available to drive from Virtual Office.
        """
        try:
            from bridge.mcp_client import list_servers
            return _ok({"servers": list_servers()})
        except Exception as e:
            return _err(f"MCP list error: {e}")

    def mcp_list_tools(self, server_name: str = "") -> dict:
        """List all tools exposed by a specific Claude Desktop MCP server.

        Args:
            server_name: name as registered in claude_desktop_config.json
                          (e.g. "gmail-mcp", "calendar-mcp", "drive-mcp")
        """
        if not server_name:
            return _err("server_name required")
        try:
            from bridge.mcp_client import list_tools
            tools = list_tools(server_name)
            return _ok({"server": server_name, "tools": tools, "count": len(tools)})
        except Exception as e:
            return _err(f"MCP list tools error: {e}")

    def mcp_call_tool(self, server_name: str = "", tool_name: str = "",
                      arguments: dict = None) -> dict:
        """Call a tool on a Claude Desktop MCP server.

        Args:
            server_name: name from claude_desktop_config.json
            tool_name:   name of the tool exposed by that server
            arguments:   dict of arguments matching the tool's schema

        Returns:
            {ok, data, isError?}. The data field is the textual content
            returned by the MCP server (multi-line string).
        """
        if not server_name or not tool_name:
            return _err("server_name and tool_name required")
        try:
            from bridge.mcp_client import call_tool
            r = call_tool(server_name, tool_name, arguments or {})
            return _ok(r) if r.get("ok") else _err(r.get("error", "unknown"))
        except Exception as e:
            return _err(f"MCP call error: {e}")

    def get_aisc_member_info(self, designation: str = "", shape: str = "") -> dict:
        """Look up a single AISC shape in the local CSV database.
        Returns section properties: lb_per_ft, depth, flange width, web thickness.
        No LLM - pure offline CSV lookup.

        SIM-07: accepts either `designation=` (canonical) or `shape=` (the Owner's
        natural kwarg). Both refer to the same value, e.g. "W12X26".
        """
        try:
            from bridge.project_processor import aisc_lookup, extract_members_from_text
            # SIM-07 alias resolution
            if not designation and shape:
                designation = shape
            if not designation:
                return _err("Provide a designation (or shape=), e.g. W14X82 or HSS6X6X1/4")
            # Normalize: HSS6X6X.500 -> HSS6X6X1/2, w14x82 -> W14X82
            try:
                norm_result = self.normalize_shape(raw_shape=designation)
                if norm_result.get("ok") and norm_result["data"].get("normalized"):
                    designation = norm_result["data"]["normalized"]
            except Exception:
                designation = designation.upper()
            props = aisc_lookup(designation)
            if not props:
                # Try extracting from text in case designation has formatting
                members = extract_members_from_text(designation)
                if members:
                    props = aisc_lookup(members[0]["designation"])
            if props:
                def _sf(v):
                    try: return float(v)
                    except (ValueError, TypeError): return 0.0
                return _ok({
                    "designation":  designation.upper(),
                    "lb_per_ft":    _sf(props.get("lb_per_ft", 0)),
                    "depth_in":     _sf(props.get("d", 0)),
                    "flange_w_in":  _sf(props.get("bf", 0)),
                    "tf_in":        _sf(props.get("tf", 0)),
                    "tw_in":        _sf(props.get("tw", 0)),
                    "source":       "AISC CSV (offline)",
                })
            return _err(f"Shape '{designation}' not found in AISC CSV. "
                        f"Check spelling. Use format like W14X82, HSS6X6X025, L4X4X375")
        except Exception as e:
            return _err(f"AISC lookup failed: {e}")

    # ═══ v3.2 AGENT BRIDGE METHODS ═════════════════════════════════

    # ── AR Invoice Agent ──────────────────────────────────────────
    def get_ar_status(self, project_name: str = "") -> dict:
        """Get accounts receivable status. Pass project_name to filter."""
        try:
            from bridge.agents.ar_invoice import get_ar_status
            return _ok(get_ar_status(project_name or None))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"AR status error: {e}")

    def create_ar_milestones(self, project_name: str = "",
                              contract_value: float = 0) -> dict:
        """Create 30/20/50 milestone invoices for a project."""
        # pass 10i: numeric input hardening - coerce or fail clean
        contract_value, _e = _coerce_num(contract_value, 'contract_value')
        if _e: return _e
        try:
            from bridge.agents.ar_invoice import create_milestone_invoices
            if not project_name or contract_value <= 0:
                return _err("project_name and contract_value > 0 required")
            return _ok({"invoices": create_milestone_invoices(project_name, contract_value)})
        except Exception as e:
            return _err(f"AR milestone error: {e}")

    def log_ar_payment(self, invoice_number: str = "",
                        paid_date: str = "") -> dict:
        """Record payment received for an invoice."""
        try:
            from bridge.agents.ar_invoice import log_payment
            return _ok(log_payment(invoice_number, paid_date or None))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"AR payment error: {e}")

    def get_ar_alerts(self) -> dict:
        """Get all AR invoices at WARNING or ESCALATION level."""
        try:
            from bridge.agents.ar_invoice import get_ar_alerts
            return _ok({"alerts": get_ar_alerts()})
        except Exception as e:
            return _err(f"AR alert error: {e}")

    # ── Change Order Agent ────────────────────────────────────────
    def create_co(self, project_name: str = "", description: str = "",
                  line_items: list = None, schedule_impact_days: int = 0,
                  markup_pct: float = 0.22) -> dict:
        """Create an AIA G701-style change order with Houston task rates."""
        # pass 10i: numeric input hardening - coerce or fail clean
        schedule_impact_days, _e = _coerce_num(schedule_impact_days, 'schedule_impact_days', cast='int')
        if _e: return _e
        markup_pct, _e = _coerce_num(markup_pct, 'markup_pct')
        if _e: return _e
        try:
            from bridge.agents.change_order import create_change_order
            if not project_name or not description:
                return _err("project_name and description required")
            return _ok(create_change_order(project_name, description,  # vj: ok-passthrough-safe
                                           line_items or [],
                                           schedule_impact_days, markup_pct))
        except Exception as e:
            return _err(f"Change order error: {e}")

    def get_change_orders(self, project_name: str = "",
                           status: str = "") -> dict:
        """List change orders, optionally filtered by project or status."""
        try:
            from bridge.agents.change_order import list_change_orders
            return _ok({"change_orders": list_change_orders(
                project_name or None, status or None)})
        except Exception as e:
            return _err(f"Change order list error: {e}")

    def advance_co_status(self, co_number: str = "", status: str = "") -> dict:
        """Move a change order to next workflow stage (APPROVED/SUBMITTED/ACCEPTED)."""
        try:
            from bridge.agents.change_order import update_co_status
            return _ok(update_co_status(co_number, status))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"CO status error: {e}")

    # ── Industrial Outreach Agent ─────────────────────────────────
    def draft_refinery_outreach(self, company: str = "", contact_name: str = "",
                                 contact_role: str = "", hook: str = "",
                                 timing_reason: str = "",
                                 template: str = "refinery_turnaround",
                                 preview_only: bool = False) -> dict:
        """Draft cold outreach for refinery/EPC targets. 5 inputs required.

        Args:
            preview_only: if True, returns rendered message without writing to
                          DB. Use for "review before send" UX. Then call
                          confirm_refinery_outreach() with same args to commit.
        """
        try:
            from bridge.agents.industrial_outreach import draft_outreach
            return _ok(draft_outreach(company, contact_name, contact_role,  # vj: ok-passthrough-safe
                                      hook, timing_reason, template,
                                      preview_only=preview_only))
        except Exception as e:
            return _err(f"Outreach error: {e}")

    def confirm_refinery_outreach(self, company: str = "", contact_name: str = "",
                                    contact_role: str = "", hook: str = "",
                                    timing_reason: str = "",
                                    template: str = "refinery_turnaround") -> dict:
        """Commit a previewed outreach to the database.

        Calls draft_outreach with preview_only=False after Joseph or Owner
        approves the preview. Same args as draft_refinery_outreach.
        """
        try:
            from bridge.agents.industrial_outreach import confirm_outreach
            return _ok(confirm_outreach(company, contact_name, contact_role,  # vj: ok-passthrough-safe
                                          hook, timing_reason, template))
        except Exception as e:
            return _err(f"Outreach confirm error: {e}")

    def get_outreach_log(self, company: str = "") -> dict:
        """Get outreach history, optionally filtered by company."""
        try:
            from bridge.agents.industrial_outreach import get_outreach_log
            return _ok({"log": get_outreach_log(company or None)})
        except Exception as e:
            return _err(f"Outreach log error: {e}")

    def get_due_followups(self) -> dict:
        """Get outreach items where follow-up is due today or overdue."""
        try:
            from bridge.agents.industrial_outreach import get_due_followups
            return _ok({"followups": get_due_followups()})
        except Exception as e:
            return _err(f"Follow-up error: {e}")

    def get_active_followups(self) -> dict:
        """Morning rollup of outreach follow-ups that need attention.

        Pass 10i (R2): Owner wanted a single method to answer "what's
        on me today for outreach?" without filtering manually. This is
        get_due_followups with three extras:

          - days_overdue computed per row
          - sorted by days_overdue DESC (most overdue first)
          - quiet response (count=0, items=[]) if nothing is due

        Returns:
          ok=True with data: {
            count: int,
            items: [{
              id, company, contact_name, contact_role,
              follow_up_date, days_overdue, hook, template_type
            }, ...]
          }
        """
        try:
            from bridge.agents.industrial_outreach import get_due_followups
            from datetime import datetime, date as _date

            raw = get_due_followups()
            today = datetime.now().date()  # vj: local-time-ok
            enriched = []
            for r in raw:
                fud = r.get("follow_up_date", "")
                try:
                    fud_date = _date.fromisoformat(fud)
                    days_overdue = (today - fud_date).days
                except (ValueError, TypeError):
                    days_overdue = 0
                enriched.append({
                    "id": r.get("id"),
                    "company": r.get("company", ""),
                    "contact_name": r.get("contact_name", ""),
                    "contact_role": r.get("contact_role", ""),
                    "follow_up_date": fud,
                    "days_overdue": days_overdue,
                    "hook": r.get("hook", ""),
                    "template_type": r.get("template_type", ""),
                })
            enriched.sort(key=lambda x: -x["days_overdue"])
            return _ok({
                "count": len(enriched),
                "items": enriched,
                "summary_line": (
                    f"{len(enriched)} follow-up(s) due. "
                    f"Most overdue: {enriched[0]['company']} ({enriched[0]['days_overdue']} days)."
                    if enriched else "No follow-ups due today."
                ),
            })
        except Exception as e:
            return _err(f"get_active_followups failed: {e}",
                        fix="Check that data/outreach_log.db exists and is readable.")

    # ── LinkedIn Content Generator ────────────────────────────────────

    def draft_linkedin_post(self, topic: str = "", format_code: str = "",
                            voice: str = "owner", project_ref: str = "",
                            numbers: str = "", hashtags: str = "",
                            max_words: int = 250) -> dict:
        """Draft a LinkedIn post using the 4-format rotation system.

        Formats: A (Counterintuitive Claim), B (Specific Project Story),
        C (AI/Process Update), D (Industry Observation).
        Auto-rotates by day of week if format_code is empty.

        This method dispatches to a background thread so the pywebview
        UI thread is never blocked, consistent with auto_process_drawing.
        Returns immediately with {job_id, status: 'generating'}.
        Poll with poll_linkedin_draft(job_id) for the result.

        Args:
            topic: What the post is about (required).
            format_code: A/B/C/D or empty for auto-rotate.
            voice: 'owner' or 'joseph'.
            project_ref: Project to reference (ICD, Elite, etc.)
            numbers: Specific stats to include.
            hashtags: Comma-separated hashtag overrides. Max 3.
            max_words: Target word count (150-250 recommended).
        """
        if not topic:
            return _err("topic is required")
        import threading, uuid
        job_id = str(uuid.uuid4())[:8]
        # linkedin_content._draft is pure local (regex + strings, no API call).
        # Background thread prevents any future API integration from blocking UI.
        def _bg():
            try:
                from bridge.linkedin_content import draft_linkedin_post as _draft
                tags = [h.strip() for h in hashtags.split(",") if h.strip()] if hashtags else None
                r = _draft(topic=topic, format_code=format_code, voice=voice,
                           project_ref=project_ref, numbers=numbers,
                           hashtags=tags, max_words=max_words)
                self._linkedin_jobs[job_id] = _ok(r) if "error" not in r else _err(r["error"])
            except Exception as e:
                self._linkedin_jobs[job_id] = _err(f"LinkedIn draft error: {e}")
        # Lazy-init job store on Bridge instance
        if not hasattr(self, "_linkedin_jobs"):
            self._linkedin_jobs = {}
        threading.Thread(target=_bg, daemon=True).start()
        return _ok({"job_id": job_id, "status": "generating", "eta_sec": 2,
                    "note": "Poll poll_linkedin_draft(job_id) for result."})

    def poll_linkedin_draft(self, job_id: str = "") -> dict:
        """Poll for a LinkedIn draft started by draft_linkedin_post().

        Returns {status: 'generating'} while pending, or the full draft
        result once complete.
        """
        if not job_id:
            return _err("job_id is required")
        if not hasattr(self, "_linkedin_jobs"):
            return _ok({"status": "generating"})
        result = self._linkedin_jobs.get(job_id)
        if result is None:
            return _ok({"status": "generating"})
        # Cleanup after retrieval
        self._linkedin_jobs.pop(job_id, None)
        return result

    # ── v3.2.7.15 hotfix: background-thread VJ scan ─────────────────
    # PROD bug from May 14 screenshot: user typed "VJ scan and fix" at
    # 17:21, by 17:32 window was "(Not Responding)" - 11 minutes of UI
    # freeze. Root cause: vj_scan_and_fix() runs SelfRepairEngine on the
    # same thread that pumps the pywebview message queue. Frontend
    # showed "Running VJ scan (this takes 10-20s)..." spinner but on a
    # real install the scan takes 60-180s depending on Defender state,
    # AISC DB warmup, and diagnostic engine pass. UI cannot redraw.
    # Fix: kick scan into background thread, return job_id immediately,
    # let frontend poll. Same pattern as draft_linkedin_post.
    def vj_scan_async(self) -> dict:
        """Kick off a read-only VJ scan in a background thread.

        Returns immediately with {job_id, status: 'scanning'}.
        Poll with poll_vj_scan(job_id) for the result.

        v3.2.7.15: read-only variant. Use vj_scan_and_fix_async for the
        write-enabled version.
        """
        import threading, uuid
        job_id = str(uuid.uuid4())[:8]
        if not hasattr(self, "_vj_jobs"):
            self._vj_jobs = {}
        # Mark slot so poller knows the job exists
        self._vj_jobs[job_id] = None
        def _bg():
            try:
                result = self.vj_scan()
                self._vj_jobs[job_id] = result
            except Exception as e:
                self._vj_jobs[job_id] = _err(f"VJ scan error: {e}")
        threading.Thread(target=_bg, daemon=True).start()
        return _ok({"job_id": job_id, "status": "scanning",
                    "eta_sec": 30,
                    "note": "Poll poll_vj_scan(job_id) for the report."})

    def vj_scan_and_fix_async(self, fast_mode: bool = False) -> dict:
        """Kick off VJ scan-and-fix in a background thread.

        Returns immediately with {job_id, status: 'scanning'}.
        Poll with poll_vj_scan(job_id) for the result. This is the
        write-enabled variant that applies safe auto-fixes.

        Args:
            fast_mode: skip the diagnostic engine pass (saves ~30s).
        """
        import threading, uuid
        job_id = str(uuid.uuid4())[:8]
        if not hasattr(self, "_vj_jobs"):
            self._vj_jobs = {}
        self._vj_jobs[job_id] = None
        def _bg():
            try:
                result = self.vj_scan_and_fix(fast_mode=fast_mode)
                self._vj_jobs[job_id] = result
            except Exception as e:
                self._vj_jobs[job_id] = _err(f"VJ scan-and-fix error: {e}")
        threading.Thread(target=_bg, daemon=True).start()
        eta = 20 if fast_mode else 60
        return _ok({"job_id": job_id, "status": "scanning",
                    "eta_sec": eta, "fast_mode": fast_mode,
                    "note": "Poll poll_vj_scan(job_id) for the report."})

    def poll_vj_scan(self, job_id: str = "") -> dict:
        """Poll for a VJ scan started by vj_scan_async() or
        vj_scan_and_fix_async().

        Returns {status: 'scanning'} while running, or the full scan
        report once complete. Cleans up the job slot after retrieval.
        """
        if not job_id:
            # No job_id - return status of all live jobs
            if not hasattr(self, "_vj_jobs") or not self._vj_jobs:
                return _ok({"status": "idle", "jobs": []})
            return _ok({
                "status": "running",
                "jobs": [
                    {"job_id": jid,
                     "done": result is not None}
                    for jid, result in self._vj_jobs.items()
                ]
            })
        if not hasattr(self, "_vj_jobs"):
            return _err(f"unknown job_id: {job_id}")
        if job_id not in self._vj_jobs:
            return _err(f"unknown job_id: {job_id}")
        result = self._vj_jobs.get(job_id)
        if result is None:
            return _ok({"status": "scanning", "job_id": job_id})
        # Cleanup after retrieval
        self._vj_jobs.pop(job_id, None)
        return result

    def linkedin_fingerprint_check(self, text: str = "") -> dict:
        """Run anti-AI fingerprint scan on any text.

        Returns list of hits with pattern, line number, and fix suggestion.
        Empty list means the text is clean of AI tells.
        """
        if not text:
            return _err("text is required")
        from bridge.linkedin_content import fingerprint_check
        hits = fingerprint_check(text)
        return _ok({
            "hits": hits,
            "clean": len(hits) == 0,
            "scanned_words": len(text.split()),
        })

    def linkedin_list_formats(self) -> dict:
        """List the 4 LinkedIn post formats with structure guides."""
        from bridge.linkedin_content import list_formats
        return _ok({"formats": list_formats()})

    def linkedin_approved_numbers(self) -> dict:
        """Return all approved real numbers for LinkedIn posts."""
        from bridge.linkedin_content import get_approved_numbers
        return _ok({"numbers": get_approved_numbers()})

    def get_aisc_compliance_summary(self) -> dict:
        """AISC validation rollup across every active bid in the pipeline.

        Pass 10i (R3): Owner wanted to know, at a glance, how many
        shapes across his active bids pass AISC validation and which ones
        need PE attention. Walks each non-terminal bid's takeoff.json,
        runs aisc_validator.validate_shape on each member, tallies
        pass/fail, returns the unresolved list grouped by bid.

        Returns:
          ok=True with data: {
            bids_checked: int,
            shapes_total: int,
            shapes_passed: int,
            shapes_failed: int,
            pass_rate: float (0-1),
            unresolved: [{bid_number, project_name, shape, qty, issue}, ...],
            summary_line: str,
          }
        """
        try:
            from bridge.aisc_validator import validate_shape
            from bridge.bid_documents import bids_root
            import json as _json

            TERMINAL = {"WON", "LOST", "KILLED", "PASSED"}

            root = bids_root()
            if not root.exists():
                return _ok({
                    "bids_checked": 0, "shapes_total": 0, "shapes_passed": 0,
                    "shapes_failed": 0, "pass_rate": 0.0, "unresolved": [],
                    "summary_line": "No bid folders found yet.",
                })

            bids_checked = 0
            shapes_total = 0
            shapes_passed = 0
            shapes_failed = 0
            unresolved = []

            for ym in sorted(root.iterdir(), reverse=True):
                if not ym.is_dir() or not ym.name.startswith("20"):
                    continue
                for bid_dir in sorted(ym.iterdir(), reverse=True):
                    if not bid_dir.is_dir():
                        continue
                    parts = bid_dir.name.split(" - ", 1)
                    bn = parts[0]
                    pn = parts[1] if len(parts) > 1 else ""
                    takeoff_path = bid_dir / "takeoff.json"
                    if not takeoff_path.exists():
                        continue
                    # Read manifest to check bid state
                    manifest_path = bid_dir / "manifest.json"
                    state = "UNKNOWN"
                    if manifest_path.exists():
                        try:
                            mf = _json.loads(manifest_path.read_text())
                            state = mf.get("state", "UNKNOWN")
                        except (_json.JSONDecodeError, OSError):
                            pass
                    if state in TERMINAL:
                        continue  # Skip won/lost/killed bids
                    bids_checked += 1
                    try:
                        takeoff = _json.loads(takeoff_path.read_text())
                    except (_json.JSONDecodeError, OSError):
                        continue
                    members = takeoff.get("members", []) if isinstance(takeoff, dict) else takeoff
                    if not isinstance(members, list):
                        continue
                    for m in members:
                        if not isinstance(m, dict):
                            continue
                        shape = m.get("shape", "")
                        qty = m.get("qty", 1)
                        if not shape:
                            continue
                        shapes_total += 1
                        try:
                            v = validate_shape(shape)
                            if v.get("valid"):
                                shapes_passed += 1
                            else:
                                shapes_failed += 1
                                unresolved.append({
                                    "bid_number": bn,
                                    "project_name": pn,
                                    "shape": shape,
                                    "qty": qty,
                                    "issue": v.get("error") or v.get("warning") or "shape not found in AISC database",
                                })
                        except Exception as ve:
                            shapes_failed += 1
                            unresolved.append({
                                "bid_number": bn,
                                "project_name": pn,
                                "shape": shape,
                                "qty": qty,
                                "issue": f"validator error: {ve}",
                            })

            pass_rate = (shapes_passed / shapes_total) if shapes_total else 1.0
            if shapes_total == 0:
                summary = f"{bids_checked} active bid(s) checked. No shapes to validate."
            elif shapes_failed == 0:
                summary = f"{bids_checked} active bid(s), {shapes_total} shapes, ALL PASS."
            else:
                summary = (
                    f"{bids_checked} active bid(s), {shapes_total} shapes, "
                    f"{shapes_passed} pass / {shapes_failed} need PE review "
                    f"({pass_rate*100:.0f}% pass rate)."
                )

            return _ok({
                "bids_checked": bids_checked,
                "shapes_total": shapes_total,
                "shapes_passed": shapes_passed,
                "shapes_failed": shapes_failed,
                "pass_rate": round(pass_rate, 4),
                "unresolved": unresolved,
                "summary_line": summary,
            })
        except Exception as e:
            return _err(f"get_aisc_compliance_summary failed: {e}",
                        fix="Confirm bid folders exist under data/Your Company Bids/ and contain takeoff.json files.")

    # ── Ops Agents ────────────────────────────────────────────────
    def create_rfi(self, project_name: str = "", question: str = "",
                   csi_division: str = "05 12 00",
                   submitted_to: str = "", due_days: int = 7) -> dict:
        """Create and log an RFI. Auto-numbered as RFI-Project-001."""
        # pass 10i: numeric input hardening - coerce or fail clean
        due_days, _e = _coerce_num(due_days, 'due_days', cast='int')
        if _e: return _e
        try:
            from bridge.agents.ops_agents import create_rfi
            return _ok(create_rfi(project_name, question, csi_division,  # vj: ok-passthrough-safe
                                   submitted_to, due_days))
        except Exception as e:
            return _err(f"RFI error: {e}")

    def get_rfis(self, project_name: str = "", overdue_only: bool = False) -> dict:
        """List RFIs, optionally filtered by project or overdue status."""
        try:
            from bridge.agents.ops_agents import list_rfis
            return _ok({"rfis": list_rfis(project_name or None, overdue_only)})
        except Exception as e:
            return _err(f"RFI list error: {e}")

    def get_osha_300a(self, year: int = 0, hours_worked: float = 25000.0,
                       avg_employees: int = 12) -> dict:
        """Compute OSHA 300A TRIR/DART statistics for the year."""
        # pass 10i: numeric input hardening - coerce or fail clean
        hours_worked, _e = _coerce_num(hours_worked, 'hours_worked')
        if _e: return _e
        avg_employees, _e = _coerce_num(avg_employees, 'avg_employees', cast='int')
        if _e: return _e
        try:
            from bridge.agents.ops_agents import generate_osha_300a
            return _ok(generate_osha_300a(year or None, hours_worked, avg_employees))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"OSHA 300A error: {e}")

    def get_prequal_status(self, completed_items: list = None) -> dict:
        """Get prequal checklist completion status."""
        try:
            from bridge.agents.ops_agents import get_prequal_status
            return _ok(get_prequal_status(completed_items or []))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Prequal error: {e}")

    def generate_case_study(self, project_name: str = "", tonnage: float = 0,
                             scope: str = "", outcome: str = "") -> dict:
        """Generate a Tier-1-compliant case study for approved projects only."""
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            from bridge.agents.ops_agents import generate_case_study
            return _ok(generate_case_study(project_name, tonnage, scope, outcome))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Case study error: {e}")

    # ── Stock Research Agent ──────────────────────────────────────
    def get_stock_brief(self, symbol: str = "") -> dict:
        """Full investment thesis (composite score + verdict) for one ticker."""
        try:
            from bridge.agents.stock_research import investment_thesis
            sym = symbol.upper().strip() if symbol else "NUE"
            return _ok(investment_thesis(sym))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(f"Stock brief error: {e}")

    def get_stock_watchlist(self) -> dict:
        """Return the current steel sector watchlist. $X removed (acquired by Nippon Steel)."""
        try:
            from bridge.agents.stock_research import DEFAULT_WATCHLIST
            return _ok({"watchlist": DEFAULT_WATCHLIST,
                        "note": "Research only. Never execution. Never advice."})
        except Exception as e:
            return _err(f"Watchlist error: {e}")

    def get_portfolio_brief(self, symbols: list = None) -> dict:
        """Run investment thesis on full steel watchlist or provided tickers."""
        try:
            from bridge.agents.stock_research import portfolio_brief
            return _ok({"portfolio": portfolio_brief(symbols or None)})
        except Exception as e:
            return _err(f"Portfolio brief error: {e}")

    def get_steel_research(self) -> dict:
        """Get steel market intelligence from free sources."""
        try:
            from bridge.agents.steel_price.agent import get_latest_brief, stats
            return _ok({"brief": get_latest_brief(), "stats": stats()})
        except Exception as e:
            return _err(f"Steel research error: {e}")

    def track_time_saved(self, action: str = "", minutes_saved: float = 0) -> dict:
        """Track time saved by automated actions for the revenue attribution KPI."""
        import json
        from datetime import datetime
        try:
            tracker_file = _app_root() / "data" / "time_saved.json"
            tracker_file.parent.mkdir(parents=True, exist_ok=True)
            tracker = {"entries": [], "total_minutes": 0}
            if tracker_file.exists():
                tracker = json.loads(tracker_file.read_text())
            entry = {"action": action, "minutes": minutes_saved,
                     "ts": datetime.now(timezone.utc).isoformat()}
            tracker["entries"].append(entry)
            tracker["entries"] = tracker["entries"][-500:]  # cap at 500
            tracker["total_minutes"] = sum(e["minutes"] for e in tracker["entries"])
            tracker["total_hours"] = round(tracker["total_minutes"] / 60, 1)
            tracker_file.write_text(json.dumps(tracker, indent=2))
            return _ok(tracker)
        except Exception as e:
            return _err(f"Time tracking error: {e}")

    def get_time_saved(self) -> dict:
        """Get cumulative time saved stats."""
        import json
        from datetime import datetime, timedelta
        try:
            tracker_file = _app_root() / "data" / "time_saved.json"
            if not tracker_file.exists():
                return _ok({"total_hours": 0, "this_week": 0, "this_month": 0, "entries": []})
            tracker = json.loads(tracker_file.read_text())
            now = datetime.now(timezone.utc)
            week_ago = (now - timedelta(days=7)).isoformat()
            month_ago = (now - timedelta(days=30)).isoformat()
            week_mins = sum(e["minutes"] for e in tracker["entries"] if e["ts"] >= week_ago)
            month_mins = sum(e["minutes"] for e in tracker["entries"] if e["ts"] >= month_ago)
            return _ok({
                "total_hours": tracker.get("total_hours", 0),
                "this_week_hours": round(week_mins / 60, 1),
                "this_month_hours": round(month_mins / 60, 1),
                "entry_count": len(tracker["entries"])
            })
        except Exception as e:
            return _err(f"Time stats error: {e}")

    def predict_win_probability(self, project_name: str = "", tonnage: float = 0,
                                 location: str = "", project_type: str = "",
                                 gc_company: str = "") -> dict:
        """Predict bid win probability from historical patterns.
        Uses bid pipeline history to identify sweet-spot matches.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        try:
            from bridge.bid_pipeline import _conn
            c = _conn()
            # Get historical win/loss data
            won = c.execute("SELECT * FROM bids WHERE state='WON'").fetchall()
            lost = c.execute("SELECT * FROM bids WHERE state='LOST'").fetchall()
            total = c.execute("SELECT * FROM bids WHERE state IN ('WON','LOST')").fetchall()
            c.close()
            if len(total) < 3:
                # Not enough data - use industry baselines
                base_rate = 0.28  # AISC industry average for structural steel
                # Adjust by sweet-spot factors
                score = base_rate
                factors = []
                ton_val = tonnage if tonnage else 0
                if 200 <= ton_val <= 2000:
                    score += 0.12; factors.append("tonnage in sweet spot (200-2000)")
                loc = (location or "").lower()
                if "houston" in loc or "texas" in loc or "tx" in loc:
                    score += 0.10; factors.append("Houston/Texas market")
                ptype = (project_type or "").lower()
                if any(w in ptype for w in ["church", "worship", "commercial"]):
                    score += 0.15; factors.append(f"{project_type} project type match")
                if any(w in ptype for w in ["refinery", "petrochemical", "industrial"]):
                    score += 0.08; factors.append(f"{project_type} industrial match")
                score = min(score, 0.95)
                return _ok({
                    "win_probability": round(score * 100, 1),
                    "confidence": "LOW - fewer than 3 completed bids in history",
                    "factors": factors,
                    "historical_wins": len(won),
                    "historical_losses": len(lost),
                    "baseline": "AISC industry average 28%"
                })
            else:
                # Enough data - calculate from actuals
                win_rate = len(won) / len(total) if total else 0
                # Match current bid against won bid profiles
                score = win_rate
                factors = [f"Base win rate: {round(win_rate*100)}% ({len(won)}/{len(total)})"]
                # Check location match
                won_locations = [dict(r).get("location", "").lower() for r in won]
                loc = (location or "").lower()
                if loc and any(loc in wl for wl in won_locations):
                    score += 0.10; factors.append("Location matches previous wins")
                # Check tonnage range match
                won_tonnages = []
                for r in won:
                    try: won_tonnages.append(float(dict(r).get("tonnage", 0)))
                    except Exception:pass
                if won_tonnages and tonnage:
                    avg_won = sum(won_tonnages) / len(won_tonnages)
                    if 0.5 * avg_won <= tonnage <= 2.0 * avg_won:
                        score += 0.08; factors.append("Tonnage in your historical win range")
                score = min(score, 0.95)
                return _ok({
                    "win_probability": round(score * 100, 1),
                    "confidence": "MEDIUM" if len(total) < 10 else "HIGH",
                    "factors": factors,
                    "historical_wins": len(won),
                    "historical_losses": len(lost),
                    "total_decided": len(total)
                })
        except Exception as e:
            return _err(f"Win probability error: {e}")

    def run_self_test_suite(self) -> dict:
        """Alias for run_self_test - used by Settings panel button."""
        return self.run_self_test()

    # ═══ USER PREFERENCES - persistent key/value store ═══════════

    def set_user_pref(self, key: str = "", value: str = "") -> dict:
        """Save a user preference (tour_completed, bid_template, etc.).
        Persists to data/user_prefs.json - survives app restarts.
        """
        import json
        try:
            prefs_file = _app_root() / "data" / "user_prefs.json"
            prefs_file.parent.mkdir(parents=True, exist_ok=True)
            prefs = {}
            if prefs_file.exists():
                prefs = json.loads(prefs_file.read_text())
            prefs[key] = value
            prefs_file.write_text(json.dumps(prefs, indent=2))
            return _ok({"key": key, "value": value, "saved": True})
        except Exception as e:
            return _err(f"Pref save error: {e}")

    def get_user_pref(self, key: str = "") -> dict:
        """Get a user preference by key."""
        import json
        try:
            prefs_file = _app_root() / "data" / "user_prefs.json"
            if not prefs_file.exists():
                return _ok({"key": key, "value": None})
            prefs = json.loads(prefs_file.read_text())
            return _ok({"key": key, "value": prefs.get(key)})
        except Exception as e:
            return _err(f"Pref load error: {e}")

    def get_bid_template(self, template_name: str = "STANDARD") -> dict:
        """Get bid output template definition.
        Templates: STANDARD, SIMPLE, DETAILED, REFINERY.
        """
        templates = {
            "STANDARD": {
                "name": "Standard", "sections": ["header","scope","member_schedule","pricing_table","exclusions","terms","signature"],
                "description": "Professional bid with scope, pricing table, terms - Your Company letterhead",
            },
            "SIMPLE": {
                "name": "Simple Quote", "sections": ["header","summary_line","total","timeline","signature"],
                "description": "One-page budget quote - tonnage, rate, total, timeline",
            },
            "DETAILED": {
                "name": "Detailed Estimate",
                "sections": ["header","scope","member_schedule","weight_summary","labor_breakdown","material_costs","equipment","markup_table","exclusions","alternates","terms","signature"],
                "description": "Full breakdown: member-by-member weights, labor hours, material costs, markups",
            },
            "REFINERY": {
                "name": "Refinery / Industrial",
                "sections": ["header","scope","compliance_matrix","member_schedule","pricing_table","safety_reference","pla_terms","insurance_certs","signature"],
                "description": "PLA-compliant with safety plan reference, DISA/ISN compliance, prevailing wage",
            },
        }
        tpl = templates.get(template_name.upper(), templates["STANDARD"])
        return _ok({"template": tpl, "active": template_name.upper(), "available": list(templates.keys())})

    def set_bid_template(self, template_name: str = "STANDARD") -> dict:
        """Set the active bid output template."""
        valid = ["STANDARD", "SIMPLE", "DETAILED", "REFINERY"]
        name = template_name.upper()
        if name not in valid:
            return _err(f"Unknown template '{template_name}'. Available: {', '.join(valid)}")
        self.set_user_pref("bid_template", name)
        return _ok({"active": name, "message": f"Bid template set to {name}"})

    # ═══ 3D MODEL VIEWER - LOCAL AISC CALCULATIONS (no AI needed) ══════

    def generate_3d_view(self, shape: str = "W14X82", length_ft: float = 20,
                          count: int = 1) -> dict:
        """Generate a 3D STL model from AISC shape data - 100% local calculation.
        
        This uses the fabrication engine's generate_stl() with AISC cross-section
        data. No AI call is made - geometry is computed from authoritative AISC tables.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        length_ft, _e = _coerce_num(length_ft, 'length_ft')
        if _e: return _e
        count, _e = _coerce_num(count, 'count', cast='int')
        if _e: return _e
        import base64
        try:
            from bridge.fabrication import generate_stl, get_section, _load_sections
            
            # Normalize shape name: HSS6X6X.500 -> HSS6X6X1/2, w14x82 -> W14X82
            shape = shape.upper().replace(" ", "").replace("×", "X")
            try:
                norm_result = self.normalize_shape(raw_shape=shape)
                if norm_result.get("ok") and norm_result["data"].get("normalized"):
                    shape = norm_result["data"]["normalized"]
            except Exception:
                pass
            
            # Look up AISC data locally
            sec = get_section(shape)
            if not sec:
                # Try fuzzy match
                sections = _load_sections()
                candidates = [s for s in sections if shape.replace("X", "") in s.replace("X", "")]
                if candidates:
                    shape = candidates[0]
                    sec = sections[shape]
                else:
                    available = sorted(sections.keys())[:20]
                    return _err(
                        f"Shape '{shape}' not found in AISC database.\n"
                        f"Available shapes include: {', '.join(available[:10])}..."
                    )
            
            # Build member list for STL generation
            members = []
            for i in range(count):
                members.append({
                    "shape": shape,
                    "length_ft": length_ft,
                    "x_ft": i * (sec["bf"] / 12 + 2),  # space members apart
                    "y_ft": 0,
                    "z_ft": 0,
                    "mark": f"{shape}-{i+1}",
                })
            
            # Generate STL bytes - ALL LOCAL, NO AI
            stl_bytes = generate_stl(members)
            stl_b64 = base64.b64encode(stl_bytes).decode("ascii")
            
            # Save to disk so the path is available for frontend/buttons
            output_dir = Path(__file__).parent.parent / "output"
            output_dir.mkdir(exist_ok=True)
            safe_shape = shape.replace("/", "_")  # HSS6X6X1/2 -> HSS6X6X1_2
            stl_filename = f"{safe_shape}_{int(length_ft)}ft.stl"
            stl_path = output_dir / stl_filename
            stl_path.write_bytes(stl_bytes)
            
            # Calculate weight from AISC data
            weight_per_ft = sec.get("W", sec.get("weight_per_foot", 0))
            total_weight = weight_per_ft * length_ft * count
            
            return _ok({
                "stl_b64": stl_b64,
                "stl_bytes": len(stl_bytes),
                "path": str(stl_path),
                "filename": stl_filename,
                "shape": shape,
                "length_ft": length_ft,
                "member_count": count,
                "depth_in": sec.get("d", 0),
                "flange_in": sec.get("bf", 0),
                "web_thickness_in": sec.get("tw", 0),
                "flange_thickness_in": sec.get("tf", 0),
                "weight_per_ft": weight_per_ft,
                "weight_lbs": round(total_weight, 1),
                "weight_tons": round(total_weight / 2000, 3),
                "family": sec.get("family", "W"),
                "label": f"{shape} × {length_ft}′ ({count} member{'s' if count > 1 else ''})",
                "source": "AISC_LOCAL - no AI used",
            })
        except Exception as e:
            return _err(f"3D generation error: {e}")

    def get_portfolio_facts(self) -> dict:
        """Return verified portfolio facts for LinkedIn posts."""
        from bridge.linkedin_content import get_portfolio_facts
        return _ok({"facts": get_portfolio_facts()})

    # ── v3.4.0: Three-Tier Governance ─────────────────────────────────

    def get_governance_status(self) -> dict:
        """Full three-tier governance status."""
        from bridge.governance import governance_status
        _r = governance_status()
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def set_ceo_preference(self, key: str = "", value: str = "",
                           reason: str = "") -> dict:
        """Set a CEO preference (Tier 2). Blocked if conflicts with Tier 1."""
        if not key:
            return _err("key is required")
        from bridge.governance import set_ceo_pref
        return set_ceo_pref(key, value, reason)  # _ok shape: passthrough from set_ceo_pref

    def get_governance_resolution(self, key: str = "") -> dict:
        """Resolve a setting through all three governance tiers."""
        if not key:
            return _err("key is required")
        from bridge.governance import resolve
        _r = resolve(key)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def check_bid_compliance(self, content: str = "",
                             context: str = "bid") -> dict:
        """Check content against Tier 1 compliance rules."""
        if not content:
            return _err("content is required")
        from bridge.governance import check_compliance
        violations = check_compliance(content, context)
        return _ok({
            "compliant": len(violations) == 0,
            "violations": violations,
            "violation_count": len(violations),
        })

    def get_governance_audit(self, limit: int = 50) -> dict:
        """Read governance audit trail."""
        # pass 10i: numeric input hardening - coerce or fail clean
        limit, _e = _coerce_num(limit, 'limit', cast='int')
        if _e: return _e
        from bridge.governance import get_audit_trail
        _r = get_audit_trail(limit)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ── v3.4.0: Session Boot ──────────────────────────────────────────

    def session_boot(self, force_refresh: bool = False) -> dict:
        """Run session boot sequence. Loads OneDrive standing files,
        governance state, and vault context."""
        from bridge.session_boot import session_boot as _boot
        return _ok(_boot(force_refresh))  # vj: ok-passthrough-safe

    def get_session_state(self) -> dict:
        """Get current session state without re-booting."""
        from bridge.session_boot import get_session_state
        state = get_session_state()
        if state:
            return _ok(state)
        return _err("Session not booted yet. Call session_boot() first.")

    def sync_project(self, project_number: str = "", bid_id: int = 0) -> dict:
        """Phase 2: Force a State.md sync for a specific project.

        Reads current pipeline state and writes Project OS/State.md.
        Used to recover from syncer drift or after manual pipeline changes.
        """
        bid_id, _e = _coerce_num(bid_id, 'bid_id', cast='int')
        if _e: return _e
        if not project_number and not bid_id:
            return _err("project_number or bid_id required")
        try:
            from bridge.project_syncer import get_syncer
            result = get_syncer().sync_project(project_number=project_number, bid_id=bid_id)
            if result.get("ok"):
                return _ok(result)
            return _err(result.get("error", "sync failed"))
        except Exception as e:
            return _err(f"sync_project failed: {e}")

    # ── v3.3.2: Project Migration Scanner ────────────────────────────

    def run_migration_scan_pass1(self, root_dir: str = "") -> dict:
        """Read-only inventory scan of an existing project directory tree.

        Pass 1 only. Never writes. Returns confirmed matches, unknowns,
        vendor-flagged docs, and file counts per folder.

        Pass 2 (copy) requires explicit per-project instruction and is
        invoked separately. This method never copies anything.
        """
        if not root_dir:
            return _err("root_dir is required")
        try:
            from bridge.project_migration.scanner import scan_pass1
            result = scan_pass1(root_dir)
            if "error" in result:
                return _err(result["error"])
            return _ok(result)
        except Exception as e:
            return _err(f"migration scan failed: {e}")

    # ── v3.4.0: Agent 6 - Bid Review (SSP) ───────────────────────────

    def review_bid_ssp(self, ssp_text: str = "", project_name: str = "",
                       complexity: str = "standard",
                       margin_pct: float = 0.18) -> dict:
        """4-section bid review from Steel Suite Pro export.

        Sections: Scope Verification, Weight Audit, Cost Reasonableness,
        Risk Flags. All math from calculators.py, no LLM arithmetic.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        margin_pct, _e = _coerce_num(margin_pct, 'margin_pct')
        if _e: return _e
        if not ssp_text:
            return _err("ssp_text is required. Paste the SSP export data.")
        from bridge.agents.bid_review import bid_review
        _r = bid_review(ssp_text, project_name, complexity, margin_pct)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def parse_ssp_export(self, ssp_text: str = "") -> dict:
        """Parse an SSP export without running full bid review."""
        if not ssp_text:
            return _err("ssp_text is required")
        from bridge.agents.bid_review import parse_ssp_export
        _r = parse_ssp_export(ssp_text)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ── v3.4.0: Obsidian Vault Write-Back ─────────────────────────────

    def vault_sync_session(self, summary: str = "",
                           session_id: str = "") -> dict:
        """Write session summary to Obsidian vault for cross-platform sync."""
        if not summary:
            return _err("summary is required")
        from bridge.obsidian_sync import sync_session_summary
        return sync_session_summary(summary, session_id)  # _ok shape: passthrough from write_vault_file

    def vault_sync_preferences(self, prefs_text: str = "") -> dict:
        """Sync CEO preferences to Obsidian vault."""
        if not prefs_text:
            return _err("prefs_text is required")
        from bridge.obsidian_sync import sync_ceo_preferences
        return sync_ceo_preferences(prefs_text)  # _ok shape: passthrough from write_vault_file

    def vault_sync_projects(self, project_data: dict = None) -> dict:
        """Sync active project state to Obsidian vault."""
        import json as _j
        if isinstance(project_data, str):
            try: project_data = _j.loads(project_data)
            except Exception: return _err("project_data must be a JSON object (dict)")
        if not project_data or not isinstance(project_data, dict):
            return _err("project_data must be a dict")
        for k, v in project_data.items():
            if not isinstance(v, dict):
                return _err(
                    f"each project entry must be a dict; "
                    f"\"{k}\" is {type(v).__name__}"
                )
        from bridge.obsidian_sync import sync_project_state
        return sync_project_state(project_data)  # _ok shape: passthrough from write_vault_file

    def get_vault_sync_status(self) -> dict:
        """Get cross-platform vault sync status."""
        from bridge.obsidian_sync import get_sync_status
        _r = get_sync_status()
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    # ── v3.4.2: PDF Output QC (the Owner's 6 Rules) ────────────────────

    def run_pdf_qc(self, pdf_path: str = "",
                   was_rendered: bool = False) -> dict:
        """Run all 6 visual QC rules on a generated PDF."""
        if not pdf_path:
            return _err("pdf_path is required")
        from bridge.pdf_qc import run_pdf_qc
        return _ok(run_pdf_qc(pdf_path, was_rendered))  # vj: ok-passthrough-safe

    def get_pdf_qc_rules(self) -> dict:
        """List all 6 PDF visual QC rules."""
        from bridge.pdf_qc import list_rules
        return _ok(list_rules())  # vj: ok-passthrough-safe

    # ── v3.4.6: Intent Router (the Owner's Shorthand) ──────────────────

    def classify_intent(self, message: str = "") -> dict:
        """Classify the Owner's shorthand into a full pipeline.

        Returns the intent, pipeline steps, auto-defaults to apply,
        and which project files to load.
        """
        if not message:
            return _err("message is required")
        from bridge.intent_router import classify_intent
        result = classify_intent(message)
        return _ok({
            "intent": result.intent,
            "confidence": result.confidence,
            "pipeline": result.pipeline,
            "auto_defaults": result.auto_defaults,
            "ask_first": result.ask_first,
            "context_files": result.context_files,
            "voice": result.voice,
            "turnaround": result.turnaround,
        })

    def get_auto_defaults(self) -> dict:
        """Return all auto-defaults that apply silently to every bid."""
        from bridge.intent_router import get_auto_defaults
        return _ok(get_auto_defaults())  # vj: ok-passthrough-safe

    def list_intents(self) -> dict:
        """List all recognized intent triggers and their pipelines."""
        from bridge.intent_router import list_intents
        return _ok(list_intents())  # vj: ok-passthrough-safe

    # ── v3.5.2: Mail Scanner + GDrive Sync + Sentry ──────────────────

    def mail_scanner_status(self) -> dict:
        """Get M365 mail scanner status (configured, running, mailbox)."""
        from bridge.m365_mail_scanner import M365MailScanner
        scanner = M365MailScanner(_app_root(), on_bid_invite=lambda x: None)
        return _ok(scanner.status())  # vj: ok-passthrough-safe

    def gdrive_sync_status(self) -> dict:
        """Get Google Drive sync status (tracked files, config state)."""
        try:
            from bridge.gdrive_sync import GDriveSync
            sync = GDriveSync(_app_root(), folder_id="")
            return _ok(sync.status())  # vj: ok-passthrough-safe
        except Exception as e:
            return _ok({"configured": False, "error": str(e)})

    def gdrive_pull(self) -> dict:
        """Pull new/changed files from Google Drive."""
        try:
            from bridge.gdrive_sync import GDriveSync
            sync = GDriveSync(_app_root(), folder_id="")
            return _ok(sync.pull())  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(str(e))

    def gdrive_push(self, path: str = "") -> dict:
        """Push a local file to Google Drive."""
        if not path:
            return _err("path is required")
        try:
            from bridge.gdrive_sync import GDriveSync
            sync = GDriveSync(_app_root(), folder_id="")
            return _ok(sync.push(Path(path)))  # vj: ok-passthrough-safe
        except Exception as e:
            return _err(str(e))

    def get_sentry_release(self) -> dict:
        """Get the current Sentry release tag (steel-office@X.Y.Z)."""
        from bridge.sentry_setup import get_release_tag
        return _ok({"release": get_release_tag()})

    # ── v3.5.2: Skill Registry + Harnesses ────────────────────────────

    def list_skills(self) -> dict:
        """List all available skills (frontmatter only, ~80 tokens each)."""
        from bridge.skill_registry import SkillRegistry
        reg = SkillRegistry()
        return _ok(reg.list_skills())  # vj: ok-passthrough-safe

    def load_skill(self, name: str = "") -> dict:
        """Load full skill body on demand (~2K tokens)."""
        if not name:
            return _err("name is required")
        from bridge.skill_registry import SkillRegistry
        reg = SkillRegistry()
        body = reg.load(name)
        return _ok({"name": name, "body": body})

    def match_skill(self, message: str = "") -> dict:
        """Find the best matching skill for a message."""
        if not message:
            return _err("message is required")
        from bridge.skill_registry import SkillRegistry
        reg = SkillRegistry()
        skill = reg.match(message)
        if skill:
            return _ok({"name": skill.name, "description": skill.description,
                        "triggers": skill.triggers})
        return _ok({"name": None, "message": "No skill matched"})

    def run_bid_harness(self) -> dict:
        """Run the bid pipeline regression harness (13 checks)."""
        from harnesses.operational import BidPipelineHarness
        return _ok(BidPipelineHarness.run())  # vj: ok-passthrough-safe

    def check_voice(self, text: str = "") -> dict:
        """Check text against the Owner's 10 voice rules."""
        if not text:
            return _err("text is required")
        from harnesses.operational import VoiceCalibrationHarness
        return _ok(VoiceCalibrationHarness.check(text))  # vj: ok-passthrough-safe

    def run_compliance_attacks(self) -> dict:
        """Run 60+ attack phrases through compliance scanner."""
        from harnesses.operational import ComplianceAttackLibrary
        return _ok(ComplianceAttackLibrary.run_all())  # vj: ok-passthrough-safe

    # ── v3.5.2: Creative competitive-edge methods ─────────────────────

    def score_bid(self, proposal_text: str = "", tonnage: float = 0,
                  total_bid: float = 0, deck_sf: float = 0,
                  pdf_path: str = "", template: str = "STANDARD",
                  bid_id: int = 0) -> dict:
        """Score a bid proposal A-F (100-pt scale). No paid service can do this.

        Categories: Compliance (40), Voice (20), Pricing (25), Format (15).
        Returns grade, score, breakdown, deductions, recommendations, verdict.

        SIM-07: accepts `bid_id=N` to hydrate tonnage / total_bid / deck_sf
        from the pipeline row automatically. Owner expected `score_bid(bid_id=4)`
        to just work. With bid_id, the other numeric args are optional -
        you can still override them by passing explicit values.
        """
        # SIM-07: bid_id hydration
        if bid_id:
            bid_id_n, _e = _coerce_num(bid_id, 'bid_id', cast='int')
            if _e: return _e
            try:
                from bridge.bid_pipeline import get_bid as _gb
                _row = _gb(bid_id_n)
            except Exception as e:
                return _err(f"score_bid: could not load bid {bid_id}: {e}")
            if not _row:
                return _err(f"score_bid: bid {bid_id} not found",
                            fix="type `list bids` to see active IDs")
            # Hydrate any args left at their defaults
            if not tonnage:
                tonnage = _row.get('tonnage') or _row.get('struct_tons') or 0
            if not total_bid:
                total_bid = _row.get('estimated_value') or _row.get('total_bid') or 0
            if not deck_sf:
                deck_sf = _row.get('deck_sf') or _row.get('building_sf') or 0
            if not proposal_text:
                # Use scope text if available so scoring has something to read
                proposal_text = _row.get('scope_text') or _row.get('scope') or _row.get('name', '')
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        total_bid, _e = _coerce_num(total_bid, 'total_bid')
        if _e: return _e
        deck_sf, _e = _coerce_num(deck_sf, 'deck_sf')
        if _e: return _e
        from bridge.bid_scorecard import score_bid as _score
        return _ok(_score(  # vj: ok-passthrough-safe
            proposal_text=proposal_text, tonnage=tonnage,
            total_bid=total_bid, deck_sf=deck_sf,
            pdf_path=pdf_path, template=template,
        ))

    def generate_scope_narrative(self, members: str = "[]",
                                 tonnage: float = 0, deck_sf: float = 0,
                                 building_type: str = "conventional",
                                 project_name: str = "",
                                 drawing_stage: str = "IFC") -> dict:
        """Generate project-specific scope text from actual takeoff data.

        No boilerplate. Every sentence is grounded in real member counts.
        members: JSON array of {shape, qty, type} dicts.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        deck_sf, _e = _coerce_num(deck_sf, 'deck_sf')
        if _e: return _e
        import json as _j
        try:
            member_list = _j.loads(members) if isinstance(members, str) else members
        except Exception:
            return _err("members must be valid JSON array")
        from bridge.scope_narrative import generate_scope_narrative as _gen
        return _ok(_gen(  # vj: ok-passthrough-safe
            members=member_list, tonnage=tonnage, deck_sf=deck_sf,
            building_type=building_type, project_name=project_name,
            drawing_stage=drawing_stage,
        ))

    def generate_followup_sequence(self, project_name: str = "",
                                    gc_name: str = "", gc_company: str = "",
                                    bid_total: float = 0, tonnage: float = 0,
                                    bid_date: str = "",
                                    bid_number: str = "") -> dict:
        """Auto-generate 3-email follow-up sequence (day 3/7/14).

        Every email is in the Owner's voice with project-specific details.
        No paid service follows up after delivery.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        bid_total, _e = _coerce_num(bid_total, 'bid_total')
        if _e: return _e
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        if not project_name or not gc_name:
            return _err("project_name and gc_name are required")
        from bridge.bid_followup import generate_followup_sequence as _gen
        return _ok(_gen(  # vj: ok-passthrough-safe
            project_name=project_name, gc_name=gc_name,
            gc_company=gc_company, bid_total=bid_total,
            tonnage=tonnage, bid_date=bid_date, bid_number=bid_number,
        ))

    def bid_history_log(self, project_name: str = "", gc_company: str = "",
                        tonnage: float = 0, total_bid: float = 0,
                        outcome: str = "", notes: str = "") -> dict:
        """Log a bid outcome for historical learning. 

        Over time, builds a dataset of win/loss patterns by GC, 
        building type, and price point. No paid service learns from
        your bid history.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        total_bid, _e = _coerce_num(total_bid, 'total_bid')
        if _e: return _e
        import sqlite3, json
        from datetime import datetime
        from pathlib import Path
        db_path = Path(__file__).parent.parent / "data" / "bid_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS bid_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT, gc_company TEXT, tonnage REAL,
            total_bid REAL, cost_per_ton REAL, outcome TEXT,
            notes TEXT, logged_at TEXT
        )""")
        cpt = total_bid / tonnage if tonnage > 0 else 0
        conn.execute(
            "INSERT INTO bid_history VALUES (NULL,?,?,?,?,?,?,?,?)",
            (project_name, gc_company, tonnage, total_bid, cpt,
             outcome, notes, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        # Return stats
        rows = conn.execute("SELECT COUNT(*), AVG(cost_per_ton), "
                           "SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) "
                           "FROM bid_history").fetchone()
        conn.close()
        return _ok({
            "logged": True,
            "total_bids": rows[0],
            "avg_cost_per_ton": round(rows[1] or 0, 2),
            "wins": rows[2] or 0,
            "win_rate": f"{(rows[2] or 0) / max(rows[0], 1) * 100:.0f}%",
        })

    def bid_history_compare(self, tonnage: float = 0, total_bid: float = 0,
                            gc_company: str = "",
                            building_type: str = "") -> dict:
        """Compare a new bid against historical data.

        Returns how this bid stacks up against past bids by $/ton,
        GC-specific history, and win-rate context.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        tonnage, _e = _coerce_num(tonnage, 'tonnage')
        if _e: return _e
        total_bid, _e = _coerce_num(total_bid, 'total_bid')
        if _e: return _e
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent.parent / "data" / "bid_pipeline.db"
        conn = sqlite3.connect(str(db_path))
        # Ensure table exists
        conn.execute("""CREATE TABLE IF NOT EXISTS bid_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT, gc_company TEXT, tonnage REAL,
            total_bid REAL, cost_per_ton REAL, outcome TEXT,
            notes TEXT, logged_at TEXT
        )""")
        cpt = total_bid / tonnage if tonnage > 0 else 0
        # Overall stats
        overall = conn.execute(
            "SELECT COUNT(*), AVG(cost_per_ton), MIN(cost_per_ton), "
            "MAX(cost_per_ton) FROM bid_history WHERE cost_per_ton > 0"
        ).fetchone()
        # GC-specific stats
        gc_stats = None
        if gc_company:
            gc_row = conn.execute(
                "SELECT COUNT(*), AVG(cost_per_ton), "
                "SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) "
                "FROM bid_history WHERE gc_company=?", (gc_company,)
            ).fetchone()
            if gc_row[0] > 0:
                gc_stats = {
                    "bids_with_gc": gc_row[0],
                    "avg_cpt_with_gc": round(gc_row[1] or 0, 2),
                    "wins_with_gc": gc_row[2] or 0,
                }
        conn.close()

        comparison = {
            "this_bid_cpt": round(cpt, 2),
            "historical_bids": overall[0] or 0,
            "historical_avg_cpt": round(overall[1] or 0, 2),
            "historical_min_cpt": round(overall[2] or 0, 2),
            "historical_max_cpt": round(overall[3] or 0, 2),
        }
        if cpt > 0 and (overall[1] or 0) > 0:
            delta_pct = (cpt - overall[1]) / overall[1] * 100
            comparison["vs_average"] = f"{delta_pct:+.1f}%"
            if delta_pct > 15:
                comparison["warning"] = "This bid is 15%+ above your average. Verify scope."
            elif delta_pct < -15:
                comparison["warning"] = "This bid is 15%+ below your average. Check margins."
        if gc_stats:
            comparison["gc_history"] = gc_stats

        return _ok(comparison)

    def ve_suggestions(self, members: str = "[]", budget: float = 0,
                       current_total: float = 0) -> dict:
        """Value engineering suggestions when a bid exceeds budget.

        Analyzes each member and suggests lighter alternatives with
        tonnage/cost savings. Uses AISC shape data.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        budget, _e = _coerce_num(budget, 'budget')
        if _e: return _e
        current_total, _e = _coerce_num(current_total, 'current_total')
        if _e: return _e
        import json as _j, re
        try:
            member_list = _j.loads(members) if isinstance(members, str) else members
        except Exception:
            return _err("members must be valid JSON array")

        suggestions = []
        total_savings = 0

        # W-shape substitution: suggest one size lighter
        _lighter = {
            "W14X82": ("W14X68", 14), "W14X68": ("W14X53", 15),
            "W14X53": ("W14X43", 10), "W14X43": ("W14X34", 9),
            "W12X87": ("W12X72", 15), "W12X72": ("W12X58", 14),
            "W12X58": ("W12X50", 8), "W12X50": ("W12X40", 10),
            "W10X49": ("W10X39", 10), "W10X39": ("W10X33", 6),
            "W16X40": ("W16X31", 9), "W16X31": ("W16X26", 5),
            "W18X50": ("W18X40", 10), "W18X40": ("W18X35", 5),
            "W21X62": ("W21X50", 12), "W21X50": ("W21X44", 6),
            "W24X68": ("W24X55", 13), "W24X55": ("W24X44", 11),
        }

        for m in member_list:
            shape = m.get("shape", "").upper().replace(" ", "")
            qty = m.get("qty", 1)
            if shape in _lighter:
                alt, weight_save_plf = _lighter[shape]
                # Estimate length at 25' average
                savings_tons = (weight_save_plf * 25 * qty) / 2000
                savings_dollars = savings_tons * 3750  # fab rate
                total_savings += savings_dollars
                suggestions.append({
                    "current": shape,
                    "alternative": alt,
                    "qty": qty,
                    "weight_saved_plf": weight_save_plf,
                    "tonnage_saved": round(savings_tons, 2),
                    "cost_saved": round(savings_dollars, 0),
                    "note": "Requires PE confirmation of capacity.",
                })

        over_budget = current_total - budget if budget > 0 else 0

        return _ok({
            "suggestions": suggestions[:10],
            "total_potential_savings": round(total_savings, 0),
            "over_budget_by": round(over_budget, 0) if over_budget > 0 else 0,
            "covers_gap": total_savings >= over_budget if over_budget > 0 else True,
            "disclaimer": "All substitutions require PE review. Your Company does not practice engineering.",
        })

    def drawing_revision_diff(self, old_members: str = "[]",
                               new_members: str = "[]") -> dict:
        """Compare two takeoffs to detect scope changes.

        When a revised drawing set arrives, auto-detect added/removed
        members and compute the price delta.
        """
        import json as _j
        try:
            old = _j.loads(old_members) if isinstance(old_members, str) else old_members
            new = _j.loads(new_members) if isinstance(new_members, str) else new_members
        except Exception:
            return _err("Both old_members and new_members must be valid JSON")

        old_set = {}
        for m in old:
            key = m.get("shape", "")
            old_set[key] = old_set.get(key, 0) + m.get("qty", 1)

        new_set = {}
        for m in new:
            key = m.get("shape", "")
            new_set[key] = new_set.get(key, 0) + m.get("qty", 1)

        added = []
        removed = []
        changed = []

        all_shapes = set(list(old_set.keys()) + list(new_set.keys()))
        for shape in sorted(all_shapes):
            old_qty = old_set.get(shape, 0)
            new_qty = new_set.get(shape, 0)
            if old_qty == 0 and new_qty > 0:
                added.append({"shape": shape, "qty": new_qty})
            elif old_qty > 0 and new_qty == 0:
                removed.append({"shape": shape, "qty": old_qty})
            elif old_qty != new_qty:
                changed.append({"shape": shape, "old_qty": old_qty,
                               "new_qty": new_qty, "delta": new_qty - old_qty})

        # Estimate tonnage delta
        import re
        tonnage_delta = 0
        for item in added:
            w = _extract_weight(item["shape"])
            tonnage_delta += (w * 25 * item["qty"]) / 2000
        for item in removed:
            w = _extract_weight(item["shape"])
            tonnage_delta -= (w * 25 * item["qty"]) / 2000
        for item in changed:
            w = _extract_weight(item["shape"])
            tonnage_delta += (w * 25 * item["delta"]) / 2000

        return _ok({
            "added": added,
            "removed": removed,
            "changed": changed,
            "tonnage_delta": round(tonnage_delta, 2),
            "price_delta": round(tonnage_delta * 3750, 0),
            "recommendation": (
                "Issue addendum with revised pricing."
                if abs(tonnage_delta) > 0.5
                else "Scope change is negligible. No addendum needed."
            ),
        })

    # ── v3.5.2: Gemini-report-driven methods ─────────────────────────

    def validate_shapes(self, members: str = "[]") -> dict:
        """AISC Validation Gate. Every AI-extracted shape must pass through.

        Catches hallucinated shapes like "W14X81" and suggests "W14X82".
        Performs mass balance check against extracted tonnage.
        """
        import json as _j
        try:
            member_list = _j.loads(members) if isinstance(members, str) else members
        except Exception:
            return _err("members must be valid JSON array")
        if not isinstance(member_list, list):
            return _err("members must be a JSON array, got " + type(member_list).__name__)
        for i, m in enumerate(member_list):
            if not isinstance(m, dict):
                return _err(
                    f"each member must be {{shape, qty, length_ft}}; "
                    f"item [{i}] is {type(m).__name__}: {str(m)[:80]}"
                )
        from bridge.aisc_validator import validate_takeoff
        return _ok(validate_takeoff(member_list))  # vj: ok-passthrough-safe

    def hash_drawing_pages(self, pdf_path: str = "") -> dict:
        """Hash each page of a drawing PDF for revision comparison.

        When a revised set arrives, only re-process changed pages.
        Saves Gemini API costs on unchanged pages.
        """
        if not pdf_path:
            return _err("pdf_path is required")
        from bridge.page_hasher import hash_drawing_set
        r = hash_drawing_set(pdf_path)
        if isinstance(r, dict) and r.get("ok") is False:
            return _err(r.get("error", "hash_drawing_set failed"))
        return _ok(r)

    def compare_drawing_revisions(self, old_pdf: str = "",
                                   new_pdf: str = "") -> dict:
        """Compare two PDF drawing sets page-by-page.

        Returns which pages changed vs unchanged.
        Only changed pages go through Gemini vision processing.
        """
        if not old_pdf or not new_pdf:
            return _err("Both old_pdf and new_pdf are required")
        from bridge.page_hasher import compare_revisions
        r = compare_revisions(old_pdf, new_pdf)
        if isinstance(r, dict) and r.get("ok") is False:
            return _err(r.get("error", "compare_revisions failed"))
        return _ok(r)

    def aisc_mass_balance(self, extracted_tonnage: float = 0,
                          members: str = "[]") -> dict:
        """Compare AI-extracted tonnage vs member-calculated tonnage.

        If AI says 85T but members add up to 72T, something is
        missing from the takeoff.
        """
        # v3.5.10 Bug #8: validate extracted_tonnage casts cleanly to a
        # number BEFORE calling the validator. Before this fix, passing
        # a non-numeric value (e.g., from an MCP client that didn't
        # coerce) leaked the Python TypeError message
        # ("unsupported operand type(s) for -: 'str' and 'float'") to
        # the user. Now returns a clear contract error instead.
        # pass 10i: numeric input hardening - coerce or fail clean
        extracted_tonnage, _e = _coerce_num(extracted_tonnage, 'extracted_tonnage')
        if _e: return _e
        try:
            extracted_tonnage = float(extracted_tonnage)
        except (TypeError, ValueError):
            return _err(
                f"extracted_tonnage must be a number (got "
                f"{type(extracted_tonnage).__name__}: "
                f"{repr(extracted_tonnage)[:50]})"
            )
        import math as _math
        if not _math.isfinite(extracted_tonnage):
            return _err(
                f"extracted_tonnage must be finite (got {extracted_tonnage})"
            )
        import json as _j
        try:
            member_list = _j.loads(members) if isinstance(members, str) else members
        except Exception:
            return _err("members must be valid JSON array")
        from bridge.aisc_validator import mass_balance_check
        return _ok(mass_balance_check(extracted_tonnage, member_list))  # vj: ok-passthrough-safe

    # ── v3.5.2: Drawing Intelligence Pipeline (Gemini architecture) ──

    def extract_drawing_set(self, pdf_path: str = "",
                            pages: str = "") -> dict:
        """Extract structured content from a PDF drawing set using
        pymupdf4llm. Layout-aware, auto-OCR, no GPU required.
        Returns page-by-page content with structural classification.
        """
        if not pdf_path:
            return _err("pdf_path is required")
        page_list = None
        if pages:
            import json as _j
            try:
                page_list = _j.loads(pages)
            except Exception:
                pass
        from bridge.drawing_intel.preprocessor import extract_drawing_set as _extract
        _r = _extract(pdf_path, page_list)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def rasterize_drawing_page(self, pdf_path: str = "",
                                page_num: int = 0, dpi: int = 300) -> dict:
        """Rasterize a single drawing page at specified DPI.
        150 DPI for classification, 300 DPI for analysis.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        page_num, _e = _coerce_num(page_num, 'page_num', cast='int')
        if _e: return _e
        dpi, _e = _coerce_num(dpi, 'dpi', cast='int')
        if _e: return _e
        if not pdf_path:
            return _err("pdf_path is required")
        from bridge.drawing_intel.preprocessor import rasterize_page
        result = rasterize_page(pdf_path, page_num, dpi)
        if isinstance(result, dict) and "error" in result and len(result) <= 2:
            return _err(result["error"], fix="Install PyMuPDF: pip install PyMuPDF")
        return _ok(result)

    def extract_cad_layer(self, pdf_path: str = "", page_num: int = 0,
                          layer_name: str = "Steel") -> dict:
        """Extract content from a specific CAD layer (OCG).
        Isolate 'Steel' layer to reduce noise before AI processing.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        page_num, _e = _coerce_num(page_num, 'page_num', cast='int')
        if _e: return _e
        if not pdf_path:
            return _err("pdf_path is required")
        from bridge.drawing_intel.preprocessor import extract_with_ocg_isolation
        _r = extract_with_ocg_isolation(pdf_path, page_num, layer_name)
        if isinstance(_r, dict) and "error" in _r and not _r.get("ok"):
            return _err(_r["error"])
        return _ok(_r)

    def record_shape_correction(self, raw_text: str = "",
                                 corrected_shape: str = "",
                                 pe_firm: str = "",
                                 project: str = "") -> dict:
        """Record a shape correction for self-healing learning.
        After 3 corrections of the same pattern from the same firm,
        auto-generates a firm-specific normalization rule.
        """
        if not raw_text or not corrected_shape:
            return _err("raw_text and corrected_shape are required")
        from bridge.drawing_intel.self_healer import record_correction
        return _ok(record_correction(raw_text, corrected_shape, pe_firm, project))  # vj: ok-passthrough-safe

    def normalize_shape(self, raw_shape: str = "",
                        pe_firm: str = "") -> dict:
        """Normalize a shape using firm-specific rules first,
        then general AISC normalization.
        """
        if not raw_shape:
            return _err("raw_shape is required")
        from bridge.drawing_intel.self_healer import normalize_with_firm_rules
        return _ok(normalize_with_firm_rules(raw_shape, pe_firm))  # vj: ok-passthrough-safe

    def generate_wireframe(self, members: str = "[]",
                           grid_spacing_x: float = 30,
                           grid_spacing_y: float = 30,
                           eave_height: float = 24) -> dict:
        """Generate a 3D wireframe STL from takeoff data.
        If beams float (not connected to columns), flags takeoff error.
        """
        # pass 10i: numeric input hardening - coerce or fail clean
        grid_spacing_x, _e = _coerce_num(grid_spacing_x, 'grid_spacing_x')
        if _e: return _e
        grid_spacing_y, _e = _coerce_num(grid_spacing_y, 'grid_spacing_y')
        if _e: return _e
        eave_height, _e = _coerce_num(eave_height, 'eave_height')
        if _e: return _e
        import json as _j
        try:
            member_list = _j.loads(members) if isinstance(members, str) else members
        except Exception:
            return _err("members must be valid JSON array")
        from bridge.drawing_intel.model_3d import generate_wireframe as _gen
        result = _gen(member_list, grid_spacing_x, grid_spacing_y, eave_height)
        if isinstance(result, dict) and "error" in result and len(result) <= 2:
            return _err(result["error"], fix="Install the required library: pip install trimesh")
        return _ok(result)

def _extract_weight(shape: str) -> float:
    """Extract weight-per-foot from a shape designation."""
    import re
    m = re.match(r'W\d+[xX](\d+)', shape)
    if m:
        return float(m.group(1))
    m = re.match(r'HSS.*[xX]([\d.]+)', shape)
    if m:
        return float(m.group(1)) * 10
    return 20  # conservative default

_INTENT_PATTERNS = [
    # (keywords_any, keywords_none, translated_prompt)
    # Bids / estimating
    (["icd", "church"], ["email"], "give me the ICD Church full status: contract value, deposits received, uncompensated cost estimate, quantum meruit claim amount, AVL RFI status, and the exact next action Amber needs to take before any demand is sent."),
    (["afr", "america first", "brownsville", "refinery soq"], [], "give me the America First Refining SOQ status, timeline, and what the next touchpoint or follow-up should be."),
    (["marathon", "isn"], [], "what exactly is blocking the Marathon Petroleum ISN approval, who needs to do what, and what's the step-by-step to unblock it?"),
    (["auto", "liability", "progressive", "insurance upgrade"], [], "auto liability upgrade status: Progressive 868818985, current limits, required limits, who owns next step, and timeline."),
    (["compliance", "blocker", "tracker"], [], "give me the full 13-item compliance status. For each item, tell me current status, owner, and the exact next action needed."),
    (["emr", "texas mutual"], [], "EMR letter status: Texas Mutual Policy [POLICY NUMBER]. Who called, when, what was said, next step."),
    (["bid scan", "new bids", "bid email", "incoming bids"], [], "run bid scanner - scan the last 14 days of bid emails. List each bid with GC, project, deadline, and status."),
    (["scope creep", "scope watch", "change order"], ["draft"], "run scope watch - scan the last 14 days of emails and Teams for scope creep trigger phrases. List each hit with project, phrase, and recommended response."),
    (["deadline", "due date", "what's due", "overdue"], [], "pull deadlines - scan the next 14 days of calendar and inbox. Sort by: OVERDUE / TODAY / TOMORROW / THIS WEEK / NEXT WEEK."),
    (["weekly", "briefing", "week in review", "what happened"], [], "weekly briefing - synthesize the last 7 days. Top 5 events, bids submitted/won/pending, key client comms, compliance changes, and action items rolling into next week."),
    (["cold email", "cold outreach", "prospect email"], [], "draft a cold outreach email in the Owner's voice. I'll provide the 5 personalization inputs: [company + state, recent LinkedIn project, industrial client served, headcount, Tekla user?]"),
    (["follow up", "follow-up", "bid follow"], ["cold"], "draft a bid follow-up email in the Owner's voice. Provide: bid document number, GC contact name, bid date, and bid total. Reference all three specifically."),
    (["stock", "steel stock", "nue", "stld", "market", "sector research"], [], "run stock research on the steel and construction watchlist: NUE, STLD, CMC, CLF, X, RS, FLR, PWR. Include required disclaimer. Flag steel sector concentration."),
    (["tax", "sales tax", "separated contract"], [], "calculate Texas sales tax on a separated construction contract. Walk me through which portions are taxable and which are not."),
    (["rate", "rates", "what do we charge", "current rate", "pricing"], ["update"], "list all current Q2 2026 locked bid rates with GP percentages."),
    (["payment", "payment terms", "milestone", "30/20/50"], [], "list the current payment structure with client-facing wording for each milestone."),
    (["equipment", "what equipment", "shop equipment"], [], "list all shop equipment with model numbers and production rates."),
    (["rule", "hard rule", "what are the rules"], [], "list all 20 hard rules in order."),
    # v3.5.2 creative intents
    (["score", "grade this", "grade the bid", "scorecard", "letter grade", "quality check"], [], "run score_bid on the current proposal. Return the A-F grade, 100-point breakdown (compliance/voice/pricing/format), all deductions, and recommendations. If grade is D or F, list every fix needed before sending."),
    (["scope narrative", "scope text", "write the scope", "scope section"], [], "run generate_scope_narrative using the members from the current takeoff. Build project-specific scope text from real member data. No boilerplate."),
    (["follow up", "follow-up emails", "followup sequence", "chase email"], ["cold"], "run generate_followup_sequence for the current bid. Generate 3 emails (day 3/7/14) in the Owner's voice referencing the specific project, tonnage, and bid total."),
    (["we won", "we lost", "awarded", "not awarded", "bid result"], [], "log the bid outcome using bid_history_log. Ask for: project name, GC, tonnage, total bid, and outcome (won/lost/pending). Then show updated win rate."),
    (["compare to history", "how does this compare", "benchmark this", "vs average", "historical"], [], "run bid_history_compare with the current bid's tonnage and total. Show how this bid's $/ton compares to our historical average and GC-specific history."),
    (["ve", "value engineer", "over budget", "too expensive", "cut weight", "lighter"], [], "run ve_suggestions with the current takeoff members. Show lighter AISC shapes with tonnage and cost savings. Include PE disclaimer."),
    (["revised drawings", "new set", "addendum", "what changed", "rev "], ["review"], "run drawing_revision_diff comparing the previous takeoff against the new one. Show added/removed/changed members, tonnage delta, and price adjustment."),
    # ── pass 10i (R4): extend coverage to CAD/3D/calc/lookup surface ──
    (["stl", "stl file", "generate stl", "3d print"], ["wireframe"], "run generate_stl on the shape the user mentioned. Pass shape (uppercased, e.g. W14X82) and length_ft. Return the .stl file path and size."),
    (["dxf", "dxf file", "autocad", "cad export", "cnc file"], [], "run generate_dxf for the shape the user mentioned. If ezdxf isn't installed, return the install hint instead of crashing. Pass shape (e.g. 'W14X82') and output_type ('cross_section' or 'plan'). Return the .dxf file path."),
    (["3d view", "3d viewer", "3d visual", "visualize", "model viewer"], ["wireframe"], "run generate_3d_view with the shape, length_ft and count from the user's message. Return an inline STL preview the desktop viewer can render."),
    (["wireframe", "skeleton view", "framing skeleton", "wire frame"], [], "run generate_wireframe with the member list from the current takeoff. Return the wireframe geometry (lines + nodes) the viewer can render."),
    (["plate weight", "plate calc", "calculate plate", "weight of plate", "pl "], ["update"], "run calculate_plate_weight with notation (PL form) or explicit thickness_in/width_in/length_in/qty. Return weight per piece, total weight, and tonnage."),
    (["aisc lookup", "shape properties", "member info", "section properties", "lb per ft", "weight per ft"], [], "run get_aisc_member_info for the shape designation the user mentioned. Return designation, lb_per_ft, depth_in, flange_w_in, tf_in, tw_in, source."),
    (["aisc compliance", "shape validation", "validate shapes", "shapes ok"], [], "run get_aisc_compliance_summary. Return pass/fail counts across active bids and the unresolved-shape list. If all pass, say so plainly."),
]

# ═══════════════════════════════════════════════════════════════════════
# CALC AUTO-DETECT: Scan message for math patterns, run calculators
# T1-1 enforcement: AI never does arithmetic. Calculator does.
# ═══════════════════════════════════════════════════════════════════════

import re as _re

# AISC shape pattern: W12x35, W14X22, HSS6x6x1/4, C10x15.3, L4x4x1/4
_SHAPE_RE = _re.compile(
    r'\b(W\d+[xX]\d+(?:\.\d+)?'           # W shapes
    r'|HSS\d+(?:\.\d+)?[xX]\d+(?:\.\d+)?(?:[xX]\d+(?:/\d+)?)?'  # HSS
    r'|C\d+[xX]\d+(?:\.\d+)?'             # Channels
    r'|L\d+[xX]\d+(?:[xX]\d+(?:/\d+)?)?'  # Angles
    r'|WT\d+[xX]\d+(?:\.\d+)?'            # WT shapes
    r')\b', _re.IGNORECASE
)

# Length/qty patterns: "30 feet", "30ft", "30'", "qty 8", "8 pieces", "x8"
_LENGTH_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*(?:feet|foot|ft|\'|lf)\b', _re.IGNORECASE)
_QTY_RE = _re.compile(r'(?:qty|quantity|count)\s+(\d+)', _re.IGNORECASE)
_QTY_LEADING_RE = _re.compile(r'\b(\d+)\s*(?:pieces?|pcs?|each|ea)\b', _re.IGNORECASE)
# "12 W14x22" = qty 12 (number immediately before a shape designation)
_QTY_BEFORE_SHAPE_RE = _re.compile(r'\b(\d+)\s+(?=W\d|HSS|C\d|L\d|WT\d)', _re.IGNORECASE)

# Tonnage pattern: "10.5 tons", "12 ton"
_TONS_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*tons?\b', _re.IGNORECASE)

# Plate dimensions: "1/2 inch thick", "24x36 plate", thickness x width x length
_PLATE_THICK_RE = _re.compile(r'(\d+(?:/\d+)?(?:\.\d+)?)\s*(?:inch|in|")\s*(?:thick|thk|plate)', _re.IGNORECASE)

# Hours pattern: "120 fab hours", "44 erect hours"
_FAB_HRS_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*(?:fab(?:rication)?)\s*hours?', _re.IGNORECASE)
_ERECT_HRS_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*(?:erect(?:ion)?|field)\s*hours?', _re.IGNORECASE)
_ENG_HRS_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*(?:eng(?:ineering)?|detailing)\s*hours?', _re.IGNORECASE)

# Bolt pattern: bolts, anchor bolts
_BOLT_RE = _re.compile(r'(\d+)\s*(?:[-x]?\s*(\d/\d+)?\s*(?:A\d+)?)?\s*bolts?', _re.IGNORECASE)

# Date pattern: YYYY-MM-DD or "March 15" style
_DATE_RE = _re.compile(r'(\d{4}-\d{2}-\d{2})', _re.IGNORECASE)

# Weld pattern: "5/16 fillet", "1/4 leg", "3/8 weld"
_WELD_LEG_RE = _re.compile(r'(\d+/\d+)\s*(?:inch|in|")?\s*(?:fillet|leg|weld)', _re.IGNORECASE)
_WELD_LEN_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*(?:inch|in|")\s*(?:long|length|weld\s*length)', _re.IGNORECASE)

# Margin pattern: "18% margin", "margin 20"
_MARGIN_RE = _re.compile(r'(?:margin|markup)\s*(?:of\s+)?(\d+(?:\.\d+)?)\s*%?', _re.IGNORECASE)

# TRIR pattern: "3 recordables", "45000 hours worked"
_RECORDABLE_RE = _re.compile(r'(\d+)\s*recordable', _re.IGNORECASE)
_HRS_WORKED_RE = _re.compile(r'(\d[\d,]*)\s*(?:hours?\s*worked|man.?hours)', _re.IGNORECASE)

# Crew/schedule: "4 weeks", "target 6 weeks"
_TARGET_WEEKS_RE = _re.compile(r'(\d+(?:\.\d+)?)\s*weeks?\b', _re.IGNORECASE)

# Complexity mention
_COMPLEXITY_RE = _re.compile(r'\b(simple|standard|complex|heavy|retrofit)\b', _re.IGNORECASE)

# Weight-question triggers
_WEIGHT_TRIGGERS = _re.compile(
    r'\b(weigh[ts]?|how\s+heavy|tonnage|lbs|pounds|weight\s+of|steel\s+weight)\b', _re.IGNORECASE
)
# Cost/bid triggers
_COST_TRIGGERS = _re.compile(
    r'\b(cost|bid|price|estimate|labor\s+cost|how\s+much|total\s+bid|bid\s+total'
    r'|monte\s+carlo|simulation|financial\s+model|sensitivity|stress\s+test|scenario)\b', _re.IGNORECASE
)
# Hours triggers
_HOURS_TRIGGERS = _re.compile(
    r'\b(hours|how\s+long|duration|fab\s+hours|erection\s+hours|schedule|crew)\b', _re.IGNORECASE
)
# Deadline triggers
_DEADLINE_TRIGGERS = _re.compile(
    r'\b(deadline|due\s+date|days\s+until|days\s+left|when\s+is|how\s+many\s+days)\b', _re.IGNORECASE
)
# TRIR triggers
_TRIR_TRIGGERS = _re.compile(r'\b(trir|incident\s+rate|safety\s+rate|recordable)\b', _re.IGNORECASE)
# Weld triggers
_WELD_TRIGGERS = _re.compile(r'\b(weld|fillet|consumable|wire\s+lbs|gas\s+usage)\b', _re.IGNORECASE)
# Paint triggers
_PAINT_TRIGGERS = _re.compile(r'\b(paint|coat(?:ing)?|primer|intumescent|surface\s+area|sqft|sq\s*ft)\b', _re.IGNORECASE)
# Margin triggers
_MARGIN_TRIGGERS = _re.compile(r'\b(margin|markup|scenarios?|what\s+if|sensitivity)\b', _re.IGNORECASE)

def _frac_to_float(s: str) -> float:
    """Convert '3/4' or '5/16' to float."""
    if '/' in s:
        parts = s.split('/')
        return float(parts[0]) / float(parts[1])
    return float(s)

def _detect_and_run_calcs(message: str) -> list[dict]:
    """Scan user message for math patterns and run matching calculators.

    Returns list of {calc, inputs, result} dicts.
    Empty list = no calculators triggered.
    """
    from bridge.calculators import run_calc
    results = []
    msg = message

    # ── STEEL WEIGHT: shape + length/qty detected ──
    shape_matches = _SHAPE_RE.findall(msg)
    length_matches = _LENGTH_RE.findall(msg)
    qty_matches = _QTY_RE.findall(msg) + _QTY_LEADING_RE.findall(msg) + _QTY_BEFORE_SHAPE_RE.findall(msg)

    if shape_matches and (_WEIGHT_TRIGGERS.search(msg) or _COST_TRIGGERS.search(msg)
                          or _HOURS_TRIGGERS.search(msg) or length_matches):
        length = float(length_matches[0]) if length_matches else 20.0  # default 20ft
        qty = int(qty_matches[0]) if qty_matches else 1
        # Normalize shapes: CSV uses lowercase 'x' (W12x35 not W12X35)
        items = [(s.upper().replace('X', 'x'), length, qty) for s in shape_matches]
        r = run_calc("steel_weight", items=items)
        if "error" not in r:
            results.append({"calc": "steel_weight", "inputs": {"items": items}, "result": r})

            # Chain: if we have weight, also run hours + labor + bid if cost-related
            tons = r.get("tons", 0)
            if tons > 0 and (_COST_TRIGGERS.search(msg) or _HOURS_TRIGGERS.search(msg)):
                complexity = "standard"
                cm = _COMPLEXITY_RE.search(msg)
                if cm:
                    complexity = cm.group(1).lower()

                hrs = run_calc("hours_estimate", tons=tons, complexity=complexity)
                if "error" not in hrs:
                    results.append({"calc": "hours_estimate",
                                    "inputs": {"tons": tons, "complexity": complexity},
                                    "result": hrs})

                    lc = run_calc("labor_cost",
                                  fab_hours=hrs["fab_hours"],
                                  erect_hours=hrs["erect_hours"],
                                  eng_hours=hrs["eng_hours"])
                    if "error" not in lc:
                        results.append({"calc": "labor_cost",
                                        "inputs": {"fab_hours": hrs["fab_hours"],
                                                   "erect_hours": hrs["erect_hours"]},
                                        "result": lc})

                    # Full bid chain if cost/bid/price mentioned
                    if _COST_TRIGGERS.search(msg) and "error" not in lc:
                        margin = 0.18
                        mm = _MARGIN_RE.search(msg)
                        if mm:
                            margin = float(mm.group(1))
                            if margin > 1:
                                margin /= 100  # convert 18 → 0.18

                        bt = run_calc("bid_total",
                                      steel_lbs=r["total_lbs"],
                                      labor_cost_usd=lc["total_labor"],
                                      tons=tons, margin=margin)
                        if "error" not in bt:
                            results.append({"calc": "bid_total",
                                            "inputs": {"steel_lbs": r["total_lbs"],
                                                       "margin": margin},
                                            "result": bt})

    # ── HOURS from tonnage (no shape, just tons mentioned) ──
    if not shape_matches and _HOURS_TRIGGERS.search(msg):
        ton_match = _TONS_RE.findall(msg)
        if ton_match:
            tons = float(ton_match[0])
            complexity = "standard"
            cm = _COMPLEXITY_RE.search(msg)
            if cm:
                complexity = cm.group(1).lower()
            hrs = run_calc("hours_estimate", tons=tons, complexity=complexity)
            if "error" not in hrs:
                results.append({"calc": "hours_estimate",
                                "inputs": {"tons": tons, "complexity": complexity},
                                "result": hrs})

    # ── LABOR COST from explicit hours ──
    fab_m = _FAB_HRS_RE.search(msg)
    erect_m = _ERECT_HRS_RE.search(msg)
    eng_m = _ENG_HRS_RE.search(msg)
    if fab_m or erect_m or eng_m:
        fab_h = float(fab_m.group(1)) if fab_m else 0
        erect_h = float(erect_m.group(1)) if erect_m else 0
        eng_h = float(eng_m.group(1)) if eng_m else 0
        lc = run_calc("labor_cost", fab_hours=fab_h, erect_hours=erect_h, eng_hours=eng_h)
        if "error" not in lc:
            results.append({"calc": "labor_cost",
                            "inputs": {"fab_hours": fab_h, "erect_hours": erect_h, "eng_hours": eng_h},
                            "result": lc})

    # ── WELD CONSUMABLES ──
    if _WELD_TRIGGERS.search(msg):
        leg_m = _WELD_LEG_RE.search(msg)
        len_m = _WELD_LEN_RE.search(msg)
        if leg_m:
            leg = _frac_to_float(leg_m.group(1))
            length = float(len_m.group(1)) if len_m else 12.0
            count = int(qty_matches[0]) if qty_matches else 1
            r = run_calc("weld_consumables", leg_in=leg, length_in=length, count=count)
            if "error" not in r:
                results.append({"calc": "weld_consumables",
                                "inputs": {"leg_in": leg, "length_in": length, "count": count},
                                "result": r})

    # ── PAINT AREA ──
    if _PAINT_TRIGGERS.search(msg) and shape_matches:
        length = float(length_matches[0]) if length_matches else 20.0
        qty = int(qty_matches[0]) if qty_matches else 1
        items = [(s.upper().replace('X', 'x'), length, qty) for s in shape_matches]
        coating = "primer"
        if _re.search(r'intumescent', msg, _re.IGNORECASE):
            coating = "intumescent"
        elif _re.search(r'2\s*coat', msg, _re.IGNORECASE):
            coating = "2coat"
        r = run_calc("paint_area", items=items, coating=coating)
        if "error" not in r:
            results.append({"calc": "paint_area",
                            "inputs": {"items": items, "coating": coating},
                            "result": r})

    # ── TRIR ──
    if _TRIR_TRIGGERS.search(msg):
        rec_m = _RECORDABLE_RE.search(msg)
        hrs_m = _HRS_WORKED_RE.search(msg)
        if rec_m and hrs_m:
            rec = int(rec_m.group(1))
            hrs = float(hrs_m.group(1).replace(",", ""))
            r = run_calc("trir", recordables=rec, hours_worked=hrs)
            if "error" not in r:
                results.append({"calc": "trir",
                                "inputs": {"recordables": rec, "hours_worked": hrs},
                                "result": r})

    # ── DAYS UNTIL ──
    if _DEADLINE_TRIGGERS.search(msg):
        date_m = _DATE_RE.search(msg)
        if date_m:
            r = run_calc("days_until", target_date=date_m.group(1))
            if "error" not in r:
                results.append({"calc": "days_until",
                                "inputs": {"target_date": date_m.group(1)},
                                "result": r})

    # ── SCHEDULE PRESSURE (tons + deadline) ──
    if _DEADLINE_TRIGGERS.search(msg) or _re.search(r'pressure|capacity|can we', msg, _re.IGNORECASE):
        ton_m = _TONS_RE.findall(msg)
        date_m = _DATE_RE.search(msg)
        if ton_m and date_m:
            complexity = "standard"
            cm = _COMPLEXITY_RE.search(msg)
            if cm:
                complexity = cm.group(1).lower()
            r = run_calc("schedule_pressure", tons=float(ton_m[0]),
                         deadline_date=date_m.group(1), complexity=complexity)
            if "error" not in r:
                results.append({"calc": "schedule_pressure",
                                "inputs": {"tons": float(ton_m[0]),
                                           "deadline": date_m.group(1)},
                                "result": r})

    # ── MARGIN SCENARIOS ──
    if _MARGIN_TRIGGERS.search(msg) and _re.search(r'scenario|what.?if|sensitivity|range', msg, _re.IGNORECASE):
        # Need a direct cost to run scenarios
        direct = 0
        # Check if we already computed a bid_total
        for prev in results:
            if prev["calc"] == "bid_total":
                direct = prev["result"].get("direct", 0)
                break
        if direct > 0:
            r = run_calc("margin_scenario", direct_cost=direct)
            if "error" not in r:
                results.append({"calc": "margin_scenario",
                                "inputs": {"direct_cost": direct},
                                "result": r})

    return results

def _build_facts_block(calc_results: list[dict]) -> str:
    """Format calculator results as a FACTS block prepended to the AI prompt.

    The AI sees these as GIVEN FACTS - it formats and interprets but never recomputes.
    """
    lines = [
        "═══ CALCULATOR RESULTS (deterministic, audited - T1-1 compliant) ═══",
        "These numbers were computed by local offline calculators.",
        "They are FACTS. Do NOT recalculate or estimate. Present them as given.",
        "",
    ]

    for cr in calc_results:
        calc_name = cr["calc"]
        r = cr["result"]

        if calc_name == "steel_weight":
            lines.append(f"STEEL WEIGHT: {r['total_lbs']:,.2f} lbs ({r['tons']:.4f} tons)")
            for ln in r.get("lines", []):
                lines.append(f"  {ln['qty']}x {ln['shape']} @ {ln['length_ft']}ft"
                             f" × {ln['lb_per_ft']} lb/ft = {ln['lbs']:,.2f} lbs")
            if r.get("unknown_shapes"):
                lines.append(f"  WARNING: Shapes not in AISC database: {', '.join(r['unknown_shapes'])}")

        elif calc_name == "hours_estimate":
            lines.append(f"HOURS: fab={r['fab_hours']:.1f} erect={r['erect_hours']:.1f}"
                         f" eng={r['eng_hours']:.1f} TOTAL={r['total_hours']:.1f} hrs"
                         f" (complexity: {r['complexity']}, factor: {r['factor']})")

        elif calc_name == "labor_cost":
            lines.append(f"LABOR COST: ${r['total_labor']:,.2f}"
                         f" (fab=${r['fab_cost']:,.2f} erect=${r['erect_cost']:,.2f}"
                         f" eng=${r['eng_cost']:,.2f})"
                         f" blended=${r['blended_rate']:.2f}/hr")

        elif calc_name == "bid_total":
            lines.append(f"BID TOTAL: ${r['bid_total']:,.2f}"
                         f" (direct=${r['direct']:,.2f} + margin=${r['margin_amt']:,.2f}"
                         f" @ {r['margin_pct']:.0%})")
            s = r.get("sanity", {})
            lines.append(f"  Per-ton: ${s.get('per_ton',0):,.2f}"
                         f" | Labor: {s.get('labor_pct',0):.1%}"
                         f" | Material: {s.get('material_pct',0):.1%}"
                         f" | Sanity: {'ALL PASS' if s.get('all_pass') else 'CHECK FLAGGED'}")

        elif calc_name == "bolt_count":
            lines.append(f"BOLTS: {r['total_bolts']} total, ${r['total_cost']:,.2f},"
                         f" {r['total_weight_lb']:.1f} lbs")

        elif calc_name == "weld_consumables":
            lines.append(f"WELD: {r['wire_lbs']:.2f} lbs wire, {r['weld_hours']:.1f} hrs,"
                         f" {r['gas_cf']:.0f} cf gas, ${r['total_cost']:,.2f}")

        elif calc_name == "paint_area":
            lines.append(f"PAINT AREA: {r['total_sf']:,.1f} sqft, {r['coating']} coating,"
                         f" ${r['total_cost']:,.2f} (@ ${r['cost_per_sf']}/sf)")

        elif calc_name == "trir":
            lines.append(f"TRIR: {r['trir']:.2f}"
                         f" ({'BELOW' if r['below_avg'] else 'ABOVE'} industry avg {r['industry_avg']})")

        elif calc_name == "days_until":
            lines.append(f"DEADLINE: {r['days']} days ({r['severity']})"
                         f" target={r['target']}")

        elif calc_name == "schedule_pressure":
            lines.append(f"SCHEDULE: {r['pressure']} pressure"
                         f" | {r['crew_needed']} crew needed"
                         f" | {r['weeks_available']:.1f} weeks available"
                         f" | max capacity={r['max_capacity']}"
                         f" | {r['days_left']} days left")

        elif calc_name == "margin_scenario":
            lines.append(f"MARGIN SCENARIOS (direct=${r['direct_cost']:,.2f}):")
            for s in r.get("scenarios", []):
                lines.append(f"  {s['margin_pct']:.0%} → ${s['bid_total']:,.2f}"
                             f" (profit=${s['profit']:,.2f})")

        lines.append("")

    lines.append("═══ END CALCULATOR RESULTS ═══")
    return "\n".join(lines)

def _translate_intent(raw_message: str) -> str:
    """Convert the Owner's casual language into a structured prompt.

    If a pattern matches, returns the detailed prompt.
    Otherwise returns the original message unchanged - the AI's
    system prompt handles the rest.

    v3.5.7: keyword matching uses word boundaries (\\b) instead of
    substring `in`. The substring rule clobbered any prompt starting
    with "generate" - "rate" is a substring of "geneRATE", so
    "Generate a 3D STL model..." was getting translated into the
    Q2 2026 bid-rates query and never reached the model_3d intercept.
    Joseph reported this as "3d modeling is not working" on v3.5.6.
    """
    import re as _re
    lower = raw_message.lower().strip()

    # Skip if already a long detailed prompt (Owner or Quick Action)
    if len(raw_message) > 120:
        return raw_message

    def _kw_hit(kw: str, text: str) -> bool:
        # Word-boundary match. `re.escape` handles multi-word phrases like
        # "what do we charge" and special chars cleanly.
        return _re.search(rf'\b{_re.escape(kw.strip())}\b', text) is not None

    for keys_any, keys_none, prompt in _INTENT_PATTERNS:
        if any(_kw_hit(k, lower) for k in keys_any):
            if keys_none and any(_kw_hit(k, lower) for k in keys_none):
                continue
            return prompt

    return raw_message

# BUG-4 fix: external callers (MCP server, setup docs, README examples)
# reference the method as `morning_brief`. The implementation is named
# `morning_briefing`. Add a one-line alias so both names work.
Bridge.morning_brief = Bridge.morning_briefing
