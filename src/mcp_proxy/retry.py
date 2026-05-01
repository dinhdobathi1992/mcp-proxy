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

    last_error: Exception | None = None
    backoff = policy.initial_backoff

    for attempt in range(policy.max_retries + 1):
        try:
            return fn()
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < policy.max_retries:
                time.sleep(backoff)
                backoff *= policy.backoff_multiplier
            else:
                raise
        except Exception:
            raise

    raise last_error  # type: ignore[misc]
