"""Gemini SDK compatibility shim.

google-genai (new SDK) uses `from google import genai`.
google-generativeai (legacy SDK) uses `import google.generativeai as genai`.

This shim tries new SDK first, falls back to legacy, provides a
consistent interface regardless of which is installed.

v3.2.7 pass 10f (Owner roadmap #3): SDK probe is LAZY. No warning
prints at import-time. The warning fires only on the first call to
get_genai() or get_sdk_version() when no SDK is found.
"""

import logging
log = logging.getLogger("gemini_compat")

# Lazy-init sentinel: None = not yet probed, otherwise the probe result.
genai = None
_sdk_version = None
_probed = False


def _probe_sdk():
    """Probe for Gemini SDK once. Cached. Silent if SDK present."""
    global genai, _sdk_version, _probed
    if _probed:
        return
    _probed = True
    try:
        from google import genai as _genai
        genai = _genai
        _sdk_version = "google-genai"
        log.debug("Using google-genai (new SDK)")
        return
    except ImportError:
        pass
    try:
        import google.generativeai as _genai
        genai = _genai
        _sdk_version = "google-generativeai"
        log.debug("Using google-generativeai (legacy SDK)")
        return
    except ImportError:
        pass
    # Only warn now, on first probe attempt where neither SDK exists.
    # Subsequent calls are silent because _probed is True.
    # Owner roadmap #3: demote to debug. No-SDK is a degraded-mode
    # state for an optional feature, not a warning. Real ImportError still
    # raises in make_client() when caller actually attempts Gemini use.
    log.debug("No Gemini SDK installed. Install: pip install google-genai")
    _sdk_version = None


def get_genai():
    """Return the genai module, whichever SDK is installed."""
    _probe_sdk()
    return genai


def get_sdk_version():
    """Return which SDK is active: 'google-genai', 'google-generativeai', or None."""
    _probe_sdk()
    return _sdk_version


def get_types():
    """Return the types module from whichever SDK is installed."""
    if _sdk_version == "google-genai":
        from google.genai import types
        return types
    elif _sdk_version == "google-generativeai":
        # Legacy SDK has types at a different path
        try:
            import google.generativeai.types as types
            return types
        except ImportError:
            return None
    return None


def make_client(api_key: str):
    """Create a Gemini client compatible with whichever SDK is installed.
    New SDK: genai.Client(api_key=...)
    Legacy SDK: genai.configure(api_key=...) then return genai itself.
    """
    if not genai:
        raise ImportError("No Gemini SDK installed. Run: pip install google-genai")
    if _sdk_version == "google-genai":
        return genai.Client(api_key=api_key)
    else:
        # Legacy SDK uses configure() then the module IS the client
        genai.configure(api_key=api_key)
        return genai


def is_available():
    """Check if any Gemini SDK is installed."""
    return genai is not None
