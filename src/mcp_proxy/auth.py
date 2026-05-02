from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque


class APIKeyAuth:
    """Simple bearer token authentication."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def validate(self, auth_header: str | None) -> bool:
        """Validate an Authorization header value.

        Returns True if valid (or no key configured), False otherwise.
        Uses constant-time comparison to avoid timing leaks.
        """
        if self._api_key is None:
            return True
        if not auth_header:
            return False
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            return False
        return hmac.compare_digest(parts[1], self._api_key)


class RateLimiter:
    """Sliding window rate limiter per client IP.

    Uses ``deque`` for O(1) eviction. Idle IPs are pruned periodically
    so the per-IP map cannot grow without bound.
    """

    _GC_INTERVAL = 60.0

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._last_gc = time.monotonic()

    def allow(self, client_ip: str) -> bool:
        """Check if a request from client_ip is allowed."""
        now = time.monotonic()
        with self._lock:
            cutoff = now - self._window
            timestamps = self._requests[client_ip]
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            if len(timestamps) >= self._max:
                self._maybe_gc(now, cutoff)
                return False
            timestamps.append(now)
            self._maybe_gc(now, cutoff)
            return True

    def _maybe_gc(self, now: float, cutoff: float) -> None:
        if now - self._last_gc < self._GC_INTERVAL:
            return
        self._last_gc = now
        for ip in list(self._requests):
            q = self._requests[ip]
            while q and q[0] < cutoff:
                q.popleft()
            if not q:
                del self._requests[ip]
