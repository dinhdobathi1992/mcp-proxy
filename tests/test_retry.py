from __future__ import annotations

import pytest

from mcp_proxy.retry import RetryPolicy, with_retry


class TestRetryPolicy:
    def test_defaults(self):
        policy = RetryPolicy()
        assert policy.max_retries == 3
        assert policy.initial_backoff == 0.1

    def test_custom_values(self):
        policy = RetryPolicy(max_retries=5, initial_backoff=0.5)
        assert policy.max_retries == 5
        assert policy.initial_backoff == 0.5


class TestWithRetry:
    def test_success_no_retry(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = with_retry(fn, RetryPolicy(max_retries=3))
        assert result == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        result = with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.01))
        assert result == "ok"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        def fn():
            raise ConnectionError("always fail")

        with pytest.raises(ConnectionError):
            with_retry(fn, RetryPolicy(max_retries=2, initial_backoff=0.01))

    def test_no_retry_on_non_retryable_error(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.01))
        assert call_count == 1

    def test_exponential_backoff(self):
        import time

        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        start = time.monotonic()
        with_retry(fn, RetryPolicy(max_retries=3, initial_backoff=0.05))
        elapsed = time.monotonic() - start
        assert elapsed >= 0.1
