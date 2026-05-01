from __future__ import annotations

import statistics
import threading
from collections import defaultdict
from typing import Any


class Metrics:
    """Thread-safe in-memory metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._per_backend: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)

    def record_request(self, backend_name: str, duration_ms: float, success: bool) -> None:
        with self._lock:
            self._requests_total += 1
            self._per_backend[backend_name] += 1
            self._latencies[backend_name].append(duration_ms)
            if not success:
                self._errors_total += 1

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            latency_percentiles: dict[str, dict[str, float]] = {}
            for name, values in self._latencies.items():
                if values:
                    latency_percentiles[name] = {
                        "p50": statistics.median(values),
                        "p95": self._percentile(values, 95),
                        "p99": self._percentile(values, 99),
                    }
                else:
                    latency_percentiles[name] = {"p50": 0.0, "p95": 0.0, "p99": 0.0}

            return {
                "requests_total": self._requests_total,
                "requests_per_backend": dict(self._per_backend),
                "errors_total": self._errors_total,
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
