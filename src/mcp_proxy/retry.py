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

    backoff = policy.initial_backoff

    for attempt in range(policy.max_retries + 1):
        try:
            return fn()
        except RETRYABLE_ERRORS:
            if attempt >= policy.max_retries:
                raise
            time.sleep(backoff)
            backoff *= policy.backoff_multiplier

    raise RuntimeError("with_retry exited loop without returning")  # pragma: no cover
