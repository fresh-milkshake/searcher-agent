"""Utility helpers for pipeline"""

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

    Args:
        func: Zero-arg coroutine factory to call each attempt.
        attempts: Total attempts (including the first).
        base_delay: Initial delay in seconds before the next try.
        factor: Multiplier applied to delay after each failure.

    Raises:
        The last exception if all attempts fail.
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
