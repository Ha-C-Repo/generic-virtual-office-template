"""
Your Company Virtual Office - API Registry

Persistent store of every AI API the Virtual Office can use.

Built-in providers (Claude, Gemini, GPT-4o) are pre-registered.
New APIs are added dynamically through the chat:

  User: "Add SketchDeck AI for blueprint analysis"
  → Gemini researches the API
  → Claude designs the integration
  → System prompts for API key
  → Hot-loads the integration

Each API entry stores:
  - name, provider, base_url
  - auth_method (bearer, api_key_header, api_key_param)
  - capabilities (list of what it can do)
  - feature_map (which VO features it enhances)
  - endpoints (discovered by Gemini)
  - status (active, pending_key, disabled, error)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_REGISTRY = _DATA / "api_registry.json"

# Built-in providers - always available
_BUILTINS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "auth_method": "bearer",
        "key_env": "ANTHROPIC_API_KEY",
        "capabilities": ["reasoning", "code_generation", "voice_drafting", "compliance", "bid_strategy", "self_build"],
        "feature_map": {
            "ai_ask": "primary",
            "cold_email": "primary",
            "compliance": "primary",
            "bid_analysis": "primary",
            "self_build": "primary",
        },
        "status": "active",
        "builtin": True,
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "provider": "openai",
        "base_url": "https://api.openai.com",
        "auth_method": "bearer",
        "key_env": "OPENAI_API_KEY",
        "capabilities": ["structured_output", "monte_carlo", "financial_math", "pdf_generation"],
        "feature_map": {
            "monte_carlo": "primary",
            "financial_analysis": "primary",
            "structured_data": "primary",
        },
        "status": "active",
        "builtin": True,
    },
    "google": {
        "name": "Google Gemini",
        "provider": "google",
        "base_url": "https://generativelanguage.googleapis.com",
        "auth_method": "api_key_param",
        "key_env": "GOOGLE_API_KEY",
        "capabilities": ["vision", "web_grounding", "research", "multimodal", "large_context", "api_research"],
        "feature_map": {
            "drawing_vision": "primary",
            "stock_research": "primary",
            "api_research": "primary",
            "market_research": "primary",
        },
        "status": "active",
        "builtin": True,
    },
}


def _load() -> dict:
    """Load registry from disk or return builtins."""
    try:
        if _REGISTRY.exists():
            data = json.loads(_REGISTRY.read_text())
            # Ensure builtins are always present
            for k, v in _BUILTINS.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        pass
    return dict(_BUILTINS)


def _save(data: dict):
    """Persist registry to disk."""
    _DATA.mkdir(parents=True, exist_ok=True)
    _REGISTRY.write_text(json.dumps(data, indent=2, default=str))


def get_all() -> dict:
    """Return the full registry."""
    return _load()


def get(provider_key: str) -> dict:
    """Get a single API entry."""
    return _load().get(provider_key)


def get_active() -> dict:
    """Get only active APIs."""
    return {k: v for k, v in _load().items() if v.get("status") == "active"}


def get_by_capability(capability: str) -> list:
    """Find APIs that offer a specific capability."""
    results = []
    for k, v in _load().items():
        if v.get("status") == "active" and capability in v.get("capabilities", []):
            results.append({**v, "key": k})
    return results


def register(key: str, name: str, provider: str, base_url: str,
             auth_method: str = "bearer", key_env: str = "",
             capabilities: list = None, feature_map: dict = None,
             endpoints: list = None, documentation: str = "",
             research_summary: str = "", integration_code: str = "",
             status: str = "pending_key") -> dict:
    """Register a new API in the registry."""
    data = _load()
    entry = {
        "name": name,
        "provider": provider,
        "base_url": base_url,
        "auth_method": auth_method,
        "key_env": key_env or f"{key.upper()}_API_KEY",
        "capabilities": capabilities or [],
        "feature_map": feature_map or {},
        "endpoints": endpoints or [],
        "documentation": documentation[:2000],
        "research_summary": research_summary[:3000],
        "integration_code": integration_code,
        "status": status,
        "builtin": False,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "added_by": "joseph_integrator",
    }
    data[key] = entry
    _save(data)
    return entry


def activate(key: str, api_key_value: str = "") -> bool:
    """Activate an API (usually after key is provided)."""
    data = _load()
    if key not in data:
        return False
    data[key]["status"] = "active"
    data[key]["activated_at"] = datetime.now(timezone.utc).isoformat()
    _save(data)

    # Store the key in keyvault
    if api_key_value:
        try:
            from bridge.keyvault import load_keys, store_keys
            keys = load_keys()
            keys[data[key]["key_env"]] = api_key_value
            store_keys(keys)
        except Exception:
            pass

    return True


def deactivate(key: str) -> bool:
    """Disable an API without removing it."""
    data = _load()
    if key not in data:
        return False
    data[key]["status"] = "disabled"
    _save(data)
    return True


def remove(key: str) -> bool:
    """Remove a non-builtin API from the registry."""
    data = _load()
    if key not in data or data[key].get("builtin"):
        return False
    del data[key]
    _save(data)
    return True


def update_feature_map(key: str, feature_map: dict):
    """Update which VO features an API enhances."""
    data = _load()
    if key not in data:
        return False
    data[key]["feature_map"] = feature_map
    _save(data)
    return True


def stats() -> dict:
    """Registry statistics."""
    data = _load()
    return {
        "total": len(data),
        "active": len([v for v in data.values() if v["status"] == "active"]),
        "pending": len([v for v in data.values() if v["status"] == "pending_key"]),
        "builtin": len([v for v in data.values() if v.get("builtin")]),
        "user_added": len([v for v in data.values() if not v.get("builtin")]),
    }
