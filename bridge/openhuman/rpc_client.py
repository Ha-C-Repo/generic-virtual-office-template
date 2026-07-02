"""OpenHuman JSON-RPC client (Phase 29, v6.1.0).

Communicates with the OpenHuman sidecar at localhost:7788 via JSON-RPC.
Graceful fallback when OpenHuman is not running. The virtual office is
the "structural steel engine." OpenHuman is the "office manager brain."

Voice rules: zero em-dashes. Hyphens or periods only.
"""


import logging
from typing import Any, Optional

log = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:7788/rpc"

try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class OpenHumanClient:
    """JSON-RPC 2.0 client for the OpenHuman sidecar."""

    def __init__(self, base_url: str = BASE_URL, timeout: int = 5):
        self.base_url = base_url
        self.timeout = timeout
        self._id_counter = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        """Make a JSON-RPC call to OpenHuman.

        Returns the result dict, or {"error": ...} on failure.
        """
        if not HAS_REQUESTS:
            return {"error": "requests library not installed"}

        self._id_counter += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": self._id_counter,
        }

        try:
            resp = _requests.post(
                self.base_url,
                json=payload,
                timeout=self.timeout,
            )
            data = resp.json()
            if "error" in data:
                return {"error": data["error"]}
            return data.get("result", {})
        except Exception as e:
            return {"error": str(e)}

    def is_available(self) -> bool:
        """Check if OpenHuman is running at localhost:7788."""
        result = self.call("health")
        return "error" not in result

    def get_status(self) -> dict:
        """Get OpenHuman status including connected services."""
        if not self.is_available():
            return {
                "available": False,
                "status": "not_running",
                "note": "OpenHuman sidecar is not detected at "
                        f"{self.base_url}. Install from "
                        "tinyhumans.ai/openhuman.",
            }
        status = self.call("status")
        status["available"] = True
        return status
