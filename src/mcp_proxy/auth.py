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


class AuthMiddleware:
    """ASGI middleware enforcing bearer-token auth on HTTP requests."""

    def __init__(self, app, auth: APIKeyAuth) -> None:
        self.app = app
        self._auth = auth

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header_value: str | None = None
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                header_value = value.decode("latin-1")
                break
        if not self._auth.validate(header_value):
            await _send_text(send, 401, "Unauthorized")
            return
        await self.app(scope, receive, send)


class RateLimitMiddleware:
    """ASGI middleware enforcing per-IP rate limits."""

    def __init__(self, app, limiter: RateLimiter) -> None:
        self.app = app
        self._limiter = limiter

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        if not self._limiter.allow(client_ip):
            await _send_text(send, 429, "Too Many Requests")
            return
        await self.app(scope, receive, send)


async def _send_text(send, status: int, body: str) -> None:
    payload = body.encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"content-length", str(len(payload)).encode("ascii")),
        ],
    })
    await send({"type": "http.response.body", "body": payload})
