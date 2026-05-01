from __future__ import annotations

import pytest

from mcp_proxy.metrics import Metrics


class TestMetrics:
    def test_record_request_increments_total(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("echo", 20.0, True)
        metrics = m.get_metrics()
        assert metrics["requests_total"] == 2

    def test_record_request_per_backend(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("math", 15.0, True)
        m.record_request("echo", 12.0, True)
        metrics = m.get_metrics()
        assert metrics["requests_per_backend"]["echo"] == 2
        assert metrics["requests_per_backend"]["math"] == 1

    def test_error_counter(self):
        m = Metrics()
        m.record_request("echo", 10.0, True)
        m.record_request("echo", 10.0, False)
        m.record_request("math", 10.0, False)
        metrics = m.get_metrics()
        assert metrics["errors_total"] == 2

    def test_latency_percentiles(self):
        m = Metrics()
        for i in range(100):
            m.record_request("echo", float(i), True)
        metrics = m.get_metrics()
        latency = metrics["backend_latency_ms"]["echo"]
        assert "p50" in latency
        assert "p95" in latency
        assert "p99" in latency
        assert 45 <= latency["p50"] <= 55
        assert 90 <= latency["p95"] <= 99

    def test_empty_metrics(self):
        m = Metrics()
        metrics = m.get_metrics()
        assert metrics["requests_total"] == 0
        assert metrics["errors_total"] == 0
        assert metrics["requests_per_backend"] == {}
