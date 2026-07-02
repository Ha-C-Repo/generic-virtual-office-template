"""
bridge/claude_connect.py - Claude API Connection Layer v3.1
============================================================
Drop-in replacement for _call_claude and _test_claude_available in api.py.
Adds Strategy 4 (curl.exe/WinHTTP) and Strategy 5 (verify=False/TLS bypass).

WHY EACH STRATEGY EXISTS
────────────────────────
Strategy 0  truststore        - loads Windows ROOT cert store into httpx.
                                Fixes Zscaler/BitDefender/Netskope proxy MITM.
Strategy 1  ssl_default_certs - same as 0 but without truststore package.
                                Backup if truststore failed to install.
Strategy 2  default SDK       - certifi bundle. Works on clean networks,
                                fails on any TLS-intercepting proxy.
Strategy 3  urllib            - Python's built-in HTTP. Bypasses httpx
                                entirely. Uses Windows TLS stack.
Strategy 4  curl.exe          - Windows curl.exe uses WinHTTP (native).
                                Not blocked by AV. Completely bypasses
                                Python's SSL stack. DEFINITIVE TEST.
Strategy 5  verify=False      - Disables ALL cert verification.
                                Last resort. Works if proxy presents
                                self-signed cert. Logs a warning.

If ALL 6 fail → the issue is NOT SSL/Python. It's one of:
  - API key is invalid/expired (check HTTP 401 in the error)
  - api.anthropic.com is blocked by firewall/DNS policy
  - Windows Firewall blocked python.exe outbound
"""


import json as _json
import ssl as _ssl
import sys

# Global state (mirrors api.py)
_CLAUDE_AVAILABLE: bool | None = None


def _capture_exact_error(e: Exception) -> str:
    """Return a short but complete error description for diagnostic output."""
    msg = f"{type(e).__name__}: {e}"
    # For SSL errors, include the reason which is the most useful part
    if hasattr(e, "reason"):
        msg += f" | reason={e.reason}"
    if hasattr(e, "strerror"):
        msg += f" | strerror={e.strerror}"
    return msg[:400]


