"""JEV question design (explicit decision contracts, batched).

Result-level: one shared state (task + normalized candidates), three Noul
properties per candidate: relevant / useful / authoritative.
Block-level: two Noul properties per block: relevant / actionable.

Question IDs are ``"<property>__<candidate_id>"`` so answers map back
deterministically without depending on response ordering.
"""

from __future__ import annotations

from typing import Any

from ..models import Block, SearchResult

# --- Explicit decision contracts (interpretation is fixed, not vague) ---

RESULT_QUESTIONS: dict[str, str] = {
    "relevant": (
        "Is this search result materially relevant to answering the user's research task? "
        "Answer yes only if the title, URL, and snippet indicate the page is about the task."
    ),
    "useful": (
        "Is this result likely to contain concrete information that a coding agent could use "
        "to solve the task (documentation, code, configuration, error messages, API details)? "
        "Answer yes only for pages likely to hold directly usable technical content."
    ),
    "authoritative": (
        "Does this source appear sufficiently authoritative or technically credible for this task "
        "(official docs, primary source, reputable technical publication)?"
    ),
}

BLOCK_QUESTIONS: dict[str, str] = {
    "relevant": (
        "Is this content block materially relevant to answering the user's coding/research task? "
        "Answer yes only if the block is about the task, not merely from a related page."
    ),
    "actionable": (
        "Does this block contain information that a coding agent could directly use to implement, "
        "configure, debug, or understand the requested functionality "
        "(code, commands, configuration values, API signatures, error causes/fixes, version facts)?"
    ),
}

RESULT_PROPERTIES = ("relevant", "useful", "authoritative")
BLOCK_PROPERTIES = ("relevant", "actionable")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def build_result_state(
    query: str,
    results: list[SearchResult],
    *,
    max_state_chars: int = 80_000,
    max_snippet_chars: int = 600,
) -> dict[str, Any]:
    """One shared state object: the task plus all normalized candidates."""
    candidates: list[dict[str, Any]] = []
    for result in results:
        candidates.append(
            {
                "id": result.id,
                "title": _truncate(result.title, 300),
                "url": result.url,
                "domain": result.domain,
                "snippet": _truncate(result.snippet, max_snippet_chars),
            }
        )
    state: dict[str, Any] = {"task": query, "candidates": candidates}
    # Hard cap: truncate snippets progressively rather than dropping candidates.
    import json as _json

    serialized = _json.dumps(state)
    if len(serialized) > max_state_chars and candidates:
        budget = max(100, max_snippet_chars // 2)
        for cand in candidates:
            cand["snippet"] = _truncate(str(cand["snippet"]), budget)
        state = {"task": _truncate(query, 2000), "candidates": candidates}
    return state


def build_result_questions(
    results: list[SearchResult],
    *,
    properties: tuple[str, ...] = RESULT_PROPERTIES,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Return (questions, meta) with one Noul question per (property, result)."""
    questions: dict[str, dict[str, Any]] = {}
    meta: dict[str, str] = {}
    for result in results:
        for prop in properties:
            qid = f"{prop}__{result.id}"
            questions[qid] = {
                "type": "noul",
                "instructions": (
                    f"{RESULT_QUESTIONS[prop]} Candidate id {result.id}: "
                    f"title={result.title!r} url={result.url!r} "
                    f"domain={result.domain!r} snippet={result.snippet!r}"
                ),
            }
            meta[qid] = f"{prop}__{result.id}"
    return questions, meta


def build_block_state(
    query: str,
    blocks: list[Block],
    *,
    source_url: str = "",
    max_block_chars: int = 2_000,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for block in blocks:
        items.append(
            {
                "id": block.id,
                "type": block.type.value,
                "parent_heading": block.parent_heading or "",
                "text": _truncate(block.text, max_block_chars),
            }
        )
    return {"task": query, "source_url": source_url, "blocks": items}


def build_block_questions(
    blocks: list[Block],
    *,
    properties: tuple[str, ...] = BLOCK_PROPERTIES,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    questions: dict[str, dict[str, Any]] = {}
    meta: dict[str, str] = {}
    for block in blocks:
        heading = f" Under heading {block.parent_heading!r}." if block.parent_heading else ""
        for prop in properties:
            qid = f"{prop}__{block.id}"
            questions[qid] = {
                "type": "noul",
                "instructions": (
                    f"{BLOCK_QUESTIONS[prop]} Block id {block.id} "
                    f"(type {block.type.value}).{heading} Content: {block.text!r}"
                ),
            }
            meta[qid] = f"{prop}__{block.id}"
    return questions, meta
