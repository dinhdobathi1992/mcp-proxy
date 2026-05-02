from __future__ import annotations

import statistics
import threading
import time
from collections import defaultdict, deque
from typing import Any, Callable

try:
    from fastmcp.server.middleware import Middleware
except ImportError:  # pragma: no cover - fastmcp always present at runtime
    Middleware = object  # type: ignore[assignment,misc]

LATENCY_WINDOW = 1000


class Metrics:
    """Thread-safe in-memory metrics collector.

    Latency samples bounded per-backend to avoid unbounded memory growth.
    """

    def __init__(self, latency_window: int = LATENCY_WINDOW) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._per_backend: dict[str, int] = defaultdict(int)
        self._errors_per_backend: dict[str, int] = defaultdict(int)
        self._latency_window = latency_window
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=latency_window)
        )

    def record_request(self, backend_name: str, duration_ms: float, success: bool) -> None:
        with self._lock:
            self._requests_total += 1
            self._per_backend[backend_name] += 1
            self._latencies[backend_name].append(duration_ms)
            if not success:
                self._errors_total += 1
                self._errors_per_backend[backend_name] += 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            latency_percentiles: dict[str, dict[str, float]] = {}
            for name, values in self._latencies.items():
                if values:
                    snapshot = list(values)
                    latency_percentiles[name] = {
                        "p50": statistics.median(snapshot),
                        "p95": self._percentile(snapshot, 95),
                        "p99": self._percentile(snapshot, 99),
                    }
                else:
                    latency_percentiles[name] = {"p50": 0.0, "p95": 0.0, "p99": 0.0}

            return {
                "requests_total": self._requests_total,
                "requests_per_backend": dict(self._per_backend),
                "errors_total": self._errors_total,
                "errors_per_backend": dict(self._errors_per_backend),
                "backend_latency_ms": latency_percentiles,
            }

    @staticmethod
    def _percentile(values: list[float], pct: int) -> float:
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_vals):
            return sorted_vals[-1]
        return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


class MetricsMiddleware(Middleware):
    """FastMCP middleware that records per-backend request metrics.

    Resolves the backend by matching the called tool name against the
    configured backend prefixes. With a single backend FastMCP does not
    add a prefix, so we attribute calls directly.
    """

    def __init__(
        self,
        metrics: Metrics,
        backends: Callable[[], list[str]],
    ) -> None:
        super().__init__()
        self._metrics = metrics
        self._backends = backends

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        start = time.monotonic()
        success = True
        try:
            return await call_next(context)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            tool_name = getattr(getattr(context, "message", None), "name", "") or ""
            backend = self._resolve_backend(tool_name)
            self._metrics.record_request(backend, duration_ms, success)

    def _resolve_backend(self, tool_name: str) -> str:
        names = self._backends()
        if not names:
            return "unknown"
        if len(names) == 1:
            return names[0]
        for name in names:
            if tool_name == name or tool_name.startswith(name + "_"):
                return name
        return "unknown"
