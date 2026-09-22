"""Bounded retry for transient JEV/upstream failures only.

Retried: transport connection errors, timeouts, HTTP 429 (rate limit),
HTTP 529 (overloaded). Never retried: auth (401/403), validation (422/400),
security rejections, malformed responses.

The official SDK already retries some errors internally (see its
RetryPolicy defaults). To avoid nested retry storms, the SDK provider keeps
the SDK's default policy but adds an outer retry *only* for
rate-limit/overload errors, capped at ``MAX_TRANSIENT_RETRIES`` with
exponential backoff. The HTTP fallback provider (no SDK retry inside) uses
the same cap for all transient classes.
"""

from __future__ import annotations

import asyncio

from ..errors import ErrorCode, EvidenceError

MAX_TRANSIENT_RETRIES = 2
BACKOFF_BASE_SECONDS = 0.5

RETRYABLE_STATUS_CODES = {408, 429, 502, 503, 504, 529}


def backoff_delay_seconds(attempt: int) -> float:
    """attempt is 1-based: 0.5s, 1.0s, 2.0s, ... capped at 5s."""
    return min(BACKOFF_BASE_SECONDS * (2.0 ** (attempt - 1)), 5.0)


async def sleep_backoff(attempt: int) -> None:
    await asyncio.sleep(backoff_delay_seconds(attempt))


class RetryableJevError(EvidenceError):
    """Transient JEV failure (rate limit / overload / transport).

    A distinct subclass so retry loops can match on type instead of
    sniffing message strings. Still an EvidenceError with code JEV_ERROR.
    """

    def __init__(self, message: str, code: ErrorCode = ErrorCode.JEV_ERROR) -> None:
        super().__init__(code, message)
