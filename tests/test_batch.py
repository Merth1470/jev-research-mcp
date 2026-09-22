"""Batching: ID-preserving chunks for results, blocks, fetch jobs."""

from __future__ import annotations

import pytest

from jev_evidence_mcp.batch import batch_list, batched_with_ids


def test_batch_list_even_split() -> None:
    assert list(batch_list([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]


def test_batch_list_remainder() -> None:
    assert list(batch_list([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_batch_list_larger_than_input() -> None:
    assert list(batch_list([1, 2], 20)) == [[1, 2]]


def test_batch_list_empty() -> None:
    assert list(batch_list([], 5)) == []


def test_batch_list_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        list(batch_list([1], 0))


def test_batched_with_ids_preserves_mapping() -> None:
    lookup = {"r0": "a", "r1": "b", "r2": "c"}
    batches = list(batched_with_ids(["r0", "r1", "r2"], lookup, 2))
    assert batches == [[("r0", "a"), ("r1", "b")], [("r2", "c")]]


def test_batched_with_ids_unknown_id_raises() -> None:
    with pytest.raises(KeyError):
        list(batched_with_ids(["r9"], {}, 5))
