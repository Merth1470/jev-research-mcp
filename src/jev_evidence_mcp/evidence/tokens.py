"""Token budgeting with a documented approximation.

V1 uses ``estimate_tokens(text) = ceil(chars / 4)`` — a clearly labeled
approximation, NOT an exact tokenizer count. Selection keeps whole blocks
(code blocks are never cut in half); a single over-budget block is kept
whole and stops the budget rather than being sliced.
"""

from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Approximate token count (chars/4, rounded up). Documented estimate."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def fits_in_budget(texts: list[str], max_tokens: int) -> list[int]:
    """Return indices that fit in budget, preserving input order."""
    kept: list[int] = []
    used = 0
    for index, text in enumerate(texts):
        cost = estimate_tokens(text)
        if used + cost > max_tokens:
            # A single first item that alone exceeds the budget is still
            # kept whole (never slice evidence); it just consumes the budget.
            if not kept:
                kept.append(index)
            break
        kept.append(index)
        used += cost
    return kept
