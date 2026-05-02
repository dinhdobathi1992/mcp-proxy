from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")

RETRYABLE_ERRORS = (ConnectionError, OSError, TimeoutError)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_backoff: float = 0.1
    backoff_multiplier: float = 2.0


def with_retry(
    fn: Callable[..., T],
    policy: RetryPolicy | None = None,
) -> T:
    """Execute fn with retry on transient errors."""
    if policy is None:
        policy = RetryPolicy()
    if policy.max_retries < 0:
        raise ValueError("max_retries must be non-negative")

    backoff = policy.initial_backoff
    attempt = 0
    while True:
        try:
            return fn()
        except RETRYABLE_ERRORS:
            if attempt >= policy.max_retries:
                raise
            attempt += 1
            time.sleep(backoff)
            backoff *= policy.backoff_multiplier
