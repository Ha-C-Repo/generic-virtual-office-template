"""
Your Company Virtual Office - API Integrator

The engine that adds new AI APIs to the Virtual Office through chat.

Workflow:
  1. User says "Add SketchDeck AI for blueprint analysis"
  2. detect_integration_request() parses the service name + purpose
  3. research_api() → Gemini researches endpoints, auth, capabilities
  4. design_integration() → Claude designs how it maps to VO features
  5. generate_integration_code() → Claude writes the adapter module
  6. prompt_for_key() → System asks user for API key
  7. activate() → Key stored encrypted, integration hot-loaded

The entire flow runs through the chat - no manual coding needed.
"""

import json, re, os, importlib, traceback
from datetime import datetime, timezone
from pathlib import Path

_EXT_DIR = Path(__file__).resolve().parent.parent / "extensions"


# ══════════════════════════════════════════════════════════════════
#  STEP 1: DETECT - Is this an API integration request?
# ══════════════════════════════════════════════════════════════════

# Patterns that indicate the user wants to add an external API
_INTEGRATION_PATTERNS = [
    r"(?:add|integrate|connect|hook up|set up|use|incorporate)\s+(.+?)(?:\s+(?:api|service|tool|platform|for|to)\b)",
    r"(?:add|integrate|connect|incorporate)\s+(.+?)(?:\s+(?:into|to|with)\s+(?:the|our|my)\s+(?:virtual office|vo|system|app))",
    r"(?:can (?:you|we)|i want to)\s+(?:add|use|integrate)\s+(.+?)(?:\s+(?:api|for|to)\b)",
    r"paste.*(?:api|key).*(?:for|from)\s+(.+)",
    r"here(?:'s| is) (?:the|my)\s+(.+?)(?:\s+(?:api|key))",
]

# Keywords that suggest this is about an API, not a general question
_API_SIGNALS = [
    "api", "key", "integrate", "add", "connect", "incorporate", "hook up",
    "endpoint", "sdk", "service", "platform", "plugin",
]


def detect_integration_request(message: str) -> dict:
    """Detect if a message is requesting an API integration.

    Returns:
      {"is_integration": True, "service_name": "SketchDeck", "purpose": "blueprint analysis"}
      or {"is_integration": False}
    """
    # vj: parity-ok (pass 10g classified: mixed J=0.40; needs manual audit)
    msg_lower = message.lower()

    # Check for API signals
    has_signal = any(s in msg_lower for s in _API_SIGNALS)
    if not has_signal:
        return {"is_integration": False}

    # Check if this is a key paste (user providing an API key)
    key_match = re.search(
        r"(?:here(?:'s| is)|paste|my)\s+(?:the\s+)?(.+?)\s*(?:api\s*)?key\s*[:=]?\s*([A-Za-z0-9_\-]{20,})",
        message, re.IGNORECASE
    )
    if key_match:
        return {
            "is_integration": True,
            "type": "key_paste",
            "service_name": key_match.group(1).strip(),
            "api_key": key_match.group(2).strip(),
        }

    # Check for integration request patterns
    for pattern in _INTEGRATION_PATTERNS:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            service_raw = m.group(1).strip()
            # Clean up service name
            service = re.sub(r"^(the|a|an)\s+", "", service_raw, flags=re.IGNORECASE)
            service = re.sub(r"\s*(api|service|tool|platform)$", "", service, flags=re.IGNORECASE).strip()

            # Extract purpose (what comes after "for")
            purpose_match = re.search(r"for\s+(.+?)(?:\.|$)", message, re.IGNORECASE)
            purpose = purpose_match.group(1).strip() if purpose_match else ""

            if len(service) >= 2:
                return {
                    "is_integration": True,
                    "type": "new_api",
                    "service_name": service,
                    "purpose": purpose,
                    "raw": service_raw,
                }

    return {"is_integration": False}


# ══════════════════════════════════════════════════════════════════
#  STEP 2: RESEARCH - Gemini investigates the API
# ══════════════════════════════════════════════════════════════════