def call_claude_robust(api_key: str, model: str, system: str, messages: list) -> dict:
    """
    Call Anthropic Claude API with 6-strategy fallback cascade.

    Returns dict: {text, stop_reason, input_tokens, output_tokens, _transport}
    Raises ValueError for auth errors, ConnectionError when all strategies fail.
    """
    import anthropic

    # ── Key validation ────────────────────────────────────────────────────
    if not api_key or len(api_key) < 20:
        raise ValueError(
            f"Claude API key is empty or too short ({len(api_key)} chars).\n"
            "Open: API Keys\\Claude API.txt - paste ONLY the key on line 1, no quotes, no spaces."
        )
    if not api_key.startswith("sk-ant-"):
        raise ValueError(
            f"Claude API key has wrong prefix (got '{api_key[:8]}...').\n"
            "Anthropic keys start with 'sk-ant-'. Check API Keys\\Claude API.txt for extra characters."
        )

    errors: dict[str, str] = {}

    # ── Strategy 0: truststore (Windows OS cert store via httpx) ─────────
    try:
        import truststore
        from anthropic import DefaultHttpxClient
        ssl_ctx = truststore.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        hc = DefaultHttpxClient(verify=ssl_ctx, http2=False, timeout=60.0)
        client = anthropic.Anthropic(api_key=api_key, http_client=hc)
        resp = client.messages.create(
            model=model, max_tokens=1500, system=system, messages=messages
        )
        return _pack(resp, "truststore_windows_ca")
    except anthropic.AuthenticationError:
        raise ValueError(
            "Claude API key is INVALID (Anthropic rejected it - HTTP 401).\n"
            "Go to: console.anthropic.com/settings/keys\n"
            "Create a new key and save it to: API Keys\\Claude API.txt"
        )
    except anthropic.RateLimitError:
        raise ValueError("Claude rate limit. Wait 60 seconds and retry.")
    except Exception as e:
        errors["s0_truststore"] = _capture_exact_error(e)

    # ── Strategy 1: ssl.load_default_certs (no truststore package needed) ─
    try:
        from anthropic import DefaultHttpxClient
        ctx = _ssl.create_default_context()
        ctx.load_default_certs(_ssl.Purpose.SERVER_AUTH)
        hc = DefaultHttpxClient(verify=ctx, http2=False, timeout=60.0)
        client = anthropic.Anthropic(api_key=api_key, http_client=hc)
        resp = client.messages.create(
            model=model, max_tokens=1500, system=system, messages=messages
        )
        return _pack(resp, "ssl_default_certs")
    except anthropic.AuthenticationError:
        raise ValueError("Claude API key is INVALID.\nCreate a new key at: console.anthropic.com/settings/keys")
    except anthropic.RateLimitError:
        raise ValueError("Claude rate limit. Wait 60 seconds.")
    except Exception as e:
        errors["s1_ssl_default"] = _capture_exact_error(e)

    # ── Strategy 2: Default SDK (certifi bundle - clean networks only) ────
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=1500, system=system, messages=messages
        )
        return _pack(resp, "default_sdk_certifi")
    except anthropic.AuthenticationError:
        raise ValueError("Claude API key is INVALID.\nCreate a new key at: console.anthropic.com/settings/keys")
    except anthropic.RateLimitError:
        raise ValueError("Claude rate limit. Wait 60 seconds.")
    except Exception as e:
        errors["s2_default_sdk"] = _capture_exact_error(e)

    # ── Strategy 3: Raw urllib (bypasses httpx, uses OS TLS) ─────────────
    try:
        import urllib.request
        payload = _json.dumps({
            "model": model,
            "max_tokens": 1500,
            "system": system,
            "messages": [
                {"role": m["role"],
                 "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                for m in messages
            ]
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "User-Agent": "YourCo-VirtualOffice/3.1",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            body = _json.loads(r.read().decode("utf-8"))
        return _unpack_body(body, "urllib_builtin")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 401:
            raise ValueError(
                f"Claude API key is INVALID (HTTP 401).\n"
                f"Create a new key at: console.anthropic.com/settings/keys\n"
                f"Server said: {body_text}"
            )
        errors["s3_urllib"] = f"HTTPError {e.code}: {body_text}"
    except Exception as e:
        errors["s3_urllib"] = _capture_exact_error(e)

    # ── Strategy 4: curl.exe subprocess (WinHTTP - Windows native HTTP) ──
    # curl.exe ships with Windows 10/11. Uses WinHTTP - not Python SSL.
    # NOT blocked by most AV software (it's a Windows system binary).
    if sys.platform == "win32":
        try:
            import subprocess, shutil
            curl_path = (
                shutil.which("curl.exe")
                or r"C:\Windows\System32\curl.exe"
                or "curl.exe"
            )
            payload_str = _json.dumps({
                "model": model,
                "max_tokens": 1500,
                "system": system,
                "messages": [
                    {"role": m["role"],
                     "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
                    for m in messages
                ]
            })
            result = subprocess.run(
                [
                    curl_path, "-s",
                    "-X", "POST",
                    "https://api.anthropic.com/v1/messages",
                    "-H", f"x-api-key: {api_key}",
                    "-H", "anthropic-version: 2023-06-01",
                    "-H", "content-type: application/json",
                    "--data-binary", "@-",
                    "--max-time", "60",
                ],
                input=payload_str.encode("utf-8"),
                capture_output=True,
                timeout=65,
            )
            if result.returncode != 0:
                raise ConnectionError(
                    f"curl.exe exited {result.returncode}: {result.stderr.decode()[:200]}"
                )
            body = _json.loads(result.stdout.decode("utf-8"))
            if "error" in body:
                err_type = body["error"].get("type", "")
                err_msg  = body["error"].get("message", str(body["error"]))
                if err_type == "authentication_error":
                    raise ValueError(
                        f"Claude API key is INVALID (curl confirmed HTTP 401).\n"
                        f"Create a new key at: console.anthropic.com/settings/keys\n"
                        f"Details: {err_msg}"
                    )
                raise ConnectionError(f"Claude API error via curl: {err_msg}")
            return _unpack_body(body, "curl_exe_winhttp")
        except (ValueError, ConnectionError):
            raise
        except Exception as e:
            errors["s4_curl_exe"] = _capture_exact_error(e)

    # ── Strategy 5: httpx verify=False (TLS bypass - AV/proxy last resort) ─
    # If this works → your network has a TLS-intercepting proxy.
    # The real fix is: export the proxy CA cert and set SSL_CERT_FILE.
    try:
        from anthropic import DefaultHttpxClient
        hc = DefaultHttpxClient(verify=False, http2=False, timeout=60.0)
        client = anthropic.Anthropic(api_key=api_key, http_client=hc)
        resp = client.messages.create(
            model=model, max_tokens=1500, system=system, messages=messages
        )
        # If we get here, a TLS-intercepting proxy is confirmed.
        # Log a warning but return the result.
        result = _pack(resp, "no_ssl_verify_PROXY_DETECTED")
        result["_warning"] = (
            "⚠ TLS verification disabled. A corporate proxy is intercepting HTTPS.\n"
            "To fix: export your proxy CA cert and set SSL_CERT_FILE=<path_to_ca.pem>\n"
            "or add the cert to Windows trusted root store."
        )
        return result
    except anthropic.AuthenticationError:
        raise ValueError("Claude API key is INVALID.\nCreate a new key at: console.anthropic.com/settings/keys")
    except anthropic.RateLimitError:
        raise ValueError("Claude rate limit. Wait 60 seconds.")
    except Exception as e:
        errors["s5_no_ssl_verify"] = _capture_exact_error(e)

    # ── ALL 6 STRATEGIES FAILED ───────────────────────────────────────────
    err_lines = "\n".join(f"  [{k}] {v}" for k, v in errors.items())
    raise ConnectionError(
        f"Cannot reach Anthropic API. All connection strategies failed.\n\n"
        f"{err_lines}\n\n"
        f"DIAGNOSIS GUIDE:\n"
        f"  • If errors mention '401' or 'authentication_error':\n"
        f"    → Your API key is invalid. Get a new one:\n"
        f"      console.anthropic.com/settings/keys\n\n"
        f"  • If errors mention 'Connection refused' or 'Network unreachable':\n"
        f"    → api.anthropic.com is blocked. Check:\n"
        f"      1. Windows Firewall - is python.exe allowed outbound?\n"
        f"      2. Antivirus - is Python blocked from internet?\n"
        f"      3. IT policy - is api.anthropic.com in a blocklist?\n"
        f"      Run: DIAGNOSE_CLAUDE.bat for a full network test.\n\n"
        f"  • If only Strategy 4 (curl.exe) worked:\n"
        f"    → Python SSL stack is broken. Reinstall Python from python.org.\n\n"
        f"  • If Strategy 5 (verify=False) worked:\n"
        f"    → Corporate proxy intercepting TLS. Ask IT for the proxy CA cert.\n"
    )


def test_claude_available(api_key: str) -> bool:
    """
    Quick availability check. Sets module-level _CLAUDE_AVAILABLE.
    Returns True/False. Captures the EXACT error for each strategy.
    """
    global _CLAUDE_AVAILABLE

    if not api_key or len(api_key) < 20:
        _CLAUDE_AVAILABLE = False
        return False

    # We try all strategies with tiny payloads for speed.
    # _test_strategies returns (success: bool, transport: str, errors: dict)
    ok, transport, diag = _try_all_strategies(api_key, quick=True)
    _CLAUDE_AVAILABLE = ok
    return ok


def _try_all_strategies(api_key: str, quick: bool = False) -> tuple[bool, str, dict]:
    """
    Try all connection strategies. Returns (success, transport_name, errors_dict).
    Used by both call_claude_robust and test_claude_available.
    quick=True uses max_tokens=5 for speed.
    """
    import anthropic

    max_tok = 5 if quick else 10
    errors = {}
    ping_msgs = [{"role": "user", "content": "ping"}]

    def _test_sdk(client):
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tok,
            messages=ping_msgs
        )
        return r.stop_reason in ("end_turn", "max_tokens")

    # S0: truststore
    try:
        import truststore
        from anthropic import DefaultHttpxClient
        ctx = truststore.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        ok = _test_sdk(anthropic.Anthropic(api_key=api_key,
                       http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=20)))
        if ok:
            return True, "truststore_windows_ca", errors
    except anthropic.AuthenticationError:
        errors["s0"] = "AUTH_ERROR: key is invalid"
        return False, "", errors
    except Exception as e:
        errors["s0_truststore"] = _capture_exact_error(e)

    # S1: ssl.load_default_certs
    try:
        from anthropic import DefaultHttpxClient
        ctx = _ssl.create_default_context()
        ctx.load_default_certs(_ssl.Purpose.SERVER_AUTH)
        ok = _test_sdk(anthropic.Anthropic(api_key=api_key,
                       http_client=DefaultHttpxClient(verify=ctx, http2=False, timeout=20)))
        if ok:
            return True, "ssl_default_certs", errors
    except anthropic.AuthenticationError:
        errors["s1"] = "AUTH_ERROR: key is invalid"
        return False, "", errors
    except Exception as e:
        errors["s1_ssl_default"] = _capture_exact_error(e)

    # S2: default SDK
    try:
        ok = _test_sdk(anthropic.Anthropic(api_key=api_key))
        if ok:
            return True, "default_sdk_certifi", errors
    except anthropic.AuthenticationError:
        errors["s2"] = "AUTH_ERROR: key is invalid"
        return False, "", errors
    except Exception as e:
        errors["s2_default_sdk"] = _capture_exact_error(e)

    # S3: urllib
    try:
        import urllib.request
        payload = _json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tok,
            "messages": ping_msgs
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json",
                     "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            _json.loads(r.read())
        return True, "urllib_builtin", errors
    except urllib.error.HTTPError as e:
        if e.code == 401:
            errors["s3"] = "AUTH_ERROR: key is invalid (HTTP 401)"
            return False, "", errors
        errors["s3_urllib"] = f"HTTPError {e.code}"
    except Exception as e:
        errors["s3_urllib"] = _capture_exact_error(e)

    # S4: curl.exe (Windows only)
    if sys.platform == "win32":
        try:
            import subprocess, shutil
            curl = shutil.which("curl.exe") or r"C:\Windows\System32\curl.exe"
            payload_str = _json.dumps({
                "model": "claude-sonnet-4-6",
                "max_tokens": max_tok,
                "messages": ping_msgs
            })
            res = subprocess.run(
                [curl, "-s", "-X", "POST",
                 "https://api.anthropic.com/v1/messages",
                 "-H", f"x-api-key: {api_key}",
                 "-H", "anthropic-version: 2023-06-01",
                 "-H", "content-type: application/json",
                 "--data-binary", "@-",
                 "--max-time", "20"],
                input=payload_str.encode("utf-8"),
                capture_output=True, timeout=25
            )
            if res.returncode == 0:
                body = _json.loads(res.stdout)
                if "error" in body and body["error"].get("type") == "authentication_error":
                    errors["s4"] = "AUTH_ERROR: key is invalid (curl confirmed)"
                    return False, "", errors
                if "content" in body:
                    return True, "curl_exe_winhttp", errors
            errors["s4_curl"] = f"curl exit={res.returncode}: {res.stderr.decode()[:100]}"
        except Exception as e:
            errors["s4_curl_exe"] = _capture_exact_error(e)

    # S5: verify=False
    try:
        from anthropic import DefaultHttpxClient
        ok = _test_sdk(anthropic.Anthropic(api_key=api_key,
                       http_client=DefaultHttpxClient(verify=False, http2=False, timeout=20)))
        if ok:
            return True, "no_ssl_verify_PROXY_DETECTED", errors
    except anthropic.AuthenticationError:
        errors["s5"] = "AUTH_ERROR: key is invalid"
        return False, "", errors
    except Exception as e:
        errors["s5_no_ssl"] = _capture_exact_error(e)

    return False, "", errors


# ── Helpers ──────────────────────────────────────────────────────────────────
def _pack(resp, transport: str) -> dict:
    """Pack an Anthropic SDK response object into a plain dict."""
    text = resp.content[0].text if resp.content else ""
    return {
        "text": text,
        "stop_reason": resp.stop_reason,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "_transport": transport,
    }


def _unpack_body(body: dict, transport: str) -> dict:
    """Unpack a raw API response dict (from urllib / curl)."""
    text = ""
    for block in body.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
    return {
        "text": text,
        "stop_reason": body.get("stop_reason", ""),
        "input_tokens": body.get("usage", {}).get("input_tokens", 0),
        "output_tokens": body.get("usage", {}).get("output_tokens", 0),
        "_transport": transport,
    }


# ═════════════════════════════════════════════════════════════════
# Pass 8: call_claude_with_mcps - Anthropic Messages API with remote
# URL-based MCP servers attached. Lets Claude (via API) reach the Owner's
# Microsoft 365 / Slack / etc connectors the same way they're reachable
# from the Claude Desktop App.
# ═════════════════════════════════════════════════════════════════

def call_claude_with_mcps(api_key: str, model: str, system: str, messages: list,
                          mcp_servers: list = None, max_tokens: int = 1500) -> dict:
    """Call Claude API with optional remote MCP servers attached.

    BUG-006 FIX: now uses the same truststore TLS strategy as call_claude_robust.
    Previously used a bare anthropic.Anthropic() with no TLS override, meaning MCP
    calls failed on corporate TLS-intercepting proxies where regular chat worked fine.

    Args:
        api_key:     Anthropic API key (sk-ant-...)
        model:       model_id string (e.g. "claude-sonnet-4-6")
        system:      system prompt
        messages:    [{role, content}] list
        mcp_servers: list of {type:"url", url:..., name:...} dicts.
                     Empty list or None = plain API call (no MCPs).
        max_tokens:  generation cap

    Returns dict: {text, stop_reason, input_tokens, output_tokens,
                   _transport, mcp_tool_uses[], mcp_tool_results[]}
    """
    import anthropic

    if not api_key or len(api_key) < 20:
        raise ValueError(f"Claude API key empty or too short ({len(api_key)} chars).")
    if not api_key.startswith("sk-ant-"):
        raise ValueError(f"Claude API key wrong prefix ('{api_key[:8]}...').")

    extra_kwargs = {}
    if mcp_servers:
        extra_kwargs["mcp_servers"] = mcp_servers
        # The Anthropic SDK requires the beta header for MCP support.
        extra_kwargs["extra_headers"] = {"anthropic-beta": "mcp-client-2025-04-04"}

    # BUG-006 FIX: build the client with the truststore TLS strategy so MCP
    # calls succeed on Windows networks with TLS-intercepting proxies (Zscaler,
    # BitDefender, Netskope). Falls back to plain client if truststore missing.
    def _build_client() -> anthropic.Anthropic:
        try:
            import truststore
            from anthropic import DefaultHttpxClient
            ssl_ctx = truststore.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            hc = DefaultHttpxClient(verify=ssl_ctx, http2=False, timeout=120.0)
            return anthropic.Anthropic(api_key=api_key, http_client=hc)
        except Exception:
            pass
        try:
            from anthropic import DefaultHttpxClient
            ctx = _ssl.create_default_context()
            ctx.load_default_certs(_ssl.Purpose.SERVER_AUTH)
            hc = DefaultHttpxClient(verify=ctx, http2=False, timeout=120.0)
            return anthropic.Anthropic(api_key=api_key, http_client=hc)
        except Exception:
            pass
        # Final fallback: default certifi bundle (works on clean networks)
        return anthropic.Anthropic(api_key=api_key)

    try:
        client = _build_client()
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system, messages=messages,
            **extra_kwargs,
        )
    except TypeError as e:
        # SDK version doesn't accept mcp_servers kwarg - fall back to urllib
        if "mcp_servers" in str(e) or "unexpected keyword" in str(e):
            return _call_claude_with_mcps_urllib(
                api_key, model, system, messages, mcp_servers, max_tokens
            )
        raise

    # Extract text + any MCP tool activity
    text_parts = []
    mcp_uses = []
    mcp_results = []
    for block in (resp.content or []):
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(getattr(block, "text", "") or "")
        elif btype == "mcp_tool_use":
            mcp_uses.append({
                "name":   getattr(block, "name", ""),
                "server": getattr(block, "server_name", ""),
                "input":  getattr(block, "input", {}),
            })
        elif btype == "mcp_tool_result":
            content = getattr(block, "content", [])
            text_content = []
            for c in (content or []):
                if isinstance(c, dict) and c.get("type") == "text":
                    text_content.append(c.get("text", ""))
                else:
                    t = getattr(c, "text", None) if c else None
                    if t:
                        text_content.append(t)
            mcp_results.append({
                "tool_use_id": getattr(block, "tool_use_id", ""),
                "is_error":    getattr(block, "is_error", False),
                "text":        "\n".join(text_content),
            })

    return {
        "text":             "\n".join(text_parts),
        "stop_reason":      resp.stop_reason,
        "input_tokens":     resp.usage.input_tokens,
        "output_tokens":    resp.usage.output_tokens,
        "_transport":       "mcp_sdk",
        "mcp_tool_uses":    mcp_uses,
        "mcp_tool_results": mcp_results,
        "mcp_servers_used": [s.get("name", "") for s in (mcp_servers or [])],
    }


def _call_claude_with_mcps_urllib(api_key, model, system, messages, mcp_servers, max_tokens):
    """Urllib fallback when SDK is too old to accept mcp_servers kwarg."""
    import urllib.request, json as _json
    payload = {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": m["role"], "content": str(m["content"])} for m in messages],
    }
    if mcp_servers:
        payload["mcp_servers"] = mcp_servers
    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }
    if mcp_servers:
        headers["anthropic-beta"] = "mcp-client-2025-04-04"
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=_json.dumps(payload).encode(),
        headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = _json.loads(resp.read().decode())

    text_parts = []
    mcp_uses = []
    mcp_results = []
    for block in body.get("content", []):
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "mcp_tool_use":
            mcp_uses.append({
                "name":   block.get("name", ""),
                "server": block.get("server_name", ""),
                "input":  block.get("input", {}),
            })
        elif btype == "mcp_tool_result":
            content = block.get("content", [])
            text_content = [c.get("text", "") for c in content if c.get("type") == "text"]
            mcp_results.append({
                "tool_use_id": block.get("tool_use_id", ""),
                "is_error":    block.get("is_error", False),
                "text":        "\n".join(text_content),
            })

    return {
        "text":             "\n".join(text_parts),
        "stop_reason":      body.get("stop_reason", ""),
        "input_tokens":     body.get("usage", {}).get("input_tokens", 0),
        "output_tokens":    body.get("usage", {}).get("output_tokens", 0),
        "_transport":       "mcp_urllib",
        "mcp_tool_uses":    mcp_uses,
        "mcp_tool_results": mcp_results,
        "mcp_servers_used": [s.get("name", "") for s in (mcp_servers or [])],
    }
