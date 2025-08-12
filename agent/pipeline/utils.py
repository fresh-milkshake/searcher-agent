"""Utility helpers for the research pipeline.

This module currently provides a small set of runtime helpers that are reused
across pipeline stages. The public API is intentionally minimal and stable.

Example::

    from agent.pipeline.utils import retry_async

    async def fetch():
        # some flaky network call
        return 42

    result = await retry_async(lambda: fetch(), attempts=3, base_delay=1.0)
    assert result == 42
"""

import asyncio
from typing import Awaitable, Callable, Optional, TypeVar

from shared.logger import get_logger


logger = get_logger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 5.0,
    factor: float = 2.0,
) -> T:
    """Retry an async operation with exponential backoff.

    :param func: Zero-argument coroutine factory to call on each attempt. Using a
                 factory defers creation of the coroutine until it is awaited,
                 avoiding "already awaited" errors on retries.
    :param attempts: Total attempts including the first call (>= 1). Default 3.
    :param base_delay: Initial delay in seconds before the next attempt. Default 5.0.
    :param factor: Multiplicative backoff factor after each failure. Default 2.0.
    :returns: The value returned by the successful call to ``func``.
    :raises Exception: Re-raises the last exception encountered if all attempts fail.

    Example::

        async def get_value() -> int:
            return 7

        value = await retry_async(lambda: get_value(), attempts=5, base_delay=0.2)
        assert value == 7
    """
    delay = base_delay
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt >= attempts:
                break
            logger.warning(
                f"Retryable error on attempt {attempt}/{attempts}: {error}. Sleeping {delay:.1f}s"
            )
            await asyncio.sleep(delay)
            delay *= factor
    assert last_error is not None
    raise last_error
