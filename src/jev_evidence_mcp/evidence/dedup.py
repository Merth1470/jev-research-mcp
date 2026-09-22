"""Deterministic exact deduplication (no embeddings in V1).

Normalization: collapse whitespace runs, strip trivial formatting
surrounding the text, lowercase only for comparison (original text kept).
Identical hashes collapse to one item; provenance of dropped duplicates is
recorded so callers can see which URLs carried the same content.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_WS_RUN = re.compile(r"\s+")


def normalize_for_hash(text: str) -> str:
    collapsed = _WS_RUN.sub(" ", text).strip()
    # Strip trivial markdown fencing for comparison only.
    collapsed = collapsed.strip("`").strip()
    return collapsed.casefold()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_for_hash(text).encode("utf-8")).hexdigest()


@dataclass
class DedupResult:
    items: list[int]  # indices into the input list that survive
    dropped: dict[int, str] = field(default_factory=dict)  # dropped idx -> reason
    duplicate_of: dict[int, int] = field(default_factory=dict)  # dropped idx -> kept idx


def deduplicate(texts: list[str]) -> DedupResult:
    seen: dict[str, int] = {}
    kept: list[int] = []
    dropped: dict[int, str] = {}
    duplicate_of: dict[int, int] = {}
    for index, text in enumerate(texts):
        if not text.strip():
            dropped[index] = "empty"
            continue
        digest = content_hash(text)
        if digest in seen:
            dropped[index] = "exact-duplicate"
            duplicate_of[index] = seen[digest]
        else:
            seen[digest] = index
            kept.append(index)
    return DedupResult(items=kept, dropped=dropped, duplicate_of=duplicate_of)
