"""Small local in-memory cache (no infrastructure).

Keys account for URL only (GET semantics); entries expire after TTL.
Disabled when ``CACHE_TTL_SECONDS`` is 0 or ``ENABLE_CACHE`` is false.
Documented behavior: process-local, bounded size, no sensitive data written
to disk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class MemoryCache(Generic[T]):
    def __init__(self, *, ttl_seconds: float = 3600.0, max_entries: int = 200) -> None:
        self._ttl = max(0.0, ttl_seconds)
        self._max = max(1, max_entries)
        self._store: dict[str, _Entry[T]] = {}

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def get(self, key: str) -> T | None:
        if not self.enabled:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            self._store.pop(key, None)
            return None
        return entry.value

    def put(self, key: str, value: T) -> None:
        if not self.enabled:
            return
        if len(self._store) >= self._max:
            # Evict the entry with the earliest expiry (simple + deterministic).
            oldest = min(self._store.items(), key=lambda kv: kv[1].expires_at)[0]
            self._store.pop(oldest, None)
        self._store[key] = _Entry(value=value, expires_at=time.monotonic() + self._ttl)

    def clear(self) -> None:
        self._store.clear()
