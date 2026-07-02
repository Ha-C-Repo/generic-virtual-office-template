"""
Your Company Virtual Office - Multi-Model Pipeline System

Architecture:
  Gemini  = research grunt (web grounding, vision, large context, cheap tokens)
  GPT-4o  = math engine (Monte Carlo, structured JSON, calculations)
  Claude  = the boss (validates, applies rules, formats in voice, catches errors)
  LOCAL   = offline calculators (deterministic, audited, zero AI tokens)

For simple tasks: single model call (unchanged).
For complex tasks: multi-step pipeline where cheaper models do heavy lifting
and Claude does lightweight validation + voice formatting.

T1-1 EXCEPTION: Advanced math (Monte Carlo, stochastic modeling, optimization,
regression) may be delegated to GPT-4o ONLY after all preliminary values have
been computed locally by offline calculators and passed as FACTS.

Claude Validator: ~300 token system prompt. Checks output against 20 hard rules.
Rewrites violations. Formats in the Owner's voice. Costs 10% of a full Claude call.
"""

# ── Claude Validator Prompt (tiny - sent after every non-Claude response) ──

VALIDATOR_PROMPT = """You are the Your Company quality gate. You receive AI output from another model.
Check it against these rules and fix violations IN PLACE. Do not add commentary.

RULES TO ENFORCE:
1. No supplier names in client-facing output. Use "qualified supplier" or ASTM/SDI spec.
2. No PE names or internal team names on output documents.
3. No headcount disclosure.
4. Engineering folded into fab + erection. Never line-itemed.
5. Never Alamo Heights / 5600 Broadway. Use: [COMPANY ADDRESS].
6. 30/20/50 payment. 40/20/40 is dead.
7. No Red Dot / PEMB-manufacturer language.
8. [FORBIDDEN PROJECT] is NOT our project.
9. No em-dashes (signals AI). Use periods or hyphens.
10. No "Great question!" or filler openers. No three-adjective lists.
11. PDF only to clients. Never .docx.
12. Literal & always. Never &amp;.
13. Deck always in scope. Never optional.

VOICE: Short sentences. Specific numbers. No filler. No hedge words.

If the output is clean, return it unchanged.
If violations found, fix them silently and return the corrected output.
Do NOT add a summary of what you changed. Just return the final text."""


# ── GPT-4o Advanced Math Handoff Prompt ───────────────────────────────
# This is prepended to GPT-4o's system prompt when it receives local calc
# FACTS for advanced computation. It enforces the T1-1 exception rules.

GPT_HANDOFF_PROMPT = """You are the Your Company advanced computation engine.

CRITICAL RULES:
1. The FACTS BLOCK below contains values pre-computed by local offline calculators.
   These are DETERMINISTIC, AUDITED numbers. Do NOT recalculate them.
   Use them exactly as given. They are your input constants.

2. Your job is ONLY the advanced computation that the local machine cannot do:
   Monte Carlo simulation, stochastic modeling, multi-variable sensitivity,
   optimization, regression, probability distributions.

3. Show your work. For Monte Carlo: state the distributions, the number of
   iterations, and return structured percentiles (P10, P25, P50, P75, P90).

4. If any pre-computed FACT seems wrong or inconsistent, FLAG IT but still
   use it. Do not substitute your own estimate. The local calculator is
   the authority for deterministic math.

5. Return structured results. Use tables, not prose, for numeric output."""


# ── Pipeline Step Definitions ──────────────────────────────────────────

