"""
Your Company Virtual Office - Resilience Layer

Three defensive systems that sit between the Bridge and the AI providers:

1. RETRY WITH BACKOFF
   - 3 attempts per provider, 1s → 2s → 4s exponential delay
   - On exhaustion, cascade to next provider automatically

2. CIRCUIT BREAKER
   - After 3 consecutive failures from one provider, open the circuit
   - Provider paused for 60 seconds, all calls route to fallback
   - Auto-resets after cooldown

3. RATE LIMITER (Token Bucket)
   - 20 calls per minute, 200 per hour
   - Returns (allowed, wait_seconds) - caller can show "try again in N seconds"
   - Prevents runaway API spend from stuck loops or rapid-fire input

None of this changes the Owner's UI. It hardens the engine underneath.
"""

import time
import threading
from collections import defaultdict


# ═══ RATE LIMITER (Token Bucket) ════════════════════════════════════

class RateLimiter:
    """Token-bucket rate limiter. Thread-safe."""

    def __init__(self, per_minute: int = 20, per_hour: int = 200):
        self._lock = threading.Lock()
        self._minute_max = per_minute
        self._hour_max = per_hour
        self._minute_tokens = per_minute
        self._hour_tokens = per_hour
        self._last_minute_refill = time.monotonic()
        self._last_hour_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        # Refill minute bucket
        elapsed_min = now - self._last_minute_refill
        if elapsed_min >= 60:
            self._minute_tokens = self._minute_max
            self._last_minute_refill = now
        else:
            refill = int(elapsed_min * (self._minute_max / 60))
            if refill > 0:
                self._minute_tokens = min(self._minute_max, self._minute_tokens + refill)
                self._last_minute_refill = now

        # Refill hour bucket
        elapsed_hr = now - self._last_hour_refill
        if elapsed_hr >= 3600:
            self._hour_tokens = self._hour_max
            self._last_hour_refill = now
        else:
            refill = int(elapsed_hr * (self._hour_max / 3600))
            if refill > 0:
                self._hour_tokens = min(self._hour_max, self._hour_tokens + refill)
                self._last_hour_refill = now

    def allow(self) -> tuple:
        """Check if a call is allowed. Returns (allowed: bool, wait_seconds: float)."""
        with self._lock:
            self._refill()
            if self._minute_tokens <= 0:
                wait = 60 - (time.monotonic() - self._last_minute_refill)
                return False, max(1, int(wait))
            if self._hour_tokens <= 0:
                wait = 3600 - (time.monotonic() - self._last_hour_refill)
                return False, max(1, int(wait))
            self._minute_tokens -= 1
            self._hour_tokens -= 1
            return True, 0

    def status(self) -> dict:
        with self._lock:
            self._refill()
            return {
                "minute_remaining": self._minute_tokens,
                "minute_max": self._minute_max,
                "hour_remaining": self._hour_tokens,
                "hour_max": self._hour_max,
            }


# ═══ CIRCUIT BREAKER ════════════════════════════════════════════════

class CircuitBreaker:
    """Per-provider circuit breaker. Thread-safe.

    States:
      CLOSED  - normal operation, calls pass through
      OPEN    - provider is failing, all calls rejected (route to fallback)
      HALF    - cooldown expired, next call is a test
    """

    COOLDOWN = 60  # seconds

    def __init__(self, failure_threshold: int = 3):
        self._lock = threading.Lock()
        self._threshold = failure_threshold
        self._failures = defaultdict(int)      # provider → consecutive failure count
        self._open_since = {}                   # provider → timestamp when circuit opened
        self._state = defaultdict(lambda: "CLOSED")

    def is_available(self, provider: str) -> bool:
        """Check if a provider is available for calls."""
        with self._lock:
            state = self._state[provider]
            if state == "CLOSED":
                return True
            if state == "OPEN":
                if time.monotonic() - self._open_since.get(provider, 0) >= self.COOLDOWN:
                    self._state[provider] = "HALF"
                    return True  # allow one test call
                return False
            if state == "HALF":
                return True
            return True

    def record_success(self, provider: str):
        """Record a successful call - resets the circuit."""
        with self._lock:
            self._failures[provider] = 0
            self._state[provider] = "CLOSED"

    def record_failure(self, provider: str):
        """Record a failed call - may open the circuit."""
        with self._lock:
            self._failures[provider] += 1
            if self._failures[provider] >= self._threshold:
                self._state[provider] = "OPEN"
                self._open_since[provider] = time.monotonic()

    def get_fallback_order(self, primary: str) -> list:
        """Return available providers in fallback order."""
        all_providers = ["claude", "gemini", "openai"]
        available = [p for p in all_providers if p != primary and self.is_available(p)]
        if self.is_available(primary):
            return [primary] + available
        return available

    def status(self) -> dict:
        with self._lock:
            return {
                p: {
                    "state": self._state[p],
                    "failures": self._failures[p],
                }
                for p in ["claude", "gemini", "openai"]
            }


# ═══ RETRY WITH BACKOFF ═════════════════════════════════════════════

def retry_with_backoff(fn, args=(), kwargs=None, max_attempts=3, base_delay=1.0):
    """Execute fn with exponential backoff retry.

    Returns (success: bool, result, attempts: int, errors: list)
    """
    kwargs = kwargs or {}
    errors = []

    for attempt in range(max_attempts):
        try:
            result = fn(*args, **kwargs)
            return True, result, attempt + 1, errors
        except Exception as e:
            errors.append(f"Attempt {attempt + 1}: {type(e).__name__}: {str(e)[:200]}")
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                time.sleep(delay)

    return False, None, max_attempts, errors


# ═══ GLOBAL INSTANCES ═══════════════════════════════════════════════

rate_limiter = RateLimiter(per_minute=20, per_hour=200)
circuit_breaker = CircuitBreaker(failure_threshold=3)