RESEARCH_PROMPT = """You are researching an external AI API for the Your Company Virtual Office.
This is a structural steel fabrication company in Houston, TX.

Research the following service and provide a structured JSON response:

Service: {service_name}
Purpose: {purpose}

Return ONLY valid JSON with this structure:
{{
  "name": "Official service name",
  "provider": "Company that makes it",
  "base_url": "API base URL (e.g. https://api.example.com/v1)",
  "documentation_url": "Link to API docs",
  "auth_method": "bearer | api_key_header | api_key_param",
  "auth_header": "Header name if api_key_header (e.g. X-API-Key)",
  "capabilities": ["list", "of", "what", "it", "can", "do"],
  "relevant_endpoints": [
    {{"method": "POST", "path": "/analyze", "description": "What it does"}}
  ],
  "pricing": "Free tier details or cost per call",
  "steel_relevance": "How this API specifically helps a structural steel company",
  "vo_features": {{
    "bid_scanning": "How it improves bid scanning (or null)",
    "estimating": "How it improves estimating (or null)",
    "fabrication": "How it improves fabrication/3D modeling (or null)",
    "compliance": "How it improves compliance (or null)",
    "communication": "How it improves email/communication (or null)",
    "document_generation": "How it improves document generation (or null)"
  }},
  "integration_difficulty": "easy | medium | hard",
  "recommended": true
}}

If you cannot find information about this service, set recommended to false and explain why in steel_relevance.
Return ONLY the JSON object, no markdown, no backticks, no explanation."""


