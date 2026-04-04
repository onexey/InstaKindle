"""Retry utilities for transient network failures.

Provides a lightweight retry decorator with exponential backoff for
network-bound operations (API calls, image downloads, SMTP sending).

Usage:
    @retry(max_attempts=3, backoff_factor=2.0, exceptions=(RequestException,))
    def fetch_data():
        ...

Any new network-facing function should use this decorator (or the
``urllib3.util.Retry`` adapter on a ``requests.Session``) to handle
transient errors gracefully.  See ``docs/development.md`` for details.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    *,
    exceptions: tuple[type[BaseException], ...],
) -> Callable[[_F], _F]:
    """Decorator that retries a function on specified exceptions.

    Args:
        max_attempts: Total number of attempts (including the first call).
            Must be at least 1.
        backoff_factor: Multiplier for exponential wait between retries.
            Wait time for attempt *n* (0-indexed) is ``backoff_factor ** n``
            seconds (i.e. 1 s, 2 s, 4 s for the default factor of 2.0).
            Must be positive.
        exceptions: Tuple of exception types that trigger a retry.
            This is a required keyword-only argument to prevent accidentally
            retrying on all exceptions.

    Returns:
        The decorated function.

    Raises:
        ValueError: If ``max_attempts < 1`` or ``backoff_factor <= 0``.
        The last caught exception if all attempts are exhausted.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
    if backoff_factor <= 0:
        raise ValueError(f"backoff_factor must be > 0, got {backoff_factor}")

    def decorator(func: _F) -> _F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_factor**attempt
                    logger.warning(
                        "Attempt %d/%d for %s failed, retrying in %.1fs...",
                        attempt + 1,
                        max_attempts,
                        getattr(func, "__qualname__", getattr(func, "__name__", repr(func))),
                        wait,
                    )
                    time.sleep(wait)

        return wrapper  # type: ignore[return-value]

    return decorator
