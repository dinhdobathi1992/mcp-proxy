from __future__ import annotations

import time

import pytest

from mcp_proxy.auth import APIKeyAuth, RateLimiter


class TestAPIKeyAuth:
    def test_no_key_configured_allows_all(self):
        auth = APIKeyAuth(api_key=None)
        assert auth.validate("Bearer anything") is True
        assert auth.validate("") is True

    def test_valid_key_accepted(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Bearer secret123") is True

    def test_invalid_key_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Bearer wrong") is False

    def test_missing_header_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("") is False
        assert auth.validate(None) is False

    def test_malformed_header_rejected(self):
        auth = APIKeyAuth(api_key="secret123")
        assert auth.validate("Basic secret123") is False


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.allow("127.0.0.1") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is False

    def test_different_ips_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.1") is True
        assert limiter.allow("10.0.0.2") is True
        assert limiter.allow("10.0.0.2") is True
        assert limiter.allow("10.0.0.1") is False
        assert limiter.allow("10.0.0.2") is False

    def test_window_expiry_resets(self):
        limiter = RateLimiter(max_requests=2, window_seconds=0.1)
        assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is True
        assert limiter.allow("127.0.0.1") is False
        time.sleep(0.15)
        assert limiter.allow("127.0.0.1") is True
