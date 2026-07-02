"""Ollama service wrapper.

Wraps the Ollama HTTP API (default http://localhost:11434) to give the
takeoff pipeline a deterministic, sandbox-safe vision endpoint. The
wrapper degrades cleanly when Ollama is not installed or not running,
which lets the rest of the system fall through to Tier 2 (Gemini) or
Tier 3 (GPT-4o) without raising.

Why HTTP and not the `ollama` Python package: zero pip dependency.
The HTTP API is stable and built into every Ollama install. We use
the standard library (urllib) so the wrapper still works in stripped-
down environments and can be unit-tested with simple mocks.

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import base64
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 120  # seconds. Vision calls can be slow on first warmup.


# ── Public helpers ────────────────────────────────────────────────────────

def is_ollama_running(host: str = DEFAULT_HOST,
                     timeout: float = 2.0) -> bool:
    """Quick TCP probe. True if the Ollama daemon answers on its port."""
    try:
        # urllib parse without importing urllib.parse for the host
        # because we only need host + port. Strip protocol prefix.
        cleaned = host.replace("http://", "").replace("https://", "")
        if "/" in cleaned:
            cleaned = cleaned.split("/", 1)[0]
        if ":" in cleaned:
            host_part, port_part = cleaned.split(":", 1)
            port = int(port_part)
        else:
            host_part = cleaned
            port = 11434
        with socket.create_connection((host_part, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def list_installed_models(host: str = DEFAULT_HOST) -> list[str]:
    """Return Ollama model names installed locally. Empty list on failure."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", []) or []
        return [m.get("name", "") for m in models if m.get("name")]
    except (urllib.error.URLError, ValueError, OSError):
        return []


def pull_model_if_missing(model: str,
                          host: str = DEFAULT_HOST,
                          progress_callback=None) -> dict:
    """Pull a model via the Ollama daemon if not already installed.

    Args:
        model: e.g. "llama3.2-vision:11b"
        host: Ollama base URL.
        progress_callback: optional callable(line_dict) for stream updates.

    Returns:
        dict with keys success, message, already_present.
    """
    if not is_ollama_running(host):
        return {
            "success": False,
            "message": "Ollama daemon not running. Start Ollama first.",
            "already_present": False,
        }

    if model in list_installed_models(host):
        return {
            "success": True,
            "message": f"Model {model} already present.",
            "already_present": True,
        }

    body = json.dumps({"name": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/pull",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60 * 30) as resp:
            for raw in resp:
                if not raw:
                    continue
                try:
                    line = json.loads(raw.decode("utf-8").strip())
                except ValueError:
                    continue
                if progress_callback:
                    try:
                        progress_callback(line)
                    except Exception:
                        pass
                if line.get("error"):
                    return {
                        "success": False,
                        "message": str(line.get("error")),
                        "already_present": False,
                    }
                if line.get("status") == "success":
                    return {
                        "success": True,
                        "message": f"Pulled {model}.",
                        "already_present": False,
                    }
        # Stream ended without explicit success line. Re-check tags.
        if model in list_installed_models(host):
            return {
                "success": True,
                "message": f"Pulled {model} (verified via tags).",
                "already_present": False,
            }
        return {
            "success": False,
            "message": "Pull stream ended without success marker.",
            "already_present": False,
        }
    except (urllib.error.URLError, OSError) as e:
        return {
            "success": False,
            "message": f"Pull failed: {e}",
            "already_present": False,
        }


# ── Client class ──────────────────────────────────────────────────────────

class OllamaClient:
    """Vision-capable Ollama wrapper.

    Usage:
        c = OllamaClient(model="llama3.2-vision:11b")
        if c.is_available():
            resp = c.classify_page(image_bytes, prompt="...")
    """

    def __init__(self,
                 model: str = "llama3.2-vision:11b",
                 host: str = DEFAULT_HOST,
                 timeout: int = DEFAULT_TIMEOUT):
        self.model = model
        self.host = host
        self.timeout = timeout

    def is_available(self) -> bool:
        """True if the daemon is up AND the configured model is installed."""
        if not is_ollama_running(self.host):
            return False
        return self.model in list_installed_models(self.host)

    def health_check(self) -> dict:
        """Detailed availability report for the GUI."""
        running = is_ollama_running(self.host)
        installed = list_installed_models(self.host) if running else []
        present = self.model in installed
        return {
            "daemon_running": running,
            "model": self.model,
            "model_installed": present,
            "available_models": installed,
            "ready": running and present,
        }

    def generate(self,
                 prompt: str,
                 image_paths: Optional[list[str]] = None,
                 image_bytes: Optional[list[bytes]] = None,
                 system: Optional[str] = None) -> dict:
        """Run a single non-streaming generate call.

        Returns:
            {"success": bool, "text": str, "raw": dict | None, "error": str}
        """
        if not is_ollama_running(self.host):
            return {
                "success": False,
                "text": "",
                "raw": None,
                "error": "Ollama daemon not running",
            }

        images_b64: list[str] = []
        if image_paths:
            for p in image_paths:
                try:
                    raw = Path(p).read_bytes()
                    images_b64.append(base64.b64encode(raw).decode("ascii"))
                except OSError as e:
                    return {
                        "success": False, "text": "", "raw": None,
                        "error": f"Image read failed: {e}",
                    }
        if image_bytes:
            for raw in image_bytes:
                images_b64.append(base64.b64encode(raw).decode("ascii"))

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if images_b64:
            payload["images"] = images_b64
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "text": data.get("response", ""),
                "raw": data,
                "error": "",
            }
        except urllib.error.HTTPError as e:
            return {
                "success": False, "text": "", "raw": None,
                "error": f"HTTP {e.code}: {e.reason}",
            }
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {
                "success": False, "text": "", "raw": None,
                "error": str(e),
            }

    def classify_page(self,
                      image_bytes: bytes,
                      prompt: str = "Classify this drawing sheet. "
                                    "Return one of: plan, elevation, "
                                    "section, schedule, detail, cover, "
                                    "notes, other.") -> dict:
        """Tier 1 page-class triage helper. Returns class label + raw."""
        r = self.generate(prompt=prompt, image_bytes=[image_bytes])
        if not r["success"]:
            return {"success": False, "label": "", "error": r["error"]}
        text = (r["text"] or "").strip().lower()
        # Pick the first known label that appears in the response.
        for label in ("plan", "elevation", "section", "schedule",
                      "detail", "cover", "notes", "other"):
            if label in text:
                return {"success": True, "label": label, "raw_text": r["text"]}
        return {"success": True, "label": "other", "raw_text": r["text"]}
