"""Reusable batching utilities with explicit ID preservation.

Never depend on response ordering alone: every batch carries the caller
supplied IDs through so JEV answers can be mapped back deterministically.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")


def batch_list(items: Sequence[T], batch_size: int) -> Iterator[list[T]]:
    """Generic batching helper used for results, blocks, and fetch jobs."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for i in range(0, len(items), batch_size):
        yield list(items[i : i + batch_size])


def batched_with_ids(
    ids: Sequence[str], lookup: dict[str, T], batch_size: int
) -> Iterator[list[tuple[str, T]]]:
    """Yield ``(id, item)`` batches; raises KeyError on unknown IDs."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    for i in range(0, len(ids), batch_size):
        group = ids[i : i + batch_size]
        yield [(cid, lookup[cid]) for cid in group]