def _data_step_stocks(tickers: list[str] | None = None) -> str:
    """Gather stock data without spending any AI tokens."""
    from bridge.data_sources import fetch_watchlist, fetch_stock_data

    if tickers:
        data = fetch_stock_data(tickers)
    else:
        data = fetch_watchlist()

    if "error" in data:
        return f"[DATA ERROR: {data['error']}. yfinance may not be installed.]"

    lines = ["LIVE MARKET DATA (fetched just now, no AI tokens spent):"]
    sections = data if not tickers else {"requested": data}
    for section, stocks in sections.items():
        if section == "fetched_at":
            continue
        lines.append(f"\n{section.upper()}:")
        for ticker, info in stocks.items():
            if isinstance(info, dict) and "error" not in info:
                price = info.get("price", "?")
                chg = info.get("change_pct", 0)
                arrow = "▲" if chg > 0 else "▼" if chg < 0 else "-"
                pe = info.get("pe_ratio", "N/A")
                lines.append(f"  {ticker:5} ${price:>8}  {arrow}{abs(chg):.1f}%  P/E:{pe}")
    return "\n".join(lines)


def _data_step_weather() -> str:
    """Gather Houston weather without AI tokens."""
    from bridge.data_sources import houston_weather
    w = houston_weather()
    if "error" in w:
        return f"[WEATHER ERROR: {w['error']}]"
    return f"Houston: {w['temp_f']}°F, {w['condition']}, Humidity {w['humidity']}%, Wind {w['wind_mph']}mph"


def _local_calc_step(message: str) -> str:
    """Run ALL possible offline calculators on the message BEFORE any AI call.

    This is the T1-1 exception gate: everything that CAN be computed locally
    MUST be computed locally. Only the remainder goes to GPT-4o.

    Returns a FACTS block string (empty string if no calcs triggered).
    """
    from bridge.api import _detect_and_run_calcs, _build_facts_block

    results = _detect_and_run_calcs(message)
    if not results:
        return ""

    return _build_facts_block(results)


# ── Pipeline Definitions ──────────────────────────────────────────────

