from __future__ import annotations

import threading
import time
from collections import defaultdict


class APIKeyAuth:
    """Simple bearer token authentication."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def validate(self, auth_header: str | None) -> bool:
        """Validate an Authorization header value.

        Returns True if valid (or no key configured), False otherwise.
        """
        if self._api_key is None:
            return True
        if not auth_header:
            return False
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != "Bearer":
            return False
        return parts[1] == self._api_key


class RateLimiter:
    """Sliding window rate limiter per client IP."""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, list[float]] = defaultdict(list)

    def allow(self, client_ip: str) -> bool:
        """Check if a request from client_ip is allowed."""
        now = time.monotonic()
        with self._lock:
            timestamps = self._requests[client_ip]
            cutoff = now - self._window
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) >= self._max:
                return False
            timestamps.append(now)
            return True
