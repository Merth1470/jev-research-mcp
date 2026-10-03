"""In-memory cache: TTL expiry, disable flag, bounded eviction."""

from __future__ import annotations

import time

from jev_research_mcp.cache import MemoryCache


def test_put_get_roundtrip() -> None:
    cache: MemoryCache[str] = MemoryCache(ttl_seconds=60.0)
    cache.put("https://x.com/", "page")
    assert cache.get("https://x.com/") == "page"
    assert cache.get("https://missing/") is None


def test_disabled_cache_never_stores() -> None:
    cache: MemoryCache[str] = MemoryCache(ttl_seconds=0.0)
    assert cache.enabled is False
    cache.put("k", "v")
    assert cache.get("k") is None


def test_expired_entries_miss() -> None:
    cache: MemoryCache[str] = MemoryCache(ttl_seconds=0.01)
    cache.put("k", "v")
    time.sleep(0.02)
    assert cache.get("k") is None


def test_bounded_eviction() -> None:
    cache: MemoryCache[int] = MemoryCache(ttl_seconds=60.0, max_entries=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None
    assert cache.get("c") == 3