PIPELINES = {
    # ── Stock Research: Gemini gathers + analyzes, Claude validates ──
    "stock_research": {
        "description": "5-agent stock research with free data + AI analysis",
        "steps": [
            {"type": "data", "fn": "_data_step_stocks",
             "inject": "prefix"},  # prepend data to user message
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": "Analyze this market data. Include: trend, key indicators, sector comparison. End with the required RESEARCH ONLY disclaimer."},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Market Data: just fetch + Gemini summary, Claude validates ──
    "market_data": {
        "description": "Quick market snapshot",
        "steps": [
            {"type": "data", "fn": "_data_step_stocks", "inject": "prefix"},
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": "Summarize this data concisely. Highlight movers. Include disclaimer."},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Drawing Analysis: Gemini reads image, Claude applies rules ──
    "drawing_vision": {
        "description": "Gemini reads the drawing, Claude enforces S-001/S-002 rules",
        "steps": [
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": "Extract all structural steel members, dimensions, and notes from this drawing. List each member mark, size, quantity, and length."},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Monte Carlo: LOCAL calcs first, then GPT-4o for simulation ──
    # T1-1 EXCEPTION: all deterministic math done locally, GPT-4o handles
    # only the stochastic simulation using pre-computed FACTS as inputs.
    "monte_carlo": {
        "description": "Local calcs → GPT-4o Monte Carlo simulation → Claude validates",
        "steps": [
            {"type": "local_calc", "inject": "prefix"},
            {"type": "ai", "provider": "openai",
             "model": "gpt-4o",
             "use_handoff_prompt": True,
             "note": (
                "Run a 1,000-iteration Monte Carlo simulation using the pre-computed "
                "FACTS as base values. Vary these parameters:\n"
                "  - Material cost: ±15% (normal distribution)\n"
                "  - Labor hours: ±20% (normal distribution)\n"
                "  - Schedule: ±2 weeks (uniform distribution)\n"
                "  - Margin: 15%-25% range (uniform)\n"
                "Return: percentile table (P10, P25, P50, P75, P90) for total bid, "
                "profit, and schedule. Include probability of exceeding budget and "
                "probability of schedule overrun. Show the distributions you used."
             )},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Financial Model: LOCAL calcs first, then GPT-4o for modeling ──
    # T1-1 EXCEPTION: base numbers computed locally, GPT-4o builds the
    # multi-period model and sensitivity analysis from those FACTS.
    "financial_model": {
        "description": "Local calcs → GPT-4o financial model → Claude validates",
        "steps": [
            {"type": "local_calc", "inject": "prefix"},
            {"type": "ai", "provider": "openai",
             "model": "gpt-4o",
             "use_handoff_prompt": True,
             "note": (
                "Build a structured financial model using the pre-computed FACTS as "
                "base inputs. Include: revenue projections, cost structure, margin "
                "analysis, break-even point, and cash flow forecast. Show all "
                "assumptions clearly. Use deterministic math for projections but "
                "note where uncertainty ranges would apply."
             )},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Sensitivity Analysis: LOCAL calcs, GPT-4o multi-variable ──
    # T1-1 EXCEPTION: base bid computed locally, GPT-4o runs >6 variable
    # sensitivity that exceeds simple margin_scenario calculator.
    "sensitivity": {
        "description": "Local calcs → GPT-4o multi-variable sensitivity → Claude validates",
        "steps": [
            {"type": "local_calc", "inject": "prefix"},
            {"type": "ai", "provider": "openai",
             "model": "gpt-4o",
             "use_handoff_prompt": True,
             "note": (
                "Using the pre-computed FACTS as base values, run a multi-variable "
                "sensitivity analysis. Vary ALL of: material cost (±15%), labor rate "
                "(±10%), overhead (1.10-1.25), complexity factor (0.85-1.50), margin "
                "(15%-25%), freight rate (±20%), coating type (paint vs galv). "
                "Present a tornado chart ranking variables by impact on total bid. "
                "Identify the 3 most sensitive variables."
             )},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Weekly Briefing: Gemini gathers context, Claude formats ──
    "briefing": {
        "description": "Gemini gathers data, Claude writes briefing in voice",
        "steps": [
            {"type": "data", "fn": "_data_step_weather", "inject": "prefix"},
            {"type": "data", "fn": "_data_step_stocks", "inject": "prefix"},
            {"type": "ai", "provider": "claude",
             "model": "claude-sonnet-4-6",
             "note": "Write the weekly briefing using the live data above. Include weather, market snapshot, then synthesize priorities and action items."},
        ],
    },

    # ═══ FABRICATION PIPELINES ═══════════════════════════════════════

    # ── 3D Model from Drawing: Gemini extracts, local builds STL ──
    "model_3d": {
        "description": "Gemini reads drawing → local AISC lookup → local STL generation",
        "steps": [
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": (
                 "Extract ALL structural steel members from this drawing. "
                 "Return a JSON array of objects, each with: "
                 "shape (AISC designation e.g. W12x35), length_ft (number), "
                 "x_ft (horizontal position), y_ft (vertical position), "
                 "z_ft (elevation), mark (member mark e.g. B1, C3). "
                 "Be precise with dimensions. Use the scale on the drawing."
             )},
            {"type": "local_calc", "inject": "prefix"},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── CNC Plasma from Drawing: Gemini extracts, local generates G-code ──
    "cnc_plasma": {
        "description": "Gemini reads plate drawing → local generates G-code",
        "steps": [
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": (
                 "Extract all plate cut contours from this drawing. "
                 "Return a JSON array of contours. Each contour is an array of "
                 "[x, y] coordinate pairs in inches. Include plate outline and "
                 "all holes/slots/cutouts as separate contours."
             )},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── CNC Drill from Drawing: Gemini extracts, local generates G-code ──
    "cnc_drill": {
        "description": "Gemini reads hole pattern → local generates drill G-code",
        "steps": [
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": (
                 "Extract ALL hole locations from this drawing. "
                 "Return a JSON array of objects: {x, y, diameter, depth, note}. "
                 "All dimensions in inches. Include bolt holes, anchor bolt holes, "
                 "and any other penetrations."
             )},
            {"type": "local_calc", "inject": "prefix"},
            {"type": "validate", "provider": "claude"},
        ],
    },

    # ── Ironworker from Drawing: Gemini extracts, local generates schedule ──
    "ironworker": {
        "description": "Gemini reads connections → local generates punch/shear/cope schedules",
        "steps": [
            {"type": "ai", "provider": "gemini",
             "model": "gemini-2.5-flash-preview-05-20",
             "note": (
                 "Extract ALL connection details from this drawing. For each connection: "
                 "mark (piece mark), material (shape or plate), thickness (inches), "
                 "hole locations [{x, y, diameter, bolt_size}], "
                 "cope details {cope_type, cope_depth, cope_length, end}, "
                 "shear cuts {length_in, width, qty}. "
                 "Return as JSON with keys: punch_connections, shear_items, cope_members."
             )},
            {"type": "local_calc", "inject": "prefix"},
            {"type": "validate", "provider": "claude"},
        ],
    },
}


# ── Pipeline Executor ──────────────────────────────────────────────────

def should_use_pipeline(task_cat: str) -> bool:
    """Check if a task should run through a multi-model pipeline."""
    return task_cat in PIPELINES


def get_pipeline_info(task_cat: str) -> dict | None:
    """Get pipeline definition for a task category."""
    return PIPELINES.get(task_cat)


def execute_pipeline(task_cat: str, message: str, keys: dict,
                     system_prompt: str, voice_note: str,
                     files: list | None = None) -> dict:
    """Execute a multi-model pipeline.

    Returns dict with: text, provider, model, pipeline_steps, tokens_saved
    """
    pipeline = PIPELINES.get(task_cat)
    if not pipeline:
        return {"error": f"No pipeline defined for {task_cat}"}

    accumulated_context = ""
    final_text = ""
    steps_log = []
    total_tokens = 0
    last_provider = "pipeline"
    last_model = "multi"
    local_calc_facts = ""  # FACTS from local calculators (for GPT handoff)

    for step in pipeline["steps"]:
        step_type = step["type"]

        if step_type == "data":
            # Pure Python data gathering - zero AI tokens
            fn_name = step["fn"]
            if fn_name == "_data_step_stocks":
                data_text = _data_step_stocks()
            elif fn_name == "_data_step_weather":
                data_text = _data_step_weather()
            else:
                data_text = "[Unknown data function]"

            if step.get("inject") == "prefix":
                accumulated_context += data_text + "\n\n"
            steps_log.append(f"DATA:{fn_name} ({len(data_text)} chars, 0 tokens)")

        elif step_type == "local_calc":
            # T1-1: Run ALL offline calculators BEFORE any AI call
            # Everything that CAN be computed locally MUST be computed locally
            facts = _local_calc_step(message)
            if facts:
                local_calc_facts = facts
                if step.get("inject") == "prefix":
                    accumulated_context += facts + "\n\n"
                # Count how many calcs ran
                calc_count = facts.count("CALCULATOR RESULTS") + facts.count("STEEL WEIGHT") + \
                             facts.count("HOURS:") + facts.count("LABOR COST") + \
                             facts.count("BID TOTAL") + facts.count("TRIR:") + \
                             facts.count("DEADLINE:") + facts.count("WELD:") + \
                             facts.count("PAINT AREA") + facts.count("SCHEDULE:")
                steps_log.append(f"LOCAL_CALC: {calc_count} calcs fired ({len(facts)} chars, 0 tokens)")
            else:
                steps_log.append("LOCAL_CALC: no calcs triggered (message has no math patterns)")

        elif step_type == "ai":
            # AI call to a specific provider
            provider = step["provider"]
            model = step["model"]
            note = step.get("note", "")
            use_handoff = step.get("use_handoff_prompt", False)

            # Build the message with accumulated context
            full_message = accumulated_context + message
            if note:
                full_message = note + "\n\nUser request: " + full_message

            # If this is a GPT-4o handoff with local calc FACTS, use the handoff prompt
            effective_system = system_prompt
            if use_handoff and local_calc_facts:
                effective_system = GPT_HANDOFF_PROMPT + "\n\n" + system_prompt
                # Ensure FACTS are in the message even if not prefix-injected
                if local_calc_facts not in full_message:
                    full_message = local_calc_facts + "\n\n" + full_message
                steps_log.append(f"GPT_HANDOFF: handoff prompt active ({len(GPT_HANDOFF_PROMPT)} chars)")

            msgs = [{"role": "user", "content": full_message}]

            # Add file content if present and this is the first AI step
            if files and not final_text:
                from bridge.api import Bridge
                content = Bridge._build_content_blocks(full_message, files, provider)
                msgs = [{"role": "user", "content": content}]

            api_key = _get_key(keys, provider)
            if not api_key:
                # Fall back to Claude
                api_key = keys.get("ANTHROPIC_API_KEY", "")
                provider = "claude"
                model = "claude-sonnet-4-6"

            try:
                if provider == "openai":
                    from bridge.api import _call_openai
                    final_text = _call_openai(api_key, model, effective_system, msgs)
                elif provider == "gemini":
                    from bridge.api import _call_gemini
                    final_text = _call_gemini(api_key, model, effective_system, msgs)
                else:
                    from bridge.api import _call_claude
                    result = _call_claude(api_key, model, effective_system + voice_note, msgs)
                    final_text = result.get("text", "")
                    total_tokens += result.get("input_tokens", 0) + result.get("output_tokens", 0)

                last_provider = provider
                last_model = model
                steps_log.append(f"AI:{provider}/{model} ({len(final_text)} chars)")
            except Exception as e:
                print(f"[pipeline] step error detail: {type(e).__name__}: {e}", flush=True)
                steps_log.append(f"AI:{provider}/{model} FAILED: {e}")
                final_text = f"[Pipeline step failed: {e}]"

        elif step_type == "validate":
            # Claude validates the output from previous step
            if not final_text or last_provider == "claude":
                steps_log.append("VALIDATE:skipped (already Claude or empty)")
                continue

            # v3.5.8: skip validation when an upstream AI step failed.
            # The ai-step exception handler sets final_text to
            # "[Pipeline step failed: <exception>]". Without this guard
            # the Claude validator received that error string as content
            # and replied "you haven't given me any AI output to check".
            # That was Joseph's quality gate misfire bug. Better: surface
            # the real error to the user instead of the gate's confused reply.
            if final_text.startswith("[Pipeline step failed"):
                steps_log.append("VALIDATE:skipped (upstream pipeline error)")
                continue

            claude_key = keys.get("ANTHROPIC_API_KEY", "")
            if not claude_key:
                steps_log.append("VALIDATE:skipped (no Claude key)")
                continue

            try:
                from bridge.api import _call_claude
                validate_msgs = [{"role": "user", "content": final_text}]
                result = _call_claude(
                    claude_key, "claude-sonnet-4-6",
                    VALIDATOR_PROMPT + voice_note,
                    validate_msgs
                )
                validated_text = result.get("text", final_text)
                v_tokens = result.get("input_tokens", 0) + result.get("output_tokens", 0)
                total_tokens += v_tokens

                # Only use validated text if it's reasonable
                if len(validated_text) > len(final_text) * 0.3:
                    final_text = validated_text
                    steps_log.append(f"VALIDATE:claude ({v_tokens} tokens)")
                else:
                    steps_log.append("VALIDATE:skipped (validator returned too little)")

            except Exception as e:
                steps_log.append(f"VALIDATE:failed ({e})")

    return {
        "text": final_text,
        "provider": "pipeline",
        "model": f"{last_provider}/{last_model}",
        "pipeline_steps": steps_log,
        "pipeline_name": task_cat,
    }


def _get_key(keys: dict, provider: str) -> str:
    """Get API key for a provider."""
    key_map = {
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    return keys.get(key_map.get(provider, ""), "")
