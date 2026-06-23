from __future__ import annotations

import asyncio
from typing import TypeVar, Callable, Any

T = TypeVar("T")

MAX_RETRIES = 2
BACKOFF_SECONDS = [1.0, 2.0]
RETRYABLE_STATUS = {429, 502, 503, 504}


async def with_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    retryable_exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]