def research_api(service_name: str, purpose: str, keys: dict) -> dict:
    """Send Gemini to research the API. Returns parsed research data."""
    google_key = keys.get("GOOGLE_API_KEY", "")
    if not google_key:
        return {"error": "Gemini API key required for research. Add Google API key first."}

    prompt = RESEARCH_PROMPT.format(service_name=service_name, purpose=purpose)

    try:
        # v3.5.6: migrated from deprecated google-generativeai to google-genai.
        from bridge.gemini_compat import make_client
        client = make_client(google_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = resp.text.strip()

        # Clean JSON from potential markdown wrapping
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        data = json.loads(text)
        data["_researched_at"] = datetime.now(timezone.utc).isoformat()
        data["_researched_by"] = "gemini-2.5-flash"
        return data

    except json.JSONDecodeError as e:
        return {"error": f"Gemini returned invalid JSON: {str(e)[:100]}", "raw": text[:500]}
    except Exception as e:
        return {"error": f"Research failed: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════
#  STEP 3: DESIGN - Claude designs the integration
# ══════════════════════════════════════════════════════════════════

DESIGN_PROMPT = """You are the Your Company Virtual Office integration architect.
A new API has been researched. Design how to integrate it.

API Research:
{research_json}

Virtual Office Current Capabilities:
- 13 offline steel calculators (weight, bolt, weld, crane, deck, etc.)
- Bid scanner with PEMB disqualifier, 200-mile Houston filter
- Cold email drafting with contact database personalization
- Bid proposal PDF generation (reportlab)
- 3D model generation (STL), DXF section drawings, G-code
- Monte Carlo risk simulation
- Compliance tracking (ISNetworld, OSHA, WC)
- Bid pipeline with lifecycle states
- Project cost tracking with variance

Design the integration. Return ONLY valid JSON:
{{
  "provider_key": "lowercase_slug_for_registry",
  "feature_map": {{
    "feature_name": "how this API enhances it"
  }},
  "integration_points": [
    {{
      "target": "Which existing module to modify (e.g. bid_scanner, fabrication, pipeline)",
      "method": "What to add or replace",
      "description": "What changes and why"
    }}
  ],
  "new_bridge_methods": [
    {{
      "name": "method_name",
      "params": "param1: str, param2: int",
      "description": "What this method does"
    }}
  ],
  "setup_instructions": "What the user needs to do (just paste the key usually)",
  "estimated_impact": "How this measurably improves the Owner's workflow"
}}

Return ONLY the JSON object."""


def design_integration(research: dict, keys: dict) -> dict:
    """Claude designs how the API integrates with the Virtual Office."""
    claude_key = keys.get("ANTHROPIC_API_KEY", "")
    if not claude_key:
        return {"error": "Claude API key required for design."}

    prompt = DESIGN_PROMPT.format(research_json=json.dumps(research, indent=2)[:4000])

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=claude_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Claude returned invalid JSON", "raw": text[:500]}
    except Exception as e:
        return {"error": f"Design failed: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════
#  STEP 4: GENERATE - Claude writes the adapter code
# ══════════════════════════════════════════════════════════════════

CODEGEN_PROMPT = """Write a Python adapter module for the Your Company Virtual Office.

API: {api_name}
Base URL: {base_url}
Auth: {auth_method}
Endpoints: {endpoints}

Design spec:
{design_json}

Requirements:
1. Module must be self-contained (one .py file)
2. All API calls use httpx or requests
3. Auth key loaded from environment: os.environ.get("{key_env}")
4. Include error handling with try/except on every call
5. Include a test_connection() function
6. Include docstring explaining what each function does
7. Functions must return plain dicts (not objects)

Write ONLY the Python code. No markdown, no backticks, no explanation.
Start with the import statements."""


def generate_adapter(api_name: str, base_url: str, auth_method: str,
                     key_env: str, endpoints: list, design: dict,
                     keys: dict) -> dict:
    """Claude generates the Python adapter module."""
    claude_key = keys.get("ANTHROPIC_API_KEY", "")
    if not claude_key:
        return {"error": "Claude API key required for code generation."}

    prompt = CODEGEN_PROMPT.format(
        api_name=api_name, base_url=base_url, auth_method=auth_method,
        key_env=key_env, endpoints=json.dumps(endpoints[:5], indent=2),
        design_json=json.dumps(design, indent=2)[:3000],
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=claude_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        code = resp.content[0].text.strip()
        code = re.sub(r"^```(?:python)?\s*", "", code)
        code = re.sub(r"\s*```$", "", code)

        return {"code": code, "success": True}
    except Exception as e:
        return {"error": f"Code generation failed: {str(e)[:200]}"}


# ══════════════════════════════════════════════════════════════════
#  STEP 5: INSTALL - Save adapter, register in registry, hot-load
# ══════════════════════════════════════════════════════════════════

def install_adapter(provider_key: str, code: str, research: dict, design: dict) -> dict:
    """Save the generated adapter and register it."""
    _EXT_DIR.mkdir(parents=True, exist_ok=True)

    # Save the adapter module
    module_name = f"api_{provider_key}"
    module_path = _EXT_DIR / f"{module_name}.py"
    module_path.write_text(code)

    # Register in the API registry
    from bridge.api_registry import register
    entry = register(
        key=provider_key,
        name=research.get("name", provider_key),
        provider=research.get("provider", provider_key),
        base_url=research.get("base_url", ""),
        auth_method=research.get("auth_method", "bearer"),
        key_env=design.get("key_env", f"{provider_key.upper()}_API_KEY"),
        capabilities=research.get("capabilities", []),
        feature_map=design.get("feature_map", {}),
        endpoints=research.get("relevant_endpoints", []),
        documentation=research.get("documentation_url", ""),
        research_summary=json.dumps(research)[:3000],
        integration_code=str(module_path),
        status="pending_key",
    )

    # Log in audit
    try:
        from bridge.audit import log
        log("system", "api_integration", f"Installed adapter for {provider_key}")
    except Exception:
        pass

    return {
        "success": True,
        "module_path": str(module_path),
        "provider_key": provider_key,
        "status": "pending_key",
        "message": f"Integration installed. Paste your {research.get('name', provider_key)} API key to activate.",
    }


def activate_with_key(provider_key: str, api_key: str) -> dict:
    """Activate an integration after user provides their key."""
    from bridge.api_registry import activate, get

    entry = get(provider_key)
    if not entry:
        return {"error": f"No integration found for '{provider_key}'"}

    # Store the key
    key_env = entry.get("key_env", f"{provider_key.upper()}_API_KEY")
    os.environ[key_env] = api_key

    # Also encrypt for persistence
    try:
        from bridge.keyvault import load_keys, store_keys
        keys = load_keys()
        keys[key_env] = api_key
        store_keys(keys)
    except Exception:
        pass

    # Activate in registry
    activate(provider_key, api_key)

    # Try to load and test the adapter
    test_result = None
    try:
        module_path = entry.get("integration_code", "")
        if module_path:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"api_{provider_key}", module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "test_connection"):
                test_result = mod.test_connection()
    except Exception as e:
        test_result = {"error": str(e)[:200]}

    # Log
    try:
        from bridge.audit import log
        log("system", "api_activated", f"Activated {provider_key}")
    except Exception:
        pass

    return {
        "success": True,
        "provider_key": provider_key,
        "status": "active",
        "test_result": test_result,
        "message": f"{entry.get('name', provider_key)} is now active in your Virtual Office.",
    }


# ══════════════════════════════════════════════════════════════════
#  ORCHESTRATOR - The full integration pipeline
# ══════════════════════════════════════════════════════════════════

def run_full_integration(service_name: str, purpose: str, keys: dict) -> dict:
    """Run the complete integration pipeline:
    1. Research (Gemini)
    2. Design (Claude)
    3. Generate code (Claude)
    4. Install adapter
    5. Return status + prompt for key

    This is what gets called when the user says "add SketchDeck AI for blueprint analysis"
    """
    result = {
        "service": service_name,
        "purpose": purpose,
        "steps": [],
    }

    # Step 1: Research
    result["steps"].append({"step": "research", "status": "running", "agent": "Gemini"})
    research = research_api(service_name, purpose, keys)
    if research.get("error"):
        result["steps"][-1]["status"] = "failed"
        result["error"] = research["error"]
        return result
    result["steps"][-1]["status"] = "complete"
    result["research"] = research

    # Step 2: Design
    result["steps"].append({"step": "design", "status": "running", "agent": "Claude"})
    design = design_integration(research, keys)
    if design.get("error"):
        result["steps"][-1]["status"] = "failed"
        result["error"] = design["error"]
        return result
    result["steps"][-1]["status"] = "complete"
    result["design"] = design

    provider_key = design.get("provider_key", service_name.lower().replace(" ", "_"))
    key_env = f"{provider_key.upper()}_API_KEY"

    # Step 3: Generate adapter code
    result["steps"].append({"step": "codegen", "status": "running", "agent": "Claude"})
    codegen = generate_adapter(
        api_name=research.get("name", service_name),
        base_url=research.get("base_url", ""),
        auth_method=research.get("auth_method", "bearer"),
        key_env=key_env,
        endpoints=research.get("relevant_endpoints", []),
        design=design,
        keys=keys,
    )
    if codegen.get("error"):
        result["steps"][-1]["status"] = "failed"
        result["error"] = codegen["error"]
        return result
    result["steps"][-1]["status"] = "complete"

    # Step 4: Install
    result["steps"].append({"step": "install", "status": "running", "agent": "system"})
    install = install_adapter(provider_key, codegen["code"], research, design)
    result["steps"][-1]["status"] = "complete"
    result["install"] = install

    # Final result
    result["success"] = True
    result["provider_key"] = provider_key
    result["key_env"] = key_env
    result["awaiting_key"] = True
    result["prompt"] = (
        f"✅ Integration designed and installed for **{research.get('name', service_name)}**.\n\n"
        f"**What it adds:**\n"
        + "\n".join(f"• {k}: {v}" for k, v in (design.get("feature_map") or {}).items() if v)
        + f"\n\n**To activate:** Paste your {research.get('name', service_name)} API key below.\n"
        f"The key will be encrypted and stored securely."
    )
    return result
