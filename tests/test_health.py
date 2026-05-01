from __future__ import annotations

import pytest

from mcp_proxy.health import HealthChecker, HealthStatus


class TestHealthStatus:
    def test_initial_state_is_unknown(self):
        checker = HealthChecker(backends=[], interval=1.0)
        assert checker.get_status("any") == HealthStatus.UNKNOWN

    def test_get_all_status_empty(self):
        checker = HealthChecker(backends=[], interval=1.0)
        assert checker.get_all_status() == {}


class TestHealthCheckerLifecycle:
    def test_start_and_stop(self):
        checker = HealthChecker(backends=[], interval=1.0)
        checker.start()
        assert checker._task is not None
        checker.stop()
        assert checker._task is None

    def test_stop_without_start_is_noop(self):
        checker = HealthChecker(backends=[], interval=1.0)
        checker.stop()  # Should not raise
